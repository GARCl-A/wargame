"""The game's sounds: each cue name plays one of a few variants from `assets/sounds/`
(Kenney, CC0, `LICENSE.txt` there) at the player's `volume` setting.

The web reads `CUES` and `LEVEL` and plays them in the browser; the Editor's own player is
`editor/sound.py`."""

import os

DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds")

CUES = {
    "hit": ("impactPunch_medium_000.ogg", "impactPunch_medium_001.ogg",
            "impactPunch_medium_002.ogg", "impactPunch_medium_003.ogg"),
    "crit": ("impactPlate_heavy_000.ogg", "impactPlate_heavy_001.ogg"),
    "miss": ("cloth1.ogg", "cloth2.ogg", "cloth3.ogg"),
    "fall": ("impactSoft_heavy_000.ogg", "impactSoft_heavy_001.ogg", "impactSoft_heavy_002.ogg"),
    "coins": ("handleCoins.ogg", "handleCoins2.ogg"),
    "level_up": ("confirmation_002.ogg",),
    "click": ("click_002.ogg",),
}

# how loud each cue sits against the others, before the player's volume
LEVEL = {"hit": 0.7, "crit": 0.9, "miss": 0.5, "fall": 0.8, "coins": 0.7, "level_up": 0.8, "click": 0.35}
