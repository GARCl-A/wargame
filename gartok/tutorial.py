"""The tutorial: state only -- no pygame here, so `guild.py` can hold one
without breaking its "stays pygame-free" promise (see its module docstring).

An id names one card's worth of copy under `tutorial.<id>.*` in
`locales/en.json` (`i18n.py` resolves it at draw time -- `tutorial_card.py`
does the actual drawing). A screen exposes which id applies right now via
`Screen.tutorial_key()`; this module just remembers which ids the player has
already dismissed, whether the system is switched on at all, and which id (if
any) the player forced back open with a screen's `?` badge.
"""

from . import i18n

TUTORIALS = (
    "draft.intro", "draft.vocation", "draft.pick", "draft.identity", "combat_lab",
    "map",
    "guild.members", "guild.overview", "guild.reputations",
    "squad", "battle", "report", "memorial", "level_up", "loot", "reward",
    "market", "taverna", "hunt", "bank", "level", "library",
    "group", "missions", "trust", "ledger", "craft", "medic", "property", "claim", "guard", "dialogue", "prison", "stable", "wagon_yard", "watch", "garage", "gathering", "initiation",
    "group_turn"
)


def card(key):
    """The copy of `key`'s card: title, paragraphs, an optional closing pointer and the button."""
    title = i18n.t(f"tutorial.{key}.title")
    body = i18n.t(f"tutorial.{key}.body")
    if isinstance(body, str):
        body = [body]
    suggestion_key = f"tutorial.{key}.suggestion"
    suggestion = i18n.t(suggestion_key) if i18n.has(suggestion_key) else None
    button_key = f"tutorial.{key}.button"
    button = i18n.t(button_key if i18n.has(button_key) else "tutorial.default_button")
    return {"title": title, "body": list(body), "suggestion": suggestion, "button": button}


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
