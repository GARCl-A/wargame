"""Static checks that catch what only blows up on a rarely-drawn code path."""

import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent / "gartok"


def test_no_undefined_names_in_the_package():
    """A name used but never imported only blows up when that code path draws
    (the guard screen shipped once without `caps` imported)."""
    try:
        r = subprocess.run([sys.executable, "-m", "ruff", "check", str(PKG),
                            "--select", "F821", "--no-cache"],
                           capture_output=True, text=True)
    except OSError:
        pytest.skip("ruff unavailable")
    if "No module named ruff" in r.stderr:
        pytest.skip("ruff unavailable")
    assert r.returncode == 0, r.stdout
