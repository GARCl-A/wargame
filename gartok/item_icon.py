"""What each item looks like: the adapter between `items` and `ui/item_icons.draw_item_icon`.

`ICONS` names every item once (kind, material, shape); an item it does not know falls back to a
generic icon for its type, so a new item never draws nothing. Rarity is the rim colour; a Large
or Huge weapon, a spell scroll and a language dictionary share the icon of their plain kind.
"""

from . import items
from .ui.item_icons import TONES, draw_item_icon
from .ui.tokens import T

RIM = {items.ItemRarity.UNCOMMON: T.GREEN, items.ItemRarity.RARE: T.BRASS, items.ItemRarity.UNIQUE: T.BLOOD}
SCALE = 0.8

ICONS = {
    "Dagger": ("blade", "iron", {"length": 34, "width": 8, "guard": 16, "taper": .3}),
    "Rapier": ("blade", "steel", {"length": 62, "width": 5, "guard": 26, "taper": .2}),
    "Sword": ("blade", "iron", {"length": 48, "width": 10, "guard": 24, "taper": .3}),
    "Broadsword": ("blade", "iron", {"length": 58, "width": 14, "guard": 30, "taper": .3}),
    "Hatchet": ("hafted", "wood", {"head": "axe", "length": 62, "size": .75, "metal": TONES["iron"]}),
    "Axe": ("hafted", "wood", {"head": "axe", "length": 72, "metal": TONES["iron"]}),
    "Dwarf Axe": ("hafted", "oak", {"head": "axe", "length": 72, "double": True, "size": .8, "metal": TONES["brass"]}),
    "Light Hammer": ("hafted", "wood", {"head": "hammer", "length": 60, "size": .7, "metal": TONES["iron"]}),
    "Hammer": ("hafted", "wood", {"head": "hammer", "length": 74, "metal": TONES["iron"]}),
    "Club": ("hafted", "wood", {"head": "club", "length": 66}),
    "Quarterstaff": ("hafted", "wood", {"head": "staff", "length": 90}),
    "Shortspear": ("hafted", "wood", {"head": "spear", "length": 84, "metal": TONES["steel"]}),
    "Glaive": ("hafted", "wood", {"head": "glaive", "length": 92, "metal": TONES["iron"]}),
    "Light Pick": ("hafted", "wood", {"head": "pick", "length": 60, "size": .7, "metal": TONES["iron"]}),
    "Pick": ("hafted", "wood", {"head": "pick", "length": 74, "metal": TONES["iron"]}),
    "Light Crossbow": ("crossbow", "wood", {}),
    "Shortbow": ("bow", "wood", {}),
    "Longbow": ("bow", "oak", {"draw": 1.3}),
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
    "Bloom Fruit": ("apple", "fruit", {}),
    "Potato": ("potato", "potato", {}),
    "1L Beer": ("mug", "oak", {}),
    "Jerky": ("jerky", "jerky", {}),
    "Rotten Food": ("apple", "rot", {"rot": True}),
    "Salt": ("sack", "salt", {}),
    "Sugar": ("sack", "salt", {"accent": TONES["amber"]}),
    "Roast Meat": ("steak", "flesh", {}),
    "Fruit Compote": ("flask", "glass", {"accent": TONES["red"]}),
    "Venom Gland": ("drop", "green", {}),
    "Snake Venom Gland": ("drop", "green", {}),
    "Snake Dragon Corpse": ("hide", "green", {}),
    "Dragon Egg": ("egg", "red", {}),
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
    "Flint and Steel": ("rocks", "iron", {}),
    "Signal Horn": ("horn", "bone", {"accent": TONES["brass"]}),
    "Leather of Biwolf": ("hide", "fur", {}),
    "Thunderhide": ("storm_hide", "storm", {}),
    "Semi-precious Gemstone": ("gems", "blue", {}),
    "Precious Gemstone": ("gems", "gold", {}),
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

# the founding trades: the same silhouettes, picked for what the trade does
VOCATION_ICONS = {
    "warband": ("shield", "iron", {"boss": TONES["brass"]}),
    "delvers": ("hafted", "wood", {"head": "pick", "length": 74, "metal": TONES["iron"]}),
    "wilds": ("bow", "wood", {}),
    "scholars": ("book", "leather", {"clasp": True}),
    "caravan": ("compass", "brass", {}),
    "marsh": ("drop", "green", {}),
}


# the web client's game-icons.net glyph per kind (`assets/icons/item/<glyph>.svg`); a hafted weapon is told by
# its head, an armour by its style
GLYPHS = {
    "blade": "broadsword", "bow": "pocket-bow", "crossbow": "crossbow", "armor": "leather-vest", "cloak": "hood",
    "shield": "round-shield", "flask": "round-bottom-flask", "apple": "shiny-apple", "hide": "animal-hide",
    "storm_hide": "animal-hide", "rocks": "stone-pile", "steak": "meat", "jerky": "meat", "sack": "swap-bag",
    "drop": "drop", "horn": "hunting-horn", "book": "book-cover", "chest": "locked-chest", "coin": "two-coins",
    "gems": "gems", "gem": "emerald", "potato": "potato", "mug": "beer-stein", "egg": "egg-clutch",
    "mushroom": "mushroom-gills", "logs": "log", "ingot": "metal-bar", "brick": "brick-pile", "sheet": "rolled-cloth",
    "ink": "quill-ink", "scroll": "scroll-unfurled", "torch": "torch", "lantern": "lantern-flame",
    "aid_kit": "first-aid-kit", "quiver": "quiver", "beartrap": "wolf-trap", "alarm": "alarm-clock",
    "saddle": "saddle", "harness": "horse-head", "rope": "rope-coil", "scissors": "scissors", "shovel": "spade",
    "chisel": "chisel", "pliers": "pincers", "compass": "compass", "cards": "card-random", "lute": "lyre",
    "holy": "ankh", "chains": "crossed-chains", "map": "treasure-map", "letter": "envelope",
}
HEAD_GLYPHS = {"axe": "battle-axe", "hammer": "flat-hammer", "club": "wood-club", "spear": "stone-spear",
               "staff": "wizard-staff", "glaive": "glaive", "pick": "war-pick"}
STYLE_GLYPHS = {"mail": "chain-mail", "plates": "breastplate"}


def _base(name):
    """The catalogue name an icon is filed under: no ` (aged)` suffix, no `Large ` / `Huge ` prefix, and every
    spell scroll and language dictionary is the plain Scroll and Dictionary."""
    if hasattr(name, "name"):
        name = name.name
    name = str(name).split(" (")[0].removeprefix("Large ").removeprefix("Huge ").removeprefix("Any ")
    if name.startswith("Scroll of "):
        return "Scroll"
    if name.startswith("Dictionary of "):
        return "Dictionary"
    return name


def icon_spec(name):
    """-> `(kind, tone, rim, scale, shape)` for `draw_item_icon`."""
    if hasattr(name, "name"):
        name = name.name
    defn = items.get(name)
    kind, material, shape = ICONS.get(_base(name)) or FALLBACK.get(defn.type if defn else None, GENERIC)
    return kind, TONES[material], RIM.get(defn.rarity if defn else None), SCALE, shape


def glyph(name):
    """-> `"item/<glyph>"`, the item's glyph under `assets/icons/`."""
    kind, _tone, _rim, _scale, shape = icon_spec(name)
    if kind == "blade" and _base(name) == "Dagger":
        return "item/plain-dagger"
    return "item/" + (HEAD_GLYPHS.get(shape.get("head")) if kind == "hafted"
                      else STYLE_GLYPHS.get(shape.get("style"), GLYPHS["armor"]) if kind == "armor"
                      else GLYPHS.get(kind, "knapsack"))


def vocation_icon(vocation_id):
    """-> `(kind, tone, shape)` for `draw_item_icon`, the plain data a vocation card carries."""
    kind, material, shape = VOCATION_ICONS[vocation_id]
    return kind, TONES[material], shape


def draw_icon(surf, rect, name):
    if hasattr(name, "name"):
        name = name.name
    kind, tone, rim, scale, shape = icon_spec(name)
    draw_item_icon(surf, rect, kind, tone, rim, scale=scale, **shape)
