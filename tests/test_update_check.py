"""The start-up check for a newer release: version comparison, the notice, and silence when offline."""

import io
import json
import threading
import time

import pytest

from gartok import persist, update_check
from gartok.web.title_session import TitleSession


def _opener(payload):
    def opener(req, timeout):
        assert timeout == update_check.TIMEOUT
        return io.BytesIO(json.dumps(payload).encode())
    return opener


def _release(tag, url="https://github.com/GARCl-A/wargame/releases/tag/x"):
    return {"tag_name": tag, "html_url": url}


@pytest.mark.parametrize("tag, current, expected", [
    ("v0.1.16", "0.1.15", True),
    ("v0.1.15", "0.1.15", False),
    ("v0.1.14", "0.1.15", False),
    ("v0.1.9", "0.1.15", False),
    ("v0.2.0", "0.1.15", True),
    ("v1.0", "0.9.9", True),
    ("nightly", "0.1.15", False),
    (None, "0.1.15", False),
])
def test_newer_compares_numbers_not_text(tag, current, expected):
    assert update_check.newer(tag, current) is expected


def test_fetch_returns_the_notice_for_a_newer_release():
    got = update_check.fetch(_opener(_release("v99.0.0")))
    assert got == {"version": "99.0.0", "url": "https://github.com/GARCl-A/wargame/releases/tag/x"}


def test_fetch_is_none_when_up_to_date_offline_or_malformed():
    assert update_check.fetch(_opener(_release("v0.0.1"))) is None
    assert update_check.fetch(_opener(["not", "a", "release"])) is None
    assert update_check.fetch(_opener(_release("v99.0.0", url="https://evil.example/x"))) is None

    def offline(req, timeout):
        raise OSError("no network")
    assert update_check.fetch(offline) is None

    def garbage(req, timeout):
        return io.BytesIO(b"<html>")
    assert update_check.fetch(garbage) is None


def test_start_reports_pending_then_the_answer_through_the_title(tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    release = threading.Event()
    notice = {"version": "9.9.9", "url": "https://github.com/GARCl-A/wargame/releases/tag/v9.9.9"}

    def slow():
        release.wait(5)
        return notice

    update_check.start(slow)
    title = TitleSession()
    assert title.GET["update"](title, {}) == {"pending": True, "update": None}
    release.set()
    for _ in range(100):
        got = title.GET["update"](title, {})
        if not got["pending"]:
            break
        time.sleep(0.02)
    assert got == {"pending": False, "update": notice}
