"""The Dragon's Lair (lair.py, missions.BLOOD_CLUTCH): finding it from the Mine, the board, the
dragon's sleep and the noise that ends it, the kobold patrols and their challenge, leaving with
an egg, what the squad keeps, the dragon itself, Dragonfire, and the keepers who buy eggs."""

import random

import pygame
import pytest

from gartok import (
    actions,
    ai,
    combat_lab,
    data,
    dialogue,
    economy,
    factions,
    items,
    lair,
    loot,
    missions,
    npc_lib,
    world,
)
from gartok.battle import Battle
from gartok.clock import Clock
from gartok.group import Group
from gartok.guild import Guild
from gartok.scenario import ErmosScenario
from tests.helpers import Unit, _FixedRNG, make_app


def _lair(seed=6, level=3, size=4):
    battle, _ = combat_lab.build("lair", level, size, seed=seed)
    return battle, battle.scenario


def _guild(node="mine", n=2):
    random.seed(7)
    g = Group([Unit("player") for _ in range(n)], node=node)
    guild = Guild(None, groups=[g])
    guild.clock = Clock()
    return guild, g


def _take_clutch(guild, group):
    guild.missions.append(missions.Mission(missions.LIBRARY_ANCIENT_CODEX.id, group.members[0].uid, 1, None,
                                           state="done"))
    assert missions.BLOOD_CLUTCH in missions.offers_at(guild, "blood_sanctuary")
    return missions.accept(guild, group.leader, missions.BLOOD_CLUTCH)


# --- finding the lair --------------------------------------------------------- #

def test_the_lair_is_a_hidden_node_two_hours_off_the_mine():
    n = world.node(lair.NODE)
    assert n.hidden and n.has("dragon_lair") and dict(world.neighbors(lair.NODE)) == {"mine": 2}


def test_searching_the_mine_finds_nothing_without_the_job():
    guild, g = _guild()
    found, msg = lair.search(guild, g, _FixedRNG(20))
    assert not found and not guild.is_node_revealed(lair.NODE) and "echoes" in msg


def test_searching_with_the_job_out_rolls_wisdom_and_reveals_it():
    guild, g = _guild()
    _take_clutch(guild, g)
    found, msg = lair.search(guild, g, _FixedRNG(1))
    assert not found and "DC 12" in msg
    found, _ = lair.search(guild, g, _FixedRNG(20))
    assert found and guild.is_node_revealed(lair.NODE)


def test_the_map_offers_the_search_at_the_mine_while_the_job_is_out():
    from gartok.map_screen import MapScreen
    from gartok.ui.tokens import fonts
    guild, g = _guild()
    ms = MapScreen(fonts(), guild, on_guild=None, on_wipe=None, on_advance=None, on_manage_group=None)
    keys = [b.get("key") for b in ms._inspector_content(g, world.node("mine"))]
    assert "search_lair" not in keys
    _take_clutch(guild, g)
    keys = [b.get("key") for b in ms._inspector_content(g, world.node("mine"))]
    assert "search_lair" in keys


# --- the board ------------------------------------------------------------------ #

def test_the_board_holds_the_eggs_the_hoard_the_patrols_and_the_dragon_asleep():
    b, sc = _lair()
    eggs = [o for o in b.ground if o.is_relic and o.item_name == lair.EGG]
    piles = [o for o in b.ground if o.is_chest]
    assert len(eggs) == len(lair.EGG_CELLS) and len(piles) == len(lair.HOARD_PILES)
    dragon = lair.dragon_of(b)
    assert dragon.pos == lair.DRAGON_CELL and dragon.dormant and dragon.footprint == 3
    patrols = [u for u in b.foe_units if getattr(u, "patrol_route", None)]
    assert len(patrols) == sum(len(s) for s, _ in lair.PATROLS)
    assert all(u.race["name"] == "Kobold" and "Draconic" in u.languages for u in patrols)
    assert all(set(b.cells_of(u)) <= lair._cells(*lair.MOUTH) for u in b.player_units)
    assert sc.stage == "asleep" and b.escape_cells == set(lair.ENTRANCE)


