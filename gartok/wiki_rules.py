"""The wiki's RULES tab: the rules a player looks up mid-run, read off the live constants.

`sections()` is `[(key, title, [line, ...])]`; the numbers come from the modules that run the rule,
so the page moves with them. RULES.md stays the designer's full prose.
"""

from . import (
    actions,
    captives,
    cohesion,
    data,
    dialogue,
    economy,
    group,
    i18n,
    intel,
    items,
    morale,
    poisons,
    recruit,
    talents,
    tavern,
    wagon,
)
from .actions.base import OFF_GUARD_AC
from .actions.weapon_actions import BRUTAL, EDGE_DIE, EDGE_TO_HIT, REPEL_CELLS
from .combatant import AP_PER_TURN
from .conditions import DEFEND_AC
from .unit_hunger import HUNGER_PENALTIES, STARVING_HP_MAX


def _lines(section, n, **fmt):
    return [i18n.t(f"wiki_rules.{section}.{i}", **fmt) for i in range(1, n + 1)]


def _morale_lines():
    half, quarter = morale.HP_MARKS_ONCE
    return _lines(
        "morale", 7, base=morale.BASE, per=morale.PER_RACIAL_LEVEL, lawful=f"{morale.LAWFUL:+d}",
        chaotic=f"{morale.CHAOTIC:+d}", min=morale.START_MIN, ally_down=-morale.ALLY_DOWN, ally_dead=-morale.ALLY_DEAD,
        wound=-morale.HP_MARK, half=round(half * 100), quarter=round(quarter * 100),
        low=round(morale.HP_MARK_EVERY * 100), shaken=-morale.DEMORALIZED, foe_down=morale.FOE_DOWN)


def _off_guard_lines():
    relief = int(talents.bonus(["peripheral_vision"], "off_guard_defense"))
    return _lines("flanking", 4, pen=OFF_GUARD_AC, reduced=OFF_GUARD_AC - relief, brutal=BRUTAL,
                  die="d".join(map(str, EDGE_DIE)), hit=EDGE_TO_HIT)


def _weapon_lines(reach, hit):
    return [*_lines("weapon", 6, brutal=BRUTAL, hit=EDGE_TO_HIT, die="d".join(map(str, EDGE_DIE)), cells=REPEL_CELLS),
            i18n.t("wiki_rules.weapon.7", reach=reach, hit=hit)]


def _terms(pairs):
    return " + ".join(i18n.t(f"wiki_rules.term.{label}") for label, _ in pairs)


PARTS = (
    ("combat", ("turns", "flanking", "morale", "weapon", "talk", "stomp", "placement", "reading")),
    ("body", ("hunger", "poison")),
    ("work", ("money", "study")),
    ("world", ("recruiting", "groups", "captives", "wagons", "dungeon")),
)
"""The Rules chapter's subchapters, in reading order, each with the keys of its sections. A key is the
section's id for good (a link to `rules:<key>` survives a retitle or a translation); the title is only
what the player reads."""


def title(key):
    """A section's title as the wiki shows it."""
    return i18n.t(f"wiki_rules.{key}.title")


def part_title(part):
    return i18n.t(f"wiki_rules.part.{part}")


def part_of(key):
    return next(part for part, keys in PARTS if key in keys)


def sections():
    """`[(key, title, [line, ...])]` in the order of `PARTS`."""
    built = _built()
    return [(key, title(key), built[key]) for _, keys in PARTS for key in keys]


