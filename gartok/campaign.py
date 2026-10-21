"""Folding a finished battle back into the campaign.

`Battle` wraps each squad member in a `Combatant` that carries all the battle
state (see `battle.py`), so the persistent roster is untouched during the fight;
once it is over this maps the outcome onto that roster:

- permadeath drops the fallen from `guild.roster`;
- survivors keep the little that carries forward (a lit torch, for now) and
  otherwise return at full HP -- the rest of the spoils come from the loot pool;
- the campaign clock advances by the rounds fought (~6 s each);
- a win bumps the tally;
- `factions.settle` checks the faction deeds against the result -- e.g. a first
  arena win completes "First Blood" and earns a point of reputation with the
  Pits. It is handed a `factions.Event("battle", node=, outcome=)`; the deed
  checks read `arena_tier` (a `world.Bout`), `squad_size` and `player_kos` off
  the outcome, so those are set before `settle`.

`app` owns the *screen* that comes next (loot, reward, or straight to the map);
this module owns the *state change*, returned as a `BattleOutcome`.

`advance` (below) is the other half: the tick/orders engine that moves the map
when groups are travelling, working, or approaching an activity independently
of one another -- see `orders.py` for what an order is.
"""

import math
import random
from dataclasses import dataclass, field

from . import (
    aftermath,
    arena,
    captives,
    data,
    economy,
    factions,
    forced,
    loot,
    objectives,
    orders,
    recorder,
    solo,
    vocations,
    wildfire,
    world,
)


@dataclass
class BattleOutcome:
    won: bool
    survivors: list                              # roster units that came back
    fallen: list                                 # roster units lost for good
    loot_pool: list = field(default_factory=list)  # item names on the field (lethal win only)
    arena_reward: int | None = None              # copper purse to hand out (arena win only)
    campaign_over: bool = False                   # the guild is empty now
    xp_awards: dict = field(default_factory=dict)  # {member name: combat XP gained this battle}
    squad_size: int = 0                           # how many the guild sent into the fight
    player_kos: int = 0                           # enemies the squad put down (for the "Untouchable" deed)
    arena_tier: object = None                     # the world.Bout, for an arena fight
    deeds_earned: list = field(default_factory=list)  # factions.Deed completed by this result
    arena_title_event: str | None = None          # a one-liner if the Champion of the Pit title changed hands
    stabilized: list = field(default_factory=list) # survivors that were stabilized / broken at end of combat
    leveled_up: list = field(default_factory=list) # survivors that gained a combat or magic level from XP
    captive_notes: list = field(default_factory=list)  # lines for the foes bound and led away
    report: list = field(default_factory=list)    # aftermath.ReportRow per squad member
    takedowns: list = field(default_factory=list)  # aftermath.takedowns: (who, whom, mine)
    level_ups: list = field(default_factory=list)  # aftermath.LevelUp, before / after numbers
    memorials: list = field(default_factory=list)  # aftermath.Memorial per fallen member
    result: str = ""                              # aftermath.result_word: VICTORY / FLED / DEFEAT


def _carry_forward(member, combatant):
    """The battle state a survivor keeps: what they are holding (including picked up 
    or thrown weapons), light sources, and their ammo/first aid charges."""
    if hasattr(combatant, "equipped_weapon"):
        member.equipped_weapon = combatant.equipped_weapon
    if not getattr(combatant, "weapon_hand", False):
        member.equipped_weapon = None
        
    if combatant.torch_hand:
        member.equipped_offhand = data.TORCH_ITEM
    elif combatant.lantern_hand:
        member.equipped_offhand = data.LANTERN_ITEM
    else:
        member.equipped_offhand = None
        
    # combatant.inventory stays the flat, per-charge battle-time list (see
    # unit.flatten_pack); only the roster-side rebuild below deals in stacks.
    torch_spares = combatant.inventory.count(data.TORCH_ITEM)
    lantern_spares = combatant.inventory.count(data.LANTERN_ITEM)
    bear_traps = combatant.inventory.count("Bear Trap")
    alarm_traps = combatant.inventory.count("Alarm Trap")
    member._base_inventory = [
        it for it in member._base_inventory
        if it[0] not in (data.TORCH_ITEM, data.LANTERN_ITEM, "Bear Trap", "Alarm Trap")]
    for name, qty in ((data.TORCH_ITEM, torch_spares), (data.LANTERN_ITEM, lantern_spares),
                      ("Bear Trap", bear_traps), ("Alarm Trap", alarm_traps)):
        if qty:
            member.give_to_pack(name, qty)

    member.first_aid_charges = combatant.first_aid_charges
    if member.first_aid_charges <= 0:
        member.remove_named(data.FIRST_AID_ITEM)

    member.quiver_charges = combatant.ammo
    if member.quiver_charges <= 0:
        member.remove_named(data.AMMO_ITEM)

    for item in getattr(combatant, "picked_up_items", []):
        member.give_to_pack(item)
    for tool in combatant.capture_tools_used:
        member.remove_named(tool)

    if combatant.hp <= 0:
        member.hp = 1
    else:
        member.hp = combatant.hp
    member.hp = min(member.hp_max, member.hp + member.talent_bonus("post_combat_heal"))


