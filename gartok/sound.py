"""The game's sounds: each cue name plays one of a few variants from `assets/sounds/`
(Kenney, CC0, `LICENSE.txt` there) at the player's `volume` setting.

Silent until `enable()` (the app calls it once), so tests and headless tools never
open an audio device; a machine with none stays silent too. pygame loads only there: the web reads
`CUES` and plays them in the browser."""

import os
import random

from . import settings

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

_sounds = None
_rng = random.Random()      # its own stream: a sound never moves the game's dice


def enable():
    """Open the mixer and load every cue; on a machine with no audio the game stays silent."""
    global _sounds
    import pygame

    _sounds = {}
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        for cue, files in CUES.items():
            _sounds[cue] = [pygame.mixer.Sound(os.path.join(DIR, f)) for f in files]
    except pygame.error:
        _sounds = {}


def play(cue):
    if not _sounds or cue not in _sounds:
        return
    volume = settings.get("volume") / 100
    if volume <= 0:
        return
    snd = _rng.choice(_sounds[cue])
    snd.set_volume(volume * LEVEL[cue])
    snd.play()
