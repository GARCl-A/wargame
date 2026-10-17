"""Factions: the organisations the guild builds standing with, and the deeds
that earn it.

Reputation is per faction (`guild.reputation[faction_id]`) and it moves ONLY by
completing deeds -- there is no per-win grind. A deed is a one-shot achievement:
a named condition that, once true, is banked in `guild.deeds_done` forever and
pays its `rep` into the faction's score. The player works a faction's deed list
in any order; a deed carries `requires` only when order must be forced.

Hand-grown, node by node, like the talent trees -- no procedural generator. A
faction's deeds *are* its rules: "this is what this place wants from you." A
faction is its own thing, not a node -- it may hold ground across several nodes.

First faction: the Pits (staked bouts, at the `arena` node). Its deed list is the
first arena's whole "sub-campaign": win a bout, solo the entry pit, then dethrone
its champion team. Second faction: the Bankers -- not combat, proof the guild
moves money through the city (an economic job done, a market spend threshold, a
spread of goods sold). Repeatable reputation missions come later.

A deed check reads a `factions.Event` -- what just happened. `settle` is called
after any moment a deed might fire on: a battle (`campaign.absorb_battle`, the
event carries the `campaign.BattleOutcome`), arriving somewhere on the map
(`map_screen`), a mission turned in (`missions.turn_in`, the event carries the
template's `tag`), and a market visit (`market_screen`, after a buy or sell). A
check keys off `event.kind` first, then reads only the fields its own kind sets;
it also gets `guild`, so a "visited every node" or "banked 1000 copper" deed
reads campaign state straight off that.
"""

from collections.abc import Callable
from dataclasses import dataclass

from .constants import fmt_money


@dataclass(frozen=True)
class Faction:
    id: str
    name: str
    blurb: str
    hidden: bool = False                      # unknown to the guild until it enters one of `nodes`
    nodes: tuple[str, ...] = ()               # the nodes that belong to it


@dataclass(frozen=True)
class Event:
    """Something that just happened that a deed might fire on.

    `kind` names it ("battle", "travel", "market", "mission", "hunt", "recruit",
    ...); `node` is where it happened, or None. The rest is per-kind payload --
    a deed check reads only the fields its own kind sets. A battle event
    carries `outcome` (a `campaign.BattleOutcome`); a mission event carries
    `tag` / `tags` (the `missions.MissionTemplate.tags` just turned in, e.g. ("economic", "apothecary"));
    other kinds add their own fields as deeds come to need them.
    """
    kind: str
    node: object = None
    outcome: object = None                    # kind == "battle"
    tag: str = None                           # kind == "mission"
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        tags_val = self.tags
        tag_val = self.tag
        if isinstance(tags_val, str):
            tags_val = (tags_val,)
            if not tag_val:
                tag_val = tags_val[0]
        elif not tags_val and tag_val:
            tags_val = (tag_val,)
        elif tags_val and not tag_val:
            tag_val = tags_val[0]
        object.__setattr__(self, "tags", tuple(tags_val) if tags_val else ())
        object.__setattr__(self, "tag", tag_val)


@dataclass(frozen=True)
class Deed:
    id: str
    faction: str
    name: str
    blurb: str
    rep: int                                  # reputation banked on completion
    check: Callable                           # (guild, event) -> bool
    requires: str | None = None            # deed id that must be done first
    exclusive: str | None = None           # a set only one deed of which can ever be done


def _arena_win(event):
    """The common front of every arena deed: a battle win, at the pits."""
    out = event.outcome
    return (event.kind == "battle" and event.node is not None
            and event.node.arena and out is not None and out.won)


def _arena_tier(event):
    """The `world.Bout` an arena win was fought under, once it is a confirmed
    pit win -- else None, so a deed can chain `.champion` / `.ctf` off it."""
    return event.outcome.arena_tier if _arena_win(event) else None


