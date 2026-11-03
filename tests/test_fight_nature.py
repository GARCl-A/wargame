"""Every fight the game starts declares its nature (`fight_nature`), as the audit table in `RULES.md`
(*Where fights come from*) lists it."""

import ast
import pathlib

import pytest

from gartok import arena, fight_nature, forced, hunt, ox
from gartok.web import campaign_fight

SOUGHT, OPPORTUNIST, DETERMINED = fight_nature.SOUGHT, fight_nature.OPPORTUNIST, fight_nature.DETERMINED

FORCED_TABLE = {
    "ambush": OPPORTUNIST,
    "gather_ambush": OPPORTUNIST,
    "supply_ambush": OPPORTUNIST,
    "fortress_ambush": DETERMINED,
    "guard": DETERMINED,
    "eviction": DETERMINED,
    "wilds_raid": OPPORTUNIST,
    "wilds_seizure": OPPORTUNIST,
    "wilds_aid": OPPORTUNIST,
    "wilds_retake": SOUGHT,
}

DECLARED = {
    "hunt.PACK_NATURE": (hunt.PACK_NATURE, OPPORTUNIST),
    "hunt.BIWOLF_NATURE": (hunt.BIWOLF_NATURE, DETERMINED),
    "ox.TRACK_NATURE": (ox.TRACK_NATURE, SOUGHT),
    "arena.BOUT_NATURE": (arena.BOUT_NATURE, SOUGHT),
    "arena.DEFENSE_NATURE": (arena.DEFENSE_NATURE, DETERMINED),
    "campaign_fight.CLAIM_NATURE": (campaign_fight.CLAIM_NATURE, SOUGHT),
    "campaign_fight.DELVE_NATURE": (campaign_fight.DELVE_NATURE, SOUGHT),
    "campaign_fight.ERRAND_NATURE": (campaign_fight.ERRAND_NATURE, SOUGHT),
}


def test_every_forced_event_has_the_nature_the_audit_gave_it():
    assert {k: e.nature for k, e in forced.EVENTS.items()} == FORCED_TABLE


@pytest.mark.parametrize("name", sorted(DECLARED))
def test_every_other_fight_source_declares_the_audited_nature(name):
    declared, audited = DECLARED[name]
    assert declared == audited


def test_every_campaign_fight_passes_a_nature_to_enter():
    """`campaign_fight._enter` is the one door of every campaign fight; each call names its nature."""
    root = pathlib.Path(campaign_fight.__file__).parent.parent
    calls = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_enter":
                calls.append((path.name, node.lineno, any(k.arg == "nature" for k in node.keywords)))
    assert len(calls) >= 7
    assert [c for c in calls if not c[2]] == []


def test_enter_refuses_an_unknown_nature():
    with pytest.raises(ValueError, match="nature"):
        campaign_fight._enter(None, None, None, None, "k", "t", None, nature="ambushed")


def test_the_ledger_hold_ambush_is_its_own_event_after_the_road_one():
    kinds = list(forced.EVENTS)
    assert forced.EVENTS["fortress_ambush"].arrival == (forced.fortress_ambush_catch,)
    assert forced.road_ambush_catch in forced.EVENTS["ambush"].arrival
    assert forced.fortress_ambush_catch not in forced.EVENTS["ambush"].arrival
    assert kinds.index("ambush") < kinds.index("fortress_ambush")
    assert "fortress_ambush" in forced.TALKS
