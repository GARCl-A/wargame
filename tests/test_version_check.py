import csv

from gartok import persist
from gartok.version import GAME_VERSION
from scripts import version_check

ROW = {"version": GAME_VERSION, "date": "2026-11-01", "hash": "abc", "save_version": str(persist.SAVE_VERSION),
       "breaks_save": "yes", "path": ""}


def test_matching_table_has_no_errors_and_only_stray_dirt_warns():
    assert version_check.check([ROW], []) == ([], [])
    assert version_check.check([ROW], ["docs/versions.csv", "gartok/version.py"]) == ([], [])
    errors, warnings = version_check.check([ROW], ["gartok/unit.py"])
    assert not errors and len(warnings) == 1


def test_a_moved_save_version_or_game_version_is_an_error():
    errors, _ = version_check.check([{**ROW, "save_version": "-1"}], [])
    assert "SAVE_VERSION" in errors[0]
    errors, _ = version_check.check([{**ROW, "version": "9.9.9"}], [])
    assert "GAME_VERSION" in errors[0]
    assert version_check.check([], [])[0]


def test_the_shipped_table_matches_the_code():
    with open(version_check.CSV_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert version_check.check(rows, [])[0] == []


def test_next_version_is_minor_when_saves_break_else_patch():
    assert version_check.next_version("0.1.4", True) == "0.2.0"
    assert version_check.next_version("0.1.4", False) == "0.1.5"


def test_the_probe_reads_a_save_written_by_the_current_code():
    head = version_check.git("rev-parse", "HEAD")
    if not head:
        return
    breaks, reason = version_check.saves_break(head)
    assert not breaks, reason


def test_commits_that_only_touch_the_release_files_are_not_code():
    head = version_check.git("rev-parse", "HEAD")
    assert not version_check.code_changed_since(head, head)
    assert not version_check.code_changed_since("", head)
