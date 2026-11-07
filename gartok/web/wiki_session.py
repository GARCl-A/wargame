"""The wiki and compendium, as pygame's `WikiScreen`: nine chapters (items, recipes, actions,
spells, keywords, talents, races, beasts, rules) read off the live catalogs, and a filter over the open one.
Opened from the title or the map's menu; BACK returns there."""

from typing import ClassVar

from .. import (
    abilities,
    art_files,
    data,
    i18n,
    item_icon,
    items,
    magic,
    talents,
    weapon_traits,
    wiki_races,
    wiki_rules,
    wiki_terms,
)
from .session import Session

CHAPTERS = (("items", "Items"), ("recipes", "Recipes"), ("actions", "Actions"), ("spells", "Spells"), ("keywords", "Keywords"),
            ("talents", "Talents"),
            ("races", "Races"), ("beasts", "Beasts"), ("rules", "Rules"))
MAX_QUERY = 24


def _entry(name, kind="", meta=(), body=(), tags=(), glyph=None, find=(), eid=None, links=(), label=None):
    """One card: `find` is what the filter reads besides the name and the kind; `links` are the terms
    it names, each a tag that opens the term's entry and shows it on hover. `name` is the id the entry is
    found by; `label` is what the player reads in its place when the catalog names it."""
    return {"id": eid or name, "name": label or name, "kind": kind, "meta": [m for m in meta if m], "body": list(body),
            "tags": list(tags), "links": list(links), "glyph": glyph, "_find": " ".join([label or name, name, kind, *find]).lower()}


def _link(tid, label):
    return {"ref": f"{wiki_terms.terms()[tid]['chapter']}:{tid}", "label": label, "tip": wiki_terms.tip(tid)}


def _item(it):
    tags = []
    if it.damage:
        tags.append(f"{it.damage[0]}d{it.damage[1]}")
    if it.ac:
        tags.append(f"AC +{it.ac}")
    tags += [tid.replace("_", " ").title() for tid in it.traits if not weapon_traits.get(tid)]
    links = [_link(tid, label) for tid, label in wiki_terms.of_item(it)]
    if it.range:
        tags.append(i18n.t("wiki_session.range_sq", range=it.range))
    if it.hands == 2:
        tags.append(i18n.t("wiki_session.two_handed"))
    return _entry(it.name, i18n.lab(it.type.value), [i18n.t("wiki_session.kg", weight=it.weight), f"${it.price}", i18n.lab(it.rarity.value)], tags=tags,
                  glyph=item_icon.glyph(it.name), links=links, find=[x["label"] for x in links],
                  label=i18n.name("item", it.name))


def _recipe(target, rec):
    station = i18n.lab(rec.station.value.title())
    shown = i18n.name("item", target)
    return _entry(f"{target} ×{rec.yield_qty}" if rec.yield_qty > 1 else target, station,
                  [i18n.t("wiki_session.batch_h", h=f"{rec.batch_hours:.1f}"), i18n.t("wiki_session.level", level=rec.level)],
                  [" + ".join(i18n.name("item", m) for m in rec.materials)]
                  + ([i18n.t("wiki_session.tools", join=', '.join(i18n.name("item", t) for t in rec.tools))] if rec.tools else []),
                  glyph=item_icon.glyph(target), find=[" ".join(rec.materials)],
                  label=f"{shown} ×{rec.yield_qty}" if rec.yield_qty > 1 else shown)


def _terms(chapter):
    """The entries of a chapter that reads `wiki_terms`; each links the keywords its text names."""
    out = []
    for tid, t in wiki_terms.terms().items():
        if t["chapter"] != chapter:
            continue
        links = [_link(k, wiki_terms.terms()[k]["name"]) for k in wiki_terms.keywords_in(t["text"]) if k != tid]
        out.append(_entry(t["name"], t["kind"], body=[t["text"]] if t["text"] else [], links=links,
                          find=[t["text"], *(x["label"] for x in links)], eid=tid))
    return sorted(out, key=lambda e: e["name"])


def _talents():
    rows = sorted(((track, t) for track, tree in talents.TREE.items() for t in tree),
                  key=lambda p: (p[0], p[1].tier, p[1].name))
    out = []
    for track, t in rows:
        need = talents.get(t.requires) if t.requires else None
        races = (t.race,) if isinstance(t.race, str) else tuple(t.race or ())
        out.append(_entry(t.name, i18n.t("wiki_session.tier", track=track, tier=t.tier),
                          [i18n.t("wiki_session.needs", value=need.name if need else t.requires) if t.requires else i18n.lab("a root"),
                           i18n.t("wiki_session.only", join=', '.join(races)) if races else None],
                          [t.effect], glyph=t.icon, find=[t.effect, *races]))
    return out