def test_the_tunnel_out_is_too_narrow_for_the_dragon():
    b, _ = _lair()
    dragon = lair.dragon_of(b)
    dest = b.path_step_toward(dragon, (2, 10), 999, reach=0)
    assert dest[0] > 8                         # it can get to the warren, never into the tunnel


# --- the dragon's sleep ------------------------------------------------------------ #

def test_noise_stirs_then_wakes_the_dragon():
    b, sc = _lair()
    dragon = lair.dragon_of(b)
    sc.hear(b, lair.STIR_AT, "test")
    assert sc.stage == "stirring" and dragon.dormant and dragon.awareness_radius == lair.STIR_SIGHT
    sc.hear(b, lair.WAKE_AT, "test")
    assert sc.stage == "awake" and not dragon.dormant and dragon.alerted and b.aggressor == "enemy"


def test_running_near_the_dragon_is_loud_and_a_creep_rolls_dex_against_its_watch():
    b, sc = _lair()
    me = b.player_units[0]
    me.pos = (30, 10)
    me.path = [(30 - k, 10) for k in range(me.speed, -1, -1)]
    sc.on_turn_end(b, me)
    assert sc.noise == lair.RUN + (lair.CLANK if me.armor is not None and me.armor.speed_penalty else 0)
    sc.noise = 0
    me.path = [(29, 10), (30, 10)]
    sc.rng = _FixedRNG(1)
    sc.on_turn_end(b, me)
    assert sc.noise >= lair.MISSTEP
    sc.noise = 0
    sc.rng = _FixedRNG(20)
    me.equipped_armor = None
    sc.on_turn_end(b, me)
    assert sc.noise == (lair.CLANK if me.armor is not None and me.armor.speed_penalty else 0)


def test_footsteps_far_from_the_dragon_go_unheard():
    b, sc = _lair()
    me = b.player_units[0]
    me.path = [(1, 10), (2, 10), (3, 10), (4, 10), (5, 10), (6, 10), (7, 10), (8, 10)]
    sc.on_turn_end(b, me)
    assert sc.noise == 0


def test_a_blow_struck_anywhere_carries_to_the_dragon():
    b, sc = _lair()
    me, foe = b.player_units[0], b.foe_units[0]
    sc.on_turn_start(b, me)
    foe.hp -= 1
    sc.on_turn_end(b, me)
    assert sc.noise >= lair.BLOW


def test_scooping_the_hoard_and_lifting_an_egg_are_noise():
    b, sc = _lair()
    me = b.player_units[0]
    pile = next(o for o in b.ground if o.is_chest)
    egg = next(o for o in b.ground if o.is_relic)
    sc.on_pick_up(b, me, pile)
    sc.on_pick_up(b, me, egg)
    assert sc.noise == lair.HOARD + lair.LIFT


def test_picking_up_a_hoard_pile_pays_the_carrier_at_once():
    b, sc = _lair()
    me = b.player_units[0]
    pile = next(o for o in b.ground if o.is_chest)
    me.pos = pile.pos
    before = me.char.money
    actions.PICK_UP.execute(b, me)
    assert me.char.money > before and sc.noise == lair.HOARD


def test_the_hoard_contains_the_scroll_of_hex():
    b, _ = _lair()
    hex_chest = next(o for o in b.ground if o.is_chest and o.pos == lair.HEX_CELL)
    assert lair.HEX_SCROLL in hex_chest.contents
    me = b.player_units[0]
    me.pos = hex_chest.pos
    actions.PICK_UP.execute(b, me)
    assert lair.HEX_SCROLL in me.inventory


# --- the breath -------------------------------------------------------------------- #

def test_the_dragons_breath_leaves_the_lair_burning():
    b, _ = _lair()
    dragon = lair.dragon_of(b)
    dragon.ap = 2
    dragon.dormant = False
    target = (dragon.pos[0] - 1, dragon.pos[1] + 1)
    random.seed(1)
    actions.DRAGON_BREATH.execute(b, dragon, target)
    assert b.fire and b.fire <= set(actions.DRAGON_BREATH.area_cells(b, dragon, target))


# --- the patrols ------------------------------------------------------------------- #

def _patrol_member(b, pid=0):
    return next(u for u in b.foe_units if getattr(u, "patrol_id", None) == pid)


