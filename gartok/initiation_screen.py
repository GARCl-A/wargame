"""The INITIATION tab of a hidden sanctuary: pick who stays to board for the school's rite."""

import pygame

from . import factions, rite, world
from .constants import fmt_money
from .screen import Screen
from .ui.initiation_panel import draw_initiation
from .ui.primitives import caps, set_pointer, text, wrap
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .ui.vendor_panel import draw_vendor, draw_vendor_name


class InitiationScreen(Screen):
    native = True

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.school = rite.school_at(group.node)
        keeper = world.vendor(group.node, "shrine")
        self.vendor_card = keeper.card if keeper else None
        self.picked = None
        self.notice = None
        self.row_rects = []
        self.begin_rect = pygame.Rect(0, 0, 0, 0)
        self.leave_rect = pygame.Rect(0, 0, 0, 0)

    def tutorial_key(self):
        return "initiation"

    def handle_escape(self):
        self.on_done()
        return True

    def _member(self, uid):
        return next((u for u in self.group.members if u.uid == uid), None)

    def _status(self, u):
        if self.school in u.magic_sources:
            return f"initiated in {self.school.title()} magic"
        label, done, total = rite.stage(u, self.school)
        if label == "blood test":
            left = f"{total - done} day(s) of testing, then {rite.POINTS['blood']} learning points"
        else:
            per_day = max(1, 10.5 + u.mod_intelligence)
            left = f"{done}/{total} learning points  ·  about {round((total - done) / per_day)} day(s) left"
        boarding = "boarding  ·  " if u.rite_school == self.school else ""
        return f"{boarding}{left}  ·  INT {u.mod_intelligence:+}"

    def _terms(self):
        faction = rite.FACTION[self.school]
        have = self.guild.reputation.get(faction, 0)
        terms = [("The school", f"{factions.FACTIONS[faction].name}: reputation {have} of {rite.REP_NEEDED}",
                  have >= rite.REP_NEEDED)]
        if self.school == "faith":
            terms.append(("Up front", f"one {rite.HOLY_SYMBOL}, consumed", True))
        if self.school == "blood":
            terms.append(("Blood test", f"{rite.BLOOD_TEST_DAYS} days: only magic blood goes on; a failed test is final",
                          True))
        terms.append(("Learning", f"{rite.POINTS[self.school]} points, 1d20 + INT a day, kept if you leave", True))
        terms.append(("Board", f"${rite.BOARD_PER_DAY} a day with the meal, only on a day with no food in the pack",
                      True))
        where = ("alone, in a group of their own" if self.guild.free_slots or len(self.group.members) == 1
                 else "the whole group waits (no free group slot)")
        terms.append(("Who waits", where, True))
        terms.append(("Grants", "the school and its root in the magic talents; no spell", True))
        return terms

    def _rows(self):
        rows = []
        for u in self.group.members:
            blocked = rite.blocker(self.guild, self.group, u, self.school)
            rows.append({"key": u.uid, "name": u.name, "status": self._status(u),
                         "note": blocked or "", "enabled": blocked is None, "picked": u.uid == self.picked})
        return rows

    def _action(self):
        u = self._member(self.picked)
        if u is None or rite.blocker(self.guild, self.group, u, self.school):
            return None
        return "RESUME THE RITE" if rite.paid(u, self.school) else "BEGIN THE RITE"

    def _click(self, pos):
        if self.leave_rect.collidepoint(pos):
            self.on_done()
            return
        if self.begin_rect.collidepoint(pos) and self._action():
            ok, lines = rite.begin(self.guild, self.group, self._member(self.picked), self.school)
            self.notice = "  ".join(lines)
            if ok:
                self.picked = None
            return
        enabled = {r["key"]: r["enabled"] for r in self._rows()}
        for uid, rect in self.row_rects:
            if rect.collidepoint(pos):
                self.notice = None
                self.picked = None if self.picked == uid or not enabled[uid] else uid
                if not enabled[uid]:
                    self.notice = rite.blocker(self.guild, self.group, self._member(uid), self.school)
                return

    framed = False          # a hub's tab: the hub draws the keeper, the tabs and the back

    def hub_cards(self):
        purse = sum(u.money for u in self.group.members)
        return [{"label": "party purse", "value": fmt_money(purse), "tone": "money"}]

    def draw(self, screen):
        F = self.fonts if (isinstance(self.fonts, dict) and "body" in self.fonts) else ui_fonts()
        screen.fill(T.TABLE)
        m = T.S * 3
        sub = "Leave one member to board here until the school takes them in."
        if self.framed:
            text(screen, F["body"], sub, (m, 0), T.TX_MUTED)
            top = T.S * 5
        else:
            face = draw_vendor(screen, F, (m, m), self.vendor_card)
            caps(screen, F["head"], f"{world.node(self.group.node).name.upper()}  ·  INITIATION", (m + face, m), T.TX)
            draw_vendor_name(screen, F, (m + face, m + T.S * 4), self.vendor_card)
            text(screen, F["body"], sub, (m + face, m + T.S * 7), T.TX_MUTED)
            top = m + T.S * 11
        notice_h = 0
        if self.notice:
            lines = wrap(F["body_sm"], self.notice, screen.get_width() - 2 * m)
            for i, ln in enumerate(lines):
                text(screen, F["body_sm"], ln, (m, screen.get_height() - m - T.S * 2 - (len(lines) - i) * 18), T.BRASS)
            notice_h = len(lines) * 18 + T.S
        area = pygame.Rect(m, top, screen.get_width() - 2 * m, screen.get_height() - top - m - notice_h)
        self.row_rects, self.begin_rect, self.leave_rect = draw_initiation(
            screen, F, area, self._terms(), self._rows(), self._action(),
            None if self.framed else "LEAVE THE SANCTUARY", self.mouse)
        set_pointer(any(r.collidepoint(self.mouse) for _, r in self.row_rects)
                    or self.begin_rect.collidepoint(self.mouse) or self.leave_rect.collidepoint(self.mouse))
