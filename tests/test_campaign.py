"""Folding a battle back into the guild; the arena deeds and the title."""

import random
from dataclasses import replace

from tests.helpers import abilities, actions, Battle, CustomScenario, data, Unit, world


# --------------------------------------------------------------------------- #
# Campaign: folding a battle back into the guild                                #
# --------------------------------------------------------------------------- #

def test_absorb_battle_permadeath_and_clock():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(2)
    squad = [Unit("player") for _ in range(3)]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    battle.round_no = 4
    battle.player_units[1].status = "dead"          # the middle member falls
    battle.player_units[0].status = battle.player_units[2].status = "up"

    out = campaign.absorb_battle(guild, squad, battle)

    assert out.won and not out.campaign_over
    assert squad[1] not in guild.roster and len(guild.roster) == 2
    assert out.fallen == [squad[1]] and set(out.survivors) == {squad[0], squad[2]}
    assert guild.battles_won == 1
    assert guild.clock.seconds == 4 * 6                # ~6 s per round fought


def test_absorb_battle_carries_the_equipped_lantern_forward():
    from gartok import campaign
    from gartok.guild import Guild
    random.seed(2)
    member = Unit("player")
    member.equipped_weapon, member.equipped_offhand = "Dagger", data.LANTERN_ITEM
    squad = [member]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")])
    battle.winner = "player"
    battle.round_no = 1
    battle.player_units[0].status = "up"

    campaign.absorb_battle(guild, squad, battle)

    assert member.equipped_offhand == data.LANTERN_ITEM
    assert data.LANTERN_ITEM not in member._base_inventory   # equipped, not double-counted


def test_absorb_battle_arena_win_pays_the_purse_not_loot():
    from gartok import campaign, world
    from gartok.guild import Guild
    random.seed(5)
    squad = [Unit("player")]
    guild = Guild(list(squad))
    battle = Battle(squad, [Unit("enemy")], lethal=False)
    battle.winner = "player"
    for u in battle.player_units:
        u.status = "up"

    out = campaign.absorb_battle(guild, squad, battle, node=world.node("arena"),
                                 arena_offer=world.Bout("Bronze ring", entry=15, purse=55,
                                                        enemies=1, rep=2))
    assert out.arena_reward == 55 and out.loot_pool == []
    # a first arena win completes "First Blood" -> +1 reputation with the Pits
    # (not Lone Wolf: this bout is above the entry tier)
    assert [d.id for d in out.deeds_earned] == ["arena_first_blood"]
    assert guild.arena_reputation == 1 and "arena_first_blood" in guild.deeds_done


_ENTRY_TIER = world.Bout("Rookie pit", entry=4, purse=15, enemies=1, rep=0)


def _arena_bout(guild, n=1, tier=None, node_id="arena", win=True):
    from gartok import campaign, world
    squad = [Unit("player") for _ in range(n)]
    guild.roster = list(squad)
    battle = Battle(squad, [Unit("enemy") for _ in range(n)], lethal=False)
    battle.winner = "player" if win else "enemy"
    for u in battle.player_units:
        u.status = "up"
    return campaign.absorb_battle(guild, squad, battle, node=world.node(node_id),
                                  arena_offer=tier or _ENTRY_TIER)


def test_deeds_are_one_shot_and_only_move_rep_they_earn():
    from gartok.guild import Guild
    random.seed(6)
    guild = Guild([Unit("player")])

    first = _arena_bout(guild, n=2)               # a party win: First Blood only
    assert [d.id for d in first.deeds_earned] == ["arena_first_blood"]
    assert guild.arena_reputation == 1

    again = _arena_bout(guild, n=2)               # a 2nd arena win earns nothing now
    assert again.deeds_earned == []
    assert guild.arena_reputation == 1            # no per-win grind
    assert guild.deeds_done == ["arena_first_blood"]


def test_lone_wolf_wants_a_solo_win_in_the_entry_pit():
    from gartok.guild import Guild
    random.seed(9)

    # a solo win in the entry pit clears First Blood AND Lone Wolf at once
    g1 = Guild([Unit("player")])
    earned = {d.id for d in _arena_bout(g1, n=1).deeds_earned}
    assert earned == {"arena_first_blood", "arena_lone_wolf"}
    assert g1.arena_reputation == 2

    # two fighters -> not solo
    g2 = Guild([Unit("player")])
    assert "arena_lone_wolf" not in {d.id for d in _arena_bout(g2, n=2).deeds_earned}

    # solo, but not the entry tier
    g3 = Guild([Unit("player")])
    bronze = replace(_ENTRY_TIER, rep=2, name="Bronze ring")
    assert "arena_lone_wolf" not in {d.id for d in _arena_bout(g3, n=1, tier=bronze).deeds_earned}


