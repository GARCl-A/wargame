"""Guild screen: the guild's roster and character hub.

Left, every band as a collapsible list of member cards; right, the selected
member's sheet, progression and roles; a second tab for faction standing.
This module only adapts the model into the plain data the `ui/` panels draw
and routes clicks back -- the drawing lives in `ui/guild_roster.py`,
`ui/member_panel.py` and `ui/reputation_panel.py`.
"""

from types import SimpleNamespace

import pygame

from . import artwork, data, factions, magic, progression, talents, vocations, world
from .animals import STARVE_DAYS, Animal
from .combatant import Combatant
from .constants import fmt_money
from .group import BASE_CAPACITY
from .screen import Screen
from .ui import guild_panel, guild_roster, member_panel, reputation_panel
from .ui.primitives import (
    contained,
    draw_button,
    draw_tooltip,
    panel,
    scrollbar,
    set_pointer,
    smooth_circle,
    tabs,
    text,
)
from .ui.sheet_card import hp_tooltip, unit_to_ch
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

TABS = (("members", "MEMBERS"), ("guild", "GUILD"), ("reputations", "REPUTATIONS"))
FILTERS = (
    ("all", "ALL", "Every member of every group"),
    ("idle", "IDLE", "Groups waiting for orders"),
    ("busy", "BUSY", "Groups travelling, working or studying"),
    ("alerts", "ALERTS", "Members and animals that are hungry, or have a level-up waiting"),
)
ATTRIBUTE_LABELS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
                    ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))
LIST_MIN, LIST_MAX = 300, 420
FIGHT_DUE_TIP = "A fight is about to start -- this group can't change until it is over"
SCROLL_STEP = 36
FOOTER_H = 52


def _node_label(node_id):
    if not isinstance(node_id, str):
        return "Camp"
    try:
        return world.node(node_id).name
    except KeyError:
        return node_id.replace("_", " ").title()


def _token_of(unit):
    return SimpleNamespace(race=unit.race, portrait_id=getattr(unit, "portrait_id", None),
                           token=getattr(unit, "token", "?"))


def _animal_token(animal):
    return SimpleNamespace(race=animal.race, portrait_id=None, token=animal.race.get("token", "?"))


def _is_idle(group):
    return group.order is None or group.order.kind == "idle"


def _needs_attention(unit):
    return bool(unit.pending_picks) or unit.hunger_level >= 2


