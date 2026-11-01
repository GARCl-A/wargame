import csv
import os

from gartok import persist
from gartok.version import GAME_VERSION
from scripts import version_check

ROW = {"version": GAME_VERSION, "date": "2026-11-01", "hash": "abc", "save_version": str(persist.SAVE_VERSION),
       "breaks_save": "yes", "path": ""}


def test_matching_table_has_no_errors_and_warns_when_head_moved():
    assert version_check.check([ROW], "abc", False) == ([], [])
    errors, warnings = version_check.check([ROW], "", True)
    assert not errors and len(warnings) == 1


def test_a_moved_save_version_or_game_version_is_an_error():
    errors, _ = version_check.check([{**ROW, "save_version": "-1"}], "abc", False)
    assert "saves break" in errors[0]
    errors, _ = version_check.check([{**ROW, "version": "9.9.9"}], "abc", False)
    assert "GAME_VERSION" in errors[0]
    assert version_check.check([], "abc", False)[0]


def test_the_shipped_table_matches_the_code():
    path = os.path.join(version_check.ROOT, "docs", "versions.csv")
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert version_check.check(rows, "", False)[0] == []
