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

from . import data, economy, factions, i18n, items, orders, world
from .constants import fmt_money

SANCTUARY = {"blood_sanctuary": "blood", "nature_grove": "nature", "faith_cathedral": "faith"}
FACTION = {"blood": "blood_cult", "nature": "nature_coven", "faith": "faith_order"}
REP_NEEDED = 2
POINTS = {"faith": 180, "blood": 90, "nature": 270}
BLOOD_TEST_DAYS = 7
BOARD_PER_DAY = 3
HOLY_SYMBOL = items.HOLY_SYMBOL_ITEM
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
        return i18n.t("rite.is_already_initiated_in_magic", name=unit.name, school=name)
    if guild.reputation.get(FACTION[school], 0) < REP_NEEDED:
        return i18n.t("rite.school_takes_no_one_until", rep_needed=REP_NEEDED)
    if school == "blood" and unit.blood_tested and not unit.magic_blood:
        return i18n.t("rite.cult_tested_s_blood_there", name=unit.name)
    if school == "faith" and not paid(unit, school) and not any(u.has_item(HOLY_SYMBOL) for u in _holders(group)):
        return i18n.t("rite.rite_consumes_and_group_carries", holy_symbol=HOLY_SYMBOL)
    if group.locked:
        return i18n.t("rite.group_with_order_in_flight")
    return None


def stage(unit, school):
    """`(label, done, total)` of where `unit` stands in `school`'s rite."""
    if school == "blood" and not unit.blood_tested:
        return i18n.t("rite.blood_test"), unit.blood_test_days, BLOOD_TEST_DAYS
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
        lines.append(i18n.t("rite.order_takes_s", name=holder.name, holy_symbol=HOLY_SYMBOL))
    unit.rite_progress.setdefault(school, 0)
    unit.rite_school = school
    order = orders.garrison(JOB)
    if guild.send_alone(group, unit, order, f"{unit.name} (rite)") is None:
        group.order = order
        lines.append(i18n.t("rite.no_free_group_slot_group", name=unit.name))
    else:
        lines.append(i18n.t("rite.stays_to_board_at_sanctuary", name=unit.name, title=school.title()))
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
            return i18n.t("rite.blood_cult_finds_no_magic", name=unit.name)
        return i18n.t("rite.blood_cult_finds_magic_in", name=unit.name)
    unit.rite_progress[school] = unit.rite_progress.get(school, 0) + max(0, data.roll(1, 20) + unit.mod_intelligence)
    if unit.rite_progress[school] < POINTS[school]:
        return None
    unit.rite_school = None
    unit.add_magic_source(school)
    unit._derive_combat()
    return i18n.t("rite.is_initiated_into_magic", name=unit.name, title=school.title())


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
        events.append(i18n.t("rite.nobody_left_boarding_for_rite", name=world.node(group.node).name))
    return events


class Initiation:
    """A sanctuary's INITIATION tab with no window: the school's terms, who may stay to board and why not,
    the pick and the begin. `web/initiation_tab.py` draws it."""

    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.school = school_at(group.node)
        self.picked = None
        self.notice = None

    def _member(self, uid):
        return next((u for u in self.group.members if u.uid == uid), None)

    def _status(self, u):
        if self.school in u.magic_sources:
            return i18n.t("rite.initiated_in_magic", title=self.school.title())
        label, done, total = stage(u, self.school)
        if label == "blood test":
            left = i18n.t("rite.day_s_of_testing_then", value=total - done, points=POINTS['blood'])
        else:
            per_day = max(1, 10.5 + u.mod_intelligence)
            left = i18n.t("rite.learning_points_about_day_s", done=done, total=total, round=round((total - done) / per_day))
        boarding = "boarding  ·  " if u.rite_school == self.school else ""
        return i18n.t("rite.int", boarding=boarding, left=left, mod_intelligence=u.mod_intelligence)

    def _terms(self):
        faction = FACTION[self.school]
        have = self.guild.reputation.get(faction, 0)
        terms = [(i18n.t("rite.school"), i18n.t("rite.reputation_of", name=factions.FACTIONS[faction].name, have=have, rep_needed=REP_NEEDED),
                  have >= REP_NEEDED)]
        if self.school == "faith":
            terms.append((i18n.t("rite.up_front"), i18n.t("rite.one_consumed", holy_symbol=HOLY_SYMBOL), True))
        if self.school == "blood":
            terms.append((i18n.t("rite.blood_test_2"), i18n.t("rite.days_only_magic_blood_goes", blood_test_days=BLOOD_TEST_DAYS),
                          True))
        terms.append(("Learning", i18n.t("rite.points_d_int_day_kept", points=POINTS[self.school]), True))
        terms.append(("Board", i18n.t("rite.day_with_meal_only_on", board_per_day=BOARD_PER_DAY),
                      True))
        where = (i18n.t("rite.alone_in_group_of_their") if self.guild.free_slots or len(self.group.members) == 1
                 else i18n.t("rite.whole_group_waits_no_free"))
        terms.append((i18n.t("rite.who_waits"), where, True))
        terms.append(("Grants", i18n.t("rite.school_and_its_root_in"), True))
        return terms

    def _rows(self):
        rows = []
        for u in self.group.members:
            blocked = blocker(self.guild, self.group, u, self.school)
            rows.append({"key": u.uid, "name": u.name, "status": self._status(u),
                         "face": {"race": u.race["name"], "portrait_id": getattr(u, "portrait_id", None),
                                  "token": u.token},
                         "sub": i18n.t("rite.int_2", race=u.race_label, mod_intelligence=u.mod_intelligence),
                         "note": blocked or "", "enabled": blocked is None, "picked": u.uid == self.picked})
        return rows

    def _action(self):
        u = self._member(self.picked)
        if u is None or blocker(self.guild, self.group, u, self.school):
            return None
        return i18n.t("rite.resume_rite") if paid(u, self.school) else i18n.t("rite.begin_rite")

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
        return [{"label": i18n.t("rite.party_purse"), "value": fmt_money(purse), "tone": "money"}]
