"""Manage Gear: shuffle the roster's loadouts side by side.

The guild screen is a master-detail view -- good for reading one member, poor for
the job you do most between outings: moving gear across several members at once.
This screen fixes that. Every roster member gets a row on the left rail; pin one
(click it with nothing carried) to open its full column -- HANDS / OFF / (TONGUE)
/ BODY / PACK -- and every column, plus the rail row itself, is both a source and
a drop target. Move items by:

- **drag** an item onto a HAND / OFF / BODY slot, onto another column's body for
  its pack, or onto a rail row to hand it to someone not currently pinned;
- **click** it to pick it up and click the destination (click it again, or click
  away, to put it back);
- **shift/ctrl-click** to gather several pack items for one move; or
- **right-click** an item (or its "..." button) for a "send to..." menu -- the
  fastest way to hand a pile to a specific member's pack, or throw it away.

Built on `gartok.ui.loadout_panel`'s `rail`/`column`/`send_menu`, the same pieces
`group_screen.py` uses for a single group's members -- this is that same "band
of members, pick who's open" view, just scoped to the whole roster instead of
one group. It edits the same persistent `equipped_weapon` / `equipped_offhand` /
`equipped_armor` / `_base_inventory` the guild screen does (`LoadoutMoveMixin`),
so the next battle re-seeds every `Combatant` from the new loadout.
`native = True`. `on_back()` returns to the guild screen.
"""

import pygame

from . import chest, data, magic, missions
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import PackColumnMixin
from .screen import Screen
from .theme import set_pointer
from .ui import loadout_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

RAIL_W = 230
COL_MIN, COL_MAX = 300, 420


class GearScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, Screen):
    native = True

    def __init__(self, fonts, guild, on_back):
        super().__init__()
        self.fonts = fonts                   # legacy theme.Fonts -- unused, kept for the ctor's existing shape
        self._F = None
        self.guild = guild
        self.roster = guild.roster
        self.on_back = on_back
        self.pinned = list(self.roster)      # members shown as full columns, clamped to fit at draw time
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"|"offhand"|"tongue"|"armor" or a pack index
        self.menu = None                     # send-to/context menu, see `_open_menu`
        self.notice = None                   # last chest-opening/study result, shown in the footer
        self.zones = []                     # [(rect, unit|None, "hand"|"offhand"|"tongue"|"armor"|"pack"|"discard")]
        self.sources = []                  # [(rect, unit, loc)]
        self.buttons = []                  # [(key, rect)]
        self._dots_hits = []              # [(rect, unit, loc)] -- the "..." button, opens the menu directly
        self._rail_hits = []              # [(rect, unit)] -- also the drop targets `_zone_at` reuses
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._unit_by_uid = {u.uid: u for u in self.roster}
        self.back_rect = None

    # ------------------------------------------------------------------ #
    # soft tutorial (screen.py)                                          #
    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "gear"

    def _ui_fonts(self):
        if getattr(self, "_F", None) is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    # input                                                              #
    # ------------------------------------------------------------------ #
    def _source_at(self, px):
        if self._lock_at(px) is not None or self._dots_at(px) is not None:
            return None
        for rect, unit, loc in self.sources:
            if rect.collidepoint(px):
                return (unit, loc)
        return None

    def _dots_at(self, px):
        for rect, unit, loc in getattr(self, "_dots_hits", []):
            if rect.collidepoint(px):
                return (unit, loc)
        return None

    def _zone_at(self, px):
        for rect, unit, zone in self.zones:
            if rect.collidepoint(px):
                return (unit, zone)
        return None

    def _begin_drag(self, src):
        if src not in self.selected:
            self.selected = [src]

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self._rail_rect and self._rail_rect.collidepoint(self.mouse):
                self._rail_scroll = max(0, min(self._rail_max_scroll,
                                               self._rail_scroll - event.y * 40))
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.menu:
            self._menu_click(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._open_menu(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.menu = None
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        lock_hit = self._lock_at(px)
        if lock_hit is not None:
            lock_hit[0].toggle_lock(lock_hit[1])
            return

        dots_hit = self._dots_at(px)
        if dots_hit is not None:
            self._open_menu(px, picks=[dots_hit])
            return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                if key == "back":
                    self.on_back()
                elif key == "distribute":
                    self._distribute_load()
                return

        mods = pygame.key.get_mods()
        if src is not None and mods & (pygame.KMOD_SHIFT | pygame.KMOD_CTRL):
            if src in self.selected:
                self.selected.remove(src)
            else:
                self.selected.append(src)
            return

        if self.selected:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            elif src in self.selected:
                self.selected.remove(src)
            elif src is not None:
                self.selected = [src]
            else:
                self.selected = []
            return

        # nothing carried -- a plain click on a rail row toggles its pin
        # instead of picking anything up (rail rows are drop zones, never
        # `sources`)
        for rect, unit in self._rail_hits:
            if rect.collidepoint(px):
                if unit in self.pinned:
                    self.pinned.remove(unit)
                else:
                    self.pinned.append(unit)
                return

        self.selected = [src] if src is not None else []

    def _distribute_load(self):
        from . import unit as unit_module
        targets = [u for u in self.pinned if u in self.roster] or list(self.roster)
        if len(targets) <= 1:
            return
        unit_module.distribute_load(targets)
        self.notice = "Redistributed pack load across members."

    # ------------------------------------------------------------------ #
    # send-to / context menu                                             #
    # ------------------------------------------------------------------ #
    def _study_label(self, unit, target):
        return "stop studying" if unit.study_target == target.id else f"study {target.name}"

    def _open_menu(self, anchor, picks=None):
        if picks is None:
            src = self._source_at(anchor)
            if src is None:
                self.menu = None
                return
            picks = self.selected if src in self.selected else [src]
        picks = [p for p in picks if self._item_at(*p) is not None]
        if not picks:
            self.menu = None
            return
        self.selected = list(picks)

        # a member you'd only be handing their own pack items back to is a no-op
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) for p in picks)
        dests = [u for u in self.pinned if lift or id(u) not in owners]
        rows = [("member", f"to {u.name}", u) for u in dests] + [("discard", "throw away", None)]

        if len(picks) == 1 and self._item_at(*picks[0]) in (data.CHEST_ITEM, data.MISSION_CHEST_ITEM):
            rows.append(("open", "OPEN THE CHEST", None))
        if len(picks) == 1:
            unit, item = picks[0][0], self._item_at(*picks[0])
            spell = magic.spell_for_scroll(item) if item else None
            if spell and unit.magic_source and spell.id not in unit.spells_known:
                rows.append(("study", self._study_label(unit, spell), spell))
            lang = magic.language_for_dictionary(item) if item else None
            if lang and lang.name not in unit.languages:
                rows.append(("study", self._study_label(unit, lang), lang))

        self.menu = {"anchor": anchor, "rows": rows, "picks": list(picks)}

    def _menu_click(self, px):
        m = self.menu
        self.menu = None
        if m is None or not m.get("rect") or not m["rect"].collidepoint(px):
            return
        for r, kind, arg in m["hits"]:
            if not r.collidepoint(px):
                continue
            if kind == "open":
                unit, loc = m["picks"][0]
                self._open_chest(unit, self._item_at(unit, loc))
            elif kind == "study":
                unit = m["picks"][0][0]
                unit.study_target = None if unit.study_target == arg.id else arg.id
                self.selected = []
            else:
                self.selected = list(m["picks"])
                self._give_many(arg, "pack" if kind == "member" else "discard")
            return

    def _draw_menu(self, screen):
        F = self._ui_fonts()
        res = loadout_panel.send_menu(screen, F, self.menu["anchor"], self.menu["rows"], self.mouse)
        self.menu["rect"], self.menu["hits"] = res["rect"], res["hits"]

    def _open_chest(self, unit, item):
        """Pick the lock right where the chest sits -- no move, no drop, just
        the roll. A miss costs nothing (the chest stays put, try again any
        time), so this never asks for confirmation. `item` is whichever chest
        was actually right-clicked (not just "does `unit` have one somewhere"
        -- a unit could carry both kinds at once, e.g. via the sandbox
        editor). The Bankers' own sealed chest (`data.MISSION_CHEST_ITEM`)
        picks the same lock but fails its mission and marks a crime on a hit
        -- `missions.open_mission_chest`, not `chest.try_open`."""
        sealed = item == data.MISSION_CHEST_ITEM
        opened, gems = (missions.open_mission_chest(self.guild, unit) if sealed
                       else chest.try_open(unit))
        if not opened:
            self.notice = f"{unit.name} can't pick the lock -- the chest is still there."
        elif sealed:
            self.notice = (f"{unit.name} breaks the Bankers' seal -- {gems} {data.GEM_ITEM} "
                           f"spill out, but the trust mission is ruined. Crime: {unit.crime}.")
        else:
            self.notice = f"{unit.name} picks the lock -- {gems} {data.GEM_ITEM} inside."
        self.selected = []

    # ------------------------------------------------------------------ #
    # adapters: real Unit -> the plain dicts loadout_panel draws          #
    # ------------------------------------------------------------------ #
    def _hand_note(self, unit):
        name = unit.equipped_weapon
        if not name or name not in data.WEAPONS:
            return None
        wd = data.WEAPONS[name]
        hit_bonus, _ = unit.attack_bonus
        dn, faces = wd["damage"]
        dmg = f"{dn}d{faces}"
        if (wd["range"] == 0 or wd["thrown"]) and unit.mod_strength:
            dmg += f" {unit.mod_strength:+}"
        return f"{hit_bonus:+} hit  ·  {dmg} dmg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        if not name or name not in data.ARMOR:
            return None
        ad = data.ARMOR[name]
        return f"+{ad['ac']} AC"

    def _member_dict(self, unit, carried):
        two_handed = bool(unit.equipped_weapon) and data.WEAPONS[unit.equipped_weapon]["hands"] >= 2
        selected_locs = {loc for u, loc in self.selected if u is unit}

        def held(kind, name, note):
            return {"name": name, "note": note, "sel": kind in selected_locs,
                    "accepts": bool(carried) and any(self._fits_slot(unit, kind, n) for n in carried)}

        member = {
            "name": unit.full_name, "role": role_for(unit.occupation),
            "pending_picks": bool(unit.pending_picks),
            "kg": unit.load, "cap": unit.carry_normal,
            "hand": held("hand", unit.equipped_weapon, self._hand_note(unit)),
            "offhand": None if two_handed else held("offhand", unit.equipped_offhand, None),
            "armor": held("armor", unit.equipped_armor, self._armor_note(unit)),
            "pack": [(name, self._item_tag(name), data.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        return member

    # ------------------------------------------------------------------ #
    # RAIL / columns                                                      #
    # ------------------------------------------------------------------ #
    def _draw_rail(self, screen, F, rect):
        members = [{"key": u.uid, "name": u.name, "role": role_for(u.occupation),
                    "kg": u.load, "cap": u.carry_normal} for u in self.roster]
        pinned_keys = {u.uid for u in self.pinned}
        hits, max_scroll = loadout_panel.rail(screen, F, rect, members, pinned_keys,
                                              bool(self.selected), self._rail_scroll, self.mouse)
        self._rail_rect = rect
        self._rail_max_scroll = max_scroll
        self._rail_scroll = max(0, min(self._rail_scroll, max_scroll))
        self._rail_hits = [(r, self._unit_by_uid[uid]) for r, uid in hits]
        for r, u in self._rail_hits:
            self.zones.append((r, u, "pack"))

    def _draw_columns(self, screen, F, area):
        gap = T.S * 2
        shown = [u for u in self.pinned if u in self.roster]
        cap = max(1, (area.w + gap) // (COL_MIN + gap))
        shown = shown[:cap]
        n = max(1, len(shown))
        col_w = min(COL_MAX, max(COL_MIN, (area.w - (n - 1) * gap) // n))
        carried = self._carried_names()

        for i, u in enumerate(shown):
            r = pygame.Rect(area.x + i * (col_w + gap), area.y, col_w, area.h)
            member = self._member_dict(u, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(u), 0), self.mouse)
            self._pack_scroll[id(u)] = res["scroll"]
            for kind, slot_rect in res["slot_rects"].items():
                if slot_rect is None:
                    continue
                self.zones.append((slot_rect, u, kind))
                if member[kind]["name"]:
                    self.sources.append((slot_rect, u, kind))
            self.zones.append((res["pack_zone"], u, "pack"))
            self._pack_areas.append((res["pack_area"], u))
            for pr, idx in res["pack_hits"]:
                self.sources.append((pr, u, idx))
            for lr, idx in res["lock_hits"]:
                self._lock_hits.append((lr, u, u._base_inventory[idx][0]))
            for dr, idx in res["dots_hits"]:
                self._dots_hits.append((dr, u, idx))

        hidden = len(self.pinned) - len(shown)
        if hidden > 0:
            text(screen, F["body_sm"],
                f"+{hidden} pinned but hidden -- widen the window or unpin someone",
                (area.x, area.bottom + 4), T.TX_FAINT)
        if not shown:
            text(screen, F["body"], "Pin a member on the left to see their gear.",
                area.center, T.TX_FAINT, center=True)

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = {u.uid: u for u in self.roster}
        self.pinned = [u for u in self.pinned if u in self.roster]
        self.zones, self.sources, self.buttons = [], [], []
        self._dots_hits = []
        self._pack_areas = []
        self._lock_hits = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        rail_rect = pygame.Rect(0, head.bottom, RAIL_W, H - head.bottom - T.S * 10)
        cols = pygame.Rect(rail_rect.right, head.bottom, W - rail_rect.right, rail_rect.h)

        header(screen, F, head, "Manage Gear",
              "drag onto a slot or pack, or click then click a destination  ·  "
              "shift/ctrl gathers  ·  right-click for send-to", (), None, mpos=self.mouse)
        self.back_rect = pygame.Rect(head.x, head.y, T.S * 6, head.h)

        self._draw_rail(screen, F, rail_rect)
        self._draw_columns(screen, F, cols.inflate(-T.S * 2, -T.S * 2))

        if self._carried_names():
            trash = pygame.Rect(0, 0, T.S * 22, T.S * 4)
            trash.center = (W // 2, H - T.S * 8 + T.S * 2)
            over = trash.collidepoint(self.mouse)
            pygame.draw.rect(screen, T.BLOOD if over else T.STEEL, trash)
            pygame.draw.rect(screen, T.BLOOD, trash, 1)
            text(screen, F["bodyb"], "THROW AWAY", trash.center, T.TX, center=True)
            self.zones.append((trash, None, "discard"))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "back to guild", primary=True, mpos=self.mouse)
        self.buttons.append(("back", done_r))
        if len(self.roster) > 1:
            dist_r = pygame.Rect(done_r.right + T.S * 2, H - T.S * 8, T.S * 22, T.S * 4)
            draw_button(screen, F, dist_r, "distribute load", mpos=self.mouse)
            self.buttons.append(("distribute", dist_r))
        if self.notice:
            text(screen, F["body_sm"], self.notice, (T.S * 2, H - T.S * 10), T.BRASS)

        if self.menu is not None:
            self._draw_menu(screen)

        set_pointer(self._hovering())

    def _hovering(self):
        if self.menu:
            return any(r.collidepoint(self.mouse) for r, *_ in self.menu.get("hits", ()))
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self._rail_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._dots_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._lock_hits):
            return True
        return any(r.collidepoint(self.mouse) for r, *_ in self.sources)
