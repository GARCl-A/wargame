"""Learning a recipe: the same process as a level-0 spell (RULES.md "Learning a recipe"), read from a
`Recipe of <Name>` paper -- and the Apothecary's second job, which pays that paper."""

import pytest

from gartok import data, factions, magic, missions, persist, routine_book, world
from gartok import routines as r
from gartok.band_kit import BandKit
from gartok.group import Group
from gartok.guild import Guild
from gartok.guild_sheet import GuildSheet
from gartok.tavern import Tavern
from gartok.unit import Unit
from gartok.web.jobs_tab import JobsTab
from tests.helpers import standard_unit

PAPER = "Recipe of Antidote"
TARGET = "recipe:Antidote"


def _student(money=500, paper=True):
    u = standard_unit()
    u.money = money
    if paper:
        u.give_to_pack(PAPER)
    return u


def _roll(monkeypatch, value=20):
    monkeypatch.setattr(data, "roll", lambda n, d: value)


def test_the_paper_names_its_recipe_and_level():
    recipe = magic.recipe_for_paper(PAPER)
    assert (recipe.id, recipe.recipe, recipe.level) == (TARGET, "Antidote", 0)
    assert magic.recipe_of(TARGET) == recipe
    assert magic.recipe_for_paper("Scroll of Sleep") is None
    assert magic.recipe_of("recipe:Nothing") is None and magic.recipe_of("Elvish") is None
    assert magic.study_item_name(TARGET) == PAPER


