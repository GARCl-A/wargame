"""The character sheet as one component, three densities.

    draw_sheet(surf, F, rect, ch, density, editable, only, mouse)
        -> (height consumed, tooltip or None)
    draw_row(surf, F, rect, ch, selected, tag)
        -> the list-row form (guild list / band rail)

Design, carried over from the planning pass in
`character_sheet_audit/planejamentos/sheet.py`:

  1. CANONICAL ORDER. Blocks always come out in `ORDER`. A screen cuts
     blocks (`only=`), it never reorders them -- the eye learns where to
     look once and never relearns it.
  2. THREE DENSITIES. Each density fixes which blocks appear and the
     FIXED HEIGHT of each one. Fixed height is what lets cards drawn
     side by side (squad draft, a band column) align without any screen
     doing its own layout math.
  3. `ch` is a plain dict (`unit_to_ch` builds it from a real Unit/
     Combatant) -- this module never reads a domain object directly, so
     it stays reusable the way every other `gartok/ui` component is.

Who uses what (today; more lands as screens migrate):
    density="full"     sheet modal (`sheet_panel.SheetModalMixin`)
    density="compact"  battle inspect panel, character creator preview

`density="normal"` (draft card / band column / guild panel) and
`draw_row` (guild list / band rail) are built here for the next
migration pass but not wired into a screen yet -- see the redesign
notes in `character_sheet_audit/README.md` for why (mostly: those
screens interleave real interactive state -- edit mode, drag/drop,
leadership controls -- that this read-only renderer doesn't attempt to
own).
"""

import pygame

from .. import data
from .primitives import caps, contained, ellipsize, section, text, token_badge, wrap
from .tokens import T

# ---------------------------------------------------------------- order
ORDER = ["identity", "status", "vitals", "attributes", "weapon", "gear",
         "languages", "ability"]

BLOCKS = {
    "compact": ["identity", "status", "vitals", "attributes", "weapon", "gear"],
    "normal":  ["identity", "status", "vitals", "attributes", "weapon", "gear",
                "languages", "ability"],
    "full":    ORDER,
}

# fixed height per block per density -- this is what makes cards align
H = {
    "compact": dict(identity=T.S * 5, status=T.S * 3, vitals=T.S * 4,
                    attributes=T.S * 4, weapon=T.S * 6, gear=T.S * 5),
    "normal":  dict(identity=T.S * 6, status=T.S * 3, vitals=T.S * 8,
                    attributes=T.S * 8, weapon=T.S * 8, gear=T.S * 6,
                    languages=T.S * 5, ability=T.S * 9),
    "full":    dict(identity=T.S * 8, status=T.S * 3, vitals=T.S * 10,
                    attributes=T.S * 10, weapon=T.S * 9, gear=T.S * 14,
                    languages=T.S * 5, ability=T.S * 9),
}

GAP = {"compact": T.S, "normal": T.S * 2, "full": T.S * 2}


def sheet_height(density, only=None):
    blocks = [b for b in BLOCKS[density] if only is None or b in only]
    if not blocks:
        return 0
    return sum(H[density][b] for b in blocks) + GAP[density] * (len(blocks) - 1)


# ---------------------------------------------------------------- adapter
def _to_hit(u):
    """Mirrors `sheet_panel._to_hit` -- kept as its own small copy here
    (rather than imported) so this module never imports the legacy
    `sheet_panel`, which itself will come to depend on this one."""
    if u.improvised:
        return u.mod_strength, "STR"
    return u.attack_bonus


def _weapon_line(u):
    """Mirrors `sheet_panel._weapon_lines`, trimmed to what the card needs."""
    if u.unarmed:
        n, faces = u.unarmed_damage
        return "unarmed", f"{n}d{faces} {u.mod_strength:+} (STR)", "melee"
    n, faces = (u.unarmed_damage if u.improvised else u.weapon["damage"])
    if u.improvised:
        return (f"{u.weapon_name} (no arrow -> improvised)",
                f"{n}d{faces} {u.mod_strength:+} (STR)", "melee")
    bonus = u.mod_strength if not u.ranged else 0
    dmg = f"{n}d{faces}" + (f" {bonus:+} (STR)" if bonus else "")
    hands = "2 hands" if u.weapon["hands"] == 2 else "1 hand"
    if u.ranged:
        reach = f"range {u.weapon['range']}  ·  {u.ammo} arrows  ·  {hands}"
    else:
        thrown = f"  ·  thrown {u.weapon['thrown']}" if u.weapon["thrown"] else ""
        reach = f"melee  ·  {hands}{thrown}"
    return u.weapon_name, dmg, reach


