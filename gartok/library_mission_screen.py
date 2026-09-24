"""The library's mission board: a City NPC offering a paid, time-boxed job
(`missions.py`).
"""

from . import missions
from .ui.mission_offer_screen import MissionOfferScreen


class LibraryMissionScreen(MissionOfferScreen):
    GIVER = "library"

    @property
    def title_text(self):
        return "THE LIBRARY (JOBS)"

    @property
    def subtitle_text(self):
        return '"We need to expand our archives. Translations are well paid."'

    @property
    def accept_label(self):
        return "ACCEPT THE JOB"

    @property
    def leave_label(self):
        return "LEAVE"

    def get_template(self):
        return next((t for t in missions.TEMPLATES.values()
                     if t.giver == self.GIVER and t.node == self.group.node), None)

    def get_req_str(self, t):
        if t.goal_item == "Any Dictionary":
            return f"goal: {t.goal_qty}x Dictionary (Any Language)  ·  pay: {t.reward} copper  ·  deadline: {t.deadline_days} days"
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {t.reward} copper  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        item_label = "Dictionary" if t.goal_item == "Any Dictionary" else t.goal_item
        return f"{progress} / {t.goal_qty} {item_label}  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return f"paid out {reward} copper, split across the group."
