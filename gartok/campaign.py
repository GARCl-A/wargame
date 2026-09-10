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
  Pits. The deed checks read `node`, `arena_tier` (a `world.Bout`) and
  `squad_size` off the outcome, so those are set before `settle`.

`app` owns the *screen* that comes next (loot, reward, or straight to the map);
this module owns the *state change*, returned as a `BattleOutcome`.
"""

from dataclasses import dataclass, field

from . import arena, data, factions, loot


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
    """The only battle state a survivor keeps: a torch still in hand, plus any
    spare torches picked up during the fight."""
    member.equipped_offhand = data.TORCH_ITEM if combatant.torch_hand else None
    spares = combatant.inventory.count(data.TORCH_ITEM)
    member._base_inventory = (
        [it for it in member._base_inventory if it != data.TORCH_ITEM]
        + [data.TORCH_ITEM] * spares)


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

    guild.roster = [u for u in guild.roster if u not in fallen]
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

    outcome.deeds_earned = factions.settle(guild, node, outcome)

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
