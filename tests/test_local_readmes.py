"""gartok/assets/README.md stays true: it lists every icon folder and names only files that exist."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "gartok" / "assets"


def test_assets_readme_names_real_folders_and_files():
    readme = (ASSETS / "README.md").read_text(encoding="utf-8")
    folders = {d.name for d in (ASSETS / "icons").iterdir() if d.is_dir()}
    missing = sorted(f for f in folders if not re.search(rf"\b{f}/", readme))
    assert not missing, f"gartok/assets/README.md does not list icons/{missing}"
    for path in re.findall(r"`((?:gartok|editor)/[\w/]+\.py)`", readme):
        assert (ROOT / path).is_file(), f"gartok/assets/README.md names {path}, which does not exist"
