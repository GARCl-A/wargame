"""GARTOK item system -- single source of truth for all items in the world.

Replaces fragmented item tables across data.py and economy.py.
All items are defined with strong types, Enums, and typed ItemDef instances.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class ItemType(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    FOOD = "food"
    TOOL = "tool"
    MATERIAL = "material"
    GEM = "gem"
    POTION = "potion"
    SCROLL = "scroll"
    DICTIONARY = "dictionary"
    CONTAINER = "container"
    TRAP = "trap"
    LIGHT = "light"
    QUEST = "quest"
    TACK = "tack"
    ARTIFACT = "artifact"
    MISC = "misc"


class ItemRarity(StrEnum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    UNIQUE = "unique"


class WeaponSize(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


class CraftingStation(StrEnum):
    FORGE = "forge"
    APOTHECARY = "apothecary"
    SCRIPTORIUM = "scriptorium"
    COOKING = "cooking"


@dataclass(frozen=True)
class ItemDef:
    id: str
    name: str
    type: ItemType
    rarity: ItemRarity = ItemRarity.COMMON
    weight: float = 0.5
    price: int = 0
    size: WeaponSize | None = None
    damage: tuple[int, int] | None = None
    range: int = 0
    finesse: bool = False
    thrown: int = 0
    hands: int = 1
    reload: bool = False
    ac: int = 0
    max_dex: int | None = None
    speed_penalty: int = 0
    guard_bonus: int = 0
    food: bool = False
    material: bool = False
    lifespan: int | None = None
    spell_id: str | None = None
    language: str | None = None
    max_charges: int | None = None
    light_radius: int = 0

    @property
    def speed(self) -> int:
        return self.speed_penalty

    def __getitem__(self, key: str) -> Any:
        if key == "speed":
            return self.speed_penalty
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "speed":
            return self.speed_penalty
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        if key == "speed":
            return True
        return hasattr(self, key)



@dataclass
class ItemInstance:
    id: str
    charges: int | None = None
    days_old: int = 0
    qty: int = 1
    _name: str | None = None

    @property
    def defn(self) -> ItemDef:
        item = get(self.id)
        if item is None:
            name = self._name or self.id.title()
            return ItemDef(id=self.id, name=name, type=ItemType.MISC, weight=0.5)
        return item

    @property
    def name(self) -> str:
        if self._name:
            return self._name
        return self.defn.name

    @property
    def weight(self) -> float:
        return round(self.defn.weight * self.qty, 2)

    @property
    def food(self) -> bool:
        return self.defn.food

    @property
    def material(self) -> bool:
        return self.defn.material or is_material(self.name)

    def is_rotten(self) -> bool:
        if self.defn.lifespan is None:
            return False
        return self.days_old > self.defn.lifespan

    def copy(self) -> "ItemInstance":
        return ItemInstance(
            id=self.id,
            charges=self.charges,
            days_old=self.days_old,
            qty=self.qty,
            _name=self._name,
        )

    def to_dict(self) -> dict:
        d = {"id": self.id, "name": self.name, "qty": self.qty}
        if self.charges is not None:
            d["charges"] = self.charges
        if self.days_old:
            d["days_old"] = self.days_old
        return d

    @classmethod
    def from_raw(cls, raw: Any) -> "ItemInstance":
        if isinstance(raw, ItemInstance):
            return raw.copy()
        if isinstance(raw, dict):
            key = raw.get("id") or raw.get("name")
            qty = raw.get("qty", 1)
            charges = raw.get("charges")
            days_old = raw.get("days_old", 0)
            name_override = raw.get("name") if raw.get("id") else None
            inst = create_instance(key, qty=qty, days_old=days_old, charges=charges)
            if name_override and inst.name != name_override:
                inst._name = name_override
            return inst
        raise ValueError(f"Cannot create ItemInstance from {raw!r}")

    def __getitem__(self, idx: int) -> Any:
        if idx == 0:
            return self.name
        elif idx == 1:
            return self.qty
        raise IndexError(idx)

    def __len__(self) -> int:
        return 2

    def __iter__(self):
        yield self.name
        yield self.qty

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.name == other or self.id == other
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return (self.name, self.qty) == (other[0], other[1])
        if isinstance(other, ItemInstance):
            return (self.id, self.qty, self.charges, self.days_old) == (other.id, other.qty, other.charges, other.days_old)
        if isinstance(other, dict):
            return self.to_dict() == other
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, ItemInstance):
            return self.name < other.name
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return (self.name, self.qty) < tuple(other)
        if isinstance(other, str):
            return self.name < other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.id, self.charges, self.days_old, self.qty, self._name))

    def __repr__(self) -> str:
        extra = []
        if self.charges is not None:
            extra.append(f"charges={self.charges}")
        if self.days_old:
            extra.append(f"days_old={self.days_old}")
        ext_str = f", {', '.join(extra)}" if extra else ""
        return f"ItemInstance({self.name!r}, qty={self.qty}{ext_str})"



DAMAGE_STEPS = {
    (1, 2): (1, 3),
    (1, 3): (1, 4),
    (1, 4): (1, 6),
    (1, 6): (1, 8),
    (1, 8): (1, 10),
    (1, 10): (1, 12),
    (1, 12): (2, 8),
    (2, 6): (2, 8),
    (2, 8): (3, 8),
}


def step_damage_die(dice: tuple[int, int]) -> tuple[int, int]:
    return DAMAGE_STEPS.get(tuple(dice), (dice[0], dice[1] + 2))


# --------------------------------------------------------------------------- #
# Static Item Registry                                                         #
# --------------------------------------------------------------------------- #

_REGISTRY: dict[str, ItemDef] = {}
_LOOKUP: dict[str, ItemDef] = {}


def _register(item: ItemDef, *aliases: str) -> ItemDef:
    if (item.type == ItemType.MATERIAL or item.id == "rope") and not item.material:
        item = replace(item, material=True)
    _REGISTRY[item.id] = item
    _LOOKUP[item.id] = item
    _LOOKUP[item.name.lower()] = item
    _LOOKUP[item.name] = item
    for alias in aliases:
        _LOOKUP[alias.lower()] = item
        _LOOKUP[alias] = item
    return item


# 15 Base Weapons
_BASE_WEAPONS_DATA = [
    ("dagger", "Dagger", ItemRarity.COMMON, 0.5, 8, (1, 4), 0, True, 6, 1, False),
    ("hatchet", "Hatchet", ItemRarity.COMMON, 1.0, 10, (1, 6), 0, False, 0, 1, False),
    ("axe", "Axe", ItemRarity.COMMON, 3.0, 35, (1, 8), 0, False, 0, 1, False),
    ("light_hammer", "Light Hammer", ItemRarity.COMMON, 1.0, 10, (1, 4), 0, True, 0, 1, False),
    ("hammer", "Hammer", ItemRarity.COMMON, 4.0, 35, (1, 8), 0, False, 0, 1, False),
    ("club", "Club", ItemRarity.COMMON, 1.5, 6, (1, 6), 0, False, 0, 1, False),
    ("quarterstaff", "Quarterstaff", ItemRarity.COMMON, 2.0, 5, (1, 6), 0, False, 0, 1, False),
    ("shortspear", "Shortspear", ItemRarity.COMMON, 1.5, 12, (1, 6), 0, False, 0, 1, False),
    ("light_pick", "Light Pick", ItemRarity.COMMON, 1.0, 10, (1, 4), 0, True, 0, 1, False),
    ("pick", "Pick", ItemRarity.COMMON, 3.0, 30, (1, 8), 0, False, 0, 1, False),
    ("broadsword", "Broadsword", ItemRarity.COMMON, 4.0, 105, (1, 12), 0, False, 0, 2, False),
    ("light_crossbow", "Light Crossbow", ItemRarity.COMMON, 2.5, 80, (1, 8), 11, False, 0, 2, True),
    ("shortbow", "Shortbow", ItemRarity.COMMON, 1.0, 320, (1, 6), 11, False, 0, 2, False),
    ("dwarf_axe", "Dwarf Axe", ItemRarity.UNCOMMON, 4.0, 75, (1, 10), 0, False, 0, 1, False),
    ("rapier", "Rapier", ItemRarity.UNCOMMON, 1.0, 65, (1, 6), 0, True, 0, 1, False),
]

for slug, name, rarity, weight, price, dmg, rng, fin, thr, hands, reload in _BASE_WEAPONS_DATA:
    _register(ItemDef(
        id=slug, name=name, type=ItemType.WEAPON, rarity=rarity,
        weight=weight, price=price, size=WeaponSize.MEDIUM, damage=dmg,
        range=rng, finesse=fin, thrown=thr, hands=hands, reload=reload
    ))
    # Large variant
    large_slug = f"large_{slug}"
    large_name = f"Large {name}"
    _register(ItemDef(
        id=large_slug, name=large_name, type=ItemType.WEAPON, rarity=rarity,
        weight=round(weight * 2, 1), price=price * 2, size=WeaponSize.LARGE,
        damage=step_damage_die(dmg), range=rng, finesse=fin, thrown=thr,
        hands=hands, reload=reload
    ))

# Armor
_register(ItemDef(id="leather_jerkin", name="Leather Jerkin", type=ItemType.ARMOR, rarity=ItemRarity.COMMON, weight=4.0, price=20, ac=1, max_dex=None, speed_penalty=0))
_register(ItemDef(id="studded_leather", name="Studded Leather", type=ItemType.ARMOR, rarity=ItemRarity.COMMON, weight=6.0, price=55, ac=2, max_dex=3, speed_penalty=0))
_register(ItemDef(id="chainmail", name="Chainmail", type=ItemType.ARMOR, rarity=ItemRarity.UNCOMMON, weight=10.0, price=160, ac=3, max_dex=2, speed_penalty=0))
_register(ItemDef(id="brigandine", name="Brigandine", type=ItemType.ARMOR, rarity=ItemRarity.UNCOMMON, weight=18.0, price=400, ac=4, max_dex=1, speed_penalty=1))
_register(ItemDef(id="plate_armor", name="Plate Armor", type=ItemType.ARMOR, rarity=ItemRarity.RARE, weight=28.0, price=950, ac=5, max_dex=0, speed_penalty=2))
_register(ItemDef(id="dwarf_armor", name="Dwarf Armor", type=ItemType.ARMOR, rarity=ItemRarity.RARE, weight=25.0, price=110, ac=5, max_dex=0, speed_penalty=1))

# Shields
_register(ItemDef(id="dwarf_shield", name="Dwarf Shield", type=ItemType.SHIELD, rarity=ItemRarity.UNCOMMON, weight=3.0, price=60, ac=2))

# Food
_register(ItemDef(id="meat", name="Meat", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=1.0, price=5, food=True, lifespan=2))
_register(ItemDef(id="fruit", name="Fruit", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=0.2, price=4, food=True, lifespan=1))
_register(ItemDef(id="potato", name="Potato", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=1.0, price=3, food=True, lifespan=7))
_register(ItemDef(id="1l_beer", name="1L Beer", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=1.0, price=4, food=True, lifespan=30), "beer")
_register(ItemDef(id="salt", name="Salt", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=0.5, price=3))
_register(ItemDef(id="jerky", name="Jerky", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=0.5, price=8, food=True, lifespan=20))
_register(ItemDef(id="rotten_food", name="Rotten Food", type=ItemType.FOOD, rarity=ItemRarity.COMMON, weight=1.0, price=2, food=True, lifespan=None))

# Scrolls
_register(ItemDef(id="scroll", name="Scroll", type=ItemType.SCROLL, rarity=ItemRarity.COMMON, weight=0.1, price=1))
_register(ItemDef(id="scroll_of_light_globe", name="Scroll of Light Globe", type=ItemType.SCROLL, rarity=ItemRarity.UNCOMMON, weight=0.1, price=180, spell_id="light_globe"), "scroll_light_globe")
_register(ItemDef(id="scroll_of_magic_missile", name="Scroll of Magic Missile", type=ItemType.SCROLL, rarity=ItemRarity.UNCOMMON, weight=0.1, price=180, spell_id="magic_missile"), "scroll_magic_missile")
_register(ItemDef(id="scroll_of_floating_disk", name="Scroll of Floating Disk", type=ItemType.SCROLL, rarity=ItemRarity.UNCOMMON, weight=0.1, price=180, spell_id="floating_disk"), "scroll_floating_disk")
_register(ItemDef(id="scroll_of_sleep", name="Scroll of Sleep", type=ItemType.SCROLL, rarity=ItemRarity.RARE, weight=0.1, price=465, spell_id="sleep"), "scroll_sleep")

# Dictionaries
_register(ItemDef(id="dictionary", name="Dictionary", type=ItemType.DICTIONARY, rarity=ItemRarity.COMMON, weight=2.0, price=4))
_LANGUAGES = ["Ankarin", "Draconic", "Dwarvish", "Elvish", "Gnomish", "Goblin", "Halfling", "Jotun", "Orcish", "Sylvan", "Verdant"]
for lang in _LANGUAGES:
    slug = f"dictionary_of_{lang.lower()}"
    name = f"Dictionary of {lang}"
    _register(ItemDef(id=slug, name=name, type=ItemType.DICTIONARY, rarity=ItemRarity.UNCOMMON, weight=2.0, price=150, language=lang), f"dictionary_{lang.lower()}")


# Gear / Tools / Supplies / Containers / Traps / Gems
_register(ItemDef(id="torch", name="Torch", type=ItemType.LIGHT, rarity=ItemRarity.COMMON, weight=0.5, price=2, light_radius=4))
_register(ItemDef(id="lantern", name="Lantern", type=ItemType.LIGHT, rarity=ItemRarity.COMMON, weight=1.0, price=30, light_radius=6))
_register(ItemDef(id="first_aid_kit", name="First Aid Kit", type=ItemType.CONTAINER, rarity=ItemRarity.COMMON, weight=0.8, price=40, max_charges=10))
_register(ItemDef(id="quiver", name="Quiver", type=ItemType.CONTAINER, rarity=ItemRarity.COMMON, weight=1.5, price=25, max_charges=20))
_register(ItemDef(id="minor_healing_potion", name="Minor Healing Potion", type=ItemType.POTION, rarity=ItemRarity.COMMON, weight=0.2, price=80))
_register(ItemDef(id="venom_gland", name="Venom Gland", type=ItemType.MATERIAL, rarity=ItemRarity.UNCOMMON, weight=0.2, price=25))
_register(ItemDef(id="antidote", name="Antidote", type=ItemType.POTION, rarity=ItemRarity.UNCOMMON, weight=0.2, price=60))
_register(ItemDef(id="vial", name="Vial", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=0.1, price=10))
_register(ItemDef(id="1sqm_hide", name="1sqm Hide", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=2.0, price=12), "hide")
_register(ItemDef(id="red_mushroom", name="Red Mushroom", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=0.1, price=10))
_register(ItemDef(id="lumber", name="Lumber", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=2.0, price=7))
_register(ItemDef(id="iron_bar", name="Iron Bar", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=5.0, price=15))
_register(ItemDef(id="1kg_coal", name="1kg Coal", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=1.0, price=5), "coal")
_register(ItemDef(id="iron_ore", name="Iron Ore", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=4.0, price=8))
_register(ItemDef(id="stone_brick", name="Stone Brick", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=3.0, price=10))
_register(ItemDef(id="paper", name="Paper", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=0.1, price=10))
_register(ItemDef(id="ink", name="Ink", type=ItemType.MATERIAL, rarity=ItemRarity.COMMON, weight=0.1, price=45))
_register(ItemDef(id="bear_trap", name="Bear Trap", type=ItemType.TRAP, rarity=ItemRarity.COMMON, weight=3.0, price=35))
_register(ItemDef(id="alarm_trap", name="Alarm Trap", type=ItemType.TRAP, rarity=ItemRarity.COMMON, weight=1.0, price=45))
_register(ItemDef(id="copper_coin", name="Copper Coin", type=ItemType.MISC, rarity=ItemRarity.COMMON, weight=0.005, price=1))
_register(ItemDef(id="gold_coin", name="Gold Coin", type=ItemType.MISC, rarity=ItemRarity.COMMON, weight=0.005, price=100))
_register(ItemDef(id="pack_saddle", name="Pack Saddle", type=ItemType.TACK, rarity=ItemRarity.COMMON, weight=5.0, price=60))
_register(ItemDef(id="harness", name="Harness", type=ItemType.TACK, rarity=ItemRarity.COMMON, weight=4.0, price=30))
_register(ItemDef(id="rope", name="Rope", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=2.0, price=4))
_register(ItemDef(id="scissors", name="Scissors", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.2, price=1))
_register(ItemDef(id="shovel", name="Shovel", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=2.0, price=4))
_register(ItemDef(id="chisel", name="Chisel", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.3, price=1))
_register(ItemDef(id="pliers", name="Pliers", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.3, price=2))
_register(ItemDef(id="compass", name="Compass", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.2, price=1))
_register(ItemDef(id="deck_of_cards", name="Deck of Cards", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.2, price=1))
_register(ItemDef(id="musical_instrument", name="Musical Instrument", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=2.0, price=4))
_register(ItemDef(id="holy_symbol", name="Holy Symbol", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.5, price=1))
_register(ItemDef(id="signal_horn", name="Signal Horn", type=ItemType.ARTIFACT, rarity=ItemRarity.UNCOMMON, weight=1.0, price=60))
_register(ItemDef(id="leather_of_biwolf", name="Leather of Biwolf", type=ItemType.ARTIFACT, rarity=ItemRarity.RARE, weight=1.0, price=150))
_register(ItemDef(id="cloak", name="Cloak", type=ItemType.ARMOR, rarity=ItemRarity.COMMON, weight=1.0, price=2, guard_bonus=1))
_register(ItemDef(id="chains", name="Chains", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=5.0, price=10))
_register(ItemDef(id="map", name="Map", type=ItemType.TOOL, rarity=ItemRarity.COMMON, weight=0.1, price=1))
_register(ItemDef(id="amethyst", name="Amethyst", type=ItemType.GEM, rarity=ItemRarity.UNCOMMON, weight=0.5, price=120))
_register(ItemDef(id="gemstones", name="Gemstones", type=ItemType.GEM, rarity=ItemRarity.UNCOMMON, weight=0.1, price=60))
_register(ItemDef(id="locked_chest", name="Locked Chest", type=ItemType.CONTAINER, rarity=ItemRarity.UNCOMMON, weight=8.0, price=16))
_register(ItemDef(id="sealed_chest", name="Sealed Chest", type=ItemType.CONTAINER, rarity=ItemRarity.UNCOMMON, weight=8.0, price=16))
_register(ItemDef(id="letter_of_receipt", name="Letter of Receipt", type=ItemType.QUEST, rarity=ItemRarity.COMMON, weight=0.1, price=1))
_register(ItemDef(id="ancient_codex", name="Ancient Codex", type=ItemType.QUEST, rarity=ItemRarity.RARE, weight=2.0, price=4))


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def get(key: str) -> ItemDef | None:
    """Flexible lookup by slug id, display name, or alias."""
    if not isinstance(key, str):
        return None
    item = _LOOKUP.get(key)
    if item is not None:
        return item
    return _LOOKUP.get(key.lower())


def all_items() -> dict[str, ItemDef]:
    """-> dict of all canonical items keyed by display name."""
    return {item.name: item for item in _REGISTRY.values()}



def weapons() -> dict[str, ItemDef]:
    return {item.name: item for item in _REGISTRY.values() if item.type == ItemType.WEAPON}


def armor() -> dict[str, ItemDef]:
    return {item.name: item for item in _REGISTRY.values() if item.type == ItemType.ARMOR}


def shields() -> dict[str, ItemDef]:
    return {item.name: item for item in _REGISTRY.values() if item.type == ItemType.SHIELD}


def food_items() -> dict[str, ItemDef]:
    return {item.name: item for item in _REGISTRY.values() if item.food}


def is_weapon(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and item.type == ItemType.WEAPON


def is_armor(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and item.type == ItemType.ARMOR


def is_artifact(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and item.type == ItemType.ARTIFACT


def is_shield(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and item.type == ItemType.SHIELD


def is_food(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and item.food


def is_consumable(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    if item is None:
        return False
    return item.food or item.type in (ItemType.CONSUMABLE, ItemType.POTION) or item.name in ("First Aid Kit", "Minor Healing Potion")


def is_light_source(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    return item is not None and (item.type == ItemType.LIGHT or item.light_radius > 0)


def is_material(item_or_name: Any) -> bool:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    if item is None:
        return False
    return item.material or item.type == ItemType.MATERIAL or is_crafting_material(item.name)


def is_crafting_material(name: str) -> bool:
    return name in crafting_materials()


def crafting_materials() -> set[str]:
    return {m for r in CRAFTING_RECIPES.values() for m in r.materials}




def item_weight(item_or_name: Any) -> float:
    if isinstance(item_or_name, ItemInstance):
        return item_or_name.weight
    if isinstance(item_or_name, ItemDef):
        return item_or_name.weight
    item = get(item_or_name)
    if item is not None:
        return item.weight
    return 0.5


def weapon_size(item_or_name: Any) -> str:
    if isinstance(item_or_name, ItemInstance):
        return item_or_name.defn.size or WeaponSize.MEDIUM
    if isinstance(item_or_name, ItemDef):
        return item_or_name.size or WeaponSize.MEDIUM
    item = get(item_or_name)
    if item is not None and item.size is not None:
        return item.size
    return WeaponSize.MEDIUM


def buy_price(item_or_name: Any, markup: float = 0.0) -> int:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    if item is None:
        return 1
    return max(1, round(item.price * (1.0 + markup)))


def sell_price(item_or_name: Any, markup: float = 0.0) -> int:
    item = item_or_name if isinstance(item_or_name, ItemDef) else get(getattr(item_or_name, "id", item_or_name))
    if item is None:
        return 1
    return max(1, round(item.price * 0.5 * (1.0 + markup)))


class ChargedName(str):
    """An item name that remembers the charges of the stack it was lifted from, so
    moving a half-empty quiver between packs, stashes and shops does not refill it.
    Equal to, and hashed like, the plain name; `stack_add` is what reads `.charges`."""

    def __new__(cls, name, charges):
        s = super().__new__(cls, name)
        s.charges = charges
        return s


def stack_name(entry) -> str:
    """The name of a pack stack, tagged with its charges when it has any."""
    if isinstance(entry, ItemInstance) and entry.charges is not None:
        return ChargedName(entry.name, entry.charges)
    return entry[0]


def create_instance(key: str, qty: int = 1, days_old: int = 0, charges: int | None = None) -> ItemInstance:
    item = get(key)
    if item is None:
        item_id = str(key).lower().replace(" ", "_")
        c = charges
        name_override = str(key)
    else:
        item_id = item.id
        c = charges if charges is not None else item.max_charges
        name_override = None
    return ItemInstance(id=item_id, charges=c, days_old=days_old, qty=qty, _name=name_override)



# --------------------------------------------------------------------------- #
# Crafting Recipes Registry                                                   #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CraftingRecipe:
    target: str
    materials: list[str]
    complexity: int
    station: CraftingStation
    yield_qty: int = 1
    tools: tuple[str, ...] = ()

    @property
    def level(self) -> int:
        """Worked out from the recipe's difficulty, never set by hand (see `craft_level`)."""
        from .craft_level import level_of
        return level_of(self)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)



