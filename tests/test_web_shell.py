"""The server under the native client (`python -m gartok --shell`, the `shell/` folder): where it keeps the
player's files and how it stops with no window of its own."""

import io
import json
import os
import queue
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

from gartok import persist, settings
from gartok.web import __main__ as launcher

ROOT = Path(__file__).resolve().parent.parent


def test_the_data_folder_is_the_clients_then_the_exes_then_the_repos():
    assert persist.data_dir({"GARTOK_DATA_DIR": "C:/Users/x/AppData/GARTOK"}, True, "C:/game/GARTOK.exe") \
        == "C:/Users/x/AppData/GARTOK"
    assert persist.data_dir({}, True, os.path.join("C:/game", "gartok-server.exe")) == "C:/game"
    assert persist.data_dir({"GARTOK_DATA_DIR": ""}, False, "python") == str(ROOT)
    assert persist.data_dir({}, False, "python") == str(ROOT)


def test_the_settings_file_lives_in_the_data_folder():
    assert settings.PATH == os.path.join(persist.DATA_DIR, "settings.json")


def test_a_setting_is_kept_even_when_the_data_folder_is_not_there_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PATH", str(tmp_path / "GARTOK" / "settings.json"))
    settings.reload()
    try:
        settings.put("volume", 25)
        settings.reload()
        assert settings.get("volume") == 25
    finally:
        settings.reload()


def test_the_server_stops_when_its_stdin_ends():
    stopped = []
    launcher._stop_on_eof(io.StringIO(""), lambda: stopped.append(True))
    assert stopped == [True]


class _Server:
    """`python -m gartok --shell` as the native client starts it: stdin and stdout are pipes, the data folder
    does not exist yet."""

    def __init__(self, data_dir):
        env = {**os.environ, "GARTOK_DATA_DIR": str(data_dir)}
        self.proc = subprocess.Popen([sys.executable, "-m", "gartok", "--shell"], cwd=ROOT, env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        first = queue.Queue()
        threading.Thread(target=lambda: first.put(self.proc.stdout.readline()), daemon=True).start()
        try:
            line = first.get(timeout=60)
        except queue.Empty:
            self.proc.kill()
            raise AssertionError("the server printed no URL line") from None
        assert line.startswith("GARTOK web: http://127.0.0.1:"), line
        self.url = line.split()[2]

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=30) as r:
            return json.loads(r.read())

    def post(self, path):
        req = urllib.request.Request(self.url + path, data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=10)
        self.proc.stdout.close()


@pytest.fixture
def shell_server(tmp_path):
    srv = _Server(tmp_path / "fresh" / "GARTOK")
    yield srv
    srv.close()


def test_the_server_serves_a_first_run_and_exits_clean_when_the_client_closes_its_stdin(shell_server):
    assert shell_server.get("/api/screen")["screen"] == "title"
    assert shell_server.get("/api/title/state")                 # no saves folder yet: an empty list of guilds
    shell_server.proc.stdin.close()
    assert shell_server.proc.wait(timeout=10) == 0


def test_the_server_exits_clean_when_the_player_quits_in_the_game(shell_server):
    assert shell_server.post("/api/title/quit")["quit"] is True
    assert shell_server.proc.wait(timeout=10) == 0
