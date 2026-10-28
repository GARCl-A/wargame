"""A giver's jobs board with no window: which jobs it shows, which are on offer, the leader signing for one,
the turn-in and its notice, each card's line and button. `Board` is what every giver shares; `TannerBoard`,
`ApothecaryBoard`, `LibraryBoard`, `ShrineBoard` and `TrustBoard` say what each one asks for and pays.
`web/jobs_tab.py` draws them.
"""

from . import factions, lair, missions, wildfire, world
from .constants import fmt_money

TAG_TONE = {"economic": "money", "trust": "money", "bankers": "money", "apothecary": "good", "ruins": "bad"}


class Board:
    accept_label = "ACCEPT THE JOB"

    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.notice = None

    def hub_cards(self):
        """The jobs board's cards: how many jobs are up, how many the guild holds here."""
        templates = self.get_templates()
        ids = {t.id for t in templates}
        held = sum(1 for m in self.guild.missions if m.template_id in ids and m.state == "active")
        purse = sum(u.money for u in self.group.members)
        return [{"label": "jobs on the board", "value": str(len(templates))},
                {"label": "taken", "value": str(held)},
                {"label": "party purse", "value": fmt_money(purse), "tone": "money"}]

    @property
    def subtitle_text(self):
        raise NotImplementedError

    def get_template(self):
        raise NotImplementedError

    def get_templates(self):
        """Every job the board shows, top to bottom. The default is the one
        `get_template` picks; a giver with several jobs at once overrides this."""
        t = self.get_template()
        return [] if t is None else [t]

    def get_req_str(self, t):
        raise NotImplementedError

    def get_status_str(self, t, progress, ready, days_left):
        raise NotImplementedError

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN" if ready else f"NEED {t.goal_qty - progress} MORE"

    def footer_action(self):
        """`(label, enabled)` for a second button beside the leave one (a keeper buying
        something), or None for none."""
        return None

    def run_footer_action(self):
        """Press the footer action: -> the notice to show."""
        return None

    def get_success_notice(self, reward):
        return f"paid out {fmt_money(reward)}, split across the group."

    @property
    def _template(self):
        """The first job on the board."""
        return next(iter(self.get_templates()), None)

    def _is_offered(self, t):
        """Whether `t` can be freshly accepted here right now
        (`missions.offers_at` -- the "one job out at a time" rule)."""
        return t in missions.offers_at(self.guild, self.group.node)

    def _active_of(self, t):
        """`t`'s job out right now, if any, regardless of who's holding it."""
        return next((m for m in self.guild.missions
                     if m.template_id == t.id and m.state == "active"), None)

    def _completed_of(self, t):
        return any(m.template_id == t.id and m.state in ("done", "failed")
                   for m in self.guild.missions)

    def _mission_of(self, t):
        """`t`'s active job, but only if the group standing here right now is
        the one sharing it (its signer is one of `self.group.members`)."""
        m = self._active_of(t)
        if m is None:
            return None
        return m if any(u.uid == m.unit_uid for u in self.group.members) else None

    @property
    def _offered(self):
        t = self._template
        return t is not None and self._is_offered(t)

    @property
    def _active(self):
        t = self._template
        return None if t is None else self._active_of(t)

    @property
    def _completed(self):
        t = self._template
        return t is not None and self._completed_of(t)

    @property
    def _mission(self):
        t = self._template
        return None if t is None else self._mission_of(t)

    def accept(self, t):
        """The leader signs for `t` when it is on offer here: -> whether they did."""
        if not self._is_offered(t):
            return False
        missions.accept(self.guild, self.group.leader, t)
        self.notice = None
        return True

    def turn_in(self, t):
        """Hand over `t`'s goal when this band holds the job and carries it: -> whether it was paid."""
        m = self._mission_of(t)
        if m is None or not missions.can_turn_in(self.guild, m):
            return False
        earned = missions.turn_in(self.guild, m)
        self.notice = self.get_success_notice(t.reward)
        if t.reward_recipe:
            self.notice += f"  ·  the group learns to craft the {t.reward_recipe}"
        if t.reward_item:
            self.notice += f"  ·  you are given a {t.reward_item}"
        for d in earned:
            self.notice += "  ·  " + factions.deed_notice(d)
        return True

    def _job_button(self, t, m, lay):
        """`(key, label, enabled)` of the button at the foot of `t`'s card."""
        if m is not None:
            ready = lay["ready"]
            return ("turn_in", t.id), self.get_turn_in_label(t, lay["progress"], ready), ready
        offered = self._is_offered(t)
        wait = missions.retry_in(self.guild, t)
        if wait:
            label = f"Failed: try again in {wait} day{'s' if wait != 1 else ''}"
        elif missions.closed(self.guild, t):
            label = "Failed: it went to another school"
        elif self._completed_of(t):
            done = any(x.template_id == t.id and x.state == "done" for x in self.guild.missions)
            label = "Job completed" if done else "Job failed"
        elif offered:
            label = self.accept_label
        else:
            label = "Out with another group"
        return ("accept", t.id), label, offered