def missing_tools(recipe: CraftingRecipe, packs) -> list[str]:
    """The tools `recipe` needs that no pack in `packs` holds. A tool is never consumed and
    needs no particular crafter: any pack of the working group is enough."""
    return [t for t in recipe.tools if not any(u.has_item(t) for u in packs)]


def recipe_goal(recipe: CraftingRecipe) -> int:
    """The progress one batch of `recipe` takes: its complexity plus what its materials cost."""
    total = recipe.complexity
    for mat in recipe.materials:
        mat_item = get(mat)
        total += mat_item.price if mat_item else 10
    return total


CRAFTING_RECIPES: dict[str, CraftingRecipe] = {
    "Minor Healing Potion": CraftingRecipe(
        target="Minor Healing Potion",
        materials=["1L Beer", "Red Mushroom", "Red Mushroom", "Fruit", "Vial"],
        complexity=15,
        station=CraftingStation.APOTHECARY,
    ),
    "Antidote": CraftingRecipe(
        target="Antidote",
        materials=["Venom Gland", "Vial"],
        complexity=15,
        station=CraftingStation.APOTHECARY,
    ),
    "Dwarf Axe": CraftingRecipe(
        target="Dwarf Axe",
        materials=["Iron Bar", "1sqm Hide", "1kg Coal"],
        complexity=10,
        station=CraftingStation.FORGE,
    ),
    "Dwarf Shield": CraftingRecipe(
        target="Dwarf Shield",
        materials=["Iron Bar", "Lumber", "1kg Coal"],
        complexity=10,
        station=CraftingStation.FORGE,
    ),
    "Dwarf Armor": CraftingRecipe(
        target="Dwarf Armor",
        materials=["Iron Bar", "Iron Bar", "1sqm Hide", "1kg Coal"],
        complexity=15,
        station=CraftingStation.FORGE,
    ),
    "Bear Trap": CraftingRecipe(
        target="Bear Trap",
        materials=["Iron Bar"],
        complexity=5,
        station=CraftingStation.FORGE,
    ),
    "Alarm Trap": CraftingRecipe(
        target="Alarm Trap",
        materials=["Iron Bar", "Rope"],
        complexity=5,
        station=CraftingStation.FORGE,
    ),
}

