"""The Rules chapter's "People & World" sections that are not the recruiting, group and wagon ones:
the numbers read off the modules that run them."""

from . import animals, constants, economy, forced, guild_upkeep, i18n, justice, world


def _lines(section, n, **fmt):
    return [i18n.t(f"wiki_rules.{section}.{i}", **fmt) for i in range(1, n + 1)]


def built():
    return {
        "alignment": _lines("alignment", 2),
        "languages": _lines("languages", 2),
        "leader": _lines("leader", 2),
        "animals": _lines("animals", 2, days=animals.STARVE_DAYS),
        "travel": _lines("travel", 5, chance=round(world.ROAD_AMBUSH_CHANCE * 100)),
        "claim": _lines("claim", 1, days=economy.WILDS_CLAIM_SUSTAIN_DAYS, chance=round(economy.WILDS_RAID_CHANCE * 100),
                        level=economy.WILDS_RAID_LEVEL, size=economy.WILDS_RAID_SIZE),
        "reputation": _lines("reputation", 3),
        "justice": _lines("justice", 5, grace=economy.CITY_PROPERTY_DEBT_GRACE_DAYS, min=justice.GUARD_CHECK_MIN,
                          days=constants.PRISON_DAYS_PER_CRIME, size=constants.PATROL_SIZE, cap=constants.PATROL_LEVEL_CAP,
                          fade=guild_upkeep.CRIME_FADE_DAYS, raid=round(forced.CITY_RAID_CHANCE * 100)),
    }