def _built():
    reach, hit = 1 + items.get("Glaive").reach, actions.LongThrust.TO_HIT
    terms = " + ".join(i18n.t(f"wiki_rules.term.{label.lower().replace(' ', '_')}") for _, label, _ in group.CAPACITY_TERMS)
    tools = i18n.t("wiki_rules.or").join(i18n.name("item", t) for t in captives.CAPTURE_TOOLS)
    return dict([
        ("turns", _lines("turns", 7, ap=AP_PER_TURN, cost=actions.DEFEND.cost, ac=DEFEND_AC,
                         delay=actions.DELAY.cost, flee=actions.FLEE.cost)),
        ("flanking", _off_guard_lines()),
        ("morale", _morale_lines()),
        ("weapon", _weapon_lines(reach, hit)),
        ("talk", [
            i18n.t("wiki_rules.talk.1", dc=dialogue.BASE_DC),
            i18n.t("wiki_rules.talk.2", cap=dialogue.OUTMATCH_CAP),
            i18n.t("wiki_rules.talk.3", shift=dialogue.ALIGN_SHIFT),
            i18n.t("wiki_rules.talk.4"),
            i18n.t("wiki_rules.talk.5", margin=dialogue.ROUT_MARGIN, edge=dialogue.INITIATIVE_EDGE),
            i18n.t("wiki_rules.talk.6", bribe=dialogue.BRIBE_PER_FOE),
            i18n.t("wiki_rules.talk.7"),
        ]),
        ("recruiting", [
            i18n.t("wiki_rules.recruiting.1"),
            i18n.t("wiki_rules.recruiting.2", pen=recruit.SIZE_PENALTY, free=recruit.FREE_SLOTS),
            i18n.t("wiki_rules.recruiting.3", align=recruit.ALIGNMENT_PENALTY),
            i18n.t("wiki_rules.recruiting.4", base=recruit.BASE_RECRUIT_CAPACITY, terms=_terms(recruit.SPONSOR_TERMS),
                   leader=_terms(recruit.LEADER_SPONSOR_TERMS)),
            i18n.t("wiki_rules.recruiting.5"),
            i18n.t("wiki_rules.recruiting.6", tavern=recruit.TAVERNA_SIZE, prison=recruit.PRISON_SIZE, days=recruit.REFRESH_DAYS, bail=tavern.BAIL_BONUS[0], step=tavern.BAIL_STEP),
        ]),
        ("groups", [
            i18n.t("wiki_rules.groups.1", base=group.BASE_SLOTS, fame=group.FAME_PER_SLOT),
            i18n.t("wiki_rules.groups.2", cap=group.BASE_CAPACITY, terms=terms, herd=group.HERD_BASE, herd_terms=_terms(group.HERD_TERMS)),
            i18n.t("wiki_rules.groups.3", days=cohesion.NOTICE_DAYS),
            i18n.t("wiki_rules.groups.4"),
        ]),
        ("captives", [
            i18n.t("wiki_rules.captives.1", tools=tools, capture=actions.CAPTURE.cost),
            i18n.t("wiki_rules.captives.2", weight=captives.HERD_WEIGHT, days=captives.CAPTIVE_DAYS),
            i18n.t("wiki_rules.captives.3"),
        ]),
        ("wagons", [i18n.t("wiki_rules.wagons.1", dist=wagon.WEAR_DISTANCE, hp=wagon.WEAR_HP), *_lines("wagons", 3)[1:]]),
        ("money", _lines("money", 4, copper=items.COIN_VALUE[items.COIN_ITEM], gold=items.COIN_VALUE[items.GOLD_ITEM])),
        ("hunger", _lines(
            "hunger", 8, d1=1, d2=2, d3=len(HUNGER_PENALTIES) - 1, pen1=HUNGER_PENALTIES[1], pen2=HUNGER_PENALTIES[2], pen3=HUNGER_PENALTIES[3],
            death=data.STARVATION_DEATH_DAYS, cap=STARVING_HP_MAX)),
        ("stomp", _lines("stomp", 2)),
        ("poison", _lines("poison", 4, hours=poisons.ANTIDOTE_COOLDOWN_HOURS, dc=poisons.POISONS["snake_venom"].base_dc,
                                 spent=poisons.POISONS["snake_venom"].hours, rot=poisons.POISONS["gut_rot"].hours)),
        ("study", _lines("study", 4, cost=economy.TAVERN_STUDY_COST_PER_DAY)),
        ("dungeon", _lines("dungeon", 4)),
        ("placement", _lines("placement", 3)),
        ("reading", _lines("reading", 4, dc=intel.BASE_DC, discount=intel.RACE_DISCOUNT, bonus=intel.ASSESS_BONUS,
                                 assess=actions.ASSESS.cost)),
    ])


def matching(query):
    """The sections whose title or a line contains `query` (all of them for an empty one)."""
    q = query.lower()
    return [(k, t, lines) for k, t, lines in sections()
            if not q or q in t.lower() or any(q in ln.lower() for ln in lines)]
