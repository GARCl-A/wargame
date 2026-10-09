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
    arena,
    constants,
    data,
    economy,
    encounters,
    factions,
    justice,
    loot,
    missions,
    orders,
    recorder,
    solo,
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
    leveled_up: list = field(default_factory=list) # survivors that gained a combat level from XP


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


def absorb_battle(guild, squad, battle, node=None, arena_offer=None):
    """Fold `battle`'s result into `guild` (mutates it) and return a `BattleOutcome`.

    `squad` is the same-order list of roster units that `battle.player_units`
    wraps. `node` is the world node the fight happened at (for the faction deeds);
    `arena_offer` is the `world.Bout` for an arena fight, or None.
    """
    survivors, fallen, fallen_combatants, stabilized, xp_awards, leveled_up = [], [], [], [], {}, []
    for combatant, member in zip(battle.player_units, squad):
        if combatant.survived:
            if combatant.status in ("stable", "broken"):
                stabilized.append(member)
            if combatant.combat_xp_earned:        # XP scaled by the level gap of each kill
                old_lvl = member.combat_level
                member.combat_xp += combatant.combat_xp_earned
                member.collect_levels()           # a new mean level rolls a hit die
                xp_awards[member.name] = combatant.combat_xp_earned
                if member.combat_level > old_lvl:
                    leveled_up.append(member)
            _carry_forward(member, combatant)
            survivors.append(member)
        else:
            fallen.append(member)
            fallen_combatants.append(combatant)
            recorder.death(member, "combat", **_death_note(battle, combatant))

    guild.remove_members(fallen)
    guild.clock.advance_rounds(battle.round_no)
    won = battle.winner == "player"
    if won:
        guild.record_victory()

    player_kos = sum(c.kills for c in battle.player_units)
    outcome = BattleOutcome(won, survivors, fallen, xp_awards=xp_awards,
                            squad_size=len(squad), player_kos=player_kos,
                            arena_tier=arena_offer, stabilized=stabilized,
                            leveled_up=leveled_up)

    if guild.empty:                               # full wipe: campaign over
        outcome.campaign_over = True
        return outcome

    if arena_offer and won:                       # arena bout: the flat purse
        outcome.arena_reward = arena_offer.purse
    elif won and battle.lethal:                   # lethal win: loot the field
        outcome.loot_pool = loot.field_loot(battle, fallen_combatants)
        
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


def advance(guild, dt=None, busy=()):
    """`_advance`, with the play recorder told which orders a person gave before it and
    which the engine made during it."""
    recorder.orders_issued(guild)
    try:
        return _advance(guild, dt, busy)
    finally:
        recorder.orders_settled(guild)


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
    forced = dt is not None
    active = [g for g in guild.groups if g.busy and g.order.kind != "garrison"]
    if not forced:
        if not active:
            return TickResult(hungry=[u for u in guild.roster if u.hunger_level > 0])
        dt = min(g.order.remaining for g in active)

    start_day = guild.clock.day
    events, casualties = guild.pass_time(dt, busy=busy)
    days_crossed = guild.clock.day - start_day
    if forced:
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
        if order.kind == "travel" and order.path:
            # arrived at a waypoint, not the final stop -- visibly stop here and
            # queue the next edge, rather than resolving the whole route at once
            prev = g.node
            g.node = order.dest
            events += _wear_wagons(g, prev, order.dest)
            pause = _arrival_pause(guild, g, prev, order.path)
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
            g.order = orders.next_leg(order.dest, list(order.path), g.speed)
            continue
        g.order = None                         # resolved -- the group goes idle
        if order.kind == "travel":
            prev = g.node
            g.node = order.dest
            events += _wear_wagons(g, prev, order.dest)
            pause = _arrival_pause(guild, g, prev, ())
            if pause is not None:
                pending.append((g, pause))
                continue
            for d in factions.settle(guild, factions.Event("travel", node=world.node(order.dest))):
                events.append(factions.deed_notice(d))
        elif order.kind == "work":
            events += guild._pay_shift(g.members, order.hours, order.eta, g.node)
        elif order.kind == "rest":
            events += guild.eat_now_pass(g.members)
        elif order.kind == "solo":
            events += solo.finish(guild, g, order)
        elif order.interactive:                # arena/market/bank/recruit/hunt
            pending.append((g, order))
    claim_events, claim_pending = _wilds_claim_attack_check(guild, days_crossed)
    events += claim_events
    pending += claim_pending
    for g, order in pending:
        if order.kind in orders.FORCED_KINDS:
            g.pending = order
    return TickResult(events=events, pending=pending, wiped=guild.empty, casualties=casualties, hungry=hungry)


