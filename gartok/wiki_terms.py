"""The terms the compendium links: every weapon trait and every combat action is one entry of the
ACTIONS chapter, named by its id, and an item names the ones it brings. The wiki's item pages link
them, and any screen that names one shows the entry on hover."""

from . import actions, items, weapon_traits

# what an item brings to the board besides its traits
ITEM_ACTIONS = {
    items.FIRST_AID_ITEM: ("first_aid", "stabilize"),
    "Minor Healing Potion": ("drink_potion",),
    items.SIGNAL_HORN_ITEM: ("signal_horn",),
}


def terms() -> dict[str, dict]:
    """Every term by id: its name, its kind line and its text; a trait that is a weapon action is
    that action's entry."""
    out = {}
    for tr in weapon_traits.all_traits():
        out.setdefault(tr.id, {"name": tr.name, "kind": "Weapon action · 2 AP" if tr.action_id else "Weapon trait",
                               "text": tr.desc})
    for a in actions.PANEL_ACTIONS:
        kind = "Combat" if a in actions.COMBAT_ACTIONS else "Utility"
        out.setdefault(a.id, {"name": a.name, "kind": f"{kind} · {a.cost} AP", "text": getattr(a, "desc", "") or ""})
    return out


def tip(term_id: str) -> str:
    """The entry as the game's tooltip reads it: the name, the kind, the text."""
    t = terms()[term_id]
    return "\n".join(x for x in (t["name"], t["kind"], t["text"]) if x)


def of_item(it) -> list[tuple[str, str]]:
    """The terms an item (an `ItemDef`) names, in order, each as (term id, its label on the page)."""
    known = terms()
    ids = [tid for tid in it.traits if tid in known]
    if it.finesse and "finesse" not in ids:
        ids.append("finesse")
    if it.thrown:
        ids += [t for t in ("thrown", "throw") if t not in ids]
    ids += [a for a in ITEM_ACTIONS.get(it.name, ()) if a not in ids]
    return [(tid, f"Thrown {it.thrown} sq" if tid == "thrown" else known[tid]["name"]) for tid in ids]


def action_tip(name: str | None) -> str:
    """The tooltip of the action called `name` (as the sheet names a weapon's), or "" if none."""
    if not name:
        return ""
    return next((tip(tid) for tid, t in terms().items() if t["name"] == name), "")