def test_a_recipe_is_studied_to_the_end_and_the_paper_stays(monkeypatch):
    _roll(monkeypatch)
    u = _student()
    magic.begin_study(u, TARGET)
    days = 0
    while "Antidote" not in u.recipes:
        assert magic.progress_study(u) is None or "Antidote" in u.recipes
        days += 1
        assert days < 60
    assert days == -(-magic.points_to_learn(0) // 20)
    assert u.study_target is None and u.study_progress == {}
    assert u.count_of(PAPER) == 1 and u.locked_of(PAPER) == 0
    assert u.magic_xp == 0
    assert "Antidote" in u.known_recipes


def test_mastering_it_tells_the_player(monkeypatch):
    _roll(monkeypatch)
    u = _student()
    magic.begin_study(u, TARGET)
    u.study_progress = {TARGET: magic.points_to_learn(0) - 1}
    assert "Antidote" in magic.progress_study(u)


def test_it_cannot_be_studied_without_the_paper_or_once_known():
    u = _student(paper=False)
    assert not magic.can_study(u, TARGET)
    u.give_to_pack(PAPER)
    assert magic.can_study(u, TARGET)
    u.recipes.append("Antidote")
    assert not magic.can_study(u, TARGET)


def test_a_mate_may_hold_the_paper():
    u, mate = _student(paper=False), _student()
    group = Group([u, mate], "tavern")
    assert not magic.can_study(u, TARGET) and magic.can_study(u, TARGET, group)
    assert magic.begin_study(u, TARGET, group.members) is mate and u.count_of(PAPER) == 1


def test_no_paper_no_progress_but_the_rent_is_due(monkeypatch):
    _roll(monkeypatch)
    u = _student(paper=False)
    u.study_target = TARGET
    magic.progress_study(u)
    assert u.study_progress == {} and u.money == 500 - 15


def test_points_are_kept_when_the_target_changes(monkeypatch):
    _roll(monkeypatch, 10)
    u = _student()
    u.give_to_pack("Dictionary of Elvish")
    magic.begin_study(u, TARGET)
    magic.progress_study(u)
    assert u.study_progress == {TARGET: 10}
    magic.begin_study(u, "Elvish")
    magic.progress_study(u)
    assert u.study_progress == {TARGET: 10, "Elvish": 10}
    magic.begin_study(u, TARGET)
    magic.progress_study(u)
    assert u.study_progress[TARGET] == 20
    assert u.locked_of("Dictionary of Elvish") == 0 and u.locked_of(PAPER) == 1


def test_a_harder_paper_takes_longer():
    assert magic.points_to_learn(1) > magic.points_to_learn(0)


def test_the_learned_recipe_opens_both_antidote_variants():
    from gartok import items
    u = _student()
    assert "Antidote" not in u.known_recipes
    u.recipes.append("Antidote")
    assert len(items.CRAFTING_RECIPES["Antidote"]) == 2 and "Antidote" in u.known_recipes


def test_the_tavern_lists_the_paper_as_something_to_study_and_starts_it():
    u, mate = _student(paper=False), _student()
    group = Group([u, mate], "tavern")
    desk = Tavern(Guild([u, mate]), group)
    option = next(o for o in desk._available_study_options(u) if o["kind"] == "recipe")
    assert option["id"] == TARGET and option["name"] == PAPER and option["holder"] == mate.name
    desk._set_target(u, option)
    assert u.study_target == TARGET and u.count_of(PAPER) == 1


def test_the_tavern_tab_shows_the_target_with_its_progress():
    from gartok.web.tavern_tab import TavernTab
    u = _student()
    guild = Guild([u])
    group = Group([u], "tavern")
    tab = TavernTab(guild, group, world.node("tavern"))
    tab.set_target(u.uid, TARGET)
    u.study_progress[TARGET] = 12
    student = tab._rooms()["students"][0]
    assert student["target"] == {"name": PAPER, "progress": 12, "needed": magic.points_to_learn(0)}
    assert [o["id"] for o in student["options"]] == [TARGET]


def test_the_item_menu_offers_to_study_the_paper_and_to_stop():
    u = _student(money=0)
    guild = Guild([u])
    kit = BandKit(guild, guild.groups[0])
    rows = kit._menu_rows([(u, 0)])
    row = next(x for x in rows if x[0] == "study")
    assert row[1] == f"study {PAPER}"
    kit._menu_run([(u, 0)], "study", row[2])
    assert u.study_target == TARGET
    assert next(x for x in kit._menu_rows([(u, 0)]) if x[0] == "study")[1].endswith(PAPER)
    kit._menu_run([(u, 0)], "study", row[2])
    assert u.study_target is None


def test_the_sheet_names_the_recipe_and_its_points():
    u = _student()
    u.study_target = TARGET
    u.study_progress = {TARGET: 7}
    track = next(t for t in GuildSheet._tracks(u) if t["label"] == "Academic study")
    assert PAPER in track["value"] and str(magic.points_to_learn(0)) in track["value"]


def test_a_routine_may_study_a_recipe_and_the_band_boards_for_it(monkeypatch):
    _roll(monkeypatch)
    u = _student()
    g = Group([u], node="tavern", leader=u)
    guild = Guild(None, groups=[g])
    routine_book.check(guild, (r.Study(TARGET, 2),))
    with pytest.raises(ValueError):
        routine_book.check(guild, (r.Study("recipe:Nothing", 2),))
    r.assign(guild, g, r.Routine([r.Study(TARGET, 2)]))
    assert g.order.job == "study" and u.study_target == TARGET


def test_the_progress_survives_a_save():
    u = _student()
    u.study_target = TARGET
    u.study_progress = {TARGET: 33}
    u.recipes.append("Antidote")
    back = Unit.from_save(persist.unit_to_dict(u))
    assert back.study_target == TARGET and back.study_progress == {TARGET: 33}
    assert "Antidote" in back.recipes


# --------------------------------------------------------------------------- #
# the Apothecary's second job                                                 #
# --------------------------------------------------------------------------- #

def _apothecary(done=True):
    u = standard_unit()
    guild = Guild([u], node="apothecary")
    if done:
        u.give_to_pack("Red Mushroom", 15)
        missions.turn_in(guild, missions.accept(guild, u, missions.APOTHECARY_MUSHROOMS))
    return guild, u


def test_the_second_job_waits_for_the_first():
    guild, _ = _apothecary(done=False)
    assert missions.APOTHECARY_VENOM.id not in {t.id for t in missions.offers_at(guild, "apothecary")}
    guild, _ = _apothecary()
    assert missions.APOTHECARY_VENOM.id in {t.id for t in missions.offers_at(guild, "apothecary")}


def test_the_job_pays_no_coin_and_runs_sixty_days():
    t = missions.APOTHECARY_VENOM
    assert t.reward == 0 and t.deadline_days == 60 and t.requires == "apothecary_mushrooms"
    guild, u = _apothecary()
    m = missions.accept(guild, u, t)
    assert missions.days_left(guild, m) == 60


def test_three_glands_of_either_kind_in_any_mix_complete_it():
    guild, u = _apothecary()
    m = missions.accept(guild, u, missions.APOTHECARY_VENOM)
    u.give_to_pack("Venom Gland", 2)
    assert missions.progress(guild, m) == 2 and not missions.can_turn_in(guild, m)
    u.give_to_pack("Snake Venom Gland")
    assert missions.progress(guild, m) == 3 and missions.can_turn_in(guild, m)


def test_a_mate_and_the_stores_count_and_the_turn_in_consumes_the_glands():
    random_mate = standard_unit()
    guild, u = _apothecary()
    guild.groups[0].members.append(random_mate)
    m = missions.accept(guild, u, missions.APOTHECARY_VENOM)
    u.give_to_pack("Venom Gland", 2)
    random_mate.give_to_pack("Snake Venom Gland", 2)
    money = u.money + random_mate.money
    missions.turn_in(guild, m)
    left = u.count_of("Venom Gland") + u.count_of("Snake Venom Gland") + random_mate.count_of("Snake Venom Gland")
    assert left == 1 and m.state == "done"
    assert u.money + random_mate.money == money


def test_turning_it_in_gives_the_paper_an_antidote_and_one_reputation():
    guild, u = _apothecary()
    before = guild.reputation.get("apothecary", 0)
    m = missions.accept(guild, u, missions.APOTHECARY_VENOM)
    u.give_to_pack("Venom Gland", 3)
    earned = missions.turn_in(guild, m)
    assert [d.id for d in earned] == ["apothecary_venom"]
    assert "apothecary_venom" in guild.deeds_done
    assert guild.reputation["apothecary"] == before + 1
    assert u.count_of(PAPER) == 1 and u.count_of("Antidote") == 1
    assert u.count_of("Venom Gland") == 0
    assert "Antidote" not in u.recipes            # the paper is studied, not learnt at once


def test_the_deed_is_registered_with_the_faction():
    assert "apothecary_venom" in [d.id for d in factions.DEEDS_BY_FACTION["apothecary"]]


def test_a_mission_can_hand_over_several_items():
    assert missions.APOTHECARY_VENOM.reward_items == (PAPER, "Antidote")
    assert missions.BLOOD_CLUTCH.reward_items == ("Scroll of Dragonfire",)


def _tab(guild):
    return JobsTab(guild, guild.groups[0], world.node("apothecary"))


def test_the_board_shows_the_second_job_only_after_the_first():
    guild, _ = _apothecary(done=False)
    assert [j["id"] for j in _tab(guild).state()["jobs"]] == ["apothecary_mushrooms"]
    guild, _ = _apothecary()
    assert [j["id"] for j in _tab(guild).state()["jobs"]] == ["apothecary_venom"]


def test_the_second_job_reads_without_a_money_line_and_its_notice_names_the_prize():
    guild, u = _apothecary()
    tab = _tab(guild)
    job = tab.state()["jobs"][0]
    text = " ".join(job["detail"])
    assert "venom glands" in text and "$" not in text and "60 days" in text
    tab.accept(missions.APOTHECARY_VENOM.id)
    u.give_to_pack("Snake Venom Gland", 3)
    job = tab.state()["jobs"][0]
    assert job["ready"] and "3 / 3 venom glands" in " ".join(job["detail"])
    tab.turn_in(missions.APOTHECARY_VENOM.id)
    notice = tab.state()["notice"]
    assert "split" not in notice and PAPER in notice and "Antidote" in notice and "tavern" in notice
    assert "apothecary_venom" in guild.deeds_done


def test_the_carried_line_adds_both_kinds_of_gland():
    guild, u = _apothecary()
    tab = _tab(guild)
    tab.accept(missions.APOTHECARY_VENOM.id)
    u.give_to_pack("Venom Gland")
    u.give_to_pack("Snake Venom Gland", 2)
    carried = tab.state()["carried"][0]
    assert carried["have"] == 3 and carried["goal"] == 3


def test_the_first_job_still_reads_as_before():
    guild, _ = _apothecary(done=False)
    job = _tab(guild).state()["jobs"][0]
    assert job["detail"] == ["15x Red Mushroom", "pay: $150", "deadline: 10 days"]


def test_every_recipe_paper_teaches_a_real_recipe_with_a_composed_name_and_the_shared_icon():
    from gartok import i18n, item_icon, items
    papers = magic.recipe_papers()
    assert papers
    for paper in papers:
        assert paper.recipe in items.CRAFTING_RECIPES
        assert item_icon.icon_spec(paper.paper) == item_icon.icon_spec("Recipe of Antidote")
    i18n.set_language("pt-br")
    try:
        assert i18n.name("item", PAPER) == "Receita de Antídoto"
    finally:
        i18n.set_language("en")
    assert i18n.name("item", PAPER) == PAPER
