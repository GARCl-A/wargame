"""The dialogue before initiative (dialogue.py): the verbs and their checks, the language gate,
bribes, what each answer does to the fight that follows (Battle.open_with), the combat log and
the save carrying it, the forced events that open it, and the squad's AI."""

import random
from types import SimpleNamespace

import pygame
import pytest

from gartok import combat_log, dialogue, forced, justice, orders, persist
from gartok.battle import Battle
from gartok.group import Group
from gartok.guild import Guild
from tests.helpers import Unit, _FixedRNG, make_app


def _speaker(lang="Common", money=0, seed=1):
    random.seed(seed)
    u = Unit("player")
    u.languages = [lang] if lang else []
    u.money = money
    return u


def _pack(n=3, lang="Common", seed=2):
    random.seed(seed)
    pack = [Unit("enemy") for _ in range(n)]
    for u in pack:
        u.languages = [lang] if lang else []
    return pack


def _ambush(n=3, lang="Common"):
    return dialogue.Ambush(_pack(n, lang))


PASS, MISS = 99, -99          # a die no DC can stop / one no modifier can save


# --- who talks, and the gate ------------------------------------------------ #

def test_a_pack_with_nobody_who_speaks_opens_no_dialogue():
    assert not dialogue.can_talk(_pack(lang=None))
    assert dialogue.leader_of(_pack(lang=None)) is None
    beasts = _pack(lang=None)
    g = Group([_speaker()], node="road")
    order = orders.Order("ambush", pack=tuple(beasts))
    assert forced.encounter(Guild(None, groups=[g]), g, order) is None


def test_the_leader_is_the_most_experienced_foe_who_speaks():
    pack = _pack()
    pack[1].languages = []
    pack[2].combat_xp = 500
    pack[2].collect_levels()
    assert dialogue.leader_of(pack) is pack[2]


def test_talking_verbs_need_a_shared_language_coin_and_steel_do_not():
    enc = _ambush(lang="Orcish")
    me = _speaker("Common", money=500)
    opts = {o.verb: o for o in enc.options(me, [me])}
    for verb in ("persuade", "bluff", "intimidate"):
        assert opts[verb].block == "needs Orcish"
    assert opts["bribe"].open and opts["attack"].open
    with pytest.raises(ValueError):
        enc.choose("bluff", me, [me])
    me.languages.append("Orcish")
    assert all(o.open for o in enc.options(me, [me]))


def test_each_check_shows_its_attribute_dc_and_odds():
    enc = _ambush()
    me = _speaker()
    bluff = enc.option("bluff", me, [me])
    assert bluff.check == f"CHA {me.mod_charisma:+d} vs DC {enc.dc('bluff')}"
    assert bluff.odds == dialogue.odds(me.mod_charisma, enc.dc("bluff"))
    assert dialogue.odds(0, 10) == 0.55 and dialogue.odds(0, 30) == 0.0 and dialogue.odds(10, 5) == 1.0


def test_no_criticals_a_natural_twenty_can_still_miss():
    passed, margin, line = dialogue.roll(-5, 30, _FixedRNG(20))
    assert not passed and margin == -15 and "d20(20)" in line
    passed, _, _ = dialogue.roll(10, 5, _FixedRNG(1))
    assert passed


# --- what each answer does --------------------------------------------------- #

def test_persuade_passed_is_peace_missed_is_a_plain_fight():
    me = _speaker()
    win = _ambush().choose("persuade", me, [me], rng=_FixedRNG(PASS))
    assert win.kind == "peace" and win.opening is None
    miss = _ambush().choose("persuade", me, [me], rng=_FixedRNG(MISS))
    assert miss.kind == "fight" and miss.opening == dialogue.Opening()


def test_persuade_is_easier_on_a_good_leader_and_harder_on_an_evil_one():
    enc = _ambush()
    enc.leader.alignment = "Neutral and Good"
    good = enc.dc("persuade")
    enc.leader.alignment = "Neutral and Evil"
    assert enc.dc("persuade") == good + 2 * dialogue.ALIGN_SHIFT