class TannerBoard(Board):
    """The tanner: the group's **leader** signs (same "who speaks for the group" convention as market
    haggling), and the job then travels with that unit, not this group (see `missions.py`)."""
    GIVER = "tanner"
    subtitle_text = '"Bring me hide and I\'ll pay well for it."'

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

    def get_success_notice(self, reward):
        if not reward:
            return "the tanner takes the leather and puts your name about."
        return super().get_success_notice(reward)


class ApothecaryBoard(Board):
    GIVER = "apothecary"
    subtitle_text = '"Need someone to fetch rare reagents from the wilds."'

    def get_template(self):
        return next((t for t in missions.TEMPLATES.values()
                     if t.giver == self.GIVER and t.node == self.group.node), None)

    def get_req_str(self, t):
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {fmt_money(t.reward)}  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        return f"{progress} / {t.goal_qty} {t.goal_item}  ·  {days_left} day(s) left"


class LibraryBoard(Board):
    GIVER = "library"
    subtitle_text = '"We need to expand our archives. Translations are well paid."'

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_req_str(self, t):
        if t.goal_item == "Any Dictionary":
            return f"goal: {t.goal_qty}x Dictionary (Unarchived Tongue)  ·  pay: {fmt_money(t.reward)}  ·  deadline: {t.deadline_days} days"
        return f"goal: {t.goal_qty}x {t.goal_item}  ·  pay: {fmt_money(t.reward)}  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        item_label = "Dictionary" if t.goal_item == "Any Dictionary" else t.goal_item
        return f"{progress} / {t.goal_qty} {item_label}  ·  {days_left} day(s) left"


KEEPER_LINE = {
    "blood": '"Blood remembers. What runs in the veins can be read."',
    "nature": '"The grove is patient. What was twisted can be tended."',
    "faith": '"The faithful are tested, not hurried. Bring us what the ruins kept."',
}