def _wear_wagons(group, src, dest):
    """A leg walked: the road takes its toll on the group's wagons."""
    distance = next((w for v, w in world.neighbors(src) if v == dest), 0)
    return group.wear_wagons(distance)


def _arrival_pause(guild, group, prev_node, resume_path):
    """After `group` arrives at `group.node`: does anything happen there that
    must pause its order before the arrival is considered complete? Checked in
    order -- the guard (`justice.py`, jurisdiction) first, then a road ambush
    (`encounters.py`, an unsafe node), then the trust mission's fortress
    ambush (`missions.py`, mission-conditional, not a node property at all),
    then a raid on a squatted City property (`guild.house.squatting`),
    then a fight to retake a seized Wilds claim (`guild.wilds_claim_owner`) --
    and returns the `Order` to pause on, or None to let the caller proceed
    exactly as it would without any of them. The first two never both fire
    off one arrival in practice (no node is both a jurisdiction and unsafe
    today), but the order is deliberate in case that changes: the guard is a
    *legal* consequence of who you are, checked before whatever the road
    throws at you; the rest are checked last since each only ever fires at
    one specific node anyway."""
    guard = _guard_catch(group, prev_node, resume_path)
    if guard is not None:
        return guard
    ambush = _road_ambush_catch(group, resume_path)
    if ambush is not None:
        return ambush
    fortress = _fortress_ambush_catch(guild, group, resume_path)
    if fortress is not None:
        return fortress
    raid = _property_raid_catch(guild, group, resume_path)
    if raid is not None:
        return raid
    return _wilds_claim_retake_catch(guild, group, resume_path)


def _guard_catch(group, prev_node, resume_path):
    """If `group.node` is a jurisdiction node, roll the guard test
    (`justice.catch`) on its crime-carrying members. Returns a "guard" `Order`
    to pause on if anyone is caught, else None."""
    if not world.node(group.node).jurisdiction:
        return None
    caught = justice.catch(group)
    if not caught:
        return None
    return orders.Order("guard", caught=tuple(u.uid for u in caught),
                        prev_node=prev_node, resume_path=tuple(resume_path))


def _road_ambush_catch(group, resume_path):
    """If `group.node` is unsafe, roll `world.ROAD_AMBUSH_CHANCE` once (per
    leg, not per hour -- see `world.py`'s docstring) against the node's own
    `encounter_table`. Returns an "ambush" `Order` carrying the rolled pack to
    pause on if it hits, else None."""
    node = world.node(group.node)
    if not node.unsafe:
        return None
    chance = world.ROAD_AMBUSH_CHANCE
    if group.has_talent("woodland_scout"):
        chance /= 2.0
    if random.random() >= chance:
        return None
    pack = encounters.roll_encounter(node.encounter_table)
    return orders.Order("ambush", pack=tuple(pack), resume_path=tuple(resume_path))


FORTRESS_AMBUSH_LEVEL = constants.FORTRESS_AMBUSH_LEVEL   # placeholder, tune once this has been played -- see justice.py's own
FORTRESS_AMBUSH_SIZE = constants.FORTRESS_AMBUSH_SIZE    # placeholders for the guard patrol / Old Road pack


def _fortress_ambush_catch(guild, group, resume_path):
    """The trust mission's own one-off ambush at Ledger Hold
    (`missions.pending_fortress_ambush`): bandits who know the sealed chest is
    valuable, not a standing risk of the fortress itself the way `unsafe`
    marks the Old Road (so gated on the guild's mission state too, not just
    the node) -- but it still only ever happens AT Ledger Hold, hence the
    `ledger` function check up front, same shape as `_road_ambush_catch`'s own
    `node.unsafe` gate. Marks the mission's `ambush_done` the moment it fires,
    win or lose, so it never springs twice on the same shipment."""
    if not world.node(group.node).has("ledger"):
        return None
    mission = missions.pending_fortress_ambush(guild, group)
    if mission is None:
        return None
    mission.ambush_done = True
    pack = tuple(encounters.build_enemy(FORTRESS_AMBUSH_LEVEL)
                for _ in range(FORTRESS_AMBUSH_SIZE))
    return orders.Order("ambush", pack=pack, resume_path=tuple(resume_path))


