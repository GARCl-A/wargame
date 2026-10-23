"""The web front-end's seam: the battle as one side knows it, the turn flow it drives, and the
local server in front of it."""

import json
import os
import threading
import urllib.error
import urllib.request

import pytest

from gartok import actions, artwork, combat_lab, vision
from gartok.web.battle_session import BattleSession
from gartok.web.server import Game, serve


def _session(fight="dungeon", seed=3):
    battle, meta = combat_lab.build(fight, 2, 4, seed=seed)
    return BattleSession(battle, meta)


def _to_my_turn(s, limit=200):
    for _ in range(limit):
        if s.my_turn() or s.battle.winner is not None:
            return
        s.advance()
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
    events = s.advance()
    assert set(events) == {"log", "fx", "acts", "cues"}
    assert not s.battle.fx_events and not s.battle.acts and not s.battle.cues


def test_a_fight_played_through_the_session_ends():
    s = _session("wilds", seed=4)
    for _ in range(600):
        if s.battle.winner is not None:
            break
        if s.my_turn():
            s.act("defend_end")
        else:
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
    srv = serve(Game("wilds", 2, 3, seed=4))
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
    assert _get(server + "/client/battle.js")[0] == 200
    assert _get(server + "/assets/icons/gui/halt.svg")[0] == 200
    status, body = _get(server + "/api/state")
    assert status == 200 and "board" in json.loads(body)


def test_server_keeps_to_its_folders(server):
    for path in ("/assets/../persist.py", "/client/../server.py", "/assets/sounds/x.ogg"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(server + path)
        assert e.value.code == 404


def test_server_refuses_an_illegal_act_and_plays_a_legal_one(server):
    state = json.loads(_get(server + "/api/state")[1])
    for _ in range(200):
        if state["my_turn"]:
            break
        state = _post(server + "/api/advance", {})["state"]
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/act", {"action": "no_such_action"})
    assert e.value.code == 409
    after = _post(server + "/api/act", {"action": "defend_end"})
    assert {"events", "state"} <= set(after)
