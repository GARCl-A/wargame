"""The Champion of the Pit: the arena's one personal title.

Beating the pit's champion team -- Adelio Small-Knife and two hired nobodies --
is the deed `factions.arena_dethrone`. Whoever on the winning squad lands the
blow that puts Adelio down takes his title. It is a *character's* title, held on
the `Unit` (`unit.arena_title`), never the guild's. A messy finish (nobody on the
player's side put him down cleanly -- e.g. his own hireling dropped him) leaves
the title vacant, and there is no rematch: the deed is banked either way.

The title only bites inside the arena (`battle.arena`), all in `actions.Demoralize`:
- Demoralize any target, shared language or not;
- +1 to the roll when a language IS shared;
- +1 Mental Defense against Demoralize.

Holding it draws challengers. Every `CHALLENGE_CYCLE` days a formal challenge
falls due; the champion has `CHALLENGE_GRACE` days to turn up at the arena for a
1v1 or the title is forfeit -- again, for good. `guild.arena_challenge_day` is the
day the current challenge came due (or None). The challenger is built to the
champion's own mean level + 1, so as the champion levels on these fights the
newcomers drifting into the pits keep pace.

Once Adelio has been dethroned he becomes a fixture: `ADELIO_CAMEO_CHANCE` that
any ordinary pit bout fields him as one of the opponents. He never levels.
"""

import random

from . import encounters, npc_lib, world

CHAMPION_SLUG = "adelio-small-knife"

CHAMPION_GOONS = 2                 # random level-0 bodies fighting alongside the champion
CHAMPION_ENTRY = 20               # stake per fighter to challenge for the title
CHAMPION_PURSE = 120             # flat purse for taking the champion team down
DEFENSE_PURSE = 90              # flat purse for turning a title challenger away

CHALLENGE_CYCLE = 15            # days between formal title challenges
CHALLENGE_GRACE = 7           # days the champion has to reach the arena and defend

ADELIO_CAMEO_CHANCE = 0.05    # chance an ordinary pit bout fields the dethroned Adelio

CHAMPION_MAP = "the-pit"          # the hand-laid arena the title bout is fought on

# The Games -- the arena's second stage, opened by dethroning the champion. A
# salon of violent sports: a 3v3 brawl and a capture-the-flag bout against
# opponents scaled level 1..6 (`encounters.ARENA_LEVEL_WEIGHTS`), and the boss
# bout -- the Ribbit brothers, 6-a-side on an authored map (`boss_bout`).
STAGE2_ENTRY = 30              # stake per fighter for a Games bout
STAGE2_PURSE = 130            # flat purse for winning one
STAGE2_ENEMIES = 3           # opponents fielded (a 3v3)

# The Games' boss: the three Ribbit brothers -- a hand-built Grippli team
# (`npcs/ribit|bufo|peep.json`, placed by the map's `deploy_npc`) backed by
# scaled goons, fought capture-the-flag on an authored map. The stage's capstone:
# a 6-a-side bout, so the player may bring six.
BOSS_ENTRY = 40
BOSS_PURSE = 450
BOSS_GOONS = 3                 # scaled bodies fighting alongside the brothers
BOSS_GOON_LEVEL = 3          # the goons' mean level -- the expected player level here
BOSS_SQUAD = 6               # brothers + goons; the player matches it
BOSS_MAP = "capture-the-flag-the-gamers"


def champion_bout():
    """The staked bout for challenging Adelio's team. No `rep`: it is not a rep
    tier and must not satisfy the Lone Wolf deed. `map_slug` points
    `app._start_battle` at the authored map (`maps/the-pit.json`) instead of the
    procedural `ArenaScenario`; the win condition is unchanged -- put the whole
    champion team down, the hole is only scenery."""
    return world.Bout("Challenge the Champion", entry=CHAMPION_ENTRY,
                       purse=CHAMPION_PURSE, enemies=1 + CHAMPION_GOONS,
                       champion=True, map_slug=CHAMPION_MAP)


def defense_bout():
    """A mandatory 1v1 title defense (no stake, a purse for a win)."""
    return world.Bout("Defend the Title", entry=0, purse=DEFENSE_PURSE,
                      enemies=1, defense=True)


