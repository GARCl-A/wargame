"""The wiki's RULES tab (wiki_rules.py): the numbers are the live ones and the filter finds a rule."""


import re

from gartok import data, dialogue, group, recruit, wiki_rules
from gartok.unit_hunger import HUNGER_PENALTIES


def _rules():
    return {key: lines for key, _, lines in wiki_rules.sections()}


def test_the_rules_quote_the_live_constants():
    body = " ".join(" ".join(lines) for _, _, lines in wiki_rules.sections())
    assert f"against {dialogue.BASE_DC} +" in body
    assert f"-{recruit.SIZE_PENALTY} for every member of the whole guild past {recruit.FREE_SLOTS}" in body


def test_the_hunger_section_quotes_the_live_constants():
    body = " ".join(_rules()["hunger"])
    assert str(HUNGER_PENALTIES[1]) in body
    assert str(HUNGER_PENALTIES[2]) in body
    assert str(data.STARVATION_DEATH_DAYS) in body


def test_the_filter_finds_the_crowd_penalty():
    keys = [k for k, _, _ in wiki_rules.matching("crowd")]
    assert keys == ["recruiting"]
    assert len(wiki_rules.matching("")) == len(wiki_rules.sections())


def test_the_group_size_line_names_every_term_capacity_adds():
    line = next(ln for ln in _rules()["groups"] if "A group holds" in ln)
    assert f"holds {group.BASE_CAPACITY} + " in line
    for phrase, _, _ in group.CAPACITY_TERMS:
        assert phrase in line


def test_the_poison_rule_reads_the_antidote_cooldown_off_the_code():
    from gartok import items, poisons
    line = " ".join(_rules()["poison"])
    assert f"every {poisons.ANTIDOTE_COOLDOWN_HOURS} h" in line
    assert str(poisons.ANTIDOTE_COOLDOWN_HOURS) in " ".join(items.item_tip_lines("Antidote"))


_DICE = re.compile(r"\d*d\d+")
_PLACEHOLDER = re.compile(r"\{[^}]*\}")
_UNTIED = {
    "turns.2": "the diagonal cost cycle is the pathing's shape, not a constant",
    "morale.5": "the Routed threshold is 0 by definition",
    "morale.6": "the Routed threshold is 0 by definition",
    "weapon.title": "the title is also the entry id, so it cannot take a placeholder",
    "wagons.1": "a wagon breaks at 0 HP, zero being the definition",
    "talk.1": "natural 1 and 20 are the die's faces",
    "talk.6": "the bribe's (level + 1) is a formula, its rate is the placeholder",
    "hunger.1": "one meal a day is the rule's shape",
    "study.3": "'first-level' names the spell level",
}


def _wiki_texts():
    from gartok import i18n
    for lang in ("en", "pt-br"):
        catalog = i18n._catalog(lang)
        for key, text in catalog.items():
            if key.startswith("wiki_rules.") and isinstance(text, str):
                yield lang, key.removeprefix("wiki_rules."), text


def test_no_wiki_rule_hardcodes_a_number():
    bare = [(lang, key) for lang, key, text in _wiki_texts()
            if key not in _UNTIED and re.search(r"\d", _DICE.sub("", _PLACEHOLDER.sub("", text)))]
    assert not bare, f"a wiki_rules text holds a digit that should be a placeholder read off the code: {bare}"


def test_the_wiki_numbers_follow_the_constants(monkeypatch):
    from gartok import conditions
    from gartok.actions import weapon_actions
    before = " ".join(_rules()["turns"])
    monkeypatch.setattr(wiki_rules, "DEFEND_AC", conditions.DEFEND_AC + 7)
    after = " ".join(_rules()["turns"])
    assert f"+{conditions.DEFEND_AC} Guard" in before and f"+{conditions.DEFEND_AC + 7} Guard" in after
    monkeypatch.setattr(wiki_rules, "EDGE_TO_HIT", weapon_actions.EDGE_TO_HIT + 5)
    assert f"+{weapon_actions.EDGE_TO_HIT + 5} to hit" in " ".join(_rules()["weapon"])


def test_the_tavern_card_reads_its_numbers_off_the_code():
    from gartok import economy, tutorial
    body = " ".join(tutorial.card("taverna")["body"])
    assert f"past {recruit.FREE_SLOTS}" in body
    assert f"${economy.TAVERN_STUDY_COST_PER_DAY} a day" in body
    assert f"sponsor {recruit.BASE_RECRUIT_CAPACITY} +" in body


