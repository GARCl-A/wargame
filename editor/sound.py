"""The Editor's player for the game's sound cues (`gartok.sound`): pygame's mixer, silent until `enable()`,
so tests never open an audio device and a machine with none stays silent too."""

import os
import random

from gartok import settings
from gartok.sound import CUES, DIR, LEVEL

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
