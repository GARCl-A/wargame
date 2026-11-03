"""One clock for the whole guild: hours a band spends on a screen (a show, a Medic's visit, a craft the band
waits out, the claim's work, a repair) are an order, so every other band's order runs with them, and the
map takes over the moment another band needs the person (playtest 2026-10-31: a band at the lumber yard
froze while its split-off musicians played)."""

from gartok import campaign, economy, medic, orders, persist, stints
from gartok.group import Group
from gartok.wagon import Wagon
from gartok.web.guild_session import GuildSession
from tests.helpers import fixed_d20, packed, standard_unit
from tests.test_web_hub import _bench, _claim, _hub, _ward


def _mill(guild, left):
    """A second band on a wage shift at the lumber yard with `left` hours to go."""
    u = standard_unit()
    u.give_to_pack("Potato", 6)
    band = Group([u], node="lumber_yard", leader=u)
    guild.groups.append(band)
    band.order = orders.work(guild, band, 16)
    band.order.remaining = left
    u.money = 0
    return band


def _stage(hours):
    hub, guild, g = _hub("tavern", "recruit")
    bard = g.members[0]
    bard._base_inventory = packed(["Musical Instrument"])
    bard.money = 0
    hub.tavern.s.perform_hours = hours
    return hub, guild, g, bard


def test_a_show_that_outlasts_the_other_bands_shift_hands_the_map_over_at_the_shifts_end():
    hub, guild, g, bard = _stage(4)
    mill = _mill(guild, 2)
    t0 = guild.clock.seconds
    st = hub.perform()
    assert hub.game.session is hub.map and st["turn"]["name"] == mill.display_name
    assert guild.clock.seconds - t0 == 2 * 3600
    assert not mill.busy and mill.members[0].money > 0
    assert g.order.task == "perform" and g.order.remaining == 2 and bard.money == 0
    chip = next(b for b in st["groups"] if b["gid"] == g.gid)["chip"]
    assert chip == "performing"
    mill.order = orders.rest(8)
    with fixed_d20(20):
        hub.map._advance()
    assert not g.busy and bard.money > 0 and guild.clock.seconds - t0 == 4 * 3600


def test_a_show_the_other_band_outlasts_stays_on_the_stage_with_the_tips_and_runs_the_shift():
    hub, guild, g, bard = _stage(2)
    mill = _mill(guild, 6)
    with fixed_d20(20):
        st = hub.perform()
    assert hub.game.session is hub and st["tab"] == "perform"
    assert any("Tavern stage" in line for line in st["tavern"]["report"]) and bard.money > 0
    assert mill.busy and mill.order.remaining == 4


def test_a_show_on_the_stage_runs_the_other_bands_wage_shift_to_its_end_and_pays_it():
    hub, guild, g, bard = _stage(4)
    mill = _mill(guild, 4)
    hub.perform()
    assert not mill.busy and mill.members[0].money > 0 and not g.busy


def test_a_show_with_another_band_idle_goes_to_the_map_and_waits_for_that_band():
    hub, guild, g, bard = _stage(2)
    idle = _mill(guild, 1)
    idle.order = None
    t0 = guild.clock.seconds
    st = hub.perform()
    assert st["screen"] == "map" and guild.clock.seconds == t0 and g.order.task == "perform"


def test_a_medic_visit_the_other_band_cuts_short_is_paid_now_and_cures_when_its_hours_are_up():
    hub, guild, g = _ward()
    hurt = g.members[0]
    hours = medic.quote(hurt).hours
    mill = _mill(guild, hours / 2)
    hub.patient(hurt.uid)
    money = sum(u.money for u in g.members)
    st = hub.treat()
    assert st["screen"] == "map" and sum(u.money for u in g.members) < money
    assert any("The Medic treats" in n for n in st["notices"])
    assert hurt.hp < hurt.hp_max and g.order.task == "treat" and not mill.busy
    mill.order = orders.rest(8)
    hub.map._advance()
    assert hurt.hp == hurt.hp_max and not g.busy


def test_a_craft_the_band_waits_out_is_a_solo_order_the_other_band_can_interrupt():
    hub, guild, g = _bench()
    mill = _mill(guild, 2)
    st = hub.craft("Club", 8, False)
    assert st["screen"] == "map" and g.order.kind == "solo" and g.order.remaining == 6 and not mill.busy