def brawl_bout():
    """The Games' straight fight: a 3v3 with a bigger stake and purse than the
    rep ladder, against opponents scaled level 1..6 (`stage2_pack`). Offered once
    the champion has been dethroned."""
    return world.Bout("Games: Brawl", entry=STAGE2_ENTRY, purse=STAGE2_PURSE,
                      enemies=STAGE2_ENEMIES, stage2=True)


def ctf_bout():
    """The Games' capture-the-flag bout: same stake and field as the brawl, but
    fought on a `FlagScenario` -- it ends when a fighter carries the enemy flag
    back to their own, not when a side is wiped."""
    return world.Bout("Games: Capture the Flag", entry=STAGE2_ENTRY,
                      purse=STAGE2_PURSE, enemies=STAGE2_ENEMIES,
                      stage2=True, ctf=True)


def boss_bout():
    """The Games' capstone: the three Ribbit brothers (the authored NPC team the
    `BOSS_MAP` places) plus `BOSS_GOONS` goons at `BOSS_GOON_LEVEL`, fought
    capture-the-flag on that map. A 6-a-side bout -- `squad_max=BOSS_SQUAD`."""
    return world.Bout("Games: The Ribbit Brothers", entry=BOSS_ENTRY,
                      purse=BOSS_PURSE, enemies=BOSS_GOONS, level=BOSS_GOON_LEVEL,
                      stage2=True, ctf=True, boss=True, map_slug=BOSS_MAP,
                      squad_max=BOSS_SQUAD)


def stage2_pack(n=STAGE2_ENEMIES, rng=random):
    """`n` opponents for a Games bout, each rolled level 1..6 off
    `encounters.ARENA_LEVEL_WEIGHTS` (level 1 common, level 6 rare)."""
    return [encounters.build_enemy(
        encounters.weighted_choice(encounters.ARENA_LEVEL_WEIGHTS, rng), rng)
        for _ in range(n)]


def champion_of(guild):
    """The roster member holding the Champion of the Pit title, or None."""
    return next((u for u in guild.roster if u.arena_title), None)


def defense_due(guild):
    """A challenge has come due and its grace window is still open -- turning up
    at the arena now means a 1v1 for the title."""
    day = guild.arena_challenge_day
    return (day is not None and champion_of(guild) is not None
            and day <= guild.clock.day <= day + CHALLENGE_GRACE)


def defense_deadline(guild):
    """Last day the champion can defend before forfeiting, or None."""
    day = guild.arena_challenge_day
    return None if day is None else day + CHALLENGE_GRACE


def sync(guild):
    """Housekeeping to run whenever the guild lands back on the map. Strips a
    title whose defense window has lapsed and clears a stale challenge. Returns
    event lines for the caller to surface."""
    day = guild.arena_challenge_day
    champ = champion_of(guild)
    if champ is None:
        guild.arena_challenge_day = None
        return []
    if day is not None and guild.clock.day > day + CHALLENGE_GRACE:
        champ.arena_title = False
        guild.arena_challenge_day = None
        return [f"{champ.name} never answered the challenge -- "
                f"the Champion of the Pit title is forfeit."]
    return []


def build_challenger(mean_level):
    """A fresh title challenger pitched at `mean_level` -- a scaled `Unit("enemy")`
    with random valid talent picks (`encounters.build_enemy`)."""
    return encounters.build_enemy(mean_level)


def load_champion():
    """Adelio, from the NPC library, rigged as the pit champion for a bout."""
    adelio = npc_lib.load_npc(CHAMPION_SLUG)
    adelio.arena_role = "champion"
    adelio.arena_title = True                     # +1 MD in his own pit while he still holds it
    return adelio


def cameo_enemy():
    """The dethroned Adelio, `ADELIO_CAMEO_CHANCE` of the time, else None."""
    if random.random() >= ADELIO_CAMEO_CHANCE:
        return None
    try:
        return npc_lib.load_npc(CHAMPION_SLUG)
    except OSError:
        return None
