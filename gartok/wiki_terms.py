"""The terms the compendium links: every weapon trait and every combat action is one entry of the
ACTIONS chapter, every keyword (`keywords.py`) one of the KEYWORDS chapter, each named by its id, and
an item names the ones it brings. The wiki's item pages link
them, and any screen that names one shows the entry on hover."""

import re

from . import actions, i18n, items, keywords, weapon_traits

# what an item brings to the board besides its traits
ITEM_ACTIONS = {
    items.FIRST_AID_ITEM: ("first_aid", "stabilize"),
    "Minor Healing Potion": ("drink_potion",),
    items.SIGNAL_HORN_ITEM: ("signal_horn",),
}


def terms() -> dict[str, dict]:
    """Every term by id: its name, its kind line, its text and the wiki chapter it opens in; a trait
    that is a weapon action is that action's entry."""
    out = {}
    for tr in weapon_traits.all_traits():
        out.setdefault(tr.id, {"name": tr.name, "kind": i18n.t("wiki_terms.weapon_action") if tr.action_id else i18n.t("wiki_terms.weapon_trait"),
                               "text": tr.desc, "chapter": "actions"})
    for a in actions.PANEL_ACTIONS:
        kind = i18n.t("wiki_terms.combat" if a in actions.COMBAT_ACTIONS else "wiki_terms.utility")
        out.setdefault(a.id, {"name": a.name, "kind": i18n.t("wiki_terms.kind_cost", kind=kind, ap=a.cost), "text": getattr(a, "desc", "") or "",
                              "chapter": "actions"})
    for k in keywords.all_keywords():
        out.setdefault(k.id, {"name": k.name, "kind": i18n.t("wiki_terms.keyword"), "text": k.text, "chapter": "keywords"})
    return out


def keywords_in(text: str) -> list[str]:
    """The ids of the keywords `text` names, in the order they first appear."""
    found = [(m.start(), k.id) for k in keywords.all_keywords()
             for m in [re.search(rf"\b{re.escape(k.name)}\b", text or "")] if m]
    return [kid for _, kid in sorted(found)]


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
    return [(tid, i18n.t("wiki_terms.thrown_sq", n=it.thrown) if tid == "thrown" else known[tid]["name"]) for tid in ids]


def action_tip(name: str | None) -> str:
    """The tooltip of the action called `name` (as the sheet names a weapon's), or "" if none."""
    if not name:
        return ""
    return next((tip(tid) for tid, t in terms().items() if t["name"] == name), "")
