"""The tanner's last job: finding Aurochs, the immortal ox.

Three steps, each its own rule here:

- the **Country Roads** hide the Ox Fields until the guild searches them with the
  job out (`scout_country_roads`, a Wisdom check); once found they stay on the map;
- at the Fields the party **tracks** the beast (`track`): one Wisdom check per hour
  of daylight against a DC that climbs `TRACK_DC_STEP` every time the trail was
  found before -- a lost hunt is run again, harder;
- a found trail opens the tactical map (`ox_fields.OxFieldsScenario`).

Aurochs himself is authored (`npcs/aurochs.json`); killing him closes the trail
(`missions.slay_ox`) and drops the hide and the horn (`loot.UNIQUE_DROPS`).
"""

import random

from . import clock, data, fight_nature, i18n, missions, npc_lib
from .ox_fields import AUROCHS_SLUG

SCOUT_HOURS = 2
SCOUT_DC = 10
TRACK_DC = 12
TRACK_DC_STEP = 2
TRACK_SHIFT_HOURS = (2, 4, 6, 8)
TRACK_NATURE = fight_nature.SOUGHT     # the band runs the ox down


def _scout(party):
    return max(party, key=lambda u: u.mod_wisdom) if party else None


def scout_country_roads(guild, group):
    """The roll at the end of `SCOUT_HOURS` on the lanes (an `orders.search` order) for the fields the tanner talks
    about. Only finds them while the ox job is out. -> (found, message)."""
    scout = _scout(group.members)
    who = scout.name if scout else i18n.t("ox.squad")
    if missions.pending_ox(guild) is None:
        return False, i18n.t("ox.walks_lanes_for_hours_farms", who=who, scout_hours=SCOUT_HOURS)
    nat = data.d20()
    total = nat + (scout.mod_wisdom if scout else 0)
    if total >= SCOUT_DC:
        guild.reveal_node("ox_fields")
        return True, (i18n.t("ox.follows_churned_earth_to_where", who=who))
    return False, (i18n.t("ox.searches_lanes_for_hours_and", who=who, scout_hours=SCOUT_HOURS, nat=nat, value=scout.mod_wisdom if scout else 0, total=total, scout_dc=SCOUT_DC))


def track_dc(guild):
    return TRACK_DC + TRACK_DC_STEP * guild.ox_trails


def daylight_hours(hour):
    """Hours of daylight left from clock `hour` (0 once it is dark): the trail is
    only read by day."""
    n = 0
    while n < 24 and clock.daylight_at(hour + n):
        n += 1
    return n


def track(state, guild, rng=random):
    """Spend the hunt's hours one at a time, each a Wisdom check of the best
    tracker against `track_dc`. Mutates `state` (`hours_left` down, `hours_hunted`
    up). -> `(elapsed_hours, found)`; a found trail counts toward the next DC."""
    scout = _scout(state.party)
    mod = scout.mod_wisdom if scout else 0
    dc = track_dc(guild)
    elapsed = 0
    while state.hours_left > 0:
        state.hours_left -= 1
        state.hours_hunted += 1
        elapsed += 1
        if rng.randint(1, 20) + mod >= dc:
            guild.ox_trails += 1
            return elapsed, True
    return elapsed, False


def aurochs_pack():
    return [npc_lib.load_npc(AUROCHS_SLUG)]
