# Crafting & Traps

## Crafting System
- `data.CRAFTING_RECIPES` defines `materials` and `complexity` per item.
- `unit.Unit` has `recipes` (learned items), `crafting_target`, and `crafting_progress`. Crafting is advanced with `1d20 + INT mod` rolls against `(material_value + complexity)`.
- `guild.crafting_shift` manages the crafting interaction: consuming materials from the crafter's pack, advancing time, and resolving completion.
- `crafting_screen.py` offers the forge UI in Ankareth. 
- *Rule:* The guild has no shared treasury or stash; crafters must hold the required materials in their personal packs (`_base_inventory`).

## Traps
- `GroundObject.TRAP` introduced with `trap_type` and `trap_owner_team`.
- **Pre-battle Deployment**: The AI deploys traps near its spawn point (`scenario.py`), while players position theirs in an interactive phase before round 1 (`battle_screen.py`).
- **Combat Integration**: Traps trigger on normal movement (`battle.move_unit`) and forced movement (`Push`). Bear traps apply 1d8 damage and halt movement; Alarm traps only penalize movement and log noise.
- Traps are consumed on use. Un-triggered traps on the field are returned to the `loot_pool` in `loot.field_loot`.

## State Holes Fixed
During implementation, a state hole in `campaign._carry_forward` was identified: consumable items used dynamically during combat were not being synced back to the persistent `char` roster after the `Battle` was absorbed. This allowed for infinite traps and duplicated thrown weapons. `_carry_forward` was updated to explicitly purge missing traps and un-sync `equipped_weapon` if it was dropped/thrown in combat.