def test_the_claims_scouting_is_a_stint_the_other_band_can_interrupt():
    hub, guild, g = _claim()
    mill = _mill(guild, 1)
    st = hub.claim_work("scout")
    assert st["screen"] == "map" and guild.wilds_claim_stage == "NONE" and g.order.task == "claim_scout"
    mill.order = orders.rest(24)
    hub.map._advance()
    assert guild.wilds_claim_stage == "SCOUTED" and not g.busy


def test_the_claims_oven_takes_its_bricks_as_the_work_starts_and_stands_when_it_is_done():
    hub, guild, g = _claim("SWEPT")
    builder = g.members[0]
    builder.give_to_pack(economy.CLAIM_OVEN_BRICK, economy.CLAIM_OVEN_BRICKS)
    order = hub.claim.s._build_oven()
    assert order.task == "claim_oven" and not builder.count_of(economy.CLAIM_OVEN_BRICK) and not guild.claim_oven
    g.order = order
    campaign.advance(guild)
    assert guild.claim_oven


def test_a_repair_from_the_band_sheet_is_a_stint_the_other_band_can_interrupt():
    hub, guild, g = _hub("city", "market")
    wagon = Wagon("Cart")
    wagon.hp = 1
    g.wagons.append(wagon)
    g.members[0].give_to_pack("Lumber", wagon.repair_cost)
    m = hub.map
    m.game.open(m)
    mill = _mill(guild, 0.5)
    sheet = GuildSession(m, "bands", g.gid)
    m.game.open(sheet)
    st = sheet.button(f"repair:{wagon.uid}")
    assert st["screen"] == "map" and g.order.task == "repair" and not mill.busy
    mill.order = orders.rest(8)
    with fixed_d20(20):
        m._advance()
    assert wagon.hp > 1 and not g.busy


def test_a_stint_in_flight_survives_a_save():
    o = stints.order("repair", 1, [standard_unit()], wagon="w1")
    back = persist.order_from_dict(persist.order_to_dict(o))
    assert back == o and isinstance(back.crew, tuple)


def test_a_headless_shift_runs_every_other_bands_order_too():
    hub, guild, g = _hub("lumber_yard", "recruit")
    mill = _mill(guild, 5)
    guild.work_shift(g.members, 3)
    assert 1.9 < mill.order.remaining < 2.1


def _hunters(monkeypatch, ambush):
    from gartok import hunt
    from tests.test_web_hub import _guild
    from gartok.web.map_session import MapSession
    from gartok.web.server import Game
    monkeypatch.setattr(hunt, "AMBUSH_CHANCE_PER_HOUR", ambush)
    guild = _guild("wilds")
    game = Game(MapSession(guild))
    g = guild.groups[0]
    assert game.session.act(g.gid, "hunt") == {"screen": "hunt"}
    return game, guild, g


def test_a_long_hunt_hands_the_map_to_the_lumber_yard_when_its_shift_ends_and_comes_back_when_it_is_up(monkeypatch):
    game, guild, g = _hunters(monkeypatch, 0)
    mill = _mill(guild, 6)
    hunt_screen, t0 = game.session, guild.clock.seconds
    hunt_screen.set_hours(16)
    st = hunt_screen.start()
    assert game.session is hunt_screen.map and st["screen"] == "map"
    assert st["turn"]["name"] == mill.display_name and guild.clock.seconds - t0 == 6 * 3600
    assert not mill.busy and mill.members[0].money > 0
    assert g.order.kind == "hunting" and g.order.remaining == 10
    assert next(b for b in st["groups"] if b["gid"] == g.gid)["chip"] == "hunting"
    m = game.session
    mill.order = orders.work(guild, mill, 16)
    st = m._after_order()
    assert st["turn"]["name"] == g.display_name and st["turn"]["action"] == "HUNTING"
    assert guild.clock.seconds - t0 == 16 * 3600 and mill.order.remaining == 6
    assert m.go_on() == {"screen": "hunt", **hunt_screen.state()} and hunt_screen.phase == "done"
    assert hunt_screen.done()["screen"] == "map" and not m.hunts


def test_an_ambush_springs_on_the_hunt_screen_at_its_hour_with_the_other_band_still_at_work(monkeypatch):
    game, guild, g = _hunters(monkeypatch, 1)
    mill = _mill(guild, 6)
    hunt_screen, t0 = game.session, guild.clock.seconds
    st = hunt_screen.start()
    assert game.session is hunt_screen and st["screen"] == "hunt" and hunt_screen.phase == "ambush"
    assert guild.clock.seconds - t0 == 3600 and mill.order.remaining == 5 and not g.busy


