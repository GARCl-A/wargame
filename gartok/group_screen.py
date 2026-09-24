"""Manage Gear: shuffle the roster's loadouts side by side, two views on the
same band.

Ported from the `screen_prototypes/group_screen.py` v6 mock onto the real
`gartok.ui` component set instead of the legacy `PackColumnMixin`/`theme.py`
drawing layer `GearScreen` still uses, and wired back onto the same
drag/click plumbing the gear-management screens share (`DragSelectMixin` /
`LoadoutMoveMixin`, `gartok/dragselect.py`) -- the mock's own click-only
interaction never grew an equip gesture, so dragging an item onto a
HAND/OFF/BODY slot (or another member's column, or the rail) is how gear
actually moves here, exactly like `GearScreen`. Click-then-click-destination
still works too (a click without dragging "picks up" a source; shift/ctrl
gathers several).

This file is the adapter + input/state layer only, same split as
`map_screen.py`: it turns real `Unit`/`Group` objects into the plain dicts
`gartok/ui/loadout_panel.py`'s `rail`/`column`/`cargo_table`/`send_menu`/
`split_prompt` draw from, and translates the rects they hand back into
`self.sources`/`self.zones` (which stay `Unit`-keyed -- that's the boundary
where "component" ends and "domain" begins, same seam `LoadoutMoveMixin`
already sits on for `GearScreen`).

  RAIL   left strip, every member, always -- a compact row per member and,
         since this is *also* a drop target whether or not that member's
         column is open, the fastest way to hand something to someone not
         currently pinned. Clicking a row (with nothing carried) pins/
         unpins its full column.
  BAGS   pinned members as full columns: HAND / OFF / (TONGUE) / BODY /
         PACK, dragged exactly like `GearScreen`.
  CARGO  every stack across the whole band in one sortable table, with the
         same pick-up-and-place selection (a row is a `sources` pick, same
         as a BAGS pack row) so batch actions (send to.../split/drop) reuse
         `LoadoutMoveMixin._give_many` unchanged.

Right-click (or the send-to button in CARGO's bulk bar) opens the one send-to
menu, extended past the original with "split stack" (peels part of a stack
into its own row -- `Unit.split_pack`) and "open the chest" for a Bankers'
seal or a plain lockbox, same rules as before.

Locking a stack (`Unit.locked_items`/`toggle_lock`) only exempts it from
`distribute_load`'s automatic rebalance -- it was never a hard block on a
player picking it up by hand, so no gate is added here either.

It edits the same persistent `equipped_weapon` / `equipped_offhand` /
`equipped_tongue` / `equipped_armor` / `_base_inventory` the guild/gear
screens do, so the next battle re-seeds every `Combatant` from the new
loadout. `native = True`. `on_back()` returns to the map.
"""

import pygame

from . import chest, data, missions, world
from .dragselect import DragSelectMixin, LoadoutMoveMixin
from .packbox import PackColumnMixin
from .screen import Screen
from .sheet_panel import SheetModalMixin
from .theme import set_pointer
from .ui import loadout_panel, quest_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

COL_MIN, COL_MAX = 300, 400              # loadout column width clamps
RAIL_W = 230


def _short(name):
    return name.split()[0][:10]


