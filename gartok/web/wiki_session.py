"""The wiki and compendium, as pygame's `WikiScreen`: seven chapters (items, recipes, actions,
talents, races, beasts, rules) read off the live catalogs, and a filter over the open one.
Opened from the title or the map's menu; BACK returns there."""

from typing import ClassVar

from .. import (
    abilities,
    art_files,
    data,
    item_icon,
    items,
    talents,
    weapon_traits,
    wiki_races,
    wiki_rules,
    wiki_terms,
)
from .session import Session

CHAPTERS = (("items", "Items"), ("recipes", "Recipes"), ("actions", "Actions"), ("talents", "Talents"),
            ("races", "Races"), ("beasts", "Beasts"), ("rules", "Rules"))
MAX_QUERY = 24


def _entry(name, kind="", meta=(), body=(), tags=(), glyph=None, find=(), eid=None, links=()):
    """One card: `find` is what the filter reads besides the name and the kind; `links` are the terms
    it names, each a tag that opens the term's entry and shows it on hover."""
    return {"id": eid or name, "name": name, "kind": kind, "meta": [m for m in meta if m], "body": list(body),
            "tags": list(tags), "links": list(links), "glyph": glyph, "_find": " ".join([name, kind, *find]).lower()}


def _link(tid, label):
    return {"ref": f"actions:{tid}", "label": label, "tip": wiki_terms.tip(tid)}


def _item(it):
    tags = []
    if it.damage:
        tags.append(f"{it.damage[0]}d{it.damage[1]}")
    if it.ac:
        tags.append(f"AC +{it.ac}")
    tags += [tid.replace("_", " ").title() for tid in it.traits if not weapon_traits.get(tid)]
    links = [_link(tid, label) for tid, label in wiki_terms.of_item(it)]
    if it.range:
        tags.append(f"Range {it.range} sq")
    if it.hands == 2:
        tags.append("Two-handed")
    return _entry(it.name, it.type.value, [f"{it.weight:g} kg", f"${it.price}", it.rarity.value], tags=tags,
                  glyph=item_icon.glyph(it.name), links=links, find=[x["label"] for x in links])


def _recipe(target, rec):
    station = rec.station.value.title()
    return _entry(f"{target} ×{rec.yield_qty}" if rec.yield_qty > 1 else target, station,
                  [f"{rec.batch_hours:.1f} h a batch", f"level {rec.level}"],
                  [" + ".join(rec.materials)] + ([f"Tools: {', '.join(rec.tools)}"] if rec.tools else []),
                  glyph=item_icon.glyph(target), find=[" ".join(rec.materials)])


def _actions():
    return sorted((_entry(t["name"], t["kind"], body=[t["text"]] if t["text"] else [], find=[t["text"]], eid=tid)
                   for tid, t in wiki_terms.terms().items()), key=lambda e: e["name"])


def _talents():
    rows = sorted(((track, t) for track, tree in talents.TREE.items() for t in tree),
                  key=lambda p: (p[0], p[1].tier, p[1].name))
    out = []
    for track, t in rows:
        need = talents.get(t.requires) if t.requires else None
        races = (t.race,) if isinstance(t.race, str) else tuple(t.race or ())
        out.append(_entry(t.name, f"{track} · tier {t.tier}",
                          [f"needs {need.name if need else t.requires}" if t.requires else "a root",
                           f"{', '.join(races)} only" if races else None],
                          [t.effect], glyph=t.icon, find=[t.effect, *races]))
    return out


def _races():
    return [_entry(e["name"], "Race", [e["meta"]], e["abilities"], tags=e["mods"].split("  "),
                   glyph=f"head/{art_files.RACE_ICON[e['name']]}" if e["name"] in art_files.RACE_ICON else None,
                   find=[e["meta"], *e["abilities"], *e["talents"]])
            | {"track": e["talents"]} for e in wiki_races.entries()]


def _beasts():
    out = []
    for b in sorted(data._BEASTS, key=lambda b: b["name"]):
        ab = b.get("ability") or ()
        ab = ab if isinstance(ab, (tuple, list)) else (ab,)
        traits = [t.name for a in ab if (t := abilities.get(a))]
        drops = ([f"{b['drop_item']} ({round(b.get('drop_chance', 0) * 100)}%)"] if b.get("drop_item") else []) + \
                [f"{it} ×{qty} ({round(ch * 100)}%)" for it, ch, qty in b.get("also_drops", ())]
        out.append(_entry(b["name"], b.get("kind", "beast"), [f"Hit Die d{b['hd']}", b["size"], f"Speed {b['speed']:g} m"],
                          [f"Drops: {', '.join(drops) or 'nothing'}"], tags=traits, find=traits))
    return out


def _rules():
    return [_entry(title.title(), body=lines, find=lines) for title, lines in wiki_rules.sections()]


BUILD = {"items": lambda: [_item(i) for i in sorted(items.all_items().values(), key=lambda i: i.name)],
         "recipes": lambda: sorted((_recipe(target, rec)
                                    for target, rl in items.CRAFTING_RECIPES.items()
                                    for rec in (rl if isinstance(rl, (list, tuple)) else [rl])),
                                   key=lambda e: e["name"]),
         "actions": _actions, "talents": _talents, "races": _races, "beasts": _beasts, "rules": _rules}


class WikiSession(Session):
    screen = "wiki"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "chapter": lambda s, b: s.chapter(b["chapter"]),
        "find": lambda s, b: s.find(b.get("q", "")),
        "open": lambda s, b: s.open(b["ref"]),
        "back": lambda s, b: s.back_to(),
    }

    def __init__(self, back, back_label="Back"):
        self.back_to = back
        self.back_label = back_label
        self.tab = "items"
        self.query = ""
        self.focus = None

    def chapter(self, tab):
        if tab not in BUILD:
            raise ValueError(f"no chapter called {tab}")
        self.tab = tab
        self.focus = None
        return self.state()

    def open(self, ref):
        """Turn to the entry `ref` ("chapter:id") names, the filter cleared so it shows."""
        tab, _, eid = str(ref).partition(":")
        if tab not in BUILD or not any(e["id"] == eid for e in BUILD[tab]()):
            raise ValueError(f"no entry called {ref}")
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
        return {"chapters": [{"id": c, "label": label} for c, label in CHAPTERS], "chapter": self.tab,
                "query": self.query, "entries": shown, "total": len(rows), "back": self.back_label,
                "focus": self.focus}
