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
its champion team. Repeatable reputation missions, and the other factions, come
later.

The deed checks read `node`, `outcome.arena_tier` (the `world.Bout`, or None)
and `outcome.squad_size` off a `campaign.BattleOutcome`.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Faction:
    id: str
    name: str
    blurb: str


@dataclass(frozen=True)
class Deed:
    id: str
    faction: str
    name: str
    blurb: str
    rep: int                                  # reputation banked on completion
    check: Callable                           # (guild, node, outcome) -> bool
    requires: Optional[str] = None            # deed id that must be done first


def _arena_win(node, outcome):
    """The common front of every arena deed: a win, at the pits."""
    return node is not None and node.arena and outcome.won


_FACTIONS = [
    Faction("arena", "The Pits",
            "The staked bouts in the cellars under the city. Win, and be known."),
]

_DEEDS = [
    Deed("arena_first_blood", "arena", "First Blood",
         "Win a staked bout in the pits.", rep=1,
         check=lambda g, node, out: _arena_win(node, out)),

    Deed("arena_lone_wolf", "arena", "Lone Wolf",
         "Win in the entry pit with a single fighter.", rep=1,
         check=lambda g, node, out: (
             _arena_win(node, out) and out.squad_size == 1
             and out.arena_tier is not None and out.arena_tier.rep == 0)),

    Deed("arena_dethrone", "arena", "Dethrone the Champions",
         "Beat the pit's champion team.", rep=1,
         check=lambda g, node, out: (
             _arena_win(node, out)
             and out.arena_tier is not None and out.arena_tier.champion)),

    # The Games -- the arena's second stage. Locked behind the champion bout; the
    # bouts that satisfy these only appear once `arena_dethrone` is banked.
    Deed("arena_bloodsport", "arena", "Bloodsport",
         "Win a bout in the Games -- the arena's second stage.", rep=1,
         requires="arena_dethrone",
         check=lambda g, node, out: (
             _arena_win(node, out)
             and out.arena_tier is not None and out.arena_tier.stage2)),

    Deed("arena_flag_runner", "arena", "Flag Runner",
         "Capture the enemy flag in the Games.", rep=1,
         requires="arena_dethrone",
         check=lambda g, node, out: (
             _arena_win(node, out)
             and out.arena_tier is not None and out.arena_tier.ctf)),

    Deed("arena_untouchable", "arena", "Untouchable",
         "Capture the flag without knocking anyone out.", rep=1,
         requires="arena_dethrone",
         check=lambda g, node, out: (
             _arena_win(node, out)
             and out.arena_tier is not None and out.arena_tier.ctf
             and out.player_kos == 0)),
]

FACTIONS = {f.id: f for f in _FACTIONS}
DEEDS = {d.id: d for d in _DEEDS}
DEEDS_BY_FACTION = {fid: [d for d in _DEEDS if d.faction == fid] for fid in FACTIONS}


def faction(fid):
    return FACTIONS[fid]


def open_deeds(guild):
    """Deeds not yet done whose `requires` (if any) is already done."""
    done = set(guild.deeds_done)
    return [d for d in _DEEDS
            if d.id not in done and (d.requires is None or d.requires in done)]


def settle(guild, node, outcome):
    """Check every open deed against a just-resolved event; bank the ones whose
    condition now holds (mark done, add their `rep` to the faction). Loops so a
    deed gated behind one that completes in the same pass still fires. Returns
    the newly completed deeds, in completion order, for the caller to show."""
    earned = []
    progressing = True
    while progressing:
        progressing = False
        for d in open_deeds(guild):
            if d.check(guild, node, outcome):
                guild.deeds_done.append(d.id)
                guild.reputation[d.faction] = guild.reputation.get(d.faction, 0) + d.rep
                earned.append(d)
                progressing = True
    return earned
