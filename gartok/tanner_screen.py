"""The tanner: a City NPC offering a paid, time-boxed job (`missions.py`) --
distinct from the market (buy/sell, unlimited except a few scarce lines) and
the bank (shared storage). `self.group` is just whoever walked up right now --
the group's **leader** is who actually signs (same "who speaks for the group"
convention as market haggling), and the job then travels with that unit, not
this particular group (see `missions.py`'s module docstring).
"""

from . import missions
from .constants import fmt_money
from .ui.mission_offer_screen import MissionOfferScreen


class TannerScreen(MissionOfferScreen):
    GIVER = "tanner"

    @property
    def title_text(self):
        return "THE TANNER"

    @property
    def subtitle_text(self):
        return '"Bring me hide and I\'ll pay well for it."'

    @property
    def accept_label(self):
        return "ACCEPT THE JOB"

    @property
    def leave_label(self):
        return "LEAVE THE TANNER"

    def get_template(self):
        """The job to show: the one out right now, else the first still on offer, else
        the last one the guild took (a finished chain reads "JOB COMPLETED")."""
        mine = [t for t in missions.TEMPLATES.values()
                if t.giver == self.GIVER and t.node == self.group.node]
        on_offer = {t.id for t in missions.offers_at(self.guild, self.group.node)}
        out = {m.template_id for m in self.guild.missions if m.state == "active"}
        return (next((t for t in mine if t.id in out), None)
                or next((t for t in mine if t.id in on_offer), None)
                or next((t for t in reversed(mine)
                         if any(m.template_id == t.id for m in self.guild.missions)), None)
                or next(iter(mine), None))

    def get_req_str(self, t):
        pay = f"  ·  pay: {fmt_money(t.reward)}" if t.reward else ""
        due = "no deadline" if t.deadline_days is None else f"deadline: {t.deadline_days} days"
        return f"goal: {t.goal_qty}x {t.goal_item}{pay}  ·  {due}"

    def get_status_str(self, t, progress, ready, days_left):
        left = "" if days_left is None else f"  ·  {days_left} day(s) left"
        return f"{progress} / {t.goal_qty} {t.goal_item}{left}"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        if not reward:
            return "the tanner takes the leather and puts your name about."
        return f"paid out {fmt_money(reward)}, split across the group."