_ATTRS = [("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
          ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma")]


def unit_to_ch(u):
    """Adapts a Unit or Combatant (`u`) into the plain dict every block
    painter below reads. `u` should be a `Combatant` when to-hit/ammo
    need battle context (see callers) -- a bare `Unit` works too since
    `Combatant` proxies the same attributes it doesn't override."""
    status = []
    if u.dying:
        status.append(f"dying {u.death_clock}/{data.DYING_TURNS}")
    elif u.stable:
        status.append("stable")
    elif u.broken:
        status.append("broken")
    elif u.fled:
        status.append("fled")
    elif u.dead:
        status.append("dead")
    elif u.hunger_level:
        status.append(u.hunger_label)
    tags = ["champion of the pit"] if getattr(u, "arena_title", False) else []

    wname, dmg, reach = _weapon_line(u)
    bab, src = _to_hit(u)
    tongue = None
    if u.has_tongue_weapon:
        tn, tf = u.tongue_weapon["damage"]
        tb = u.mod_strength + u.char.talent_bonus("melee_damage")
        tongue = (u.tongue_weapon_name,
                  f"{tn}d{tf}" + (f" {tb:+} (STR)" if tb else ""), u.tongue_reach)

    held = " + ".join(p for p in ("weapon" if u.weapon_hand else "",
                                  "torch" if u.torch_hand else "",
                                  "lantern" if u.lantern_hand else "") if p) or "empty"
    a = u.armor
    armor = (f"{u.armor_name}  ·  +{a['ac']} AC") if a else None
    pack = list(u.inventory)

    return {
        "name": u.name, "race": u.race["name"], "occ": u.occupation["name"],
        "align": u.alignment, "size": u.size, "age": u.age, "combat": f"N{u.combat_level}",
        "status": status, "tags": tags,
        "hp": (max(u.hp, 0), u.hp_max), "ac": u.ac, "md": u.mental_defense, "spd": u.speed,
        "init": f"{u.initiative_bonus():+}",
        "attrs": [(k, getattr(u, name), getattr(u, f"mod_{name}")) for k, name in _ATTRS],
        "weapon": {"nm": wname, "hit": f"d20 {bab:+} ({src})", "dmg": dmg, "tags": reach,
                  "crit": "crit 20, fumble 1"},
        "tongue": tongue,
        "gear": {"hands": held, "armor": armor, "pack": pack,
                "load": (u.load, u.carry_normal, u.carry_max), "copper": u.gold},
        "langs": list(u.languages),
        "recipes": list(getattr(u, "recipes", []) or []),
        "ability": (u.ability.name, u.ability.effect),
        "unit": u,                    # kept for tooltip lookups (hp_breakdown, etc.)
    }


def _hp_tooltip(u, F):
    b = u.hp_breakdown()
    lines = [("hit points (hp)", F["microb"], T.BRASS)]
    dice_cnt = b["hit_dice"]
    lines.append((f"base die 1d{b['hd']} x {dice_cnt}, dice sum {b['dice_sum']}",
                  F["body_sm"], T.TX_MUTED))
    con_col = T.GREEN if b["con_total"] > 0 else T.BLOOD if b["con_total"] < 0 else T.TX_MUTED
    lines.append((f"CON {b['con_mod']:+} x {dice_cnt} HD = {b['con_total']:+}",
                  F["body_sm"], con_col))
    if b["talent_total"]:
        lines.append((f"Hardy talent: +{b['talent_total']}", F["body_sm"], T.GREEN))
    if b["ability_bonus"]:
        lines.append((f"{b['ability_name']}: +{b['ability_bonus']}", F["body_sm"], T.GREEN))
    if b["override"] is not None:
        lines.append((f"manual override: {b['override']}", F["body_sm"], T.BRASS))
    if b["starving"]:
        lines.append(("starving: capped at 1 HP", F["body_sm"], T.BLOOD))
    lines.append((f"max HP: {b['final_max']}", F["bodyb"], T.BRASS))
    return lines


# ---------------------------------------------------------------- helpers
def _cell(s, F, rect, label, value, color=T.TX, small=False):
    pygame.draw.rect(s, T.TABLE, rect)
    pygame.draw.rect(s, T.STEEL_LINE, rect, 1)
    caps(s, F["micro"], label, (rect.centerx, rect.y + 7), T.TX_FAINT, center=True)
    f = F["bodyb"] if small else F["big"]
    text(s, f, str(value), (rect.centerx, rect.centery + (3 if small else 7)), color, center=True)


def _hp_color(cur, mx):
    if mx <= 0:
        return T.TX_FAINT
    ratio = cur / mx
    if ratio <= 0.25:
        return T.BLOOD
    if ratio <= 0.5:
        return T.BRASS
    return T.GREEN


# ---------------------------------------------------------------- blocks
def _b_identity(s, F, r, ch, d, ed, mouse, tip):
    if d == "compact":
        text(s, F["bodyb"], ch["name"], (r.x, r.y), T.TX)
        caps(s, F["micro"], f"{ch['race']} · {ch['occ']}", (r.x, r.y + T.S * 2 + 2), T.TX_FAINT)
        return
    dr = T.S * 3 if d == "normal" else T.S * 4
    cx, cy = r.x + dr, r.y + dr
    token_badge(s, F, (cx, cy), ch["unit"], r=dr)
    x = r.x + dr * 2 + T.S * 2
    text(s, F["titleb"] if d == "full" else F["nameb"], ch["name"], (x, r.y), T.TX)
    caps(s, F["micro"], f"{ch['race']} · {ch['occ']}", (x, r.y + T.S * 3 + 4), T.TX_MUTED)
    if d == "full":
        caps(s, F["micro"], f"{ch['align']} · {ch['size']} · {ch['age']} yrs · combat {ch['combat']}",
             (x, r.y + T.S * 5 + 4), T.TX_FAINT)


def _b_status(s, F, r, ch, d, ed, mouse, tip):
    x = r.x
    for tagtxt in ch["status"]:
        w = F["micro"].size(tagtxt.upper())[0] + T.S * 2
        box = pygame.Rect(x, r.y, w, T.S * 2 + 4)
        pygame.draw.rect(s, T.STEEL, box)
        pygame.draw.rect(s, T.BLOOD, box, 1)
        caps(s, F["micro"], tagtxt, box.center, T.BLOOD, center=True)
        x += w + T.S
    for tagtxt in ch["tags"]:
        w = F["micro"].size(tagtxt.upper())[0] + T.S * 2
        box = pygame.Rect(x, r.y, w, T.S * 2 + 4)
        pygame.draw.rect(s, T.STEEL_LINE, box, 1)
        caps(s, F["micro"], tagtxt, box.center, T.TX_MUTED, center=True)
        x += w + T.S


def _b_vitals(s, F, r, ch, d, ed, mouse, tip):
    cur, mx = ch["hp"]
    vals = dict(hp=str(cur), ac=ch["ac"], md=ch["md"], spd=ch["spd"])
    keys = ["hp", "ac", "md", "spd"] + (["init"] if d == "full" else [])
    if d == "full":
        vals["init"] = ch["init"]
    if d == "compact":
        x = r.x
        for k in keys:
            caps(s, F["micro"], k, (x, r.y + 2), T.TX_FAINT)
            text(s, F["bodyb"], str(vals[k]), (x + T.S * 4, r.y),
                 _hp_color(cur, mx) if k == "hp" else T.TX)
            x += T.S * 9
        return
    n = len(keys)
    cw = (r.w - T.S * (n - 1)) // n
    for i, k in enumerate(keys):
        c = pygame.Rect(r.x + i * (cw + T.S), r.y, cw, r.h)
        _cell(s, F, c, k, vals[k], _hp_color(cur, mx) if k == "hp" else T.TX)
        if mouse and c.collidepoint(mouse):
            if k == "hp":
                tip.append(_hp_tooltip(ch["unit"], F))
            elif k.upper() in data.DERIVED_HELP:
                t, desc = data.DERIVED_HELP[k.upper()]
                tip.append(_format_tip(t, desc, F))


def _format_tip(title, desc, F):
    from .primitives import format_tooltip
    return format_tooltip(title, desc, F)


def _b_attributes(s, F, r, ch, d, ed, mouse, tip):
    n = len(ch["attrs"])
    if d == "compact":
        x = r.x
        for nm, v, mod in ch["attrs"]:
            caps(s, F["micro"], nm, (x, r.y + 2), T.TX_FAINT)
            text(s, F["body"], f"{v}", (x + T.S * 3, r.y - 1), T.TX)
            caps(s, F["micro"], f"{mod:+d}", (x + T.S * 5 + 4, r.y + 2),
                 T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT)
            x += T.S * 8
        return
    cw = (r.w - T.S * (n - 1)) // n
    for i, (nm, v, mod) in enumerate(ch["attrs"]):
        c = pygame.Rect(r.x + i * (cw + T.S), r.y, cw, r.h)
        _cell(s, F, c, nm, v, T.TX, small=(d == "normal"))
        caps(s, F["micro"], f"{mod:+d}", (c.centerx, c.bottom - 14),
             T.GREEN if mod > 0 else T.BLOOD if mod < 0 else T.TX_FAINT, center=True)
        if mouse and c.collidepoint(mouse) and nm in data.ATTRIBUTE_HELP:
            t, desc = data.ATTRIBUTE_HELP[nm]
            tip.append(_format_tip(t, desc, F))


def _b_weapon(s, F, r, ch, d, ed, mouse, tip):
    w = ch["weapon"]
    y = r.y
    if d != "compact":
        y = section(s, F, "attack with the weapon in hand", r.x, y, r.w)
    text(s, F["bodyb"], w["nm"], (r.x, y), T.TX)
    caps(s, F["micro"], w["tags"], (r.right, y + 2), T.TX_FAINT, right=True)
    y += T.S * 2 + 4
    text(s, F["micro"], f"to hit  {w['hit']}   ·   {w['crit']}", (r.x, y), T.TX_MUTED)
    y += T.S * 2
    text(s, F["micro"], f"damage  {w['dmg']}", (r.x, y), T.TX_MUTED)
    if ch["tongue"] and d == "full":
        y += T.S * 2
        tn, tdmg, treach = ch["tongue"]
        text(s, F["micro"], f"tongue  {tn}  ·  {tdmg}  ·  reach {treach}", (r.x, y), T.TX_FAINT)


def _b_gear(s, F, r, ch, d, ed, mouse, tip):
    g = ch["gear"]
    cur, norm, high = g["load"]
    y = r.y
    if d == "full":
        y = section(s, F, "gear", r.x, y, r.w)
        vx = r.x + T.S * 8
        vw = r.right - vx
        for lab, val in (("hands", g["hands"]), ("armor", g["armor"] or "none"),
                         ("pack", ", ".join(g["pack"]) if g["pack"] else "empty")):
            caps(s, F["micro"], lab, (r.x, y + 2), T.TX_FAINT)
            text(s, F["body"], ellipsize(val, F["body"], vw), (vx, y - 1),
                 T.TX_FAINT if val in ("empty", "none") else T.TX_MUTED)
            y += T.S * 2 + 4
        y += 2
    bar = pygame.Rect(r.x, y, r.w, 8)
    pygame.draw.rect(s, T.TABLE, bar)
    pygame.draw.rect(s, T.STEEL_LINE, bar, 1)
    ratio = min(cur / high, 1.0) if high else 0
    over = cur > norm
    pygame.draw.rect(s, T.BLOOD if over else T.GREEN,
                     pygame.Rect(bar.x + 1, bar.y + 1, int((bar.w - 2) * ratio), bar.h - 2))
    if high:
        mark = bar.x + int((bar.w - 2) * (norm / high))
        pygame.draw.line(s, T.TX_FAINT, (mark, bar.y - 2), (mark, bar.bottom + 2), 1)
    caps(s, F["micro"], f"load {cur:g} kg  ·  normal {norm:g}  ·  high {high:g}",
         (r.x, bar.bottom + 4), T.BLOOD if over else T.TX_FAINT)
    caps(s, F["micro"], f"{g['copper']} c", (r.right, bar.bottom + 4), T.BRASS, right=True)


def _b_languages(s, F, r, ch, d, ed, mouse, tip):
    y = section(s, F, "languages", r.x, r.y, r.w)
    text(s, F["body"], ", ".join(ch["langs"]) or "none", (r.x, y), T.TX_MUTED)
    if ch["recipes"]:
        y += 20
        caps(s, F["micro"], "recipes", (r.x, y), T.TX_FAINT)
        text(s, F["body_sm"], ", ".join(ch["recipes"]), (r.x + T.S * 9, y - 1), T.TX_MUTED)


def _b_ability(s, F, r, ch, d, ed, mouse, tip):
    nm, desc = ch["ability"]
    y = section(s, F, "racial ability", r.x, r.y, r.w)
    box = pygame.Rect(r.x, y, r.w, r.bottom - y)
    pygame.draw.rect(s, T.TABLE, box)
    pygame.draw.rect(s, T.STEEL_LINE, box, 1)
    text(s, F["bodyb"], nm, (box.x + T.S, box.y + T.S - 2), T.BRASS)
    ly = box.y + T.S * 3
    for ln in wrap(F["micro"], desc, box.w - T.S * 2):
        if ly > box.bottom - 12:
            break
        text(s, F["micro"], ln, (box.x + T.S, ly), T.TX_FAINT)
        ly += T.S * 2


_PAINT = {"identity": _b_identity, "status": _b_status, "vitals": _b_vitals,
         "attributes": _b_attributes, "weapon": _b_weapon, "gear": _b_gear,
         "languages": _b_languages, "ability": _b_ability}


# ---------------------------------------------------------------- api
def draw_sheet(surf, F, rect, ch, density="normal", editable=False, only=None, mouse=None):
    """Draws the sheet's blocks top-down from `rect.y`, clipped to `rect`
    so a height mismatch crops instead of spilling. Returns `(height
    consumed, tooltip)` -- `tooltip` is `None` or a `format_tooltip`-shaped
    list the caller passes straight to `draw_tooltip`."""
    blocks = [b for b in BLOCKS[density] if only is None or b in only]
    tip = []
    with contained(surf, pygame.Rect(rect.x, rect.y, rect.w, max(rect.h, sheet_height(density, only) + 4))):
        y = rect.y
        for i, b in enumerate(blocks):
            h = H[density][b]
            r = pygame.Rect(rect.x, y, rect.w, h)
            _PAINT[b](surf, F, r, ch, density, editable, mouse, tip)
            y += h + (GAP[density] if i < len(blocks) - 1 else 0)
    return y - rect.y, (tip[-1] if tip else None)


def draw_row(surf, F, rect, ch, selected=False, tag=None):
    """The list-row form: guild list / band rail. Fixed HP/AC/load
    trailing stat -- screens whose one extra fact isn't HP/AC/load (Hunt's
    rations, Crafting's recipe count, ...) keep their own one-liner for now,
    see `character_sheet_audit/README.md`."""
    pygame.draw.rect(surf, T.STEEL_HI if selected else T.STEEL, rect)
    pygame.draw.rect(surf, T.BRASS if selected else T.STEEL_LINE, rect, 1)
    cx = rect.x + T.S * 3
    token_badge(surf, F, (cx, rect.centery), ch["unit"], r=T.S * 2)
    text(surf, F["name"], ch["name"], (rect.x + T.S * 6, rect.centery - 16), T.TX)
    caps(surf, F["micro"], f"{ch['race']} · {ch['occ']}",
         (rect.x + T.S * 6, rect.centery + 4), T.TX_FAINT)
    cur, _mx = ch["hp"]
    caps(surf, F["micro"], f"hp {cur}   ac {ch['ac']}   {ch['gear']['load'][0]:g} kg",
         (rect.right - T.S * 2, rect.centery - 14), T.TX_MUTED, right=True)
    if ch["status"]:
        caps(surf, F["micro"], ch["status"][0], (rect.right - T.S * 2, rect.centery + 2),
             T.BLOOD, right=True)
    if tag:
        label_w = F["micro"].size(f"{ch['race']} · {ch['occ']}".upper())[0]
        caps(surf, F["micro"], tag, (rect.x + T.S * 6 + label_w + T.S * 2, rect.centery + 4),
             T.BRASS)