for _lang in _LANGUAGES:
    CRAFTING_RECIPES[f"Dictionary of {_lang}"] = CraftingRecipe(
        target=f"Dictionary of {_lang}",
        materials=["1sqm Hide", "Paper", "Ink"],
        complexity=25,
        station=CraftingStation.SCRIPTORIUM,
    )

CRAFTING_RECIPES["Jerky"] = CraftingRecipe(
    target="Jerky",
    materials=["Meat", "Meat", "Salt"],
    complexity=5,
    station=CraftingStation.COOKING,
    yield_qty=2,
)

COMMON_RECIPES = ["Jerky"]            # known by everyone, no talent or teacher needed

APOTHECARY_RECIPES = ["Minor Healing Potion", "Antidote"]
BLACKSMITH_RECIPES = ["Bear Trap", "Alarm Trap"]

# --------------------------------------------------------------------------- #
# Standard Item Constants                                                     #
# --------------------------------------------------------------------------- #

TORCH_ITEM = "Torch"
COIN_ITEM = "Copper Coin"      # 1 $; 200 weigh 1 kg
GOLD_ITEM = "Gold Coin"        # 100 $, only ever minted at the bank
COIN_VALUE = {COIN_ITEM: 1, GOLD_ITEM: 100}
LANTERN_ITEM = "Lantern"
SIGNAL_HORN_ITEM = "Signal Horn"
BIWOLF_LEATHER_ITEM = "Leather of Biwolf"
AMMO_ITEM = "Quiver"
FIRST_AID_ITEM = "First Aid Kit"
ANTIDOTE_ITEM = "Antidote"
VENOM_GLAND_ITEM = "Venom Gland"
CHEST_ITEM = "Locked Chest"
GEM_ITEM = "Gemstones"
MISSION_CHEST_ITEM = "Sealed Chest"
LETTER_ITEM = "Letter of Receipt"
CODEX_ITEM = "Ancient Codex"


