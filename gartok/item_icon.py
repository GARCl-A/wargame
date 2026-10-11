"""What each item looks like: the adapter between `items` and `ui/item_icons.draw_item_icon`.

`ICONS` names every item once (kind, material, shape); an item it does not know falls back to a
generic icon for its type, so a new item never draws nothing. Rarity is the rim colour; a Large
weapon, a spell scroll and a language dictionary share the icon of their plain kind.
"""

from . import items
from .ui.item_icons import TONES, draw_item_icon
from .ui.tokens import T

RIM = {items.ItemRarity.UNCOMMON: T.GREEN, items.ItemRarity.RARE: T.BRASS, items.ItemRarity.UNIQUE: T.BLOOD}
SCALE = 0.8

ICONS = {
    "Dagger": ("blade", "iron", {"length": 34, "width": 8, "guard": 16, "taper": .3}),
    "Rapier": ("blade", "steel", {"length": 62, "width": 5, "guard": 26, "taper": .2}),
    "Broadsword": ("blade", "iron", {"length": 58, "width": 14, "guard": 30, "taper": .3}),
    "Hatchet": ("hafted", "wood", {"head": "axe", "length": 62, "size": .75, "metal": TONES["iron"]}),
    "Axe": ("hafted", "wood", {"head": "axe", "length": 72, "metal": TONES["iron"]}),
    "Dwarf Axe": ("hafted", "oak", {"head": "axe", "length": 72, "double": True, "size": .8, "metal": TONES["brass"]}),
    "Light Hammer": ("hafted", "wood", {"head": "hammer", "length": 60, "size": .7, "metal": TONES["iron"]}),
    "Hammer": ("hafted", "wood", {"head": "hammer", "length": 74, "metal": TONES["iron"]}),
    "Club": ("hafted", "wood", {"head": "club", "length": 66}),
    "Quarterstaff": ("hafted", "wood", {"head": "staff", "length": 90}),
    "Shortspear": ("hafted", "wood", {"head": "spear", "length": 84, "metal": TONES["steel"]}),
    "Light Pick": ("hafted", "wood", {"head": "pick", "length": 60, "size": .7, "metal": TONES["iron"]}),
    "Pick": ("hafted", "wood", {"head": "pick", "length": 74, "metal": TONES["iron"]}),
    "Light Crossbow": ("crossbow", "wood", {}),
    "Shortbow": ("bow", "wood", {}),
    "Leather Jerkin": ("armor", "leather", {}),
    "Studded Leather": ("armor", "leather", {"style": "studded"}),
    "Chainmail": ("armor", "iron", {"style": "mail"}),
    "Brigandine": ("armor", "leather", {"style": "plates", "trim": TONES["iron"]}),
    "Plate Armor": ("armor", "steel", {"style": "plates", "pauldrons": 1.0}),
    "Dwarf Armor": ("armor", "iron", {"style": "plates", "pauldrons": 1.0, "trim": TONES["brass"]}),
    "Cloak": ("cloak", "cloth", {}),
    "Dwarf Shield": ("shield", "iron", {"boss": TONES["brass"]}),
    "Meat": ("steak", "flesh", {}),
    "Fruit": ("apple", "fruit", {}),
    "Potato": ("potato", "potato", {}),
    "1L Beer": ("mug", "oak", {}),
    "Jerky": ("jerky", "jerky", {}),
    "Rotten Food": ("apple", "rot", {"rot": True}),
    "Salt": ("sack", "salt", {}),
    "Venom Gland": ("drop", "green", {}),
    "Vial": ("flask", "glass", {"empty": True}),
    "1sqm Hide": ("hide", "leather", {}),
    "Red Mushroom": ("mushroom", "mushroom", {}),
    "Lumber": ("logs", "wood", {}),
    "Iron Bar": ("ingot", "iron", {}),
    "1kg Coal": ("rocks", "coal", {"flecks": (120, 120, 130)}),
    "Iron Ore": ("rocks", "iron", {"flecks": (190, 100, 60)}),
    "Stone Brick": ("brick", "stone", {}),
    "Paper": ("sheet", "paper", {}),
    "Ink": ("ink", "glass", {}),
    "Legendary Horn": ("horn", "bone", {"accent": TONES["gold"]}),
    "Scroll": ("scroll", "paper", {}),
    "Dictionary": ("book", "leather", {}),
    "Torch": ("torch", "wood", {}),
    "Lantern": ("lantern", "iron", {}),
    "First Aid Kit": ("aid_kit", "salt", {}),
    "Quiver": ("quiver", "leather", {}),
    "Locked Chest": ("chest", "wood", {}),
    "Sealed Chest": ("chest", "wood", {"sealed": True}),
    "Minor Healing Potion": ("flask", "glass", {"accent": TONES["red"]}),
    "Antidote": ("flask", "glass", {"accent": TONES["green"]}),
    "Bear Trap": ("beartrap", "iron", {}),
    "Alarm Trap": ("alarm", "wood", {}),
    "Copper Coin": ("coin", "copper", {}),
    "Gold Coin": ("coin", "gold", {"mark": "g"}),
    "Pack Saddle": ("saddle", "leather", {}),
    "Harness": ("harness", "leather", {}),
    "Rope": ("rope", "cloth", {}),
    "Scissors": ("scissors", "iron", {}),
    "Shovel": ("shovel", "iron", {}),
    "Chisel": ("chisel", "steel", {}),
    "Pliers": ("pliers", "iron", {}),
    "Compass": ("compass", "brass", {}),
    "Deck of Cards": ("cards", "paper", {}),
    "Musical Instrument": ("lute", "wood", {}),
    "Holy Symbol": ("holy", "gold", {}),
    "Chains": ("chains", "iron", {}),
    "Map": ("map", "paper", {}),
    "Signal Horn": ("horn", "bone", {"accent": TONES["brass"]}),
    "Leather of Biwolf": ("hide", "fur", {}),
    "Thunderhide": ("storm_hide", "storm", {}),
    "Amethyst": ("gem", "purple", {}),
    "Gemstones": ("gems", "blue", {}),
    "Letter of Receipt": ("letter", "paper", {}),
    "Ancient Codex": ("book", "oak", {"clasp": True, "accent": TONES["amber"]}),
}