CITY_RAID_CHANCE = constants.CITY_RAID_CHANCE    # per arrival at a squatted City property -- placeholder, tune once played
CITY_RAID_LEVEL = constants.CITY_RAID_LEVEL        # placeholders for the guard patrol sent to clear a squat
CITY_RAID_SIZE = 3


def _property_raid_catch(guild, group, resume_path):
    """The City guard coming to clear a squatted property
    (`guild.house.squatting`, set by `guild.house.squat` after
    the guild refuses a repossession offer): gated on the node's `property` function the
    same way `_fortress_ambush_catch` gates on `ledger`, plus the squat
    state itself, then rolls `CITY_RAID_CHANCE` once per arrival like
    `_road_ambush_catch` does for an unsafe node. Unlike a road ambush, losing
    this fight has a further consequence (`resolve_property_raid` ends the
    squat for good) -- see [[gartok-property-two-paths]]."""
    if not (guild.house.squatting and world.node(group.node).has("property")):
        return None
    if random.random() >= CITY_RAID_CHANCE:
        return None
    pack = tuple(encounters.build_enemy(CITY_RAID_LEVEL) for _ in range(CITY_RAID_SIZE))
    return orders.Order("eviction", pack=pack, resume_path=tuple(resume_path))


def _claim_attack_rolls(days):
    """Whether a claim attack lands over `days` calendar days crossed: `WILDS_RAID_CHANCE`
    is a per-day chance, so a jump of several days gets the odds of at least one hit and
    a call that crosses no midnight (a 1 h rest) never rolls."""
    return days > 0 and random.random() < 1 - (1 - economy.WILDS_RAID_CHANCE) ** days


def _wilds_claim_attack_check(guild, days):
    """`(events, pending)` for whichever periodic Wilds-claim attack applies
    after `days` calendar days crossed (see `_wilds_claim_raid_check`'s
    docstring for why this can't live on `_arrival_pause` like every other
    forced fight): a raid mid-`"SUSTAINING"`, or (Sistema 4) a seizure attempt
    once `"ESTABLISHED"` and still `guild.wilds_claim_owner == "guild"`. The
    two stages never overlap, so exactly one branch (or neither) ever fires."""
    if guild.wilds_claim_stage == "SUSTAINING":
        return [], _wilds_claim_raid_check(guild, days)
    if guild.wilds_claim_stage == "ESTABLISHED" and guild.wilds_claim_owner == "guild":
        return _wilds_claim_seizure_check(guild, days)
    return [], []


def _wilds_claim_raid_check(guild, days):
    """Whether a raider band tests the Wilds claim's garrison during
    `"SUSTAINING"`: not through `_arrival_pause` like every other forced
    fight above, because a garrison never "arrives" again after
    `orders.garrison` is issued (it's excluded from `active` on purpose), so
    nothing would ever call this if it lived on that seam instead. Rolls
    `economy.WILDS_RAID_CHANCE` per day crossed for each garrisoned group actually sitting at
    `world.WILDS_TERRITORY_NODE` -- carries `job` so a won fight can reissue
    the exact `orders.garrison(job)` it interrupted. Losing only resets the
    sustain countdown (`resolve_wilds_raid`) -- there is no ownership yet to
    lose."""
    pending = []
    for g in guild.groups:
        if g.empty or g.order is None or g.order.kind != "garrison":
            continue
        if g.node != world.WILDS_TERRITORY_NODE:
            continue
        if not _claim_attack_rolls(days):
            continue
        job = g.order.job
        pack = tuple(encounters.build_enemy(economy.WILDS_RAID_LEVEL)
                    for _ in range(economy.WILDS_RAID_SIZE))
        g.order = None
        pending.append((g, orders.Order("wilds_raid", pack=pack, job=job)))
    return pending