class GuildScreen(Screen):
    native = True

    def __init__(self, fonts, guild, on_back, on_level=None, on_manage=None, on_bank=None):
        super().__init__()
        self.fonts = fonts
        self._F = None
        self.guild = guild
        self.roster = guild.roster
        self.battles_won = guild.battles_won
        self.on_back = on_back
        self.on_level = on_level
        self.on_manage = on_manage
        self.on_bank = on_bank               # opens the read-only City vault
        self.tab = "members"
        pending = [u for u in self.roster if u.pending_picks]
        self.member = pending[0] if pending else (self.roster[0] if self.roster else None)

        self.tab_hits = []
        self.member_hits = []
        self.buttons = []
        self.accordion_hits = []
        self.filter_hits = []

        self._hot = False
        self.tooltip = None
        self._rep_scroll = 0
        self._rep_max_scroll = 0
        self._guild_scroll = 0
        self._guild_max_scroll = 0
        self._roster_scroll = 0
        self._roster_max_scroll = 0
        self._detail_scroll = 0
        self._detail_max_scroll = 0
        self._roster_right = 0               # x where the roster column ends (wheel routing)

        self.collapsed_groups = set()
        self.filter_mode = "all"

    def _ui_fonts(self):
        if self._F is None:
            self._F = ui_fonts()
        return self._F

    # ------------------------------------------------------------------ #
    def tutorial_key(self):
        return "guild.overview" if self.tab == "guild" else f"guild.{self.tab}"

    def tutorial_badge_rect(self, size):
        W, _ = size
        pad = 16 if W < 1500 else 24
        return pygame.Rect(W - pad - 28, pad - 4, 28, 28)

    # ------------------------------------------------------------------ #
    def _group_of(self, member):
        """The group holding a member -- or an animal of its herd."""
        if isinstance(member, Animal):
            return next((g for g in self.guild.groups if member in g.herd), None)
        return self.guild.group_of(member) if member is not None else None

    def _everyone(self):
        return [*self.roster, *(a for g in self.guild.groups for a in g.herd)]

    def _fight_due(self, unit):
        """The unit's group has a forced fight waiting: nothing about it may change."""
        group = self._group_of(unit)
        return group is not None and group.fight_due

    def _is_group_leader(self, unit):
        group = self.guild.group_of(unit)
        return group is not None and group.leader is unit

    def _recruited_by(self, unit):
        if not getattr(unit, "recruited_by", None):
            return None
        who = next((u for u in self.roster if u.uid == unit.recruited_by), None)
        return who.name if who else "someone long gone"

    def _scroll_by(self, attr, max_attr, delta):
        setattr(self, attr, max(0, min(getattr(self, max_attr), getattr(self, attr) + delta)))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            delta = -event.y * SCROLL_STEP
            if self.tab == "reputations":
                self._scroll_by("_rep_scroll", "_rep_max_scroll", delta)
            elif self.tab == "guild":
                self._scroll_by("_guild_scroll", "_guild_max_scroll", delta)
            elif self.mouse[0] < self._roster_right:
                self._scroll_by("_roster_scroll", "_roster_max_scroll", delta)
            else:
                self._scroll_by("_detail_scroll", "_detail_max_scroll", delta)
        elif event.type == pygame.KEYDOWN and self.tab == "reputations":
            step = {pygame.K_UP: -SCROLL_STEP, pygame.K_k: -SCROLL_STEP,
                    pygame.K_DOWN: SCROLL_STEP, pygame.K_j: SCROLL_STEP,
                    pygame.K_PAGEUP: -200, pygame.K_PAGEDOWN: 200}.get(event.key)
            if step:
                self._scroll_by("_rep_scroll", "_rep_max_scroll", step)

    def _click(self, px):
        for rect, mode in self.filter_hits:
            if rect.collidepoint(px):
                self.filter_mode = mode
                self._roster_scroll = 0
                return
        for rect, key in self.accordion_hits:
            if rect.collidepoint(px):
                self.collapsed_groups ^= {key}
                return
        for key, rect in self.buttons:
            if rect.collidepoint(px):
                self._press(key)
                return
        for rect, key in self.tab_hits:
            if rect.collidepoint(px):
                self.tab = key
                return
        for rect, unit in self.member_hits:
            if rect.collidepoint(px):
                if unit is not self.member:
                    self._detail_scroll = 0
                self.member = unit
                return

    def _press(self, key):
        m = self.member
        group = self._group_of(m)
        if isinstance(m, Animal) and key in ("level", "share_food", "group_leader", "guild_leader"):
            return
        if key == "level" and self.on_level and m is not None:
            self.on_level(m)
        elif key == "share_food" and m is not None:
            m.share_food = not m.share_food
        elif key == "group_leader" and group:
            self.guild.set_group_leader(group, m)
        elif key == "guild_leader" and m is not None:
            self.guild.set_leader(m)
        elif key == "distribute" and group and len(group.members) > 1:
            group.distribute_load()
        elif key == "vault" and self.on_bank:
            self.on_bank()
        elif key == "manage" and self.on_manage and group is not None:
            self.on_manage(group)
        elif key == "back":
            self.on_back()

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._ui_fonts()
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons, self.member_hits, self.tab_hits = [], [], []
        self.accordion_hits, self.filter_hits = [], []
        self._hot = False
        self.tooltip = None

        pending = [u for u in self.roster if u.pending_picks]
        if self.member not in self._everyone():
            self.member = pending[0] if pending else (self.roster[0] if self.roster else None)

        pad = 16 if W < 1500 else 24
        self._draw_header(screen, F, W, pad, pending)

        top, bottom = pad + 76, H - FOOTER_H - T.S * 2
        if self.tab in ("reputations", "guild"):
            self._roster_right = 0
            body = pygame.Rect(pad, top, W - 2 * pad, bottom - top)
            (self._draw_reputations if self.tab == "reputations" else self._draw_guild)(screen, F, body)
        else:
            list_w = int(min(max(W * 0.22, LIST_MIN), LIST_MAX))
            list_rect = pygame.Rect(pad, top, list_w, bottom - top)
            det_rect = pygame.Rect(pad + list_w + 16, top, W - 2 * pad - list_w - 16, bottom - top)
            self._roster_right = list_rect.right + 8
            self._draw_roster(screen, F, list_rect)
            if isinstance(self.member, Animal):
                self._draw_animal_detail(screen, F, det_rect, self.member)
            elif self.member is not None:
                self._draw_detail(screen, F, det_rect, self.member)

        self._draw_footer(screen, F, W, H, pad)
        if self.tooltip:
            draw_tooltip(screen, F, self.tooltip, self.mouse)
        set_pointer(self._hot)

    def _draw_header(self, screen, F, W, pad, pending):
        banner = (pad + 16, pad + 14)
        smooth_circle(screen, self.guild.banner_color, banner, 16)
        art = artwork.banner_icon(self.guild.banner_icon, 22, (15, 15, 20))
        if art is not None:
            screen.blit(art, art.get_rect(center=banner))
        text(screen, F["titleb"], self.guild.name or "The Guild", (pad + 40, pad - 2), T.TX)
        sub = f"{self.battles_won} battle victories  ·  {len(self.roster)} members"
        if pending:
            sub += f"  ·  {len(pending)} ready to level up"
        text(screen, F["body"], sub, (pad + 40, pad + 28), T.BRASS if pending else T.TX_MUTED)

        x = W - pad - (36 if self.tutorial_key() is not None else 0)
        for key, r in tabs(screen, F, (x, pad - 4), [t[0] for t in TABS], self.tab,
                           mpos=self.mouse, right=True).items():
            self.tab_hits.append((r, key))
            self._hot = self._hot or r.collidepoint(self.mouse)

    # ------------------------------------------------------------------ #
    def _member_data(self, unit, selected):
        badges = []
        if unit.pending_picks:
            badges.append(("LEVEL UP", T.BRASS))
        if unit.hunger_level >= 2:
            badges.append(("HUNGRY", T.BLOOD))
        if unit is self.guild.leader:
            badges.append(("GUILD LEADER", T.TX_MUTED))
        elif self._is_group_leader(unit):
            badges.append(("GROUP LEADER", T.TX_FAINT))
        return {
            "key": unit.uid, "name": unit.name, "selected": selected, "badges": badges,
            "sub": (f"{unit.race['name']} · Lv {unit.racial_level}"
                    f"  (C{unit.combat_level} W{unit.work_level})"),
            "hp": (max(0, unit.hp), unit.hp_max), "load": (unit.load, unit.carry_normal),
            "token": _token_of(unit),
        }

    def _animal_data(self, animal, grp, selected):
        badges = [("HUNGRY", T.BLOOD)] if animal.unfed_days else []
        pulled = grp.pulling(animal)
        job = f"pulls {pulled.kind.lower()}" if pulled else animal.role or "no tack"
        return {
            "key": animal.uid, "name": animal.species, "selected": selected, "badges": badges,
            "sub": f"{animal.species} · {job}",
            "hp": (max(0, animal.hp), animal.hp_max), "load": (animal.load, animal.carry_normal),
            "token": _animal_token(animal),
        }

    def _roster_bands(self):
        bands = []
        for grp in self.guild.groups:
            members = [m for m in grp.members if self._passes_filter(grp, m)]
            herd = [a for a in grp.herd if self._passes_filter(grp, a)]
            if not (members or herd) and self.filter_mode != "all":
                continue
            bands.append({
                "key": grp.gid, "name": grp.display_name, "where": _node_label(grp.node),
                "task": "Idle" if _is_idle(grp) else grp.order.kind.title(),
                "collapsed": grp.gid in self.collapsed_groups, "count": len(members),
                "members": [self._member_data(m, m is self.member) for m in members]
                           + [self._animal_data(a, grp, a is self.member) for a in herd],
            })
        return bands

    def _passes_filter(self, grp, unit):
        mode = self.filter_mode
        if mode == "idle":
            return _is_idle(grp)
        if mode == "busy":
            return not _is_idle(grp)
        if mode == "alerts":
            return bool(unit.unfed_days) if isinstance(unit, Animal) else _needs_attention(unit)
        return True

    def _draw_roster(self, screen, F, rect):
        pending = sum(1 for u in self.roster if u.pending_picks)
        footer = f"{len(self.roster)} members · {len(self.guild.groups)} groups"
        if pending:
            footer += f" · {pending} ready to level"
        hits = guild_roster.draw_guild_roster(screen, F, rect, self._roster_bands(), FILTERS,
                                              self.filter_mode, self._roster_scroll, footer, self.mouse)
        self.filter_hits = hits["filters"]
        by_gid = {g.gid: g for g in self.guild.groups}
        self.accordion_hits = [(r, k) for r, k in hits["bands"] if k in by_gid]
        by_uid = {u.uid: u for u in self._everyone()}
        self.member_hits = [(r, by_uid[k]) for r, k in hits["members"]]
        self._roster_max_scroll = max(0, hits["content_h"] - hits["view_h"])
        self._roster_scroll = min(self._roster_scroll, self._roster_max_scroll)
        if hits["tip"]:
            self.tooltip = hits["tip"]
        self._hot = self._hot or bool(hits["tip"])

    # ------------------------------------------------------------------ #
    def _draw_detail(self, screen, F, rect, unit):
        mouse = self.mouse
        panel(screen, rect)
        pad = T.S * 2
        inner = rect.inflate(-2 * pad, -2 * pad)
        gap = T.S * 3
        col_w = (inner.w - gap) // 2
        ax, bx = inner.x, inner.x + col_w + gap
        y0 = inner.y - self._detail_scroll
        mp = mouse if inner.collidepoint(mouse) else (-1, -1)

        c = Combatant(unit)
        ch = unit_to_ch(c)
        grp = self.guild.group_of(unit)
        tips = []
        with contained(screen, inner):
            y, t = self._draw_left(screen, F, ax, y0, col_w, unit, c, ch, grp, mp)
            tips.append(t)
            yb, t, hits = self._draw_right(screen, F, bx, y0, inner.w - col_w - gap, unit, grp, mp)
            tips.append(t)
            self.buttons += [(k, r.clip(inner)) for k, r in hits if r.colliderect(inner)]
        self._detail_max_scroll = max(0, max(y, yb) - y0 - inner.h)
        self._detail_scroll = min(self._detail_scroll, self._detail_max_scroll)
        if self._detail_max_scroll:
            scrollbar(screen, pygame.Rect(inner.x, inner.y, inner.w + T.S * 3, inner.h), self._detail_scroll, self._detail_max_scroll,
                      inner.h + self._detail_max_scroll)
        tip = next((t for t in tips if t), None)
        if tip:
            self.tooltip = tip
        self._hot = self._hot or any(r.collidepoint(mouse) for _, r in self.buttons)

    def _draw_animal_detail(self, screen, F, rect, animal):
        panel(screen, rect)
        inner = rect.inflate(-2 * T.S * 2, -2 * T.S * 2)
        mp = self.mouse if inner.collidepoint(self.mouse) else (-1, -1)
        grp = self._group_of(animal)
        pulled = grp.pulling(animal) if grp else None
        tips = []
        x, w, y0 = inner.x, inner.w, inner.y - self._detail_scroll
        y = y0

        def run(fn, *args):
            nonlocal y
            y, t = fn(screen, F, x, y, w, *args, mp)
            tips.append(t)

        owner = grp.display_name if grp else "no group"
        with contained(screen, inner):
            self._draw_animal_blocks(run, animal, grp, pulled, owner)
        self._detail_max_scroll = max(0, y - y0 - inner.h)
        self._detail_scroll = min(self._detail_scroll, self._detail_max_scroll)
        if self._detail_max_scroll:
            scrollbar(screen, pygame.Rect(inner.x, inner.y, inner.w + T.S * 3, inner.h), self._detail_scroll,
                      self._detail_max_scroll, inner.h + self._detail_max_scroll)
        tip = next((t for t in tips if t), None)
        if tip:
            self.tooltip = tip

    def _draw_animal_blocks(self, run, animal, grp, pulled, owner):
        run(member_panel.draw_identity, {
            "name": animal.species, "token": _animal_token(animal),
            "sub": f"{animal.size} animal · kept by {owner}",
            "where": _node_label(grp.node) if grp else "Camp",
            "task": "Idle" if grp is None or _is_idle(grp) else grp.order.kind.title(),
        })
        run(member_panel.draw_vitals, {
            "hp": (max(0, animal.hp), animal.hp_max),
            "hp_tip": f"{animal.hp} of {animal.hp_max} hit points",
            "stats": [("SPD", f"{animal.speed:g} m", "Meters it covers in one move"),
                      ("SIZE", animal.size, "Body size: decides how much it can carry")],
            "attrs": [(label, animal.attributes[name], data.mod(animal.attributes[name]), False)
                      for label, name in ATTRIBUTE_LABELS],
        })
        if animal.race["ability"]:
            run(member_panel.draw_ability, {"ability": (animal.ability.name, animal.ability.effect)})
        run(member_panel.draw_animal_work, self._animal_work_rows(animal, pulled))

    @staticmethod
    def _animal_work_rows(animal, pulled):
        if animal.role == "pack":
            role = f"carries up to {animal.capacity:g} kg on its back"
        elif animal.role == "draft":
            hitched = f" -- hitched to the {pulled.kind.lower()}" if pulled else " -- not hitched"
            role = f"pulls up to {animal.pull:g} kg{hitched}"
        else:
            role = (f"idle: a Pack Saddle lets it carry {animal.back_load:g} kg, "
                    f"a Harness lets it pull {animal.draw:g} kg")
        fed = ((f"hungry {animal.unfed_days} day(s) -- starves at {STARVE_DAYS}", T.BLOOD) if animal.unfed_days
               else ("fed", T.GREEN))
        return [("TACK", animal.tack or "none", T.TX), ("ROLE", role, T.TX_MUTED),
                ("LOAD", f"{animal.load:g} / {animal.carry_normal:g} kg", T.TX_MUTED),
                ("FEED", *fed), ("VALUE", fmt_money(animal.price), T.TX_MUTED)]

    def _draw_left(self, screen, F, x, y, w, unit, c, ch, grp, mp):
        tips = []

        def run(fn, *args):
            nonlocal y
            y, t = fn(screen, F, x, y, w, *args, mp)
            tips.append(t)

        run(member_panel.draw_identity, {
            "name": unit.name, "token": _token_of(unit),
            "sub": f"{unit.race['name']} · {unit.age} yrs · {unit.alignment.capitalize()}",
            "where": _node_label(grp.node) if grp else "Camp",
            "task": "Idle" if grp is None or _is_idle(grp) else grp.order.kind.title(),
        })
        run(member_panel.draw_vitals, {
            "hp": ch["hp"], "hp_tip": hp_tooltip(unit, F),
            "stats": [("AC", ch["ac"], member_panel.format_breakdown(
                           F, "ARMOR CLASS", unit.ac_breakdown(), c.ac)),
                      ("MD", ch["md"], member_panel.format_breakdown(
                           F, "MENTAL DEFENSE", unit.md_breakdown(), c.mental_defense)),
                      ("SPD", ch["spd"], member_panel.format_breakdown(
                           F, "SPEED (SQUARES)", unit.speed_breakdown(), c.speed)),
                      ("INIT", ch["init"], member_panel.format_breakdown(
                           F, "INITIATIVE", unit.initiative_breakdown(), ch["init"]))],
            "attrs": ch["attrs"],
        })
        run(member_panel.draw_weapon, self._weapon_data(unit, c, ch))
        run(member_panel.draw_gear, self._gear_data(unit, c))
        run(member_panel.draw_ability, {"ability": ch["ability"], "langs": ch["langs"]})
        return y, next((t for t in tips if t), None)

    def _weapon_data(self, unit, c, ch):
        w = ch["weapon"]
        bab = w["hit"].split("(")[0].replace("d20", "").strip()
        src = w["hit"].split("(")[-1].rstrip(")")
        dmg = w["dmg"].split("(")[0].strip()
        reach = f"{unit.weapon['range'] * 1.5:g} m" if unit.weapon and unit.weapon.get("range") else "1.5 m"
        return {
            "name": w["nm"], "tags": w["tags"],
            "chips": [
                ("ATTACK", bab, f"Attack modifier {bab} ({src}): d20 {bab} against the target's armor class"),
                ("DAMAGE", dmg, f"{w['dmg']}: weapon dice plus strength on a hit"),
                ("REACH", reach, "Distance this weapon can strike"),
            ],
        }

    def _gear_data(self, unit, c):
        offhand = getattr(unit, "equipped_offhand", None)
        if not offhand:
            offhand = "Torch" if getattr(c, "torch_hand", False) else (
                "Lantern" if getattr(c, "lantern_hand", False) else None)
        weapon = c.weapon_name or "Unarmed"
        load, norm, mx = unit.load, unit.carry_normal, unit.carry_max
        if load > mx:
            state = ("IMMOBILE", T.BLOOD)
        elif load > norm:
            state = ("OVERLOADED  -1 SPD  -2 STR/DEX", member_panel.AMBER)
        else:
            state = ("UNENCUMBERED", T.GREEN)
        return {
            "hands": f"{weapon} + {offhand}" if offhand and offhand != "None" else weapon,
            "armor": unit.armor_name if unit.armor else "None",
            "armor_note": (f"+{unit.armor['ac']} AC" + (f"  -{unit.armor.speed_penalty} SPD"
                                                       if unit.armor.speed_penalty else "")) if unit.armor else "",
            "coins": unit.money,
            "rations": (unit.rations, unit.ability.id == "autotroph"),
            "load": (load, norm, mx), "load_state": state,
        }

    def _draw_right(self, screen, F, x, y, w, unit, grp, mp):
        tips, hits = [], []
        if self.on_level:
            n = len(unit.pending_picks)
            lb = pygame.Rect(x, y, w, T.S * 5)
            label = (f"LEVEL UP READY -- {n} PICK{'S' if n != 1 else ''}" if n else "TALENT TREE & STATS")
            draw_button(screen, F, lb, label, primary=bool(n), mpos=mp)
            hits.append(("level", lb))
            if lb.collidepoint(mp):
                tips.append("Open the talent tree: spend picks and review this member's build")
            y = lb.bottom + T.S * 2

        y, t = member_panel.draw_tracks(screen, F, x, y, w, self._tracks(unit), mp)
        tips.append(t)
        tal = [(talents.get(tid).name if talents.get(tid) else tid.title(),
                talents.get(tid).desc if talents.get(tid) else "")
               for track in talents.TRACKS for tid in unit.talents.get(track, [])]
        y, t = member_panel.draw_talents(screen, F, x, y, w, tal, mp)
        tips.append(t)
        y, t, row_hits = member_panel.draw_role_rows(screen, F, x, y, w, self._role_rows(unit, grp), mp)
        tips.append(t)
        hits += row_hits

        recruiter = self._recruited_by(unit)
        lines = [(f"Recruited by {recruiter}" if recruiter else "Founding member of the guild", T.TX_MUTED, "body_sm")]
        if getattr(unit, "arena_title", False):
            lines.append(("Champion of the Pit", T.BRASS, "body_sm"))
        if getattr(unit, "bio", ""):
            lines.append((unit.bio, T.TX_FAINT, "micro"))
        y, t = member_panel.draw_record(screen, F, x, y, w, lines, mp)
        return y, next((t for t in tips if t), None), hits

    def _role_rows(self, unit, grp):
        cap = BASE_CAPACITY + unit.mod_charisma + (unit.racial_level // 2)
        band = grp.display_name if grp else "the group"
        free_swap = self.guild.leader_swaps_used < 1
        rows = []
        if unit is self.guild.leader:
            rows.append({"key": "guild_leader", "title": "★ Guild leader", "lit": True,
                         "sub": "Adds a CHA bonus to taverna recruitment", "badge": ("CURRENT", T.GREEN),
                         "action": None, "tip": "Leads the whole guild"})
        else:
            rows.append({"key": "guild_leader", "title": "Guild leader", "badge": None,
                         "sub": "1 free transfer left" if free_swap else "No free transfer left",
                         "action": ("MAKE GUILD LEADER", free_swap, False),
                         "tip": "Make this member lead the whole guild"})
        if self._is_group_leader(unit):
            rows.append({"key": "group_leader", "title": "Group leader", "lit": False,
                         "sub": f"Leads {band} -- holds up to {cap} members",
                         "badge": ("CURRENT", T.GREEN), "action": None,
                         "tip": "Group size capacity is 3 + CHA modifier + half racial level"})
        else:
            fight_due = self._fight_due(unit)
            can = grp is not None and len(grp.members) > 1 and not fight_due
            rows.append({"key": "group_leader", "title": "Group leader", "badge": None,
                         "sub": f"Would hold up to {cap} members",
                         "action": ("MAKE GROUP LEADER", can, False),
                         "tip": (FIGHT_DUE_TIP if fight_due
                                 else f"Make this member the leader of {band}")})
        can_share = unit.ability.id != "autotroph"
        if not can_share:
            sub = "Does not eat or carry rations"
        elif unit.share_food:
            sub = "Feeds starving groupmates from its pack"
        else:
            sub = "Keeps its food in its own pack"
        rows.append({"key": "share_food", "title": "Rations", "badge": None, "sub": sub,
                     "action": ("STOP SHARING" if unit.share_food else "SHARE RATIONS", can_share, False),
                     "tip": "Pool rations so a hungry bandmate is fed first, or keep them private"})
        size = len(grp.members) if grp else 1
        fight_due = self._fight_due(unit)
        rows.append({"key": "distribute", "title": "Pack load", "badge": None,
                     "sub": (f"Even out pack items across {size} members" if size > 1
                             else "Needs two or more members in the group"),
                     "action": ("DISTRIBUTE", size > 1 and not fight_due, False),
                     "tip": (FIGHT_DUE_TIP if fight_due
                             else "Rebalances unlocked pack items by free carrying capacity")})
        return rows

    def _tracks(self, unit):
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        into_w, span_w = progression.to_next(progression.WORK_XP_THRESHOLDS, unit.work_xp)
        into_r, span_r = progression.to_next(progression.RACIAL_XP_THRESHOLDS, unit.racial_xp)
        jobs = progression.eligible_work_activities(unit.work_level, unit)
        racial = (f"Combat {unit.combat_level} + Work {unit.work_level} levels. +1 hit die per level. "
                  + (f"First racial talent at Lv 5 ({5 - unit.racial_level} to go)."
                     if unit.racial_level < 5 else "Racial talent tree unlocked."))
        tracks = [
            {"label": "Combat career", "value": f"LVL {unit.combat_level}  ({into_c}/{span_c} XP)" if span_c
             else f"LVL {unit.combat_level}  (MAX)",
             "frac": into_c / span_c if span_c else 0,
             "text": f"Down standing enemies of Lv {unit.combat_level}+ (Arena, Wilds, Ambushes).",
             "tip": (f"Downing an enemy grants (enemy level - {unit.combat_level}) + 1 XP; "
                     f"enemies below Lv {unit.combat_level} grant none.")},
            {"label": "Base labor & work", "value": f"LVL {unit.work_level}  ({into_w}/{span_w} XP)" if span_w
             else f"LVL {unit.work_level}  (MAX)",
             "frac": into_w / span_w if span_w else 0,
             "text": ("Facility labor: " + ", ".join(jobs)) if jobs
             else f"No standard facilities teach past Lv {unit.work_level} yet.",
             "tip": (f"1 mark per 16 hours of facility day-labour. Activity level must be at least "
                     f"Lv {unit.work_level} to teach.")},
            {"label": "Racial maturity", "value": f"LVL {unit.racial_level}  ({into_r}/{span_r})" if span_r
             else f"LVL {unit.racial_level}  (MAX)",
             "frac": into_r / span_r if span_r else 0, "text": racial,
             "tip": "Racial XP is the sum of combat and work levels."},
        ]
        if unit.study_target:
            spell = magic.SPELLS.get(unit.study_target)
            name = spell.name if spell else unit.study_target
            need = magic.points_to_learn(spell.level if spell else 0)
            cur = min(unit.study_progress, need)
            tracks.append({"label": "Academic study", "value": f"{name}  ({cur}/{need} pts)",
                           "frac": cur / need if need else 0,
                           "text": "Studying at the taverna: daily progress toward mastery.",
                           "tip": f"Rolls 1d20 + INT per day on a Study order. {cur}/{need} points."})
        return tracks

    # ------------------------------------------------------------------ #
    def _group_task(self, grp):
        if _is_idle(grp):
            return "Idle"
        order = grp.order
        if order.kind == "garrison":
            job = getattr(order, "job", None)
            return f"Garrison ({job})" if job else "Garrison"
        return order.kind.title()

    def _notice_days(self):
        """`{uid: days left}` for everyone who has given notice."""
        day = self.guild.clock.day
        return {uid: max(0, due - day) for uid, due in self.guild.leaving.items()}

    @staticmethod
    def _days(n):
        return f"{n} day{'s' if n != 1 else ''}"

    def _group_rows(self):
        left = self._notice_days()
        notice = {}
        for u in self.roster:
            if u.uid in left:
                notice[self.guild.group_of(u).gid] = (
                    f"NOTICE: {u.name} leaves the guild in {self._days(left[u.uid])}")
        return [{"name": g.display_name, "where": _node_label(g.node), "task": self._group_task(g),
                 "size": len(g.members), "capacity": g.capacity, "over": g.overextension,
                 "note": notice.get(g.gid, "")} for g in self.guild.groups]

    def _notices(self):
        """Banners for the top of the GUILD tab: whoever is about to walk out
        (bad), then any overextended group nobody has given notice from yet (warn)."""
        left = self._notice_days()
        out = [(f"{u.name} has given notice and leaves the guild in {self._days(left[u.uid])} -- "
                + f"{self.guild.group_of(u).display_name} is over capacity with no free slot.", "bad")
               for u in self.roster if u.uid in left]
        warned = {self.guild.group_of(u) for u in self.roster if u.uid in left}
        if not self.guild.free_slots:
            out += [(f"{g.display_name} is over capacity and the guild has no free slot: "
                     + "its weakest member may give notice any day.", "warn")
                    for g in self.guild.groups if g.overextension and g not in warned]
        day = self.guild.clock.day
        out += [(f"{g.display_name} cannot control its herd: an animal strays in "
                 + f"{self._days(max(0, g.herd_notice - day))}.", "warn")
                for g in self.guild.groups if g.herd_notice is not None]
        return out

    def _holdings(self):
        guild, house = self.guild, self.guild.house
        out = []
        if not house.owned:
            out.append(("City house", "NOT OWNED", "muted", "Buy one from the Bankers in the City."))
        elif house.squatting:
            out.append(("City house", "SQUATTED", "bad", "Unpaid tax: the guard raids it."))
        elif house.missed_payments:
            out.append(("City house", "BEHIND ON TAX", "warn",
                        f"{house.missed_payments} missed payment{'s' if house.missed_payments != 1 else ''}."))
        else:
            out.append(("City house", "OWNED", "good", "Tax paid up."))

        stage = guild.wilds_claim_stage
        held = any(g.node == world.WILDS_TERRITORY_NODE and g.order is not None
                   and g.order.kind == "garrison" and not g.empty for g in guild.groups)
        if stage == "NONE":
            out.append(("The Claim", "NOT CLAIMED", "muted", "Scout it from the Wilds to start."))
        elif stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
            out.append(("The Claim", "SEIZED", "bad", "Travel there and beat the occupiers to retake it."))
        elif stage == "ESTABLISHED":
            out.append(("The Claim", "HELD" if held else "UNGUARDED", "good" if held else "warn",
                        "A garrison stands on the land." if held
                        else "An unguarded claim can be seized without a fight."))
        else:
            left = guild.wilds_claim_sustain_days_left
            detail = (f"{left} days to hold it" if stage == "SUSTAINING" and left is not None
                      else "Claim campaign in progress.")
            out.append(("The Claim", stage.title(), "warn", detail))

        bank = guild.bank
        out.append(("Strongbox", "RENTED" if bank.open else "NONE", "good" if bank.open else "muted",
                    f"{bank.load:g}/{bank.capacity:g} kg used" if bank.open
                    else "Rent one at the bank in the City."))
        return [{"name": n, "status": st, "tone": tone, "detail": d} for n, st, tone, d in out]

    def _vocation(self):
        voc = vocations.of(self.guild)
        return None if voc is None else {"name": voc.name, "perk": voc.perk, "dormant": not voc.active}

    def _draw_guild(self, screen, F, rect):
        guild = self.guild
        data = {
            "fame": guild.fame, "fame_next": guild.fame_to_next_slot,
            "slots": (len(guild.groups), guild.group_slots),
            "factions": [(f.name, guild.reputation.get(f.id, 0)) for f in factions.FACTIONS.values()],
            "notices": self._notices(), "groups": self._group_rows(), "bases": self._holdings(),
            "vocation": self._vocation(),
        }
        info = guild_panel.draw_guild(screen, F, rect, data, self._guild_scroll, self.mouse)
        self._guild_max_scroll = max(0, info["content_h"] - info["view_h"])
        self._guild_scroll = min(self._guild_scroll, self._guild_max_scroll)

    # ------------------------------------------------------------------ #
    def _draw_reputations(self, screen, F, rect):
        done = set(self.guild.deeds_done)
        data = []
        for fac in factions.FACTIONS.values():
            rep = self.guild.reputation.get(fac.id, 0)
            data.append({
                "name": fac.name, "blurb": fac.blurb, "rep": rep,
                "deeds": [(d.name, d.blurb, d.rep, d.id in done) for d in factions.DEEDS_BY_FACTION[fac.id]],
                "unlocks": [(u.title, u.description, rep >= u.rep_required, u.rep_required)
                            for u in factions.get_unlocks(fac.id)],
            })
        info = reputation_panel.draw_reputation(screen, F, rect, data, self._rep_scroll, self.mouse)
        self._rep_max_scroll = max(0, info["content_h"] - info["view_h"])
        self._rep_scroll = min(self._rep_scroll, self._rep_max_scroll)

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, F, W, H, pad):
        y, h, gap = H - FOOTER_H, 36, T.S * 2
        rx = W - pad

        def button(key, label, w, enabled=True, primary=False, tip=None):
            nonlocal rx
            rect = pygame.Rect(rx - w, y, w, h)
            draw_button(screen, F, rect, label, primary=primary, enabled=enabled, mpos=self.mouse)
            if enabled:
                self.buttons.append((key, rect))
            if rect.collidepoint(self.mouse):
                self._hot = self._hot or enabled
                self.tooltip = tip or self.tooltip
            rx = rect.x - gap

        button("back", "BACK TO MAP", T.S * 24, primary=True)
        if self.on_manage:
            fight_due = self._fight_due(self.member)
            button("manage", "MANAGE GEAR", T.S * 20,
                   enabled=self._group_of(self.member) is not None and not fight_due,
                   tip=(FIGHT_DUE_TIP if fight_due
                        else "Equip and swap gear between the members of the selected group"))
        has_chest = self.guild.bank.open and self.on_bank is not None
        button("vault", "VIEW CITY VAULT", T.S * 22, enabled=has_chest,
               tip=(f"See what the strongbox holds ({self.guild.bank.load:g}/{self.guild.bank.capacity:g} kg). "
                    "Moving gear needs a group at the bank." if has_chest
                    else "No strongbox yet -- rent one at the bank in the City."))
