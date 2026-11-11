"""The Demon Cult's site (`docs/plans/holy_symbol_quest.md`): the hidden place off the Country Roads where
Edric Ashvale's daughter is held for the ritual.

The node is ethereal (`world.add_node`): it is on the map, with its two roads (the Country Roads, the Faith
Cathedral), only once the guild has found it, so a route never walks through a place the guild cannot see.
Finding it is a search of the Country Roads while the job is out: Wisdom against a hard DC, helped by every
clue asking around turned up (`investigation.bonus`).
"""

from . import data, i18n, investigation, missions, world

NODE = "cult_site"
SEARCH_HOURS = 2
SEARCH_DC = 22
SEARCH_PER_CLUE = 2
POS = (0.76, 0.95)
LINKS = (("country_roads", 2), ("faith_cathedral", 2))


def quest_active(guild):
    return missions.active(guild, missions.FARMER_DAUGHTER)


def _node():
    return world.Node(NODE, "Demon Cult Site", "town", POS, floor="earth")


def sync_world(guild):
    """Put the site back on the map when the guild has found it (after a load, or a new guild)."""
    if world.exists(NODE):
        world.remove_node(NODE)
    if guild.is_node_revealed(NODE):
        world.add_node(_node(), list(LINKS))


def reveal(guild):
    """The site is found: on the guild's map and in the world. -> whether it was new."""
    new = guild.reveal_node(NODE)
    sync_world(guild)
    return new


def search_bonus(guild):
    return investigation.bonus(guild, missions.FARMER_DAUGHTER.id, SEARCH_PER_CLUE)


def search(guild, group):
    """The roll at the end of `SEARCH_HOURS` on the Country Roads. -> (found, message)."""
    scout = max(group.members, key=lambda u: u.mod_wisdom) if group.members else None
    who = scout.name if scout else i18n.t("ox.squad")
    if not quest_active(guild):
        return False, i18n.t("cult_site.nothing_on_the_roads", who=who, hours=SEARCH_HOURS)
    if guild.is_node_revealed(NODE):
        return True, i18n.t("cult_site.already_found", who=who)
    nat = data.d20()
    mod = scout.mod_wisdom if scout else 0
    bonus = search_bonus(guild)
    total = nat + mod + bonus
    if total >= SEARCH_DC:
        reveal(guild)
        return True, i18n.t("cult_site.found", who=who)
    return False, i18n.t("cult_site.missed", who=who, hours=SEARCH_HOURS, nat=nat, mod=f"{mod:+}", bonus=bonus,
                         total=total, dc=SEARCH_DC)
