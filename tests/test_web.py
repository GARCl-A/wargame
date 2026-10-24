"""The web front-end's seam: the battle as one side knows it, the turn flow it drives, and the
local server in front of it."""

import json
import os
import threading
import urllib.error
import urllib.request
from itertools import pairwise

import pytest

from gartok import actions, ai, artwork, combat_lab, lighting, recorder, vision
from gartok.web.battle_session import BattleSession
from gartok.web.server import Game, serve


def _session(fight="dungeon", seed=3):
    battle, meta = combat_lab.build(fight, 2, 4, seed=seed)
    return BattleSession(battle, meta)


def _settle(s):
    """Answer what a person must before the fight goes on: the flag, the traps, a challenge.
    True when there was something to answer."""
    st = s.state()
    if st["setup"]:
        if st["setup"]["kind"] == "flag":
            s.act("plant_flag", cell=st["setup"]["cells"][0])
        else:
            s.act("skip_traps")
        return True
    if st["talk"]:
        s.answer(go_on=True) if st["talk"]["result"] else s.answer(verb="attack")
        return True
    return False


def _to_my_turn(s, limit=200):
    for _ in range(limit):
        if s.my_turn() or s.battle.winner is not None:
            return
        _settle(s) or s.advance()
    raise AssertionError("the AI never handed the turn back")


def test_state_holds_only_what_the_side_knows():
    s = _session()
    _to_my_turn(s)
    st = s.state()
    b = s.battle
    obs = vision.observers(b, False, "player")
    known = {tuple(c) for c in st["visible"]} | {tuple(c) for c in st["seen"]}
    shown = {u["id"] for u in st["units"]}
    hidden = [u for u in b.units if u.alive and u.team != "player"
              and not vision.enemy_visible(b, obs, u) and not actions.ATTACK.can(b, b.active, u)]
    assert hidden, "this seed opens with foes out of sight"
    assert not shown & {s.uid(u) for u in hidden}
    assert all(tuple(w) in known for w in st["board"]["walls"])
    assert sum(1 for c in st["initiative"] if c["id"] is None) == len(hidden)
    assert all("hp" not in u for u in st["units"] if u["side"] == "foe")
    json.dumps(st)


def test_a_foe_shows_its_health_in_steps_and_its_card_only_what_intel_opened():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    b = s.battle
    wolf = next(u for u in b.units if u.team == "enemy" and u.alive)
    ax, ay = b.active.pos
    wolf.pos = next(c for c in ((ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1))
                    if actions._cell_free(b, wolf, c))
    foe = next(u for u in s.state()["units"] if u["id"] == s.uid(wolf))
    assert "hp" not in foe and 0 <= foe["hp_frac"] <= 1
    card = s.state(foe["id"])["inspect"]
    assert card["kind"] == "foe" and card["steps_max"] == 5
    assert all("label" in r for band in card["bands"] for r in band["rows"])


def test_move_walks_the_active_unit_and_a_cell_out_of_reach_is_refused():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    actor = s.battle.active
    reach = s.battle.reachable(actor)
    dest = max((c for c in reach if c != actor.pos), key=lambda c: reach[c])
    s.act("move", cell=dest)
    assert actor.pos == dest
    with pytest.raises(ValueError):
        s.act("move", cell=(-5, -5))


def test_an_action_the_unit_cannot_take_is_refused():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    with pytest.raises(ValueError):
        s.act("attack", target="u999")
    with pytest.raises(ValueError):
        s.act("no_such_action")


def test_advance_never_moves_for_the_player():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    active, ap = s.battle.active, s.battle.active.ap
    s.advance()
    assert s.battle.active is active and active.ap == ap


def test_events_drain_what_the_step_did():
    s = _session("fortress", seed=11)
    steps = s.advance()
    assert steps and all(set(st) == {"moves", "sounds", "log", "fx", "acts", "cues", "state"} for st in steps)
    assert not s.battle.fx_events and not s.battle.acts and not s.battle.cues


def _snapshot(battle):
    return [(u.pos, u.hp, u.ap, u.alive) for u in battle.units] + [battle.round_no, battle.winner]


def test_the_steps_of_ai_turns_add_up_to_the_same_fight_as_plain_take_turn():
    stepped, plain = [], []
    s = _session("fortress", seed=11)
    for _ in range(40):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
        else:
            steps = s.advance()
            assert steps[-1]["state"] == s.state()
        stepped.append(_snapshot(s.battle))
    battle, _ = combat_lab.build("fortress", 2, 4, seed=11)
    for _ in range(len(stepped)):
        if battle.active.team == "player" and not battle.active.ai_ally:
            if actions.DEFEND.can(battle, battle.active):
                actions.DEFEND.execute(battle, battle.active)
            battle.end_turn()
        else:
            ai.take_turn(battle, battle.active)
        plain.append(_snapshot(battle))
    assert stepped == plain