def _hunt_saved(monkeypatch, ambush, mill_left):
    """A hunt sent out on a 16 h shift while a mill band has `mill_left` hours to go: the map takes over
    mid-stretch and autosaves; -> the game rebuilt from that save, its guild, the hunt and the mill."""
    from tests.test_web_hub import _guild
    from gartok import hunt
    from gartok.web.map_session import MapSession
    from gartok.web.server import Game
    monkeypatch.setattr(hunt, "AMBUSH_CHANCE_PER_HOUR", ambush)
    guild = _guild("wilds")
    game = Game(MapSession(guild, "w1"))
    g = guild.groups[0]
    game.session.act(g.gid, "hunt")
    _mill(guild, mill_left)
    hunt_screen = game.session
    hunt_screen.set_hours(16)
    assert hunt_screen.start()["screen"] == "map" and g.order.kind == "hunting"
    loaded = persist.load_game("w1")
    game = Game(MapSession(loaded, "w1"))
    return game, loaded, guild, hunt_screen


def test_a_save_mid_stretch_loads_with_the_hunt_still_out_on_the_clock(monkeypatch):
    game, loaded, guild, before = _hunt_saved(monkeypatch, 0, 6)
    g, mill = loaded.groups
    assert loaded.clock.seconds == guild.clock.seconds
    assert g.order.kind == "hunting" and g.order.remaining == 10 and g.busy
    restored = game.session.hunts[g.gid]
    s, was = restored.state_, before.state_
    assert [u.uid for u in s.party] == [u.uid for u in was.party] and all(u in g.members for u in s.party)
    assert (s.hours_hunted, s.hours_left, s.yield_hours, s.target) == (16, 0, was.yield_hours, "meat")
    assert restored.phase == "out" and restored.found is None
    mill.order = orders.work(loaded, mill, 16)
    m = game.session
    assert m._after_order()["screen"] == "hunt" and game.session is restored and restored.phase == "done"
    assert loaded.clock.seconds - guild.clock.seconds == 10 * 3600
    assert sum(u.count_of("Meat") for u in g.members) == s.meat > 0
    assert restored.done()["screen"] == "map" and not m.hunts and not g.busy


def test_an_ambush_rolled_before_the_save_still_springs_after_the_load(monkeypatch):
    game, loaded, guild, before = _hunt_saved(monkeypatch, 1, 0.5)
    g, mill = loaded.groups
    restored = game.session.hunts[g.gid]
    assert g.order.remaining == 0.5 and g.order.state["found"] == "wilds" and restored.found == "wilds"
    assert restored.state_.hours_hunted == 1 and restored.state_.hours_left == 15
    mill.order = orders.work(loaded, mill, 16)
    st = game.session._after_order()
    assert st["screen"] == "hunt" and restored.phase == "ambush" and restored.pack
    assert restored.state_.fights == 1 and st["ambush"]["title"] == "Ambush in the Wilds!"


def test_the_pack_rolled_with_the_stretch_is_the_one_that_springs_after_the_load(monkeypatch):
    from gartok import hunt
    game, loaded, guild, before = _hunt_saved(monkeypatch, 1, 0.5)
    g, mill = loaded.groups
    rolled = [u.uid for u in before.rolled]
    assert rolled and [u.uid for u in g.order.pack] == rolled

    def roll_again(**kw):
        raise AssertionError("the pack is rolled with the stretch, not again on arrival")

    monkeypatch.setattr(hunt, "wilds_pack", roll_again)
    restored = game.session.hunts[g.gid]
    mill.order = orders.work(loaded, mill, 16)
    game.session._after_order()
    assert [u.uid for u in restored.pack] == rolled


