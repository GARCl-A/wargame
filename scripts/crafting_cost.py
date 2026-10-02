"""Calculates production time, food consumption, and base costs for crafting recipes,
evaluating the 'Best Possible Crafter' for each item in GARTOK.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import data, economy


def calc_hours_distribution(target_progress: int, roll_bonus: int):
    """Calculates the exact probability distribution of hours required to reach target_progress.
    Returns (expected_hours, min_hours, max_hours).
    """
    dp = {0: 1.0}
    dist = {}
    for h in range(1, 150):
        new_dp = {}
        for current_p, prob in dp.items():
            for d in range(1, 21):
                prog = max(1, d + roll_bonus)
                next_p = current_p + prog
                if next_p >= target_progress:
                    dist[h] = dist.get(h, 0.0) + prob / 20.0
                else:
                    new_dp[next_p] = new_dp.get(next_p, 0.0) + prob / 20.0
        dp = new_dp
        if not dp:
            break
    exp_h = sum(h * pr for h, pr in dist.items())
    min_h = min(dist.keys()) if dist else 0
    max_h = max(dist.keys()) if dist else 0
    return exp_h, min_h, max_h


def best_crafter_profile(recipe_name: str, station: str):
    """Returns the optimal crafter configuration for a given recipe.
    Returns a dict with crafter details.
    """
    # Dwarven ancestral forge items require Dwarf race
    if recipe_name in ("Dwarf Axe", "Dwarf Shield", "Dwarf Armor"):
        return {
            "race": "Dwarf",
            "int_score": 18,
            "int_mod": 4,
            "talents": ["crafter (+1)", "dwarf_crafting", "brisk_hands (-10% time)"],
            "roll_bonus": 5,  # +4 INT + 1 Crafter
            "speedup": 0.9,
            "food_rate": 3.0,  # 3 cp/day (Potato)
            "autotroph": False,
            "note": "Exclusivo Anão (Dwarven Forging)",
        }

    # Traps can be made by Kobolds (with +1 forge bonus) or Leshys (autotroph)
    if recipe_name in ("Bear Trap", "Alarm Trap"):
        return {
            "race": "Kobold",
            "int_score": 19,
            "int_mod": 4,
            "talents": ["crafter (+1)", "blacksmith (+1 forge)", "kobold_trapper", "brisk_hands (-10% time)"],
            "roll_bonus": 6,  # +4 INT + 1 Crafter + 1 Blacksmith
            "speedup": 0.9,
            "food_rate": 3.0,
            "autotroph": False,
            "note": "Especialista em Armadilhas (Kobold Trapper + Blacksmith)",
        }

    # Potion / general apothecary
    if station == "apothecary":
        return {
            "race": "Elf",
            "int_score": 19,
            "int_mod": 4,
            "talents": ["crafter (+1)", "apothecary (+1 brew)", "brisk_hands (-10% time)"],
            "roll_bonus": 6,
            "speedup": 0.9,
            "food_rate": 3.0,
            "autotroph": False,
            "note": "Boticário Elfo (INT 19 + Crafter + Apothecary)",
        }

    # Scriptorium (dictionaries)
    if station == "scriptorium":
        return {
            "race": "Elf",
            "int_score": 19,
            "int_mod": 4,
            "talents": ["crafter (+1)", "brisk_hands (-10% time)"],
            "roll_bonus": 5,
            "speedup": 0.9,
            "food_rate": 3.0,
            "autotroph": False,
            "note": "Escriba Elfo (INT 19 + Crafter)",
        }

    return {
        "race": "Human",
        "int_score": 18,
        "int_mod": 4,
        "talents": ["crafter (+1)", "brisk_hands (-10% time)"],
        "roll_bonus": 5,
        "speedup": 0.9,
        "food_rate": 3.0,
        "autotroph": False,
        "note": "Padrão Artesão",
    }


def analyze_recipe(recipe_name: str, labor_wage_hourly: float = 1.0, daily_food_cp: float = 3.0):
    recipe = data.CRAFTING_RECIPES[recipe_name]
    station = recipe.get("station", "forge")
    crafter = best_crafter_profile(recipe_name, station)

    mat_cost = sum(economy.PRICES.get(m, 10) for m in recipe["materials"])
    target_val = mat_cost + recipe["complexity"]

    exp_h, min_h, max_h = calc_hours_distribution(target_val, crafter["roll_bonus"])
    clock_hours = exp_h * crafter["speedup"]

    food_cost = 0.0 if crafter["autotroph"] else (clock_hours / 24.0) * daily_food_cp
    labor_cost = exp_h * labor_wage_hourly

    total_base_cost = mat_cost + food_cost + labor_cost

    return {
        "item": recipe_name,
        "station": station,
        "level": recipe.get("level", 1),
        "target": target_val,
        "crafter_race": crafter["race"],
        "roll_bonus": crafter["roll_bonus"],
        "note": crafter["note"],
        "mat_cost": mat_cost,
        "exp_hours": exp_h,
        "min_hours": min_h,
        "max_hours": max_h,
        "clock_hours": clock_hours,
        "food_cost": food_cost,
        "labor_cost": labor_cost,
        "total_base_cost": total_base_cost,
    }


def print_table(results, title="ANALISE DE CUSTO E TEMPO: BEST POSSIBLE CRAFTER"):
    print("\n" + "=" * 114)
    print(f" {title}")
    print("=" * 114)
    header = (
        f"{'Item':<14} | {'Crafter Ideal':<16} | {'Roll':<5} | {'Target':<6} | "
        f"{'Mats(cp)':<8} | {'Horas(Media)':<13} | {'Comida(cp)':<10} | {'Mao-de-Obra':<11} | {'Custo Base':<10}"
    )
    print(header)
    print("-" * 114)
    for r in results:
        print(
            f"{r['item']:<14} | "
            f"{r['crafter_race']:<16} | "
            f"+{r['roll_bonus']:<4} | "
            f"{r['target']:<6} | "
            f"{r['mat_cost']:>7.0f}c | "
            f"{r['exp_hours']:>5.2f}h ({r['min_hours']}-{r['max_hours']:>2}h) | "
            f"{r['food_cost']:>9.2f}c | "
            f"{r['labor_cost']:>10.2f}c | "
            f"{r['total_base_cost']:>9.2f}c"
        )
    print("=" * 114 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Best Possible Crafter Analyzer")
    parser.add_argument("--station", choices=["forge", "apothecary", "scriptorium", "all"], default="forge")
    parser.add_argument("--wage", type=float, default=1.0, help="Labor wage in cp per hour (default: 1.0 cp/h)")
    parser.add_argument("--food-price", type=float, default=3.0, help="Daily ration price in cp (default: 3.0 cp)")
    parser.add_argument("--compare-traps", action="store_true", help="Compare Kobold vs Leshy vs Dwarf for traps")
    parser.add_argument("--compare-novice", action="store_true", help="Compare Best Crafter vs Novice (0 INT, 0 talents)")
    args = parser.parse_args()

    if args.compare_novice:
        print("\n" + "=" * 114)
        print(" COMPARATIVO: BEST POSSIBLE CRAFTER vs NOVATO COMPLETO (0 INT, 0 TALENTOS)")
        print("=" * 114)
        header = (
            f"{'Item':<14} | {'Target':<6} | {'Best Crafter':<22} | {'Novato (0 INT/Tal)':<21} | "
            f"{'Diferenca Tempo':<18} | {'Delta Custo':<12}"
        )
        print(header)
        print("-" * 114)
        for item in ["Bear Trap", "Alarm Trap", "Dwarf Axe", "Dwarf Shield", "Dwarf Armor"]:
            best = analyze_recipe(item, labor_wage_hourly=args.wage, daily_food_cp=args.food_price)
            target = best["target"]
            mats = best["mat_cost"]
            b_h = best["exp_hours"]
            b_min, b_max = best["min_hours"], best["max_hours"]
            b_cost = best["total_base_cost"]

            nov_h, nov_min, nov_max = calc_hours_distribution(target, 0)
            nov_food = (nov_h / 24.0) * args.food_price
            nov_labor = nov_h * args.wage
            nov_cost = mats + nov_food + nov_labor

            diff_pct = ((nov_h - b_h) / b_h) * 100
            diff_hours = nov_h - b_h
            diff_cost = nov_cost - b_cost

            b_str = f"{b_h:.2f}h ({b_min}-{b_max:>2}h) [+{best['roll_bonus']}]"
            n_str = f"{nov_h:.2f}h ({nov_min}-{nov_max:>2}h) [+0]"
            d_time_str = f"+{diff_hours:.2f}h (+{diff_pct:.1f}%)"
            d_cost_str = f"+{diff_cost:.2f}c"

            print(f"{item:<14} | {target:<6} | {b_str:<22} | {n_str:<21} | {d_time_str:<18} | {d_cost_str:<12}")
        print("=" * 114)
        print(" * Novato nao possui Brisk Hands (-10% no relogio). O melhor crafter rola entre +5 e +6.")
        print(" * O piso de progresso por hora do melhor crafter e 6-7, enquanto o novato pode tirar 1 de progresso.\n")
        return

    if args.compare_traps:
        print("\n--- COMPARACAO DE ARTESAOS PARA ARMADILHAS ---")
        items = ["Bear Trap", "Alarm Trap"]
        profiles = [
            ("Kobold (INT 19, Trapper, Crafter, Blacksmith +1)", 6, 0.9, False),
            ("Leshy (INT 17, Autotroph 0 comida, Crafter)", 4, 0.9, True),
            ("Dwarf (INT 18, Crafter, Blacksmith sem bonus)", 5, 0.9, False),
        ]
        for item in items:
            recipe = data.CRAFTING_RECIPES[item]
            mats = sum(economy.PRICES.get(m, 10) for m in recipe["materials"])
            target = mats + recipe["complexity"]
            print(f"\nItem: {item} (Target: {target}, Mats: {mats}c)")
            for name, bonus, speedup, autotroph in profiles:
                eh, minh, maxh = calc_hours_distribution(target, bonus)
                clock_h = eh * speedup
                food = 0.0 if autotroph else (clock_h / 24.0) * args.food_price
                labor = eh * args.wage
                total = mats + food + labor
                print(f"  * {name:<48}: {eh:.2f}h ({minh}-{maxh}h) | Comida: {food:.2f}c | Mao-de-obra: {labor:.2f}c | Custo Total: {total:.2f}c")
        print()
        return

    items = []
    for name, r in data.CRAFTING_RECIPES.items():
        if args.station == "all" or r.get("station") == args.station:
            items.append(name)

    results = [analyze_recipe(item, labor_wage_hourly=args.wage, daily_food_cp=args.food_price) for item in items]
    print_table(results, f"ESTIMATIVA DE CUSTO E MAO DE OBRA ({args.station.upper()})")


if __name__ == "__main__":
    main()
