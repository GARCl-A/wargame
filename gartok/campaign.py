"""Folding a finished battle back into the campaign.

`Battle` wraps each squad member in a `Combatant` that carries all the battle
state (see `battle.py`), so the persistent roster is untouched during the fight;
once it is over this maps the outcome onto that roster:

- permadeath drops the fallen from `guild.roster`;
- survivors keep the little that carries forward (a lit torch, for now) and
  otherwise return at full HP -- the rest of the spoils come from the loot pool;
- the campaign clock advances by the rounds fought (~6 s each);
- a win bumps the tally, and an arena win also raises `arena_reputation`.

`app` owns the *screen* that comes next (loot, reward, or straight to the map);
this module owns the *state change*, returned as a `BattleOutcome`.
"""

from dataclasses import dataclass, field

from . import data, loot


@dataclass
class BattleOutcome:
    won: bool
    survivors: list                              # roster units that came back
    fallen: list                                 # roster units lost for good
    loot_pool: list = field(default_factory=list)  # item names on the field (lethal win only)
    arena_reward: int | None = None              # copper purse to hand out (arena win only)
    campaign_over: bool = False                   # the guild is empty now
    xp_awards: dict = field(default_factory=dict)  # {member name: combat XP gained this battle}


def _carry_forward(member, combatant):
    """The only battle state a survivor keeps: a torch still in hand, plus any
    spare torches picked up during the fight."""
    member.equipped_offhand = data.TORCH_ITEM if combatant.torch_hand else None
    spares = combatant.inventory.count(data.TORCH_ITEM)
    member._base_inventory = (
        [it for it in member._base_inventory if it != data.TORCH_ITEM]
        + [data.TORCH_ITEM] * spares)


def absorb_battle(guild, squad, battle, arena_offer=None):
    """Fold `battle`'s result into `guild` (mutates it) and return a `BattleOutcome`.

    `squad` is the same-order list of roster units that `battle.player_units`
    wraps. `arena_offer` is the staked tier for an arena bout, or None.
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

    if guild.empty:                               # full wipe: campaign over
        return BattleOutcome(won, survivors, fallen, campaign_over=True, xp_awards=xp_awards)

    if arena_offer and won:                       # arena bout: reputation + the purse
        guild.arena_reputation += 1
        return BattleOutcome(won, survivors, fallen, arena_reward=arena_offer["purse"],
                             xp_awards=xp_awards)

    pool = loot.field_loot(battle, fallen_combatants) if won and battle.lethal else []
    return BattleOutcome(won, survivors, fallen, loot_pool=pool, xp_awards=xp_awards)