def test_the_biwolf_and_the_ox_a_stretch_rolled_are_who_springs_after_the_load(monkeypatch):
    from gartok import hunt, ox, world
    from gartok.web.hunt_session import HuntSession
    from tests.test_web_hub import _guild
    from gartok.web.map_session import MapSession
    guild = _guild("wilds")
    g = guild.groups[0]
    m = MapSession(guild)
    s = hunt.begin(guild, g.members, world.node("wilds"), g.stance)
    monkeypatch.setattr(hunt, "biwolf_pack", lambda guild: ["biwolf"])
    monkeypatch.setattr(ox, "aurochs_pack", lambda: ["ox"])
    for found, pack in (("biwolf", ["biwolf"]), ("ox", ["ox"])):
        g.order = orders.Order("hunting", eta=2, remaining=2, state={"hunt": hunt.to_dict(s), "found": found,
                                                                        "guarded": True})
        back = persist.group_from_dict(persist.group_to_dict(g))
        assert HuntSession.restore(m, back)._pack(back.order.state["found"]) == pack


def test_a_hunt_on_its_screen_is_not_in_the_save_the_band_loads_back_idle():
    from tests.test_web_hub import _guild
    from gartok.web.map_session import MapSession
    from gartok.web.server import Game
    guild = _guild("wilds")
    game = Game(MapSession(guild, "w1"))
    g = guild.groups[0]
    game.session.act(g.gid, "hunt")
    assert game.session.phase == "setup"
    game.session.map._save()
    loaded = persist.load_game("w1")
    assert loaded.groups[0].order is None and loaded.groups[0].node == "wilds"
    assert not MapSession(loaded, "w1").hunts


def test_a_hunting_order_saved_without_its_hunt_is_dropped_on_load():
    from tests.test_web_hub import _guild
    from gartok.web.map_session import MapSession
    guild = _guild("wilds")
    g = guild.groups[0]
    g.order = orders.Order("hunting", eta=4, remaining=4, crew=(g.members[0].uid,))
    back = persist.group_from_dict(persist.group_to_dict(g))
    guild.groups = [back]
    assert not MapSession(guild).hunts and back.order is None


def test_only_the_tick_engine_moves_the_clock():
    """`Guild.pass_time` jumps the clock without the bands' orders: only `campaign._advance` may call it.
    The headless shortcuts (`Guild.tick`) are for the sims and the tests: the game itself never calls them,
    its hours are orders."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "gartok"
    shortcuts = re.compile(r"\b(work_shift|perform_shift|crafting_shift|repair_wagon|claim_build_oven|"
                           r"wilds_claim_light_campfire)\(|\bmedic\.treat\(")
    headless = {"guild_labor.py", "guild_claim.py", "guild_holdings.py", "medic.py"}
    for path in root.rglob("*.py"):
        lines = [line for line in path.read_text().splitlines() if not line.lstrip().startswith("def ")]
        text = "\n".join(lines)
        rel = path.relative_to(root).as_posix()
        if rel != "campaign.py":
            assert ".pass_time(" not in text, rel
        if path.name not in headless:
            assert ".tick(" not in text and not shortcuts.search(text), rel


def test_a_stretch_due_behind_the_card_is_not_lost_on_a_save_and_load(monkeypatch):
    from gartok.web.map_session import MapSession
    from gartok.web.server import Game
    game, loaded, guild, before = _hunt_saved(monkeypatch, 0, 6)
    g, mill = loaded.groups
    m = game.session
    mill.order = orders.work(loaded, mill, 16)
    m.seen = mill.gid
    st = m._after_order()
    assert st["turn"]["action"] == "HUNTING" and g.due_hunt is not None and not g.busy
    m._save()
    again = persist.load_game("w1")
    assert again.groups[0].due_hunt is not None
    game = Game(MapSession(again, "w1"))
    st = game.session.land_due()
    assert st["screen"] == "hunt" and game.session.phase == "done"
    assert again.groups[0].due_hunt is None



def test_the_autosave_before_a_hunt_ambush_still_holds_the_stretch(monkeypatch):
    from tests.test_web_hub import _guild
    from gartok import hunt
    from gartok.web.map_session import MapSession
    from gartok.web.server import Game
    monkeypatch.setattr(hunt, "AMBUSH_CHANCE_PER_HOUR", 1.0)
    guild = _guild("wilds")
    game = Game(MapSession(guild, "w1"))
    game.session.act(guild.groups[0].gid, "hunt")
    screen = game.session
    screen.set_hours(16)
    assert screen.start()["screen"] == "hunt" and screen.phase == "ambush"
    screen.fight()
    auto = next(r for r in persist.list_saves("w1") if r["id"].startswith("auto"))
    again = persist.load_game("w1", auto["id"])
    assert again.groups[0].due_hunt is not None
    assert Game(MapSession(again, "w1")).session.land_due()["screen"] == "hunt"