def _death_note(battle, combatant):
    """How a fallen combatant was lost, read off the battle log: the way the death came
    (a failed death save, or the defeat that finished everyone on the ground) and the lines
    leading up to the fall."""
    lines, name = battle.log_lines, combatant.name

    def last(*needles, before=len(lines)):
        return next((i for i in range(before - 1, -1, -1)
                     if name in lines[i] and any(n in lines[i] for n in needles)), None)

    end = last("dies", "survive their wounds")
    how = "unknown" if end is None else "defeat" if "survive their wounds" in lines[end] else "death_save"
    down = last("goes down", "collapses", before=len(lines) if end is None else end + 1)
    trail = [] if down is None else [ln.strip() for ln in lines[max(0, down - 3):down + 1]]
    foes = [c.name for c in battle.enemy_units][:8]
    return {"how": how, "round": battle.round_no, "foes": foes, "trail": trail}


def _salvage_traps(battle, survivors):
    """Kobold Trap Salvage: the squad's bear and alarm traps that never sprang go back into
    the pack of a survivor who holds the talent."""
    salvager = next((m for m in survivors if m.talent_bonus("trap_salvage")), None)
    if salvager is None:
        return
    for obj in battle.ground:
        if (obj.is_trap and obj.trap_owner_team == "player"
                and obj.trap_type in ("bear trap", "alarm trap")):
            salvager.give_to_pack(obj.trap_type.title())


def absorb_battle(guild, squad, battle, node=None, arena_offer=None):
    """Fold `battle`'s result into `guild` (mutates it) and return a `BattleOutcome`.

    `squad` is the same-order list of roster units that `battle.player_units`
    wraps. `node` is the world node the fight happened at (for the faction deeds);
    `arena_offer` is the `world.Bout` for an arena fight, or None.
    """
    survivors, fallen, fallen_combatants, stabilized, xp_awards, leveled_up = [], [], [], [], {}, []
    report, level_ups, memorials = [], [], []
    takedowns, downed = aftermath.takedowns(battle), {}
    for who, whom, _mine in takedowns:
        downed.setdefault(who, []).append(whom)
    for combatant, member in zip(battle.player_units, squad):
        report.append(aftermath.ReportRow(member.name, member.race["name"], member.portrait_id,
                                          aftermath.status_of(combatant), downed.get(combatant.name, []),
                                          member.combat_xp, combatant.combat_xp_earned,
                                          combatant.magic_xp_earned))
        if combatant.survived:
            if combatant.status in ("stable", "broken"):
                stabilized.append(member)
            earned = combatant.combat_xp_earned + combatant.magic_xp_earned
            if earned:                            # XP scaled by the level gap of each kill
                before = aftermath.level_snapshot(member)
                member.combat_xp += combatant.combat_xp_earned
                member.magic_xp += combatant.magic_xp_earned
                member.collect_levels()           # a new racial level rolls a hit die
                xp_awards[member.name] = earned
                after = aftermath.level_snapshot(member)
                if (after["combat"], after["magic"]) > (before["combat"], before["magic"]):
                    leveled_up.append(member)
                    level_ups.append(aftermath.LevelUp(member, before, after))
            prev_hp = member.hp
            _carry_forward(member, combatant)
            if not battle.lethal and member.hp < prev_hp:
                member.non_lethal_damage = min(member.hp_max - member.hp,
                                               getattr(member, "non_lethal_damage", 0) + (prev_hp - member.hp))
            survivors.append(member)
        else:
            fallen.append(member)
            fallen_combatants.append(combatant)
            note = _death_note(battle, combatant)
            recorder.death(member, "combat", **note)
            killer = getattr(combatant, "downed_by", None)
            memorials.append(aftermath.memorial(
                member, day=guild.clock.day, cause="Killed in combat",
                place=getattr(node, "name", None), killer=killer.name if killer is not None else None,
                line=note["trail"][-1] if note["trail"] else None))

    guild.remove_members(fallen)
    guild.clock.advance_rounds(battle.round_no)
    won = battle.winner == "player"
    if won:
        guild.record_victory()
        _salvage_traps(battle, survivors)

    player_kos = sum(c.kills for c in battle.player_units)
    outcome = BattleOutcome(won, survivors, fallen, xp_awards=xp_awards,
                            squad_size=len(squad), player_kos=player_kos,
                            arena_tier=arena_offer, stabilized=stabilized,
                            leveled_up=leveled_up, report=report, level_ups=level_ups,
                            memorials=memorials, takedowns=takedowns,
                            result=aftermath.result_word(battle))

    if guild.empty:                               # full wipe: campaign over
        outcome.campaign_over = True
        return outcome

    if arena_offer and won:                       # arena bout: the flat purse
        outcome.arena_reward = arena_offer.purse
    elif won and battle.lethal:                   # lethal win: loot the field
        outcome.loot_pool = loot.field_loot(battle, fallen_combatants)
        bound = [c for c in battle.foe_units if c.captured]
        group = guild.group_of(survivors[0]) if survivors else None
        if bound and group is not None:
            outcome.captive_notes = captives.take(guild, group, bound)
        
        # Lizardfolk Organic Harvester
        if any(s.has_talent("organic_harvester") for s in survivors):
            organics = [it for it in outcome.loot_pool if it in ("Meat", "1sqm Hide")]
            counts = {}
            for it in organics:
                counts[it] = counts.get(it, 0) + 1
            for it, count in counts.items():
                if random.random() < 0.25:
                    extra = math.ceil(count * 0.2)
                    outcome.loot_pool.extend([it] * extra)

        # Skinner: one more hide off whatever beasts fell
        if (any(s.has_talent("skinner") for s in survivors)
                and any(it in ("Meat", "1sqm Hide") for it in outcome.loot_pool)):
            outcome.loot_pool.append("1sqm Hide")

        # Award currency from any unopened chests remaining on the battlefield
        for obj in battle.ground:
            if getattr(obj, "is_chest", False) and survivors:
                for it in getattr(obj, "contents", []):
                    amt = loot.parse_currency(it)
                    if amt:
                        share = amt // len(survivors)
                        rem = amt % len(survivors)
                        for s in survivors:
                            s.money += share
                        if rem:
                            survivors[0].money += rem

    outcome.deeds_earned = factions.settle(
        guild, factions.Event("battle", node=node, outcome=outcome))

    if arena_offer and arena_offer.champion and won:
        _claim_champion_title(guild, squad, battle, outcome)
    elif arena_offer and arena_offer.defense:
        _settle_title_defense(guild, outcome, won)
    return outcome


