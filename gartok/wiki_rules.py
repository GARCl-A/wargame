"""The wiki's RULES tab: the rules a player looks up mid-run, read off the live constants.

`sections()` is `[(title, [line, ...])]`; the numbers come from the modules that run the rule,
so the page moves with them. RULES.md stays the designer's full prose.
"""

from . import (
    actions,
    captives,
    cohesion,
    dialogue,
    group,
    i18n,
    items,
    morale,
    recruit,
    wagon,
)
from .combatant import AP_PER_TURN


def _lines(section, n, **fmt):
    return [i18n.t(f"wiki_rules.{section}.{i}", **fmt) for i in range(1, n + 1)]


def _morale_lines():
    half, quarter = morale.HP_MARKS_ONCE
    return _lines(
        "morale", 7, base=morale.BASE, per=morale.PER_RACIAL_LEVEL, lawful=f"{morale.LAWFUL:+d}",
        chaotic=f"{morale.CHAOTIC:+d}", min=morale.START_MIN, ally_down=-morale.ALLY_DOWN, ally_dead=-morale.ALLY_DEAD,
        wound=-morale.HP_MARK, half=round(half * 100), quarter=round(quarter * 100),
        low=round(morale.HP_MARK_EVERY * 100), shaken=-morale.DEMORALIZED, foe_down=morale.FOE_DOWN)


def sections():
    reach, hit = 1 + items.get("Glaive").reach, actions.LongThrust.TO_HIT
    terms = " + ".join(i18n.t(f"wiki_rules.term.{label.lower().replace(' ', '_')}") for _, label, _ in group.CAPACITY_TERMS)
    tools = i18n.t("wiki_rules.or").join(i18n.name("item", t) for t in captives.CAPTURE_TOOLS)
    return [
        (i18n.t("wiki_rules.turns.title"), _lines("turns", 7, ap=AP_PER_TURN)),
        (i18n.t("wiki_rules.flanking.title"), _lines("flanking", 4)),
        (i18n.t("wiki_rules.morale.title"), _morale_lines()),
        (i18n.t("wiki_rules.weapon.title"), [*_lines("weapon", 6), i18n.t("wiki_rules.weapon.7", reach=reach, hit=hit)]),
        (i18n.t("wiki_rules.talk.title"), [
            i18n.t("wiki_rules.talk.1", dc=dialogue.BASE_DC),
            i18n.t("wiki_rules.talk.2", cap=dialogue.OUTMATCH_CAP),
            i18n.t("wiki_rules.talk.3", shift=dialogue.ALIGN_SHIFT),
            i18n.t("wiki_rules.talk.4"),
            i18n.t("wiki_rules.talk.5", margin=dialogue.ROUT_MARGIN, edge=dialogue.INITIATIVE_EDGE),
            i18n.t("wiki_rules.talk.6", bribe=dialogue.BRIBE_PER_FOE),
            i18n.t("wiki_rules.talk.7"),
        ]),
        (i18n.t("wiki_rules.recruiting.title"), [
            i18n.t("wiki_rules.recruiting.1"),
            i18n.t("wiki_rules.recruiting.2", pen=recruit.SIZE_PENALTY, free=recruit.FREE_SLOTS),
            i18n.t("wiki_rules.recruiting.3", align=recruit.ALIGNMENT_PENALTY),
            i18n.t("wiki_rules.recruiting.4", base=recruit.BASE_RECRUIT_CAPACITY),
            i18n.t("wiki_rules.recruiting.5"),
            i18n.t("wiki_rules.recruiting.6", tavern=recruit.TAVERNA_SIZE, prison=recruit.PRISON_SIZE, days=recruit.REFRESH_DAYS),
        ]),
        (i18n.t("wiki_rules.groups.title"), [
            i18n.t("wiki_rules.groups.1", base=group.BASE_SLOTS, fame=group.FAME_PER_SLOT),
            i18n.t("wiki_rules.groups.2", cap=group.BASE_CAPACITY, terms=terms, herd=group.HERD_BASE),
            i18n.t("wiki_rules.groups.3", days=cohesion.NOTICE_DAYS),
            i18n.t("wiki_rules.groups.4"),
        ]),
        (i18n.t("wiki_rules.captives.title"), [
            i18n.t("wiki_rules.captives.1", tools=tools),
            i18n.t("wiki_rules.captives.2", weight=captives.HERD_WEIGHT, days=captives.CAPTIVE_DAYS),
            i18n.t("wiki_rules.captives.3"),
        ]),
        (i18n.t("wiki_rules.wagons.title"), [i18n.t("wiki_rules.wagons.1", dist=wagon.WEAR_DISTANCE), *_lines("wagons", 3)[1:]]),
        (i18n.t("wiki_rules.money.title"), _lines("money", 4)),
        (i18n.t("wiki_rules.stomp.title"), _lines("stomp", 2)),
    ]


def matching(query):
    """The sections whose title or a line contains `query` (all of them for an empty one)."""
    q = query.lower()
    return [(t, lines) for t, lines in sections()
            if not q or q in t.lower() or any(q in ln.lower() for ln in lines)]
