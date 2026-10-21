"""Everything the Tavern screen paints: the recruits' master and detail, the study hub and its
modal, the performance and the footer (`TavernaDrawMixin`, mixed into `TavernaScreen`).
The bodies are built from the hub kit (`ui.hub_body`), whether the hub's frame is around them or not."""

import pygame

from . import economy, magic, recruit
from .archetypes import unit_archetypes
from .constants import fmt_money
from .ui import hub_body as hb
from .ui.board_render import draw_face
from .ui.hub_frame import hub_button
from .ui.loadout_panel import icon_strip
from .ui.primitives import (
    FOOTER_H,
    draw_tooltip,
    footer_bar,
    format_tooltip,
    header,
    small_caps,
    spaced,
    text,
    wrap,
)
from .ui.tokens import T, mix

_ARCHETYPE_TONE = {"brass": "money", "green": "good", "muted": "muted"}
BUTTON_H = T.S * 6
ROW_GAP = T.S


def _face(u):
    return {"race": u.race["name"], "portrait_id": getattr(u, "portrait_id", None), "token": u.token}


def _chips(unit, limit=None):
    tags = unit_archetypes(unit)[:limit] if limit else unit_archetypes(unit)
    return [(label, _ARCHETYPE_TONE.get(style, "muted")) for label, style, _desc in tags]