class GroupScreen(PackColumnMixin, DragSelectMixin, LoadoutMoveMixin, SheetModalMixin, Screen):
    native = True

    def __init__(self, fonts, guild, group, on_back):
        super().__init__()
        self.fonts = fonts                   # legacy theme.Fonts -- only the sheet modal reads this
        self.guild = guild
        self.group = group
        self.on_back = on_back
        self.tab = "gear"
        self.view = "bags"
        self.pinned = list(self.group.members)        # columns shown in BAGS, clamped to fit at draw time
        self.selected = []                   # [(unit, loc), ...]: loc is "hand"/"offhand"/"tongue"/"armor" or a pack index
        self.menu = None                     # send-to/context menu, see `_open_menu`
        self.split_prompt = None             # {"unit","idx","name","held","amount"} while picking a split qty
        self.notice = None                   # last action's result, shown in the footer
        self.zones = []                     # [(rect, unit, "hand"|"offhand"|"tongue"|"armor"|"pack")]
        self.sources = []                  # [(rect, unit, loc)]
        self._dots_hits = []              # [(rect, unit, loc)] -- the "..." button, opens the menu directly
        self.tab_hits = []              # [(rect, tab_id)]
        self.buttons = []                  # [(key, rect)]
        self._unit_by_uid = {u.uid: u for u in self.group.members}
        self._rail_hits = []              # [(rect, unit)] -- also the drop targets `_zone_at` reuses
        self.back_rect = None                # header's back arrow -- decorative in the mock, wired here
        self._rail_rect = None
        self._rail_scroll = 0
        self._rail_max_scroll = 0
        self._cargo_rect = None
        self._cargo_scroll = 0
        self._cargo_max_scroll = 0
        self.editing_name = False
        self.name_buf = ""
        self._bulk_anchor = (0, 0)           # CARGO's "send to..." button center, set when it's drawn
        self._F = None                       # lazy: building pygame Fonts needs pygame.font initialised

    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        # GEAR/QUESTS live top-right here (matching the v6 mock's header),
        # the same corner `tutorial_card._draw_badge` always draws its
        # reopen badge in regardless of any per-screen anchor -- opts out
        # for the same reason `MapScreen.tutorial_key` does.
        return None

    def _ui_fonts(self):
        if self._F is None:
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
        for rect, unit, loc in self._dots_hits:
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
        if self.editing_name and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.group.name = self.name_buf.strip() or None
                self.editing_name = False
            elif event.key == pygame.K_ESCAPE:
                self.editing_name = False
            elif event.key == pygame.K_BACKSPACE:
                self.name_buf = self.name_buf[:-1]
            elif event.unicode and len(self.name_buf) < 24 and event.unicode.isprintable():
                self.name_buf += event.unicode
            return

        if event.type == pygame.MOUSEWHEEL:
            if self.tab == "gear" and self._rail_rect and self._rail_rect.collidepoint(self.mouse):
                self._rail_scroll = max(0, min(self._rail_max_scroll,
                                               self._rail_scroll - event.y * 40))
                return
            if (self.tab == "gear" and self.view == "cargo"
                    and self._cargo_rect and self._cargo_rect.collidepoint(self.mouse)):
                self._cargo_scroll = max(0, min(self._cargo_max_scroll,
                                                self._cargo_scroll - event.y * 40))
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.split_prompt:
            self._split_prompt_click(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.menu:
            self._menu_click(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.close_sheet_on_click():
                return
            for rect, unit in getattr(self, "sheet_hits", []):
                if rect.collidepoint(event.pos):
                    self.open_sheet(unit)
                    return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._open_menu(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.menu = None
            self.split_prompt = None
        super().handle_event(event)

    def _drop(self, px, dragging, src):
        if dragging:
            hit = self._zone_at(px)
            if hit is not None:
                self._give_many(*hit)
            return

        if self.back_rect is not None and self.back_rect.collidepoint(px):
            self.on_back()
            return

        lock_hit = self._lock_at(px)
        if lock_hit is not None:
            lock_hit[0].toggle_lock(lock_hit[1])
            return

        dots_hit = self._dots_at(px)
        if dots_hit is not None:
            self._open_menu(px, picks=[dots_hit])
            return

        for rect, tab_id in self.tab_hits:
            if rect.collidepoint(px):
                self.tab, self.selected = tab_id, []
                return

        for key, rect in self.buttons:
            if rect.collidepoint(px):
                self._handle_button(key)
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

    def _handle_button(self, key):
        if key == "done":
            self.on_back()
        elif key == "distribute":
            self.group.distribute_load()
            self.notice = "Redistributed packs by carrying capacity."
        elif key == "treat_sickness":
            self._treat_sickness()
        elif key == "rename":
            self.editing_name = True
            self.name_buf = self.group.name or ""
        elif key == "view_bags":
            self.view, self.selected = "bags", []
        elif key == "view_cargo":
            self.view, self.selected = "cargo", []
        elif key == "send_to":
            self._open_menu(self._bulk_anchor, picks=list(self.selected))
        elif key == "split":
            self._open_split_prompt()
        elif key == "drop_selected":
            self._give_many(None, "discard")
            self.notice = "Thrown away."

    def _can_treat_sickness(self):
        sick_members = [u for u in self.group.members if u.sick and not getattr(u, "medicine_attempted_today", False) and not getattr(u, "treated", False)]
        if not sick_members:
            return False
        
        for s in sick_members:
            healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != s]
            if healers:
                return True
        return False

    def _treat_sickness(self):
        sick_members = [u for u in self.group.members if u.sick and not getattr(u, "medicine_attempted_today", False) and not getattr(u, "treated", False)]
        if not sick_members:
            return
        
        target = sick_members[0]
        healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != target]
        if not healers:
            # If the only healer is the target, they can't treat themselves. But if there is another sick person, maybe we can treat them instead?
            # Find any sick member who is NOT the only healer.
            for s in sick_members:
                healers = [u for u in self.group.members if u.first_aid_charges > 0 and u != s]
                if healers:
                    target = s
                    break
            if not healers:
                self.notice = "No ally with a first-aid kit can treat this."
                return

        healer = max(healers, key=lambda u: u.mod_wisdom)
        healer.first_aid_charges -= 1
        target.medicine_attempted_today = True

        nat = data.d20()
        total = nat + healer.mod_wisdom
        
        if total >= data.FIRST_AID_DC:
            target.treated = True
            self.notice = f"{healer.name} successfully treated {target.name} (rolled {total})."
        else:
            self.notice = f"{healer.name} failed to treat {target.name} (rolled {total})."

    # ------------------------------------------------------------------ #
    # send-to / context menu                                             #
    # ------------------------------------------------------------------ #
    def _can_split(self):
        return (len(self.selected) == 1 and isinstance(self.selected[0][1], int)
                and self._qty_at(*self.selected[0]) > 1)

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

        rows = []
        if self._can_split():
            rows.append(("split", "Split stack", None))
        rows.append(("drop", "Drop", None))
        if len(picks) == 1 and self._item_at(*picks[0]) in (data.CHEST_ITEM, data.MISSION_CHEST_ITEM):
            rows.append(("open", "OPEN THE CHEST", None))

        # a member you'd only be handing their own pack items back to is a no-op
        owners = {id(p[0]) for p in picks}
        lift = len(owners) > 1 or any(isinstance(p[1], str) for p in picks)
        dests = [u for u in self.group.members if lift or id(u) not in owners]
        rows += [("member", f"to {u.name}", u.uid) for u in dests]

        self.menu = {"anchor": anchor, "rows": rows, "picks": list(picks)}

    def _menu_click(self, px):
        m = self.menu
        self.menu = None
        if m is None or not m.get("rect") or not m["rect"].collidepoint(px):
            return
        for r, kind, arg in m["hits"]:
            if not r.collidepoint(px):
                continue
            if kind == "split":
                self.selected = list(m["picks"])
                self._open_split_prompt()
            elif kind == "open":
                unit, loc = m["picks"][0]
                self._open_chest(unit, self._item_at(unit, loc))
            elif kind == "member":
                self.selected = list(m["picks"])
                self._give_many(self._unit_by_uid[arg], "pack")
            else:
                self.selected = list(m["picks"])
                self._give_many(None, "discard")
            return

    def _open_chest(self, unit, item):
        """Pick the lock right where the chest sits -- no move, no drop, just
        the roll. A miss costs nothing, so this never asks for confirmation.
        The Bankers' own sealed chest (`data.MISSION_CHEST_ITEM`) picks the
        same lock but fails its mission and marks a crime on a hit --
        `missions.open_mission_chest`, not `chest.try_open`."""
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
    # split stack                                                        #
    # ------------------------------------------------------------------ #
    def _open_split_prompt(self):
        if not self._can_split():
            self.menu = None
            return
        unit, idx = self.selected[0]
        name, held = unit._base_inventory[idx]
        self.split_prompt = {"unit": unit, "idx": idx, "name": name, "held": held,
                             "amount": max(1, held // 2)}
        self.menu = None

    def _split_prompt_click(self, px):
        p = self.split_prompt
        if p is None or not p.get("rect") or not p["rect"].collidepoint(px):
            self.split_prompt = None
            return
        for r, key in p["hits"]:
            if r.collidepoint(px):
                if key == "minus":
                    p["amount"] = max(1, p["amount"] - 1)
                elif key == "plus":
                    p["amount"] = min(p["held"] - 1, p["amount"] + 1)
                elif key == "confirm":
                    p["unit"].split_pack(p["idx"], p["amount"])
                    self.notice = f"Split {p['amount']} {p['name']} into its own stack."
                    self.selected = []
                    self.split_prompt = None
                return

    # ------------------------------------------------------------------ #
    # adapters: real Unit/Group -> the plain dicts loadout_panel draws    #
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
        return f"{hit_bonus:+} hit  ·  {dmg} dmg  ·  {wd.get('weight', 0)}kg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        if not name or name not in data.ARMOR:
            return None
        ad = data.ARMOR[name]
        dex = f"max dex {ad['max_dex']}" if ad["max_dex"] is not None else "no limit"
        return f"+{ad['ac']} AC · {dex} · {ad.get('weight', 0)}kg"

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

    def _cargo_rows(self):
        rows = []
        for u in self.group.members:
            for idx, (name, qty) in enumerate(u._base_inventory):
                rows.append((u, idx, name, qty))
        rows.sort(key=lambda t: -data.item_weight(t[2]) * t[3])
        return [((u.uid, idx), name, self._item_tag(name), data.item_weight(name), qty,
                u.locked_of(name) > 0, (u, idx) in self.selected, _short(u.name))
               for u, idx, name, qty in rows]

    # ------------------------------------------------------------------ #
    # RAIL / BAGS / CARGO                                                 #
    # ------------------------------------------------------------------ #
    def _draw_rail(self, screen, F, rect):
        members = [{"key": u.uid, "name": u.name, "role": role_for(u.occupation),
                    "kg": u.load, "cap": u.carry_normal} for u in self.group.members]
        pinned_keys = {u.uid for u in self.pinned}
        overext = self.group.overextension
        note = (f"(-{overext} mental def)", T.BLOOD, "microb") if overext > 0 else ("free", T.TX_FAINT, "micro")
        band = (f"band  ·  {len(self.group.members)} of {self.group.capacity}", *note)
        hits, max_scroll = loadout_panel.rail(screen, F, rect, members, pinned_keys,
                                              bool(self.selected), self._rail_scroll, self.mouse, band=band)

        self._rail_rect = rect
        self._rail_max_scroll = max_scroll
        self._rail_scroll = max(0, min(self._rail_scroll, max_scroll))
        self._rail_hits = [(r, self._unit_by_uid[uid]) for r, uid in hits]
        for r, u in self._rail_hits:
            self.zones.append((r, u, "pack"))

    def _draw_bags(self, screen, F, area):
        gap = T.S * 2
        shown = [u for u in self.pinned if u in self.group.members]
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
            self.sheet_hits.append((res["sheet_rect"], u))
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

    def _draw_cargo(self, screen, F, rect):
        rows = self._cargo_rows()
        sel_count = sum(1 for u, idx in self.selected if isinstance(idx, int))
        sel_kg = sum(data.item_weight(u._base_inventory[idx][0]) * u._base_inventory[idx][1]
                    for u, idx in self.selected
                    if isinstance(idx, int) and idx < len(u._base_inventory))

        footer_h = T.S * 7 if sel_count else 0
        table_rect = pygame.Rect(rect.x, rect.y, rect.w, rect.h - footer_h)
        res = loadout_panel.cargo_table(screen, F, table_rect, rows, self._cargo_scroll, self.mouse)

        self._cargo_rect = res["list_rect"]
        self._cargo_max_scroll = res["max_scroll"]
        self._cargo_scroll = res["scroll"]
        for r, (uid, idx) in res["hits"]:
            self.sources.append((r, self._unit_by_uid[uid], idx))
        for r, (uid, idx) in res["lock_hits"]:
            unit = self._unit_by_uid[uid]
            self._lock_hits.append((r, unit, unit._base_inventory[idx][0]))
        for r, (uid, idx) in res["dots_hits"]:
            self._dots_hits.append((r, self._unit_by_uid[uid], idx))

        if sel_count:
            footer_rect = pygame.Rect(rect.x, rect.bottom - footer_h, rect.w, footer_h)
            actions = [("drop_selected", "drop", True, False),
                      ("split", "split stack", self._can_split(), False),
                      ("send_to", "send to...", True, True)]
            hits = loadout_panel.cargo_bulk_bar(screen, F, footer_rect, sel_count, sel_kg, actions, self.mouse)
            for r, key in hits:
                self.buttons.append((key, r))
                if key == "send_to":
                    self._bulk_anchor = r.center

    # ------------------------------------------------------------------ #
    # QUESTS                                                              #
    # ------------------------------------------------------------------ #
    def _draw_quests(self, screen, F, area):
        uids = {u.uid for u in self.group.members}
        active = [m for m in self.guild.missions if m.state == "active" and m.unit_uid in uids]

        quests = []
        for m in active:
            t = missions.template_of(m)
            unit = self._unit_by_uid.get(m.unit_uid)
            progress = (missions.progress(self.guild, m), t.goal_qty, t.goal_item) if t.goal_qty > 0 else None
            quests.append({
                "name": t.name,
                "accepted_by": unit.name if unit else "Unknown",
                "days_left": m.deadline_day - self.guild.clock.day,
                "progress": progress,
            })

        quest_panel.quest_list(screen, F, area, quests, empty_label="No active quests for this group.")

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = {u.uid: u for u in self.group.members}
        self.zones = []
        self.sources = []
        self._dots_hits = []
        self.tab_hits = []
        self.sheet_hits = []
        self._pack_areas = []
        self._lock_hits = []
        self.buttons = []

        head = pygame.Rect(0, 0, W, T.S * 9)
        bar = pygame.Rect(0, head.bottom, W, T.S * 7)
        left = pygame.Rect(0, bar.bottom, RAIL_W, H - bar.bottom - T.S * 2)
        mid = pygame.Rect(left.right, bar.bottom, W - left.right, H - bar.bottom - T.S * 2)

        title = self.group.display_name
        order = self.group.order
        order_state = "no orders" if order is None or order.kind == "idle" else order.kind
        node_name = world.node(self.group.node).name if self.group.node else "nowhere"
        subtitle = (f"{len(self.group.members)} / {self.group.capacity} members  ·  "
                   f"{node_name}  ·  {order_state}")
        tab_rects = header(screen, F, head, "" if self.editing_name else title,
                          subtitle, ("gear", "quests"), self.tab, mpos=self.mouse)
        self.tab_hits = [(r, tab_id) for tab_id, r in tab_rects.items()]
        self.back_rect = pygame.Rect(head.x, head.y, T.S * 6, head.h)

        tw = F["titleb"].size(title)[0]
        if self.editing_name:
            title_r = pygame.Rect(T.S * 6, T.S * 2 - 2, tw + 30, 30)
            pygame.draw.rect(screen, T.STEEL_HI, title_r)
            pygame.draw.rect(screen, T.BRASS, title_r, 1)
            text(screen, F["titleb"], self.name_buf + "|", (title_r.x + 4, title_r.y), T.TX)
        rename_r = pygame.Rect(T.S * 6 + tw + T.S * 2, T.S * 2 + 4, T.S * 3, T.S * 3)
        draw_button(screen, F, rename_r, "✎", ghost=True, mpos=self.mouse)
        self.buttons.append(("rename", rename_r))

        if self.tab == "gear":
            over = self.group.total_load > self.group.total_carry_normal
            short = self.group.rations_days <= 0
            metrics = [
                ("band load", f"{self.group.total_load:.0f} / {self.group.total_carry_normal:.0f} kg",
                 T.BLOOD if over else T.TX),
                ("rations", f"{self.group.rations_days} days", T.BLOOD if short else T.TX),
            ]
            actions = [("distribute", "distribute load")]
            if self._can_treat_sickness():
                actions.append(("treat_sickness", "treat sickness"))

            res = loadout_panel.toolbar(screen, F, bar, mid.x, (("bags", "BAGS"), ("cargo", "CARGO")),
                                        self.view, metrics, actions, self.mouse)
            self.buttons.extend((f"view_{vid}", r) for r, vid in res["view_hits"])
            self.buttons.extend((key, r) for key, r in res["action_hits"])

            self._draw_rail(screen, F, left)

            if self.view == "bags":
                self._draw_bags(screen, F, mid.inflate(-T.S * 2, -T.S * 2))
            else:
                self._draw_cargo(screen, F, mid.inflate(-T.S * 2, -T.S * 2))
        else:
            self._draw_quests(screen, F, pygame.Rect(T.S * 4, bar.top + T.S * 4, W - T.S * 8, H - bar.top - T.S * 12))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "back to map", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))
        if self.notice:
            text(screen, F["body_sm"], self.notice, (done_r.right + T.S * 2, done_r.centery - 6), T.BRASS)

        if self.menu:
            res = loadout_panel.send_menu(screen, F, self.menu["anchor"], self.menu["rows"], self.mouse)
            self.menu["rect"], self.menu["hits"] = res["rect"], res["hits"]
        if self.split_prompt:
            p = self.split_prompt
            res = loadout_panel.split_prompt(screen, F, (W // 2, H // 2), p["name"], p["amount"],
                                             p["held"], self.mouse)
            p["rect"], p["hits"] = res["rect"], res["hits"]

        self.draw_sheet_modal(screen, self.fonts)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.menu:
            return any(r.collidepoint(self.mouse) for r, *_ in self.menu.get("hits", ()))
        if self.split_prompt:
            return any(r.collidepoint(self.mouse) for r, _ in self.split_prompt.get("hits", ()))
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self.tab_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, _ in self._rail_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._dots_hits):
            return True
        if any(r.collidepoint(self.mouse) for r, *_ in self._lock_hits):
            return True
        return any(r.collidepoint(self.mouse) for r, *_ in self.sources)
