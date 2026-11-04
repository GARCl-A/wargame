"""The Book of routines: the routines the player has written, and how many groups the guild may leave on
a routine at once.

Same shape as the group slots (`Guild.group_slots`): fame buys seats, and a seat is taken by every group
holding a routine, stopped or running. The player starts with none. The engine (`routines.assign`) knows
nothing of seats; the player's way in is `assign` here. A `Page` is a written routine with no pointer: a
group is given a copy, which becomes its `Routine`."""

from dataclasses import dataclass

from . import items, routines, world

NAME_MAX = 32
NOTE_MAX = 120

BASE_SLOTS = 0          # a new guild automates nothing
FAME_PER_SLOT = 6       # total reputation that buys one more group on a routine


def slots(guild):
    return BASE_SLOTS + guild.fame // FAME_PER_SLOT


def used(guild):
    return sum(1 for g in guild.groups if g.routine is not None)


def fame_to_next_slot(guild):
    return FAME_PER_SLOT - guild.fame % FAME_PER_SLOT


def assign(guild, group, routine):
    """Put `routine` on an idle `group` if a seat is free. Returns the log lines."""
    if group.routine is None and used(guild) >= slots(guild):
        raise ValueError("no free automation slot")
    return routines.assign(guild, group, routine)


@dataclass
class Page:
    name: str
    blocks: tuple = ()
    note: str = ""

    def to_dict(self):
        return {"name": self.name, "note": self.note, "blocks": routines.dump(self.blocks)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], routines.load(d["blocks"]), d.get("note", ""))


_TIMED = (routines.Gather, routines.Work, routines.Craft, routines.Rest)


def _item(name):
    if name not in items.all_items():
        raise ValueError(f"unknown item: {name}")


def _ref(ref, own_ok):
    if ref.how not in ("own", "named", "doing", "here"):
        raise ValueError(f"unknown way to name a group: {ref.how}")
    if ref.how == "own" and not own_ok:
        raise ValueError("a block that moves goods needs another group")
    if ref.how in ("named", "doing") and not ref.arg:
        raise ValueError("name the group")


def _cond(cond):
    if cond.op not in routines._OPS or cond.metric not in routines._METRICS:
        raise ValueError("unknown condition")
    if cond.metric == "items":
        _item(cond.item)
    _ref(cond.ref, True)


def _count(n):
    if n is not None and not n >= 1:
        raise ValueError("a count is at least 1")


def _check(guild, block):
    if isinstance(block, routines.Travel):
        if block.node not in {n.id for n in world.known(guild)}:
            raise ValueError(f"unknown place: {block.node}")
    elif isinstance(block, _TIMED):
        if not block.hours > 0:
            raise ValueError("hours are more than zero")
        if isinstance(block, routines.Craft) and block.recipe not in items.CRAFTING_RECIPES:
            raise ValueError(f"unknown recipe: {block.recipe}")
    elif isinstance(block, routines.Wait):
        _cond(block.cond)
    elif isinstance(block, (routines.Take, routines.HandOver)):
        _ref(block.source if isinstance(block, routines.Take) else block.to, False)
        _item(block.item)
        _count(block.count)
        if isinstance(block, routines.Take) and block.until_days is not None and block.until_days <= 0:
            raise ValueError("days of food are more than zero")
    elif isinstance(block, routines.Trade):
        for name in block.sell:
            _item(name)
        for name, count in block.buy:
            _item(name)
            _count(count)
        _item(block.food)
        if any(x is not None and x < 0 for x in (block.food_days, block.max_spend)):
            raise ValueError("a limit cannot be below zero")
    elif isinstance(block, routines.Repeat):
        _cond(block.cond)
        check(guild, block.body)
    else:
        raise TypeError(f"unknown block: {type(block).__name__}")


def check(guild, blocks):
    """Raise a ValueError with a line for the player when a block names what does not exist."""
    for block in blocks:
        _check(guild, block)


def _clean_name(guild, name, skip=None):
    name = " ".join((name or "").split())[:NAME_MAX]
    if not name:
        raise ValueError("a routine needs a name")
    if any(p.name == name for p in guild.routine_pages if p is not skip):
        raise ValueError(f"there is already a routine called {name}")
    return name


def write(guild, name):
    """Start an empty routine in the Book. Returns its index."""
    guild.routine_pages.append(Page(_clean_name(guild, name)))
    return len(guild.routine_pages) - 1


def save(guild, index, name, note, blocks_data):
    """Replace page `index` with what the editor sent (the `routines.dump` shape). Nothing changes on a refusal."""
    page = guild.routine_pages[index]
    try:
        blocks = routines.load(blocks_data)
        if not isinstance(blocks, tuple):
            raise TypeError("a routine is a list of blocks")
        check(guild, blocks)
    except (KeyError, TypeError) as err:
        raise ValueError("that routine is not well formed") from err
    page.name = _clean_name(guild, name, page)
    page.note = " ".join((note or "").split())[:NOTE_MAX]
    page.blocks = blocks


def tear(guild, index):
    del guild.routine_pages[index]