def test_a_patrol_that_sees_nobody_walks_its_round():
    b, _ = _lair()
    k = _patrol_member(b)
    start = k.pos
    while b.active is not k:
        b.active.ap = 0
        b.end_turn()
    ai.take_turn(b, k)
    assert k.pos != start and not getattr(k, "alerted", False)


def test_a_patrol_that_sees_an_egg_rings_the_alarm():
    b, sc = _lair()
    k = _patrol_member(b)
    thief = b.player_units[0]
    thief.inventory.append(lair.EGG)
    assert sc.contact(b, k, [thief]) == "fight"
    assert sc.alarm and all(u.alerted for u in sc.patrol(b, 1)) and sc.noise >= lair.ALARM


def test_a_patrol_challenge_goes_to_the_player_when_a_person_plays():
    b, sc = _lair()
    k = _patrol_member(b)
    asked = []
    b.talk_handler = lambda enc, members, done: asked.append((enc, members, done))
    assert sc.contact(b, k, [b.player_units[0]]) == "wait"
    enc, members, done = asked[0]
    assert isinstance(enc, dialogue.Challenge) and enc.offered() == ("bluff", "bribe", "attack")
    assert members == [c.char for c in b.player_units]
    done(dialogue.Result("peace", "paid"))
    assert 0 in sc.parleyed and sc.contact(b, k, [b.player_units[0]]) == "pass"


def test_fighting_a_patrol_gives_one_round_before_it_calls_out():
    b, sc = _lair()
    k = _patrol_member(b)
    enc = dialogue.Challenge(sc.patrol(b, 0))
    sc.settle(b, 0, enc, dialogue.Result("fight", "steel", dialogue.Opening()))
    assert not sc.alarm and 0 in sc.alarm_due and all(u.alerted for u in sc.patrol(b, 0))
    sc.on_turn_start(b, k)
    assert sc.alarm


def test_a_failed_bluff_rings_the_alarm_and_catches_the_squad_off_guard():
    b, sc = _lair()
    enc = dialogue.Challenge(sc.patrol(b, 0))
    enc.bluffs_told = 1
    sc.settle(b, 0, enc, dialogue.Result("fight", "lie", dialogue.Opening(surprised="player")))
    assert sc.alarm and sc.bluffs == 1
    assert all(u.has_condition("surprised") for u in b.player_units if u.alive)


def test_the_challenge_wants_draconic_even_for_a_bribe_and_each_bluff_is_harder():
    pack = [Unit("enemy") for _ in range(3)]
    for u in pack:
        u.languages = ["Draconic"]
    me = Unit("player")
    me.languages = ["Common"]
    me.money = 999
    enc = dialogue.Challenge(pack)
    opts = {o.verb: o for o in enc.options(me, [me])}
    assert opts["bluff"].block == opts["bribe"].block == "needs Draconic" and opts["attack"].open
    me.languages.append("Draconic")
    assert dialogue.Challenge(pack, bluffs=2).dc("bluff") == enc.dc("bluff") + 2 * dialogue.BLUFF_STEP
    result = enc.choose("bluff", me, [me], rng=_FixedRNG(-99))
    assert result.opening.surprised == "player" and enc.bluffs_told == 1


def test_without_a_person_the_ai_answers_the_challenge_itself():
    b, sc = _lair()
    k = _patrol_member(b)
    verdict = sc.contact(b, k, [b.player_units[0]])
    assert verdict in ("fight", "pass")
    assert (0 in sc.parleyed) == (verdict == "pass")


# --- leaving ------------------------------------------------------------------------- #

def test_the_squad_may_leave_once_everyone_standing_is_at_the_mouth_with_an_egg():
    b, _ = _lair()
    assert not b.can_withdraw
    b.player_units[0].inventory.append(lair.EGG)
    assert b.can_withdraw
    b.player_units[1].pos = (12, 10)
    assert not b.can_withdraw
    b.player_units[1].status = "dead"
    assert b.can_withdraw
    b.withdraw()
    assert b.winner == "player" and lair.eggs_taken(b) == 1


def test_with_the_dragon_dead_the_eggs_left_on_the_ground_are_loot():
    b, sc = _lair()
    dragon = lair.dragon_of(b)
    assert sc.relics_left(b) == []
    dragon.hp, dragon.status = 0, "dead"
    assert b.can_withdraw and sc.relics_left(b) == [lair.EGG] * len(lair.EGG_CELLS)
    assert loot.field_loot(b, []).count(lair.EGG) == len(lair.EGG_CELLS)