def _wilds_claim_seizure_check(guild, days):
    """Sistema 4: once `ESTABLISHED`, the same roll (`economy.WILDS_RAID_CHANCE`
    -- reused rather than a second tuning knob for what is the same kind of
    threat against the same ground) decides whether raiders test the claim.
    **Unguarded**, they simply take it -- no fight, nobody to contest it
    (`guild.wilds_claim_owner = "seized"` straight away, an `events` line for
    the caller since there is no battle to report the outcome of instead).
    **Garrisoned**, it plays out as a real fight (`"wilds_seizure"`, resolved
    by `resolve_wilds_seizure`) -- winning holds the claim, losing seizes it
    same as the unguarded case, but only after the garrison actually fell."""
    if not _claim_attack_rolls(days):
        return [], []
    garrison = next((g for g in guild.groups if not g.empty and g.order is not None
                     and g.order.kind == "garrison" and g.node == world.WILDS_TERRITORY_NODE),
                    None)
    if garrison is None:
        guild.wilds_claim_seize()
        return (["The Wilds claim sits unguarded -- it's seized without a fight."], [])
    job = garrison.order.job
    pack = tuple(encounters.build_enemy(economy.WILDS_RAID_LEVEL)
                for _ in range(economy.WILDS_RAID_SIZE))
    garrison.order = None
    return [], [(garrison, orders.Order("wilds_seizure", pack=pack, job=job))]


def _wilds_claim_retake_catch(guild, group, resume_path):
    """Arriving at a seized Wilds claim (Sistema 4, `guild.wilds_claim_owner
    == "seized"`): the occupiers are still holding it, same one-off shape as
    `_fortress_ambush_catch` (gated on `claim` rather than `ledger`,
    and on the guild's ownership state rather than a mission flag). Winning
    hands the ground back (`resolve_wilds_retake`) without redoing Sistema
    3's campaign; the structure was never touched, only who holds it."""
    if not (world.node(group.node).has("claim") and guild.wilds_claim_owner == "seized"):
        return None
    pack = tuple(encounters.build_enemy(economy.WILDS_RAID_LEVEL)
                for _ in range(economy.WILDS_RAID_SIZE))
    return orders.Order("wilds_retake", pack=pack, resume_path=tuple(resume_path))


# --------------------------------------------------------------------------- #
# resolving a paused "guard" order -- the three choices `justice_screen`      #
# offers, decided for the whole catch at once (see justice.py's docstring)    #
# and a paused "ambush" order -- no choice, just the fight `app` already ran  #
# --------------------------------------------------------------------------- #

def resolve_guard_prison(guild, group, order):
    """'Accept prison': jail every caught unit (its own days, off its own
    crime), then resume whatever the arrest interrupted."""
    events = []
    for u in list(group.members):
        if u.uid in order.caught:
            days = justice.jail(guild, u)
            events.append(f"{u.name} accepts arrest -- {days} day(s) in the City's cells.")
    events += _resume_arrival(guild, group, order)
    return events


def resolve_guard_flee(guild, group, order):
    """'Run': the group falls back to `order.prev_node` -- immediate, it
    already covered that ground. The fallback node gets the same arrival
    check as any other (`_arrival_pause`): a guard re-catch there carries
    `prev_node=None` (no further node to flee to is tracked, so
    `justice_screen.GuardScreen` hides RUN once that's the case), and an
    ambush is just as live if that node happens to be unsafe too.

    Returns `(events, pause)`: `pause` is the new "guard"/"ambush" `Order` for
    the caller to resolve next (same as a fresh entry in `TickResult.pending`
    -- `app._resolve_guard_flee` re-queues it through the normal dispatch), or
    None if the group is simply idle now. `([], None)` if called with nothing
    left to flee to."""
    group.pending = None
    if order.prev_node is None:
        return [], None
    caught = [u for u in group.members if u.uid in order.caught]
    names = ", ".join(u.name for u in caught) if caught else "The group"
    events = [f"{names} fall back toward {world.node(order.prev_node).name}."]
    group.node = order.prev_node
    pause = _arrival_pause(guild, group, None, ())
    if pause is not None:
        group.order = None            # same "not busy" convention as advance()
        if pause.kind in orders.FORCED_KINDS:
            group.pending = pause
        return events, pause
    group.order = orders.idle()
    return events, None


def resolve_guard_fight_aftermath(guild, group, order, outcome):
    """After `app` has already run the patrol fight through `absorb_battle`:
    every originally-caught unit that survived banks the crime the brawl adds
    (`justice.resolve_fight_crime`), then the group's order resumes."""
    events = []
    for u in outcome.survivors:
        if u.uid in order.caught:
            justice.resolve_fight_crime(u, outcome)
            events.append(f"{u.name} lives to fight another day -- crime now {u.crime}.")
    events += _resume_arrival(guild, group, order)
    return events