def test_an_ai_turn_comes_as_one_step_per_decision_with_each_walk_cell_by_cell():
    s = _session("fortress", seed=11)
    walks = []
    for _ in range(30):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
            continue
        steps = s.advance()
        walks += [m for st in steps for m in st["moves"]]
    assert walks, "nobody walked in thirty turns"
    for m in walks:
        path = [tuple(c) for c in m["path"]]
        assert len(path) >= 2
        unit = s.unit(m["id"])
        if unit.team == "player":
            assert len(path) == 2 or all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1 for a, b in pairwise(path))


def test_a_foe_walking_out_of_sight_never_shows_where_it_went():
    s = _session("dungeon", seed=3)
    for _ in range(60):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
            continue
        for st in s.advance():
            known = {tuple(c) for c in st["state"]["visible"]} | set(map(tuple, st["state"]["seen"]))
            for m in st["moves"]:
                if s.unit(m["id"]).team != "player":
                    assert all(tuple(c) in known for c in m["path"])


def test_the_player_move_walks_its_path_as_a_step():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    actor = s.battle.active
    reach = s.battle.reachable(actor)
    dest = max((c for c in reach if c != actor.pos), key=lambda c: reach[c])
    expected = s.battle.path_to(actor, dest)
    steps = s.act("move", cell=dest)
    walk = next(m for st in steps for m in st["moves"] if m["id"] == s.uid(actor))
    assert [tuple(c) for c in walk["path"]] == list(expected)


def test_a_fight_played_through_the_session_ends():
    s = _session("wilds", seed=4)
    for _ in range(600):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
        elif not _settle(s):
            s.advance()
    assert s.battle.winner is not None
    assert s.state()["result"] in ("VICTORY", "DEFEAT", "FLED")


def test_the_action_bar_numbers_its_free_actions_one_to_eight():
    s = _session("wilds", seed=4)
    _to_my_turn(s)
    b = s.battle
    entries = actions.panel(b, b.active, "combat", True)
    free = [e["hotkey"] for e in entries if e["action"].id not in actions.FIXED_HOTKEYS and e["hotkey"]]
    assert free == list(range(1, len(free) + 1)) and len(free) <= 8
    fixed = {e["action"].id: e["hotkey"] for e in entries if e["action"].id in actions.FIXED_HOTKEYS}
    assert fixed == {"delay": 9, "end": 0}


def test_portrait_path_names_the_file_portrait_loads():
    path = artwork.portrait_path("Gnoll", 10)
    assert path and os.path.isfile(path)
    assert artwork.portrait_path("No Such Race", 1) is None


@pytest.fixture
def server():
    srv = serve(Game.fight("wilds", 2, 3, seed=4))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_server_serves_the_client_the_art_and_the_state(server):
    assert _get(server + "/")[0] == 200
    assert _get(server + "/client/screens/battle/battle.js")[0] == 200
    assert _get(server + "/assets/icons/gui/halt.svg")[0] == 200
    status, body = _get(server + "/api/battle/state")
    assert status == 200 and "board" in json.loads(body)


