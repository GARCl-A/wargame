# Unified Item System & Rich ItemInstance Architecture

## Motivation
Historically, GARTOK items were fragmented across multiple flat tables in `data.py` (`WEAPONS`, `ARMOR`, `SHIELDS`, `ITEM_WEIGHTS`, `FOOD_ITEMS`, `FOOD_LIFESPAN`, `CRAFTING_RECIPES`) and `economy.py`. This caused duplicated lookup logic, lack of type safety, fragile string manipulation for rotting food (e.g. `"Meat (1d left)"`), and difficulty tracking item-level properties like remaining charges or lifespan.

## Architecture & Single Source of Truth
- **`gartok/items.py`**: The authoritative registry for all 96 items.
  - Typed Enums: `ItemType`, `ItemRarity`, `WeaponSize`, `CraftingStation`.
  - `ItemDef`: Frozen dataclass storing static definitions (rarity, weight, price, weapon/armor stats, food lifespan, spell/language affinities, max charges, light radius).
  - `ItemInstance`: Rich mutable item object representing an actual item stack or physical instance (`id`, `qty`, `charges`, `days_old`, `_name`).
    - Implements tuple emulation (`__iter__`, `__getitem__`, `__len__`, `__eq__`) so legacy unpackers (`for name, qty in pack:`) and string comparisons (`"Torch" in inventory`) work without breaking.
    - Implements `to_dict()` and `from_raw()` for JSON serialization.
  - Standard Item Constants: `TORCH_ITEM`, `LANTERN_ITEM`, `AMMO_ITEM`, `FIRST_AID_ITEM`, `CHEST_ITEM`, `GEM_ITEM`, `MISSION_CHEST_ITEM`, `LETTER_ITEM`, `CODEX_ITEM`.
  - Shared Helpers: `items.item_tag(item)`, `items.item_tooltip(name)`, `items.is_weapon(item)`, `items.is_armor(item)`, `items.is_shield(item)`, `items.is_food(item)`, `items.is_light_source(item)`.

## Consumer & Persistence Migration
- **Character Inventory (`Unit._base_inventory` & `Unit.inventory`)**:
  - Operates natively over `list[ItemInstance]`.
  - Pack helpers (`stack_add`, `stack_take`, `_pack_take`, `split_pack`, `_take_ration`, `distribute_load`) preserve charges, aging, and quantity on instances.
- **Upkeep & Food Aging (`guild._rot_food`)**:
  - Increments `days_old` directly on perishable food instances each daily tick.
  - When `it.is_rotten()` triggers, converts automatically into a `"Rotten Food"` `ItemInstance`.
- **Persistence (`persist.py`)**:
  - Incremented to `SAVE_VERSION = 17`.
  - `_serialize_pack()` serializes structured item dictionaries (`{"id": ..., "name": ..., "qty": ..., "charges": ..., "days_old": ...}`) for units, strongbox, and city property.
  - `pack_from_raw()` tolerates structured dicts, stacked tuples, and old flat string lists seamlessly.
