"""Character creator: roll a GARTOK character and hand-edit every field.

A sandbox, not a player flow -- it is not bound by draft / XP gating. Every
editable field is set straight to a valid value: race / occupation / alignment
from their tables, the six attributes as 3d6 scores (3..18), combat / work level
by stepper (talent picks and hit dice follow), talents from the trees, languages,
the purse, and the full loadout from the item catalog. The right column shows a
live character sheet (the real `sheet.character_sheet`, through a throwaway
`Combatant`) and the NPC library.

SAVE writes the character to `npcs/<slug>.json` (`npc_lib`), versioned in git --
authored content that later features (arena champion teams, world NPCs) will pull
from. Loading a library entry brings it back to edit; RANDOMIZE starts a fresh
roll. `on_back` returns to the editor hub.
"""

import pygame

from . import data, npc_lib, sheet, talents
from .combatant import Combatant
from .screen import Screen
from .theme import (ACCENT, ACCENT_INK, DANGER, INFO, INK, INK_DIM, INK_FAINT,
                    LINE, LINE_SOFT, MARGIN, OK, RADIUS, SP1, SP2, SP3, SP4,
                    SP5, SURFACE_0, SURFACE_1, SURFACE_2, SURFACE_3, SURFACE_4,
                    panel, section, set_pointer, text, token_badge, wrap_lines)
from .unit import Unit

