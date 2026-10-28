"""Initiation into a magic school, at its hidden sanctuary (the INITIATION tab).

The school takes a character from a guild that stands at `REP_NEEDED` with its faction (a
threshold, never spent). The character boards at the sanctuary like a student at the tavern:
they split off into a group of their own on a `garrison("rite")` order (`Guild.send_alone`),
or the whole group waits when no slot is free, and roll `1d20 + INT` learning points a day
(`Guild._garrison_upkeep`) until the school's total. Leaving keeps the points (`rite_progress`,
one counter per school). Board is `BOARD_PER_DAY` copper and covers the meal, paid only on a day
the boarder has no food in their own pack (`board`).

Faith consumes a `Holy Symbol` when the rite first starts. Blood first spends `BLOOD_TEST_DAYS`
testing the blood: `Unit.magic_blood` is rolled when the character is made (`magic.roll_magic_blood`),
the test only reveals it, and a failed test is final. The rite grants the school and its root in
the magic talent track, no spell.
"""

from . import data, economy, factions, orders, world
from .constants import fmt_money

SANCTUARY = {"blood_sanctuary": "blood", "nature_grove": "nature", "faith_cathedral": "faith"}
FACTION = {"blood": "blood_cult", "nature": "nature_coven", "faith": "faith_order"}
REP_NEEDED = 2
POINTS = {"faith": 180, "blood": 90, "nature": 270}
BLOOD_TEST_DAYS = 7
BOARD_PER_DAY = 3
HOLY_SYMBOL = "Holy Symbol"
JOB = "rite"


def school_at(node_id):
    return SANCTUARY.get(node_id)


def _holders(group):
    return (*group.members, *getattr(group, "stores", ()))


def paid(unit, school):
    """The rite was started once, so what it costs up front (Faith's symbol) is spent."""
    return school in unit.rite_progress


def blocker(guild, group, unit, school):
    """Why `unit` cannot start (or go back to) `school`'s rite now, or None."""
    name = school.title()
    if school in unit.magic_sources:
        return f"{unit.name} is already initiated in {name} magic."
    if guild.reputation.get(FACTION[school], 0) < REP_NEEDED:
        return f"The school takes no one until the guild has {REP_NEEDED} reputation with it."
    if school == "blood" and unit.blood_tested and not unit.magic_blood:
        return f"The Cult tested {unit.name}'s blood: there is no magic in it."
    if school == "faith" and not paid(unit, school) and not any(u.has_item(HOLY_SYMBOL) for u in _holders(group)):
        return f"The rite consumes a {HOLY_SYMBOL}, and the group carries none."
    if group.locked:
        return "A group with an order in flight cannot leave anyone here."
    return None


def stage(unit, school):
    """`(label, done, total)` of where `unit` stands in `school`'s rite."""
    if school == "blood" and not unit.blood_tested:
        return "blood test", unit.blood_test_days, BLOOD_TEST_DAYS
    return "learning", min(unit.rite_progress.get(school, 0), POINTS[school]), POINTS[school]


def begin(guild, group, unit, school):
    """Leave `unit` boarding at the sanctuary for `school`'s rite. Returns `(ok, lines)`."""
    blocked = blocker(guild, group, unit, school)
    if blocked:
        return False, [blocked]
    lines = []
    if school == "faith" and not paid(unit, school):
        holder = unit if unit.has_item(HOLY_SYMBOL) else next(u for u in _holders(group) if u.has_item(HOLY_SYMBOL))
        holder.remove_named(HOLY_SYMBOL, 1)
        lines.append(f"The Order takes {holder.name}'s {HOLY_SYMBOL}.")
    unit.rite_progress.setdefault(school, 0)
    unit.rite_school = school
    order = orders.garrison(JOB)
    if guild.send_alone(group, unit, order, f"{unit.name} (rite)") is None:
        group.order = order
        lines.append(f"No free group slot: the group waits while {unit.name} boards for the rite.")
    else:
        lines.append(f"{unit.name} stays to board at the sanctuary for the {school.title()} rite.")
    return True, lines


def progress(unit):
    """One day of `unit`'s rite. Returns an event worth telling, or None for a quiet day."""
    school = unit.rite_school
    if school is None:
        return None
    if school == "blood" and not unit.blood_tested:
        unit.blood_test_days += 1
        if unit.blood_test_days < BLOOD_TEST_DAYS:
            return None
        unit.blood_tested = True
        if not unit.magic_blood:
            unit.rite_school = None
            return f"The Blood Cult finds no magic in {unit.name}'s blood. They will not test it again."
        return f"The Blood Cult finds magic in {unit.name}'s blood: the learning begins."
    unit.rite_progress[school] = unit.rite_progress.get(school, 0) + max(0, data.roll(1, 20) + unit.mod_intelligence)
    if unit.rite_progress[school] < POINTS[school]:
        return None
    unit.rite_school = None
    unit.add_magic_source(school)
    unit._derive_combat()
    return f"{unit.name} is initiated into {school.title()} magic."


