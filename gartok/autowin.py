"""Auto-Win simulation and estimation via background Monte Carlo.

Evaluates whether a battle is an overwhelming stomp that can be resolved
immediately without combat grind.

Criteria for Auto-Win eligibility:
1. 100% win rate across all simulated iterations.
2. Zero player casualties (all player combatants survive standing).
3. Zero consumables used (no ammo spent, no potions drunk, no first aid charges used).

Trade-off when accepted:
- 0 combat XP awarded from kills.
- Party members take average simulated damage (rounded).
- Field loot, clock advancement, and guild victory count are preserved.
"""

import threading
import time
from dataclasses import dataclass, field

from . import ai, data
from .battle import Battle
from .scenario import Scenario
from .unit import flatten_pack


@dataclass
class AutoWinResult:
    eligible: bool = False
    iterations: int = 0
    win_rate: float = 0.0
    avg_damage: dict[str, float] = field(default_factory=dict)
    avg_rounds: float = 0.0


def simulate_matchup(squad, enemies, scenario=None, daylight=True, lethal=True,
                     max_time=1.0, max_iterations=25) -> AutoWinResult:
    """Run headless battle simulations to verify if the squad overwhelmingly stomps enemies."""
    if not squad or not enemies:
        return AutoWinResult(eligible=False)

    t0 = time.monotonic()
    total_damage: dict[str, float] = {u.uid: 0.0 for u in squad}
    total_rounds = 0
    successful_runs = 0

    for run_idx in range(max_iterations):
        if run_idx > 0 and (time.monotonic() - t0) >= max_time:
            break

        scen = scenario() if callable(scenario) else (scenario or Scenario())
        battle = Battle(list(squad), list(enemies), scenario=scen,
                        daylight=daylight, lethal=lethal)

        turn_cap = 60
        turns = 0
        while battle.winner is None and turns < turn_cap:
            act = battle.active
            if not act or not act.alive:
                battle.end_turn()
            else:
                ai.take_turn(battle, act)
            turns += 1

        # 1. 100% win requirement
        if battle.winner != "player":
            return AutoWinResult(eligible=False, iterations=run_idx + 1)

        # 2. Zero player casualties (everyone must be standing)
        for c in battle.player_units:
            if not c.alive or c.status != "up" or c.hp <= 0:
                return AutoWinResult(eligible=False, iterations=run_idx + 1)

        # 3. Zero consumables used across all runs
        for c, u in zip(battle.player_units, squad):
            pack = flatten_pack(u)
            init_ammo = getattr(u, "quiver_charges", data.QUIVER_AMMO) if data.AMMO_ITEM in pack else 0
            if c.ammo < init_ammo:
                return AutoWinResult(eligible=False, iterations=run_idx + 1)

            init_fa = u.first_aid_charges if data.FIRST_AID_ITEM in pack else 0
            if c.first_aid_charges < init_fa:
                return AutoWinResult(eligible=False, iterations=run_idx + 1)

            for item_name in ("Minor Healing Potion", "Healing Potion", "Bandage"):
                if c.inventory.count(item_name) < pack.count(item_name):
                    return AutoWinResult(eligible=False, iterations=run_idx + 1)

        # Accumulate damage and rounds for successful run
        for c, u in zip(battle.player_units, squad):
            base_hp = getattr(u, "hp", u.hp_max)
            dmg = max(0, base_hp - c.hp)
            total_damage[u.uid] += dmg

        total_rounds += battle.round_no
        successful_runs += 1

    if successful_runs > 0:
        avg_dmg = {uid: total_damage[uid] / successful_runs for uid in total_damage}
        avg_rnd = total_rounds / successful_runs
        return AutoWinResult(eligible=True, iterations=successful_runs,
                             win_rate=1.0, avg_damage=avg_dmg, avg_rounds=avg_rnd)

    return AutoWinResult(eligible=False)


class AutoWinEstimator:
    """Threaded background runner for pre-battle screens."""

    def __init__(self):
        self.result: AutoWinResult | None = None
        self.computing: bool = False
        self._token: int = 0
        self._lock = threading.Lock()

    def request(self, squad, enemies, scenario=None, daylight=True, lethal=True,
                max_time=1.0, max_iterations=25):
        with self._lock:
            self._token += 1
            token = self._token
            self.result = None
            self.computing = True

        def _worker():
            res = simulate_matchup(squad, enemies, scenario=scenario,
                                   daylight=daylight, lethal=lethal,
                                   max_time=max_time, max_iterations=max_iterations)
            with self._lock:
                if self._token == token:
                    self.result = res
                    self.computing = False

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def reset(self):
        with self._lock:
            self._token += 1
            self.result = None
            self.computing = False
