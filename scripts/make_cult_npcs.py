"""Writes the Demon Cult's eight authored NPCs to `npcs/` (`cult_site.py` fields them).

    python scripts/make_cult_npcs.py

Racial levels are fixed by the design (`docs/plans/holy_symbol_quest.md`): the leader 10, the
fighters and the channelers 7, the Demon 22. Re-run it and the files are rewritten the same
(bodies are set, not rolled; the hit dice rolls are seeded per NPC).
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gartok import npc_lib, talents
from gartok.unit import Unit

ATTRS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def body(name, race, attrs, weapon, armor, bio, *, levels, sources=(), spells=(), combat=(), work=(),
         magic_t=(), racial=(), team="enemy", shield=None, hp=None, align="Neutral and Evil", slug=None):
    random.seed(slug or name)
    u = Unit(team, name=name)
    u.set_race(race)
    u.set_kit(weapon, None)
    for a, v in zip(ATTRS, attrs):
        u.base_attributes[a] = v
    u.alignment = align
    u.bio = bio
    for s in sources:
        u.add_magic_source(s)
    for track, lv in zip(("combat", "work", "magic"), levels[:3]):
        u.set_track_level(track, lv)
    if len(levels) > 3:
        u.set_track_level("racial", levels[3])
    for sid in spells:
        u.set_spell_known(sid, True)
    for tid in racial:
        u.choose_talent("racial", tid)
    for track, wanted in (("combat", combat), ("work", work), ("magic", magic_t)):
        rng = random.Random(slug or name)
        for tid in wanted:
            if u.picks_available(track) > 0 and u.offerable(track, talents.get(tid)):
                u.choose_talent(track, tid)
        tree = talents.TREE[track]
        while u.picks_available(track) > 0:
            opts = [t.id for t in tree if u.offerable(track, t)]
            if not opts:
                break
            u.choose_talent(track, rng.choice(opts))
    if armor:
        u.give_to_armor(armor)
    if shield:
        u.give_to_offhand(shield)
    if hp:
        u.set_hp(hp)
    u.hp = u.hp_max
    return u


def build():
    return {
        "cult-leader": body(
            "Maren Voss, the Red Hierophant", "Human", (9, 12, 13, 16, 15, 14), "Quarterstaff", "Leather Jerkin",
            "Keeps the rite and the book it is read from. He means to open the door and thinks the price fair.",
            levels=(4, 6, 10), sources=("blood", "faith"), spells=("magic_missile", "hex", "sleep", "dragonfire", "healing_touch"),
            combat=("tough", "alert"), work=("charismatic", "clever"),
            magic_t=("arcane_mind", "spell_focus", "destructive_casting"), slug="cult-leader"),
        "cult-fighter-1": body(
            "Brann, Sworn Blade", "Human", (15, 12, 14, 9, 10, 8), "Sword", "Studded Leather",
            "A hired sword who stopped asking what he was hired for.", levels=(7, 7, 0), shield="Dwarf Shield",
            combat=("strong", "sure_strike", "heavy_hand", "tough"), work=("brawny", "sturdy"), slug="cult-fighter-1"),
        "cult-fighter-2": body(
            "Kessa Thorn, Knife of the Rite", "Human", (11, 16, 12, 10, 11, 9), "Rapier", "Leather Jerkin",
            "Fast and quiet. She is there to keep the channelers alive, and to end whoever reaches them.",
            levels=(7, 7, 0), combat=("agile", "duelist", "deadeye", "nimble_skirmisher"),
            work=("nimble_fingers", "sturdy"), slug="cult-fighter-2"),
        "cult-channeler-blood": body(
            "Ilsa of the Blood", "Human", (8, 13, 12, 14, 12, 13), "Dagger", "Studded Leather",
            "Reads the rite from the east point, in a voice that is not quite hers.",
            levels=(3, 5, 6), sources=("blood",), spells=("magic_missile", "hex", "sleep", "dragonfire"),
            magic_t=("arcane_mind", "spell_focus", "destructive_casting"), slug="cult-channeler-blood"),
        "cult-channeler-nature": body(
            "Orrin Greywood", "Human", (9, 11, 13, 13, 16, 10), "Quarterstaff", "Leather Jerkin",
            "A hedge-druid turned. The roots he calls hold the ground under the rite.",
            levels=(3, 5, 6), sources=("nature",), spells=("magic_missile", "grasping_roots", "water_jet", "sleep"),
            magic_t=("arcane_mind", "spell_focus"), slug="cult-channeler-nature"),
        "cult-channeler-faith": body(
            "Brother Tavish", "Human", (10, 10, 12, 12, 16, 12), "Quarterstaff", "Studded Leather",
            "A priest of the Cathedral who prayed to the wrong thing and was answered.",
            levels=(3, 5, 6), sources=("faith",), spells=("magic_missile", "sleep", "healing_touch"),
            magic_t=("arcane_mind", "spell_focus", "blessed_hands"), slug="cult-channeler-faith"),
        "farmers-daughter": body(
            "Wynn Ashvale", "Human", (9, 11, 11, 11, 12, 13), "Dagger", None,
            "Edric Ashvale's daughter. She went to the Cathedral to light a candle for her mother.",
            levels=(0, 1, 0), team="player", align="Neutral and Good", slug="farmers-daughter"),
        "the-demon": body(
            "The Pale Tenant", "Demon", (24, 14, 12, 14, 14, 18), None, None,
            "What the Cult was calling. It has no name it will answer to.",
            levels=(16, 14, 14), combat=("imposing", "menacing", "gruesome_takedown", "cull_the_broken", "merciless", "dread_voice",
                    "strong", "heavy_hand", "sure_strike", "wrestler",
                    "wordless_menace", "tough", "hardy", "bulwark", "recovery", "armor_bearer"),
            racial=("demon_claws", "cleaving_claws", "infernal_wings", "infernal_presence"),
            sources=("blood",), spells=("hex", "dragonfire"), slug="the-demon"),
    }


def main():
    for slug, u in build().items():
        npc_lib.save_npc(u, slug)
        print(f"{slug:24} racial {u.racial_level:>2}  hp {u.hp_max:>3}  ac {u.ac}")


if __name__ == "__main__":
    main()
