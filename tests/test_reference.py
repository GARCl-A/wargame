"""REFERENCE.md stays regenerated from the registries, complete, and readable."""

import re
from pathlib import Path

from gartok import (
    abilities,
    archetypes,
    data,
    factions,
    items,
    progression,
    reference,
    talents,
    vocations,
    weapon_traits,
)

ROOT = Path(__file__).resolve().parent.parent


def _sections(text):
    return {m.group(1): m.group(2) for m in re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)}


def _cells(text):
    return {c.strip() for line in text.splitlines() if line.startswith("|")
            for c in line.strip("|").split("|")}


def test_reference_doc_is_regenerated_from_the_registries():
    assert reference.is_current(), (
        "REFERENCE.md is stale -- run `python -m gartok.reference` and commit it")


def test_an_unknown_argument_never_rewrites_the_file(monkeypatch):
    wrote = []
    monkeypatch.setattr(reference, "write", lambda *a, **k: wrote.append(1))
    assert reference.main(["--help"]) == 2
    assert not wrote


def test_a_number_in_the_prose_follows_its_constant(monkeypatch):
    monkeypatch.setattr(progression, "RACIAL_PICK_EVERY", 7)
    assert "a pick every 7 Character Levels" in reference.build()


def test_every_catalog_entry_is_in_the_document():
    doc = reference.build()
    names = [*data.ALL_RACE_NAMES, *(a.name for a in abilities.ABILITIES.values()),
             *(t.name for t in talents.TALENTS.values()), *(t.name for t in weapon_traits.all_traits()),
             *(d.name for d in factions.DEEDS.values()), *(f.name for f in factions.FACTIONS.values()),
             *(v.name for v in vocations.VOCATIONS.values()),
             *(a.label for a in archetypes.ARCHETYPES.values())]
    missing = sorted(n for n in names if n not in _cells(doc) and n not in doc)
    assert not missing, f"missing from REFERENCE.md: {missing}"


def test_every_item_is_in_the_document_alone_or_in_a_group():
    doc = reference.build()
    missing = [n for n in items.all_items()
               if n not in doc and not (" of " in n and n.partition(" of ")[2] in doc)]
    assert not missing, missing


def test_items_does_not_repeat_the_weapon_armor_and_shield_tables():
    rows = _cells(_sections(reference.build())["Items"])
    own = set(items.weapons()) | set(items.armor()) | set(items.shields())
    assert not own & rows


def test_every_ability_has_a_holder():
    held = reference._holders()
    assert not [aid for aid in abilities.ABILITIES if aid not in held], "an ability no race or creature has"


def test_requires_names_a_talent_or_deed_never_its_id():
    ids = set(talents.TALENTS) | set(factions.DEEDS)
    assert not ids & _cells(reference.build())


def test_every_creature_is_a_non_playable_body():
    section = _sections(reference.build())["Creatures"]
    for name in data.ALL_RACE_NAMES:
        assert (f"| {name} |" in section) == (name not in data.RACE_NAMES), name


def test_docs_point_only_at_sections_that_exist():
    headings = {h.lower() for h in re.findall(r"^#{2,3} (.+)$", reference.build(), re.MULTILINE)}
    docs = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *ROOT.glob(".claude/skills/*/SKILL.md")]
    bad = []
    for path in docs:
        if path.name == "REFERENCE.md":
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"REFERENCE\.md[`\]\)\*]*\s*\(?§\s*([A-Z][A-Za-z ]*[A-Za-z])", text):
            bad += [(path.name, m.group(1))] * (m.group(1).lower() not in headings)
        for m in re.finditer(r"REFERENCE\.md\s+\*([A-Z][^*]+)\*", text):
            bad += [(path.name, m.group(1))] * (m.group(1).lower() not in headings)
    assert not bad, f"pointers to a REFERENCE.md section that does not exist: {bad}"


def test_every_spell_is_in_the_document_with_its_own_effect():
    from gartok import magic
    from gartok.actions.spells import _SPELL_ACTIONS
    rows = _cells(_sections(reference.build())["Spells"])
    assert set(_SPELL_ACTIONS) == set(magic.SPELLS)
    for spell in magic.SPELLS.values():
        assert spell.name in rows and _SPELL_ACTIONS[spell.id].desc in rows, spell.id


def test_a_spell_effect_quotes_the_live_range_and_dice():
    from gartok.actions import spells
    assert f"within {spells.MagicMissileAction.REACH} squares" in spells.MagicMissileAction.desc
    assert spells.DragonfireAction.desc.count(f"{spells.DragonfireAction.DICE[0]}d{spells.DragonfireAction.DICE[1]}") == 1
