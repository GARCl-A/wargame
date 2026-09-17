"""The full character sheet, drawn as a modal over whichever screen opens it.

The actual rendering lives in `gartok.ui.sheet_card` (density="full") now --
this module keeps the `SheetModalMixin` mixin's public API (`open_sheet`,
`sheet_open`, `close_sheet_on_click`, `sheet_badge`, `draw_sheet_modal`)
stable for its six still-legacy consumers (group_screen, guild_screen,
level_screen, market_screen, reward_screen, squad_screen), plus a few pure
helpers (`_to_hit`, `_weapon_lines`, `format_hp_breakdown_tooltip`) those
same screens (and draft_screen, char_editor_screen, level_screen) still
import directly for their own bespoke cards. Those helpers stay on the
legacy `theme` palette/fonts since their callers haven't migrated yet.
"""

import pygame

from .combatant import Combatant
from .theme import ACCENT, DANGER, INFO, INK, INK_DIM, OK, WARN, wrap_lines
from .ui import primitives
from .ui.sheet_card import draw_sheet as _draw_sheet_card
from .ui.sheet_card import sheet_height, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

PANEL_W = 620
PANEL_H = sheet_height("full") + 96


# ---------------------------------------------------------------- mixin
class SheetModalMixin:
    """Lets a screen pop the full character sheet over itself. The sheet needs a
    `Combatant` view (to-hit, ammo, hand state), so a roster member is wrapped in
    a throwaway one -- fresh, so it reads "full HP, standing".

    A screen mixes this in, calls `open_sheet(unit)` from its own card hit, guards
    its click handler with `if self.close_sheet_on_click(): return` and ends its
    `draw` with `self.draw_sheet_modal(surface, fonts)`.
    """

    _sheet_unit = None

    def open_sheet(self, unit):
        self._sheet_unit = unit

    @property
    def sheet_open(self):
        return self._sheet_unit is not None

    def close_sheet_on_click(self):
        """True (and closes the sheet) if a modal was up -- the click is spent on
        dismissing it and the screen should do nothing else with it."""
        if self._sheet_unit is None:
            return False
        self._sheet_unit = None
        return True

    def sheet_badge(self, screen, topright, fonts=None):
        """Draw a small 'i' disc at `topright` (the card's inspect affordance) and
        return its rect for the screen to hit-test. `fonts` is accepted for the
        callers' existing call shape but unused -- this always draws in the
        war-table palette regardless of the host screen's own font system."""
        F = ui_fonts()
        r = pygame.Rect(0, 0, 20, 20)
        r.topright = topright
        hot = r.collidepoint(self.mouse)
        pygame.draw.circle(screen, T.STEEL_HI, r.center, 9)
        pygame.draw.circle(screen, T.BRASS if hot else T.STEEL_LINE, r.center, 9, 1)
        primitives.text(screen, F["bodyb"], "i", r.center, T.BRASS if hot else T.TX_MUTED,
                        center=True)
        return r

    def draw_sheet_modal(self, screen, fonts=None):
        if self._sheet_unit is None:
            return
        F = ui_fonts()
        ch = unit_to_ch(Combatant(self._sheet_unit))
        rect = primitives.modal_card(screen, (PANEL_W, PANEL_H), veil=True)
        pad = T.S * 2
        inner = pygame.Rect(rect.x + pad, rect.y + pad, rect.w - 2 * pad, 0)
        _, tooltip = _draw_sheet_card(screen, F, inner, ch, density="full", mouse=self.mouse)
        primitives.text(screen, F["micro"], "click anywhere to close",
                        (rect.centerx, rect.bottom - 18), T.TX_FAINT, center=True)
        if tooltip:
            primitives.draw_tooltip(screen, F, tooltip, self.mouse)


def draw_sheet(screen, rect, u, fonts=None, mouse=None):
    """Legacy entry point -- draws the same modal content at an arbitrary
    rect instead of through `SheetModalMixin`. Kept for direct callers
    (tests included); `fonts` is unused, drawing is always war-table style."""
    F = ui_fonts()
    ch = unit_to_ch(u if isinstance(u, Combatant) else Combatant(u))
    _, tooltip = _draw_sheet_card(screen, F, pygame.Rect(rect.x, rect.y, rect.w, 0),
                                  ch, density="full", mouse=mouse)
    if tooltip and mouse:
        primitives.draw_tooltip(screen, F, tooltip, mouse)


# ---------------------------------------------------------------- shared helpers
# Still legacy-styled (theme fonts/colors) -- kept for guild_screen.py (`_weapon_
# lines`/`_to_hit`) and char_editor_screen.py/draft_screen.py/level_screen.py
# (`format_hp_breakdown_tooltip`), none of which are migrating in this pass.
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


def format_hp_breakdown_tooltip(u, fonts, max_px=320):
    """Formats a structured tooltip detailing how the unit's max HP is calculated."""
    b = u.hp_breakdown()
    lines = [("HIT POINTS (HP)", fonts.label, ACCENT)]

    hd = b["hd"]
    dice_cnt = b["hit_dice"]
    die_word = "Hit Die" if dice_cnt == 1 else "Hit Dice"
    lines.append((f"Base die: 1d{hd} ({dice_cnt} {die_word})", fonts.body_sm, INK))

    roll_items = [f"Base (L0): {b['base_roll']}"]
    for lvl, r in enumerate(b["level_rolls"], start=1):
        roll_items.append(f"L{lvl}: {r}")
    rolls_line = " · ".join(roll_items)
    for ln in wrap_lines([f"Rolls: {rolls_line}"], fonts.mono_sm, max_px):
        lines.append((ln, fonts.mono_sm, INK_DIM))
    lines.append((f"Dice sum: {b['dice_sum']}", fonts.mono_sm, INK_DIM))

    lines.append(("Bonuses:", fonts.label, INFO))
    con_sign = f"{b['con_mod']:+}"
    con_col = OK if b["con_total"] > 0 else (DANGER if b["con_total"] < 0 else INK_DIM)
    lines.append((f"• CON mod: {con_sign} × {dice_cnt} HD = {b['con_total']:+}", fonts.mono_sm, con_col))

    if b["talent_total"]:
        lines.append((f"• Hardy talent: +{b['talent_per_hd']} × {dice_cnt} HD = +{b['talent_total']}", fonts.mono_sm, OK))
    if b["ability_bonus"]:
        lines.append((f"• {b['ability_name']}: +{b['ability_bonus']}", fonts.mono_sm, OK))

    parts = [f"{b['dice_sum']} (dice)"]
    if b["con_total"] >= 0:
        parts.append(f"+ {b['con_total']} (CON)")
    else:
        parts.append(f"- {abs(b['con_total'])} (CON)")
    if b["talent_total"]:
        parts.append(f"+ {b['talent_total']} (talents)")
    if b["ability_bonus"]:
        parts.append(f"+ {b['ability_bonus']} (ability)")
    calc_eq = f"Calc: {' '.join(parts)} = {b['raw_total']}"
    for ln in wrap_lines([calc_eq], fonts.mono_sm, max_px):
        lines.append((ln, fonts.mono_sm, INK))

    if b["override"] is not None:
        lines.append((f"Manual override: {b['override']}", fonts.body_sm, WARN))
    if b["starving"]:
        lines.append(("Starving: capped at 1 HP", fonts.body_sm, DANGER))
    elif b["min_floor"]:
        lines.append(("Minimum HP floor: 1", fonts.body_sm, WARN))

    lines.append((f"Max HP: {b['final_max']}", fonts.body_bd, ACCENT))
    return lines