def test_dethrone_waits_for_the_champion_bout():
    from gartok.guild import Guild
    random.seed(10)

    g1 = Guild([Unit("player")])
    assert "arena_dethrone" not in {d.id for d in _arena_bout(g1, n=2).deeds_earned}

    g2 = Guild([Unit("player")])
    champ = replace(_ENTRY_TIER, champion=True)   # what "Challenge the Champion" will pass
    assert "arena_dethrone" in {d.id for d in _arena_bout(g2, n=2, tier=champ).deeds_earned}


def test_a_lost_or_non_arena_fight_completes_no_arena_deed():
    from gartok.guild import Guild
    random.seed(7)

    g1 = Guild([Unit("player")])
    assert _arena_bout(g1, n=1, win=False).deeds_earned == [] and g1.arena_reputation == 0

    g2 = Guild([Unit("player")])                  # a win, but not in the pits
    assert _arena_bout(g2, n=1, node_id="wilds").deeds_earned == [] and g2.arena_reputation == 0


def test_settle_takes_any_event_and_arena_deeds_ignore_non_battle_ones():
    from gartok import factions
    from gartok.guild import Guild
    guild = Guild([Unit("player")])

    # a non-battle event (arriving somewhere): nothing earned, nothing raised on
    # the missing outcome
    assert factions.settle(guild, factions.Event("travel", node=world.node("arena"))) == []
    assert guild.reputation == {}

    # the same event must not satisfy an arena deed -- those key off kind "battle"
    open_before = {d.id for d in factions.open_deeds(guild)}
    factions.settle(guild, factions.Event("travel", node=world.node("arena")))
    assert {d.id for d in factions.open_deeds(guild)} == open_before


# --------------------------------------------------------------------------- #
# arena: the Champion of the Pit title                                         #
# --------------------------------------------------------------------------- #

def _champion_battle(guild, squad):
    """A champion bout where `squad[0]` lands the blow that puts Adelio down."""
    from gartok import arena
    champ = arena.load_champion()
    battle = Battle(list(squad), [champ, Unit("enemy"), Unit("enemy")],
                    lethal=False, arena=True)
    battle.winner = "player"
    for u in battle.player_units:
        u.status = "up"
    cc = next(c for c in battle.enemy_units
              if getattr(c, "arena_role", None) == "champion")
    battle.player_units[0].credit_kill(cc)        # the finishing blow
    return battle


def test_champion_bout_is_fought_on_the_authored_pit_map():
    from gartok import arena, map_lib
    random.seed(3)
    offer = arena.champion_bout()
    assert offer.map_slug == arena.CHAMPION_MAP

    champ = arena.load_champion()
    batt = Battle([Unit("player")], [champ, Unit("enemy"), Unit("enemy")],
                  scenario=CustomScenario(map_lib.load_map(offer.map_slug)),
                  lethal=False, arena=True)
    assert any(z < 0 for z in batt.board.elevation.values())   # the hole it is named for
    champ_c = next(c for c in batt.enemy_units
                   if getattr(c, "arena_role", None) == "champion")
    assert champ_c.pos == (14, 7)                              # the map's NPC cell
    # win condition unchanged: the whole team has to go down, not just Adelio
    champ_c.status = "stable"
    assert batt._check_winner() is None
    for goon in (c for c in batt.enemy_units if c is not champ_c):
        goon.status = "stable"
    assert batt._check_winner() == "player"


def test_champion_title_goes_to_the_finisher():
    from gartok import arena, campaign, world
    from gartok.guild import Guild
    random.seed(11)
    winner, other = Unit("player"), Unit("player")
    guild = Guild([winner, other], node="arena")
    battle = _champion_battle(guild, [winner, other])
    out = campaign.absorb_battle(guild, [winner, other], battle,
                                 node=world.node("arena"), arena_offer=arena.champion_bout())
    assert "arena_dethrone" in {d.id for d in out.deeds_earned}
    assert winner.arena_title and not other.arena_title
    assert guild.arena_challenge_day == guild.clock.day + arena.CHALLENGE_CYCLE


