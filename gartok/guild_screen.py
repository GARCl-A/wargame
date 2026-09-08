"""Guild screen: the roster-and-gear view between outings.

Today the guild is just its members. A weapon is an item: it can sit in a
member's pack or be held in a hand. Each doll has two hand slots -- the weapon
hand (a weapon, 1 or 2 handed) and the off hand (a torch, for now). Click an
item (a hand slot or a pack row), then click where it goes: a HAND, the OFF
HAND, or the PACK. Moving works within one doll too (equip from the pack / stow
what's held).

The transfer edits the persistent `equipped_weapon` / `equipped_offhand` /
`_base_inventory`, which every battle re-seeds a `Combatant` from -- so the next
fight starts with the new loadout (which weapon is drawn, torch lit, ammo, kit).
`Unit.load` / `.ac` / ... read straight off that loadout, so the cards stay
truthful with no extra bookkeeping; the full-sheet modal wraps the member in a
throwaway `Combatant` for the in-fight numbers.

Reached from the map (opening it passes no time). `on_back()` returns to the
map; `on_menu()` to the slot menu.
"""

import pygame

from . import data, world
from .combatant import Combatant
from .screen import Screen
from .sheet_panel import PANEL_H, PANEL_W, draw_sheet
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4, SURFACE_1,
                    SURFACE_2, SURFACE_3, SURFACE_4, WARN, WIN_H, WIN_W,
                    panel, section, token_badge, text, tracked)


TABS = (("membros", "MEMBROS"), ("reputacoes", "REPUTACOES"))


def _kg(w):
    return f"{w:g} kg"


