"""The game's sounds: each cue name plays one of a few variants from `assets/sounds/`
(Kenney and StarNinjas, CC0, `LICENSE.txt` there) at the player's `volume` setting.

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
    "dice": ("die-throw-1.ogg", "die-throw-2.ogg", "die-throw-3.ogg"),
    "eat": tuple(f"crunch_{i}.ogg" for i in range(1, 8)),
}

# The music is a radio on the map and menus (one track, then 30 to 60 seconds of silence, then the next) and,
# in a fight, one battle track picked at random; both fade in and out. Files live in `assets/music/`.
MUSIC = {
    "radio": ("Exploration.mp3", "The_Old_Tower_Inn.mp3", "Minstrel_Dance.mp3", "The_Bards_Tale.mp3"),
    "battle": ("QaziJamJam.mp3", "Determined_Pursuit.mp3", "Battle_Theme.mp3"),
}
MUSIC_SILENCE = (30, 60)    # seconds of quiet between two radio tracks, drawn each time
MUSIC_FADE = 1.5            # seconds
MUSIC_LEVEL = 0.6           # where the music sits against the effects, before the player's setting

# how loud each cue sits against the others, before the player's volume
LEVEL = {"hit": 0.7, "crit": 0.9, "miss": 0.5, "fall": 0.8, "coins": 0.7, "level_up": 0.5, "click": 0.35, "eat": 0.6, "dice": 0.6}
