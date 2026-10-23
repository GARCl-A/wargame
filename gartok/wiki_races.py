"""The wiki's RACES tab: each playable race read off the live tables (`data`, `abilities`,
`talents`), so the page never drifts from the rules."""

from . import abilities, data, talents

_ABBREV = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


def _ability_ids(race):
    a = race["ability"]
    return a if isinstance(a, (tuple, list)) else (a,) if a else ()


def entries():
    """One dict per playable race, alphabetical: name, the line of numbers, the attribute
    modifiers, the racial abilities, the racial talent track."""
    out = []
    for race in sorted((r for r in data._RACES if r["name"] in data.RACE_NAMES), key=lambda r: r["name"]):
        traits = [abilities.get(a) for a in _ability_ids(race)]
        out.append({
            "name": race["name"],
            "meta": (f"{race['size']}  ·  Hit Die d{race['hd']}  ·  Speed {race['speed']:g} m  ·  "
                     f"Speaks {', '.join(race['languages'])}"),
            "mods": "  ".join(f"{a} {m:+d}" for a, m in zip(_ABBREV, race["mods"])),
            "abilities": [f"{t.name}: {t.effect}" for t in traits if t is not None],
            "talents": [t.name for t in talents.racial_tree(race["name"])],
        })
    return out


def matching(query):
    q = (query or "").lower()
    if not q:
        return entries()
    return [e for e in entries()
            if q in " ".join([e["name"], e["meta"], *e["abilities"], *e["talents"]]).lower()]
