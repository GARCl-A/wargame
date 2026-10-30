"""The log on the board: the hit flash, the crit banner, and the sounds the same events fire."""

from gartok import settings

def test_volume_label():
    assert settings.SPEC["volume"][2] in settings.SPEC["volume"][1]
    monkey = settings._values
    try:
        settings._values = {**{k: d for k, (_, _, d) in settings.SPEC.items()}, "volume": 0}
        assert settings.label("volume") == "VOLUME: OFF"
        settings._values["volume"] = 50
        assert settings.label("volume") == "VOLUME: 50%"
    finally:
        settings._values = monkey
