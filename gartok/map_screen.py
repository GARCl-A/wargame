"""World map: give orders to groups, then advance the world.

Rebuilt on the `gartok.ui` component set (see that package's own docstring)
instead of this screen's own bespoke drawing -- the four zones are COMMAND
(clock, alerts, guild stats), ROSTER (one card per group, a gear icon
expands it to SPLIT), MAP (the node graph, free pan/zoom), and INSPECTOR
(the selected group's party and whatever it can be told to do here). This
file's own job shrinks to exactly one thing the components can't know:
adapting real `world.Node`/`Group`/`Order` objects into the dicts/blocks
those components draw.

Clicking a node issues that group a **travel order** (`orders.travel`)
instead of moving it there on the spot; INSPECTOR's per-node buttons
(fight, shop, work, ...) issue the matching order too. Nothing actually
*happens* until the clock runs, via `campaign.advance` -- it jumps the
world to the soonest order completion, resolves travel/work silently, and
hands any other kind back to `app` to play its screen. There is no manual
"advance" button: the moment every group has an order (none idle), the
clock starts chasing on its own and only stops once a group goes idle
again or something needs the player's screen -- see `_maybe_auto_advance`
and `Guild.can_auto_advance`. **MAINTENANCE** forces a short 1 h stop
instead (still through the same tick, so an order in flight stays in sync
with the clock).

A group with no order may **SPLIT** (peel some of its members into a new
group, via its own roster card) or **MERGE** (fold a co-located idle group
into it, from the INSPECTOR) -- both physical, both instant, neither costs
time.

A fixed CTA row (`_footer_cta`) always sits at the bottom of INSPECTOR, right
below MANAGE GEAR/MAINTENANCE -- same slot whether it's live or not, so
nothing ever pops a new zone in and shoves the map/roster around. Red +
enabled while `pending_event` (an ambush `app` paused the clock on -- see
`app._resolve_pending_event`) is waiting to be fought; otherwise it steps
`self.selected` to whichever other band is still idle, grey when there's
none to jump to. Neither hunger nor an ambush interrupts with a screen of
its own any more -- hunger is COMMAND's own alert icon, and the ambushed
band just shows up here as `_group_blocked`, unable to take a new order
until the CTA is clicked.

The clock itself is paused at the exact instant `pending_event` happened --
every other band can still be freely inspected, split, merged and given
orders (those just won't start moving yet), but MAINTENANCE is disabled
while it's set, so nothing can force the clock past an unresolved event.
That's what keeps `app._advance` from ever running a second time before
the CTA is clicked, which would otherwise risk clobbering whatever else
was still pending from the same tick.

A band's gear icon expands its own ROSTER card into SPLIT (peel members
off) and, right alongside it, MERGE (fold in a co-located idle band) --
both act on that card's own band, not whatever happens to be `selected`.

`on_guild` opens the roster/gear screen; `on_wipe` fires if a tick starves
the guild out entirely. Leaving to the main menu is Esc -> the pause menu
(`app`), not a button here.
"""

import pygame

from . import arena, artwork, economy, orders, world
from .screen import Screen
from .theme import set_pointer
from .ui.camera import MapCamera
from .ui.command_bar import draw_command
from .ui.inspector_panel import draw_inspector, role_for
from .ui.map_panel import draw_map, node_hit_rect
from .ui.primitives import draw_button
from .ui.roster_panel import draw_roster
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .widgets import ButtonsMixin

# fractions of window width, clamped -- same "proportional with a floor/
# ceiling" shape as ui.map_panel.draw_minimap's own sizing, so the side
# panels scale with the window instead of eating/wasting fixed pixels
ROSTER_FRAC, ROSTER_MIN, ROSTER_MAX = 0.22, 260, 360
INSPECTOR_FRAC, INSPECTOR_MIN, INSPECTOR_MAX = 0.26, 320, 440
WORK_HOURS = (4, 8, 12, 16)