class TavernaDrawMixin:
    def draw(self, screen):
        F = self._F
        W, H = screen.get_size()
        screen.fill(T.TABLE)
        self.buttons.clear()
        self.cand_cards.clear()
        self.party_cards.clear()
        self._tooltips.clear()
        self._hot = False

        if self.framed:                      # the hub draws the keeper, the tabs and the back button
            content_top, content_bottom = 0, H - T.S * 4
        else:
            content_top, content_bottom = self._draw_own_header(screen, F, W, H)

        body = pygame.Rect(T.S * 5, content_top, W - T.S * 10, content_bottom - content_top)
        if self.tab == "recruits":
            self._draw_recruits_master_detail(screen, body)
        elif self.tab == "rooms":
            self._draw_study_hub(screen, body)
        elif self.tab == "perform":
            self._draw_perform(screen, body)

        if self.study_modal_member is not None:
            self._draw_study_modal(screen)

        self._draw_footer(screen, F)

        for t_rect, t_text in self._tooltips:
            if t_rect.collidepoint(self.mouse):
                draw_tooltip(screen, F, t_text, self.mouse)
                break

    def _draw_own_header(self, screen, F, W, H):
        """Out of the hub: the old header with its own tabs. Returns the body's top and bottom."""
        is_tavern = self.title == "TAVERN"
        days_left = recruit.REFRESH_DAYS - (self.guild.clock.day - 1) % recruit.REFRESH_DAYS
        if self.tab == "recruits":
            sub = f"Guild size {len(self.guild.roster)} · crowd penalty -{recruit.size_penalty(len(self.guild.roster))}"
            if is_tavern:
                sub += f" · new faces in {days_left} day(s)"
            sub += self._sub_extra()
        elif self.tab == "perform":
            sub = "Play the stage with a Musical Instrument · every hour is a Charisma test"
        else:
            sub = "Rent a quiet room for the day · anyone with a study target will make daily progress"
        tabs_list = ["RECRUIT", "STUDY", "PERFORM"] if is_tavern else []
        active_tab_label = {"recruits": "RECRUIT", "rooms": "STUDY", "perform": "PERFORM"}[self.tab]
        tab_hits = header(screen, F, pygame.Rect(0, 0, W, 72), self.title if not is_tavern else "THE TAVERN",
                          sub, tabs_list, active_tab_label, mpos=self.mouse, has_tutorial=True,
                          vendor=getattr(self, "vendor", None))
        keys = {"RECRUIT": "recruits", "STUDY": "rooms", "PERFORM": "perform"}
        for tab_name, r in tab_hits.items():
            if keys.get(tab_name) not in (None, self.tab):
                self.buttons.append((f"tab_{keys[tab_name]}", r))
        return 88, H - FOOTER_H - 12

    def _person(self, screen, rect, p):
        chips = hb.draw_person(screen, self._F, rect, p, self.mouse)
        if rect.collidepoint(self.mouse):
            self._hot = True
        return chips

    def _tip_chips(self, chips, unit):
        descs = {label: desc for label, _style, desc in unit_archetypes(unit)}
        for r, label in chips:
            if label in descs:
                self._tooltips.append((r, format_tooltip(label, descs[label], self._F)))

    # ------------------------------------------------------------------ #
    def _draw_recruits_master_detail(self, screen, body):
        F = self._F
        left_w = max(T.S * 48, min(T.S * 60, round(body.w * 0.3)))
        left = pygame.Rect(body.x, body.y, left_w, body.h)
        inner = hb.draw_panel(screen, F, left, self.LIST_LABEL.capitalize(), str(len(self.candidates)))

        if not self.candidates:
            y = inner.y
            for line in self.EMPTY_LIST.split("\n"):
                text(screen, F["hub_body"], line, (inner.x, y), T.TX_FAINT)
                y += F["hub_body"].get_linesize()
        y = inner.y
        for i, cand in enumerate(self.candidates):
            cr = pygame.Rect(inner.x - T.S, y, inner.w + T.S * 2, hb.PERSON_TALL_H)
            if cr.bottom > inner.bottom + T.S * 2:
                break
            self.cand_cards.append((cr, i))
            bail = self._bail(cand)
            chips = self._person(screen, cr, {
                "face": _face(cand), "name": cand.name,
                "sub": f"{cand.race['name']} {cand.occupation['name'].lower()}  ·  resists CHA {cand.mod_charisma:+}",
                "note": f"Speaks {', '.join(cand.languages)}" + (f"  ·  bail {fmt_money(bail)}" if bail else ""),
                "chips": _chips(cand, 3), "status": self._cand_status(cand),
                "state": "on" if i == self.sel else None})
            self._tip_chips(chips, cand)
            y += hb.PERSON_TALL_H + ROW_GAP

        right = pygame.Rect(left.right + T.S * 3, body.y, body.right - left.right - T.S * 3, body.h)
        signed = getattr(self, "signed", None)
        has_cand = self.sel is not None and self.sel < len(self.candidates)
        inner = hb.draw_panel(screen, F, right, "Dossier")
        y = inner.y
        if signed is not None:
            y = self._draw_signed_banner(screen, F, pygame.Rect(inner.x, y, inner.w, T.S * 11), signed) + T.S * 2
        if not has_cand:
            if signed is None:
                text(screen, F["hub_body"], "Pick a candidate on the left to read their dossier and make a pitch.",
                     (inner.x, y), T.TX_FAINT)
            return
        cand = self.candidates[self.sel]
        y = self._draw_dossier(screen, F, inner, y, cand)
        self._draw_pitch(screen, F, inner, y, cand, signed)

    def _cand_status(self, cand):
        if cand.uid in self.last:
            pitch, _who = self.last[cand.uid]
            return ("enlisted", "good") if pitch.ok else (self.REJECTED_LABEL.lower(), "bad")
        best = self._best(cand)
        if best is not None:
            return f"{best[0].name} can pitch", "good"
        return "cannot pitch", "bad"

    def _draw_dossier(self, screen, F, inner, y, cand):
        r = T.S * 5
        draw_face(screen, F, (inner.x + r, y + r), r, _face(cand), fallback_color=T.STEEL_HI)
        x = inner.x + 2 * r + T.S * 3
        n = small_caps(screen, F["hub_title"], F["hub_title_sc"], cand.name, (x, y + 2), T.TX)
        cap = text(screen, F["hub_body"], f"{cand.race['name']} {cand.occupation['name'].lower()}  ·  {cand.alignment}",
                   (x, n.bottom + 4), T.TX_MUTED)
        cx, chips = cap.right + T.S * 2, []
        for label, tone in _chips(cand):
            c = hb.draw_chip(screen, F, (cx, cap.centery), label, tone, anchor="midleft")
            chips.append((c, label))
            cx = c.right + T.S
        self._tip_chips(chips, cand)
        sx = x
        sy = n.bottom + T.S * 4
        for label, value in (("HP", str(cand.hp_max)), ("AC", str(cand.ac)), ("SPEED", f"{cand.speed} sq"),
                             ("ATTACK", cand.weapon_name or "Unarmed")):
            lab = spaced(screen, F["hub_label"], label, (sx, sy + 3), T.TX_MUTED)
            v = text(screen, F["hub_bodyb"], value, (lab.right + T.S, sy), T.TX)
            sx = v.right + T.S * 4
        kit = [nm for nm in (cand.equipped_weapon, cand.armor_name) if nm] + [i.name for i in cand.inventory]
        if kit:
            icon_strip(screen, F, pygame.Rect(sx, sy, inner.right - sx, T.S * 3), kit)
        y = max(y + 2 * r, sy + T.S * 3) + T.S * 2

        bail = self._bail(cand)
        if bail:
            text(screen, F["hub_bodyb"], f"Bail {fmt_money(bail)}  ·  the party holds {fmt_money(self._wealth())}",
                 (inner.x, y), T.BRASS if self._wealth() >= bail else T.BLOOD)
            y += T.S * 4
        lab = hb.draw_section(screen, F, (inner.x, y + 3), cand.ability.name)
        lines = wrap(F["hub_body"], cand.ability.effect, inner.right - lab.right - T.S * 2)
        for line in lines[:2]:
            text(screen, F["hub_body"], line, (lab.right + T.S * 2, y), T.TX_MUTED)
            y += F["hub_body"].get_linesize()
        y += T.S * 2
        pygame.draw.line(screen, T.STEEL_LINE, (inner.x, y), (inner.right, y))
        return y + T.S * 2

    def _pitch_condition(self, cand, m):
        if recruit.slots_free(self.guild, m) <= 0:
            return "no recruitment slot", "bad"
        if self._barred(cand, m):
            return "already tried this week", "bad"
        if not recruit.can_pitch(m, cand):
            return "no shared language", "bad"
        return f"1d20{self._net(m, cand):+} vs 1d20{cand.mod_charisma:+}", "good"

    def _draw_pitch(self, screen, F, inner, y, cand, signed):
        hint = tone = None
        if not self._eligible(cand):
            hint, tone = recruit.pitch_block_reason(
                self.guild, self.party, cand, lambda g, c, m: self._barred(c, m)), T.BLOOD
        who = self.selected_recruiter
        btn = pygame.Rect(inner.x, inner.bottom - BUTTON_H - 4, inner.w, BUTTON_H + 4)

        hb.draw_section(screen, F, (inner.x, y), "Who makes the pitch")
        y += T.S * 3 + 4
        rows_end = btn.y - T.S * (5 if hint or who is not None else 2)
        row_h = max(T.S * 7, min(hb.PERSON_H, (rows_end - y) // max(1, len(self.party)) - ROW_GAP))
        for m in self.party:
            mr = pygame.Rect(inner.x, y, inner.w, row_h)
            self.party_cards.append((mr, m))
            just_signed = signed is not None and signed["unit"] is m
            self._person(screen, mr, {
                "face": _face(m), "name": m.name + ("  ·  signed" if just_signed else ""),
                "sub": f"CHA {m.mod_charisma:+}  ·  speaks {', '.join(m.languages)}",
                "status": self._pitch_condition(cand, m),
                "state": "good" if just_signed else "on" if self.selected_recruiter is m else None})
            y += row_h + ROW_GAP

        can_pitch = (who is not None and recruit.can_pitch(who, cand) and not self._barred(cand, who)
                     and recruit.slots_free(self.guild, who) > 0)
        bail = self._bail(cand)
        label = f"Pay the {fmt_money(bail)} bail and convince" if bail else "Convince to join the guild"
        if bail and can_pitch and self._wealth() < bail:
            can_pitch, label = False, f"Cannot afford the {fmt_money(bail)} bail"
        elif who is not None and not can_pitch:
            label = f"{who.name} cannot pitch: {self._pitch_condition(cand, who)[0]}"
        self.add_button(screen, btn, "convince", label, primary=True, enabled=can_pitch)
        if hint is None and can_pitch:
            hint, tone = recruit.overflow_warning(self.guild, who), T.BRASS
        if hint:
            text(screen, F["hub_body"], hint[0].upper() + hint[1:], (btn.x, btn.y - T.S * 3 - 2), tone)

    # ------------------------------------------------------------------ #
    def _draw_study_hub(self, screen, body):
        F = self._F
        inner = hb.draw_panel(screen, F, body, "Study rooms",
                              "rent a quiet room for the day; anyone with a study target makes progress")
        cost = economy.TAVERN_STUDY_COST_PER_DAY
        studiers = sum(1 for m in self.party if m.study_target)
        btn = pygame.Rect(inner.right - T.S * 34, inner.y, T.S * 34, BUTTON_H)
        if self.group is None:
            text(screen, F["hub_body"], "The party is not staying here", (btn.right, btn.y + T.S * 2),
                 T.TX_FAINT, right=True)
        elif (self.group.order is not None and self.group.order.kind == "garrison"
              and self.group.order.job == "study"):
            text(screen, F["hub_bodyb"], "Studying now", (btn.x - T.S * 2, btn.y + T.S * 2), T.GREEN, right=True)
            self.add_button(screen, btn, "cancel_study", "Cancel the study order")
        else:
            self.add_button(screen, btn, "rent_study", "Rent rooms", primary=True)
        y = hb.draw_facts(screen, F, (inner.x, inner.y), btn.x - T.S * 4 - inner.x, [
            ("Rent", f"{fmt_money(cost)} a day for each member who studies", None),
            ("Today", f"{fmt_money(studiers * cost)} for {studiers} studying", "money" if studiers else "muted"),
            ("Progress", "a daily roll on Intelligence toward the target's points", "muted")])
        y = max(y, btn.bottom) + T.S
        pygame.draw.line(screen, T.STEEL_LINE, (inner.x, y), (inner.right, y))
        y += T.S * 2
        hb.draw_section(screen, F, (inner.x, y), "Who studies")
        y += T.S * 3 + 4

        buttons_w = T.S * 30
        for i, m in enumerate(self.party):
            mr = pygame.Rect(inner.x, y, inner.w, hb.PERSON_H + T.S)
            magic_tag = "/".join(s.capitalize() for s in m.magic_sources) + " magic" if m.magic_sources else "no magic"
            self._person(screen, mr, {
                "face": _face(m), "name": m.name, "reserve": buttons_w,
                "sub": f"{m.race['name']} {m.occupation['name'].lower()}  ·  INT {m.mod_intelligence:+}  ·  "
                       f"{magic_tag}  ·  {fmt_money(m.money)}"})
            mid = mr.x + round(mr.w * 0.42)
            room = mr.right - buttons_w - T.S * 4 - mid
            if m.study_target:
                if m.study_target in magic.SPELLS:
                    spell = magic.SPELLS[m.study_target]
                    target, needed = f"Scroll of {spell.name}", magic.points_to_learn(spell.level)
                else:
                    target, needed = f"Dictionary of {m.study_target}", magic.points_to_learn(0)
                text(screen, F["hub_bodyb"], target, (mid, mr.y + T.S + 4), T.BRASS)
                bar = pygame.Rect(mid, mr.y + T.S * 5, min(T.S * 30, room - T.S * 12), 6)
                hb.draw_bar(screen, bar, m.study_progress / max(1, needed))
                text(screen, F["hub_sub"], f"{m.study_progress} / {needed} pts", (bar.right + T.S * 2, bar.y - 6),
                     T.TX_MUTED)
                b2 = pygame.Rect(mr.right - T.S * 2 - T.S * 14, mr.y + T.S * 2 - 2, T.S * 14, T.S * 5)
                b1 = pygame.Rect(b2.x - T.S - T.S * 14, b2.y, T.S * 14, b2.h)
                self.add_button(screen, b1, f"stop_study_{i}", "Stop")
                self.add_button(screen, b2, f"choose_target_{i}", "Change")
            else:
                text(screen, F["hub_body"], "No study target", (mid, mr.y + T.S + 4), T.TX_MUTED)
                text(screen, F["hub_sub"], "idle in the study hours, no progress", (mid, mr.y + T.S * 4 + 4),
                     T.TX_FAINT)
                b = pygame.Rect(mr.right - T.S * 2 - T.S * 20, mr.y + T.S * 2 - 2, T.S * 20, T.S * 5)
                self.add_button(screen, b, f"choose_target_{i}", "Set target")
            y += mr.h + ROW_GAP

    # ------------------------------------------------------------------ #
    def _draw_perform(self, screen, body):
        F = self._F
        inner = hb.draw_panel(screen, F, body, "The stage", "play with a Musical Instrument; every hour is a Charisma test")
        crew = self._performers()
        go = pygame.Rect(inner.right - T.S * 34, inner.y, T.S * 34, BUTTON_H)
        self.add_button(screen, go, "perform_go", f"Play {self.perform_hours} h", primary=True, enabled=bool(crew))
        y = hb.draw_facts(screen, F, (inner.x, inner.y), go.x - T.S * 4 - inner.x, [
            ("Test", f"d20 + Charisma each hour: beat {economy.PERFORM_TIP_BASE} and the crowd tips", None),
            ("Tips", f"one more coin for every {economy.PERFORM_TIP_STEP} points over {economy.PERFORM_TIP_BASE}",
             "muted"),
            ("Needs", f"a {economy.PERFORM_ITEM} in the pack", "muted")])
        y += T.S
        lab = hb.draw_section(screen, F, (inner.x, y + T.S + 4), "Show length")
        bx = lab.right + T.S * 3
        for h in economy.PERFORM_SHIFT_HOURS:
            r = pygame.Rect(bx, y, T.S * 9, T.S * 4)
            hb.draw_toggle(screen, F, r, f"{h} h", h == self.perform_hours, self.mouse)
            if h != self.perform_hours:
                self.buttons.append((f"perf_hours_{h}", r))
                if r.collidepoint(self.mouse):
                    self._hot = True
            bx = r.right + T.S
        y += T.S * 6
        pygame.draw.line(screen, T.STEEL_LINE, (inner.x, y), (inner.right, y))
        y += T.S * 2
        hb.draw_section(screen, F, (inner.x, y), "Performers  ·  click to seat or stand down")
        y += T.S * 3 + 4
        for i, m in enumerate(self.party):
            mr = pygame.Rect(inner.x, y, inner.w, hb.PERSON_H)
            has = economy.can_perform(m)
            on = has and m not in self.perform_off
            if has:
                self.buttons.append((f"perf_toggle_{i}", mr))
                tips = economy.perform_expected(self.perform_hours, m.mod_charisma)
                status = (f"tips ~{fmt_money(round(tips, 1))} on average", "good" if tips else "muted") if on \
                    else ("sitting out", "faint")
            else:
                status = (f"no {economy.PERFORM_ITEM.lower()}", "faint")
            p = {"face": _face(m), "name": m.name, "status": status, "state": "on" if on else None,
                 "sub": f"{m.race['name']} {m.occupation['name'].lower()}  ·  CHA {m.mod_charisma:+}"}
            if has:
                self._person(screen, mr, p)
            else:
                hb.draw_person(screen, F, mr, p, (-1, -1))
            y += hb.PERSON_H + ROW_GAP

    # ------------------------------------------------------------------ #
    def _draw_study_modal(self, screen):
        F = self._F
        W, H = screen.get_size()
        student = self.study_modal_member
        self.modal_buttons.clear()

        backdrop = pygame.Surface((W, H), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 160))
        screen.blit(backdrop, (0, 0))

        dialog = pygame.Rect(0, 0, T.S * 85, T.S * 56)
        dialog.center = (W // 2, H // 2)
        inner = hb.draw_panel(screen, F, dialog, f"Study for {student.name}", None, hot=True)
        y = inner.y
        text(screen, F["hub_body"], "Pick a scroll or a dictionary the party carries to begin daily study.",
             (inner.x, y), T.TX_MUTED)
        y += T.S * 4

        options = self._available_study_options(student)
        if not options:
            line = (f"{student.name} has no magical affinity and carries no unlearned dictionaries."
                    if not student.magic_sources else "No scroll or dictionary the party carries fits.")
            text(screen, F["hub_body"], line, (inner.x, y), T.TX)
            y += T.S * 4
            for note in ("A scroll needs a matching magical affinity.",
                         "A dictionary teaches a foreign language.",
                         "Write one at the Library with paper and ink, or find scrolls in the ruins."):
                text(screen, F["hub_sub"], "·  " + note, (inner.x, y), T.TX_FAINT)
                y += T.S * 3
        for opt in options[:4]:
            opt_r = pygame.Rect(inner.x, y, inner.w, T.S * 8)
            hov = opt_r.collidepoint(self.mouse)
            if hov:
                self._hot = True
            pygame.draw.rect(screen, T.STEEL_HI if hov else mix(T.STEEL, T.TABLE, 0.35), opt_r, border_radius=6)
            text(screen, F["hub_row"], opt["name"], (opt_r.x + T.S * 2, opt_r.y + T.S + 2), T.TX)
            text(screen, F["hub_sub"], opt["desc"], (opt_r.x + T.S * 2, opt_r.y + T.S * 4 + 4), T.TX_MUTED)
            pick = pygame.Rect(opt_r.right - T.S * 14, opt_r.y + T.S + 4, T.S * 12, T.S * 5)
            hub_button(screen, F, pick, "Select", primary=hov, mpos=self.mouse)
            self.modal_buttons.append(("set_target", opt_r, opt))
            y += opt_r.h + T.S

        by = inner.bottom - BUTTON_H
        if student.study_target:
            clear_r = pygame.Rect(inner.x, by, T.S * 24, BUTTON_H)
            hub_button(screen, F, clear_r, "Stop studying", mpos=self.mouse)
            self.modal_buttons.append(("clear_target", clear_r, None))
        cancel_r = pygame.Rect(inner.right - T.S * 16, by, T.S * 16, BUTTON_H)
        hub_button(screen, F, cancel_r, "Cancel", mpos=self.mouse)
        self.modal_buttons.append(("cancel", cancel_r, None))

    # ------------------------------------------------------------------ #
    def _draw_signed_banner(self, screen, F, rect, signed):
        u, by, line = signed["unit"], signed["by"], signed["line"]
        pygame.draw.rect(screen, mix(T.STEEL, T.GREEN, 0.1), rect, border_radius=6)
        pygame.draw.rect(screen, T.GREEN, rect, 1, border_radius=6)
        r = T.S * 3
        draw_face(screen, F, (rect.x + T.S * 2 + r, rect.centery), r, _face(u), fallback_color=T.STEEL_HI)
        x = rect.x + T.S * 4 + 2 * r
        spaced(screen, F["hub_label"], f"Contract signed  ·  joins {by.name}'s roster", (x, rect.y + T.S * 2),
               T.GREEN)
        text(screen, F["hub_row"], f"{u.name}: “{line}”", (x, rect.y + T.S * 4 + 4), T.TX)
        text(screen, F["hub_sub"], f"{u.race['name']} {u.occupation['name'].lower()}  ·  HP {u.hp_max}  ·  AC {u.ac}",
             (x, rect.y + T.S * 8), T.TX_MUTED)
        sig = f"✕  {u.name}"
        s = text(screen, F["hub_bodyb"], sig, (rect.right - T.S * 2, rect.bottom - T.S * 4), T.BRASS, right=True)
        pygame.draw.line(screen, T.BRASS_DIM, (s.x - 6, s.bottom + 4), (s.right, s.bottom + 4), 1)
        return rect.bottom

    # ------------------------------------------------------------------ #
    def _draw_footer(self, screen, F):
        col = T.GREEN if (self.notice and ("signs" in self.notice or "begins" in self.notice)) else T.TX_MUTED
        if self.notice and ("lost" in self.notice or "Not enough" in self.notice):
            col = T.BLOOD
        if self.framed:
            if self.notice:
                text(screen, F["hub_body"], self.notice, (T.S * 5, screen.get_height() - T.S * 3), col)
            return
        footer_bar(self, screen, F, primary=("done", self._leave_label()),
                   notice=self.notice, notice_color=col)
