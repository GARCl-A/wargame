"""A hidden sanctuary's job board: the school's keeper takes the Ancient Codex and
whatever else that school asks for (`missions.py`), the Snake Dragon among them."""

from . import missions, wildfire, world
from .ui.mission_offer_screen import MissionOfferScreen

KEEPER_LINE = {
    "blood": '"Blood remembers. What runs in the veins can be read."',
    "nature": '"The grove is patient. What was twisted can be tended."',
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
        if t is missions.NATURE_WILDFIRE:
            return (f"goal: talk the Ogre round or beat him, and put out what fires you can  ·  "
                    f"{t.deadline_days} days  ·  the Coven gives a {wildfire.REWARD}")
        if t.fight_at:
            goal = f"win the skirmish at {world.node(t.fight_at).name}, every soldier alive"
            if t.starting_item and not any(m.template_id == t.id for m in self.guild.missions):
                goal += f"  ·  you get {t.starting_qty}x {t.starting_item}"
        else:
            goal = f"the {t.goal_item}, alive" if t.goal_captive else f"{t.goal_qty}x {t.goal_item}"
        due = f"{t.deadline_days} days" if t.deadline_days else "no deadline"
        return f"goal: {goal}  ·  {due}"

    def get_status_str(self, t, progress, ready, days_left):
        if t is missions.NATURE_WILDFIRE:
            state = self.guild.wildfire
            burned = f"  ·  {state.burned} burned" if state is not None and state.burned else ""
            due = f"  ·  {days_left} day(s) left" if days_left is not None else ""
            return f"the fires burn round The Wilds{due}{burned}"
        if t.fight_at:
            due = f"  ·  {days_left} day(s) left" if days_left is not None else ""
            return f"fight at {world.node(t.fight_at).name}, lose no soldier{due}"
        return f"{progress} / {t.goal_qty} {t.goal_item}"

    def get_turn_in_label(self, t, progress, ready):
        if t.fight_at:
            return f"GO TO {world.node(t.fight_at).name.upper()}"
        return "HAND IT OVER" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return "the keeper takes it and speaks your name to the school."