def _claim_champion_title(guild, squad, battle, outcome):
    """The champion team is down: the title goes to whoever on the squad landed
    the blow that first put Adelio down. No clean hand -> it stays vacant."""
    champ = next((c for c in battle.enemy_units
                  if getattr(c, "arena_role", None) == "champion"), None)
    downer = getattr(champ, "downed_by", None) if champ is not None else None
    winner = None
    if downer is not None:
        for combatant, member in zip(battle.player_units, squad):
            if combatant is downer and member in guild.roster:
                winner = member
    if winner is None:
        outcome.arena_title_event = ("Nobody on your side put the champion down "
                                     "cleanly -- the title stays vacant.")
        return
    winner.arena_title = True
    guild.arena_challenge_day = guild.clock.day + arena.CHALLENGE_CYCLE
    outcome.arena_title_event = (f"{winner.name} lands the finishing blow and "
                                 f"takes the Champion of the Pit.")


def _settle_title_defense(guild, outcome, won):
    champ = arena.champion_of(guild)
    if won:
        guild.arena_challenge_day = guild.clock.day + arena.CHALLENGE_CYCLE
        if champ is not None:
            outcome.arena_title_event = (f"{champ.name} turns the challenger away "
                                         f"and keeps the title.")
    else:
        guild.arena_challenge_day = None
        if champ is not None:
            champ.arena_title = False
            outcome.arena_title_event = (f"{champ.name} is beaten -- the Champion "
                                         f"of the Pit title is lost.")


# --------------------------------------------------------------------------- #
# the tick/orders engine -- advancing the map when groups are travelling,      #
# working or approaching an activity independently of one another             #
# --------------------------------------------------------------------------- #

@dataclass
class TickResult:
    events: list = field(default_factory=list)   # upkeep / travel / work notices, in order
    pending: list = field(default_factory=list)  # [(Group, Order)] interactive orders now due
    wiped: bool = False                          # the guild starved out entirely mid-tick
    casualties: list = field(default_factory=list) # characters who died during upkeep
    hungry: list = field(default_factory=list)     # characters who are starving
    level_ups: list = field(default_factory=list)  # aftermath.LevelUp gained during the tick


