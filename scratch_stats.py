import sys
import os
import statistics

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from gartok.unit import Unit
from gartok import data

def avg_damage(unit):
    wep_name = unit.equipped_weapon
    if not wep_name:
        count, sides = unit.unarmed_damage
        return count * ((sides + 1) / 2) + unit.mod_strength
    
    wep = data.WEAPONS.get(wep_name)
    if not wep:
        count, sides = unit.unarmed_damage
        return count * ((sides + 1) / 2) + unit.mod_strength
        
    count, sides = wep.get("damage", (1, 2))
    stat_mod = unit.mod_dexterity if wep.get("finesse") else unit.mod_strength
    return count * ((sides + 1) / 2) + stat_mod

def main():
    n = 10000
    
    hps = []
    speeds = []
    dmgs = []
    carries = []
    chas = []
    
    for _ in range(n):
        u = Unit("player")
        hps.append(u.hp_max)
        speeds.append(u.speed)
        dmgs.append(avg_damage(u))
        carries.append(u.carry_normal)
        chas.append(u.mod_charisma)

    print(f"Total units: {n}")
    
    metrics = {
        "HP": hps,
        "Speed": speeds,
        "Damage": dmgs,
        "Carry Normal": carries,
        "Charisma Mod": chas
    }
    
    for name, vals in metrics.items():
        _min = min(vals)
        _max = max(vals)
        _mean = statistics.mean(vals)
        _std = statistics.stdev(vals)
        print(f"{name:15}: Min: {_min:>5.2f} | Max: {_max:>5.2f} | Mean: {_mean:>5.2f} | StDev: {_std:>5.2f}")

if __name__ == '__main__':
    main()
