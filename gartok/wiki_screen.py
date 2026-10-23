"""Wiki & Compendium screen: searchable in-game encyclopedia.

Consumes centralized data catalogs:
- Items (`items.CATALOG`)
- Recipes (`items.CRAFTING_RECIPES`)
- Talents (`talents.TREES`)
- Races (`wiki_races.py`: the playable races, off `data`, `abilities` and `talents`)
- Beasts (`data.BEASTS`)
- Rules (`wiki_rules.py`: the rules a player looks up, off the live constants)
"""

import pygame

from . import (
    actions,
    artwork,
    data,
    items,
    talents,
    weapon_traits,
    wiki_races,
    wiki_rules,
)
from .screen import Screen
from .ui.primitives import draw_button, panel, set_pointer, text, wrap
from .ui.tokens import T

MARGIN = T.S * 4
TAB_W = 96
TAB_H = 32


class WikiScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.F = fonts
        self.on_back = on_back
        self.tab = "items"
        self.scroll = 0
        self._max_scroll = 0
        self.buttons = []
        self.tab_buttons = []
        self.search_query = ""

    def handle_escape(self):
        self.on_back()
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(self._max_scroll, self.scroll - event.y * 36))
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.search_query = self.search_query[:-1]
                self.scroll = 0
                return
            elif event.unicode and event.unicode.isprintable() and len(self.search_query) < 24:
                self.search_query += event.unicode.lower()
                self.scroll = 0
                return
        super().handle_event(event)

    def _click(self, px):
        for key, rect in self.tab_buttons:
            if rect.collidepoint(px):
                self.tab = key
                self.scroll = 0
                return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                elif key == "clear_search":
                    self.search_query = ""
                    self.scroll = 0
                return

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        mouse = self.mouse
        self.buttons = []
        self.tab_buttons = []

        text(screen, F["big"], "WIKI & COMPENDIUM", (MARGIN, MARGIN), T.TX)
        text(screen, F["body"], "in-game encyclopedia of rules, items, recipes, actions, talents, races and beasts",
             (MARGIN, MARGIN + 32), T.TX_MUTED)

        # Tab bar
        tabs = [("items", "ITEMS"), ("recipes", "RECIPES"), ("actions", "ACTIONS"),
                ("talents", "TALENTS"), ("races", "RACES"), ("beasts", "BEASTS"), ("rules", "RULES")]
        tx = MARGIN
        ty = MARGIN + 64
        for tab_id, tab_label in tabs:
            tr = pygame.Rect(tx, ty, TAB_W, TAB_H)
            is_active = (self.tab == tab_id)
            draw_button(screen, F, tr, tab_label, primary=is_active, enabled=not is_active, mpos=mouse)
            self.tab_buttons.append((tab_id, tr))
            tx += TAB_W + T.S

        # Search display
        sx = W - MARGIN - 260
        sr = pygame.Rect(sx, ty, 260, TAB_H)
        panel(screen, sr)
        stext = f"Filter: {self.search_query}" if self.search_query else "Type to filter..."
        text(screen, F["body"], stext, (sr.x + T.S, sr.y + 7), T.BRASS if self.search_query else T.TX_FAINT)
        if self.search_query:
            cr = pygame.Rect(sr.right - 28, sr.y + 4, 24, 24)
            draw_button(screen, F, cr, "X", mpos=mouse)
            self.buttons.append(("clear_search", cr))

        # Viewport for scrollable list
        top = ty + TAB_H + T.S * 2
        bottom = H - MARGIN - 48
        view = pygame.Rect(MARGIN, top, W - 2 * MARGIN, max(100, bottom - top))

        clip = screen.get_clip()
        screen.set_clip(view)

        y = top - self.scroll
        total_h = self._draw_content(screen, view, y)
        screen.set_clip(clip)

        self._max_scroll = max(0, total_h - view.h)

        # Footer
        r_back = pygame.Rect(MARGIN, H - MARGIN - 36, 120, 36)
        draw_button(screen, F, r_back, "BACK", mpos=mouse)
        self.buttons.append(("back", r_back))

        text(screen, F["body"], "[Esc] back  ·  [Wheel] scroll  ·  type to filter",
             (MARGIN + 140, H - MARGIN - 26), T.TX_FAINT)
        set_pointer(any(r.collidepoint(mouse) for _, r in self.tab_buttons + self.buttons))

    def _draw_content(self, screen, view, start_y):
        if self.tab == "items":
            return self._draw_items(screen, view, start_y)
        elif self.tab == "recipes":
            return self._draw_recipes(screen, view, start_y)
        elif self.tab == "actions":
            return self._draw_actions(screen, view, start_y)
        elif self.tab == "talents":
            return self._draw_talents(screen, view, start_y)
        elif self.tab == "races":
            return self._draw_races(screen, view, start_y)
        elif self.tab == "beasts":
            return self._draw_beasts(screen, view, start_y)
        else:
            return self._draw_rules(screen, view, start_y)

    def _draw_items(self, screen, view, y):
        F = self.F
        orig_y = y
        q = self.search_query
        catalog = sorted(items.all_items().values(), key=lambda i: i.name)
        if q:
            catalog = [i for i in catalog if q in i.name.lower() or q in i.type.value.lower()]

        row_h = 44
        gap = 6
        for it in catalog:
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                # Name and type
                text(screen, F["bodyb"], it.name, (r.x + T.S * 2, r.y + 6), T.TX)
                meta = f"{it.type.value.upper()}  ·  {it.weight:.1f} kg  ·  ${it.price} copper  ·  {it.rarity.value}"
                text(screen, F["micro"], meta, (r.x + T.S * 2, r.y + 24), T.TX_MUTED)
                # Weapon / armor stats if any
                extra = []
                if it.damage:
                    extra.append(f"Dmg: {it.damage[0]}d{it.damage[1]}")
                if it.ac:
                    extra.append(f"AC +{it.ac}")
                if getattr(it, "traits", ()):
                    for tid in it.traits:
                        tr = weapon_traits.get(tid)
                        if tr:
                            extra.append(tr.name)
                        else:
                            extra.append(tid.replace("_", " ").title())
                elif it.has_trait("finesse") if hasattr(it, "has_trait") else getattr(it, "finesse", False):
                    extra.append("Finesse")
                if getattr(it, "thrown", 0):
                    extra.append(f"Thrown {it.thrown}sq")
                if getattr(it, "range", 0):
                    extra.append(f"Range {it.range}sq")
                if it.hands == 2:
                    extra.append("Two-handed")
                if extra:
                    text(screen, F["body"], "  ·  ".join(extra), (r.right - T.S * 2, r.y + 12), T.BRASS, right=True)
            y += row_h + gap
        return y - orig_y

    def _draw_recipes(self, screen, view, y):
        F = self.F
        orig_y = y
        q = self.search_query
        entries = []
        for out_name, rlist in items.CRAFTING_RECIPES.items():
            recipes = rlist if isinstance(rlist, (list, tuple)) else [rlist]
            for rec in recipes:
                entries.append((out_name, rec))
        entries.sort(key=lambda pair: pair[0])
        if q:
            entries = [pair for pair in entries if q in pair[0].lower() or q in pair[1].station.lower()]

        row_h = 56
        gap = 6
        for out_name, rec in entries:
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                text(screen, F["bodyb"], f"{out_name} (x{rec.yield_qty})", (r.x + T.S * 2, r.y + 6), T.TX)
                mat_str = " + ".join(rec.materials)
                text(screen, F["body"], f"Materials: {mat_str}", (r.x + T.S * 2, r.y + 24), T.TX_MUTED)
                meta = f"Station: {rec.station.upper()}  ·  Batch: {rec.batch_hours:.1f} h  ·  Level: {rec.level}"
                text(screen, F["micro"], meta, (r.x + T.S * 2, r.y + 40), T.TX_FAINT)
            y += row_h + gap
        return y - orig_y

    def _draw_actions(self, screen, view, y):
        F = self.F
        orig_y = y
        q = self.search_query

        entries = []
        seen = set()

        for tr in weapon_traits.all_traits():
            if tr.id not in seen:
                seen.add(tr.id)
                kind = "WEAPON ACTION (2 AP)" if tr.action_id else "WEAPON TRAIT"
                entries.append((tr.name, kind, tr.desc))

        for act in actions.PANEL_ACTIONS:
            if act.id not in seen:
                seen.add(act.id)
                kind = f"COMBAT ({act.cost} AP)" if act in actions.COMBAT_ACTIONS else f"UTILITY ({act.cost} AP)"
                entries.append((act.name, kind, getattr(act, "desc", "")))

        entries.sort(key=lambda e: e[0])
        if q:
            entries = [e for e in entries if q in e[0].lower() or q in e[1].lower() or q in e[2].lower()]

        row_h = 44
        gap = 6
        for name, kind, desc in entries:
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                text(screen, F["bodyb"], name, (r.x + T.S * 2, r.y + 6), T.TX)
                text(screen, F["micro"], kind, (r.x + T.S * 2, r.y + 24), T.BRASS)
                text(screen, F["body"], desc, (r.x + 240, r.y + 12), T.TX_MUTED)
            y += row_h + gap
        return y - orig_y

    def _draw_talents(self, screen, view, y):
        F = self.F
        orig_y = y
        q = self.search_query
        all_talents = []
        for track, tree in talents.TREE.items():
            for t in tree:
                all_talents.append((track, t))
        all_talents.sort(key=lambda pair: (pair[0], pair[1].tier, pair[1].name))
        if q:
            all_talents = [p for p in all_talents if q in p[1].name.lower() or q in p[1].desc.lower() or q in p[0].lower()]

        row_h = 56
        gap = 6
        for track, t in all_talents:
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                req_str = f"Requires: {t.requires}" if t.requires else "Root node"
                text(screen, F["bodyb"], t.name, (r.x + T.S * 2, r.y + 6), T.TX)
                text(screen, F["micro"], f"Track: {track.upper()}  ·  Tier {t.tier}  ·  {req_str}",
                     (r.x + T.S * 2, r.y + 24), T.BRASS)
                text(screen, F["body"], t.effect, (r.x + T.S * 2, r.y + 38), T.TX_MUTED)
            y += row_h + gap
        return y - orig_y

    def _draw_races(self, screen, view, y):
        F = self.F
        orig_y = y
        icon_px, line_h, gap = 48, 18, 6
        for e in wiki_races.matching(self.search_query):
            lines = e["abilities"] + ([f"Racial track: {', '.join(e['talents'])}"] if e["talents"] else [])
            row_h = 52 + line_h * len(lines) + T.S
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                glyph = artwork.race_icon(e["name"], icon_px, T.TX_MUTED)
                if glyph:
                    screen.blit(glyph, (r.x + T.S * 2, r.y + T.S))
                x = r.x + T.S * 3 + icon_px
                text(screen, F["bodyb"], e["name"], (x, r.y + 6), T.TX)
                text(screen, F["body"], e["mods"], (r.right - T.S * 2, r.y + 6), T.BRASS, right=True)
                text(screen, F["micro"], e["meta"], (x, r.y + 26), T.TX_MUTED)
                ly = r.y + 46
                for line in lines:
                    text(screen, F["body"], line, (x, ly), T.TX)
                    ly += line_h
            y += row_h + gap
        return y - orig_y

    def _draw_beasts(self, screen, view, y):
        F = self.F
        orig_y = y
        q = self.search_query
        beast_list = sorted(data._BEASTS, key=lambda b: b["name"])
        if q:
            beast_list = [b for b in beast_list if q in b["name"].lower()]

        row_h = 52
        gap = 6
        for b in beast_list:
            r = pygame.Rect(view.x, y, view.w, row_h)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                text(screen, F["bodyb"], b["name"], (r.x + T.S * 2, r.y + 6), T.TX)
                abilities = b.get("ability", "")
                if isinstance(abilities, (tuple, list)):
                    ab_str = ", ".join(abilities) if abilities else "None"
                else:
                    ab_str = abilities or "None"
                drops = []
                if b.get("drop_item"):
                    pct = int(b.get("drop_chance", 0.0) * 100)
                    drops.append(f"{b['drop_item']} ({pct}%)")
                for it, ch, qty in b.get("also_drops", ()):
                    pct = int(ch * 100)
                    drops.append(f"{it} x{qty} ({pct}%)")
                drops_str = ", ".join(drops) if drops else "None"
                text(screen, F["micro"], f"HD: d{b['hd']}  ·  Size: {b['size']}  ·  Speed: {b['speed']}m  ·  Ability: {ab_str}",
                     (r.x + T.S * 2, r.y + 22), T.TX_MUTED)
                text(screen, F["micro"], f"Drops: {drops_str}", (r.x + T.S * 2, r.y + 36), T.TX_FAINT)
            y += row_h + gap
        return y - orig_y

    def _draw_rules(self, screen, view, y):
        F = self.F
        orig_y = y
        line_h, inner_w = 22, view.w - T.S * 6
        for title, lines in wiki_rules.matching(self.search_query):
            wrapped = [wrap(F["body"], line, inner_w) for line in lines]
            th = 30 + sum(len(w) for w in wrapped) * line_h + len(lines) * 4 + 12
            r = pygame.Rect(view.x, y, view.w, th)
            if r.bottom > view.top and r.top < view.bottom:
                panel(screen, r)
                text(screen, F["bodyb"], title, (r.x + T.S * 2, r.y + 8), T.BRASS)
                ly = r.y + 32
                for rows in wrapped:
                    text(screen, F["body"], "•", (r.x + T.S * 2, ly), T.TX_MUTED)
                    for row in rows:
                        text(screen, F["body"], row, (r.x + T.S * 4, ly), T.TX)
                        ly += line_h
                    ly += 4
            y += th + 10
        return y - orig_y