KIND_TERRAIN = {"town": "town", "market": "town", "tavern": "town",
                "battle": "rock", "prison": "rock", "wilds": "green"}
WASH = {"town": T.WASH_TOWN, "rock": T.WASH_ROCK, "green": T.WASH_GREEN}
DEFAULT_REGION_R = 0.045
WILDS_REGION_R = 0.09

KIND_ICON = {"battle": ("body", "sword-tie"), "market": ("gui", "wallet"),
            "tavern": ("action", "drinking"), "town": ("gui", "house"),
            "wilds": ("action", "wolf-howl"), "prison": ("body", "imprisoned")}
WORK_ICON = ("action", "stick-splitting")


def _icon_fn(surf, node, center):
    """`map_panel.draw_map_node`'s `icon_fn` hook -- draws the app's real
    game-icons.net silhouettes instead of the component's own three
    hand-drawn glyph shapes."""
    slug = WORK_ICON if node["work"] else KIND_ICON.get(node["kind"])
    if slug is None:
        return
    img = artwork.icon(slug[0], slug[1], 20, color=T.INK)
    if img is not None:
        surf.blit(img, img.get_rect(center=center))


def _alert_icon_fn(surf, icon_key, rect, color):
    """`command_bar.draw_command`'s `icon_fn` hook, same idea as `_icon_fn`
    above but for the COMMAND bar's alert tray."""
    img = artwork.icon(icon_key[0], icon_key[1], 18, color=color)
    if img is not None:
        surf.blit(img, img.get_rect(center=rect.center))


def _party_icon_fn(surf, item, center):
    """`inspector_panel.draw_inspector`'s `party_icon` hook -- the same race
    silhouette as the unit's own token elsewhere (guild/squad/loot/...),
    tinted light instead of `theme.TOKEN_INK` since this sits on dark
    steel, not a bright token disc."""
    race_name = item[3] if len(item) > 3 else ""
    img = artwork.race_icon(race_name, 20, T.TX) if race_name else None
    if img is not None:
        surf.blit(img, img.get_rect(center=center))


def _hp_frac(u):
    return (u.hp / u.hp_max) if u.hp_max else 0.0


def _race_tag(u):
    return f"{u.race.get('name', '')} · R-Lvl {u.racial_level}"


