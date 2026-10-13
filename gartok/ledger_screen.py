"""Ledger Hold: the Bankers' fortified outpost where the trust mission's
sealed chest (`data.MISSION_CHEST_ITEM`) is traded, intact, for a letter of
receipt (`data.LETTER_ITEM`) -- the thing `missions.turn_in` actually counts
back at the City (`trust_screen.py`). No progress bar, no goal_qty -- either
someone in the group is carrying the chest, or there is nothing to hand over.
"""

import pygame

from . import data
from .screen import Screen
from .ui.primitives import draw_button, footer_bar, panel, text
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts

CARD_W = 560


class LedgerScreen(Screen):
    native = True

    def tutorial_key(self):
        return "ledger"

    def __init__(self, fonts, guild, group, on_done):
        super().__init__()
        self.fonts = fonts
        self._F = ui_fonts()
        self.guild = guild
        self.group = group
        self.on_done = on_done
        self.notice = None
        self.buttons = []              # [(key, rect)]
        self._hot = False

    def _reset_buttons(self):
        self.buttons = []
        self._hot = False

    def add_button(self, surf, rect, key, label, *, enabled=True, primary=False,
                   danger=False, font=None, sub=None):
        """Draws through `ui.primitives.draw_button` and tracks button hit rects."""
        draw_button(surf, self._F, rect, label, sub=sub, primary=primary, danger=danger,
                   enabled=enabled, mpos=self.mouse, fnt=font)
        hov = enabled and rect.collidepoint(self.mouse)
        if enabled:
            self.buttons.append((key, rect))
            self._hot = self._hot or hov
        return hov

    def _carrier(self):
        return next((u for u in self.group.members
                    if u.has_item(data.MISSION_CHEST_ITEM)), None)

    def _click(self, px):
        for key, rect in self.buttons:
            if not rect.collidepoint(px):
                continue
            if key == "exchange":
                carrier = self._carrier()
                if carrier is not None:
                    carrier.remove_named(data.MISSION_CHEST_ITEM)
                    carrier.give_to_pack(data.LETTER_ITEM)
                    self.notice = (f"{carrier.name} hands over the sealed chest -- the "
                                   "outpost gives a letter of receipt in return.")
            elif key == "accept_mentorship":
                from . import missions
                recruit = missions.make_treefolk_recruit()
                self.guild.add_member(recruit, self.group)
                signer = self.group.leader or self.group.members[0]
                missions.accept_treefolk_mentorship(self.guild, signer, recruit)
                self.notice = f"{recruit.name} (Treefolk) joins your group for mentorship."
            elif key == "deliver_recruit":
                from . import missions
                m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
                if m_tree is not None:
                    recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
                    if recruit is not None:
                        missions.deliver_treefolk_recruit(self.guild, self.group, m_tree, recruit)
                        self.notice = f"{recruit.name} steps into the garrison. $230 reward received!"
            elif key == "supply_run":
                from . import orders
                try:
                    self.group.order = orders.supply_run(self.guild, self.group)
                    self.on_done()
                except ValueError as err:
                    self.notice = str(err)
                return
            elif key == "done":
                self.on_done()
                return
            return

    # ------------------------------------------------------------------ #
    def draw(self, screen):
        F = self._F
        m = T.S * 3
        screen.fill(T.TABLE)
        self._reset_buttons()

        from . import world
        from .ui.vendor_panel import draw_vendor, draw_vendor_name
        vendor = world.vendor("ledger_hold", "ledger")
        card = vendor.card if vendor else None
        tx = m + draw_vendor(screen, F, (m, m - 4), card, size=T.S * 7)
        title = text(screen, F["titleb"], "LEDGER HOLD", (tx, m - 2), T.TX)
        draw_vendor_name(screen, F, (title.right + T.S * 2, title.y + 10), card)
        text(screen, F["body"], "\"State your business.\"", (tx, m + 30), T.TX_MUTED)

        card_w = min(CARD_W, screen.get_width() - 2 * m)
        cy = m + 70
        pad = 12

        # 1. Bankers' sealed chest exchange
        carrier = self._carrier()
        if carrier is not None:
            card1 = pygame.Rect(m, cy, card_w, 100)
            panel(screen, card1)
            x, y = card1.x + pad, card1.y + pad
            text(screen, F["body_sm"], f"{carrier.name} carries the Bankers' sealed chest.",
                 (x, y), T.TX_MUTED)
            r = pygame.Rect(x, y + 26, card1.w - 2 * pad, 36)
            self.add_button(screen, r, "exchange", "HAND OVER THE CHEST", primary=True)
            cy = card1.bottom + T.S * 2

        # 2. Treefolk mentorship mission
        if "bankers_trust" in self.guild.deeds_done:
            m_tree = next((m for m in self.guild.missions if m.template_id == "ledger_treefolk"), None)
            card2 = pygame.Rect(m, cy, card_w, 130)
            panel(screen, card2)
            x, y = card2.x + pad, card2.y + pad
            text(screen, F["bodyb"], "GARRISON MENTORSHIP", (x, y), T.BRASS)
            y += 24
            if m_tree is None:
                text(screen, F["body_sm"], "Commander Varkas offers a green Treefolk recruit to train to racial level 2.", (x, y), T.TX)
                r = pygame.Rect(x, y + 24, card2.w - 2 * pad, 36)
                self.add_button(screen, r, "accept_mentorship", "ACCEPT RECRUIT & MENTORSHIP", primary=True, sub="Receive Treefolk recruit (lvl 0)")
            elif m_tree.state == "active":
                recruit = next((u for u in self.guild.roster if u.uid == m_tree.recruit_uid), None)
                if recruit is None:
                    m_tree.state = "failed"
                    text(screen, F["body_sm"], "The Treefolk recruit fell in battle. The mentorship has failed.", (x, y), T.RED)
                elif recruit in self.group.members:
                    lvl = recruit.racial_level
                    ready = lvl >= 2
                    msg = f"{recruit.name} is ready for garrison service (Racial Lvl {lvl})!" if ready else f"{recruit.name} is training (Racial Lvl {lvl}/2)."
                    text(screen, F["body_sm"], msg, (x, y), T.GREEN if ready else T.TX_MUTED)
                    r = pygame.Rect(x, y + 24, card2.w - 2 * pad, 36)
                    self.add_button(screen, r, "deliver_recruit", "DELIVER TRAINED RECRUIT", enabled=ready, primary=ready,
                                    sub="$230 reward  ·  leaves the guild" if ready else "Requires racial level 2")
                else:
                    text(screen, F["body_sm"], f"{recruit.name} is in another group. Bring them here to hand over.", (x, y), T.TX_MUTED)
            else:
                text(screen, F["body_sm"], "Commander Varkas salutes: 'The Treefolk soldier serves with honor.'", (x, y), T.GREEN)
                text(screen, F["body_sm"], "Ledger Hold's gates stand open to your guild.", (x, y + 20), T.TX_MUTED)
            cy = card2.bottom + T.S * 2

            # 3. Frontier Supply Run
            from . import economy
            card3 = pygame.Rect(m, cy, card_w, 140)
            panel(screen, card3)
            x, y = card3.x + pad, card3.y + pad
            text(screen, F["bodyb"], "FRONTIER SUPPLY RUN", (x, y), T.BRASS)
            y += 24
            runs = self.guild.supply_runs_completed
            deed_done = "ledger_hold_supply_run" in self.guild.deeds_done
            status_text = f"Escort 20 kg of military supplies to the frontier outpost (10h) · Progress: {runs}/10 deliveries{' (Deed earned)' if deed_done else ''}."
            text(screen, F["body_sm"], status_text, (x, y), T.TX)
            y += 20
            cargo = self.group.free_cargo_capacity
            can_run = cargo >= economy.SUPPLY_RUN_CARGO_KG
            stat_msg = (
                f"Free cargo capacity: {cargo:.1f} kg / {economy.SUPPLY_RUN_CARGO_KG:.0f} kg required  ·  +$30 each  ·  Work Lv 5"
                if can_run else
                f"Free cargo capacity: {cargo:.1f} kg / {economy.SUPPLY_RUN_CARGO_KG:.0f} kg required (bring pack animals or lighten load)"
            )
            text(screen, F["body_sm"], stat_msg, (x, y), T.GREEN if can_run else T.RED)
            r = pygame.Rect(x, y + 24, card3.w - 2 * pad, 36)
            self.add_button(screen, r, "supply_run", "DEPART WITH SUPPLY CARAVAN", enabled=can_run, primary=can_run,
                            sub="10 hours  ·  +$30 each  ·  ambush risk on frontier roads")
            cy = card3.bottom + T.S * 2
        elif carrier is None:
            card0 = pygame.Rect(m, cy, card_w, 80)
            panel(screen, card0)
            x, y = card0.x + pad, card0.y + pad
            text(screen, F["body_sm"], "Nothing to hand over here. Complete the Bankers' trust test to earn their standing.", (x, y), T.TX_FAINT)

        self._draw_footer(screen)

    def _draw_footer(self, screen):
        footer_bar(self, screen, self._F, primary=("done", "LEAVE LEDGER HOLD"), notice=self.notice)
