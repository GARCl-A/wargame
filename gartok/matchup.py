"""Assembling one battle: who the squad faces, and on what map.

`app` owns the campaign flow and the screens. The decision of *what a squad
drops into* -- which used to sprawl across `app._start_battle` as the arena grew
bout types -- lives here, behind one call:

    enemies, scenario = matchup.build(node, offer, squad_size=len(squad), guild=guild)

- **no offer** -- a plain node fight: `squad_size` generic level-0 enemies on the
  node's own procedural scenario. (The wilds ambush pack is built by
  `hunt`/`encounters` and handed straight to `Battle`, not through here.)
- **a staked tier** (`world.ARENA_TIERS`) -- `offer.enemies` opponents scaled to
  `offer.level` (`encounters.build_enemy`), on the arena's `ArenaScenario`.
- **the champion bout** (`offer.champion`) -- Adelio (`arena.load_champion`)
  leading generic goons, on the authored `offer.map_slug` map.
- **a title defense** (`offer.defense`) -- one challenger built to the reigning
  champion's mean level + 1.
- **the Games** (`offer.stage2`) -- `arena.stage2_pack`; a `FlagScenario` when
  `offer.ctf`, else the `ArenaScenario`.
- **the Games' boss** (`offer.boss`) -- the authored NPC team the `offer.map_slug`
  map places (`map_lib.npc_units`) plus `offer.enemies` goons at `offer.level`,
  fought capture-the-flag on that map (`CustomFlagScenario`).
- once the champion is down, an ordinary pit bout has an
  `arena.ADELIO_CAMEO_CHANCE` of fielding the dethroned Adelio in one slot.
"""

from . import arena, encounters, map_lib
from .scenario import CustomFlagScenario, CustomScenario, FlagScenario
from .unit import Unit


def build(node, offer, *, squad_size, guild):
    """`(enemies, scenario)` for a battle at `node` under `offer` (a `world.Bout`,
    or None for a plain node fight). `squad_size` sizes a plain fight; `guild` is
    read for the champion cameo and the title-defense challenger."""
    return _enemies(offer, squad_size, guild), _scenario(node, offer)


def _enemies(offer, squad_size, guild):
    if offer is None:
        return [Unit("enemy") for _ in range(squad_size)]
    if offer.defense:
        champ = arena.champion_of(guild)
        mean = champ.mean_level + 1 if champ is not None else 1
        return [arena.build_challenger(mean)]
    if offer.boss:
        brothers = map_lib.npc_units(map_lib.load_map(offer.map_slug))
        goons = [encounters.build_enemy(offer.level) for _ in range(offer.enemies)]
        return brothers + goons
    if offer.stage2:
        return arena.stage2_pack(offer.enemies)

    pack = [encounters.build_enemy(offer.level) for _ in range(offer.enemies)]
    if offer.champion:
        pack[0] = arena.load_champion()
    elif "arena_dethrone" in guild.deeds_done:
        cameo = arena.cameo_enemy()
        if cameo is not None:
            pack[0] = cameo
    return pack


def _scenario(node, offer):
    if offer is not None and offer.ctf and offer.map_slug:
        return CustomFlagScenario(map_lib.load_map(offer.map_slug))
    if offer is not None and offer.ctf:
        return FlagScenario()
    if offer is not None and offer.map_slug:
        return CustomScenario(map_lib.load_map(offer.map_slug))
    return node.scenario()
