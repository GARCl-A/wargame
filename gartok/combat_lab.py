"""The combat lab: the benchmark fights, set up outside a campaign so a person can play them.

`FIGHTS` are the fights the economy leans on (`scripts/economy_activities.py` measures the AI
against them); `build` makes one on demand at a chosen level and squad size, from a seed, and
`log_path` says where its `combat_log` goes: `combat_lab/<date>/<name>.jsonl` beside the repo.
The campaign's own fights log into the world folder instead (`recorder.combat_log_path`).

Either side can be a person or `ai.py` (`controllers`), so the same fight yields a person's
decisions against the AI, or two people's against each other.
"""

import os
import random
import re
import time
from dataclasses import dataclass

from . import arena, encounters, hunt, matchup, world
from .battle import Battle
from .guild import Guild
from .scenario import AncientRuinsScenario, ErmosScenario

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "combat_lab")
MAX_LEVEL = 15
MAX_SQUAD = 6


@dataclass(frozen=True)
class LabFight:
    id: str
    name: str
    note: str
    squad: int = 3          # a fresh setup's size; the fixed-size ones set it


FIGHTS = {f.id: f for f in (
    LabFight("scrapper", "The Pit: Scrapper", "the arena's first bout, three level-0 scrappers; non-lethal"),
    LabFight("champion", "Challenge the Champion", "Adelio's team on the authored Pit map; non-lethal"),
    LabFight("brawl", "Games: Brawl", "the Games' straight fight against opponents of level 1 to 6; non-lethal"),
    LabFight("ctf", "Games: Capture the Flag", "the Brawl's field, won by carrying their flag home; non-lethal"),
    LabFight("boss", "Games: The Ribbit Brothers", "six a side, capture the flag on the authored map; non-lethal",
             squad=arena.BOSS_SQUAD),
    LabFight("wilds", "Wilds ambush", "a hunt's ambush on open ground, mostly wolves; lethal"),
    LabFight("road", "Old Road ambush", "bandits on the Old Road; lethal"),
    LabFight("dungeon", "Ancient Ruins", "the delve, in the dark with torches; lethal"),
)}

BOUTS = {"scrapper": arena.scrapper_bout, "champion": arena.champion_bout, "brawl": arena.brawl_bout,
         "ctf": arena.ctf_bout, "boss": arena.boss_bout}


def build(fight_id, level, squad_size, seed=None):
    """`(battle, meta)` for `fight_id`: a squad of `squad_size` built to mean `level` against the
    fight's own foes. `seed` pins the squads and the foes (the dice go on from there)."""
    seed = random.randrange(1 << 30) if seed is None else seed
    random.seed(seed)
    squad = [encounters.build_enemy(level) for _ in range(squad_size)]
    if fight_id in BOUTS:
        node = world.node("arena")
        enemies, scenario = matchup.build(node, BOUTS[fight_id](), squad_size=squad_size,
                                          guild=Guild(squad, node="arena"))
        battle = Battle(squad, enemies, scenario=scenario, daylight=True,
                        lethal=node.lethal, arena=node.arena)
    elif fight_id == "dungeon":
        scenario = AncientRuinsScenario()
        battle = Battle(squad, scenario.enemies, scenario=scenario, daylight=False, lethal=True)
    else:
        pack = (hunt.wilds_pack() if fight_id == "wilds"
                else encounters.roll_encounter(world.node("road").encounter_table))
        battle = Battle(squad, pack, scenario=ErmosScenario(), daylight=True, lethal=True)
    return battle, {"fight": fight_id, "level": level, "squad": squad_size, "seed": seed}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "fight"


def log_path(name, today=None, root=None):
    """A free `<root>/<date>/<name>.jsonl`; a taken name gets `-2`, `-3`, ..."""
    folder = os.path.join(root or ROOT, today or time.strftime("%Y-%m-%d"))
    base, n = slug(name), 1
    path = os.path.join(folder, f"{base}.jsonl")
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"{base}-{n}.jsonl")
    return path


def default_name(fight_id, controllers):
    sides = "-vs-".join("human" if controllers[t] == "human" else "ai" for t in ("player", "enemy"))
    return f"{fight_id}-{sides}"