def test_a_failed_bluff_lets_them_strike_first():
    me = _speaker()
    result = _ambush().choose("bluff", me, [me], rng=_FixedRNG(MISS))
    assert result.kind == "fight" and result.opening.surprised == "player"


def test_intimidate_routs_shakes_or_gives_them_the_jump():
    me = _speaker()
    enc = _ambush()
    dc, mod = enc.dc("intimidate"), enc.mod("intimidate", me)
    rout = _ambush().choose("intimidate", me, [me], rng=_FixedRNG(dc - mod + dialogue.ROUT_MARGIN))
    assert rout.kind == "peace"
    shaken = _ambush().choose("intimidate", me, [me], rng=_FixedRNG(dc - mod))
    assert shaken.kind == "fight" and shaken.opening.demoralized == "enemy"
    jumped = _ambush().choose("intimidate", me, [me], rng=_FixedRNG(dc - mod - 1))
    assert jumped.opening.initiative == {"enemy": dialogue.INITIATIVE_EDGE}


def test_intimidate_is_easier_for_a_squad_that_looks_stronger():
    enc = _ambush(n=1)
    base = enc.dc("intimidate")
    strong = [_speaker(seed=s) for s in range(6)]
    enc.set_odds(strong)
    assert 0 < enc.edge <= dialogue.OUTMATCH_CAP and enc.dc("intimidate") == base - enc.edge
    weak = _ambush(n=6)
    weak.set_odds([_speaker()])
    assert weak.edge < 0


def test_every_ambush_check_reads_the_squads_look():
    weak = _ambush(n=6)
    base = {v: weak.dc(v) for v in ("persuade", "bluff", "intimidate")}
    weak.set_odds([_speaker()])
    assert all(weak.dc(v) == base[v] - weak.edge > base[v] for v in base)


def test_an_ordinary_speaker_talks_an_even_pack_down_less_than_half_the_time():
    enc = _ambush(n=1)
    enc.set_odds(enc.foes)
    assert enc.edge == 0
    assert enc.dc("bluff") == dialogue.BASE_DC + enc.leader.mod_wisdom
    assert dialogue.odds(1, dialogue.BASE_DC) <= 0.35


def test_a_bribe_is_priced_by_the_pack_and_paid_richest_first():
    enc = _ambush()
    price = sum(dialogue.BRIBE_PER_FOE * (u.mean_level + 1) for u in enc.foes)
    assert enc.price() == price
    poor, rich = _speaker(money=1), _speaker(money=price + 5, seed=3)
    assert enc.option("bribe", poor, [poor]).block == "not enough coin"
    result = enc.choose("bribe", poor, [poor, rich])
    assert result.kind == "peace" and result.paid == price
    assert poor.money + rich.money == 1 + 5


def test_attack_is_a_plain_fight():
    me = _speaker()
    assert _ambush().choose("attack", me, [me]).opening == dialogue.Opening()


# --- the guard ---------------------------------------------------------------- #

def test_the_patrol_offers_surrender_bluff_bribe_attack_and_run_only_with_somewhere_to_run():
    caught = _speaker()
    caught.crime = 3
    enc = dialogue.Patrol(_pack(), [caught], can_run=True)
    assert [o.verb for o in enc.options(caught, [caught])] == ["surrender", "bluff", "bribe", "attack", "leave"]
    assert enc.price() == 3 * dialogue.GUARD_BRIBE_PER_CRIME
    assert dialogue.Patrol(_pack(), [caught], can_run=False).offered()[-1] == "attack"
    assert enc.choose("surrender", caught, [caught]).kind == "surrender"
    assert enc.choose("leave", caught, [caught]).kind == "leave"
    assert enc.choose("bluff", caught, [caught], rng=_FixedRNG(MISS)).opening.surprised == "player"


