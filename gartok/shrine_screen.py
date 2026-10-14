"""A hidden sanctuary's job board: the school's keeper takes the Ancient Codex and
whatever else that school asks for (`missions.py`)."""

from . import missions, world
from .ui.mission_offer_screen import MissionOfferScreen

KEEPER_LINE = {
    "blood": '"Blood remembers. Bring us what the ruins kept."',
    "nature": '"The grove is patient. Bring us what the ruins kept."',
    "faith": '"The faithful are tested, not hurried. Bring us what the ruins kept."',
}


class ShrineMissionScreen(MissionOfferScreen):
    @property
    def _giver(self):
        return next((t.giver for t in missions.TEMPLATES.values() if t.node == self.group.node), None)

    @property
    def title_text(self):
        return world.node(self.group.node).name.upper()

    @property
    def subtitle_text(self):
        return KEEPER_LINE.get(self._giver, "")

    @property
    def accept_label(self):
        return "TAKE ON THE TASK"

    @property
    def leave_label(self):
        return "LEAVE THE SANCTUARY"

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self._giver, self.group.node)

    def get_req_str(self, t):
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  no deadline"

    def get_status_str(self, t, progress, ready, days_left):
        return f"{progress} / {t.goal_qty} {t.goal_item}"

    def get_turn_in_label(self, t, progress, ready):
        return "HAND IT OVER" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return "the keeper takes the Codex and speaks your name to the school."
