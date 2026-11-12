"""The tutorial: state only -- no pygame here, so `guild.py` can hold one
without breaking its "stays pygame-free" promise (see its module docstring).

An id names one card's worth of copy under `tutorial.<id>.*` in
`locales/en.json` (`i18n.py` resolves it at draw time -- `tutorial_card.py`
does the actual drawing). A screen exposes which id applies right now via
`Screen.tutorial_key()`; this module just remembers which ids the player has
already dismissed, whether the system is switched on at all, and which id (if
any) the player forced back open with a screen's `?` badge.
"""

from . import i18n

TUTORIALS = (
    "draft.intro", "draft.vocation", "draft.pick", "draft.identity", "combat_lab",
    "map",
    "guild.members", "guild.overview", "guild.reputations", "guild.routines", "guild.band_routine",
    "squad", "battle", "report", "memorial", "level_up", "loot", "reward",
    "market", "taverna", "hunt", "bank", "level", "library",
    "group", "missions", "trust", "ledger", "craft", "medic", "property", "claim", "guard", "dialogue", "prison", "stable", "wagon_yard", "watch", "garage", "gathering", "initiation",
    "group_turn",
    "hint.study", "hint.road", "hint.reading", "hint.fallen", "hint.dungeon", "hint.place",
)


def _facts(key):
    """The live numbers a card's copy names as `{placeholders}`, so the card moves with the rule."""
    build = _FACTS.get(key)
    return build() if build else {}


def _pct(share):
    return round(share * 100)


def _taverna():
    from . import economy, recruit
    return {"free": recruit.FREE_SLOTS, "size_pen": recruit.SIZE_PENALTY, "align_pen": recruit.ALIGNMENT_PENALTY,
            "base": recruit.BASE_RECRUIT_CAPACITY, "study": economy.TAVERN_STUDY_COST_PER_DAY}


def _prison():
    from . import tavern
    return {"bail": tavern.BAIL_BONUS[0], "step": tavern.BAIL_STEP}


def _members():
    from .unit_hunger import HUNGER_PENALTIES, STARVING_HP_MAX
    return {"pen": HUNGER_PENALTIES[1], "cap": STARVING_HP_MAX}


def _battle():
    from . import actions
    from .combatant import AP_PER_TURN
    return {"ap": AP_PER_TURN, "assess": actions.ASSESS.cost}


def _hunt():
    from . import hunt
    return {"kg": f"{sum(hunt.HUNT_PARTY_YIELD[:3]):g}", "hours": hunt.HUNT_MEAT_HOURS}


def _bank():
    from . import economy, items
    return {"price": economy.BANK_CHEST_PRICE, "kg": economy.BANK_CHEST_CAPACITY, "copper": items.COIN_VALUE[items.COIN_ITEM],
            "gold": items.COIN_VALUE[items.GOLD_ITEM], "fee": economy.GOLD_FEE}


def _craft():
    from . import items
    from . import economy
    return {"jerky": items.get("Jerky").lifespan, "meat": items.get("Meat").lifespan, "fire_units": economy.FIELD_CAMPFIRE_UNITS}


def _initiation():
    from . import rite
    return {"rep": rite.REP_NEEDED, "faith": rite.POINTS["faith"], "blood": rite.POINTS["blood"],
            "nature": rite.POINTS["nature"], "days": rite.BLOOD_TEST_DAYS, "board": rite.BOARD_PER_DAY}


def _property():
    from . import economy
    return {"rep": economy.CITY_PROPERTY_REP_GATE, "price": f"{economy.CITY_PROPERTY_PRICE:,}",
            "kg": economy.CITY_PROPERTY_CAPACITY, "tax": economy.CITY_PROPERTY_TAX,
            "period": economy.CITY_PROPERTY_TAX_PERIOD_DAYS, "oven": economy.OVEN_PRICE}


def _watch():
    from . import data, world
    flight = {n: _pct(data.race_by_name(n)["flight"]) for n in data.LIVESTOCK}
    return {"take": _pct(world.ROAD_AMBUSH_CHANCE), "donkey": flight["Donkey"], "horse": flight["Horse"], "ox": flight["Ox"]}