def test_a_patrol_nobody_in_talks_still_offers_coin_steel_and_the_cells():
    caught = _speaker(money=100)
    caught.crime = 1
    enc = dialogue.Patrol(_pack(lang=None), [caught], can_run=False)
    opts = {o.verb: o for o in enc.options(caught, [caught])}
    assert opts["bluff"].block == "nobody there talks"
    assert opts["surrender"].open and opts["bribe"].open


def test_a_bribed_patrol_lets_the_group_go_with_the_crime_on_the_books():
    culprit = _speaker(money=200)
    culprit.crime = 2
    g = Group([culprit], node="city")
    guild = Guild(None, groups=[g])
    order = orders.Order("guard", caught=(culprit.uid,), prev_node="road")
    g.pending = order
    enc = forced.encounter(guild, g, order)
    assert len(order.pack) == justice.PATROL_SIZE
    result = enc.choose("bribe", culprit, [culprit])
    forced.settle_talk(guild, g, order)
    assert result.kind == "peace" and culprit.crime == 2 and g.pending is None and g.order.kind == "idle"


# --- forced events settle a talk without a fight ------------------------------ #

def test_a_peaceful_gather_ambush_banks_the_haul_like_a_won_fight(monkeypatch):
    g = Group([_speaker()], node="lumber_yard")
    guild = Guild(None, groups=[g])
    banked = []
    monkeypatch.setattr(guild, "bank_haul", lambda survivors, hours, node: banked.append(survivors) or ["haul"])
    order = orders.Order("gather_ambush", pack=tuple(_pack()), hours=8)
    g.pending = order
    assert forced.settle_talk(guild, g, order) == ["The crew drives the pack off.", "haul"]
    assert banked == [list(g.members)] and g.pending is None


def test_the_ambushes_and_the_guard_open_a_talk():
    assert {k for k, e in forced.EVENTS.items() if e.play == "talk"} == {"guard", "gather_ambush", "supply_ambush"}
    assert forced.EVENTS["ambush"].play == "map"


# --- the fight that follows ---------------------------------------------------- #

def _duel():
    random.seed(5)
    return Battle([Unit("player")], [Unit("enemy")])


def test_a_surprised_side_loses_its_first_turn():
    b = _duel()
    b.open_with(surprised="player")
    me = b.player_units[0]
    assert b.active.team == "enemy"
    while b.active is not me:
        b.end_turn()
    assert b.round_no == 2 and not me.has_condition("surprised")
    assert any("caught off guard" in ln for ln in b.log_lines)


def test_a_shaken_side_starts_demoralized_and_a_head_start_reorders_initiative():
    b = _duel()
    foe = b.enemy_units[0]
    b.open_with(demoralized="enemy", initiative={"enemy": 50})
    assert foe.has_condition("demoralized") and b.order[0] is foe and b.active is foe
    assert b.opening == {"surprised": None, "demoralized": "enemy", "initiative": {"enemy": 50}}


def test_the_combat_log_keeps_the_opening_and_a_rebuild_starts_the_same_way(tmp_path):
    b = _duel()
    b.open_with(surprised="enemy")
    path = tmp_path / "fight.jsonl"
    b.record_to(combat_log.CombatLog(str(path)))
    b.end_turn()
    b.sink.end(b)
    rows = combat_log.load(str(path))
    assert rows[0]["opening"]["surprised"] == "enemy"
    again = combat_log.rebuild(rows)
    assert again.active.team == "player" and again.opening["surprised"] == "enemy"


# --- the save, and the app ---------------------------------------------------- #

def test_a_rolled_talk_is_saved_on_the_order_so_a_reload_cannot_roll_again():
    result = dialogue.Result("fight", "seen through", dialogue.Opening(surprised="player"))
    order = orders.Order("ambush", pack=tuple(_pack()), parley=result.to_dict())
    back = persist.order_from_dict(persist.order_to_dict(order))
    again = dialogue.Result.from_dict(back.parley)
    assert again.kind == "fight" and again.opening.surprised == "player"
    assert persist.order_from_dict({**persist.order_to_dict(orders.Order("ambush")), "parley": None}).parley is None


