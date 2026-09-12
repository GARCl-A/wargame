"""The soft tutorial: state only -- no pygame here, so `guild.py` can hold one
without breaking its "stays pygame-free" promise (see its module docstring).

An id names one card's worth of copy under `tutorial.<id>.*` in
`locales/en.json` (`i18n.py` resolves it at draw time -- `tutorial_card.py`
does the actual drawing). A screen exposes which id applies right now via
`Screen.tutorial_key()`; this module just remembers which ids the player has
already dismissed, whether the system is switched on at all, and which id (if
any) the player forced back open with a screen's `?` badge.
"""

TUTORIALS = (
    "draft.pick", "draft.identity", "draft.leader",
    "map",
    "guild.members", "guild.reputations",
    "squad", "battle", "loot", "reward",
    "market", "taverna", "hunt", "bank", "gear", "level",
)


class TutorialState:
    def __init__(self, seen=None, enabled=True):
        self.seen = set(seen or ())
        self.enabled = enabled
        self.showing = None       # an id forced open by the `?` badge, or None

    def should_show(self, key):
        if not self.enabled or key is None:
            return False
        return key == self.showing or key not in self.seen

    def dismiss(self, key):
        self.seen.add(key)
        if self.showing == key:
            self.showing = None

    def reopen(self, key):
        self.showing = key

    def reset(self):
        self.seen.clear()
        self.showing = None