class GuildScreen(Screen):
    def __init__(self, fonts, guild, on_back, on_menu):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_menu = on_menu
        self.tab = "membros"                  # "membros" (roster+gear) | "reputacoes"
        self.tab_hits = []                  # [(rect, key)]
        self.selected = None                 # (unit, loc): loc is "hand" | "offhand" | pack index
        self.detail = None                   # unit whose full sheet is open (modal), or None
        self.zones = []                     # [(rect, unit, "hand"|"offhand"|"pack")]
        self.sources = []                  # [(rect, unit, loc)]
        self.info_hits = []                # [(rect, unit)] -- card headers open the sheet
        self.buttons = []                  # [(key, rect)]

    # ------------------------------------------------------------------ #
    def _recruited_by(self, unit):
        """Name of the member who recruited `unit`, or None (draft member, or the
        recruiter has since been lost)."""
        if not getattr(unit, "recruited_by", None):
            return None
        who = next((u for u in self.roster if u.uid == unit.recruited_by), None)
        return who.name if who else "alguem que ja se foi"

    @staticmethod
    def _slot_of(loc):
        return loc if isinstance(loc, str) else "pack"

    def _item_at(self, unit, loc):
        if loc == "hand":
            return unit.equipped_weapon
        if loc == "offhand":
            return unit.equipped_offhand
        if loc == "armor":
            return unit.equipped_armor
        return unit._base_inventory[loc] if loc < len(unit._base_inventory) else None

    def _carried(self):
        if self.selected is None:
            return None
        return self._item_at(*self.selected)

    # ------------------------------------------------------------------ #
    def _click(self, px):
        if self.detail is not None:            # sheet modal: any click closes it
            self.detail = None
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                (self.on_back if key == "back" else self.on_menu)()
                return

        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab = key
                return

        if self.selected is None:
            for rect, unit in self.info_hits:
                if rect.collidepoint(px):
                    self.detail = unit
                    return
            for rect, unit, loc in self.sources:
                if rect.collidepoint(px):
                    self.selected = (unit, loc)
                    return
            return

        for rect, unit, zone in self.zones:
            if rect.collidepoint(px):
                self._give(unit, zone)
                return
        self.selected = None

    def _take(self, src, loc):
        if loc == "hand":
            return src.take_from_hand()
        if loc == "offhand":
            return src.take_from_offhand()
        if loc == "armor":
            return src.take_from_armor()
        return src.take_from_pack(loc)

    def _give(self, dst, zone):
        src, loc = self.selected
        self.selected = None
        name = self._item_at(src, loc)
        if name is None:
            return
        if zone == "discard":
            self._take(src, loc)
            return
        if src is dst and self._slot_of(loc) == zone:
            return                                       # dropped back where it was
        if (zone == "hand" and not dst.is_weapon(name)) or \
           (zone == "offhand" and not dst.fits_offhand(name)) or \
           (zone == "armor" and not dst.fits_armor(name)):
            self.selected = (src, loc)                    # wrong slot: keep carrying it
            return

        self._take(src, loc)

        if zone == "hand":
            dst.give_to_hand(name)
        elif zone == "offhand":
            dst.give_to_offhand(name)
        elif zone == "armor":
            dst.give_to_armor(name)
        else:
            dst.give_to_pack(name)

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        f = self.fonts
        screen.fill((18, 19, 24))
        self.zones = []
        self.sources = []
        self.info_hits = []
        self.buttons = []

        text(screen, "GUILDA", f.title, INK, (MARGIN, MARGIN - 2))
        carried = self._carried()
        if carried is not None:
            sub, col = (f"movendo  {carried} ({_kg(data.item_weight(carried))})  ·  "
                        "clique numa MAO, OUTRA MAO, CORPO, MOCHILA ou JOGAR FORA  ·  "
                        "clique fora para cancelar", ACCENT)
        else:
            sub, col = (f"{self.battles_won} vitorias  ·  {len(self.roster)} membros  ·  "
                        "clique num item para move-lo entre os bonecos", INK_DIM)
        text(screen, sub, f.body, col, (MARGIN, MARGIN + 30))

        self.tab_hits = []
        if carried is None:
            self._draw_tabs(screen)

        if carried is None and self.tab == "reputacoes":
            self._draw_reputacoes(screen)
        else:
            n = max(1, len(self.roster))
            gap = SP3
            top = MARGIN + 64
            card_h = WIN_H - top - 72
            card_w = (WIN_W - 2 * MARGIN - (n - 1) * gap) // n
            for i, unit in enumerate(self.roster):
                rect = pygame.Rect(MARGIN + i * (card_w + gap), top, card_w, card_h)
                self._draw_card(screen, rect, unit, carried)

        self._draw_footer(screen)

        if self.detail is not None:
            r = pygame.Rect(0, 0, PANEL_W, PANEL_H)
            r.center = (WIN_W // 2, WIN_H // 2)
            draw_sheet(screen, r, Combatant(self.detail), f)

    # ------------------------------------------------------------------ #
    def _draw_card(self, screen, rect, unit, carried):
        f = self.fonts
        pad = SP3
        mouse = self.mouse
        panel(screen, rect, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)

        head = pygame.Rect(rect.x, rect.y, rect.w, 46)
        head_hov = carried is None and head.collidepoint(mouse)
        pygame.draw.rect(screen, SURFACE_4 if head_hov else SURFACE_3, head,
                         border_top_left_radius=RADIUS, border_top_right_radius=RADIUS)
        tok = (rect.x + pad + 12, rect.y + 23)
        token_badge(screen, tok, unit.token, f)
        text(screen, unit.name, f.card_name, INK, (tok[0] + 24, rect.y + 6))
        origin = self._recruited_by(unit)
        text(screen, f"{unit.race['name']}  ·  {unit.occupation['name']}"
             + (f"  ·  recrutado por {origin}" if origin else ""), f.body_sm,
             INK_DIM, (tok[0] + 24, rect.y + 26))
        text(screen, "VER FICHA ›", f.label, ACCENT if head_hov else INK_FAINT,
             (rect.right - pad, rect.y + 6), right=True)
        if carried is None:
            self.info_hits.append((head, unit))

        y = head.bottom + SP3
        text(screen, f"PV {unit.hp_max}   CA {unit.ac}   DM {unit.mental_defense}   "
             f"Desloc {unit.speed}", f.mono_sm, INK_DIM, (rect.x + pad, y))
        y += 18

        # --- carry ------------------------------------------------- #
        over_norm = unit.load > unit.carry_normal
        over_max = unit.load > unit.carry_max
        ccol = DANGER if over_max else WARN if over_norm else OK
        text(screen, f"Carga {_kg(unit.load)} / {_kg(unit.carry_normal)}",
             f.mono_sm, ccol, (rect.x + pad, y))
        note = ("  ACIMA DA CARGA ALTA  -2 FOR/DES, -1 desloc" if over_max
                else "  sobrecarregado  -2 FOR/DES, -1 desloc" if over_norm else "")
        if note:
            text(screen, note, f.label, ccol, (rect.x + pad + 168, y + 1))
        y += 16
        text(screen, f"{unit.gold} cobre", f.mono_sm, ACCENT, (rect.x + pad, y))
        text(screen, f"{unit.combat_xp} XP de combate", f.mono_sm, INFO,
             (rect.right - pad, y), right=True)
        y += 20
        if unit.ability.id == "autotroph":
            text(screen, "fome: autotrofo (nao come)", f.mono_sm, INK_DIM,
                 (rect.x + pad, y - 4))
        elif unit.hunger_level:
            text(screen, f"fome: {unit.hunger_label}  ({unit.unfed_days}d sem comer)",
                 f.mono_sm, DANGER if unit.hunger_level >= 2 else WARN,
                 (rect.x + pad, y - 4))
        else:
            text(screen, "fome: saciado", f.mono_sm, OK, (rect.x + pad, y - 4))
        y += 14

        # --- hands: weapon hand + off hand ------------------------ #
        y = section(screen, "MAOS", rect.x + pad, y, rect.w - 2 * pad, f)
        two_handed = bool(unit.equipped_weapon) and \
            data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
        for kind in ("hand", "offhand"):
            hr = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 28)
            held = unit.equipped_weapon if kind == "hand" else unit.equipped_offhand
            blocked = kind == "offhand" and two_handed
            sel = self.selected == (unit, kind)
            accepts = carried is not None and not blocked and (
                (kind == "hand" and unit.is_weapon(carried))
                or (kind == "offhand" and unit.fits_offhand(carried)))
            drop = accepts and not sel and hr.collidepoint(mouse)
            panel(screen, hr, fill=ACCENT if sel else SURFACE_3 if drop else SURFACE_1,
                  border=ACCENT if (sel or drop) else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if sel else INK

            if held:
                right = ""
                if kind == "hand":
                    n, faces = data.WEAPONS[held]["damage"]
                    right = f"{n}d{faces}  ·  "
                text(screen, held, f.body_sm, ink, (hr.x + SP2, hr.y + 7))
                text(screen, right + _kg(data.item_weight(held)), f.mono_sm,
                     ACCENT_INK if sel else INK_DIM, (hr.right - SP2, hr.y + 8), right=True)
                self.sources.append((hr, unit, kind))
            elif blocked:
                text(screen, "outra mao  ·  ocupada pela arma de 2 maos", f.body_sm,
                     INK_FAINT, (hr.x + SP2, hr.y + 7))
            else:
                empty = "arma: nenhuma (luta no soco)" if kind == "hand" else "outra mao: livre"
                text(screen, empty, f.body_sm, ACCENT if drop else INK_FAINT,
                     (hr.x + SP2, hr.y + 7))

            if not blocked:
                self.zones.append((hr, unit, kind))
            y += 28 + SP1
        y += SP1

        # --- body: armor ----------------------------------------- #
        y = section(screen, "CORPO", rect.x + pad, y, rect.w - 2 * pad, f)
        ar = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 28)
        worn = unit.equipped_armor
        asel = self.selected == (unit, "armor")
        adrop = (carried is not None and unit.fits_armor(carried)
                 and not asel and ar.collidepoint(mouse))
        panel(screen, ar, fill=ACCENT if asel else SURFACE_3 if adrop else SURFACE_1,
              border=ACCENT if (asel or adrop) else LINE_SOFT, width=1, radius=4)
        if worn:
            armor = data.ARMOR[worn]
            text(screen, worn, f.body_sm, ACCENT_INK if asel else INK, (ar.x + SP2, ar.y + 7))
            text(screen, f"+{armor['ac']} CA  ·  {_kg(data.item_weight(worn))}", f.mono_sm,
                 ACCENT_INK if asel else INK_DIM, (ar.right - SP2, ar.y + 8), right=True)
            self.sources.append((ar, unit, "armor"))
        else:
            text(screen, "corpo: sem armadura", f.body_sm,
                 ACCENT if adrop else INK_FAINT, (ar.x + SP2, ar.y + 7))
        self.zones.append((ar, unit, "armor"))
        y += 28 + SP2

        # --- pack ------------------------------------------------- #
        y = section(screen, "MOCHILA", rect.x + pad, y, rect.w - 2 * pad, f)
        if not unit._base_inventory:
            text(screen, "(vazia)", f.body_sm, INK_FAINT, (rect.x + pad, y + 2))
            y += 20
        for idx, item in enumerate(unit._base_inventory):
            ir = pygame.Rect(rect.x + pad, y, rect.w - 2 * pad, 26)
            isel = self.selected == (unit, idx)
            ihov = carried is None and ir.collidepoint(mouse)
            panel(screen, ir, fill=ACCENT if isel else SURFACE_3 if ihov else SURFACE_1,
                  border=ACCENT if isel else LINE_SOFT, width=1, radius=4)
            ink = ACCENT_INK if isel else INK
            text(screen, item, f.body_sm, ink, (ir.x + SP2, ir.y + 6))
            text(screen, _kg(data.item_weight(item)), f.mono_sm,
                 ACCENT_INK if isel else INK_DIM, (ir.right - SP2, ir.y + 7), right=True)
            tag = self._item_tag(item)
            if tag:
                text(screen, tag, f.label, ACCENT_INK if isel else INFO,
                     (ir.right - SP2 - 52, ir.y + 7), right=True)
            self.sources.append((ir, unit, idx))
            y += 26 + SP1

        if carried is not None:
            br = pygame.Rect(rect.x + pad, y + SP1, rect.w - 2 * pad, 24)
            over = br.collidepoint(mouse)
            panel(screen, br, fill=SURFACE_3 if over else SURFACE_1,
                  border=ACCENT if over else LINE_SOFT, width=1, radius=4)
            text(screen, "guardar na mochila", f.label, ACCENT if over else INK_DIM,
                 (br.centerx, br.centery - 1), center=True)
            self.zones.append((br, unit, "pack"))

    def _item_tag(self, item):
        if item in data.WEAPONS:
            return "ARMA"
        if item in data.ARMOR:
            return "ARMADURA"
        if item == data.AMMO_ITEM:
            return "MUNICAO"
        if item == data.FIRST_AID_ITEM:
            return "CURA"
        if item == data.TORCH_ITEM or item in data.LIGHT_SOURCES:
            return "LUZ"
        if item in data.FOOD_ITEMS:
            return "COMIDA"
        return ""

    # ------------------------------------------------------------------ #
    def _draw_tabs(self, screen):
        """Right-aligned pill strip on the title row: MEMBROS | REPUTACOES."""
        f = self.fonts
        x = WIN_W - MARGIN
        for key, lbl in reversed(TABS):
            w = f.body_bd.size(lbl)[0] + 2 * SP3
            r = pygame.Rect(x - w, MARGIN - 4, w, 28)
            x = r.x - SP2
            active = self.tab == key
            hov = r.collidepoint(self.mouse)
            panel(screen, r, fill=SURFACE_3 if (active or hov) else SURFACE_1,
                  border=ACCENT if active else LINE_SOFT, width=2 if active else 1,
                  radius=RADIUS)
            text(screen, lbl, f.body_bd, ACCENT if active else INK_DIM,
                 r.center, center=True)
            self.tab_hits.append((r, key))

    def _draw_reputacoes(self, screen):
        """The REPUTACOES tab: where the guild stands with each faction. Only the
        arena keeps a tally today; the panel also shows what it unlocks."""
        f = self.fonts
        rep = self.guild.arena_reputation
        top = MARGIN + 72
        r = pygame.Rect(MARGIN, top, WIN_W - 2 * MARGIN, 280)
        panel(screen, r, fill=SURFACE_2, border=LINE_SOFT, width=2, radius=RADIUS)
        pad = SP4
        x, y = r.x + pad, r.y + pad

        tracked(screen, "ARENA", f.label, INFO, (x, y))
        y += 16
        text(screen, str(rep), f.num_lg, ACCENT, (x, y))
        text(screen, "de reputacao  ·  +1 a cada luta de arena vencida",
             f.body_sm, INK_DIM, (x + 52, y + 14))
        y += 46

        y = section(screen, "O QUE ISSO LIBERA", x, y, r.w - 2 * pad, f)
        for tier in world.ARENA_TIERS:
            unlocked = rep >= tier["rep"]
            text(screen, tier["name"], f.body, INK if unlocked else INK_DIM, (x, y))
            text(screen, f"entrada {tier['entry']}/cabeca  ·  bolsa {tier['purse']}  ·  "
                 f"{tier['enemies']} oponente(s)", f.body_sm, INK_DIM, (x + 200, y + 2))
            mark = "liberado" if unlocked else f"exige {tier['rep']} de reputacao"
            text(screen, mark, f.label, OK if unlocked else INK_FAINT,
                 (r.right - pad, y + 3), right=True)
            y += 26

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen):
        f = self.fonts
        mouse = self.mouse
        y = WIN_H - 56

        if self._carried() is not None:
            trash = pygame.Rect(0, 0, 220, 36)
            trash.center = (WIN_W // 2, y + 18)
            over = trash.collidepoint(mouse)
            panel(screen, trash, fill=DANGER if over else SURFACE_2,
                  border=DANGER, width=1, radius=RADIUS)
            text(screen, "JOGAR FORA", f.body_bd,
                 ACCENT_INK if over else DANGER, trash.center, center=True)
            self.zones.append((trash, None, "discard"))

        nxt = pygame.Rect(WIN_W - MARGIN - 220, y, 220, 36)
        hov = nxt.collidepoint(mouse)
        panel(screen, nxt, fill=ACCENT if hov else SURFACE_3, border=ACCENT, width=1, radius=RADIUS)
        text(screen, "VOLTAR AO MAPA", f.body_bd, ACCENT_INK if hov else ACCENT,
             nxt.center, center=True)
        self.buttons.append(("back", nxt))

        menu = pygame.Rect(MARGIN, y, 140, 36)
        hovm = menu.collidepoint(mouse)
        panel(screen, menu, fill=SURFACE_3 if hovm else SURFACE_2, border=LINE_SOFT,
              width=1, radius=RADIUS)
        text(screen, "menu", f.body, INK if hovm else INK_DIM, menu.center, center=True)
        self.buttons.append(("menu", menu))
