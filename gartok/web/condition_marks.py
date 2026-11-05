"""The condition marks the battle board draws: a gem on a token's rim, a pip under its initiative coin.

One entry per condition id (plus poison and hunger, which are not `Condition`s): the icon, the class
that colours it and its place in the order, the control that stops a fighter first. The words are
`cond.<id>.name` / `cond.<id>.rule` in `locales/en.json`; `args` fills the rule's blanks.
"""

B = "ffffff/transparent/1x1/"

MARKS = {
    "entangled": ("trap/" + B + "lorc/spider-web", "ctl"),
    "grappled": ("trap/" + B + "lorc/manacles", "ctl"),
    "prone": ("trap/" + B + "lorc/foot-trip", "ctl"),
    "sleeping": ("state/" + B + "lorc/sleepy", "ctl"),
    "surprised": ("state/" + B + "lorc/surprised", "ctl"),
    "rooted": ("trap/" + B + "delapouite/sticky-boot", "ctl"),
    "bleeding": ("blood/" + B + "lorc/bleeding-wound", "hurt"),
    "maimed": ("blood/" + B + "lorc/internal-injury", "hurt"),
    "poisoned": ("poison/" + B + "lorc/poison-bottle", "hurt"),
    "shield_hooked": ("trap/" + B + "lorc/fishing-hook", "hurt"),
    "hexed": ("symbol/" + B + "lorc/cursed-star", "mind"),
    "demoralized": ("state/" + B + "lorc/despair", "mind"),
    "hungry": ("meat/" + B + "lorc/meat", "mind"),
    "defending": ("item/round-shield", "boon"),
    "invisible": ("state/" + B + "lorc/hidden", "boon"),
    "pixie_flight": ("wing/" + B + "lorc/fairy", "boon"),
}
_ORDER = list(MARKS)


def _args(c):
    if c.id == "bleeding":
        return {"damage": c.damage, "turns": c.duration}
    if c.id == "sleeping" and c.duration is not None:
        return {"turns": c.duration}
    return {}


def marks(u):
    """Every mark `u` wears, control first, then wounds, then the mind, then boons."""
    out = [{"id": c.id, "args": _args(c)} for c in u.conditions if c.id in MARKS]
    if u.poisoned:
        out.append({"id": "poisoned", "args": {}})
    if u.hunger_level:
        out.append({"id": "hungry", "args": {"label": u.hunger_label}})
    out.sort(key=lambda m: _ORDER.index(m["id"]))
    return [{**m, "icon": MARKS[m["id"]][0], "cls": MARKS[m["id"]][1]} for m in out]