def test_server_keeps_to_its_folders(server):
    for path in ("/assets/../persist.py", "/client/../server.py", "/assets/sounds/x.ogg"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(server + path)
        assert e.value.code == 404


def test_server_refuses_an_illegal_act_and_plays_a_legal_one(server):
    state = json.loads(_get(server + "/api/battle/state")[1])
    for _ in range(200):
        if state["my_turn"]:
            break
        if state["setup"]:
            state = _post(server + "/api/battle/act", {"action": "skip_traps"})["steps"][-1]["state"]
            continue
        state = _post(server + "/api/battle/advance", {})["steps"][-1]["state"]
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/battle/act", {"action": "no_such_action"})
    assert e.value.code == 409
    after = _post(server + "/api/battle/act", {"action": "defend_end"})
    assert after["steps"] and "state" in after["steps"][-1]


def test_each_side_has_its_own_colour_and_only_your_squad_shows_its_level():
    s = _session("necromancer", seed=5)
    _to_my_turn(s)
    b, st = s.battle, s.state()
    seats = {u["id"]: u["seat"] for u in st["units"]}
    for u in b.units:
        if s.uid(u) not in seats:
            continue
        want = ("ally" if u.ai_ally else "player" if u.team == "player"
                else "enemy" if u.team == "enemy" else "third")
        assert seats[s.uid(u)] == want
    assert {"player", "ally"} <= set(seats.values())
    assert all(c["seat"] is None for c in st["initiative"] if c["id"] is None)
    assert st["active"]["level"] == b.active.char.racial_level
    foe = next(u for u in b.units if u.team != "player" and u.alive)
    assert s._sheet(foe)["level"] is None


@pytest.mark.parametrize("fight", sorted(combat_lab.FIGHTS))
def test_every_lab_fight_plays_to_its_end_with_a_person_on_every_human_choice(fight):
    battle, meta = combat_lab.build(fight, 2, combat_lab.FIGHTS[fight].squad, seed=1)
    s = BattleSession(battle, meta)
    asked = set()
    for _ in range(3000):
        if battle.winner is not None:
            break
        st = s.state()
        if st["setup"] or st["talk"]:
            asked.add("setup" if st["setup"] else "talk")
            _settle(s)
        elif s.my_turn():
            s._stepped(lambda: ai.take_turn(battle, battle.active), None)    # a stand-in player
        else:
            before = (battle.active, battle.round_no, battle.active.ap)
            s.advance()
            assert (battle.active, battle.round_no, battle.active.ap) != before or battle.winner, "stuck"
    assert battle.winner is not None, f"{fight} never ended"
    if fight in ("ctf", "boss"):
        assert "setup" in asked


def _to_talk(seed=1):
    battle, meta = combat_lab.build("lair", 2, 4, seed=seed)
    s = BattleSession(battle, meta)
    for _ in range(300):
        st = s.state()
        if st["talk"]:
            return s
        if st["setup"]:
            _settle(s)
        elif s.my_turn():
            s._stepped(lambda: ai.take_turn(battle, battle.active), None)
        else:
            s.advance()
    raise AssertionError("no patrol challenged the squad")


def test_a_challenge_waits_for_the_person_and_their_answer_settles_it():
    s = _to_talk()
    turn = (s.battle.active, s.battle.round_no)
    s.advance()
    assert (s.battle.active, s.battle.round_no) == turn and s.talk is not None
    talk = s.state()["talk"]
    assert {o["id"] for o in talk["options"]} == {"bluff", "bribe", "attack"}
    s.answer(speaker=len(talk["speakers"]) - 1)
    assert s.state()["talk"]["speakers"][-1]["selected"]
    s.answer(verb="attack")
    with pytest.raises(ValueError):
        s.answer(verb="bluff")
    s.answer(go_on=True)
    assert s.talk is None and s.state()["talk"] is None
    assert any("strikes before they can call out" in line for line in s.battle.log_lines)


def test_a_person_plants_their_own_flag_where_the_rules_allow():
    battle, meta = combat_lab.build("ctf", 2, 3, seed=1)
    s = BattleSession(battle, meta)
    setup = s.state()["setup"]
    assert setup["kind"] == "flag" and setup["cells"]
    s.advance()
    assert battle.awaiting_flag, "the flag is the person's to plant"
    with pytest.raises(ValueError):
        s.act("plant_flag", cell=(-1, -1))
    s.act("plant_flag", cell=setup["cells"][-1])
    assert battle.flags["player"] == tuple(setup["cells"][-1])


def test_two_people_at_one_screen_pass_it_between_their_turns():
    battle, meta = combat_lab.build("brawl", 2, 3, seed=1)
    s = BattleSession(battle, meta, {"player": "human", "enemy": "human"})
    seen = set()
    for _ in range(60):
        st = s.state()
        if st["handoff"]:
            assert not s.my_turn()
            with pytest.raises(ValueError):
                s.act("defend_end")
            team = st["handoff"]
            s.take_seat()
            assert s.team == team and s.my_turn()
            seen.add(team)
        elif s.my_turn():
            assert battle.active.team == s.team
            s.act("defend_end")
        else:
            s.advance()
    assert seen == {"player", "enemy"}


def test_the_floating_disk_offers_its_heights_and_takes_the_one_picked():
    from tests.test_floating_disk import _setup_battle
    batt, caster, _ = _setup_battle()
    batt.board.elevation = {(1, 0): -2}
    batt.board.refresh_terrain()
    caster.char.spells_known.append("floating_disk")
    s = BattleSession(batt)
    while batt.active is not caster:
        batt.end_turn()
    aim = s.aim("spell:floating_disk")
    assert aim["heights"]["1,0"] == [[0, "z=0 (Ground/Caster)"], [-2, "z=-2 (Pit floor)"]]
    s.act("spell:floating_disk", cell=(1, 0), elevation=-2)
    assert [o.elevation for o in batt.ground if getattr(o, "is_disk", False)] == [-2]


def test_a_step_says_what_it_sounded_like():
    s = _session("wilds", seed=4)
    heard = set()
    for _ in range(200):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            steps = s.act("defend_end")
        elif _settle(s):
            continue
        else:
            steps = s.advance()
        heard |= {snd for st in steps for snd in st["sounds"]}
    assert heard & {"hit", "crit"} and heard <= {"hit", "crit", "miss", "fall"}


def test_a_game_with_a_log_root_writes_the_fight_as_the_lab_does(tmp_path):
    game = Game.fight("wilds", 2, 3, seed=4, log_root=str(tmp_path))
    s = game.session
    for _ in range(600):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
        elif not _settle(s):
            s.advance()
    files = list(tmp_path.rglob("*.jsonl"))
    assert len(files) == 1 and "wilds-human-vs-ai" in files[0].name
    rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["e"] == "end" and any(r.get("by") == "human" for r in rows)


def test_the_router_names_the_open_screen_and_refuses_another_screens_verbs(server):
    info = json.loads(_get(server + "/api/screen")[1])
    assert info["screen"] == "battle" and info["lab"] is True
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/api/map/state")
    assert e.value.code == 409
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/api/battle/no_such_verb")
    assert e.value.code == 404
    assert any(f["id"] == "wilds" for f in json.loads(_get(server + "/api/lab/fights")[1]))


def test_every_file_the_shell_routes_to_is_served(server):
    import re
    shell = _get(server + "/client/shell.js")[1].decode()
    manifest = re.findall(r'(\w+): \{css: \[(.*?)\], js: \[(.*?)\]\}', shell)
    assert {screen for screen, _, _ in manifest} == {"battle", "map", "away"}
    for screen, css, js in manifest:
        for name in ["screen.html", *re.findall(r'"([^"]+)"', css + js)]:
            assert _get(f"{server}/client/screens/{screen}/{name}")[0] == 200
    for path in ("/client/shell.css", "/client/fonts/fonts.css"):
        assert _get(server + path)[0] == 200


def test_a_save_opens_the_map_through_the_same_router(tmp_path, monkeypatch):
    from gartok import persist
    from gartok.group import Group
    from gartok.guild import Guild
    from gartok.unit import Unit
    monkeypatch.setattr(persist, "SAVE_DIR", str(tmp_path))
    units = [Unit("Fighter") for _ in range(2)]
    guild = Guild(None, groups=[Group(units, node="city", leader=units[1])], name="Ink Hands")
    persist.save_game("w1", guild)
    srv = serve(Game.from_save("w1"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        info = json.loads(_get(url + "/api/screen")[1])
        assert info["screen"] == "map" and info["lab"] is False
        state = json.loads(_get(url + "/api/map/state")[1])
        assert state["meta"]["name"] == "Ink Hands" and state["meta"]["day"] == guild.clock.day
        (band,) = state["groups"]
        assert [m["lead"] for m in band["members"]] == [False, True] and band["idle"]
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(url + "/api/lab/new", {"fight": "wilds"})
        assert e.value.code == 409
    finally:
        srv.shutdown()
        srv.server_close()
        recorder.detach()


def test_the_side_gets_only_the_lights_it_sees_and_the_levels_leave_them_to_the_client():
    s = _session("lair", seed=1)
    _to_my_turn(s)
    st, b = s.state(), s.battle
    visible = {tuple(c) for c in st["visible"]}
    sources = vision.light_sources(b)
    assert any(c not in visible for c, _ in sources), "this seed has a torch out of sight"
    assert sorted((x, y, r) for x, y, r, _ in st["lights"]) == sorted(
        (*c, r) for c, r in sources if c in visible)
    assert st["lights"] and not st["daylight"]
    obs = vision.observers(b, False, "player")
    alone = lighting.cell_levels(b, visible, obs, [src for src in sources if src[0] not in visible])
    assert {(x, y): v for x, y, v in st["light"]} == {c: round(v, 3) for c, v in alone.items()}
    every = lighting.cell_levels(b, visible, obs)
    torch = next(tuple(c[:2]) for c in st["lights"])
    assert every[torch] > alone[torch]


def test_a_fight_by_day_says_so_and_a_burning_cell_is_a_fire():
    s = _session("wilds")
    assert s.state()["daylight"]
    s = _session("fortress")
    _to_my_turn(s)
    st = s.state()
    fire = {tuple(c) for c in st["board"]["fire"]}
    assert fire and all(k == "fire" for x, y, _, k in st["lights"] if (x, y) in fire)
