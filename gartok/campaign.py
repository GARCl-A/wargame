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

import random
from dataclasses import dataclass, field

from . import arena, data, encounters, factions, justice, loot, orders, world


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


def _carry_forward(member, combatant):
    """The only battle state a survivor keeps: a light source still in hand
    (torch or lantern), plus any spare torches picked up during the fight."""
    if combatant.torch_hand:
        member.equipped_offhand = data.TORCH_ITEM
    elif combatant.lantern_hand:
        member.equipped_offhand = data.LANTERN_ITEM
    else:
        member.equipped_offhand = None
    torch_spares = combatant.inventory.count(data.TORCH_ITEM)
    lantern_spares = combatant.inventory.count(data.LANTERN_ITEM)
    member._base_inventory = (
        [it for it in member._base_inventory
         if it not in (data.TORCH_ITEM, data.LANTERN_ITEM)]
        + [data.TORCH_ITEM] * torch_spares
        + [data.LANTERN_ITEM] * lantern_spares)


def absorb_battle(guild, squad, battle, node=None, arena_offer=None):
    """Fold `battle`'s result into `guild` (mutates it) and return a `BattleOutcome`.

    `squad` is the same-order list of roster units that `battle.player_units`
    wraps. `node` is the world node the fight happened at (for the faction deeds);
    `arena_offer` is the `world.Bout` for an arena fight, or None.
    """
    survivors, fallen, fallen_combatants, xp_awards = [], [], [], {}
    for combatant, member in zip(battle.player_units, squad):
        if combatant.survived:
            if combatant.combat_xp_earned:        # XP scaled by the level gap of each kill
                member.combat_xp += combatant.combat_xp_earned
                member.collect_levels()           # a new mean level rolls a hit die
                xp_awards[member.name] = combatant.combat_xp_earned
            _carry_forward(member, combatant)
            survivors.append(member)
        else:
            fallen.append(member)
            fallen_combatants.append(combatant)

    guild.remove_members(fallen)
    guild.clock.advance_rounds(battle.round_no)
    won = battle.winner == "player"
    if won:
        guild.record_victory()

    player_kos = sum(c.kills for c in battle.player_units)
    outcome = BattleOutcome(won, survivors, fallen, xp_awards=xp_awards,
                            squad_size=len(squad), player_kos=player_kos,
                            arena_tier=arena_offer)

    if guild.empty:                               # full wipe: campaign over
        outcome.campaign_over = True
        return outcome

    if arena_offer and won:                       # arena bout: the flat purse
        outcome.arena_reward = arena_offer.purse
    elif won and battle.lethal:                   # lethal win: loot the field
        outcome.loot_pool = loot.field_loot(battle, fallen_combatants)

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


def advance(guild, dt=None):
    """Jump the world forward, running daily upkeep for every day crossed, then
    resolving whichever group(s) reached their order in that span.
    `travel`/`work` orders resolve silently here; every other kind comes back
    in `TickResult.pending` for the caller to play its screen and then set a
    fresh order (or `orders.idle()`) on that group before calling `advance`
    again. A group with no order, or an idle one, never blocks the jump and is
    left alone.

    `dt=None` (the default -- the ADVANCE button) jumps to the **soonest**
    order completion across every group with one in flight; no-op if nothing
    is. A caller may instead force a specific `dt` (hours) -- the map's
    MAINTENANCE stop -- so every in-flight order's `remaining` stays in
    lockstep with the shared clock even when nothing is due yet (an order that
    happens to complete within a forced `dt` still resolves normally); a forced
    stop also runs `Guild.eat_now_pass` (anyone still hungry eats right now,
    without waiting for the next daily meal) -- that's what makes it a
    *maintenance* stop rather than just a short jump."""
    forced = dt is not None
    active = [g for g in guild.groups if g.busy]
    if not forced:
        if not active:
            return TickResult()
        dt = min(g.order.remaining for g in active)

    events = guild.pass_time(dt)
    if forced:
        events += guild.eat_now_pass()
    if guild.empty:
        return TickResult(events=events, wiped=True)

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
            pause = _arrival_pause(g, prev, order.path)
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
            g.order = orders.next_leg(order.dest, list(order.path))
            continue
        g.order = None                         # resolved -- the group goes idle
        if order.kind == "travel":
            prev = g.node
            g.node = order.dest
            pause = _arrival_pause(g, prev, ())
            if pause is not None:
                pending.append((g, pause))
                continue
            for d in factions.settle(guild, factions.Event("travel", node=world.node(order.dest))):
                events.append(factions.deed_notice(d))
        elif order.kind == "work":
            events += guild._pay_shift(g.members, order.hours, order.eta)
        elif order.interactive:                # arena/market/bank/recruit/hunt
            pending.append((g, order))
    return TickResult(events=events, pending=pending, wiped=guild.empty)


def _arrival_pause(group, prev_node, resume_path):
    """After `group` arrives at `group.node`: does anything happen there that
    must pause its order before the arrival is considered complete? Checked in
    order -- the guard (`justice.py`, jurisdiction) first, then a road ambush
    (`encounters.py`, an unsafe node) -- and returns the `Order` to pause on,
    or None to let the caller proceed exactly as it would without either
    system. The two never both fire off one arrival in practice (no node is
    both a jurisdiction and unsafe today), but the order is deliberate in case
    that changes: the guard is a *legal* consequence of who you are, checked
    before whatever the road throws at you."""
    guard = _guard_catch(group, prev_node, resume_path)
    if guard is not None:
        return guard
    return _road_ambush_catch(group, resume_path)


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
    if not node.unsafe or random.random() >= world.ROAD_AMBUSH_CHANCE:
        return None
    pack = encounters.roll_encounter(node.encounter_table)
    return orders.Order("ambush", pack=tuple(pack), resume_path=tuple(resume_path))


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
    if order.prev_node is None:
        return [], None
    caught = [u for u in group.members if u.uid in order.caught]
    names = ", ".join(u.name for u in caught) if caught else "The group"
    events = [f"{names} fall back toward {world.node(order.prev_node).name}."]
    group.node = order.prev_node
    pause = _arrival_pause(group, None, ())
    if pause is not None:
        group.order = None            # same "not busy" convention as advance()
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


def _resume_arrival(guild, group, order):
    """Hand `group` back the order a guard/ambush pause interrupted: the rest
    of a multi-leg route if any is owed, or idle -- firing the "arrived"
    travel deed-settle event that was withheld while it was unresolved (skip
    it entirely on a guard "flee", which never really arrived)."""
    if group.empty:
        return []
    if order.resume_path:
        group.order = orders.next_leg(group.node, list(order.resume_path))
        return []
    events = [factions.deed_notice(d) for d in
             factions.settle(guild, factions.Event("travel", node=world.node(group.node)))]
    group.order = orders.idle()
    return events