def test_a_lost_fight_takes_no_eggs():
    b, _ = _lair()
    b.player_units[0].inventory.append(lair.EGG)
    b.winner = "enemy"
    assert lair.eggs_taken(b) == 0


def test_the_squads_ai_goes_for_an_egg_then_the_way_out():
    b, sc = _lair()
    me = b.player_units[0]
    goal, reach = sc.heist_goal(b, me)
    assert goal in lair.EGG_CELLS and reach == 1
    me.inventory.append(lair.EGG)
    other = b.player_units[1]
    other.pos = (20, 10)
    goal, reach = sc.heist_goal(b, other)
    assert goal in lair._cells(*lair.MOUTH) and reach == 0
    assert sc.heist_goal(b, me) is None            # already at the mouth: it waits


def test_an_ai_thief_walks_in_lifts_an_egg_and_leaves_with_it(monkeypatch):
    monkeypatch.setattr(lair, "STIR_AT", 10**6)       # a sleep no noise breaks: no fight, no dice
    monkeypatch.setattr(lair, "WAKE_AT", 10**6)
    b, sc = _lair(size=1)
    dragon = lair.dragon_of(b)
    for k in b.foe_units:
        if k is not dragon:
            k.hp, k.status = 0, "dead"
    n = 0
    while b.winner is None and n < 300:
        ai.take_turn(b, b.active)
        n += 1
    assert b.winner == "player" and lair.eggs_taken(b) == 1
    assert sc.stage == "asleep" and dragon.alive


# --- the dragon and Dragonfire ------------------------------------------------------ #

def test_the_dragon_is_an_authored_level_twenty_huge_red_dragon():
    d = npc_lib.load_npc(lair.DRAGON_SLUG)
    assert d.race["name"] == "Dragon" and d.race["size"] == "Huge" and d.racial_level == 20
    assert d._racial_override is None and "Draconic" in d.languages
    assert {"dragon", "dragon_breath"} <= set(d.talents["racial"]) and "dragonfire" in d.spells_known
    assert d.natural_armor == 5
    assert "Dragon" not in [r["name"] for r in data.BEAST_POOL]


def _caster_duel(caster_team="player"):
    random.seed(4)
    caster, target = Unit(caster_team), Unit("enemy" if caster_team == "player" else "player")
    caster.add_magic_source("blood")
    caster.set_spell_known("dragonfire", True)
    caster.equipped_weapon = None
    sides = ([caster], [target]) if caster_team == "player" else ([target], [caster])
    b = Battle(*sides, scenario=ErmosScenario())
    b.board.walls = set()
    me = next(u for u in b.units if u.char is caster)
    foe = next(u for u in b.units if u.char is target)
    me.pos, foe.pos = (5, 5), (8, 5)
    me.hp, me.ap = 30, 2
    return b, me, foe


def test_dragonfire_burns_and_costs_no_blood():
    b, me, foe = _caster_duel()
    spell = actions.CastSpellAction("dragonfire")
    assert spell.can(b, me, foe)
    random.seed(1)
    spell.execute(b, me, foe)
    assert me.hp == 30 and any("Dragonfire" in ln for ln in b.log_lines)
    me.ap, me.hp = 2, 1
    assert spell.can(b, me, foe)              # no blood price: even at 1 HP
    foe.pos = (5 + actions.DragonfireAction.reach() + 1, 5)
    assert not spell.can(b, me, foe)


def test_the_ai_casts_dragonfire_whatever_its_health():
    b, me, foe = _caster_duel("enemy")
    me.hp = me.hp_max = 30
    assert ai._pick_attack(b, me, foe).id == "cast_dragonfire"
    me.hp = 3
    assert ai._pick_attack(b, me, foe).id == "cast_dragonfire"


# --- the job and the eggs ------------------------------------------------------------ #