def _races():
    return [_entry(e["name"], i18n.lab("Race"), [e["meta"]], e["abilities"], tags=e["mods"].split("  "),
                   glyph=f"head/{art_files.RACE_ICON[e['name']]}" if e["name"] in art_files.RACE_ICON else None,
                   find=[e["meta"], *e["abilities"], *e["talents"]], label=i18n.name("race", e["name"]))
            | {"track": e["talents"]} for e in wiki_races.entries()]


def _beasts():
    out = []
    for b in sorted(data._BEASTS, key=lambda b: b["name"]):
        ab = b.get("ability") or ()
        ab = ab if isinstance(ab, (tuple, list)) else (ab,)
        traits = [t.name for a in ab if (t := abilities.get(a))]
        drops = ([f"{i18n.name('item', b['drop_item'])} ({round(b.get('drop_chance', 0) * 100)}%)"] if b.get("drop_item") else []) + \
                [f"{i18n.name('item', it)} ×{qty} ({round(ch * 100)}%)" for it, ch, qty in b.get("also_drops", ())]
        out.append(_entry(b["name"], i18n.lab(b.get("kind", "beast")), [i18n.t("wiki_session.hit_die_d", b=b['hd']), i18n.name("size", b["size"]), i18n.t("wiki_session.speed_m", b=b['speed'])],
                          [i18n.t("wiki_session.drops", value=', '.join(drops) or i18n.lab('nothing'))], tags=traits, find=traits, label=i18n.name("race", b["name"])))
    return out


def _spells():
    from ..actions.spells import _SPELL_ACTIONS

    out = []
    for sp in sorted(magic.SPELLS.values(), key=lambda s: (s.level, s.name)):
        action = _SPELL_ACTIONS[sp.id]
        schools = [i18n.lab(s.title()) for s in sorted(sp.sources)] if len(sp.sources) < len(magic.SOURCES) \
            else [i18n.lab("Any school")]
        desc = str(action.desc)
        out.append(_entry(sp.id, i18n.t("wiki_session.spell_level", level=sp.level),
                          [i18n.t("wiki_session.spell_ap", ap=action.cost),
                           i18n.t("wiki_session.spell_points", points=magic.points_to_learn(sp.level))],
                          [desc], tags=schools, find=[desc, *schools], label=sp.name))
    return out


def _rules():
    return [_entry(title, body=lines, find=lines) for title, lines in wiki_rules.sections()]


BUILD = {"items": lambda: [_item(i) for i in sorted(items.all_items().values(), key=lambda i: i18n.name("item", i.name))],
         "recipes": lambda: sorted((_recipe(target, rec)
                                    for target, rl in items.CRAFTING_RECIPES.items()
                                    for rec in (rl if isinstance(rl, (list, tuple)) else [rl])),
                                   key=lambda e: e["name"]),
         "actions": lambda: _terms("actions"), "spells": _spells, "keywords": lambda: _terms("keywords"),
         "talents": _talents, "races": _races, "beasts": _beasts, "rules": _rules}


class WikiSession(Session):
    screen = "wiki"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "chapter": lambda s, b: s.chapter(b["chapter"]),
        "find": lambda s, b: s.find(b.get("q", "")),
        "open": lambda s, b: s.open(b["ref"]),
        "back": lambda s, b: s.back_to(),
    }

    def __init__(self, back, back_label=None):
        self.back_to = back
        self.back_label = back_label or i18n.t("ui.title.back")
        self.tab = "items"
        self.query = ""
        self.focus = None

    def chapter(self, tab):
        if tab not in BUILD:
            raise ValueError(i18n.t("wiki_session.no_chapter_called", tab=tab))
        self.tab = tab
        self.focus = None
        return self.state()

    def open(self, ref):
        """Turn to the entry `ref` ("chapter:id") names, the filter cleared so it shows."""
        tab, _, eid = str(ref).partition(":")
        if tab not in BUILD or not any(e["id"] == eid for e in BUILD[tab]()):
            raise ValueError(i18n.t("wiki_session.no_entry_called", ref=ref))
        self.tab, self.query, self.focus = tab, "", eid
        return self.state()

    def find(self, q):
        self.query = str(q)[:MAX_QUERY].lower()
        self.focus = None
        return self.state()

    def state(self):
        rows = BUILD[self.tab]()
        q = self.query.strip()
        shown = [{k: v for k, v in e.items() if k != "_find"} for e in rows if not q or q in e["_find"]]
        return {"chapters": [{"id": c, "label": i18n.lab(label)} for c, label in CHAPTERS], "chapter": self.tab,
                "query": self.query, "entries": shown, "total": len(rows), "back": self.back_label,
                "focus": self.focus}