_CARD_UNTIED = {
    "hint.fallen.body.0": "a character is down at 0 HP, zero being the definition",
    "battle.body.2": "a character is down at 0 HP, zero being the definition",
    "watch.body.0": "a lone level 0 guard is a level, not a tuned number",
    "wagon_yard.body.2": "a wagon breaks at 0 HP, zero being the definition",
    "combat_lab.body.0": "'Player 1' and 'Player 2' are names, not numbers",
}


def _card_texts():
    from gartok import i18n
    for lang in ("en", "pt-br"):
        for key, text in i18n._catalog(lang).items():
            if key.startswith("tutorial.") and isinstance(text, str) and (".body." in key or key.endswith(".suggestion")):
                yield lang, key.removeprefix("tutorial."), text


def test_no_tutorial_card_hardcodes_a_number():
    bare = [(lang, key) for lang, key, text in _card_texts()
            if key not in _CARD_UNTIED and re.search(r"\d", _DICE.sub("", _PLACEHOLDER.sub("", text)))]
    assert not bare, f"a tutorial card holds a digit that should be a placeholder read off the code: {bare}"


def test_every_card_fills_its_placeholders():
    from gartok import tutorial
    for key in (*tutorial.TUTORIALS, "ox_hunt"):
        card = tutorial.card(key)
        assert not re.search(r"\{[a-z_]+\}", " ".join(card["body"])), key


def test_the_cards_read_their_numbers_off_the_code(monkeypatch):
    from gartok import economy, tutorial, wagon
    monkeypatch.setattr(economy, "OVEN_PRICE", economy.OVEN_PRICE + 7)
    monkeypatch.setattr(wagon, "WEAR_DISTANCE", wagon.WEAR_DISTANCE + 7)
    assert f"(${economy.OVEN_PRICE})" in " ".join(tutorial.card("property")["body"])
    assert f"per {wagon.WEAR_DISTANCE} distance" in " ".join(tutorial.card("wagon_yard")["body"])


def test_the_sponsor_and_herd_lines_name_every_term_their_formula_adds():
    from gartok import i18n
    rules = _rules()
    sponsor = next(ln for ln in rules["recruiting"] if "can sponsor" in ln)
    for label, _ in recruit.SPONSOR_TERMS + recruit.LEADER_SPONSOR_TERMS:
        assert i18n.t(f"wiki_rules.term.{label}") in sponsor
    herd = next(ln for ln in rules["groups"] if "animals" in ln)
    for label, _ in group.HERD_TERMS:
        assert i18n.t(f"wiki_rules.term.{label}") in herd


def test_the_sponsor_capacity_is_the_sum_of_its_terms():
    from tests.helpers import standard_unit
    unit = standard_unit()
    assert recruit.leader_capacity(unit) == max(0, recruit.BASE_RECRUIT_CAPACITY + unit.mod_charisma + unit.racial_level)


def test_the_library_card_and_the_shelf_read_the_same_reputation(monkeypatch):
    from gartok import factions, trade, tutorial
    assert trade.DICTIONARY_MIN_REP == factions.DEEDS["library_initiate"].rep
    monkeypatch.setattr(trade, "DICTIONARY_MIN_REP", trade.DICTIONARY_MIN_REP + 4)
    assert " 5 " in " ".join(tutorial.card("library")["body"])


def test_every_section_sits_in_one_part_and_has_a_title_and_lines():
    keys = [k for _, ks in wiki_rules.PARTS for k in ks]
    assert len(keys) == len(set(keys))
    for key, title, lines in wiki_rules.sections():
        assert title and lines and wiki_rules.part_of(key)


def test_every_hint_opens_a_wiki_entry_that_exists():
    from gartok import hints
    from gartok.web import wiki_session
    for hint in hints.IDS:
        ref = hints.wiki_ref(hint)
        if ref is None:
            continue
        chapter, _, eid = ref.partition(":")
        assert any(e["id"] == eid for e in wiki_session.BUILD[chapter]()), (hint, ref)


def test_the_defence_and_level_words_are_keywords_the_wiki_defines():
    from gartok import keywords, wiki_terms
    for kid, name in (("character_level", "Character Level"), ("evasion", "Evasion"), ("resolve", "Resolve")):
        kw = keywords.get(kid)
        assert kw.name == name and kw.text.startswith(name + ":")
        assert wiki_terms.terms()[kid]["chapter"] == "keywords"


def test_guard_the_stat_is_marked_but_the_city_guard_and_off_guard_are_not():
    from gartok import wiki_terms
    assert [m["word"] for m in wiki_terms.marks("An attack must beat Guard.")] == ["Guard"]
    assert "guard" not in wiki_terms.keywords_in("The City Guard comes. Off-guard foes lose Evasion? No: off-guard, stand guard.")
