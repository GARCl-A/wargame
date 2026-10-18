"""What the screens after a fight are built from: the after-action report's rows, the level-ups
with their before / after numbers, and the memorial of a lost character (in battle or not).

Pure data, filled in by `campaign.absorb_battle` (and by the daily upkeep for a death off the
field); `report_screen`, `level_up_screen` and `memorial_screen` draw it."""

from dataclasses import dataclass, field


@dataclass
class Memorial:
    name: str
    race: str
    occupation: str
    portrait_id: object
    joined_day: int
    day: int
    cause: str                       # "Killed in combat", "Starved to death"
    place: str | None = None
    killer: str | None = None        # who put them down, when a blow did
    line: str | None = None          # the log line of the fall, or how it came

    @property
    def days_lived(self):
        return max(1, self.day - self.joined_day + 1)


def memorial(unit, *, day, cause, place=None, killer=None, line=None):
    return Memorial(unit.name, unit.race["name"], unit.occupation["name"], unit.portrait_id,
                    unit.joined_day, day, cause, place, killer, line)


def starved(unit, *, day, place=None):
    days = unit.unfed_days
    return memorial(unit, day=day, cause="Starved to death", place=place,
                    line=f"{days} day{'s' if days != 1 else ''} without a meal.")


@dataclass
class LevelUp:
    unit: object
    before: dict
    after: dict

    @property
    def gains(self):
        """`[(label, before, after)]` for every number that moved, in reading order."""
        return [(label, self.before.get(k, 0), self.after.get(k, 0)) for k, label in LEVEL_FIELDS
                if self.after.get(k, 0) != self.before.get(k, 0)]


LEVEL_FIELDS = (("combat", "Combat level"), ("work", "Work level"), ("magic", "Magic level"),
                ("racial", "Racial level"), ("hit_dice", "Hit dice"), ("hp_max", "Max HP"))


def level_snapshot(unit):
    return {"combat": unit.combat_level, "work": unit.work_level, "magic": unit.magic_level,
            "racial": unit.racial_level, "hit_dice": 1 + len(unit._level_hp_rolls),
            "hp_max": unit.hp_max}


@dataclass
class ReportRow:
    name: str
    race: str
    portrait_id: object
    status: str                      # standing | stable | fled | fallen
    downed: list = field(default_factory=list)   # foe names this one put down
    xp_before: int = 0               # combat XP before the fight
    xp_gain: int = 0
    magic_gain: int = 0


def status_of(combatant):
    if not combatant.survived:
        return "fallen"
    if combatant.fled:
        return "fled"
    if combatant.status in ("stable", "broken"):
        return "stable"
    return "standing"


def takedowns(battle):
    """`[(who, whom, mine)]`: every downed body with the hand that put it down, the
    squad's own losses included (`mine` is True when the victim was on the squad)."""
    return [(c.downed_by.name, c.name, c.team == "player")
            for c in battle.units if getattr(c, "downed_by", None) is not None]


def result_word(battle, side="player"):
    """VICTORY / FLED / DEFEAT for `side`, the one word every after-battle header uses."""
    if battle.winner == side:
        return "VICTORY"
    if any(u.team == side and u.fled for u in battle.units):
        return "FLED"
    return "DEFEAT"
