"""The full character sheet, drawn into a rect.

`draw_sheet(screen, rect, unit, fonts)` renders everything the guild screen's
gear cards leave out: the six attributes with their modifiers, the derived
combat numbers, the actual to-hit and damage of the weapon in hand, carry,
languages and the racial ability in full. Read-only -- it is shown as a modal
over the guild screen (click a member to open, click anywhere to close).
"""

import pygame

from . import data
from .theme import (ACCENT, DANGER, DEMO_HL, INFO, INK, INK_DIM, INK_FAINT,
                    OK, SP1, SP2, SP3, SURFACE_1, SURFACE_2, WARN,
                    chip, panel, section, token_badge, text, wrap_lines)

PANEL_W, PANEL_H = 560, 604

_ATTRS = [("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
          ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma")]


def _to_hit(u):
    """Base attack bonus and the attribute it comes from -- no target, no
    flanking, no conditions (those are situational and shown in battle). A
    ranged weapon swung with no ammo left is a Strength melee attack."""
    if u.improvised:
        return u.mod_strength, "STR"
    return u.attack_bonus


def _weapon_lines(u):
    if u.unarmed:
        n, faces = u.unarmed_damage
        dmg = f"{n}d{faces} {u.mod_strength:+} (STR)"
        return "unarmed", dmg, "melee"
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


def _status_note(u):
    if u.dying:
        return f"DYING {u.death_clock}/{data.DYING_TURNS}", DANGER
    if u.stable:
        return "STABLE (unconscious)", WARN
    if u.broken:
        return "BROKEN (repair: INT vs 15)", WARN
    if u.fled:
        return "FLED THE FIGHT", INFO
    if u.dead:
        return "DEAD", DANGER
    if u.hunger_level:
        return u.hunger_label.upper(), (DANGER if u.hunger_level >= 2 else WARN)
    return None, None


def draw_sheet(screen, rect, u, f):
    veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 195))
    screen.blit(veil, (0, 0))

    panel(screen, rect, fill=SURFACE_2, border=ACCENT, width=2, radius=8)
    pad = 16
    x = rect.x + pad
    w = rect.w - 2 * pad
    y = rect.y + pad

    # --- header ---------------------------------------------------------- #
    tok = (x + 14, y + 14)
    token_badge(screen, tok, u, f, r=15)
    text(screen, u.name, f.heading, INK, (tok[0] + 26, y))
    text(screen, f"{u.race['name']}  ·  {u.occupation['name']}  ·  {u.alignment}",
         f.body_sm, INK_DIM, (tok[0] + 26, y + 18))
    text(screen, f"{u.size}  ·  {u.age} yrs  ·  combat N{u.combat_level}"
         + (f"  ·  work N{u.work_level}" if u.work_xp or u.work_level else "")
         + (f"  ·  takes {u.footprint}x{u.footprint}" if u.footprint > 1 else ""),
         f.body_sm, INK_FAINT, (tok[0] + 26, y + 33))
    note, ncol = _status_note(u)
    if note:
        text(screen, note, f.label, ncol, (rect.right - pad, y), right=True)
    y += 52

    # --- derived combat chips ------------------------------------------- #
    stats = (("HP", f"{max(u.hp, 0)}/{u.hp_max}" if u.hp != u.hp_max else u.hp_max, OK),
             ("AC", u.ac, INFO), ("MD", u.mental_defense, DEMO_HL),
             ("SPD", u.speed, INFO), ("INIT", f"{u.initiative_bonus():+}", WARN))
    cg = SP1
    cw = (w - (len(stats) - 1) * cg) // len(stats)
    for i, (k, v, ac) in enumerate(stats):
        chip(screen, pygame.Rect(x + i * (cw + cg), y, cw, 44), k, v, f, accent=ac)
    y += 44 + SP3

    # --- attributes ---------------------------------------------------- #
    y = section(screen, "ATTRIBUTES", x, y, w, f)
    aw = w // 6
    for i, (k, name) in enumerate(_ATTRS):
        val = getattr(u, name)
        m = getattr(u, f"mod_{name}")
        acx = x + i * aw + aw // 2
        cell = pygame.Rect(x + i * aw + 1, y, aw - 2, 48)
        pygame.draw.rect(screen, SURFACE_1, cell, border_radius=4)
        text(screen, k, f.label, INK_FAINT, (acx, y + 5), center=True)
        text(screen, f"{val}", f.num, INK, (acx, y + 20), center=True)
        mc = OK if m > 0 else DANGER if m < 0 else INK_FAINT
        text(screen, f"{m:+}", f.body_sm, mc, (acx, y + 38), center=True)
    y += 48 + SP1
    if u.hunger_level:
        cap = ", max HP 1" if u.hunger_level >= 2 else ""
        text(screen, f"hunger ({u.hunger_label}): {u.hunger_attribute_penalty} to every "
             f"attribute{cap}", f.body_sm, DANGER, (x, y))
        y += 14
    y += SP2

    # --- weapon: to-hit + damage ------------------------------------- #
    y = section(screen, "ATTACK WITH THE WEAPON IN HAND", x, y, w, f)
    wname, dmg, reach = _weapon_lines(u)
    bab, src = _to_hit(u)
    text(screen, wname, f.body_bd, INK, (x, y))
    y += 17
    text(screen, f"to hit:  d20 {bab:+} ({src})   ·   crit 20, fumble 1",
         f.mono_sm, INK_DIM, (x, y))
    y += 15
    text(screen, f"damage:  {dmg}   ·   {reach}", f.mono_sm, INK_DIM, (x, y))
    y += 15
    if data.FIRST_AID_ITEM in u.inventory:
        text(screen, f"first aid:  d20 {u.mod_wisdom:+} (WIS) vs 10   "
             f"·   {u.first_aid_charges} charges", f.mono_sm, INFO, (x, y))
        y += 15
    y += SP2

    # --- kit / carry ------------------------------------------------- #
    y = section(screen, "GEAR", x, y, w, f)
    held = " + ".join(p for p in ("weapon" if u.weapon_hand else "",
                                  "torch" if u.torch_hand else "") if p) or "hands free"
    text(screen, f"hands: {held}", f.body_sm, INK_DIM, (x, y))
    y += 16
    a = u.armor
    if a:
        arm = (f"{u.armor_name}  ·  +{a['ac']} AC"
               + (f"  ·  max DES +{a['max_dex']}" if a["max_dex"] is not None else "")
               + (f"  ·  -{a['speed']} speed" if a["speed"] else ""))
    else:
        arm = "(none)"
    text(screen, f"armor: {arm}", f.body_sm, INK_DIM, (x, y))
    y += 16
    inv = ", ".join(u.inventory) if u.inventory else "(empty)"
    for ln in wrap_lines([f"pack: {inv}"], f.body_sm, w):
        text(screen, ln, f.body_sm, INK_DIM, (x, y))
        y += 16
    over_n = u.encumbered
    over_m = u.load > u.carry_max
    ccol = DANGER if over_m else WARN if over_n else OK
    text(screen, f"load: {u.load:g} / normal {u.carry_normal:g} / high {u.carry_max:g}"
         + (f" (carrier +{u.carry_relief:g})" if u.carry_relief else "")
         + ("  OVERLOADED" if over_n and not over_m else
            "  OVER HIGH LOAD" if over_m else ""),
         f.mono_sm, ccol, (x, y))
    y += 16
    if u.encumbered:
        text(screen, "overloaded: -2 FOR, -2 DES, -1 speed",
             f.body_sm, WARN, (x, y))
        y += 15
    text(screen, f"copper: {u.gold}", f.mono_sm, ACCENT, (x, y))
    y += SP3

    # --- languages + ability --------------------------------------- #
    y = section(screen, "LANGUAGES", x, y, w, f)
    text(screen, ", ".join(u.languages), f.body_sm, INK, (x, y))
    y += 20

    y = section(screen, "RACIAL ABILITY", x, y, w, f)
    text(screen, u.ability.name, f.body_bd, INFO, (x, y))
    y += 17
    for ln in wrap_lines([u.ability.effect], f.body_sm, w):
        text(screen, ln, f.body_sm, INK_DIM, (x, y))
        y += 15

    text(screen, "click anywhere to close", f.body_sm, INK_FAINT,
         (rect.centerx, rect.bottom - 18), center=True)