_FACTIONS = [
    Faction("arena", "The Pits",
            "The staked bouts in the cellars under the city. Win, and be known."),
    Faction("bankers", "The Bankers",
            "The coin-keepers of the city. They rent strongboxes and trade in property."),
    Faction("library", "The Library",
            "Scholars and linguists. They trade in knowledge.", hidden=True, nodes=("library",)),
    Faction("tanners", "The Tanners",
            "The leatherworkers of the city. They pay for what the Wilds sheds.", hidden=True, nodes=("tanner",)),
    Faction("apothecary", "The Apothecary",
            "Herbalists and alchemists of the city. They brew remedies and trade in rare reagents.", hidden=True, nodes=("apothecary",)),
    Faction("ledger_hold", "Ledger Hold",
            "The fortified garrison of the march. They train soldiers and hold the border.", hidden=True, nodes=("ledger_hold",)),
    Faction("blood_cult", "The Blood Cult",
            "Mages born to it, hidden under the ruins: the magic runs in their line, from a dragon, an angel or a demon somewhere back. They study the blood that carries it.", hidden=True, nodes=("blood_sanctuary",)),
    Faction("nature_coven", "The Nature Coven",
            "Mages of the green, hidden deep in the Wilds. They keep to themselves.", hidden=True, nodes=("nature_grove",)),
    Faction("faith_order", "The Faith Order",
            "Mages of faith, hidden in a cathedral in the hills. They answer to a higher call.", hidden=True, nodes=("faith_cathedral",)),
]

def _delivered(thing, school):
    """A mission handing `thing` (a tag: "codex", "snake_dragon") to `school`'s faction."""
    def check(g, e):
        return e.kind == "mission" and thing in e.tags and school in e.tags
    return check