_ATTR_ABBR = [("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
              ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma")]

_ITEM_CATALOG = sorted(set(data.WEAPONS) | set(data.ARMOR) | set(data.ITEM_WEIGHTS)
                       | set(data.FOOD_ITEMS)
                       | {data.TORCH_ITEM, data.AMMO_ITEM, data.FIRST_AID_ITEM})

_MAX_NAME = 28


class CharEditorScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.fonts = fonts
        self.on_back = on_back
        self.hits = []                        # [(rect, action)] rebuilt each frame
        self.picker = None                    # (kind, [options], current) or None
        self.picker_hits = []
        self.edit_field = None                # "name" | "age" while typing into that row, else None
        self.edit_buf = ""
        self.notice = None                    # (text, colour)
        self.confirm_delete = None            # slug awaiting a delete confirm
        self.scroll = 0
        self._scroll_max = 0
        self._form_rect = None
        self._clip = None
        self.slug = None                      # library file this maps to, or None (unsaved)
        self.library = []
        self._load_unit(Unit("player"))

    # ------------------------------------------------------------------ #
    def _load_unit(self, unit, slug=None):
        self.unit = unit
        self.slug = slug
        self.edit_field = None
        self.scroll = 0
        self.confirm_delete = None
        self._refresh_library()

    def _refresh_library(self):
        self.library = npc_lib.list_npcs()

    def _gear(self, fn, *args):
        fn(*args)
        self.unit._derive_combat()

    def _save(self):
        self.slug = npc_lib.save_npc(self.unit, self.slug)
        self._refresh_library()
        self.notice = (f"saved  ·  npcs/{self.slug}.json", OK)

    def _start_edit(self, field):
        self.edit_field = field
        u = self.unit
        self.edit_buf = "" if (field == "name" and u._auto_name) \
            else u.name if field == "name" else str(u.age)

    def _commit_edit(self):
        if self.edit_field == "name":
            self.unit.set_name(self.edit_buf)
        elif self.edit_field == "age" and self.edit_buf:
            self.unit.set_age(int(self.edit_buf))
        self.edit_field = None

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if self.edit_field and event.type == pygame.KEYDOWN:
            digits_only = self.edit_field == "age"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_edit()
            elif event.key == pygame.K_BACKSPACE:
                self.edit_buf = self.edit_buf[:-1]
            elif event.unicode and len(self.edit_buf) < _MAX_NAME \
                    and (event.unicode.isdigit() if digits_only
                         else event.unicode.isprintable()):
                self.edit_buf += event.unicode
            return
        if event.type == pygame.MOUSEWHEEL and self._form_rect \
                and self._form_rect.collidepoint(self.mouse):
            self.scroll = max(0, min(self._scroll_max, self.scroll - event.y * 44))
            return
        super().handle_event(event)

    def _click(self, px):
        self.notice = None
        if self.picker is not None:
            self._pick_click(px)
            return
        if self.edit_field:                   # a click anywhere commits the field being typed
            self._commit_edit()
        for rect, action in self.hits:
            if rect.collidepoint(px):
                self._do(action)
                return

    def _do(self, action):
        kind = action[0]
        u = self.unit
        if kind == "back":
            self.on_back()
        elif kind == "save":
            self._save()
        elif kind == "randomize":
            self._load_unit(Unit("player"))
        elif kind in ("name", "age"):
            self._start_edit(kind)
        elif kind == "picker":
            _, pk = action
            opts = {"race": data.RACE_NAMES, "occupation": data.OCCUPATION_NAMES,
                    "alignment": [a for _, a in data.ALIGNMENTS],
                    "weapon": ["(unarmed)"] + list(data.WEAPONS),
                    "armor": ["(none)"] + list(data.ARMOR),
                    "additem": _ITEM_CATALOG}[pk]
            cur = {"race": u.race["name"], "occupation": u.occupation["name"],
                   "alignment": u.alignment, "weapon": u.equipped_weapon,
                   "armor": u.equipped_armor, "additem": None}[pk]
            self.picker = (pk, opts, cur)
        elif kind == "attr":
            _, name, delta = action
            u.set_base_attribute(name, u.base_attributes[name] + delta)
        elif kind == "level":
            _, track, delta = action
            u.set_track_level(track, u.track_level[track] + delta)
        elif kind == "gold":
            u.set_gold(u.gold + action[1])
        elif kind == "talent":
            _, track, tid = action
            (u.drop_talent if tid in u.talents[track] else u.choose_talent)(track, tid)
        elif kind == "lang":
            _, name = action
            u.set_language(name, name not in u.languages)
        elif kind == "torch":
            if u.equipped_offhand == data.TORCH_ITEM:
                self._gear(u.take_from_offhand)
            else:
                self._gear(u.give_to_offhand, data.TORCH_ITEM)
        elif kind == "unpack":
            self._gear(u.take_from_pack, action[1])
        elif kind == "load":
            self._load_unit(npc_lib.load_npc(action[1]), slug=action[1])
        elif kind == "ask_delete":
            self.confirm_delete = action[1]
        elif kind == "delete":
            npc_lib.delete_npc(action[1])
            if self.slug == action[1]:
                self.slug = None
            self.confirm_delete = None
            self._refresh_library()
        elif kind == "delete_no":
            self.confirm_delete = None

    def _pick_click(self, px):
        for rect, name in self.picker_hits:
            if not rect.collidepoint(px):
                continue
            pk = self.picker[0]
            u = self.unit
            if pk == "race":
                u.set_race(name)
            elif pk == "occupation":
                u.set_occupation(name)
            elif pk == "alignment":
                u.set_alignment(name)
            elif pk == "weapon":
                u.take_from_hand() if name == "(unarmed)" else u.give_to_hand(name)
                u._derive_combat()
            elif pk == "armor":
                u.take_from_armor() if name == "(none)" else u.give_to_armor(name)
                u._derive_combat()
            elif pk == "additem":
                u.give_to_pack(name)
                u._derive_combat()
            self.picker = None
            return
        self.picker = None

    # ------------------------------------------------------------------ #
    # drawing                                                            #
    # ------------------------------------------------------------------ #
    def _hit(self, rect, action):
        if self._clip is None or self._clip.colliderect(rect):
            self.hits.append((rect, action))

    def _btn(self, screen, rect, label, *, on=False, danger=False, font=None):
        hot = rect.collidepoint(self.mouse)
        edge = DANGER if danger else ACCENT
        panel(screen, rect, fill=edge if on else (SURFACE_3 if hot else SURFACE_2),
              border=edge if (on or hot) else LINE_SOFT, width=1, radius=4)
        col = ACCENT_INK if on else (DANGER if danger else (ACCENT if hot else INK_DIM))
        text(screen, label, font or self.fonts.label, col, rect.center, center=True)

    def draw(self, screen):
        f = self.fonts
        W, H = screen.get_size()
        screen.fill(SURFACE_0)
        self.hits = []
        self._clip = None
        pad = MARGIN if W < 1500 else SP5

        text(screen, "CHARACTER CREATOR", f.title, INK, (pad, pad - 2))
        sub = (f"editing  {self.slug}" if self.slug else "unsaved  ·  a fresh roll")
        if self.notice:
            sub, scol = self.notice[0], self.notice[1]
        else:
            scol = INK_DIM
        text(screen, sub, f.body_sm, scol, (pad, pad + 28))

        bw, bh = 108, 30
        bx = W - pad - bw
        for key, label, danger in (("back", "BACK", False), ("save", "SAVE", False),
                                   ("randomize", "RANDOMIZE", False)):
            r = pygame.Rect(bx, pad, bw, bh)
            self._btn(screen, r, label, danger=danger, font=f.body_bd)
            self._hit(r, (key,))
            bx -= bw + SP2

        top = pad + 52
        gap = SP4
        left_w = max(430, int((W - 2 * pad - gap) * 0.58))
        left = pygame.Rect(pad, top, left_w, H - top - pad)
        right = pygame.Rect(left.right + gap, top, W - pad - (left.right + gap),
                            H - top - pad)
        self._form_rect = left
        self._draw_form(screen, left)
        self._draw_side(screen, right)

        if self.picker is not None:
            self._draw_picker(screen)

        set_pointer(any(r.collidepoint(self.mouse) for r, _ in self.hits)
                    or bool(self.picker))

    # ------------------------------------------------------------------ #
    def _draw_form(self, screen, rect):
        f = self.fonts
        u = self.unit
        panel(screen, rect, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        inner = rect.inflate(-2 * SP3, -2 * SP2)
        prev = screen.get_clip()
        screen.set_clip(inner)
        self._clip = inner
        x = inner.x
        w = inner.w
        y = inner.y - self.scroll
        y0 = y

        # --- identity --------------------------------------------------- #
        y = section(screen, "IDENTITY", x, y, w, f)
        half = (w - SP2) // 2
        self._edit_row(screen, pygame.Rect(x, y, w, 26), "NAME", "name",
                       "" if u._auto_name else u.name)
        y += 26 + SP1
        for i, (pk, lbl, val) in enumerate((("race", "RACE", u.race["name"]),
                                            ("occupation", "OCC", u.occupation["name"]))):
            self._pick_row(screen, pygame.Rect(x + i * (half + SP2), y, half, 26),
                           lbl, val, ("picker", pk))
        y += 26 + SP1
        self._pick_row(screen, pygame.Rect(x, y, half, 26), "ALIGN", u.alignment,
                       ("picker", "alignment"))
        mult = u.race["age_mult"]
        self._edit_row(screen, pygame.Rect(x + half + SP2, y, half, 26), "AGE", "age",
                       f"{u.age}  ({round(u.age / mult)} at x1)")
        y += 26 + SP1
        text(screen, f"{u.race['size']}  ·  token {u.race['token']}  ·  "
             f"ability: {u.ability.name}", f.body_sm, INK_FAINT, (x, y + 2))
        y += 20

        # --- attributes ----------------------------------------------- #
        y = section(screen, "ATTRIBUTES  (3d6 score, 3..18)", x, y + SP1, w, f)
        cg = SP1
        cw = (w - 5 * cg) // 6
        for i, (abbr, name) in enumerate(_ATTR_ABBR):
            cx = x + i * (cw + cg)
            cell = pygame.Rect(cx, y, cw, 62)
            panel(screen, cell, fill=SURFACE_2, border=LINE_SOFT, width=1, radius=4)
            text(screen, abbr, f.label, INK_FAINT, (cell.centerx, cell.y + 4), center=True)
            base = u.base_attributes[name]
            text(screen, str(base), f.num, INK, (cell.centerx, cell.y + 15), center=True)
            m = getattr(u, f"mod_{name}")
            mc = OK if m > 0 else DANGER if m < 0 else INK_FAINT
            fin = getattr(u, name)
            text(screen, f"{fin} ({m:+})", f.mono_sm, mc,
                 (cell.centerx, cell.y + 44), center=True)
            dn = pygame.Rect(cell.x + 2, cell.bottom - 16, cw // 2 - 3, 14)
            up = pygame.Rect(cell.centerx + 1, cell.bottom - 16, cw // 2 - 3, 14)
            for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
                h = br.collidepoint(self.mouse)
                panel(screen, br, fill=SURFACE_4 if h else SURFACE_1,
                      border=LINE_SOFT, width=0, radius=3)
                text(screen, glyph, f.body_sm, ACCENT if h else INK_DIM,
                     br.center, center=True)
                self._hit(br, ("attr", name, sign))
        y += 62 + SP2

        # --- progression -------------------------------------------- #
        y = section(screen, "PROGRESSION", x, y, w, f)
        for i, track in enumerate(talents.TRACKS):
            lr = pygame.Rect(x + i * (half + SP2), y, half, 26)
            panel(screen, lr, fill=SURFACE_2, border=LINE_SOFT, width=1, radius=4)
            lvl = u.track_level[track]
            text(screen, f"{track.upper()}  N{lvl}", f.body_sm, INK,
                 (lr.x + SP2, lr.y + 6))
            picks = u.picks_available(track)
            if picks:
                text(screen, f"+{picks}", f.label, ACCENT, (lr.centerx + 6, lr.y + 8))
            dn = pygame.Rect(lr.right - 40, lr.y + 3, 18, 20)
            up = pygame.Rect(lr.right - 20, lr.y + 3, 18, 20)
            for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
                h = br.collidepoint(self.mouse)
                panel(screen, br, fill=SURFACE_4 if h else SURFACE_1, border=LINE_SOFT,
                      width=0, radius=3)
                text(screen, glyph, f.body_sm, ACCENT if h else INK_DIM, br.center, center=True)
                self._hit(br, ("level", track, sign))
        y += 26 + SP1
        dice = len(u._level_hp_rolls)
        lo, hi = self._hp_bounds(u)
        text(screen, f"mean level {u.mean_level}  ·  {1 + dice} hit "
             f"{'die' if dice == 0 else 'dice'}  ·  HP {u.hp_max}  (rolls {lo}-{hi})",
             f.body_sm, INK_FAINT, (x, y + 2))
        y += 20

        # --- talents ----------------------------------------------- #
        y = section(screen, "TALENTS", x, y + SP1, w, f)
        for i, track in enumerate(talents.TRACKS):
            colx = x + i * (half + SP2)
            text(screen, track.upper(), f.label, INFO, (colx, y))
            ty = y + 16
            for t in talents.TREE[track]:
                taken = t.id in u.talents[track]
                blocked = t.requires and t.requires not in u.talents[track]
                openp = not taken and not blocked and u.picks_available(track) > 0
                tr = pygame.Rect(colx + (SP3 if t.requires else 0), ty,
                                 half - (SP3 if t.requires else 0), 18)
                edge = OK if taken else ACCENT if openp else LINE_SOFT
                panel(screen, tr, fill=SURFACE_2 if (taken or openp) else SURFACE_1,
                      border=edge, width=1, radius=3)
                tc = OK if taken else ACCENT if openp else INK_FAINT
                text(screen, t.name, f.label, tc, (tr.x + SP1, tr.y + 4))
                if taken or openp:
                    self._hit(tr, ("talent", track, t.id))
                ty += 20
            y = max(y, ty)
        y += SP2

        # --- languages ------------------------------------------- #
        y = section(screen, "LANGUAGES", x, y, w, f)
        cx, cy = x, y
        for lang in data.LANGUAGES:
            on = lang in u.languages
            cwid = f.body_sm.size(lang)[0] + SP3
            if cx + cwid > x + w:
                cx, cy = x, cy + 22
            lr = pygame.Rect(cx, cy, cwid, 18)
            panel(screen, lr, fill=SURFACE_3 if on else SURFACE_1,
                  border=ACCENT if on else LINE_SOFT, width=1, radius=3)
            text(screen, lang, f.body_sm, INK if on else INK_FAINT, (lr.x + SP1, lr.y + 3))
            self._hit(lr, ("lang", lang))
            cx += cwid + SP1
        y = cy + 18 + SP2

        # --- purse + gear -------------------------------------- #
        y = section(screen, "PURSE + GEAR", x, y, w, f)
        gr = pygame.Rect(x, y, w, 24)
        panel(screen, gr, fill=SURFACE_2, border=LINE_SOFT, width=1, radius=4)
        text(screen, f"{u.gold} copper", f.body_sm, ACCENT, (gr.x + SP2, gr.y + 5))
        bxx = gr.right - 4
        for step, glyph in ((10, "+10"), (1, "+1"), (-1, "−1"), (-10, "−10")):
            sw = 34
            sr = pygame.Rect(bxx - sw, gr.y + 2, sw - 2, 20)
            self._btn(screen, sr, glyph)
            self._hit(sr, ("gold", step))
            bxx -= sw
        y += 24 + SP1

        wr = pygame.Rect(x, y, w, 24)
        self._pick_row(screen, wr, "WEAPON", u.equipped_weapon or "(unarmed)",
                       ("picker", "weapon"))
        y += 24 + SP1
        arr = pygame.Rect(x, y, w, 24)
        self._pick_row(screen, arr, "ARMOR", u.equipped_armor or "(none)",
                       ("picker", "armor"))
        y += 24 + SP1
        tr = pygame.Rect(x, y, w, 22)
        torch_on = u.equipped_offhand == data.TORCH_ITEM
        self._btn(screen, tr, ("OFF HAND: TORCH" if torch_on else "OFF HAND: EMPTY"),
                  on=torch_on)
        self._hit(tr, ("torch",))
        y += 22 + SP2

        text(screen, f"PACK  ({len(u._base_inventory)})  ·  load "
             f"{u.load:g}/{u.carry_normal:g} kg", f.label, INFO, (x, y))
        y += 16
        for idx, item in enumerate(list(u._base_inventory)):
            ir = pygame.Rect(x, y, w, 20)
            panel(screen, ir, fill=SURFACE_1, border=LINE_SOFT, width=1, radius=3)
            text(screen, item, f.body_sm, INK, (ir.x + SP2, ir.y + 3))
            text(screen, f"{data.item_weight(item):g} kg", f.mono_sm, INK_FAINT,
                 (ir.right - 44, ir.y + 4))
            xr = pygame.Rect(ir.right - 20, ir.y + 2, 16, 16)
            h = xr.collidepoint(self.mouse)
            text(screen, "×", f.body_bd, DANGER if h else INK_DIM, xr.center, center=True)
            self._hit(xr, ("unpack", idx))
            y += 22
        addr = pygame.Rect(x, y, 120, 20)
        self._btn(screen, addr, "+ ADD ITEM")
        self._hit(addr, ("picker", "additem"))
        y += 20 + SP4

        content_h = y - y0                      # y0 already carries the -scroll offset
        self._scroll_max = max(0, content_h - inner.h)
        screen.set_clip(prev)
        self._clip = None
        if self._scroll_max:
            track_h = inner.h
            kh = max(24, int(track_h * inner.h / content_h))
            ky = inner.y + int((track_h - kh) * self.scroll / self._scroll_max)
            pygame.draw.rect(screen, SURFACE_4,
                             (rect.right - 5, ky, 3, kh), border_radius=2)

    def _pick_row(self, screen, rect, label, value, action):
        f = self.fonts
        hot = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_3 if hot else SURFACE_2,
              border=ACCENT if hot else LINE, width=1, radius=4)
        text(screen, label, f.label, INK_FAINT, (rect.x + SP2, rect.centery - 5))
        text(screen, str(value), f.body_sm, INK, (rect.x + 58, rect.centery - 6))
        text(screen, "▾", f.body_sm, ACCENT if hot else INK_FAINT,
             (rect.right - SP2, rect.centery - 7), right=True)
        self._hit(rect, action)

    def _edit_row(self, screen, rect, label, field, value):
        """A click-to-type row (name / age). `value` is what shows when idle; the
        typed buffer, with a caret, shows while `field` is being edited."""
        f = self.fonts
        editing = self.edit_field == field
        hot = rect.collidepoint(self.mouse)
        panel(screen, rect, fill=SURFACE_3 if (hot or editing) else SURFACE_2,
              border=ACCENT if (hot or editing) else LINE, width=1, radius=4)
        text(screen, label, f.label, INK_FAINT, (rect.x + SP2, rect.centery - 5))
        shown = (self.edit_buf + "|") if editing else (str(value) or "(auto)")
        text(screen, shown, f.body_sm, INK, (rect.x + 46, rect.centery - 6))
        if not editing:
            text(screen, "edit", f.label, ACCENT if hot else INK_FAINT,
                 (rect.right - SP2, rect.centery - 5), right=True)
        self._hit(rect, (field,))

    @staticmethod
    def _hp_bounds(u):
        """The min/max HP the current race die + Con + kept hit dice could roll --
        the band `hp_max` sits in, so a level bump reads as a range, not a
        mystery re-roll."""
        hd, con, ab = u.race["hd"], u.mod_constitution, u.ability.hp_max
        kept = len(u._level_hp_rolls)
        flat = u.talent_bonus("hp_per_hd") * (1 + kept)
        lo = max(1, 1 + con + ab) + kept * max(1, 1 + con) + flat
        hi = max(1, hd + con + ab) + kept * max(1, hd + con) + flat
        return lo, hi

    # ------------------------------------------------------------------ #
    def _draw_side(self, screen, rect):
        f = self.fonts
        u = self.unit
        lib_h = min(int(rect.h * 0.42), 40 + 30 * (len(self.library) + 1))
        lib = pygame.Rect(rect.x, rect.y, rect.w, max(120, lib_h))
        panel(screen, lib, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        text(screen, "NPC LIBRARY", f.label, INFO, (lib.x + SP3, lib.y + SP2))
        text(screen, "npcs/", f.mono_sm, INK_FAINT, (lib.right - SP3, lib.y + SP2),
             right=True)
        ly = lib.y + 24
        if not self.library:
            text(screen, "no saved characters yet — SAVE writes one here",
                 f.body_sm, INK_FAINT, (lib.x + SP3, ly + 2))
        prev = screen.get_clip()
        screen.set_clip(lib.inflate(-SP2, -SP2))
        for row in self.library:
            if ly > lib.bottom - 20:
                break
            rr = pygame.Rect(lib.x + SP2, ly, lib.w - 2 * SP2, 26)
            cur = row["slug"] == self.slug
            hot = rr.collidepoint(self.mouse)
            panel(screen, rr, fill=SURFACE_3 if (hot or cur) else SURFACE_2,
                  border=ACCENT if cur else (LINE if hot else LINE_SOFT),
                  width=1, radius=4)
            text(screen, row["name"], f.body_sm, INK, (rr.x + SP2, rr.y + 5))
            meta = f"{row['race']}·{row['occupation']}"
            text(screen, meta, f.mono_sm, INK_FAINT, (rr.right - 44, rr.y + 6), right=True)
            if self.confirm_delete == row["slug"]:
                yb = pygame.Rect(rr.right - 40, rr.y + 3, 18, 20)
                nb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                self._btn(screen, yb, "y", danger=True)
                self._btn(screen, nb, "n")
                self._hit(yb, ("delete", row["slug"]))
                self._hit(nb, ("delete_no",))
            else:
                self._hit(rr, ("load", row["slug"]))
                xb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                h = xb.collidepoint(self.mouse)
                text(screen, "×", f.body_bd, DANGER if h else INK_FAINT, xb.center,
                     center=True)
                self._hit(xb, ("ask_delete", row["slug"]))
            ly += 28
        screen.set_clip(prev)

        # --- live sheet -------------------------------------------- #
        pr = pygame.Rect(rect.x, lib.bottom + SP3, rect.w,
                         rect.bottom - lib.bottom - SP3)
        panel(screen, pr, fill=SURFACE_1, border=LINE_SOFT, radius=RADIUS)
        px = pr.x + SP3
        pw = pr.w - 2 * SP3
        py = pr.y + SP2
        tok = (px + 12, py + 12)
        token_badge(screen, tok, u, f, r=13)
        text(screen, u.name, f.card_name, INK, (tok[0] + 24, py + 2))
        py += 30
        chips = ((f"HP {u.hp_max}", OK), (f"AC {u.ac}", INFO),
                 (f"MD {u.mental_defense}", DANGER), (f"SPD {u.speed}", INFO))
        cwc = (pw - 3 * SP1) // 4
        for i, (s, c) in enumerate(chips):
            cr = pygame.Rect(px + i * (cwc + SP1), py, cwc, 26)
            panel(screen, cr, fill=SURFACE_2, border=LINE_SOFT, width=1, radius=4)
            text(screen, s, f.mono_sm, c, cr.center, center=True)
        py += 34
        prev = screen.get_clip()
        screen.set_clip(pr.inflate(-SP2, -SP2))
        for ln in sheet.character_sheet(Combatant(u))[1:]:
            for seg in wrap_lines([ln], f.body_sm, pw):
                if py > pr.bottom - 14:
                    break
                text(screen, seg, f.body_sm, INK_DIM, (px, py))
                py += 15
        screen.set_clip(prev)

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen):
        f = self.fonts
        kind, options, current = self.picker
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        cols = 3 if len(options) > 8 else 1
        rows = (len(options) + cols - 1) // cols
        cw, ch, pad = 230, 26, SP4
        pw = cols * cw + 2 * pad
        ph = 52 + rows * ch + SP4
        W, H = screen.get_size()
        panel_r = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        panel(screen, panel_r, fill=SURFACE_2, border=ACCENT, width=2, radius=8)
        text(screen, f"pick a {kind}", f.title, INK, (panel_r.x + pad, panel_r.y + 12))

        self.picker_hits = []
        for i, name in enumerate(options):
            c, rw = i % cols, i // cols
            it = pygame.Rect(panel_r.x + pad + c * cw, panel_r.y + 46 + rw * ch,
                             cw - SP1, ch - SP1)
            sel = name == current
            hov = it.collidepoint(self.mouse)
            panel(screen, it, fill=SURFACE_3 if (hov or sel) else SURFACE_1,
                  border=ACCENT if sel else (LINE if hov else LINE_SOFT), width=1, radius=4)
            text(screen, str(name), f.body_sm, ACCENT if sel else INK,
                 (it.x + SP2, it.y + 4))
            self.picker_hits.append((it, name))
        text(screen, "click outside to cancel", f.body_sm, INK_FAINT,
             (panel_r.x + pad, panel_r.bottom - 20))
