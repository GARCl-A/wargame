"""One-time rule cards a trigger fires (the rules players miss): the card is a tutorial id, so
`TutorialState.seen` is its saved "seen" flag, and it carries a button that opens the wiki on the entry
that holds the rule (`wiki_ref`). The map and the battle ask here which one is due."""

from . import actions, items, wiki_rules

STUDY, ROAD, READING, FALLEN, DUNGEON, PLACE, FLANK = ("hint.study", "hint.road", "hint.reading", "hint.fallen", "hint.dungeon",
                                                       "hint.place", "hint.flank")
IDS = (STUDY, ROAD, READING, FALLEN, DUNGEON, PLACE, FLANK)


def _studyable(unit):
    return any((d := items.get(it.name)) and (d.spell_id or d.language or d.recipe_id) for it in unit.inventory)


def on_map(guild, seen):
    """The hint the map owes the player now, or None: a studyable item in a pack, a band on the road."""
    if STUDY not in seen and any(_studyable(u) for u in guild.roster):
        return STUDY
    if ROAD not in seen and any(g.order is not None and g.order.kind == "travel" for g in guild.groups):
        return ROAD
    return None


def _flank_seen(battle, visible):
    """A flank on the board that involves the player's side, in either direction: a foe it flanks, or a member of it that is flanked."""
    live = [u for u in battle.units if u.alive and visible(u)]
    return any(a.team != t.team and "player" in (a.team, t.team) and actions._flanked(battle, a, t)
               for a in live for t in live)


def in_battle(guild, battle, seen, visible=lambda unit: True):
    """The hint a campaign fight owes the player now, or None: a fallen member of the squad, a place the squad has to walk out of, a flank, a second fight.
    `visible` says which units the player's side can see, so a card never gives away a foe it has not met."""
    if PLACE not in seen and battle.place_queue and battle.place_queue[0].team == "player":
        return PLACE
    if FALLEN not in seen and any(u.team == "player" and u.status == "dying" for u in battle.units):
        return FALLEN
    if DUNGEON not in seen and battle.scenario.holds_field(battle):
        return DUNGEON
    if FLANK not in seen and _flank_seen(battle, visible):
        return FLANK
    if READING not in seen and guild.battles_won >= 1:
        return READING
    return None


def wiki_ref(hint):
    """The wiki entry (`chapter:id`) that holds the rule `hint` announces."""
    return {STUDY: "rules:" + wiki_rules.title("study"), ROAD: "rules:" + wiki_rules.title("hunger"),
            READING: "rules:" + wiki_rules.title("reading"), FALLEN: "actions:stabilize",
            DUNGEON: "rules:" + wiki_rules.title("dungeon"), PLACE: "rules:" + wiki_rules.title("placement"),
            FLANK: "rules:" + wiki_rules.title("flanking")}.get(hint)