def boarders(group):
    """The members boarding for the rite of the sanctuary `group` stands at."""
    school = school_at(group.node)
    if (school is None or group.order is None or group.order.kind != "garrison"
            or group.order.job != JOB or world.node(group.node).garrison_job != JOB):
        return []
    return [u for u in group.members if u.rite_school == school]


def board(guild):
    """The day's board: each boarder with no food in their own pack is fed by the sanctuary for
    `BOARD_PER_DAY`, paid from their purse and then the group's. Returns who it fed."""
    fed = set()
    for g in guild.groups:
        for u in boarders(g):
            if u.rations or u.ability.id == "autotroph":
                continue
            mates = [m for m in _holders(g) if m is not u]
            if u.money + sum(m.money for m in mates) < BOARD_PER_DAY:
                continue
            own = min(u.money, BOARD_PER_DAY)
            u.money -= own
            economy.charge_richest_first(mates, BOARD_PER_DAY - own)
            fed.add(u)
    return fed


def daily(group):
    """`_garrison_upkeep`'s day for a group on the rite: each boarder's progress, and the stay
    ends once nobody there is boarding any more. Returns the events."""
    events = [e for e in (progress(u) for u in boarders(group)) if e]
    if not boarders(group):
        group.order = None
        events.append(f"{world.node(group.node).name}: nobody left boarding for the rite.")
    return events


class Initiation:
    """A sanctuary's INITIATION tab with no window: the school's terms, who may stay to board and why not,
    the pick and the begin. `InitiationScreen` is the pygame window over it and `web/initiation_tab.py`
    the browser's."""

    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.school = school_at(group.node)
        self.picked = None
        self.notice = None

    def _member(self, uid):
        return next((u for u in self.group.members if u.uid == uid), None)

    def _status(self, u):
        if self.school in u.magic_sources:
            return f"initiated in {self.school.title()} magic"
        label, done, total = stage(u, self.school)
        if label == "blood test":
            left = f"{total - done} day(s) of testing, then {POINTS['blood']} learning points"
        else:
            per_day = max(1, 10.5 + u.mod_intelligence)
            left = f"{done}/{total} learning points  ·  about {round((total - done) / per_day)} day(s) left"
        boarding = "boarding  ·  " if u.rite_school == self.school else ""
        return f"{boarding}{left}  ·  INT {u.mod_intelligence:+}"

    def _terms(self):
        faction = FACTION[self.school]
        have = self.guild.reputation.get(faction, 0)
        terms = [("The school", f"{factions.FACTIONS[faction].name}: reputation {have} of {REP_NEEDED}",
                  have >= REP_NEEDED)]
        if self.school == "faith":
            terms.append(("Up front", f"one {HOLY_SYMBOL}, consumed", True))
        if self.school == "blood":
            terms.append(("Blood test", f"{BLOOD_TEST_DAYS} days: only magic blood goes on; a failed test is final",
                          True))
        terms.append(("Learning", f"{POINTS[self.school]} points, 1d20 + INT a day, kept if you leave", True))
        terms.append(("Board", f"${BOARD_PER_DAY} a day with the meal, only on a day with no food in the pack",
                      True))
        where = ("alone, in a group of their own" if self.guild.free_slots or len(self.group.members) == 1
                 else "the whole group waits (no free group slot)")
        terms.append(("Who waits", where, True))
        terms.append(("Grants", "the school and its root in the magic talents; no spell", True))
        return terms

    def _rows(self):
        rows = []
        for u in self.group.members:
            blocked = blocker(self.guild, self.group, u, self.school)
            rows.append({"key": u.uid, "name": u.name, "status": self._status(u),
                         "face": {"race": u.race["name"], "portrait_id": getattr(u, "portrait_id", None),
                                  "token": u.token},
                         "sub": f"{u.race['name']} {u.occupation['name'].lower()}  ·  INT {u.mod_intelligence:+}",
                         "note": blocked or "", "enabled": blocked is None, "picked": u.uid == self.picked})
        return rows

    def _action(self):
        u = self._member(self.picked)
        if u is None or blocker(self.guild, self.group, u, self.school):
            return None
        return "RESUME THE RITE" if paid(u, self.school) else "BEGIN THE RITE"

    def _pick(self, uid):
        """Pick `uid` to stay (again: unpick); one who cannot stay is not picked, and says why."""
        u = self._member(uid)
        blocked = blocker(self.guild, self.group, u, self.school)
        self.notice = blocked
        self.picked = None if self.picked == uid or blocked else uid

    def _begin(self):
        """Begin the picked one's rite. Returns `(ok, lines)`."""
        ok, lines = begin(self.guild, self.group, self._member(self.picked), self.school)
        self.notice = "  ".join(lines)
        if ok:
            self.picked = None
        return ok, lines

    def hub_cards(self):
        purse = sum(u.money for u in self.group.members)
        return [{"label": "party purse", "value": fmt_money(purse), "tone": "money"}]
