"""Character creator: roll a GARTOK character and hand-edit every field.

A sandbox, not a player flow -- it is not bound by draft / XP gating. Every
editable field is set straight to a valid value: race / occupation / alignment
from their tables, the six attributes as 3d6 scores (3..18), combat / work level
by stepper (talent picks and hit dice follow), HP (a stepper pins an override,
AUTO drops back to the roll), talents from the trees, languages, the purse, and
the full loadout from the item catalog. The right column shows a
live character sheet (the real `sheet.character_sheet`, through a throwaway
`Combatant`) and the NPC library.

SAVE writes the character to `npcs/<slug>.json` (`npc_lib`), versioned in git --
authored content that later features (arena champion teams, world NPCs) will pull
from. Loading a library entry brings it back to edit; RANDOMIZE starts a fresh
roll. `on_back` returns to the editor hub.
"""

import uuid

import pygame

from . import data, items, magic, npc_lib, persist, talents
from .combatant import Combatant
from .constants import fmt_money
from .screen import Screen
from .ui.primitives import (
    box,
    draw_button,
    draw_tooltip,
    ellipsize,
    format_tooltip,
    section,
    set_pointer,
    text,
)
from .ui.primitives import contained as ui_contained
from .ui.sheet_card import draw_sheet as draw_sheet_card
from .ui.sheet_card import hp_tooltip, sheet_height, unit_to_ch
from .ui.tokens import T
from .unit import Unit

