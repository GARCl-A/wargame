"""The build's version, written into every save. `docs/versions.csv` is the table of releases;
`scripts/version_check.py` (run by `build_exe.bat`) keeps it honest."""

import subprocess

GAME_VERSION = "0.1.5"


def build_hash():
    """Short commit of this build: baked in by the build script, else read from git, else 'unknown'."""
    try:
        from .build_info import BUILD_HASH
        return BUILD_HASH
    except ImportError:
        pass
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             timeout=5, cwd=__file__.rsplit("gartok", 1)[0] or ".")
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
