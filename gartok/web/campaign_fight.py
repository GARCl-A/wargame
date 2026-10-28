"""A campaign fight in the browser, entered and settled as `app_battle` does: the snapshot before it, the
play log, the guild's bestiary, then `BattleSession`; once it is over, `campaign.absorb_battle`, what the
fight settles for good, and `ReportSession`, which ends on the map.

What opens one: a forced fight (the guard, an ambush, a raid), after its talk or with nobody to talk to,
the Wilds Claim's two fights and an arena bout (`arena_session`). The hunt and the searches' finds still
open the away card."""

from .. import (
    campaign,
    combat_lab,
    encounters,
    forced,
    persist,
    recorder,
    vocations,
    world,
)
from ..battle import Battle
from ..combat_log import CombatLog
from ..scenario import scenario_for
from .battle_session import BattleSession
from .claim_tab import FIGHTS
from .report_session import ReportSession

AFTER_CLAIM_FIGHT = {"SCOUTED": "CLEARED", "FENCED": "SWEPT"}


def forced_fight(map_session, group, order, opening=None):
    """`group`'s forced fight (`group.pending`), as `App._start_forced_battle` plays it; `opening` is how
    the talk before it ended (`dialogue.Opening`)."""
    guild, node = map_session.guild, world.node(group.node)
    battle = Battle(list(group.members), list(order.pack), scenario=scenario_for(node),
                    daylight=guild.clock.is_daylight, lethal=True, arena=False,
                    clock_day=guild.clock.day, aggressor="enemy")
    if opening is not None:
        battle.open_with(**opening.to_dict())

    def settle(outcome):
        group.pending = None
        return forced.resolve(guild, group, order, outcome)

    return _enter(map_session, group, battle, node, order.kind, forced.EVENTS[order.kind].label.capitalize(), settle)


def claim_fight(map_session, group):
    """The Claim's fight at its stage (CLEAR, then SWEEP), as `App._start_claim_battle` plays it: won,
    the claim moves a stage."""
    guild, node = map_session.guild, world.node(group.node)
    _verb, title, size, level = FIGHTS[guild.wilds_claim_stage]
    stage = AFTER_CLAIM_FIGHT[guild.wilds_claim_stage]
    battle = Battle(list(group.members), [encounters.build_enemy(level) for _ in range(size)],
                    scenario=node.scenario(), daylight=guild.clock.is_daylight, lethal=True, arena=False,
                    clock_day=guild.clock.day, aggressor="player")

    def settle(outcome):
        if not outcome.won:
            return ["The attempt fails -- the claim's stage is unchanged."]
        {"CLEARED": guild.wilds_claim_mark_cleared, "SWEPT": guild.wilds_claim_mark_swept}[stage]()
        return [f"The Wilds claim advances -- now {stage.title()}."]

    return _enter(map_session, group, battle, node, node.id, title, settle)


def _enter(map_session, group, battle, node, kind, title, settle, *, squad=None, offer=None, after=None):
    """Every campaign fight starts here, as `App._enter_battle`: the world is saved first, so a bad
    fight can be undone. `squad` is who fights (the whole band unless an arena bout picked), `offer` the
    arena's `world.Bout`, `after(outcome)` where the report ends (the map, unless the fight says)."""
    guild, squad = map_session.guild, list(squad if squad is not None else group.members)
    if map_session.world_id is not None:
        foes = len(battle.enemy_units)
        persist.save_game(map_session.world_id, guild, kind="auto",
                          label=f"Before a fight at {node.name}: {foes} foe{'s' if foes != 1 else ''}")
    recorder.before_fight(squad)
    day = guild.clock.day
    path = recorder.combat_log_path(f"d{day:03d}-{combat_lab.slug(f'{node.id}-{kind}')}")
    if path is not None:
        battle.record_to(CombatLog(path, {"source": "campaign", "node": node.id, "kind": kind, "day": day},
                                   {"player": "human", "enemy": "ai"}))
    battle.intel.bind("player", guild.bestiary, vocations.info_bonus(guild))
    session = BattleSession(battle, {"name": node.name, "sub": f"{title} · day {day}"},
                            then=lambda: _settle(map_session, group, squad, battle, node, kind, settle, offer, after))
    map_session.game.open(session)
    return {"screen": session.screen}


def _settle(map_session, group, squad, battle, node, kind, settle, offer, after):
    """The fight is over: fold it into the guild as `App._battle_end` does, then the report."""
    from .dialogue_session import _to_map
    guild = map_session.guild
    outcome = campaign.absorb_battle(guild, squad, battle, node=node, arena_offer=offer)
    recorder.emit("fight", node=node.id, kind=kind, won=outcome.won, squad=outcome.squad_size,
                  deaths=len(outcome.fallen), foes=len(battle.enemy_units), xp=sum(outcome.xp_awards.values()),
                  level=round(sum(u.combat_level for u in guild.roster) / max(1, len(guild.roster)), 2))
    map_session.notices += outcome.captive_notes
    map_session.notices += settle(outcome)
    map_session.notices += [f"{u.name} reached combat level {u.combat_level}!" for u in outcome.leveled_up]
    if outcome.campaign_over:
        map_session.wiped = True
    map_session._save()
    def then():
        if map_session.wiped:
            return map_session.back()
        return after(outcome) if after is not None else _to_map(map_session, group)

    report = ReportSession(map_session, group, battle, outcome, place=node.name, offer=offer, then=then)
    map_session.game.open(report)
    return {"screen": report.screen}