class MapScreen(ButtonsMixin, Screen):
    native = True

    def __init__(self, fonts, guild, on_guild, on_wipe, on_advance, on_manage_group,
                pending_event=None, on_resolve_event=None):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.on_guild = on_guild
        self.on_wipe = on_wipe
        self.on_advance = on_advance
        self.on_manage_group = on_manage_group
        self._pending_event = pending_event    # (Group, Order) an ambush paused here -- see app._resolve_pending_event
        self.on_resolve_event = on_resolve_event
        # point at whichever group actually needs the player -- an ambushed
        # one outranks a merely idle one, since it's the one blocking the clock
        self.selected = (pending_event[0] if pending_event is not None else
                         next((g for g in guild.groups if not g.busy and not g.empty),
                              guild.groups[0]))
        self.split_picks = set()              # unit uids toggled to leave, while splitting
        self.notices = []                     # lines shown after a tick (route, meals, deaths)
        self.hits = []                        # [(rect, node)]
        self.buttons = []                     # [(key, rect)]
        self._hot = False

        self._F = ui_fonts()
        self._nodes = {n.id: self._node_dict(n) for n in world.NODES}
        self._region_r = {n.id: (WILDS_REGION_R if n.kind == "wilds" else DEFAULT_REGION_R)
                          for n in world.NODES}
        self._cam = MapCamera(self._nodes, min_zoom=280.0, max_zoom=2200.0, initial_zoom=650.0)
        self._pan = None                      # (anchor mouse pos, cam at anchor) while dragging
        self._split_target = None             # gid of the roster card expanded for SPLIT
        self._roster_rects = []
        self._split_member_rects = []
        self._split_confirm_rect = None
        self._merge_rects = []                # [(other_gid, rect)] -- MERGE buttons in that same card
        self._minimap_box = None
        self._minimap_params = (0.0, 0.0, 1.0)

    # ------------------------------------------------------------------ #
    # adapters: real objects -> the plain dicts gartok.ui components draw #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _node_dict(n):
        return {"pos": n.pos, "name": n.name, "terrain": KIND_TERRAIN.get(n.kind, "rock"),
                "kind": n.kind, "work": n.work}

    def _group_blocked(self, group):
        """True for the one group `self._pending_event` is paused on -- it
        can't take a new order, split, or merge until that event resolves."""
        return self._pending_event is not None and self._pending_event[0] is group

    def _is_idle(self, group):
        """A band waiting on an order: not moving/working, has members, and
        isn't the one `_group_blocked` has paused."""
        return not group.busy and not group.empty and not self._group_blocked(group)

    def _state(self, group):
        if self._group_blocked(group):
            return "AMBUSHED", T.BLOOD
        o = group.order
        if o is None or o.kind == "idle":
            return "NO ORDERS", T.BRASS
        return o.kind.upper().replace("_", " "), T.TX_MUTED

    def _order_status(self, group):
        """One-line status for a group's ROSTER card / INSPECTOR header."""
        if self._group_blocked(group):
            n = len(self._pending_event[1].pack)
            return f"ambushed -- {n} enem{'y' if n == 1 else 'ies'} block the path"
        o = group.order
        if o is None or o.kind == "idle":
            return "idle"
        if o.kind == "travel":
            dest_name = world.node(o.final_dest).name
            if o.path:                            # more waypoints still to come
                return f"→ {dest_name} via {world.node(o.dest).name} ({o.remaining:g} h)"
            return f"→ {dest_name} ({o.remaining:g} h)"
        if o.kind == "work":
            return f"working ({o.remaining:g} h left)"
        return f"heading to {o.kind} ({o.remaining:g} h)"

    def _mates_for(self, g):
        """Other idle bands standing right there -- MERGE candidates, offered
        from `g`'s own roster card once it's expanded (see roster_panel's
        SPLIT UI), never from a band that can't act on it either way."""
        return [(o.gid, o.display_name) for o in self.guild.groups
               if o is not g and o.node == g.node and not o.busy and not self._group_blocked(o)]

    def _group_dict(self, g):
        label, color = self._state(g)
        blocked = self._group_blocked(g)
        return {"key": g.gid,
                "name": g.display_name,
                "lead": g.leader.name if g.leader is not None else "",
                "at": g.node,
                "busy": g.busy,
                "needs_orders": self._is_idle(g),
                "alert": blocked,
                "state_label": label,
                "state_color": color,
                "detail": self._order_status(g),
                "rations_label": f"RATIONS: {sum(u.rations for u in g.members)}",
                "party": [(u.name, role_for(u.occupation), _hp_frac(u), u.race.get("name", "")) for u in g.members],
                "roster_members": [(u.uid, u.name, _race_tag(u)) for u in g.members],
                "mates": self._mates_for(g)}

    def _events(self):
        clock = self.guild.clock
        now = clock.hour_of_day + clock.minute_of_hour / 60
        return [(g.gid, 0, now + g.order.remaining, g.order.kind.replace("_", " "), T.TX_MUTED)
               for g in self.guild.groups if g.order is not None and g.order.kind != "idle"]

    def _messages(self):
        # the only place hunger/deadlines surface in COMMAND -- the header
        # metrics stay plain counts instead of duplicating the same warning
        msgs = []
        if arena.defense_due(self.guild):
            champ = arena.champion_of(self.guild)
            deadline = arena.defense_deadline(self.guild)
            msgs.append((f"{champ.name} must defend the Champion of the Pit by day {deadline}",
                        T.BLOOD, ("body", "sword-tie")))
        hungry = self.guild.hungry
        if hungry:
            msgs.append((f"{len(hungry)} member(s) hungry", T.BRASS, ("action", "eating")))
        if self.guild.rations == 0:
            msgs.append(("the larder is empty", T.BLOOD, ("gui", "hazard-sign")))
        return msgs

    def _metrics(self):
        return [("members", str(len(self.guild))),
               ("rations", str(self.guild.rations)),
               ("gold", str(self.guild.gold)),
               ("reputation", str(self.guild.arena_reputation))]

    def _guild_label(self):
        pending = sum(1 for u in self.guild.roster if u.pending_picks)
        return f"GUILD ({pending} LEVEL UP)" if pending else "GUILD / GEAR"

    # ------------------------------------------------------------------ #
    def update(self, dt):
        pass

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self._cam.zoom_at(pygame.mouse.get_pos(), event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (2, 3):
            if self._cam.rect.collidepoint(event.pos):
                self._pan = (event.pos, list(self._cam.cam))
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (2, 3):
            self._pan = None
        elif event.type == pygame.MOUSEMOTION and self._pan is not None:
            (ax, ay), cam0 = self._pan
            self._cam.cam = list(cam0)
            self._cam.pan_px(event.pos[0] - ax, event.pos[1] - ay)

    def handle_escape(self):
        """Esc closes an expanded SPLIT card instead of opening the pause menu."""
        if self._split_target is not None:
            self._split_target = None
            self.split_picks = set()
            return True
        return False

    def tutorial_key(self):
        # COMMAND already draws its own "?" affordance top-right -- the
        # global soft-tutorial badge (app.py/tutorial_card.py) would land
        # in that same corner and the two would overlap, so this screen
        # opts out of the shared system instead of doubling up.
        return None

    # ------------------------------------------------------------------ #
    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        """Draws through `ui.primitives.draw_button` (its disabled rendering
        included) and keeps `ButtonsMixin`'s own hit-registration bookkeeping
        (`self.buttons`/`self._hot`) -- this screen is fully on the `ui`
        component set now, whose steel/paper tokens are already this screen's
        own palette, so it no longer needs `widgets.draw_button`'s
        recolouring hooks to get there."""
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                   enabled=enabled, mpos=self.mouse, fnt=font)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    def _inspector_button(self, surf, F, rect, mpos, *, key=None, label="", sub=None,
                          primary=False, danger=False, enabled=True, font=None):
        self.add_button(surf, rect, key, label, enabled=enabled, primary=primary,
                        danger=danger, font=font, sub=sub)

    # ------------------------------------------------------------------ #
    def _here(self):
        return world.node(self.selected.node)

    def _select(self, group):
        self.selected = group

    def _issue(self, order):
        if not self.selected.busy and not self._group_blocked(self.selected):
            self.selected.order = order
            self._maybe_auto_advance()

    def _go(self, target):
        if (self.selected.busy or self._group_blocked(self.selected)
                or target.id == self.selected.node):
            return
        try:
            self.selected.order = orders.travel(self.selected, target.id)
        except ValueError:
            return
        self._maybe_auto_advance()

    def _maybe_auto_advance(self):
        """No group is left idle -- nothing else needs the player right now,
        so just run the clock (`App._advance` chases it through to the next
        real decision) instead of waiting on a click."""
        if self.guild.can_auto_advance:
            self.on_advance()

    def _group_by_gid(self, gid):
        return next((g for g in self.guild.groups if g.gid == gid), None)

    def _idle_groups(self):
        return [g for g in self.guild.groups if self._is_idle(g)]

    def _cycle_idle(self):
        """The CTA's non-urgent job: step `self.selected` to the next band
        still waiting on an order, wrapping around."""
        idle = self._idle_groups()
        if not idle:
            return
        i = idle.index(self.selected) if self.selected in idle else -1
        self.selected = idle[(i + 1) % len(idle)]

    def _footer_cta(self):
        """`(key, label, danger, enabled)` for the CTA row -- red + enabled
        while `_pending_event` blocks the clock; otherwise grey unless some
        OTHER band is idle and not already the one in view (a lone group,
        or the one idle band already selected, has nothing to jump to)."""
        if self._pending_event is not None:
            n = len(self._pending_event[1].pack)
            return ("resolve_event", f"AMBUSHED -- FIGHT ({n})", True, True)
        idle = self._idle_groups()
        enabled = any(gi is not self.selected for gi in idle)
        label = f"NEXT BAND -- {len(idle)} WAITING" if len(idle) > 1 else "NEXT BAND"
        return ("cycle_idle", label, False, enabled)

    def _confirm_split(self):
        """Splits the *expanded* card's band (`_split_target`), not whatever
        happens to be `selected` -- the gear icon doesn't select a card, so
        those can genuinely differ."""
        g = self._group_by_gid(self._split_target)
        if g is None or not self.split_picks:
            return
        chosen = [u for u in g.members if u.uid in self.split_picks]
        try:
            self.selected = self.guild.split_group(g, chosen)
        except ValueError:
            return
        self._split_target = None
        self.split_picks = set()

    def _confirm_merge(self, other_gid):
        """MERGE lives in the same expanded card as SPLIT -- folds a
        co-located idle band into `_split_target`'s, same reasoning."""
        g = self._group_by_gid(self._split_target)
        other = self._group_by_gid(other_gid)
        if g is None or other is None:
            return
        try:
            self.guild.merge_groups(g, other)
        except ValueError:
            return
        if self.selected not in self.guild.groups:
            self.selected = g
        self._split_target = None
        self.split_picks = set()

    def _click(self, pos):
        if self._split_confirm_rect is not None and self._split_confirm_rect.collidepoint(pos):
            self._confirm_split()
            return
        for member_id, rect in self._split_member_rects:
            if rect.collidepoint(pos):
                self.split_picks.symmetric_difference_update({member_id})
                return
        for mate_gid, rect in self._merge_rects:
            if rect.collidepoint(pos):
                self._confirm_merge(mate_gid)
                return

        key = self.buttons_hit(pos)
        if key is not None:
            self._handle_button(key)
            return

        if self._minimap_box is not None and self._minimap_box.collidepoint(pos):
            ox, oy, mz = self._minimap_params
            self._cam.recenter((pos[0] - ox) / mz, (pos[1] - oy) / mz)
            return

        for card_rect, gid, gear_rect in self._roster_rects:
            if gear_rect.collidepoint(pos):
                if not self._group_blocked(self._group_by_gid(gid)):
                    self._split_target = None if self._split_target == gid else gid
                    self.split_picks = set()
                return
            if card_rect.collidepoint(pos):
                self._select(self._group_by_gid(gid))
                return

        for rect, n in self.hits:
            if rect.collidepoint(pos):
                self._go(n)
                return

    def _handle_button(self, key):
        if key == "guild":
            self.on_guild()
        elif key == "resolve_event":
            self.on_resolve_event()
        elif key == "cycle_idle":
            self._cycle_idle()
        elif key == "maintain":
            self.on_advance(dt=1)
        elif key == "manage_group":
            self.on_manage_group(self.selected)
        elif key.startswith("work:"):
            self._issue(orders.work(self.guild, self.selected, int(key.split(":")[1])))
        elif key in orders.INTERACTIVE_KINDS:
            self._issue(orders.interactive(key))

    # ------------------------------------------------------------------ #
    # INSPECTOR content                                                   #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _wilds_actions():
        """The activities on offer in the wilds -- (button key, label, one-liner).
        Just Hunt for now; foraging and the like slot in here later."""
        return [("hunt", "GO HUNTING",
                 "spend the day for meat  ·  a pack may find you first")]

    def _inspector_content(self, g, here):
        if self._group_blocked(g):
            n = len(self._pending_event[1].pack)
            return [{"type": "text", "text": "Ambushed on the road!", "color": T.BLOOD},
                    {"type": "text",
                    "text": f"{n} enem{'y' if n == 1 else 'ies'} block the path -- "
                            "there is no escaping this fight.",
                    "color": T.TX_FAINT}]
        if g.busy:
            return [{"type": "text", "text": f"Busy: {self._order_status(g)}", "color": T.BRASS}]

        blocks = []
        if here.is_battle:
            defense = here.arena and arena.defense_due(self.guild)
            label = ("DEFEND YOUR TITLE" if defense else
                    "BET AT THE ARENA" if here.arena else "ATTACK")
            blocks.append({"type": "button", "key": "arena", "label": label, "primary": True})
            note = ("1v1 for the Champion of the Pit -- no stake, no backup" if defense
                   else "non-lethal · stake copper, win the purse" if here.arena
                   else "lethal combat · loot the bodies")
            blocks.append({"type": "text", "text": note, "color": T.BRASS if defense else T.TX_FAINT})
        elif here.is_market:
            blocks.append({"type": "button", "key": "market", "label": "ENTER THE MARKET"})
        elif here.is_tavern:
            blocks.append({"type": "button", "key": "recruit", "label": "ENTER THE TAVERN"})
            blocks.append({"type": "text", "text": "talk a stranger into signing with the guild",
                          "color": T.TX_FAINT})
        elif here.is_prison:
            blocks.append({"type": "button", "key": "prison", "label": "VISIT THE PRISON"})
            blocks.append({"type": "text", "text": "pay a criminal's bail for a chance to recruit them",
                          "color": T.TX_FAINT})
        elif here.work:
            blocks.append({"type": "section", "label": "work a shift"})
            blocks.append({"type": "button_row", "height": 34,
                          "items": [{"key": f"work:{h}", "label": f"{h} h"} for h in WORK_HOURS]})
            blocks.append({"type": "text",
                          "text": "trade hours of the day for copper  ·  pays little, but it's sure",
                          "color": T.TX_FAINT})
            for u in g.members:
                level = economy.lumber_level(u)
                own_axe = level >= economy.LUMBER_LEVEL_OWN_AXE
                wage = economy.LUMBER_WAGE_OWN_AXE if own_axe else economy.LUMBER_WAGE
                status = "own Axe" if own_axe else "foreman's axe"
                blocks.append({"type": "text",
                              "text": f"{u.name}: {status} -- {wage}c / "
                                      f"{economy.LUMBER_BLOCK_HOURS}h block",
                              "color": T.GREEN if own_axe else T.TX_FAINT})
            need_axe = [u for u in g.members if u.work_level > 0 and economy.lumber_level(u) == 0]
            capped = [u for u in g.members if economy.lumber_level(u) >= economy.LUMBER_LEVEL_OWN_AXE
                     and u.work_level > economy.lumber_level(u)]
            if need_axe:
                names = ", ".join(u.name for u in need_axe)
                blocks.append({"type": "wrapped_text", "color": T.BRASS,
                              "text": f"{names}: past this job bare-handed -- bring their own "
                                      "Axe for a better wage and to keep banking work XP"})
            if capped:
                names = ", ".join(u.name for u in capped)
                blocks.append({"type": "wrapped_text", "color": T.BRASS,
                              "text": f"{names}: has outgrown this job even with their own Axe "
                                      "-- no more work XP here, look for tougher work"})
        elif here.is_wilds:
            for key, label, note in self._wilds_actions():
                blocks.append({"type": "button", "key": key, "label": label})
                blocks.append({"type": "text", "text": note, "color": T.TX_FAINT})
        elif here.bank:
            blocks.append({"type": "button", "key": "bank", "label": "VISIT THE BANK"})
            if self.guild.bank_unlocked:
                blocks.append({"type": "text",
                              "text": f"strongbox: {self.guild.bank_load:g} / "
                                      f"{self.guild.bank_capacity} kg",
                              "color": T.TX_FAINT})
        else:
            blocks.append({"type": "text", "text": "Nothing happens here. A safe stop.",
                          "color": T.TX_FAINT})

        # A node's flags aren't mutually exclusive (the City is both a bank and
        # a tanner) -- checked after the kind-dispatch chain above, not nested
        # in one branch of it, so a future node can carry `tanner` on its own.
        if here.tanner:
            blocks.append({"type": "button", "key": "tanner", "label": "VISIT THE TANNER",
                          "gap_before": T.S * 2})
        if here.trust:
            blocks.append({"type": "button", "key": "trust", "label": "VISIT THE BANKERS",
                          "gap_before": T.S * 2})

        if here.forge:
            blocks.append({"type": "button", "key": "forge", "label": "VISIT THE FORGE",
                          "gap_before": T.S * 2})

        has_property_business = (self.guild.property_city_unlocked or
                                 self.guild.property_city_squatting or
                                 self.guild.bankers_debt > 0)
        if here.city_property and has_property_business:
            blocks.append({"type": "button", "key": "property", "label": "VISIT THE PROPERTY",
                          "gap_before": T.S * 2})
            if self.guild.property_city_repossession_due:
                note, col = "the Bankers want the house back, or the tax paid", T.BLOOD
            elif self.guild.property_city_squatting:
                note, col = "squatting -- the guard can still come to clear it out", T.BRASS
            elif self.guild.property_city_unlocked:
                note = (f"house: {self.guild.property_city_load:g} / "
                       f"{economy.CITY_PROPERTY_CAPACITY} kg")
                col = T.TX_FAINT
            else:
                note, col = f"owes the Bankers {self.guild.bankers_debt} copper", T.BLOOD
            blocks.append({"type": "text", "text": note, "color": col})

        if here.claim:
            blocks.append({"type": "button", "key": "claim", "label": "THE WILDS CLAIM",
                          "gap_before": T.S * 2})
            stage = self.guild.wilds_claim_stage
            if stage == "ESTABLISHED" and self.guild.wilds_claim_owner == "seized":
                note, col = "SEIZED -- send a group to retake it", T.BLOOD
            elif stage == "ESTABLISHED":
                note, col = "established -- the guild's own ground", T.GREEN
            elif stage == "SUSTAINING":
                note, col = f"sustaining: {self.guild.wilds_claim_sustain_days_left} day(s) left", T.BRASS
            elif stage == "NONE":
                note, col = "unclaimed -- scout it to begin", T.TX_FAINT
            else:
                note, col = f"stage: {stage.title()}", T.TX_FAINT
            blocks.append({"type": "text", "text": note, "color": col})

        if here.ledger:
            blocks.append({"type": "button", "key": "ledger", "label": "VISIT THE OUTPOST",
                          "gap_before": T.S * 2})
            blocks.append({"type": "text", "text": "hand over what you're carrying, if anything's owed",
                          "color": T.TX_FAINT})

        return blocks

    def _maintenance_urgent(self):
        """Mirrors the old footer's own rule: a stop only helps if a hungry
        member can actually reach a ration -- their own pack, or a
        group-mate's shared larder."""
        hungry = self.guild.hungry
        reachable = any(u.rations for u in hungry) or any(
            u.share_food and u.rations for u in self.guild.roster)
        return bool(hungry) and reachable

    def _inspector_bottom(self, g):
        """MANAGE GEAR/MAINTENANCE only apply to a band that's actually here
        to act on them; the CTA (`_footer_cta`) is the map's own "what's
        next" pointer, not about `g` specifically, so it's always appended
        regardless."""
        items = []
        if not (g.busy or self._group_blocked(g)):
            items.append({"type": "button", "key": "manage_group", "label": "MANAGE GEAR & QUESTS"})
            urgent = self._maintenance_urgent()
            # a forced stop moves the clock -- disabled while `_pending_event`
            # has it paused, so nothing can advance past an unresolved event
            paused = self._pending_event is not None
            items.append({"type": "button", "key": "maintain", "label": "MAINTENANCE  ·  1 h",
                         "gap_before": T.S * 2, "primary": urgent and not paused,
                         "danger": self.guild.rations == 0 and not paused,
                         "enabled": not paused,
                         "height": T.S * 6 if urgent else T.S * 5})
        key, label, danger, enabled = self._footer_cta()
        items.append({"type": "button", "key": key, "label": label, "gap_before": T.S * 2,
                     "primary": enabled, "danger": danger, "enabled": enabled})
        return items

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        F = self._F
        self._reset_buttons()

        roster_w = max(ROSTER_MIN, min(ROSTER_MAX, round(W * ROSTER_FRAC)))
        inspector_w = max(INSPECTOR_MIN, min(INSPECTOR_MAX, round(W * INSPECTOR_FRAC)))
        cmd = pygame.Rect(0, 0, W, T.S * 9)
        margin = T.S * 2
        bh = H - cmd.bottom - margin
        left = pygame.Rect(0, cmd.bottom, roster_w, bh)
        right = pygame.Rect(W - inspector_w, cmd.bottom, inspector_w, bh)
        mid = pygame.Rect(left.right, cmd.bottom, right.x - left.right, bh)

        groups = [self._group_dict(g) for g in self.guild.groups]

        self._minimap_box, self._minimap_params = draw_map(
            screen, F, mid, self._cam, self._nodes, world.EDGES, WASH, self._region_r,
            groups, self.selected.gid, self.mouse, icon_fn=_icon_fn)

        self.hits = [(node_hit_rect(self._cam.world_to_screen(n.pos)), n)
                    for n in world.NODES]

        clock = self.guild.clock
        cmd_hover, cmd_buttons = draw_command(
            screen, F, cmd, str(clock.day), f"{clock.hour_of_day:02d}:{clock.minute_of_hour:02d}",
            self._messages(), self._metrics(), self.mouse, guild_label=self._guild_label(),
            icon_fn=_alert_icon_fn)
        self.buttons.append(("guild", cmd_buttons["guild"]))

        (self._roster_rects, self._split_member_rects,
         self._split_confirm_rect, self._merge_rects) = draw_roster(
            screen, F, left, groups, self._events(), self.selected.gid,
            self._split_target, self.split_picks, self.mouse)

        g = self.selected
        gd = next(gd for gd in groups if gd["key"] == g.gid)
        here = self._here()
        draw_inspector(screen, F, right, gd["name"], gd["state_label"], gd["state_color"],
                       here.name, gd["party"], self._inspector_content(g, here),
                       self._inspector_bottom(g), self.mouse, button=self._inspector_button,
                       party_icon=_party_icon_fn)

        if cmd_hover:
            self._draw_tooltip(screen, cmd_hover, (W, H))
        set_pointer(self._hovering())

    def _draw_tooltip(self, screen, hover, size):
        hx, hy, htxt, hcol = hover
        t_img = self._F["body"].render(htxt, True, T.TX)
        t_rect = t_img.get_rect(midbottom=(hx, hy - 12))
        t_bg = t_rect.inflate(16, 16)
        t_bg.right = min(t_bg.right, size[0] - T.S)
        t_bg.left = max(t_bg.left, T.S)
        t_rect.center = t_bg.center
        pygame.draw.rect(screen, T.TABLE, t_bg)
        pygame.draw.rect(screen, hcol, t_bg, 1)
        screen.blit(t_img, t_rect)

    def _hovering(self):
        if any(r.collidepoint(self.mouse) for _, r in self.buttons):
            return True
        if self._split_confirm_rect is not None and self._split_confirm_rect.collidepoint(self.mouse):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self._split_member_rects):
            return True
        if any(r.collidepoint(self.mouse) for _, r in self._merge_rects):
            return True
        if any(r.collidepoint(self.mouse) for r, _, _ in self._roster_rects):
            return True
        if not self.selected.busy:
            for rect, n in self.hits:
                if rect.collidepoint(self.mouse) and n.id != self.selected.node:
                    return True
        return False