_ATTR_ABBR = [("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
              ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma")]

_ITEM_CATALOG = sorted(items.all_items().keys())

_MAX_NAME = 28
_MAX_BIO = 240


class CharEditorScreen(Screen):
    native = True

    def __init__(self, fonts, on_back):
        super().__init__()
        self.F = fonts
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
        self._lib_rect = None                 # the NPC library / live sheet panels scroll on their own
        self._sheet_rect = None
        self.lib_scroll = self.sheet_scroll = 0
        self._lib_max = self._sheet_max = 0
        self._clip = None
        self.slug = None                      # library file this maps to, or None (unsaved)
        self.library = []
        self._load_unit(Unit("player"))

    # ------------------------------------------------------------------ #
    def _load_unit(self, unit, slug=None):
        self.unit = unit
        self.slug = slug
        self.edit_field = None
        self.scroll = self.sheet_scroll = 0
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
        self.notice = (f"saved  ·  npcs/{self.slug}.json", T.GREEN)

    def _duplicate(self):
        """Clone the current character into a fresh, unsaved copy -- new identity,
        same everything else. SAVE then writes it as its own npcs/ file."""
        d = persist.unit_to_dict(self.unit)
        d["uid"] = uuid.uuid4().hex
        d["recruited_by"] = None
        clone = Unit.from_save(d)
        clone.set_name(f"{self.unit.name} (copy)")
        self._load_unit(clone, slug=None)
        self.notice = ("duplicated  ·  unsaved copy — SAVE writes a new file", T.GREEN)

    def _start_edit(self, field):
        self.edit_field = field
        u = self.unit
        self.edit_buf = "" if (field == "name" and u._auto_name) \
            else u.name if field == "name" else u.bio if field == "bio" else str(u.age)

    def _commit_edit(self):
        if self.edit_field == "name":
            self.unit.set_name(self.edit_buf)
        elif self.edit_field == "bio":
            self.unit.set_bio(self.edit_buf)
        elif self.edit_field == "age" and self.edit_buf:
            self.unit.set_age(int(self.edit_buf))
        self.edit_field = None

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def handle_event(self, event):
        if self.edit_field and event.type == pygame.KEYDOWN:
            digits_only = self.edit_field == "age"
            cap = _MAX_BIO if self.edit_field == "bio" else _MAX_NAME
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_edit()
            elif event.key == pygame.K_BACKSPACE:
                self.edit_buf = self.edit_buf[:-1]
            elif event.unicode and len(self.edit_buf) < cap \
                    and (event.unicode.isdigit() if digits_only
                         else event.unicode.isprintable()):
                self.edit_buf += event.unicode
            return
        if event.type == pygame.MOUSEWHEEL:
            for rect, attr, top in ((self._form_rect, "scroll", self._scroll_max),
                                    (self._lib_rect, "lib_scroll", self._lib_max),
                                    (self._sheet_rect, "sheet_scroll", self._sheet_max)):
                if rect and rect.collidepoint(self.mouse):
                    setattr(self, attr, max(0, min(top, getattr(self, attr) - event.y * 44)))
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
        elif kind == "duplicate":
            self._duplicate()
        elif kind == "randomize":
            self._load_unit(Unit("player"))
        elif kind in ("name", "age", "bio"):
            self._start_edit(kind)
        elif kind == "picker":
            _, pk = action
            opts = {"race": data.ALL_RACE_NAMES, "occupation": data.OCCUPATION_NAMES,
                    "alignment": [a for _, a in data.ALIGNMENTS],
                    "weapon": ["(unarmed)"] + list(items.weapons()),
                    "tongue": ["(empty)"] + [n for n, w in items.weapons().items()
                                             if w.hands == 1],
                    "armor": ["(none)"] + list(items.armor()),
                    "additem": _ITEM_CATALOG,
                    "magic": ["(none)"] + [s.capitalize() for s in magic.SOURCES]}[pk]
            cur = {"race": u.race["name"], "occupation": u.occupation["name"],
                   "alignment": u.alignment, "weapon": u.equipped_weapon,
                   "tongue": u.equipped_tongue, "armor": u.equipped_armor,
                   "additem": None,
                   "magic": u.magic_source.capitalize() if u.magic_source else "(none)"}[pk]
            self.picker = (pk, opts, cur)
        elif kind == "attr":
            _, name, delta = action
            u.set_base_attribute(name, u.base_attributes[name] + delta)
        elif kind == "level":
            _, track, delta = action
            u.set_track_level(track, u.track_level[track] + delta)
        elif kind == "natarmor":
            u.set_natural_armor(u.natural_armor + action[1])
        elif kind == "gold":
            u.set_money(u.money + action[1])
        elif kind == "hp":
            u.set_hp(u.hp_max + action[1])
        elif kind == "hp_auto":
            u.set_hp(None)
        elif kind == "racial_auto":
            u.set_track_level("racial", None)
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
            idx = action[1]
            if idx < len(u._base_inventory):
                self._gear(u.take_from_pack, idx, u._base_inventory[idx][1])
        elif kind == "spell":
            u.set_spell_known(action[1], action[1] not in u.spells_known)
        elif kind == "study":
            u.study_target = None if u.study_target == action[1] else action[1]
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
            elif pk == "tongue":
                u.take_from_tongue() if name == "(empty)" else u.give_to_tongue(name)
                u._derive_combat()
            elif pk == "armor":
                u.take_from_armor() if name == "(none)" else u.give_to_armor(name)
                u._derive_combat()
            elif pk == "magic":
                u.set_magic_source(None if name == "(none)" else name.lower())
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
        draw_button(screen, self.F, rect, label, primary=on, danger=danger and on,
                    mpos=self.mouse, fnt=font)

    def draw(self, screen):
        F = self.F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.hits = []
        self.tooltip = None
        self._clip = None
        pad = T.S * 2 if W < 1500 else T.S * 3

        text(screen, F["titleb"], "CHARACTER CREATOR", (pad, pad - 2), T.TX)
        sub = (f"editing  {self.slug}" if self.slug else "unsaved  ·  a fresh roll")
        if self.notice:
            sub, scol = self.notice[0], self.notice[1]
        else:
            scol = T.TX_MUTED
        text(screen, F["body_sm"], sub, (pad, pad + 28), scol)

        narrow = W < 980
        bw, bh = (78, 28) if narrow else (104, 30)
        bx = W - pad - bw
        for key, label, danger in (("back", "BACK", False), ("save", "SAVE", False),
                                   ("duplicate", "DUPLICATE", False),
                                   ("randomize", "RANDOMIZE", False)):
            r = pygame.Rect(bx, pad, bw, bh)
            self._btn(screen, r, label, danger=danger,
                      font=F["micro"] if narrow else F["bodyb"])
            self._hit(r, (key,))
            bx -= bw + T.S

        top = pad + 52
        gap = T.S * 2
        left_w = max(430, min(int((W - 2 * pad - gap) * 0.58),
                              W - 2 * pad - gap - 300))
        left = pygame.Rect(pad, top, left_w, H - top - pad)
        right = pygame.Rect(left.right + gap, top, W - pad - (left.right + gap),
                            H - top - pad)
        self._form_rect = left
        self._draw_form(screen, left)
        self._draw_side(screen, right)

        if self.picker is not None:
            self._draw_picker(screen)

        if getattr(self, "tooltip", None):
            draw_tooltip(screen, F, self.tooltip, self.mouse)

        set_pointer(any(r.collidepoint(self.mouse) for r, _ in self.hits)
                    or bool(self.picker))

    # ------------------------------------------------------------------ #
    def _draw_form(self, screen, rect):
        F = self.F
        u = self.unit
        box(screen, rect, fill=T.STEEL, border=T.STEEL_LINE)
        inner = rect.inflate(-2 * T.S * 2, -2 * T.S)
        prev = screen.get_clip()
        screen.set_clip(inner)
        self._clip = inner
        x = inner.x
        w = inner.w
        y = inner.y - self.scroll
        y0 = y

        # --- identity --------------------------------------------------- #
        y = section(screen, F, "IDENTITY", x, y, w)
        half = (w - T.S) // 2
        third = (w - 2 * T.S) // 3            # the three track columns (progression + talents)
        self._edit_row(screen, pygame.Rect(x, y, w, 26), "NAME", "name",
                       "" if u._auto_name else u.name)
        y += 26 + T.S // 2
        for i, (pk, lbl, val) in enumerate((("race", "RACE", u.race["name"]),
                                            ("occupation", "OCC", u.occupation["name"]))):
            self._pick_row(screen, pygame.Rect(x + i * (half + T.S), y, half, 26),
                           lbl, val, ("picker", pk))
        y += 26 + T.S // 2
        self._pick_row(screen, pygame.Rect(x, y, half, 26), "ALIGN", u.alignment,
                       ("picker", "alignment"))
        mult = u.race["age_mult"]
        self._edit_row(screen, pygame.Rect(x + half + T.S, y, half, 26), "AGE", "age",
                       f"{u.age}  ({round(u.age / mult)} at x1)")
        y += 26 + T.S // 2
        text(screen, F["body_sm"], f"{u.size}  ·  token {u.race['token']}  ·  " f"ability: {u.ability.name}",
             (x, y + 2), T.TX_FAINT)
        y += 20
        self._edit_row(screen, pygame.Rect(x, y, w, 26), "BIO", "bio", u.bio)
        y += 26 + T.S // 2

        # --- attributes ----------------------------------------------- #
        y = section(screen, F, "ATTRIBUTES  (3d6 score, 3..18)", x, y + T.S // 2, w)
        cg = T.S // 2
        cw = (w - 5 * cg) // 6
        ch, bh = 80, 16
        for i, (abbr, name) in enumerate(_ATTR_ABBR):
            cx = x + i * (cw + cg)
            cell = pygame.Rect(cx, y, cw, ch)
            box(screen, cell, fill=T.TABLE, border=T.STEEL_LINE, width=1)
            text(screen, F["micro"], abbr, (cell.centerx, cell.y + 11), T.TX_FAINT, center=True)
            base = u.base_attributes[name]
            text(screen, F["head"], str(base), (cell.centerx, cell.y + 31), T.TX, center=True)
            m = getattr(u, f"mod_{name}")
            mc = T.GREEN if m > 0 else T.BLOOD if m < 0 else T.TX_FAINT
            fin = getattr(u, name)
            text(screen, F["micro"], f"{fin} ({m:+})",
                 (cell.centerx, cell.y + 50), mc, center=True)
            dn = pygame.Rect(cell.x + 2, cell.bottom - bh - 2, cw // 2 - 3, bh)
            up = pygame.Rect(cell.centerx + 1, cell.bottom - bh - 2, cw // 2 - 3, bh)
            for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
                h = br.collidepoint(self.mouse)
                box(screen, br, fill=T.STEEL_HI if h else T.STEEL, border=T.STEEL_LINE, width=0)
                text(screen, F["body_sm"], glyph, br.center, T.BRASS if h else T.TX_MUTED, center=True)
                self._hit(br, ("attr", name, sign))
            if cell.collidepoint(self.mouse) and not dn.collidepoint(self.mouse) and not up.collidepoint(self.mouse):
                if abbr in data.ATTRIBUTE_HELP:
                    t, d = data.ATTRIBUTE_HELP[abbr]
                    self.tooltip = format_tooltip(t, d, F)
        y += ch + T.S

        # --- progression -------------------------------------------- #
        # RACIAL: sandbox pins the racial level straight; the AUTO tag on the
        # line below drops it back to derived (combat + work on a scale).
        y = section(screen, F, "PROGRESSION", x, y, w)
        for i, track in enumerate(talents.TRACKS):
            lr = pygame.Rect(x + i * (third + T.S), y, third, 26)
            box(screen, lr, fill=T.TABLE, border=T.STEEL_LINE, width=1)
            lvl = u.track_level[track]
            pin = track == "racial" and u._racial_override is not None
            text(screen, F["body_sm"], f"{track.upper()}  N{lvl}",
                 (lr.x + T.S, lr.y + 6), T.BRASS if pin else T.TX)
            picks = u.picks_available(track)
            if picks:
                text(screen, F["micro"], f"+{picks}", (lr.right - 52, lr.y + 8), T.BRASS)
            dn = pygame.Rect(lr.right - 40, lr.y + 3, 18, 20)
            up = pygame.Rect(lr.right - 20, lr.y + 3, 18, 20)
            for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
                h = br.collidepoint(self.mouse)
                box(screen, br, fill=T.STEEL_HI if h else T.STEEL, border=T.STEEL_LINE, width=0)
                text(screen, F["body_sm"], glyph, br.center, T.BRASS if h else T.TX_MUTED, center=True)
                self._hit(br, ("level", track, sign))
        y += 26 + T.S // 2

        # HP: the steppers pin an override, AUTO clears it (see Unit.set_hp).
        hr = pygame.Rect(x, y, half, 26)
        box(screen, hr, fill=T.TABLE, border=T.STEEL_LINE, width=1)
        pinned = u._hp_override is not None
        text(screen, F["body_sm"], f"HP  {u.hp_max}",
             (hr.x + T.S, hr.y + 6), T.BRASS if pinned else T.TX)
        if pinned:
            rs = pygame.Rect(hr.right - 78, hr.y + 4, 34, 18)
            rh = rs.collidepoint(self.mouse)
            box(screen, rs, fill=T.STEEL_HI if rh else T.STEEL, border=T.STEEL_LINE, width=0)
            text(screen, F["micro"], "auto", rs.center, T.BRASS if rh else T.TX_MUTED, center=True)
            self._hit(rs, ("hp_auto",))
        dn = pygame.Rect(hr.right - 40, hr.y + 3, 18, 20)
        up = pygame.Rect(hr.right - 20, hr.y + 3, 18, 20)
        for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
            h = br.collidepoint(self.mouse)
            box(screen, br, fill=T.STEEL_HI if h else T.STEEL, border=T.STEEL_LINE, width=0)
            text(screen, F["body_sm"], glyph, br.center, T.BRASS if h else T.TX_MUTED, center=True)
            self._hit(br, ("hp", sign))
        if hr.collidepoint(self.mouse) and not dn.collidepoint(self.mouse) and not up.collidepoint(self.mouse) and not (pinned and rs.collidepoint(self.mouse)):
            self.tooltip = hp_tooltip(u, F)
        y += 26 + T.S // 2

        dice = len(u._level_hp_rolls)
        lo, hi = self._hp_bounds(u)
        rl_pinned = u._racial_override is not None
        head = f"racial level {u.racial_level}"
        text(screen, F["body_sm"], head, (x, y + 2), T.BRASS if rl_pinned else T.TX_FAINT)
        hx = x + F["body_sm"].size(head)[0] + T.S // 2
        if rl_pinned:
            ar = pygame.Rect(hx, y, 34, 15)
            ah = ar.collidepoint(self.mouse)
            box(screen, ar, fill=T.STEEL_HI if ah else T.STEEL, border=T.STEEL_LINE, width=0)
            text(screen, F["micro"], "auto", ar.center, T.BRASS if ah else T.TX_MUTED, center=True)
            self._hit(ar, ("racial_auto",))
            hx = ar.right + T.S // 2
        text(screen, F["body_sm"], f"·  {1 + dice} hit {'die' if dice == 0 else 'dice'} " f"(d{u.race['hd']})  ·  HP rolls {lo}-{hi}" + ("  ·  HP pinned" if pinned else ""),
             (hx, y + 2), T.TX_FAINT)
        y += 20

        # --- talents ----------------------------------------------- #
        y = section(screen, F, "TALENTS", x, y + T.S // 2, w)
        ty0 = y
        col_bottom = y
        for i, track in enumerate(talents.TRACKS):
            colx = x + i * (third + T.S)
            text(screen, F["micro"], track.upper(), (colx, ty0), T.TX_MUTED)
            ty = ty0 + 16
            nodes = (talents.racial_tree(u.race["name"]) if track == "racial"
                     else talents.TREE[track])
            if not nodes:
                text(screen, F["micro"], "— none for this race yet", (colx, ty + 2), T.TX_FAINT)
            for t in nodes:
                taken = t.id in u.talents[track]
                blocked = t.requires and t.requires not in u.talents[track]
                openp = not taken and not blocked and u.picks_available(track) > 0
                indent = T.S * 2 if t.requires else 0
                tr = pygame.Rect(colx + indent, ty, third - indent, 18)
                edge = T.GREEN if taken else T.BRASS if openp else T.STEEL_LINE
                box(screen, tr, fill=T.TABLE if (taken or openp) else T.STEEL, border=edge, width=1)
                tc = T.GREEN if taken else T.BRASS if openp else T.TX_FAINT
                text(screen, F["micro"], ellipsize(t.name, F["micro"], tr.w - 2 * T.S // 2),
                     (tr.x + T.S // 2, tr.y + 4), tc)
                if taken or openp:
                    self._hit(tr, ("talent", track, t.id))
                ty += 20
            col_bottom = max(col_bottom, ty)
        y = col_bottom + T.S

        # --- languages ------------------------------------------- #
        y = section(screen, F, "LANGUAGES", x, y, w)
        cx, cy = x, y
        for lang in data.LANGUAGES:
            on = lang in u.languages
            cwid = F["body_sm"].size(lang)[0] + T.S * 2
            if cx + cwid > x + w:
                cx, cy = x, cy + 22
            lr = pygame.Rect(cx, cy, cwid, 18)
            box(screen, lr, fill=T.STEEL_HI if on else T.STEEL, border=T.BRASS if on else T.STEEL_LINE, width=1)
            text(screen, F["body_sm"], lang, (lr.x + T.S // 2, lr.y + 3), T.TX if on else T.TX_FAINT)
            self._hit(lr, ("lang", lang))
            cx += cwid + T.S // 2
        y = cy + 18 + T.S

        # --- magic ------------------------------------------------ #
        y = section(screen, F, "MAGIC", x, y, w)
        self._pick_row(screen, pygame.Rect(x, y, w, 26), "SOURCE",
                       (u.magic_source or "none").capitalize(),
                       ("picker", "magic"))
        y += 26 + T.S // 2
        if u.magic_source:
            cx, cy = x, y
            for spell in magic.SPELLS.values():
                if u.magic_source not in spell.sources:
                    continue
                on = spell.id in u.spells_known
                label = f"{spell.name}  L{spell.level}"
                cwid = F["body_sm"].size(label)[0] + T.S * 2
                if cx + cwid > x + w:
                    cx, cy = x, cy + 22
                sr = pygame.Rect(cx, cy, cwid, 18)
                box(screen, sr, fill=T.STEEL_HI if on else T.STEEL,
                    border=T.BRASS if on else T.STEEL_LINE, width=1)
                text(screen, F["body_sm"], label, (sr.x + T.S // 2, sr.y + 3),
                     T.TX if on else T.TX_FAINT)
                self._hit(sr, ("spell", spell.id))
                cx += cwid + T.S // 2
            y = cy + 18 + T.S
        else:
            text(screen, F["micro"], "no affinity — pick a source to teach spells",
                 (x, y), T.TX_FAINT)
            y += 16 + T.S

        # --- purse + gear -------------------------------------- #
        y = section(screen, F, "PURSE + GEAR", x, y, w)
        gr = pygame.Rect(x, y, w, 24)
        box(screen, gr, fill=T.TABLE, border=T.STEEL_LINE, width=1)
        text(screen, F["body_sm"], fmt_money(u.money), (gr.x + T.S, gr.y + 5), T.BRASS)
        bxx = gr.right - 4
        for step, glyph in ((10, "+10"), (1, "+1"), (-1, "−1"), (-10, "−10")):
            sw = 34
            sr = pygame.Rect(bxx - sw, gr.y + 2, sw - 2, 20)
            self._btn(screen, sr, glyph)
            self._hit(sr, ("gold", step))
            bxx -= sw
        y += 24 + T.S // 2

        wr = pygame.Rect(x, y, w, 24)
        self._pick_row(screen, wr, "WEAPON", u.equipped_weapon or "(unarmed)",
                       ("picker", "weapon"))
        y += 24 + T.S // 2
        if u.has_tongue:
            tr2 = pygame.Rect(x, y, w, 24)
            self._pick_row(screen, tr2, "TONGUE", u.equipped_tongue or "(empty)",
                           ("picker", "tongue"))
            y += 24 + T.S // 2
        arr = pygame.Rect(x, y, w, 24)
        self._pick_row(screen, arr, "ARMOR", u.equipped_armor or "(none)",
                       ("picker", "armor"))
        y += 24 + T.S // 2
        nr = pygame.Rect(x, y, w, 24)
        box(screen, nr, fill=T.TABLE, border=T.STEEL_LINE, width=1)
        text(screen, F["micro"], "NATURAL ARMOR", (nr.x + T.S, nr.centery - 5), T.TX_FAINT)
        text(screen, F["body_sm"], f"+{u.natural_armor}" if u.natural_armor else "none",
             (nr.x + T.S + F["micro"].size("NATURAL ARMOR")[0] + T.S, nr.centery - 6),
             T.BRASS if u.natural_armor else T.TX)
        dn = pygame.Rect(nr.right - 40, nr.y + 2, 18, 20)
        up = pygame.Rect(nr.right - 20, nr.y + 2, 18, 20)
        for br, sign, glyph in ((dn, -1, "−"), (up, +1, "+")):
            h = br.collidepoint(self.mouse)
            box(screen, br, fill=T.STEEL_HI if h else T.STEEL, border=T.STEEL_LINE, width=0)
            text(screen, F["body_sm"], glyph, br.center, T.BRASS if h else T.TX_MUTED, center=True)
            self._hit(br, ("natarmor", sign))
        y += 24 + T.S // 2
        tr = pygame.Rect(x, y, w, 22)
        torch_on = u.equipped_offhand == data.TORCH_ITEM
        self._btn(screen, tr, ("OFF HAND: TORCH" if torch_on else "OFF HAND: EMPTY"),
                  on=torch_on)
        self._hit(tr, ("torch",))
        y += 22 + T.S

        text(screen, F["micro"], f"PACK  ({len(u._base_inventory)})  ·  load " f"{u.load:g}/{u.carry_normal:g} kg",
             (x, y), T.TX_MUTED)
        y += 16
        for idx, (item, qty) in enumerate(list(u._base_inventory)):
            ir = pygame.Rect(x, y, w, 20)
            box(screen, ir, fill=T.STEEL, border=T.STEEL_LINE, width=1)
            label = item if qty == 1 else f"{item} ×{qty}"
            text(screen, F["body_sm"], ellipsize(label, F["body_sm"], ir.w - T.S - 78),
                 (ir.x + T.S, ir.y + 3), T.TX)
            text(screen, F["micro"], f"{items.item_weight(item) * qty:g} kg",
                 (ir.right - 26, ir.y + 4), T.TX_FAINT, right=True)
            xr = pygame.Rect(ir.right - 20, ir.y + 2, 16, 16)
            h = xr.collidepoint(self.mouse)
            text(screen, F["bodyb"], "×", xr.center, T.BLOOD if h else T.TX_MUTED, center=True)
            self._hit(xr, ("unpack", idx))
            target = None
            if item.startswith("Scroll of ") and u.magic_source:
                spell = magic.spell_for_scroll(item)
                if spell and spell.id not in u.spells_known:
                    target = spell
            elif item.startswith("Dictionary of "):
                lang = magic.language_for_dictionary(item)
                if lang and lang.name not in u.languages:
                    target = lang
            if target is not None:
                studying = u.study_target == target.id
                sr = pygame.Rect(xr.left - 48, ir.y + 2, 44, 16)
                sh = sr.collidepoint(self.mouse)
                s_col = T.BRASS if studying else (T.GREEN if sh else T.TX_MUTED)
                box(screen, sr, fill=T.STEEL_HI if sh else T.TABLE, border=s_col, width=1)
                text(screen, F["micro"], "study", sr.center, s_col, center=True)
                self._hit(sr, ("study", target.id))
            y += 22
        addr = pygame.Rect(x, y, 120, 20)
        self._btn(screen, addr, "+ ADD ITEM")
        self._hit(addr, ("picker", "additem"))
        y += 20 + T.S * 2

        content_h = y - y0                      # y0 already carries the -scroll offset
        self._scroll_max = max(0, content_h - inner.h)
        screen.set_clip(prev)
        self._clip = None
        if self._scroll_max:
            track_h = inner.h
            kh = max(24, int(track_h * inner.h / content_h))
            ky = inner.y + int((track_h - kh) * self.scroll / self._scroll_max)
            pygame.draw.rect(screen, T.STEEL_HI,
                             (rect.right - 5, ky, 3, kh), border_radius=2)

    def _scrollbar(self, screen, rect, top, pos, view_h):
        if not top:
            return
        kh = max(24, int(view_h * view_h / (view_h + top)))
        ky = rect.y + int((view_h - kh) * pos / top)
        pygame.draw.rect(screen, T.STEEL_HI, (rect.right - 5, ky, 3, kh), border_radius=2)

    def _pick_row(self, screen, rect, label, value, action):
        F = self.F
        hot = rect.collidepoint(self.mouse)
        box(screen, rect, fill=T.STEEL_HI if hot else T.TABLE, border=T.BRASS if hot else T.STEEL_LINE, width=1)
        text(screen, F["micro"], label, (rect.x + T.S, rect.centery - 5), T.TX_FAINT)
        vx = rect.x + T.S + F["micro"].size(label)[0] + T.S
        vw = rect.right - T.S - F["body_sm"].size("▾")[0] - T.S // 2 - vx
        text(screen, F["body_sm"], ellipsize(str(value), F["body_sm"], vw),
             (vx, rect.centery - 6), T.TX)
        text(screen, F["body_sm"], "▾",
             (rect.right - T.S, rect.centery - 7), T.BRASS if hot else T.TX_FAINT, right=True)
        self._hit(rect, action)

    def _edit_row(self, screen, rect, label, field, value):
        """A click-to-type row (name / age). `value` is what shows when idle; the
        typed buffer, with a caret, shows while `field` is being edited."""
        F = self.F
        editing = self.edit_field == field
        hot = rect.collidepoint(self.mouse)
        box(screen, rect, fill=T.STEEL_HI if (hot or editing) else T.TABLE, border=T.BRASS if (hot or editing) else T.STEEL_LINE, width=1)
        text(screen, F["micro"], label, (rect.x + T.S, rect.centery - 5), T.TX_FAINT)
        vx = rect.x + T.S + F["micro"].size(label)[0] + T.S
        edit_w = 0 if editing else F["micro"].size("edit")[0] + T.S
        vw = rect.right - T.S - edit_w - vx
        if editing:
            shown = self.edit_buf + "|"
            while len(shown) > 1 and F["body_sm"].size(shown)[0] > vw:
                shown = shown[1:]                 # keep the caret end in view
        else:
            shown = ellipsize(str(value) or "(auto)", F["body_sm"], vw)
        text(screen, F["body_sm"], shown, (vx, rect.centery - 6), T.TX)
        if not editing:
            text(screen, F["micro"], "edit",
                 (rect.right - T.S, rect.centery - 5), T.BRASS if hot else T.TX_FAINT, right=True)
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
        F = self.F
        u = self.unit
        lib_h = min(int(rect.h * 0.30), 40 + 30 * (len(self.library) + 1))
        lib = pygame.Rect(rect.x, rect.y, rect.w, max(120, lib_h))
        self._lib_rect = lib
        self._lib_max = max(0, 24 + 28 * len(self.library) + T.S - lib.h)
        self.lib_scroll = min(self.lib_scroll, self._lib_max)
        box(screen, lib, fill=T.STEEL, border=T.STEEL_LINE)
        text(screen, F["micro"], "NPC LIBRARY", (lib.x + T.S * 2, lib.y + T.S), T.TX_MUTED)
        text(screen, F["micro"], "npcs/", (lib.right - T.S * 2, lib.y + T.S), T.TX_FAINT, right=True)
        ly = lib.y + 24 - self.lib_scroll
        if not self.library:
            text(screen, F["body_sm"], "no saved characters yet — SAVE writes one here",
                 (lib.x + T.S * 2, ly + 2), T.TX_FAINT)
        prev = screen.get_clip()
        screen.set_clip(pygame.Rect(lib.x, lib.y + 22, lib.w, lib.h - 22 - T.S // 2))
        for row in self.library:
            rr = pygame.Rect(lib.x + T.S, ly, lib.w - 2 * T.S, 26)
            cur = row["slug"] == self.slug
            hot = rr.collidepoint(self.mouse)
            box(screen, rr, fill=T.STEEL_HI if (hot or cur) else T.TABLE, border=T.BRASS if cur else (T.STEEL_LINE if hot else T.STEEL_LINE), width=1)
            name_w = int(rr.w * 0.46)
            text(screen, F["body_sm"], ellipsize(row["name"], F["body_sm"], name_w),
                 (rr.x + T.S, rr.y + 5), T.TX)
            meta = f"{row['race']} · {row['occupation']}"
            text(screen, F["micro"], ellipsize(meta, F["micro"], rr.w - name_w - 52),
                 (rr.right - 44, rr.y + 6), T.TX_FAINT, right=True)
            if self.confirm_delete == row["slug"]:
                yb = pygame.Rect(rr.right - 40, rr.y + 3, 18, 20)
                nb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                self._btn(screen, yb, "y", on=True, danger=True)
                self._btn(screen, nb, "n")
                self._hit(yb, ("delete", row["slug"]))
                self._hit(nb, ("delete_no",))
            else:
                self._hit(rr, ("load", row["slug"]))
                xb = pygame.Rect(rr.right - 20, rr.y + 3, 18, 20)
                h = xb.collidepoint(self.mouse)
                text(screen, F["bodyb"], "×", xb.center, T.BLOOD if h else T.TX_FAINT, center=True)
                self._hit(xb, ("ask_delete", row["slug"]))
            ly += 28
        screen.set_clip(prev)
        self._scrollbar(screen, lib, self._lib_max, self.lib_scroll, lib.h)

        # --- live sheet -------------------------------------------- #
        # The read-only preview: same `gartok/ui` sheet component the sheet
        # modal uses (density="full"), so this stops being a second, plain-
        # text rendering of the same facts. The editable form stays its own
        # bespoke left-column widgets -- only this preview panel changed.
        pr = pygame.Rect(rect.x, lib.bottom + T.S * 2, rect.w,
                         rect.bottom - lib.bottom - T.S * 2)
        box(screen, pr, fill=T.STEEL, border=T.STEEL_LINE)
        ch = unit_to_ch(Combatant(u))
        self._sheet_rect = pr
        self._sheet_max = max(0, sheet_height("full", ch=ch) + T.S * 2 - pr.h)
        self.sheet_scroll = min(self.sheet_scroll, self._sheet_max)
        inner = pygame.Rect(pr.x + T.S * 2, pr.y + T.S - self.sheet_scroll, pr.w - 2 * T.S * 2, 0)
        with ui_contained(screen, pr.inflate(-T.S // 2, -T.S // 2)):
            _, tooltip = draw_sheet_card(screen, F, inner, ch, density="full",
                                         mouse=self.mouse)
        self._scrollbar(screen, pr, self._sheet_max, self.sheet_scroll, pr.h)
        if tooltip:
            self.tooltip = tooltip

    # ------------------------------------------------------------------ #
    def _draw_picker(self, screen):
        F = self.F
        kind, options, current = self.picker
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 190))
        screen.blit(veil, (0, 0))

        W, H = screen.get_size()
        ch, pad = 26, T.S * 2
        cols = 3 if len(options) > 8 else 1
        # keep the panel inside the window on any screen size
        cw = min(230, (min(W - 2 * T.S * 2, 780) - 2 * pad) // cols)
        rows = (len(options) + cols - 1) // cols
        pw = cols * cw + 2 * pad
        ph = min(H - 2 * T.S * 2, 52 + rows * ch + T.S * 2)
        panel_r = pygame.Rect((W - pw) // 2, (H - ph) // 2, pw, ph)
        box(screen, panel_r, fill=T.TABLE, border=T.BRASS, width=2)
        noun = {"additem": "an item", "occupation": "an occupation",
                "alignment": "an alignment", "armor": "armor",
                "tongue": "a tongue weapon", "magic": "a magic source"}.get(kind, f"a {kind}")
        text(screen, F["titleb"], f"pick {noun}", (panel_r.x + pad, panel_r.y + 12), T.TX)

        prev = screen.get_clip()
        screen.set_clip(panel_r.inflate(-2, -2))
        self.picker_hits = []
        for i, name in enumerate(options):
            c, rw = i % cols, i // cols
            it = pygame.Rect(panel_r.x + pad + c * cw, panel_r.y + 46 + rw * ch,
                             cw - T.S // 2, ch - T.S // 2)
            if it.bottom > panel_r.bottom - T.S * 2:
                continue
            sel = name == current
            hov = it.collidepoint(self.mouse)
            box(screen, it, fill=T.STEEL_HI if (hov or sel) else T.STEEL, border=T.BRASS if sel else (T.STEEL_LINE if hov else T.STEEL_LINE), width=1)
            text(screen, F["body_sm"], ellipsize(str(name), F["body_sm"], it.w - 2 * T.S),
                 (it.x + T.S, it.y + 4), T.BRASS if sel else T.TX)
            self.picker_hits.append((it, name))
        screen.set_clip(prev)
        text(screen, F["body_sm"], "click outside to cancel",
             (panel_r.x + pad, panel_r.bottom - 20), T.TX_FAINT)
