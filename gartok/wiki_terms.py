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


LINKED_CONDITIONS = ("routed",)   # conditions a keyword's text names: they link to their entry in the CONDITIONS chapter


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
    for cid in LINKED_CONDITIONS:
        out.setdefault(cid, {"name": i18n.t(f"ui.cond.{cid}.name"), "kind": i18n.t("wiki_terms.condition"),
                             "text": i18n.t(f"ui.cond.{cid}.rule"), "chapter": "conditions"})
    return out


def keywords_in(text: str) -> list[str]:
    """The ids of the keywords `text` names, in the order they first appear."""
    named = [(k.id, k.name) for k in keywords.all_keywords()] + [(c, terms()[c]["name"]) for c in LINKED_CONDITIONS]
    found = [(m.start(), kid) for kid, name in named
             for m in [re.search(rf"\b{re.escape(name)}s?\b", text or "")] if m]
    return [kid for _, kid in sorted(found)]


def tip(term_id: str) -> str:
    """The entry as the game's tooltip reads it: the name, the kind, the text, then the text of each
    keyword it names (one level, so a tooltip never opens a chain)."""
    t = terms()[term_id]
    return "\n".join(x for x in (t["name"], t["kind"], t["text"], *glosses(t["text"], skip=term_id)) if x)


def of_item(it) -> list[tuple[str, str]]:
    """The terms an item (an `ItemDef`) names, in order, each as (term id, its label on the page)."""
    known = terms()
    ids = [tid for tid in it.traits if tid in known]
    if it.finesse and "finesse" not in ids:
        ids.append("finesse")
    if it.thrown:
        ids += [t for t in ("thrown", "throw") if t not in ids]
    ids += [a for a in ITEM_ACTIONS.get(it.name, ()) if a not in ids]
    labels = {"thrown": i18n.t("wiki_terms.thrown_sq", n=it.thrown),
              "reach": i18n.t("wiki_terms.reach_n", n=1 + it.reach),
              "distance": i18n.t("wiki_terms.distance_sq", n=it.range)}
    # Reach 1 is every weapon's and goes unsaid; Distance is a shot's
    ids = [*(["reach"] if it.reach else []), *(["distance"] if it.range else []), *ids]
    return [(tid, labels.get(tid, known[tid]["name"])) for tid in ids]


def glosses(text: str, skip: str = "") -> list[str]:
    """The text of each keyword `text` names, for a tooltip to carry under it."""
    known = terms()
    return [known[k]["text"] for k in keywords_in(text) if k != skip]


def item_tip(name: str | None) -> str:
    """The item's wiki entry as a tooltip: name, kind, its stats, then each term it brings, or "" for
    a body that is no catalog item (Unarmed, a beast's Bite)."""
    it = items.get(name) if name else None
    if it is None:
        return ""
    stats = [f"{it.damage[0]}d{it.damage[1]}"] if it.damage else []
    stats += [f"AC +{it.ac}"] if it.ac else []
    known = terms()
    brought = [(lab, known[tid]["text"]) for tid, lab in of_item(it) if known[tid]["text"]]
    return "\n".join([i18n.name("item", it.name), " · ".join([i18n.lab(it.type.value), *stats]),
                      *(f"{lab}: {text}" for lab, text in brought), *glosses(" ".join(text for _, text in brought))])


def ability_tip(kind: str, name: str, effect: str) -> str:
    """A named rule of a unit (racial ability, talent) as a tooltip, with the keywords it names."""
    return "\n".join([name, kind, effect, *glosses(effect)])


def action_tip(name: str | None) -> str:
    """The tooltip of the action called `name` (as the sheet names a weapon's), or "" if none."""
    if not name:
        return ""
    return next((tip(tid) for tid, t in terms().items() if t["name"] == name), "")
