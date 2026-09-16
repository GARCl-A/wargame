"""The tanner: a City NPC offering a paid, time-boxed job (`missions.py`) --
distinct from the market (buy/sell, unlimited except a few scarce lines) and
the bank (shared storage). `self.group` is just whoever walked up right now --
the group's **leader** is who actually signs (same "who speaks for the group"
convention as market haggling), and the job then travels with that unit, not
this particular group (see `missions.py`'s module docstring).
"""

from . import missions
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
        return next((t for t in missions.TEMPLATES.values()
                     if t.giver == self.GIVER and t.node == self.group.node), None)

    def get_req_str(self, t):
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} copper  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        return f"{progress} / {t.goal_qty} {t.goal_item}  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return f"paid out {reward} copper, split across the group."