def test_champion_title_stays_vacant_on_a_messy_finish():
    from gartok import arena, campaign, world
    from gartok.guild import Guild
    random.seed(12)
    p = Unit("player")
    guild = Guild([p], node="arena")
    champ = arena.load_champion()
    battle = Battle([p], [champ, Unit("enemy")], lethal=False, arena=True)
    battle.winner = "player"
    for u in battle.player_units:
        u.status = "up"
    # nobody credited with putting the champion down
    out = campaign.absorb_battle(guild, [p], battle, node=world.node("arena"),
                                 arena_offer=arena.champion_bout())
    assert "arena_dethrone" in {d.id for d in out.deeds_earned}   # deed still lands
    assert not p.arena_title and guild.arena_challenge_day is None


def test_title_defense_won_keeps_the_title_and_renews_the_cycle():
    from gartok import arena, campaign, world
    from gartok.guild import Guild
    random.seed(0)
    champ = Unit("player")
    champ.arena_title = True
    guild = Guild([champ], node="arena")
    guild.arena_challenge_day = guild.clock.day               # a challenge was due
    battle = Battle([champ], [Unit("enemy")], lethal=False, arena=True)
    battle.winner = "player"
    for u in battle.player_units:
        u.status = "up"
    out = campaign.absorb_battle(guild, [champ], battle, node=world.node("arena"),
                                 arena_offer=arena.defense_bout())
    assert champ.arena_title                                  # kept
    assert guild.arena_challenge_day == guild.clock.day + arena.CHALLENGE_CYCLE
    assert out.arena_reward == arena.DEFENSE_PURSE            # a win pays the defense purse


def test_title_defense_is_due_and_forfeits_when_missed():
    from gartok import arena
    from gartok.guild import Guild
    from gartok.clock import Clock, SECONDS_PER_DAY
    champ = Unit("player")
    champ.arena_title = True
    guild = Guild([champ], node="city")
    guild.clock = Clock(0)
    guild.arena_challenge_day = 5
    guild.clock.seconds = 5 * SECONDS_PER_DAY
    assert arena.defense_due(guild)
    guild.clock.seconds = (5 + arena.CHALLENGE_GRACE + 1) * SECONDS_PER_DAY
    assert not arena.defense_due(guild)
    assert arena.sync(guild) and not champ.arena_title and guild.arena_challenge_day is None


def test_challenger_is_built_one_mean_level_above():
    from gartok import arena
    random.seed(13)
    ch = arena.build_challenger(4)
    assert ch.mean_level == 4
    assert all(ch.picks_available(t) == 0 for t in ("combat", "work"))


def test_arena_title_only_bites_inside_the_arena():
    a = Unit("player"); a.languages = ["Elvish"]
    d = Unit("enemy"); d.languages = ["Orcish"]
    a._ability = abilities.get("none")

    for in_arena, expected in ((True, True), (False, False)):
        batt = Battle([a], [d], arena=in_arena)
        ac, dc = batt.player_units[0], batt.enemy_units[0]
        ac.arena_title = True
        ac.ap, ac.torch_hand = 2, True
        ac.pos, dc.pos = (5, 5), (6, 5)
        assert actions.DEMORALIZE.can(batt, ac, dc) is expected


def test_arena_offers_scale_with_reputation():
    from gartok import world
    assert [o.name for o in world.arena_offers(0)] == ["Rookie pit"]
    assert [o.name for o in world.arena_offers(2)] == ["Rookie pit"]  # 3 deeds = 3 rep
    assert len(world.arena_offers(3)) == 2                               # ...opens Bronze
    assert len(world.arena_offers(99)) == len(world.ARENA_TIERS)
    # ordered cheapest first; one fighter's entry always below the purse
    for tier in world.ARENA_TIERS:
        assert tier.entry < tier.purse


def test_arena_entry_is_staked_per_fighter():
    from gartok.app import App
    from gartok.squad_screen import SquadScreen
    from gartok import world

    roster = [Unit("player") for _ in range(3)]
    for u in roster:
        u.gold = 50
    iron = world.ARENA_TIERS[2]                       # Iron cage: 3 opponents, squad of 3
    scr = SquadScreen(None, roster, world.node("arena"), on_confirm=lambda *a: None,
                      on_back=lambda: None, arena_offers=[iron])
    assert scr.picked == roster                       # roster fits the cap, all auto-picked
    assert scr.entry_cost == iron.entry * 3
    assert scr.ok and scr.picked_gold >= scr.entry_cost

    scr.picked = roster[:1]                           # solo pays a third
    assert scr.entry_cost == iron.entry

    # the app bills that whole stake off the squad, richest first
    App._charge(roster, iron.entry * 3)
    assert sum(u.gold for u in roster) == 150 - iron.entry * 3