def test_the_clutch_is_offered_once_the_codex_is_recovered_and_pays_a_scroll():
    guild, g = _guild(node="blood_sanctuary")
    assert missions.BLOOD_CLUTCH not in missions.offers_at(guild, "blood_sanctuary")
    m = _take_clutch(guild, g)
    assert missions.pending_clutch(guild) is m
    g.members[1].give_to_pack(lair.EGG, 2)
    assert missions.can_turn_in(guild, m)
    earned = missions.turn_in(guild, m)
    assert m.state == "done" and g.members[0].count_of("Scroll of Dragonfire") == 1
    assert g.members[1].count_of(lair.EGG) == 1
    assert "blood_clutch" in {d.id for d in earned} and factions.DEEDS["blood_clutch"].faction == "blood_cult"


def test_the_keepers_pay_more_for_an_egg_than_the_market():
    from gartok.shrine_screen import ShrineMissionScreen
    guild, g = _guild(node="nature_grove")
    g.members[0].give_to_pack(lair.EGG)
    scr = ShrineMissionScreen(None, guild, g, on_done=lambda: None)
    label, enabled = scr.footer_action()
    assert enabled and str(lair.SHRINE_EGG_PRICE) in label
    before = g.members[0].money
    scr.run_footer_action()
    assert g.members[0].money - before == lair.SHRINE_EGG_PRICE and not g.members[0].count_of(lair.EGG)
    assert scr.footer_action() is None
    assert economy.sell_price(lair.EGG) < lair.SHRINE_EGG_PRICE


def test_the_cult_will_not_buy_the_egg_it_asked_for():
    from gartok.shrine_screen import ShrineMissionScreen
    guild, g = _guild(node="blood_sanctuary")
    _take_clutch(guild, g)
    g.members[0].give_to_pack(lair.EGG)
    scr = ShrineMissionScreen(None, guild, g, on_done=lambda: None)
    assert scr.footer_action()[1] is False


def test_the_shrine_board_draws_with_the_egg_sale():
    from gartok.shrine_screen import ShrineMissionScreen
    guild, g = _guild(node="faith_cathedral")
    g.members[0].give_to_pack(lair.EGG)
    scr = ShrineMissionScreen(None, guild, g, on_done=lambda: None)
    pygame.font.init()
    scr.draw(pygame.Surface((1280, 720)))
    assert any(k == "footer_action" for k, _ in scr.buttons)


def test_entering_the_lair_from_the_map_starts_the_heist():
    guild, g = _guild(node=lair.NODE)
    app = make_app(guild)
    app._enter_lair(g, world.node(lair.NODE))
    battle = app.scene.battle
    assert isinstance(battle.scenario, lair.LairScenario) and battle.talk_handler is not None


def test_the_egg_is_worth_a_lot_and_weighs_on_its_carrier():
    egg = items.get(lair.EGG)
    assert egg.price >= 400 and egg.weight >= 8


@pytest.mark.parametrize("fight", ["lair"])
def test_the_lab_builds_the_lair(fight):
    assert fight in combat_lab.FIGHTS
    b, meta = combat_lab.build(fight, 3, 4, seed=1)
    assert isinstance(b.scenario, lair.LairScenario) and meta["fight"] == fight


def test_the_battle_screen_hosts_a_challenge_over_the_board_and_waits_on_it(monkeypatch):
    from gartok.battle_screen import BattleScreen
    from gartok.ui.tokens import fonts
    pygame.font.init()
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    b, sc = _lair()
    scr = BattleScreen(fonts(), b, on_battle_end=lambda battle: None,
                       controllers={"player": "human", "enemy": "ai"})
    got = []
    enc = dialogue.Challenge(sc.patrol(b, 0))
    b.talk_handler(enc, [c.char for c in b.player_units], got.append)
    active = b.active
    scr.update(10_000)
    assert scr._talk is not None and b.active is active
    scr.draw(pygame.Surface((1280, 720)))
    assert scr._talk.hits["options"]
    scr._talk.choose("attack")
    scr._talk.go_on()
    assert scr._talk is None and got[0].kind == "fight"


def test_only_the_first_kobold_of_each_patrol_holds_a_torch_however_it_is_outfitted():
    random.seed(0)
    patrols = lair.build_patrols(6)
    torches = [u for u in patrols if u.equipped_offhand == data.TORCH_ITEM]
    assert len(torches) == len(lair.PATROLS)
    assert {u.patrol_id for u in torches} == set(range(len(lair.PATROLS)))