class ShrineBoard(Board):
    """A hidden sanctuary's board: the school's keeper takes the Ancient Codex and whatever else that
    school asks for, the Snake Dragon among them."""
    accept_label = "TAKE ON THE TASK"

    @property
    def _giver(self):
        return next((t.giver for t in missions.TEMPLATES.values() if t.node == self.group.node), None)

    @property
    def subtitle_text(self):
        return KEEPER_LINE.get(self._giver, "")

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self._giver, self.group.node)

    def get_req_str(self, t):
        if t is missions.NATURE_WILDFIRE:
            return (f"goal: talk the Ogre round or beat him, and put out what fires you can  ·  "
                    f"{t.deadline_days} days  ·  the Coven gives a {wildfire.REWARD}")
        if t is missions.FAITH_NECROMANCER:
            return (f"goal: find and put down whoever raises the dead at {world.node(t.fight_at).name}  ·  "
                    f"{t.deadline_days} days")
        if t.fight_at:
            goal = f"win the skirmish at {world.node(t.fight_at).name}, every soldier alive"
            if t.starting_item and not any(m.template_id == t.id for m in self.guild.missions):
                goal += f"  ·  you get {t.starting_qty}x {t.starting_item}"
        else:
            goal = f"the {t.goal_item}, alive" if t.goal_captive else f"{t.goal_qty}x {t.goal_item}"
        due = f"{t.deadline_days} days" if t.deadline_days else "no deadline"
        prize = f"  ·  you get a {t.reward_item}" if t.reward_item else ""
        return f"goal: {goal}  ·  {due}{prize}"

    def get_status_str(self, t, progress, ready, days_left):
        if t is missions.NATURE_WILDFIRE:
            state = self.guild.wildfire
            burned = f"  ·  {state.burned} burned" if state is not None and state.burned else ""
            due = f"  ·  {days_left} day(s) left" if days_left is not None else ""
            return f"the fires burn round The Wilds{due}{burned}"
        if t.fight_at:
            due = f"  ·  {days_left} day(s) left" if days_left is not None else ""
            if t is missions.FAITH_NECROMANCER:
                return f"the dead rise at {world.node(t.fight_at).name}: find the one who wakes them{due}"
            return f"fight at {world.node(t.fight_at).name}, lose no soldier{due}"
        return f"{progress} / {t.goal_qty} {t.goal_item}"

    def get_turn_in_label(self, t, progress, ready):
        if t.fight_at:
            return f"GO TO {world.node(t.fight_at).name.upper()}"
        return "HAND IT OVER" if ready else f"NEED {t.goal_qty - progress} MORE"

    def get_success_notice(self, reward):
        return "the keeper takes it and speaks your name to the school."

    def _egg_holder(self):
        if self._giver == "blood" and missions.pending_clutch(self.guild) is not None:
            return None                   # the first egg is the Cult's job here, not a sale
        return next((u for u in self.group.members if u.count_of(lair.EGG)), None)

    def footer_action(self):
        holder = self._egg_holder()
        if holder is None and not any(u.count_of(lair.EGG) for u in self.group.members):
            return None
        return f"SELL A DRAGON EGG  ·  ${lair.SHRINE_EGG_PRICE}", holder is not None

    def run_footer_action(self):
        holder = self._egg_holder()
        if holder is None:
            return None
        holder.remove_named(lair.EGG, 1)
        holder.money += lair.SHRINE_EGG_PRICE
        return f"the keeper weighs the egg in both hands and pays {holder.name} ${lair.SHRINE_EGG_PRICE}."


class TrustBoard(Board):
    """The Bankers' test of trust: accepting hands the signer a sealed chest
    (`missions.TRUST_CHEST.starting_item`); the goal is the letter of receipt Ledger Hold
    (`ledger.py`) trades for it once the band gets there safely."""
    TEMPLATE = missions.TRUST_CHEST
    accept_label = "ACCEPT THE TEST OF TRUST"
    subtitle_text = '"Prove the guild can be trusted with something precious."'

    def get_template(self):
        return self.TEMPLATE

    def get_req_str(self, t):
        return f"carry: {t.starting_item}  ·  bring back: {t.goal_item}  ·  deadline: {t.deadline_days} days"

    def get_status_str(self, t, progress, ready, days_left):
        if ready:
            return f"{t.goal_item} in hand  ·  {days_left} day(s) left"
        return f"carrying the sealed chest to Ledger Hold  ·  {days_left} day(s) left"

    def get_turn_in_label(self, t, progress, ready):
        return "TURN IN THE LETTER" if ready else "NOT BACK YET"

    def get_success_notice(self, reward):
        return "the Bankers accept the letter -- your trust is earned."


# a node's function -> its giver's board, in the order a node's tabs list them
BOARDS = (("tanner", TannerBoard), ("apothecary", ApothecaryBoard), ("library", LibraryBoard),
          ("shrine", ShrineBoard), ("trust", TrustBoard))
