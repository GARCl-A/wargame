"""Auto-Win simulation and estimation via background Monte Carlo.

Evaluates whether a battle is an overwhelming stomp that can be resolved
immediately without combat grind.

Every run counts toward `stomp_rate`, the share of clean stomps the pre-battle screens show, and
`win_rate`, the plain share of wins.

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
    stomp_rate: float = 0.0
    avg_damage: dict[str, float] = field(default_factory=dict)
    avg_rounds: float = 0.0


def simulate_matchup(squad, enemies, scenario=None, daylight=True, lethal=True,
                     max_time=1.0, max_iterations=25) -> AutoWinResult:
    """Fight the matchup headless until the time or the iterations run out. `stomp_rate` is the
    share of those fights that were a clean stomp, `win_rate` the share won; `eligible` (the
    auto-win) only when every one of them was a clean stomp."""
    if not squad or not enemies:
        return AutoWinResult(eligible=False)

    t0 = time.monotonic()
    total_damage: dict[str, float] = {u.uid: 0.0 for u in squad}
    total_rounds = 0
    runs = wins = clean = 0

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

        runs += 1
        if battle.winner != "player":
            continue
        wins += 1
        if not _stomp(battle, squad):
            continue
        clean += 1
        for c, u in zip(battle.player_units, squad):
            base_hp = getattr(u, "hp", u.hp_max)
            total_damage[u.uid] += max(0, base_hp - c.hp)
        total_rounds += battle.round_no

    if not runs:
        return AutoWinResult(eligible=False)
    eligible = clean == runs
    return AutoWinResult(eligible=eligible, iterations=runs, win_rate=wins / runs, stomp_rate=clean / runs,
                         avg_damage={uid: d / clean for uid, d in total_damage.items()} if eligible else {},
                         avg_rounds=total_rounds / clean if eligible else 0.0)


def _stomp(battle, squad):
    """A won fight with everyone standing and nothing spent: no ammo, first aid or potion."""
    for c in battle.player_units:
        if not c.alive or c.status != "up" or c.hp <= 0:
            return False
    for c, u in zip(battle.player_units, squad):
        pack = flatten_pack(u)
        init_ammo = getattr(u, "quiver_charges", data.QUIVER_AMMO) if data.AMMO_ITEM in pack else 0
        if c.ammo < init_ammo:
            return False
        init_fa = u.first_aid_charges if data.FIRST_AID_ITEM in pack else 0
        if c.first_aid_charges < init_fa:
            return False
        for item_name in ("Minor Healing Potion", "Healing Potion", "Bandage"):
            if c.inventory.count(item_name) < pack.count(item_name):
                return False
    return True


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