_DEEDS = [
    Deed("arena_first_blood", "arena", "First Blood",
         "Win a staked bout in the pits.", rep=1,
         check=lambda g, e: _arena_win(e)),

    Deed("arena_lone_wolf", "arena", "Lone Wolf",
         "Win in the entry pit with a single fighter.", rep=1,
         check=lambda g, e: (
             _arena_win(e) and e.outcome.squad_size == 1
             and _arena_tier(e) is not None and _arena_tier(e).rep == 0)),

    Deed("arena_dethrone", "arena", "Dethrone the Champions",
         "Beat the pit's champion team.", rep=1,
         check=lambda g, e: (
             _arena_win(e) and _arena_tier(e) is not None and getattr(_arena_tier(e), "champion", False))),

    # The Games -- the arena's second stage. Locked behind the champion bout; the
    # bouts that satisfy these only appear once `arena_dethrone` is banked.
    Deed("arena_bloodsport", "arena", "Bloodsport",
         "Win a bout in the Games -- the arena's second stage.", rep=1,
         requires="arena_dethrone",
         check=lambda g, e: (
             _arena_tier(e) is not None and _arena_tier(e).stage2)),

    Deed("arena_flag_runner", "arena", "Flag Runner",
         "Capture the enemy flag in the Games.", rep=1,
         requires="arena_dethrone",
         check=lambda g, e: (
             _arena_tier(e) is not None and _arena_tier(e).ctf)),

    Deed("arena_untouchable", "arena", "Untouchable",
         "Capture the flag without knocking anyone out.", rep=1,
         requires="arena_dethrone",
         check=lambda g, e: (
             _arena_tier(e) is not None and _arena_tier(e).ctf
             and e.outcome.player_kos == 0)),

    Deed("arena_ribbit_brothers", "arena", "The Ribbit Brothers",
         "Beat the three Grippli in the Games.", rep=1,
         requires="arena_dethrone",
         check=lambda g, e: (
             _arena_tier(e) is not None and _arena_tier(e).boss)),

    # The Bankers' first deed list: not combat, but the same "one-shot,
    # any order" shape -- proof the guild is worth lending to, measured by
    # how it moves money through the city. A fourth deed, gated on all three
    # of these being done rather than a single `requires`, is meant to follow
    # once there is something to spend that trust on (buying property).
    Deed("bankers_good_for_business", "bankers", "Good for Business",
         "Complete an economic job in the City.", rep=1,
         check=lambda g, e: e.kind == "mission" and ("economic" in e.tags or e.tag == "economic")),

    Deed("bankers_steady_customer", "bankers", "Steady Customer",
         "Spend 1000 copper at the market.", rep=1,
         check=lambda g, e: e.kind == "market" and g.total_spent >= 1000),

    Deed("bankers_diverse_portfolio", "bankers", "Diverse Portfolio",
         "Sell 5 different kinds of goods to the market.", rep=1,
         check=lambda g, e: (
             e.kind == "market" and len(g.items_sold_kinds) >= 5)),

    # Gated on all three economic deeds above rather than a single `requires`
    # (that field only chains one prerequisite) -- `check` reads
    # `guild.deeds_done` directly instead. It reads the finished trust mission
    # rather than the turn-in event: the chest can come home before the three
    # deeds are done, and the one-shot event would be gone by then.
    Deed("bankers_trust", "bankers", "Earned Trust",
         "Carry the Bankers' trust all the way to Ledger Hold and back.", rep=1,
         check=lambda g, e: (
             any(m.template_id == "bankers_trust_chest" and m.state == "done"
                 for m in g.missions)
             and {"bankers_good_for_business", "bankers_steady_customer",
                  "bankers_diverse_portfolio"} <= set(g.deeds_done))),
    
    Deed("tanners_hides", "tanners", "Fifteen Hides",
         "Bring the tanner fifteen hides.", rep=1,
         check=lambda g, e: e.kind == "mission" and "hides" in e.tags),

    Deed("tanners_biwolf", "tanners", "The Biwolf's Hide",
         "Bring the tanner the leather of the Biwolf.", rep=1,
         check=lambda g, e: e.kind == "mission" and "biwolf" in e.tags),

    Deed("tanners_ox", "tanners", "The Immortal Ox",
         "Bring the tanner the hide of Aurochs, the immortal ox.", rep=1,
         requires="tanners_biwolf",
         check=lambda g, e: e.kind == "mission" and "ox" in e.tags),

    # Library deeds
    Deed("library_initiate", "library", "Library Initiate",
         "Complete a task for the library.", rep=1,
         check=lambda g, e: e.kind == "mission" and ("library" in e.tags or e.tag == "library")),
    Deed("library_trusted", "library", "Trusted Scholar",
         "Complete a second task for the library.", rep=1,
         requires="library_initiate",
         check=lambda g, e: e.kind == "mission" and ("library" in e.tags or e.tag == "library") and
             sum(1 for m in g.missions if m.state == "done" and ("library" in getattr(__import__('gartok.missions', fromlist=['']).template_of(m), "tags", ()) or __import__('gartok.missions', fromlist=['']).template_of(m).tag == "library")) >= 2),

    # Apothecary deeds
    Deed("apothecary_mushrooms", "apothecary", "Fifteen Red Mushrooms",
         "Bring the apothecary fifteen red mushrooms.", rep=1,
         check=lambda g, e: e.kind == "mission" and ("apothecary" in getattr(e, "tags", ()) or getattr(e, "tag", None) == "apothecary")),

    # Ledger Hold deeds
    Deed("ledger_hold_mentoring", "ledger_hold", "Treefolk Mentorship",
         "Train a designated Treefolk recruit to racial level 2 and deliver them to Ledger Hold.", rep=1,
         check=lambda g, e: e.kind == "mission" and ("ledger_hold" in getattr(e, "tags", ()) or getattr(e, "tag", None) == "ledger_hold")),
    # One Codex exists, so it goes to one school; one Snake Dragon, dead or alive.
    Deed("blood_codex", "blood_cult", "The Codex Delivered",
         "Bring the Ancient Codex to the Blood Sanctuary.", rep=1,
         check=_delivered("codex", "blood"), exclusive="codex"),
    Deed("nature_codex", "nature_coven", "The Codex Delivered",
         "Bring the Ancient Codex to the Nature Grove.", rep=1,
         check=_delivered("codex", "nature"), exclusive="codex"),
    Deed("faith_codex", "faith_order", "The Codex Delivered",
         "Bring the Ancient Codex to the Faith Cathedral.", rep=1,
         check=_delivered("codex", "faith"), exclusive="codex"),
    Deed("blood_snake", "blood_cult", "The Dragon's Blood",
         "Bring the Snake Dragon's body to the Blood Sanctuary.", rep=1,
         check=_delivered("snake_dragon", "blood"), exclusive="snake_dragon"),
    Deed("nature_snake", "nature_coven", "The Snake Saved",
         "Bring the Snake Dragon alive to the Nature Grove.", rep=1,
         check=_delivered("snake_dragon", "nature"), exclusive="snake_dragon"),
    Deed("faith_battlefield", "faith_order", "Mercy at the Front",
         "Win the Battlefield's skirmish without losing one of the soldiers.", rep=1,
         check=lambda g, e: e.kind == "mission" and "battlefield" in e.tags and "faith" in e.tags),
    Deed("faith_necromancer", "faith_order", "The Necromancer at the Front",
         "Put down the necromancer raising the dead at the Battlefield.", rep=1,
         check=lambda g, e: e.kind == "mission" and "necromancer" in e.tags and "faith" in e.tags),
    Deed("nature_wildfire", "nature_coven", "The Ogre's Wildfire",
         "Talk the Ogre round, or beat him, before his fires take the Wilds.", rep=1,
         check=lambda g, e: e.kind == "mission" and "wildfire" in e.tags and "nature" in e.tags),
    Deed("blood_clutch", "blood_cult", "The Dragon's Clutch",
         "Bring one of the dragon's eggs from under the Mine to the Blood Sanctuary.", rep=1,
         check=_delivered("dragon_clutch", "blood")),
    Deed("ledger_hold_supply_run", "ledger_hold", "Frontier Supply Run",
         "Successfully complete 10 military supply caravan runs to the frontier outpost.", rep=1,
         check=lambda g, e: e.kind == "supply_run" and g.supply_runs_completed >= 10),
]

