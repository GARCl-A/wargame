"""Everything the Group screen paints: the member rail, the bags, the wagon column, the cargo and
the quests, with the dicts each component takes (`GroupDrawMixin`, mixed into `GroupScreen`)."""

import pygame

from . import items, missions, store_column, world
from .animals import Animal
from .ui import loadout_panel, quest_panel
from .ui.inspector_panel import role_for
from .ui.primitives import draw_button, header, set_pointer, text
from .ui.tokens import T
from .wagon import Wagon

COL_MIN, COL_MAX = 300, 400              # loadout column width clamps
RAIL_W = 230


def _short(name):
    return name.split()[0][:10]


class GroupDrawMixin:
    # ------------------------------------------------------------------ #
    # split stack                                                        #
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # adapters: real Unit/Group -> the plain dicts loadout_panel draws    #
    # ------------------------------------------------------------------ #
    def _hand_note(self, unit):
        name = unit.equipped_weapon
        w = items.get(name)
        if not name or not items.is_weapon(w):
            return None
        hit_bonus, _ = unit.attack_bonus
        dn, faces = w.damage
        dmg = f"{dn}d{faces}"
        if (w.range == 0 or (w.has_trait("thrown") if hasattr(w, "has_trait") else getattr(w, "thrown", 0))) and unit.mod_strength:
            dmg += f" {unit.mod_strength:+}"
        return f"{hit_bonus:+} hit  ·  {dmg} dmg  ·  {w.weight}kg"

    @staticmethod
    def _armor_note(unit):
        name = unit.equipped_armor
        a = items.get(name)
        if not name or not items.is_armor(a):
            return None
        dex = f"max dex {a.max_dex}" if a.max_dex is not None else "no limit"
        return f"{items.armor_note(a)} · {dex} · {a.weight}kg"

    def _member_dict(self, unit, carried):
        w = items.get(unit.equipped_weapon)
        two_handed = bool(w) and w.hands >= 2
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
            "pack": [(name, unit.pack_tag(name), items.item_weight(name), qty,
                     unit.locked_of(name) > 0, idx in selected_locs)
                    for idx, (name, qty) in enumerate(unit._base_inventory)],
        }
        if unit.has_tongue:
            member["tongue"] = held("tongue", unit.equipped_tongue, None)
        member["artifact"] = held("artifact", unit.equipped_artifact, None)
        if self.group.wagons:
            riding = unit in self.group.riders
            member["action"] = {"label": "RIDES  ·  MAKE WALK" if riding else
                                "WALKS  ·  LET RIDE" if unit.afoot else "WALKS  ·  NO ROOM",
                                "enabled": riding or unit.afoot}
        return member

    def _cargo_rows(self):
        rows = []
        q = (self.cargo_search or "").strip().lower()
        for u in self._owners():
            for idx, (name, qty) in enumerate(u._base_inventory):
                if q and q not in name.lower() and q not in u.pack_tag(name).lower():
                    continue
                rows.append((u, idx, name, qty))
        rows.sort(key=lambda t: -items.item_weight(t[2]) * t[3])
        return [((u.uid, idx), name, u.pack_tag(name), items.item_weight(name), qty,
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

    def _store_dict(self, store, carried):
        selected = {loc for o, loc in self.selected if o is store}
        return store_column.store_dict(self.group, store, selected, carried)

    def _draw_bags(self, screen, F, area):
        gap = T.S * 2
        members = [u for u in self.pinned if u in self.group.members]
        other_wagons = [w for i, w in enumerate(self.group.wagons) if i != self._wagon_idx]
        stores = [*self.group.herd, *other_wagons]
        shown = members + stores
        window, col_w = self._cols.fit(len(shown), area.w, gap, COL_MIN, COL_MAX)
        shown = shown[window]
        carried = self._carried_names()

        for i, u in enumerate(shown):
            r = pygame.Rect(area.x + i * (col_w + gap), area.y, col_w, area.h)
            member = self._store_dict(u, carried) if self._is_store(u) else self._member_dict(u, carried)
            res = loadout_panel.column(screen, F, r, member, self._pack_scroll.get(id(u), 0), self.mouse)
            self._pack_scroll[id(u)] = res["scroll"]
            if not self._is_store(u):
                self.sheet_hits.append((res["sheet_rect"], u))
                if res["action_rect"] is not None and member["action"]["enabled"]:
                    self.buttons.append((f"ride:{u.uid}", res["action_rect"]))
            if isinstance(u, Wagon):
                self.zones.append((res["head_rect"], u, "hitch"))
                if res["action_rect"] is not None and member["action"]["enabled"]:
                    self.buttons.append((f"repair:{u.uid}", res["action_rect"]))
            elif isinstance(u, Animal) and u.role == "draft":
                self.sources.append((res["head_rect"], u, "hitch"))
                if res["action_rect"] is not None:
                    self.buttons.append((f"hitch:{u.uid}", res["action_rect"]))
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

        self._cols.hint(screen, F, area, self.mouse)

        hidden = len(members) - len([u for u in shown if not self._is_store(u)])
        if hidden > 0:
            msg = f"+{hidden} pinned but hidden -- scroll horizontally or unpin someone"
            text(screen, F["body_sm"], msg, (area.x, area.bottom + 24), T.TX_FAINT)
        if not shown:
            text(screen, F["body"], "Pin a member on the left to see their gear.",
                area.center, T.TX_FAINT, center=True)

    def _draw_wagon_column(self, screen, F, area):
        if not self.group.wagons:
            return
        if self._wagon_idx >= len(self.group.wagons):
            self._wagon_idx = 0
        wagon = self.group.wagons[self._wagon_idx]
        carried = self._carried_names()
        member = self._store_dict(wagon, carried)

        col_area = area
        if len(self.group.wagons) > 1:
            sel_h = T.S * 4
            btn_w = T.S * 4
            sel_rect = pygame.Rect(area.x, area.y, area.w, sel_h)
            lbl = f"{self._wagon_idx + 1} / {len(self.group.wagons)} {wagon.kind}"
            text(screen, F["body_sm"], lbl, sel_rect.center, T.TX_MUTED, center=True)
            prev_r = pygame.Rect(area.x, area.y, btn_w, sel_h)
            next_r = pygame.Rect(area.right - btn_w, area.y, btn_w, sel_h)
            draw_button(screen, F, prev_r, "<", ghost=True, mpos=self.mouse)
            draw_button(screen, F, next_r, ">", ghost=True, mpos=self.mouse)
            self.buttons.append(("wagon_prev", prev_r))
            self.buttons.append(("wagon_next", next_r))
            col_area = pygame.Rect(area.x, area.y + sel_h + 2, area.w, area.h - sel_h - 2)

        res = loadout_panel.column(screen, F, col_area, member, self._pack_scroll.get(id(wagon), 0), self.mouse)
        self._pack_scroll[id(wagon)] = res["scroll"]
        self.zones.append((res["head_rect"], wagon, "hitch"))
        if res["action_rect"] is not None and member.get("action", {}).get("enabled"):
            self.buttons.append((f"repair:{wagon.uid}", res["action_rect"]))
        for kind, slot_rect in res["slot_rects"].items():
            if slot_rect is not None:
                self.zones.append((slot_rect, wagon, kind))
                if member.get(kind, {}).get("name"):
                    self.sources.append((slot_rect, wagon, kind))
        self.zones.append((res["pack_zone"], wagon, "pack"))
        self._pack_areas.append((res["pack_area"], wagon))
        for pr, idx in res["pack_hits"]:
            self.sources.append((pr, wagon, idx))
        for lr, idx in res["lock_hits"]:
            self._lock_hits.append((lr, wagon, wagon._base_inventory[idx][0]))
        for dr, idx in res["dots_hits"]:
            self._dots_hits.append((dr, wagon, idx))

    def _draw_cargo(self, screen, F, rect):
        search_h = T.S * 4
        search_rect = pygame.Rect(rect.x, rect.y, rect.w, search_h)
        s_res = loadout_panel.cargo_search_bar(screen, F, search_rect, self.cargo_search, self.editing_search, self.mouse)
        self._search_rect = s_res["rect"]
        self._search_clear_rect = s_res["clear_rect"]
        if self._search_clear_rect is not None:
            self.buttons.append(("clear_cargo_search", self._search_clear_rect))

        rows = self._cargo_rows()
        sel_count = sum(1 for u, idx in self.selected if isinstance(idx, int))
        sel_kg = sum(items.item_weight(u._base_inventory[idx][0]) * u._base_inventory[idx][1]
                    for u, idx in self.selected
                    if isinstance(idx, int) and idx < len(u._base_inventory))

        footer_h = T.S * 7 if sel_count else 0
        table_y = search_rect.bottom + T.S
        table_h = rect.h - search_h - T.S - footer_h
        table_rect = pygame.Rect(rect.x, table_y, rect.w, table_h)
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

        if not rows:
            msg = f'No items matching "{self.cargo_search}".' if self.cargo_search else "No items in cargo."
            text(screen, F["body_sm"], msg, (table_rect.x + T.S * 4, table_rect.y + T.S * 6), T.TX_FAINT)

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
                "tags": getattr(t, "tags", ()),
                "accepted_by": unit.name if unit else "Unknown",
                "days_left": missions.days_left(self.guild, m),
                "progress": progress,
            })

        bottom = quest_panel.quest_list(screen, F, area, quests, empty_label="No active quests for this group.")
        today = self.guild.clock.day
        rows = [{"key": c.unit.uid, "name": c.name, "race": c.unit.race["name"],
                 "days_left": c.days_left(today)} for c in self.group.captives]
        below = pygame.Rect(area.x, bottom + T.S * 2, area.w, area.bottom - bottom - T.S * 2)
        hits = quest_panel.captive_list(screen, F, below, rows, self.mouse)
        self.buttons.extend((f"release:{key}", r) for r, key in hits)

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self._unit_by_uid = self._owners_by_uid()
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
        has_wagon = bool(self.group.wagons)
        wagon_w = min(320, max(260, (W - RAIL_W) // 4)) if has_wagon else 0
        mid_w = W - left.right - (wagon_w + T.S * 2 if has_wagon else 0)
        mid = pygame.Rect(left.right, bar.bottom, mid_w, H - bar.bottom - T.S * 2)
        right = pygame.Rect(W - wagon_w - T.S * 2, bar.bottom, wagon_w, H - bar.bottom - T.S * 2) if has_wagon else None

        title = self.group.display_name
        order = self.group.order
        order_state = "no orders" if order is None or order.kind == "idle" else order.kind
        node_name = world.node(self.group.node).name if self.group.node else "nowhere"
        subtitle = (f"{len(self.group.members)} / {self.group.capacity} members  ·  "
                   f"{node_name}  ·  {order_state}")
        tab_rects = header(screen, F, head, "" if self.editing_name else title,
                          subtitle, ("gear", "quests"), self.tab, mpos=self.mouse,
                          has_tutorial=self.tutorial_key() is not None)
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
                ("speed", f"{self.group.speed:g} m", T.TX),
            ]
            actions = [("distribute", "distribute load")]
            if self._can_treat_sickness():
                actions.append(("treat_sickness", "treat sickness"))
            if self._can_treat_poison():
                actions.append(("treat_poison", "use antidote"))
            if self.on_cook:
                if self.group.has_campfire(self.guild.clock.seconds):
                    left = self.group.campfire_hours_left(self.guild.clock.seconds)
                    actions.append(("campfire_cook", f"campfire ({left:g}h)"))
                else:
                    actions.append(("campfire_cook", "campfire cooking"))

            res = loadout_panel.toolbar(screen, F, bar, mid.x, (("bags", "BAGS"), ("cargo", "CARGO")),
                                        self.view, metrics, actions, self.mouse)
            self.buttons.extend((f"view_{vid}", r) for r, vid in res["view_hits"])
            self.buttons.extend((key, r) for key, r in res["action_hits"])

            self._draw_rail(screen, F, left)

            if self.view == "bags":
                self._draw_bags(screen, F, mid.inflate(-T.S * 2, -T.S * 2))
            else:
                self._draw_cargo(screen, F, mid.inflate(-T.S * 2, -T.S * 2))

            if right is not None:
                self._draw_wagon_column(screen, F, right.inflate(-T.S * 1, -T.S * 2))
        else:
            self._draw_quests(screen, F, pygame.Rect(T.S * 4, bar.top + T.S * 4, W - T.S * 8, H - bar.top - T.S * 12))

        done_r = pygame.Rect(T.S * 2, H - T.S * 8, T.S * 25, T.S * 4)
        draw_button(screen, F, done_r, "back to map", primary=True, mpos=self.mouse)
        self.buttons.append(("done", done_r))
        if self.notice:
            text(screen, F["body_sm"], self.notice, (done_r.right + T.S * 2, done_r.centery - 6), T.BRASS)

        self._draw_menu(screen)

        self.draw_sheet_modal(screen, self.fonts)
        set_pointer(self._hovering())

    def _hovering(self):
        if self.menu:
            return self._menu_hovering()
        if self.split_prompt:
            return self._split_hovering()
        if self.back_rect is not None and self.back_rect.collidepoint(self.mouse):
            return True
        if self._search_rect is not None and self._search_rect.collidepoint(self.mouse):
            return True
        if self._search_clear_rect is not None and self._search_clear_rect.collidepoint(self.mouse):
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