def is_coin(name) -> bool:
    """A Copper or Gold Coin: money, not merchandise -- it never sells or sorts as gear."""
    return isinstance(name, str) and name in COIN_VALUE


def item_tag(item: str | ItemDef | None) -> str:
    """The category pill used across inventory screens: every tag the item
    has, joined by " · " (`FOOD · MATERIAL`). Empty when it has none."""
    return TAG_SEP.join(item_tags(item))


TAG_SEP = " · "


def item_tags(item: str | ItemDef | None) -> list[str]:
    """Category tags, the item's main kind first (WEAPON, ARMOR, SHIELD, AMMO,
    HEAL, LIGHT, FOOD, CHEST, SEALED), then MATERIAL when a recipe uses it too."""
    if not item:
        return []
    it = get(item) if not isinstance(item, ItemDef) else item
    if it is None:
        return []
    main = _main_tag(it)
    tags = [main] if main else []
    if main != "MATERIAL" and is_material(it) and it.type not in (ItemType.WEAPON, ItemType.ARMOR, ItemType.SHIELD):
        tags.append("MATERIAL")
    return tags


def _main_tag(it: ItemDef) -> str:
    if it.type == ItemType.TACK:
        return "TACK"
    if it.type == ItemType.WEAPON:
        return "WEAPON"
    if it.type == ItemType.ARMOR:
        return "ARMOR"
    if it.type == ItemType.SHIELD:
        return "SHIELD"
    if it.type == ItemType.ARTIFACT:
        return "ARTIFACT"
    if it.id == "quiver" or it.name == AMMO_ITEM:
        return "AMMO"
    if it.id == "first_aid_kit" or it.name == FIRST_AID_ITEM:
        return "HEAL"
    if it.type == ItemType.LIGHT or it.light_radius > 0:
        return "LIGHT"
    if it.food:
        return "FOOD"
    if it.name == CHEST_ITEM:
        return "CHEST"
    if it.name == MISSION_CHEST_ITEM:
        return "SEALED"
    if is_material(it):
        return "MATERIAL"
    return ""