FACTIONS = {f.id: f for f in _FACTIONS}
DEEDS = {d.id: d for d in _DEEDS}
DEEDS_BY_FACTION = {fid: [d for d in _DEEDS if d.faction == fid] for fid in FACTIONS}


def faction(fid):
    return FACTIONS[fid]


def known(guild):
    """The factions the guild knows of: the open ones, plus every hidden one it has met
    (`Guild.meet_factions_at`) or already holds standing with."""
    return [f for f in _FACTIONS if guild.faction_known(f.id)]


def deed_notice(d):
    """The one line every caller shows for a just-earned deed (`campaign.py`'s
    travel/battle events, the tanner's turn-in, the market's buy/sell) -- kept
    here so the wording only has one place to drift out of sync."""
    return f"DEED · {d.name}  +{d.rep} reputation with {faction(d.faction).name}"


@dataclass(frozen=True)
class Unlock:
    faction: str
    rep_required: int
    title: str
    description: str


def get_unlocks(faction_id: str):
    """Dynamic catalog of perks/services unlocked as reputation rises."""
    from . import economy
    unlocks = []
    if faction_id == "bankers":
        unlocks.append(
            Unlock(
                "bankers",
                economy.CITY_PROPERTY_REP_GATE,
                "City Property",
                f"Buy a house in the City ({fmt_money(economy.CITY_PROPERTY_PRICE)}, {economy.CITY_PROPERTY_CAPACITY} kg storage)",
            )
        )
    elif faction_id == "arena":
        unlocks.append(
            Unlock(
                "arena",
                2,
                "The Games (Stage 2)",
                "Brawl, Capture the Flag, and The Ribbit Brothers bouts",
            )
        )
    elif faction_id == "library":
        unlocks.append(
            Unlock(
                "library",
                1,
                "Expanded Catalog",
                "More language dictionaries become available to buy."
            )
        )
        unlocks.append(
            Unlock(
                "library",
                2,
                "Rare Manuscripts",
                "The library unlocks rare language dictionaries and deeper archives."
            )
        )
    elif faction_id == "ledger_hold":
        unlocks.append(
            Unlock(
                "ledger_hold",
                1,
                "Military Supply Network",
                "Recognised caravan runner for the military frontier outpost."
            )
        )
    return unlocks


def failed(guild, deed):
    """`deed` can never be done: another deed of its exclusive set already was."""
    done = set(guild.deeds_done)
    return (deed.exclusive is not None and deed.id not in done
            and any(d.exclusive == deed.exclusive and d.id in done for d in _DEEDS))


def open_deeds(guild):
    """Deeds not yet done (nor failed) whose `requires` (if any) is already done."""
    done = set(guild.deeds_done)
    return [d for d in _DEEDS
            if d.id not in done and (d.requires is None or d.requires in done)
            and not failed(guild, d)]


def settle(guild, event):
    """Check every open deed against a just-happened `event` (a `factions.Event`);
    bank the ones whose condition now holds (mark done, add their `rep` to the
    faction). Loops so a deed gated behind one that completes in the same pass
    still fires. Returns the newly completed deeds, in completion order, for the
    caller to show."""
    if event.node is not None:
        guild.meet_factions_at(event.node.id)
    earned = []
    progressing = True
    while progressing:
        progressing = False
        for d in open_deeds(guild):
            if d.check(guild, event):
                guild.deeds_done.append(d.id)
                guild.reputation[d.faction] = guild.reputation.get(d.faction, 0) + d.rep
                earned.append(d)
                progressing = True
    return earned