def resolve_road_ambush(guild, group, order):
    """After `app` has already run the ambush fight through `absorb_battle`:
    there is no choice to make here (unlike a guard catch) -- whoever's left
    just resumes whatever the ambush interrupted."""
    return _resume_arrival(guild, group, order)


def resolve_property_raid(guild, group, order, outcome):
    """After `app` has already run the eviction fight through `absorb_battle`:
    no choice to make (same as a road ambush), but losing has a consequence
    beyond casualties -- the guard finally clears the squat for good. Winning
    just drives the patrol off; the squat stands until the next roll."""
    events = _resume_arrival(guild, group, order)
    if outcome.won:
        events.insert(0, "The guild's fighters drive off the guard patrol -- the "
                      "property stays, for now.")
    else:
        guild.house.abandon()
        events.insert(0, "The City guard finally clears the squatted property -- it's gone for good.")
    return events


def resolve_wilds_raid(guild, group, order, outcome):
    """After `app` has already run the raid fight through `absorb_battle`: no
    choice to make (same as a road ambush), but this one doesn't go through
    `_resume_arrival` -- a garrisoned group was never "travelling" anywhere,
    it was just standing there. Winning reissues the same `orders.garrison`
    it interrupted; losing doesn't touch the stages already done, it only
    resets the sustain countdown (`Guild.wilds_claim_start_sustaining`'s
    value) and leaves survivors idle -- same "no partial punishment" shape
    `resolve_property_raid` uses for a lost City squat."""
    group.pending = None
    if group.empty:
        return []
    if outcome.won:
        group.order = orders.garrison(order.job)
        return ["The garrison drives off the raiders and keeps sustaining the claim."]
    guild.wilds_claim_sustain_days_left = economy.WILDS_CLAIM_SUSTAIN_DAYS
    group.order = orders.idle()
    return ["The garrison is scattered -- sustaining the claim starts over."]


def resolve_wilds_seizure(guild, group, order, outcome):
    """After `app` has already run the seizure fight through `absorb_battle`
    (Sistema 4, `ESTABLISHED` + garrisoned): winning resumes the same
    garrison job; losing hands the claim to the occupiers
    (`guild.wilds_claim_owner = "seized"`) -- unlike `resolve_wilds_raid`,
    there is no "try again from here", the structure stands but someone else
    holds it until a retake (`resolve_wilds_claim_retake`)."""
    group.pending = None
    if outcome.won:
        if not group.empty:
            group.order = orders.garrison(order.job)
        return ["The garrison drives off the raiders and holds the claim."]
    guild.wilds_claim_seize()
    if not group.empty:
        group.order = orders.idle()
    return ["The garrison falls -- the Wilds claim is seized."]


def resolve_wilds_claim_retake(guild, group, order, outcome):
    """After `app` has already run the retake fight through `absorb_battle`:
    winning hands the claim back to the guild (`resolve_wilds_claim_retake`
    itself never re-runs Sistema 3's campaign, the structure was never
    touched); losing just resumes whatever arrival this interrupted -- the
    claim stays seized, nothing stops the guild trying again."""
    events = _resume_arrival(guild, group, order)
    if outcome.won:
        guild.wilds_claim_owner = "guild"
        events.insert(0, "The Wilds claim is retaken -- the occupiers are driven out.")
    else:
        events.insert(0, "The attempt to retake the claim fails -- it stays lost.")
    return events


def _resume_arrival(guild, group, order):
    """Hand `group` back the order a guard/ambush pause interrupted: the rest
    of a multi-leg route if any is owed, or idle -- firing the "arrived"
    travel deed-settle event that was withheld while it was unresolved (skip
    it entirely on a guard "flee", which never really arrived)."""
    group.pending = None
    if group.empty:
        return []
    if order.resume_path:
        group.order = orders.next_leg(group.node, list(order.resume_path), group.speed)
        return []
    events = [factions.deed_notice(d) for d in
             factions.settle(guild, factions.Event("travel", node=world.node(group.node)))]
    group.order = orders.idle()
    return events


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
        guild.ancient_ruins_discovered = True
        name = scout.name if scout else "The squad"
        msg = f"{name} spots ancient stone markers half-buried in the scrub! The Ancient Ruins are discovered."
        return True, msg
    else:
        name = scout.name if scout else "The squad"
        msg = f"{name} spends 4 hours searching the brush, but finds no trace of the ruins (d20({nat}) {wis_mod:+}(WIS) = {total} vs DC {dc})."
        return False, msg