def armor_note(it: ItemDef) -> str:
    """The armor slot's one-line summary: AC, plus the guard-test bonus if any."""
    note = f"+{it.ac} AC"
    return f"{note} · +{it.guard_bonus} guard" if it.guard_bonus else note


def item_tooltip(name: str) -> tuple[str, str]:
    """Returns (title, description) for an item's tooltip."""
    it = get(name)
    if it is None:
        return name, ""

    desc = []
    if it.type == ItemType.WEAPON:
        n, faces = it.damage or (1, 4)
        hands = "Two-handed" if it.hands >= 2 else "One-handed"
        reach = f"{it.range * 1.5:g}m range" if it.range else "Melee"
        desc.append(f"Weapon: {n}d{faces} damage  ·  {hands}  ·  {reach}.")
        if it.finesse:
            desc.append("Finesse: Uses Dexterity for attack rolls if it is higher than Strength.")
        if it.thrown:
            desc.append(f"Thrown: Can be thrown up to {it.thrown * 1.5:g}m.")
    elif it.type == ItemType.ARMOR:
        desc.append(f"Armor: +{it.ac} Armor Class.")
        if it.max_dex is not None:
            desc.append(f"Maximum Dexterity bonus to AC is capped at +{it.max_dex}.")
        if it.speed:
            desc.append(f"Heavy: Reduces movement speed by {it.speed} cells.")
        if it.guard_bonus:
            desc.append(f"Disguise: +{it.guard_bonus} to the guard test for a character with a record.")
    elif it.type == ItemType.SHIELD:
        desc.append(f"Shield: +{it.ac} Armor Class when equipped in the off-hand.")
    elif it.type == ItemType.ARTIFACT:
        if it.name == BIWOLF_LEATHER_ITEM:
            desc.append("Artifact: worn in its own slot.")
            desc.append("Passive: +1 AC against anything that is not a humanoid.")
        else:
            desc.append("Artifact: worn in its own slot, it grants a combat action.")
        if it.name == SIGNAL_HORN_ITEM:
            desc.append("Once per battle, 2 points: allies within 10 squares gain +2 initiative.")
    elif it.name == FIRST_AID_ITEM or it.id == "first_aid_kit":
        charges = it.max_charges or 10
        desc.append(f"Restores HP or stabilizes a dying unit. Starts with {charges} charges.")
    elif it.name == AMMO_ITEM or it.id == "quiver":
        ammo = it.max_charges or 20
        desc.append(f"Ammunition for ranged weapons. Holds {ammo} arrows/bolts.")
    elif it.name == "Minor Healing Potion" or it.id == "minor_healing_potion":
        desc.append("Restores 1d6 HP when consumed.")
    elif it.name == TORCH_ITEM or it.id == "torch":
        r = it.light_radius or 4
        desc.append(f"Provides light in a {r * 1.5:g}m radius. Can be dropped on the ground.")
    elif it.type == ItemType.LIGHT or it.light_radius > 0:
        desc.append(f"Provides light in a {it.light_radius * 1.5:g}m radius when equipped in the off-hand.")
    elif it.food:
        desc.append("A day's ration. Prevents starvation when resting.")
        if it.lifespan is not None:
            desc.append(f"Spoils in {it.lifespan} day(s).")

    if is_material(it) and it.type not in (ItemType.WEAPON, ItemType.ARMOR, ItemType.SHIELD):
        desc.append("Crafting material: used in workshop recipes.")

    wt = it.weight
    desc.append(f"Weight: {wt:g} kg.")
    return it.name, " ".join(desc)