FALLBACK = {
    items.ItemType.WEAPON: ("blade", "iron", {}), items.ItemType.ARMOR: ("armor", "leather", {}),
    items.ItemType.SHIELD: ("shield", "iron", {}), items.ItemType.POTION: ("flask", "glass", {}),
    items.ItemType.CONSUMABLE: ("flask", "glass", {}), items.ItemType.FOOD: ("apple", "fruit", {}),
    items.ItemType.MATERIAL: ("rocks", "stone", {}), items.ItemType.SCROLL: ("scroll", "paper", {}),
    items.ItemType.DICTIONARY: ("book", "leather", {}), items.ItemType.LIGHT: ("torch", "wood", {}),
    items.ItemType.CONTAINER: ("chest", "wood", {}), items.ItemType.TRAP: ("beartrap", "iron", {}),
    items.ItemType.MISC: ("coin", "copper", {}), items.ItemType.TACK: ("saddle", "leather", {}),
    items.ItemType.TOOL: ("scissors", "iron", {}), items.ItemType.GEM: ("gem", "purple", {}),
    items.ItemType.QUEST: ("letter", "paper", {}), items.ItemType.ARTIFACT: ("horn", "bone", {}),
}
GENERIC = ("coin", "copper", {})


def _base(name):
    """The catalogue name an icon is filed under: no ` (aged)` suffix, no `Large ` prefix, and every
    spell scroll and language dictionary is the plain Scroll and Dictionary."""
    name = name.split(" (")[0].removeprefix("Large ")
    if name.startswith("Scroll of "):
        return "Scroll"
    if name.startswith("Dictionary of "):
        return "Dictionary"
    return name


def icon_spec(name):
    """-> `(kind, tone, rim, scale, shape)` for `draw_item_icon`."""
    defn = items.get(name)
    kind, material, shape = ICONS.get(_base(name)) or FALLBACK.get(defn.type if defn else None, GENERIC)
    return kind, TONES[material], RIM.get(defn.rarity if defn else None), SCALE, shape


def draw_icon(surf, rect, name):
    kind, tone, rim, scale, shape = icon_spec(name)
    draw_item_icon(surf, rect, kind, tone, rim, scale=scale, **shape)
