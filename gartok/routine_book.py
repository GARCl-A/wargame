"""The Book of routines: the routines the player has written, and how many groups the guild may leave on
a routine at once.

Same shape as the group slots (`Guild.group_slots`): fame buys seats, and a seat is taken by every group
holding a routine, stopped or running. The player starts with none. The engine (`routines.assign`) knows
nothing of seats; the player's way in is `assign` here. A `Page` is a written routine with no pointer: a
group is given a copy, which becomes its `Routine`."""

from dataclasses import dataclass

from . import data, i18n, items, magic, routines, world

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
        raise ValueError(i18n.t("routine_book.no_free_automation_slot"))
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
        raise ValueError(i18n.t("routine_book.unknown_item", name=name))


def _ref(ref, own_ok):
    if ref.how not in ("own", "named", "doing", "here"):
        raise ValueError(i18n.t("routine_book.unknown_way_to_name_group", how=ref.how))
    if ref.how == "own" and not own_ok:
        raise ValueError(i18n.t("routine_book.block_that_moves_goods_needs"))
    if ref.how in ("named", "doing") and not ref.arg:
        raise ValueError(i18n.t("routine_book.name_group"))


def _cond(cond):
    if cond.op not in routines._OPS or cond.metric not in routines._METRICS:
        raise ValueError(i18n.t("routine_book.unknown_condition"))
    if cond.metric == "items":
        _item(cond.item)
    _ref(cond.ref, True)


def _count(n):
    if n is not None and not n >= 1:
        raise ValueError(i18n.t("routine_book.count_is_at_least"))


def _check(guild, block):
    if isinstance(block, routines.Travel):
        if block.node not in {n.id for n in world.known(guild)}:
            raise ValueError(i18n.t("routine_book.unknown_place", node=block.node))
    elif isinstance(block, _TIMED):
        if not block.hours > 0:
            raise ValueError(i18n.t("routine_book.hours_are_more_than_zero"))
        if isinstance(block, routines.Craft) and block.recipe not in items.CRAFTING_RECIPES:
            raise ValueError(i18n.t("routine_book.unknown_recipe", recipe=block.recipe))
    elif isinstance(block, routines.Study):
        if block.target not in magic.SPELLS and block.target not in data.LANGUAGES:
            raise ValueError(i18n.t("routine_book.unknown_thing_to_study", target=block.target))
        if not block.days > 0:
            raise ValueError(i18n.t("routine_book.days_are_more_than_zero"))
    elif isinstance(block, routines.Repair):
        if not block.wagon.strip():
            raise ValueError(i18n.t("routine_book.name_wagon_to_mend"))
    elif isinstance(block, (routines.Store, routines.Fetch)):
        if block.place not in routines.PLACES:
            raise ValueError(i18n.t("routine_book.unknown_stash", place=block.place))
        _item(block.item)
        _count(block.count)
    elif isinstance(block, routines.Wait):
        _cond(block.cond)
    elif isinstance(block, (routines.Take, routines.HandOver)):
        _ref(block.source if isinstance(block, routines.Take) else block.to, False)
        _item(block.item)
        _count(block.count)
        if isinstance(block, routines.Take) and block.until_days is not None and block.until_days <= 0:
            raise ValueError(i18n.t("routine_book.days_of_food_are_more"))
    elif isinstance(block, routines.Trade):
        for name in block.sell:
            _item(name)
        for name, count in block.buy:
            _item(name)
            _count(count)
        _item(block.food)
        if any(x is not None and x < 0 for x in (block.food_days, block.max_spend)):
            raise ValueError(i18n.t("routine_book.limit_cannot_be_below_zero"))
    elif isinstance(block, routines.Repeat):
        _cond(block.cond)
        check(guild, block.body)
    else:
        raise TypeError(i18n.t("routine_book.unknown_block", name=type(block).__name__))


def check(guild, blocks):
    """Raise a ValueError with a line for the player when a block names what does not exist."""
    for block in blocks:
        _check(guild, block)


def _clean_name(guild, name, skip=None):
    name = " ".join((name or "").split())[:NAME_MAX]
    if not name:
        raise ValueError(i18n.t("routine_book.routine_needs_name"))
    if any(p.name == name for p in guild.routine_pages if p is not skip):
        raise ValueError(i18n.t("routine_book.there_is_already_routine_called", name=name))
    return name


def write(guild, name):
    """Start an empty routine in the Book. Returns its index."""
    guild.routine_pages.append(Page(_clean_name(guild, name)))
    return len(guild.routine_pages) - 1


def save(guild, index, name, note, blocks_data):
    """Replace page `index` with what the editor sent (the `routines.dump` shape). Nothing changes on a refusal."""
    page = guild.routine_pages[index]
    blocks = _parse(guild, blocks_data)
    page.name = _clean_name(guild, name, page)
    page.note = " ".join((note or "").split())[:NOTE_MAX]
    page.blocks = blocks


def tear(guild, index):
    del guild.routine_pages[index]


def _parse(guild, blocks_data):
    try:
        blocks = routines.load(blocks_data)
        if not isinstance(blocks, tuple):
            raise TypeError(i18n.t("routine_book.routine_is_list_of_blocks"))
        check(guild, blocks)
    except (KeyError, TypeError) as err:
        raise ValueError(i18n.t("routine_book.that_routine_is_not_well")) from err
    return blocks


def equip(guild, group, index):
    """Give an idle `group` a copy of page `index`: what it adjusts afterwards never touches the Book."""
    page = guild.routine_pages[index]
    if group.routine is not None:
        raise ValueError(i18n.t("routine_book.already_has_routine", display_name=group.display_name))
    copy = routines.Routine(routines.load(routines.dump(page.blocks)), name=page.name, note=page.note)
    return assign(guild, group, copy)


def _fits(blocks, path):
    level = blocks
    for depth, i in enumerate(path):
        if i >= len(level):
            return False
        if depth < len(path) - 1:
            if not isinstance(level[i], routines.Repeat):
                return False
            level = level[i].body
    return True


def adjust(guild, group, blocks_data):
    """Replace the blocks of the routine on `group`; the pointer stays when it still points at a block, else
    the routine starts over. Nothing changes on a refusal."""
    routine = group.routine
    blocks = _parse(guild, blocks_data)
    routine.blocks = blocks
    if not _fits(blocks, routine.path):
        routine.path, routine.inflight, routine.waited_since = [0], False, None


def take_off(group):
    """The group is given back to the player; an order already out is left to finish."""
    group.routine = None


def save_back(guild, group):
    """Send the group's copy to the Book as a page of its own. Returns its index."""
    routine = group.routine
    base = routine.name or "Routine"
    name, n = base, 1
    while any(p.name == name for p in guild.routine_pages):
        n += 1
        name = f"{base} {n}"[:NAME_MAX]
    guild.routine_pages.append(Page(name, routine.blocks, routine.note))
    return len(guild.routine_pages) - 1
