"""The wiki's RACES tab: each playable race read off the live tables (`data`, `abilities`,
`talents`), so the page never drifts from the rules."""

from . import abilities, data, i18n, talents

_ABBREV = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


def _ability_ids(race):
    a = race["ability"]
    return a if isinstance(a, (tuple, list)) else (a,) if a else ()


def mods_line(race):
    """The six attribute modifiers, abbreviated in the current language."""
    return "  ".join(f"{i18n.lab(a)} {m:+d}" for a, m in zip(_ABBREV, race["mods"]))


def meta_line(race, hit_die=True):
    return "  ·  ".join([i18n.name("size", race["size"]), *([i18n.t("wiki_session.hit_die_d", b=race["hd"])] if hit_die else []),
                         i18n.t("wiki_session.speed_m", b=race["speed"]),
                         i18n.t("wiki_session.speaks", languages=", ".join(i18n.names("language", race["languages"])))])


def entries():
    """One dict per playable race, alphabetical: name, the line of numbers, the attribute
    modifiers, the racial abilities, the racial talent track."""
    out = []
    for race in sorted((r for r in data._RACES if r["name"] in data.RACE_NAMES), key=lambda r: r["name"]):
        traits = [abilities.get(a) for a in _ability_ids(race)]
        out.append({
            "name": race["name"],
            "meta": meta_line(race),
            "mods": mods_line(race),
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


def race_tip(name: str) -> str:
    """The tooltip of a race: its localized name, attribute modifiers, and racial abilities."""
    if not name:
        return ""
    race = data.race_by_name(name)
    if not race:
        return ""
    head = i18n.name("race", race["name"])
    mods = mods_line(race)
    traits = [abilities.get(a) for a in _ability_ids(race)]
    ab_lines = [f"{t.name}: {t.effect}" for t in traits if t is not None]
    return "\n".join([head, mods, meta_line(race, hit_die=False), *ab_lines])

