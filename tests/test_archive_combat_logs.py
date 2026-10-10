"""scripts/archive_combat_logs.py: campaign combat logs copied out of the untracked saves/ folder."""

import json
import os
import sys

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS)
import archive_combat_logs as arch


def _world(saves, world_id, name, logs):
    d = saves / world_id
    (d / "combat_logs").mkdir(parents=True)
    (d / "current.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    for fname, body in logs.items():
        (d / "combat_logs" / fname).write_text(body, encoding="utf-8")


def test_each_guild_gets_a_folder_and_a_second_run_copies_only_what_is_new(tmp_path, monkeypatch):
    saves, archive = tmp_path / "saves", tmp_path / "combat_lab" / "campaign"
    monkeypatch.setattr(arch, "SAVES", str(saves))
    monkeypatch.setattr(arch, "ARCHIVE", str(archive))
    _world(saves, "ab12", "Green Guild!", {"d005-arena.jsonl": "one\n"})

    assert arch.archive() == {"Green-Guild-ab12": ["d005-arena.jsonl"]}
    assert (archive / "Green-Guild-ab12" / "d005-arena.jsonl").read_text(encoding="utf-8") == "one\n"
    assert arch.archive() == {}

    (saves / "ab12" / "combat_logs" / "d006-hunt.jsonl").write_text("two\n", encoding="utf-8")
    assert arch.archive() == {"Green-Guild-ab12": ["d006-hunt.jsonl"]}


def test_dry_run_copies_nothing_and_a_world_without_logs_is_skipped(tmp_path, monkeypatch):
    saves, archive = tmp_path / "saves", tmp_path / "archive"
    monkeypatch.setattr(arch, "SAVES", str(saves))
    monkeypatch.setattr(arch, "ARCHIVE", str(archive))
    _world(saves, "ab12", "G", {"d001-x.jsonl": "x"})
    (saves / "cd34").mkdir()

    assert arch.archive(dry_run=True) == {"G-ab12": ["d001-x.jsonl"]}
    assert not archive.exists()
