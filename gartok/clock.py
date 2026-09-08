"""The campaign clock: one running count of elapsed time.

The guild carries a single `Clock`. Travelling between map nodes advances it by
hours; a battle advances it by `SECONDS_PER_ROUND` per round fought. Everything
time-shaped reads off this: day/night for outdoor scenarios now, rest and
healing over time later.

Stored as whole seconds so a short battle still moves the needle without float
drift. Day starts at hour `DAY_START`, night at `NIGHT_START`.
"""

SECONDS_PER_HOUR = 3600
HOURS_PER_DAY = 24
SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY
SECONDS_PER_ROUND = 6

DAY_START = 6
NIGHT_START = 18


class Clock:
    def __init__(self, seconds=0):
        self.seconds = int(seconds)

    # advancing -------------------------------------------------------- #
    def advance_seconds(self, s):
        self.seconds += int(s)

    def advance_hours(self, h):
        self.seconds += int(round(h * SECONDS_PER_HOUR))

    def advance_rounds(self, rounds):
        self.seconds += rounds * SECONDS_PER_ROUND

    # reading -------------------------------------------------------- #
    @property
    def day(self):
        return self.seconds // SECONDS_PER_DAY + 1

    @property
    def hour_of_day(self):
        return (self.seconds // SECONDS_PER_HOUR) % HOURS_PER_DAY

    @property
    def minute_of_hour(self):
        return (self.seconds // 60) % 60

    @property
    def is_daylight(self):
        return DAY_START <= self.hour_of_day < NIGHT_START

    @property
    def phase(self):
        return "dia" if self.is_daylight else "noite"

    @property
    def label(self):
        return f"Dia {self.day}  {self.hour_of_day:02d}:{self.minute_of_hour:02d}  ({self.phase})"

    def __repr__(self):
        return f"<Clock {self.label}>"