def advance(guild, dt=None, busy=()):
    """`_advance`, with the play recorder told which orders a person gave before it and
    which the engine made during it."""
    recorder.orders_issued(guild)
    try:
        return _advance(guild, dt, busy)
    finally:
        recorder.orders_settled(guild)
        objectives.check_and_bank(guild)


def _advance(guild, dt=None, busy=()):
    """Jump the world forward, running daily upkeep for every day crossed, then
    resolving whichever group(s) reached their order in that span.
    `travel`/`work` orders resolve silently here; every other kind comes back
    in `TickResult.pending` for the caller to play its screen and then set a
    fresh order (or `orders.idle()`) on that group before calling `advance`
    again. A group with no order, or an idle one, never blocks the jump and is
    left alone.

    `dt=None` (the default) jumps to the **soonest** order completion across
    every group with one in flight; no-op if nothing is. A caller may instead
    force a specific `dt` (hours) -- the map's ADVANCE when every group is
    garrisoned, or a hunt's hours -- so every in-flight order's `remaining` stays
    in lockstep with the shared clock even when nothing is due yet (an order that
    happens to complete within a forced `dt` still resolves normally); a forced
    stop also runs `Guild.eat_now_pass` (anyone still hungry eats right now,
    without waiting for the next daily meal). Resting is not this: it is a
    group's `rest` order, so the other groups are not frozen by it.

    A `"garrison"` order (`orders.py`) is excluded from `active` on purpose --
    it has no `eta`/`remaining` countdown to chase (it never completes; its
    payoff runs through `Guild._garrison_upkeep` on every day crossed
    instead), so folding it in here would either wreck the soonest-completion
    jump (its `remaining` is meaningless) or, on a forced stop, decrement it
    toward a spurious "completion" no kind branch below handles."""
    from . import rest

    jumped = dt is not None
    active = [g for g in guild.groups if g.busy and g.order.kind != "garrison"]
    if not jumped:
        if not active:
            return TickResult(hungry=[u for u in guild.roster if u.hunger_level > 0])
        dt = min(g.order.remaining for g in active)

    before_levels = {u.uid: aftermath.level_snapshot(u) for u in guild.roster}
    start_day = guild.clock.day
    events, casualties = guild.pass_time(dt, busy=busy)
    days_crossed = guild.clock.day - start_day
    if jumped:
        events += guild.eat_now_pass()
    
    hungry = [u for u in guild.roster if u.hunger_level > 0]
    
    if guild.empty:
        return TickResult(events=events, wiped=True, casualties=casualties, hungry=hungry)

    pending = []
    for g in active:
        if g.empty:                            # starved out during this tick's upkeep
            continue
        g.order.remaining -= dt
        if g.order.remaining > 1e-9:
            continue
        order = g.order
        if order.kind == "travel" and order.owed > 0:
            # a supply caravan stopped on the road: it stays at the leg's start until the fight
            g.order = None
            pending.append((g, guild.supply_ambush(order)))
            continue
        if order.kind == "travel" and order.path:
            # arrived at a waypoint, not the final stop -- visibly stop here and
            # queue the next edge, rather than resolving the whole route at once
            prev = g.node
            g.node = order.dest
            events += _wear_wagons(g, prev, order.dest)
            pause = forced.arrival_pause(guild, g, prev, order.path)
            if pause is not None:
                # NOT g.order = pause: same convention as an interactive order
                # below -- once due, the group goes idle (order=None) and the
                # data a resolved catch/ambush needs travels in the `pending`
                # tuple instead, so a second advance() call before the player
                # resolves it (e.g. another group's hunt tick) can't mistake
                # this group for still busy and silently wipe it.
                g.order = None
                pending.append((g, pause))
                continue
            if order.task == "supply_run":
                g.order = guild.supply_leg(g, order.dest, list(order.path))
            else:
                g.order = orders.next_leg(order.dest, list(order.path), g.speed,
                                          vocations.travel_mult(guild, g))
            continue
        g.order = None                         # resolved -- the group goes idle
        if order.kind == "travel":
            prev = g.node
            g.node = order.dest
            events += _wear_wagons(g, prev, order.dest)
            if order.task == "supply_run":
                events += guild.bank_supply_run(g.members)
            pause = forced.arrival_pause(guild, g, prev, ())
            if pause is not None:
                pending.append((g, pause))
                continue
            events += forced.arrival_notices(guild, order.dest)
        elif order.kind == "work" and order.gather:
            gathered, ambush = guild.gather_shift(g, order)
            events += gathered
            if ambush is not None:
                pending.append((g, ambush))
        elif order.kind == "work" and order.task == "put_out":
            events += wildfire.put_out(guild, g)
        elif order.kind == "work":
            events += guild._pay_shift(g.members, order.hours, order.eta, g.node)
        elif order.kind == "rest":
            events += guild.eat_now_pass(g.members)
            events += _fletcher_rest_pass(guild, g)
            still_hurt = [u for u in g.members if u.hp < u.hp_max]
            if still_hurt and rest.hours_to_midnight(guild) <= rest.JUST_BEFORE_MIDNIGHT * 2:
                who = ", ".join(f"{u.name} {u.hp}/{u.hp_max} HP" for u in still_hurt)
                events.append(f"{g.display_name}: stopped resting before midnight to keep a day of rations ({who}).")
        elif order.kind == "solo":
            events += solo.finish(guild, g, order)
        elif order.interactive:                # arena/market/bank/recruit/hunt
            pending.append((g, order))
    forced_events, forced_pending = forced.daily_checks(guild, days_crossed)
    events += forced_events
    pending += forced_pending
    for g, order in pending:
        if order.kind in forced.EVENTS:
            g.pending = order
    level_ups = []
    for u in guild.roster:
        b = before_levels.get(u.uid)
        if b is None:
            continue
        a = aftermath.level_snapshot(u)
        if (a["combat"], a.get("work", 0), a["magic"]) > (b["combat"], b.get("work", 0), b["magic"]):
            level_ups.append(aftermath.LevelUp(u, b, a))
    return TickResult(events=events, pending=pending, wiped=guild.empty, casualties=casualties,
                      hungry=hungry, level_ups=level_ups)


