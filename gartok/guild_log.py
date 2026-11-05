"""The guild's history: what happened while the days passed, kept per guild and saved with it.

An entry is a list `[t, kind, band, text, tone]` (compact on purpose: the save is written with
indent=2). `t` is the clock's seconds, so the day and the hour come off it; `band` is the group's
name at the time, or None for the guild as a whole. A line is written where it is born (the clock's
upkeep and orders, a fight, a talk), never from the map's `notices`, which only say what to show now.
"""

import bisect
import os
import re

from . import i18n
from .clock import SECONDS_PER_DAY, SECONDS_PER_HOUR

KINDS = ("food", "work", "craft", "travel", "rest", "fight", "talk", "guild", "day")
NEAR_FULL = 0.9

# a line that is a warning: the player is told when a step fails, a body falls or food spoils
BAD = re.compile(r"\b(died|dies|starved|did not eat|hungry|rotted|sick|Gut Rot|no haul|ran short|"
                 r"lost|lose|fails?|failed|broke|ambush|killed|dead|poison)", re.IGNORECASE)


def export_dir():
    """Beside `saves`, like `settings.json`; imported late because `persist` imports the guild."""
    from . import persist
    return os.path.join(os.path.dirname(persist.SAVE_DIR), "log-export")


def stamp(t):
    """`(day, "hh:mm")` of clock second `t`."""
    return t // SECONDS_PER_DAY + 1, f"{t // SECONDS_PER_HOUR % 24:02d}:{t // 60 % 60:02d}"


class GuildLog:
    def __init__(self, entries=None, cap=None):
        self.entries = [list(e) for e in entries or ()]
        self.cap = cap                       # a fixed limit (tests); else the player's `log_lines` setting
        self.muted = False                   # "later" answered to the full prompt, until the next load
        self._trim()

    @property
    def limit(self):
        from . import settings
        return self.cap or settings.get("log_lines")

    @property
    def full(self):
        return len(self.entries) >= self.limit

    @property
    def near_full(self):
        return len(self.entries) >= self.limit * NEAR_FULL

    @property
    def prompt(self):
        """The full-log question is due: asked on the map only, so it never cuts a jump short."""
        return self.full and not self.muted

    def record(self, lines, t, kind, band=None):
        """Add `lines` at clock second `t` (kept in order of `t`, a later line of the same second after)."""
        for text in lines:
            entry = [int(t), kind, band, text, "bad" if BAD.search(text) else ""]
            at = bisect.bisect_right(self.entries, entry[0], key=lambda e: e[0])
            self.entries.insert(at, entry)
        self._trim()

    def _trim(self):
        extra = len(self.entries) - self.limit
        if extra > 0:
            del self.entries[:extra]

    def rows(self, entries):
        out = []
        for t, kind, band, text, tone in entries:
            day, at = stamp(t)
            out.append({"day": day, "at": at, "kind": kind, "band": band, "text": text, "tone": tone})
        return out

    def tail(self, n):
        return self.rows(self.entries[-n:])

    def search(self, q="", kind=None, band=None, limit=500):
        """The lines holding `q` (any case), narrowed to a kind and to a band (`"-"` = the guild's own),
        newest last; the last `limit` of them."""
        q = (q or "").strip().lower()
        hits = [e for e in self.entries
                if (not kind or e[1] == kind)
                and (not band or (e[2] is None if band == "-" else e[2] == band))
                and (not q or q in e[3].lower() or q in (e[2] or "").lower())]
        return self.rows(hits[-limit:]), len(hits)

    def _oldest_half(self):
        return max(1, len(self.entries) // 2)

    def discard_oldest(self):
        n = self._oldest_half()
        del self.entries[:n]
        self.muted = False
        return n

    def export_and_trim(self, guild_name, day):
        """Write the oldest half to `log-export/` as text and drop it. -> the path written."""
        n = self._oldest_half()
        folder = export_dir()
        os.makedirs(folder, exist_ok=True)
        safe = re.sub(r"[^\w .-]", "", guild_name or i18n.t("guild_log.guild")).strip() or i18n.t("guild_log.guild")
        path = os.path.join(folder, f"{safe}-day{day}.txt")
        stem, n_file = path[:-4], 1
        while os.path.exists(path):
            n_file += 1
            path = f"{stem}-{n_file}.txt"
        with open(path, "w", encoding="utf-8") as fh:
            for row in self.rows(self.entries[:n]):
                who = f"[{row['band']}] " if row["band"] else ""
                fh.write(i18n.t("guild_log.day", day=row['day'], at=row['at'], who=who, text=row['text']))
        self.discard_oldest()
        return path

    def to_list(self):
        return [list(e) for e in self.entries]
