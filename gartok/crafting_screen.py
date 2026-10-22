"""The Forge: craft items using recipes and materials.

Requires members to have learned recipes.
Materials come from the whole group's packs, wagons and animals (padlocked items excepted) and are consumed immediately.
Progress requires rolling a 1d20+INT over hours.
"""

from collections import Counter

import pygame

from . import items, progression, solo
from .item_icon import draw_icon
from .screen import Screen
from .ui import hub_body as hb
from .ui.hub_frame import hub_button
from .ui.primitives import ellipsize, footer_bar, scrollbar, text
from .ui.tokens import T, mix
from .ui.tokens import fonts as ui_fonts
from .ui.vendor_panel import draw_vendor, draw_vendor_name
from .unit_loadout import pooled_unlocked

CARD_H = T.S * 13

class CraftingScreen(Screen):
    native = True
    framed = False          # a hub's tab: the hub draws the keeper, the tabs and the back

    def hub_cards(self):
        known = {r for u in self.crafters for r in u.known_recipes if self._for_station(r)}
        return [{"label": "crafters", "value": f"{len(self.crafters)} of {len(self.group.members)}"},
                {"label": "recipes known", "value": str(len(known))}]

    def _for_station(self, recipe):
        """Is `recipe` worked at this screen's station (any station when it has none)?"""
        found = items.CRAFTING_RECIPES.get(recipe)
        variants = found if isinstance(found, list) else [found] if found else []
        return not self.station or any(rc.station == self.station for rc in variants)

    def tutorial_key(self):
        return "craft"

    def __init__(self, fonts, guild, group, on_done, title="THE FORGE",
                 subtitle="forge weapons and armor  ·  needs recipes and materials",
                 station="forge", vendor=None):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.title = title
        self.subtitle = subtitle
        self.station = station
        self.vendor = vendor
        
        self.crafters = [u for u in group.members if any(self._for_station(r) for r in u.known_recipes)]
        self.selected_crafter = self.crafters[0] if self.crafters else None

        self.buttons = []         # [(key, rect)]
        self._hot = False
        self.roster_rows = []     # [(rect, member)]
        self.notices = []
        self.scroll = self.max_scroll = 0
        self.roster_area = pygame.Rect(0, 0, 0, 0)
        self.roster_scroll = self.roster_max = 0

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False, danger=False):
        hub_button(surf, self._F, rect, label, primary=primary, enabled=enabled, mpos=self.mouse)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    def handle_escape(self):
        return False

    @property
    def _packs(self):
        return [*self.group.members, *self.group.stores]

    def _get_missing_materials(self, recipe):
        recipe_data = items.get_recipe(recipe)
        if not recipe_data:
            return []
        need = Counter(recipe_data.materials)
        missing = []
        for mat, qty in need.items():
            have = pooled_unlocked(self._packs, mat)
            if have < qty:
                missing.append(f"{qty - have}x {mat}")
        return missing

    def _get_missing_tools(self, recipe):
        recipe_data = items.get_recipe(recipe)
        return items.missing_tools(recipe_data, self._packs) if recipe_data else []

    def _has_materials(self, recipe):
        return not self._get_missing_materials(recipe) and not self._get_missing_tools(recipe)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL and self.roster_area.collidepoint(self.mouse):
            self.roster_scroll = max(0, min(self.roster_max, self.roster_scroll - event.y * T.S * 4))
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self.max_scroll, self.scroll - event.y))
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        px = event.pos
        
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "done":
                    self.on_done()
                elif key.startswith("alone:"):
                    parts = key.split(":", 2)
                    hours = parts[1]
                    recipe = parts[2]
                    ok, lines = solo.craft(self.guild, self.group, self.selected_crafter, recipe, int(hours))
                    if ok:
                        self.on_done()
                    self.notices = lines
                elif key.startswith("work:"):
                    parts = key.split(":", 2)
                    hours = int(parts[1])
                    recipe = parts[2]
                    result = self.guild.crafting_shift(self.selected_crafter, recipe, hours,
                                                      pool=self._packs)
                    self.notices = result[0] if isinstance(result, tuple) else result
                return

        for rect, m in self.roster_rows:
            if rect.collidepoint(px):
                self.selected_crafter = m
                self.notices = []
                self.scroll = 0
                return

    def _recipes(self, m):
        """`(recipe_id, data, active)` for each recipe `m` works at this station."""
        out = []
        for r_name in m.known_recipes:
            found = items.CRAFTING_RECIPES.get(r_name, [])
            variants = found if isinstance(found, (list, tuple)) else [found] if found else []
            for i, r_data in enumerate(variants):
                if not r_data or (self.station and r_data.station != self.station):
                    continue
                recipe_id = f"{r_name}:{i}" if len(variants) > 1 else r_name
                active = m.crafting_target == recipe_id or (len(variants) == 1 and m.crafting_target == r_name)
                out.append((recipe_id, r_data, active))
        return out

    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._reset_buttons()
        self.roster_rows = []

        if self.framed:
            top, bottom = 0, H - T.S * 4 - T.S * 3 * len(self.notices)
        else:
            m = T.S * 3
            card = self.vendor.card if self.vendor else None
            tx = m + draw_vendor(screen, F, (m, m - 4), card, size=T.S * 7)
            title = text(screen, F["titleb"], self.title, (tx, m - 2), T.TX)
            draw_vendor_name(screen, F, (title.right + T.S * 2, title.y + 10), card)
            text(screen, F["body"], self.subtitle, (tx, m + 30), T.TX_MUTED)
            top, bottom = m + 62, H - 72 - T.S * 3 * len(self.notices)
        body = pygame.Rect(T.S * 5, top, W - T.S * 10, bottom - top)
        side_w = max(T.S * 44, min(T.S * 56, round(body.w * 0.28)))
        self._draw_roster(screen, pygame.Rect(body.x, body.y, side_w, body.h))
        self._draw_crafting(screen, pygame.Rect(body.x + side_w + T.S * 3, body.y, body.w - side_w - T.S * 3, body.h))
        self._draw_footer(screen)

    def _draw_roster(self, screen, area):
        F = self._F
        inner = hb.draw_panel(screen, F, area, "Crafters", "pick who works")
        n = max(1, len(self.crafters))
        row_h = max(hb.PERSON_H, min(hb.PERSON_H + T.S * 3, (inner.h + T.S) // n - T.S))
        content_h = n * (row_h + T.S) - T.S
        self.roster_area, self.roster_max = inner, max(0, content_h - inner.h)
        self.roster_scroll = min(self.roster_scroll, self.roster_max)
        view = inner.inflate(T.S * 2, 0)
        clip = screen.get_clip()
        screen.set_clip(view.clip(clip))
        y = inner.y - self.roster_scroll
        for m in self.crafters:
            r = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2 - (T.S if self.roster_max else 0), row_h)
            y += r.h + T.S
            seen = r.clip(view)
            if not seen.h:
                continue
            count = len(self._recipes(m))
            mod = m.mod_intelligence + m.craft_bonus(self.station)
            hb.draw_person(screen, F, r, {
                "face": {"race": m.race["name"], "portrait_id": getattr(m, "portrait_id", None), "token": m.token},
                "name": m.name, "state": "on" if m is self.selected_crafter else None,
                "sub": f"{m.occupation['name']}  ·  d20{mod:+d}  ·  {count} recipe{'s' if count != 1 else ''}",
                "note": f"working on {m.crafting_target.split(':')[0]}" if m.crafting_target else None},
                self.mouse)
            self._hot = self._hot or seen.collidepoint(self.mouse)
            self.roster_rows.append((seen, m))
        screen.set_clip(clip)
        if self.roster_max:
            scrollbar(screen, view, self.roster_scroll, self.roster_max, content_h)
        if not self.crafters:
            y = inner.y
            for line in ("No one in the party knows a recipe", "for this station."):
                text(screen, F["hub_body"], line, (inner.x, y), T.TX_FAINT)
                y += F["hub_body"].get_linesize()

    def _draw_crafting(self, screen, area):
        F = self._F
        m = self.selected_crafter
        inner = hb.draw_panel(screen, F, area, "Recipes",
                              f"{m.name}'s, from the group's packs" if m else None)
        if not m:
            text(screen, F["hub_body"], "No known recipes for this station yet.", (inner.x, inner.y), T.TX)
            text(screen, F["hub_sub"], "Recipes come from Work talent picks on the Guild screen, "
                 "or from a starting occupation.", (inner.x, inner.y + T.S * 3 + 4), T.TX_MUTED)
            return
        recipes = self._recipes(m)
        fit = max(1, (inner.h + T.S) // (CARD_H + T.S))
        self.max_scroll = max(0, len(recipes) - fit)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        y = inner.y
        for recipe_id, r_data, active in recipes[self.scroll:self.scroll + fit]:
            self._draw_recipe(screen, pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, CARD_H), m, recipe_id,
                              r_data, active)
            y += CARD_H + T.S
        if self.max_scroll:
            text(screen, F["hub_sub"], f"{self.scroll + 1}-{self.scroll + fit} of {len(recipes)}  ·  scroll for more",
                 (inner.right, area.bottom - T.S * 3), T.TX_FAINT, right=True)

    def _draw_recipe(self, screen, r, m, recipe_id, r_data, active):
        F = self._F
        pygame.draw.rect(screen, mix(T.STEEL, T.BRASS, 0.07) if active else mix(T.STEEL, T.TABLE, 0.35), r,
                         border_radius=6)
        if active:
            pygame.draw.rect(screen, T.BRASS_DIM, r, 1, border_radius=6)
        icon = pygame.Rect(r.x + T.S * 2, r.y + T.S * 2, T.S * 7, T.S * 7)
        draw_icon(screen, icon, r_data.target)
        x = icon.right + T.S * 2
        buttons_w = T.S * 42
        right = r.right - buttons_w - T.S * 3

        name = text(screen, F["hub_row"], r_data.target, (x, r.y + T.S + 6), T.TX)
        xp_mult = progression.work_xp_hours(1, r_data.level, m.work_level)
        chips = [(f"level {r_data.level}", "money"), (f"×{xp_mult} work XP" if xp_mult else "no work XP", "muted")]
        if r_data.yield_qty > 1:
            chips.append((f"makes {r_data.yield_qty}", "good"))
        cx = name.right + T.S * 2
        for label, tone in chips:
            cx = hb.draw_chip(screen, F, (cx, name.centery), label, tone, anchor="midleft").right + T.S

        y = r.y + T.S * 5
        lab = hb.draw_section(screen, F, (x, y + 3), "Uses")
        end = hb.draw_items(screen, F, (lab.right + T.S * 2, y), r_data.materials, T.TX, right)
        if r_data.tools:
            lab = hb.draw_section(screen, F, (end + T.S * 3, y + 3), "Tools")
            hb.draw_items(screen, F, (lab.right + T.S * 2, y), r_data.tools, T.TX, right)

        y = r.y + T.S * 9
        goal = m.crafting_goal(r_data)
        mod = m.mod_intelligence + m.craft_bonus(r_data.station)
        if active:
            bar = pygame.Rect(x, y + T.S, min(T.S * 30, right - x - T.S * 16), 6)
            hb.draw_bar(screen, bar, m.crafting_progress / max(1, goal))
            text(screen, F["hub_body"], f"{m.crafting_progress} / {goal} progress", (bar.right + T.S * 2, y), T.BRASS)
        else:
            line = text(screen, F["hub_body"], f"needs {goal} progress  ·  rolls d20{mod:+d} an hour", (x, y),
                        T.TX_MUTED)
            lacking = self._get_missing_materials(recipe_id) + [f"a {t}" for t in self._get_missing_tools(recipe_id)]
            if lacking:
                text(screen, F["hub_bodyb"], ellipsize("missing " + ", ".join(lacking), F["hub_bodyb"],
                                                       right - line.right - T.S * 2),
                     (line.right + T.S * 2, y), T.BLOOD)

        bx0 = r.right - T.S * 2 - buttons_w
        if not (active or self._has_materials(recipe_id)):
            text(screen, F["hub_sub"], "the materials must be with the group (packs, wagons, animals) to start",
                 (r.right - T.S * 2, r.centery - T.S), T.TX_FAINT, right=True)
            return
        if len(self.group.members) > 1 and not self.guild.free_slots:
            alone_no = "no free group slot"
        elif self.guild.craft_blocker(m, recipe_id, [m]) is not None:
            alone_no = "not in their own pack"
        else:
            alone_no = None
        bw, bh = (buttons_w - T.S * 12) // 3, T.S * 4 + 4
        rows = (("Group waits", "work", (1, 4, 8), None), ("Alone", "alone", (4, 8, 16), alone_no))
        for row, (label, kind, hours, no) in enumerate(rows):
            by = r.y + T.S * 2 + row * (bh + T.S * 2)
            mid = by + (bh - F["hub_sub"].get_height()) // 2
            text(screen, F["hub_sub"], label, (bx0, mid), T.TX_FAINT if no else T.TX_MUTED)
            if no:
                text(screen, F["hub_sub"], ellipsize(no, F["hub_sub"], buttons_w - T.S * 12),
                     (bx0 + T.S * 12, mid), T.TX_FAINT)
                continue
            for i, h in enumerate(hours):
                b = pygame.Rect(bx0 + T.S * 12 + i * (bw + T.S), by, bw, bh)
                self.add_button(screen, b, f"{kind}:{h}:{recipe_id}", f"{h} h")

    def _draw_footer(self, screen):
        F = self._F
        H = screen.get_height()
        ny = H - (T.S * 3 if self.framed else 72) - T.S * 3 * (len(self.notices) - 1)
        for notice in self.notices:
            text(screen, F["hub_body"], notice, (T.S * 5, ny), T.BRASS)
            ny += T.S * 3
        if not self.framed:
            footer_bar(self, screen, F, primary=("done", f"LEAVE {self.title}"))
