"""Batch stat calculator: roll many characters at a given level and print the spread.

Draft bodies (`Unit("player")`, level 0) lifted to a combat/work level with random
valid talent picks -- the way a player's squad ends up -- beside authored NPCs
(Adelio) and the champion's goons (`Unit("enemy")`, level 0).

    python scripts/unit_compare.py                    # combat 2 vs Adelio and his goons
    python scripts/unit_compare.py --combat 4 --work 1 --npc the-ancient-archivist -n 5000
"""

import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import arena, npc_lib, talents
from gartok.unit import Unit

METRICS = ("HP", "AC", "MD", "Speed", "To-hit", "Avg dmg", "Dmg/turn vs AC10")


def avg_damage(u):
    w = u.weapon
    if w is None:
        n, sides = u.unarmed_damage
        mod = u.mod_strength
    else:
        n, sides = w.damage
        mod = u.mod_dexterity if (w.finesse or w.range > 0) else u.mod_strength
    return n * (sides + 1) / 2 + mod + u.talent_bonus("damage")


def hit_chance(to_hit, ac):
    return min(0.95, max(0.05, (21 - (ac - to_hit)) / 20))


def stats(u):
    to_hit = u.attack_bonus[0]
    dmg = avg_damage(u)
    return {"HP": u.hp_max, "AC": u.ac, "MD": u.mental_defense, "Speed": u.speed,
            "To-hit": to_hit, "Avg dmg": dmg,
            "Dmg/turn vs AC10": hit_chance(to_hit, 10) * dmg}


def pick_talents(u, rng):
    for track in talents.TRACKS:
        tree = (talents.TREE[track] if track in talents.XP_TRACKS
                else talents.racial_tree(u.race["name"]))
        guard = 0
        while u.picks_available(track) > 0 and guard < 20:
            guard += 1
            taken = u.talents[track]
            options = [t.id for t in tree if t.id not in taken
                       and (t.requires is None or t.requires in taken)]
            if not options:
                break
            u.choose_talent(track, rng.choice(options))


def drafted(combat, work, rng):
    u = Unit("player")
    u.set_track_level("combat", combat)
    u.set_track_level("work", work)
    pick_talents(u, rng)
    return u


def summarize(label, rows):
    print(f"\n{label}  (n={len(rows)})")
    print(f"  {'':<18}{'mean':>8}{'p10':>8}{'median':>8}{'p90':>8}")
    for m in METRICS:
        vals = sorted(r[m] for r in rows)
        p10, p50, p90 = (vals[min(len(vals) - 1, int(p * len(vals)))] for p in (.1, .5, .9))
        print(f"  {m:<18}{statistics.mean(vals):>8.2f}{p10:>8.1f}{p50:>8.1f}{p90:>8.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=2000)
    ap.add_argument("--combat", type=int, default=2)
    ap.add_argument("--work", type=int, default=0)
    ap.add_argument("--npc", action="append", default=None, help="NPC slug(s); default: the champion")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    random.seed(args.seed)

    squad = [drafted(args.combat, args.work, rng) for _ in range(args.n)]
    summarize(f"Draft body lifted to combat {args.combat} / work {args.work} "
              f"(racial {squad[0].racial_level})", [stats(u) for u in squad])
    summarize("Draft body, level 0", [stats(Unit("player")) for _ in range(args.n)])
    summarize(f"Champion goon (enemy, level 0) x{arena.CHAMPION_GOONS} per bout",
              [stats(Unit("enemy")) for _ in range(args.n)])

    for slug in args.npc or [arena.CHAMPION_SLUG]:
        u = npc_lib.load_npc(slug)
        s = stats(u)
        print(f"\n{u.name} ({u.race['name']} {u.occupation}): combat {u.combat_level} / "
              f"work {u.work_level} / racial {u.racial_level}, weapon {u.equipped_weapon}, "
              f"armor {u.armor_name}")
        print("  " + "  ".join(f"{m} {s[m]:.1f}" for m in METRICS))

        better = {m: sum(r[m] >= s[m] for r in (stats(x) for x in squad)) / len(squad) for m in METRICS}
        print("  share of the lifted squad at or above him: "
              + "  ".join(f"{m} {better[m]:.0%}" for m in METRICS))


if __name__ == "__main__":
    main()
