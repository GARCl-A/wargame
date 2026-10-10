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

from . import clock, data, missions, npc_lib
from .ox_fields import AUROCHS_SLUG

SCOUT_HOURS = 2
SCOUT_DC = 10
TRACK_DC = 12
TRACK_DC_STEP = 2
TRACK_SHIFT_HOURS = (2, 4, 6, 8)


def _scout(party):
    return max(party, key=lambda u: u.mod_wisdom) if party else None


def scout_country_roads(guild, group):
    """Spend `SCOUT_HOURS` searching the lanes for the fields the tanner talks
    about. Only finds them while the ox job is out. -> (found, message)."""
    guild.clock.advance_hours(SCOUT_HOURS)
    scout = _scout(group.members)
    who = scout.name if scout else "The squad"
    if missions.pending_ox(guild) is None:
        return False, f"{who} walks the lanes for {SCOUT_HOURS} hours: farms, fences and nothing worth the trip."
    nat = data.d20()
    total = nat + (scout.mod_wisdom if scout else 0)
    if total >= SCOUT_DC:
        guild.ox_fields_discovered = True
        return True, (f"{who} follows the churned earth to where the land opens out. "
                      "The Legendary Ox Fields are found.")
    return False, (f"{who} searches the lanes for {SCOUT_HOURS} hours and finds no sign "
                   f"(d20({nat}) {scout.mod_wisdom if scout else 0:+}(WIS) = {total} vs DC {SCOUT_DC}).")


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