def _claim():
    from . import economy
    return {"scout": economy.WILDS_CLAIM_SCOUT_HOURS, "lumber": economy.WILDS_CLAIM_FENCE_LUMBER,
            "fence": economy.WILDS_CLAIM_FENCE_HOURS, "days": economy.WILDS_CLAIM_SUSTAIN_DAYS,
            "raid": _pct(economy.WILDS_RAID_CHANCE), "bricks": economy.CLAIM_OVEN_BRICKS, "oven": economy.CLAIM_OVEN_HOURS,
            "fire": economy.CAMPFIRE_HOURS, "fuel_units": economy.CAMPFIRE_FUEL_UNITS}


def _wagon_yard():
    from . import wagon
    cart, carriage = wagon.VEHICLES["Cart"], wagon.VEHICLES["Carriage"]
    return {"cart_price": cart.price, "cart_kg": cart.capacity, "carriage_price": carriage.price, "carriage_kg": carriage.capacity,
            "dist": wagon.WEAR_DISTANCE, "hp": wagon.WEAR_HP, "hours": wagon.REPAIR_HOURS, "dc": wagon.REPAIR_DC}


def _shifts():
    from . import economy, gather
    return {"min": min(economy.LUMBER_SHIFT_HOURS), "max": max(economy.LUMBER_SHIFT_HOURS), "day": gather.DAY_HOURS}


def _overview():
    from . import cohesion
    return {"days": cohesion.NOTICE_DAYS}


def _identity():
    from . import recruit
    return {"base": recruit.BASE_RECRUIT_CAPACITY}


def _ox_hunt():
    from . import ox
    return {"step": ox.TRACK_DC_STEP}


def _medic():
    from . import economy
    return {"pct": _pct(economy.MEDIC_PRICE_FACTOR)}


def _garage():
    from . import economy
    return {"price": economy.GARAGE_PRICE}


def _library():
    from . import trade
    return {"rep": trade.DICTIONARY_MIN_REP}


_FACTS = {
    "library": _library,
    "taverna": _taverna,
    "prison": _prison,
    "guild.members": _members,
    "guild.overview": _overview,
    "draft.identity": _identity,
    "battle": _battle,
    "hint.reading": _battle,
    "hunt": _hunt,
    "ox_hunt": _ox_hunt,
    "bank": _bank,
    "craft": _craft,
    "initiation": _initiation,
    "medic": _medic,
    "property": _property,
    "garage": _garage,
    "watch": _watch,
    "claim": _claim,
    "wagon_yard": _wagon_yard,
    "work": _shifts,
    "gathering": _shifts,
}


def card(key, rows=(), spot=None, wiki=None):
    """The copy of `key`'s card: title, paragraphs, an optional closing pointer and the button.
    `rows` is what the copy cannot hold, drawn by the screen's session from its own registry: each
    row is {"stamp": {"label", "style"}, "rule", "text"} plus an optional "image" (a url), shown
    between the paragraphs and the pointer; a row may carry a `focus` (a CSS selector lit on the screen
    while the pointer is on the row). `spot` is the selector of the part of the screen the card is about,
    kept lit above the veil while the card is up; `wiki` is the entry (`chapter:id`) a second button opens."""
    title = i18n.t(f"tutorial.{key}.title")
    body = i18n.t(f"tutorial.{key}.body", **_facts(key))
    if isinstance(body, str):
        body = [body]
    suggestion_key = f"tutorial.{key}.suggestion"
    suggestion = i18n.t(suggestion_key, **_facts(key)) if i18n.has(suggestion_key) else None
    button_key = f"tutorial.{key}.button"
    button = i18n.t(button_key if i18n.has(button_key) else "tutorial.default_button")
    return {"title": title, "body": list(body), "rows": list(rows), "suggestion": suggestion, "button": button, "spot": spot, "wiki": wiki,
            "wiki_button": i18n.t("tutorial.wiki_button") if wiki else None}


class TutorialState:
    def __init__(self, seen=None, enabled=True):
        self.seen = set(seen or ())
        self.enabled = enabled
        self.showing = None       # an id forced open by the `?` badge, or None

    def should_show(self, key):
        if not self.enabled or key is None:
            return False
        return key == self.showing or key not in self.seen

    def dismiss(self, key):
        self.seen.add(key)
        if self.showing == key:
            self.showing = None

    def reopen(self, key):
        self.showing = key

    def reset(self):
        self.seen.clear()
        self.showing = None