def _fletcher_rest_pass(guild, group):
    """If anyone in the group has the Fletcher talent and any member needs
    arrows, consume 1 Lumber from the group's packs/stores to refill/craft quivers."""
    fletcher = next((u for u in group.members if u.has_talent("fletcher")), None)
    if fletcher is None:
        return []

    needy = []
    for u in group.members:
        if u.count_of(data.AMMO_ITEM) > 0:
            if u.quiver_charges < data.QUIVER_AMMO:
                needy.append(u)
        elif bool(u.weapon and getattr(u.weapon, "range", 0) > 0):
            needy.append(u)

    if not needy:
        return []

    lumber_carrier = None
    for u in group.members:
        if u.unlocked_of(economy.FIELD_CAMPFIRE_LUMBER) > 0:
            lumber_carrier = u
            break
    if lumber_carrier is None:
        for w in getattr(group, "wagons", []):
            if not getattr(w, "broken", False) and w.stash.count_of(economy.FIELD_CAMPFIRE_LUMBER) > 0:
                lumber_carrier = w.stash
                break
    if lumber_carrier is None:
        for a in getattr(group, "herd", []):
            if a.stash.count_of(economy.FIELD_CAMPFIRE_LUMBER) > 0:
                lumber_carrier = a.stash
                break

    if lumber_carrier is None:
        return []

    lumber_carrier.remove_named(economy.FIELD_CAMPFIRE_LUMBER, 1)

    for u in needy:
        if u.count_of(data.AMMO_ITEM) == 0:
            u.give_to_pack(data.AMMO_ITEM)
        u.quiver_charges = data.QUIVER_AMMO

    return [f"{fletcher.name} carved arrows from 1 Lumber while resting, refilling quivers."]


def _wear_wagons(group, src, dest):
    """A leg walked: the road takes its toll on the group's wagons."""
    distance = next((w for v, w in world.neighbors(src) if v == dest), 0)
    return group.wear_wagons(distance)


def scout_ancient_ruins(guild, group):
    """Spend 4 hours searching the scrub off the Old Road for the lost library ruins.
    Tests WIS mod vs DC 12. On success, discovers the Ancient Ruins."""
    guild.clock.advance_hours(4)
    scout = max(group.members, key=lambda u: u.mod_wisdom) if group.members else None
    wis_mod = scout.mod_wisdom if scout else 0
    nat = data.d20()
    total = nat + wis_mod
    dc = 12
    if total >= dc:
        guild.reveal_node("ancient_ruins")
        name = scout.name if scout else "The squad"
        msg = f"{name} spots ancient stone markers half-buried in the scrub! The Ancient Ruins are discovered."
        return True, msg
    else:
        name = scout.name if scout else "The squad"
        msg = f"{name} spends 4 hours searching the brush, but finds no trace of the ruins (d20({nat}) {wis_mod:+}(WIS) = {total} vs DC {dc})."
        return False, msg