def _ambushed_app(money=0):
    me = _speaker(money=money)
    g = Group([me], node="road")
    guild = Guild(None, groups=[g])
    order = orders.Order("ambush", pack=tuple(_pack()))
    g.pending = order
    app = make_app(guild)
    app._pending_event = (g, order)
    return app, g, order, me


def test_the_road_ambush_cta_opens_the_talk_and_a_bribe_sends_the_group_on():
    app, g, order, me = _ambushed_app(money=500)
    app._resolve_pending_event()
    scr = app.scene
    assert scr.__class__.__name__ == "DialogueScreen" and app._pending_event is None
    scr.choose("bribe")
    assert order.parley["kind"] == "peace"
    scr.go_on()
    assert g.pending is None and g.order.kind == "idle" and me.money < 500


def test_a_reloaded_talk_opens_on_its_result_and_its_fight_keeps_the_opening():
    app, g, order, _ = _ambushed_app()
    order.parley = dialogue.Result("fight", "seen through", dialogue.Opening(surprised="player")).to_dict()
    app._open_dialogue(g, order)
    assert app.scene.result.kind == "fight"
    app.scene.go_on()
    battle = app.scene.battle
    assert app.scene.__class__.__name__ == "BattleScreen" and battle.opening["surprised"] == "player"
    assert battle.active.team == "enemy"


def test_the_dialogue_screen_draws_choosing_and_after_the_roll():
    app, g, order, _ = _ambushed_app(money=500)
    app._open_dialogue(g, order)
    scr = app.scene
    pygame.font.init()
    surf = pygame.Surface((1280, 720))
    scr.draw(surf)
    assert scr.hits["options"] and scr.hits["speakers"] and scr.tutorial_key() == "dialogue"
    _, rect = scr.hits["options"][0]
    scr._click(rect.center)
    assert scr.result is not None
    scr.draw(pygame.Surface((1000, 640)))
    assert scr.hits["button"] is not None


# --- the squad's AI ----------------------------------------------------------- #

def test_the_ai_pays_a_cheap_bribe():
    enc = _ambush()
    me = _speaker(money=enc.price() * 20)
    assert dialogue.ai_choice(enc, [me], fight_odds=0.5)[0] == "bribe"


def test_the_ai_attacks_when_it_cannot_talk_and_cannot_pay():
    enc = _ambush(lang="Orcish")
    me = _speaker("Common")
    assert dialogue.ai_choice(enc, [me], fight_odds=0.9) == ("attack", me)


def test_the_ai_picks_its_best_speaker_for_a_talk():
    enc = _ambush()
    mute, voice = _speaker(None), _speaker("Common", seed=4)
    verb, who = dialogue.ai_choice(enc, [mute, voice], fight_odds=0.2)
    assert who is voice and verb in ("persuade", "bluff", "intimidate")


def test_ai_play_walks_a_wildfire_talk_to_its_end(monkeypatch):
    calls = []

    class _Enc:
        def __init__(self):
            self.step = 0

        def choose(self, verb, speaker, members, rng):
            calls.append(verb)
            self.step += 1
            return SimpleNamespace(over=self.step == 2, kind="peace")

    monkeypatch.setattr(dialogue, "ai_choice", lambda enc, members, odds: ("persuade", members[0]))
    assert dialogue.ai_play(_Enc(), [_speaker()]).kind == "peace" and calls == ["persuade", "persuade"]


def test_the_screen_hands_the_word_to_someone_the_leader_understands():
    from gartok.dialogue_screen import DialogueScreen
    charmer, linguist = _speaker("Elvish", seed=1), _speaker("Common", seed=3)
    charmer.base_attributes["charisma"] = 18
    charmer._apply_attributes()
    g = Group([charmer, linguist], node="road")
    scr = DialogueScreen(None, Guild(None, groups=[g]), g, _ambush(), on_done=lambda r: None)
    assert scr.speaker is linguist
