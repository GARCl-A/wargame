"""A new guild's draft: a pool of nine candidates, pick three, then name the guild, pick its banner
and choose which of the three leads it.

The player has 3 Commission Tokens across the whole draft to call the archetypes the pool lacks
(Leaders, Strong, Tough, etc.): the commission picks the archetypes, then the candidate it replaces.
A replaced card that was picked leaves the squad. The name and banner are cosmetic (`Guild.name`,
`banner_color`, `banner_icon`); the leader is `Guild.leader`. `web/draft_session.py` drives it."""

from . import art_files, recruit, vocations
from .archetypes import generate_candidate
from .guild import BANNER_COLORS
from .unit import Unit

TEAM_SIZE = 3
POOL_SIZE = 9
COMMISSION_TOKENS = 3
MAX_GUILD_NAME = 24


def leader_recruits(u):
    """How many people `u` could sponsor as the guild's leader, and why."""
    parts = [f"base {recruit.BASE_RECRUIT_CAPACITY}", f"CHA {u.mod_charisma:+d}"]
    if u.racial_level:
        parts.append(f"level {u.racial_level:+d}")
    return recruit.leader_capacity(u), " · ".join(parts)


class Draft:
    def __init__(self, vocation=None):
        self.vocation = vocation
        self.pool = ([Unit("player", race=r) for r in vocations.draft_pool(vocation, POOL_SIZE)]
                     if vocation else [Unit("player") for _ in range(POOL_SIZE)])
        self.picks = []
        self.tokens = COMMISSION_TOKENS
        self.commissioned = {}     # id(unit) -> the archetypes that were called for it
        self.pending_labels = []   # a confirmed commission waiting for the card it replaces
        self.guild_name = ""
        self.banner_color = BANNER_COLORS[0][1]
        self.banner_icon = art_files.BANNER_ICONS[0][1]
        self.leader_pick = None

    def toggle_pick(self, unit):
        if unit in self.picks:
            self.picks.remove(unit)
        elif len(self.picks) < TEAM_SIZE:
            self.picks.append(unit)

    def replace(self, unit):
        """Spend the pending commission on `unit`'s slot in the pool."""
        labels = self.pending_labels
        fresh = generate_candidate(labels)
        self.pool[self.pool.index(unit)] = fresh
        if unit in self.picks:
            self.picks.remove(unit)
        self.commissioned.pop(id(unit), None)
        self.commissioned[id(fresh)] = list(labels)
        self.tokens -= len(labels)
        self.pending_labels = []
