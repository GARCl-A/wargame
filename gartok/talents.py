"""Talent trees: what each track of experience lets a character get better at.

One tree per XP track (see `progression.py`). Reaching a new level in a track
grants one pick in that track's tree; `Unit.choose_talent` spends it. Mirrors
`abilities.py` -- a frozen-dataclass registry, effects as plain numeric knobs
picked up in `Unit._derive_combat` (plus `economy.market_deal` for the haggle
one). Adding a node that reuses an existing knob = editing only this file.

The trees are grown by hand, node by node. Seeded here: only the tier-1 roots
the design calls for. Nodes are not yet mutually exclusive -- each level is one
free pick and the roots have no prerequisite; a `group` field for "pick one of
these" can come later.

`name` / `effect` are player-facing (English, the current text standard); `id`
and field names are English identifiers.
"""

from dataclasses import dataclass

TRACKS = ("combat", "work")


@dataclass(frozen=True)
class Talent:
    id: str
    track: str                       # "combat" | "work"
    tier: int                        # 1 = a root; deeper nodes sit at higher tiers
    name: str
    effect: str
    requires: str | None = None      # id of a talent that must be taken first

    # --- effect knobs (all optional) ---------------------------------- #
    attr_bonus: tuple = ()           # ((attribute, amount), ...) -- added to the SCORE
    haggle_charisma: int = 0         # +N Charisma, market buy/sell checks only
    carry_light_items: int = 0       # -N kg per non-weapon/non-consumable item, carry check only

    @property
    def desc(self):
        return f"{self.name}: {self.effect}"


_LIST = [
    # -- combat: pick the kind of fighter you are ----------------------- #
    Talent("strong", "combat", 1, "Strong",
           "+1 Strength.", attr_bonus=(("strength", 1),)),
    Talent("agile", "combat", 1, "Agile",
           "+1 Dexterity.", attr_bonus=(("dexterity", 1),)),
    Talent("tough", "combat", 1, "Tough",
           "+1 Constitution.", attr_bonus=(("constitution", 1),)),

    # -- work: two roots, negotiator and carrier ---------------------- #
    Talent("negotiator", "work", 1, "Negotiator",
           "+1 Charisma for market buy and sell checks.", haggle_charisma=1),
    Talent("carrier", "work", 1, "Carrier",
           "carry 1 kg less per item that is not a weapon or a consumable.",
           carry_light_items=1),
]

TALENTS = {t.id: t for t in _LIST}

# Per-track, ordered by tier -- what the level screen draws.
TREE = {track: [t for t in _LIST if t.track == track] for track in TRACKS}


def get(talent_id):
    return TALENTS.get(talent_id)
