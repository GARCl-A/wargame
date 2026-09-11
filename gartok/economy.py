"""Money and the market  (designed for the wargame).

Currency is copper coins. Coins live on the character -- the guild has no
treasury (see [[gartok-tactical-project]]). `PRICES` is the shop's buy price;
you sell back at `SELL_FACTOR` of it, always a loss.

Haggling: a shopper who speaks the vendor's tongue can bend the price.
`market_deal` turns the party + vendor into a single "deal" fraction -- > 0
narrows the spread in the shopper's favour (cheaper buys, better sell-back),
< 0 is a vendor charging a premium to deal with an outsider. No shared language
-> deal 0, tabled prices.

Only the raw generator tables and game constants stay in `data.py`; the pricing
and haggling *behaviour* lives here.
"""

from . import data

TORCH_ITEM = data.TORCH_ITEM

STARTING_WEALTH_DICE = (5, 10)          # 5d10 copper rolled at character creation
SELL_FACTOR = 0.5                       # resale = half the buy price, floored at 1
CHA_DEAL_STEP = 0.04                    # deal fraction per point of haggle Charisma
                                       #   mod (and per step of the food talent)

# The lumber yard outside the walls: day-labour for anyone who is broke. You
# borrow the foreman's axe and fell trees on land that is not yours, so you keep
# no wood -- just a flat wage for the hours. Kept deliberately meagre: a full
# 16 h day feeds you and leaves a little over, while a won arena bout or a wilds
# haul pays several times better. It is a floor, not a living.
LUMBER_WAGE = 3                         # copper earned per whole block worked
LUMBER_WAGE_OWN_AXE = 4                 # ...more, once you swing your own Axe (see lumber_level)
LUMBER_BLOCK_HOURS = 4                  # ...one block is four hours at the yard
LUMBER_XP_HOURS = 16                    # hours of labour banked per work-XP mark
LUMBER_SHIFT_HOURS = (4, 8, 12, 16)     # shift lengths the foreman offers
LUMBER_LEVEL_OWN_AXE = 1                # the yard's ceiling once you bring your own Axe

# The Bankers rent the guild its first shared property: a strongbox at the bank
# in the City. A flat fee for the right to it, no reputation gate. One tier for
# now -- `BANK_CHEST_CAPACITY` is a value a later, pricier tier can raise.
BANK_CHEST_PRICE = 50                   # copper for the right to a strongbox
BANK_CHEST_CAPACITY = 10                # kg the strongbox holds

PRICES = {
    # weapons
    "Dagger": 8, "Hatchet": 10, "Axe": 35, "Light Hammer": 10,
    "Hammer": 35, "Club": 6, "Quarterstaff": 5, "Shortspear": 12,
    "Light Pick": 10, "Pick": 30, "Broadsword": 105, "Light Crossbow": 80,
    # armor (buy price climbs steeply with the AC it grants -- plate is a
    # long-run goal, several top-tier arena purses)
    "Leather Jerkin": 20, "Studded Leather": 55, "Chainmail": 160,
    "Brigandine": 400, "Plate Armor": 950,
    # kit
    TORCH_ITEM: 2, "Quiver": 25, "First Aid Kit": 40, "Lantern": 30,
    "Rope": 4, "Sack": 2,
    # food (a day's meal each)
    "Meat": 5, "Potato": 3,
}

# What the market keeps in stock to buy (fixed list for now).
MARKET_STOCK = [
    "Dagger", "Hatchet", "Club", "Shortspear", "Axe", "Hammer", "Broadsword",
    "Light Crossbow", "Quiver",
    "Leather Jerkin", "Studded Leather", "Chainmail", "Brigandine", "Plate Armor",
    "Meat", "Potato", TORCH_ITEM, "First Aid Kit", "Lantern",
]


# The market's category tabs, in display order. Weapons and armor read straight
# off the data tables; everything else is "kit" (the stackable/consumable shelf,
# where the quantity stepper lives).
_MARKET_TABS = (("WEAPONS", "weapons"), ("ARMOR", "armor"), ("CONSUMABLES & KIT", "kit"))


def _stock_category(name):
    if name in data.WEAPONS:
        return "weapons"
    if name in data.ARMOR:
        return "armor"
    return "kit"


def market_categories():
    """`[(label, key, [names])]` for the market tabs, in display order -- the
    active tab's list is what `market_screen` lays out."""
    groups = {key: [] for _lbl, key in _MARKET_TABS}
    for name in MARKET_STOCK:
        groups[_stock_category(name)].append(name)
    return [(lbl, key, groups[key]) for lbl, key in _MARKET_TABS]


DEAL_MIN, DEAL_MAX = -0.15, 0.25
_ALIGN_DEAL = {0: 0.10, 1: 0.05, 2: 0.0, 3: -0.05, 4: -0.10}   # keyed by alignment_distance


# Haggling -- the "deal" is a list of contributions, not one scalar, so a new
# source (a talent, later a vendor's standing) is just another `PriceMod` rather
# than a new argument threaded through pricing. The base haggle is one untyped
# mod; `buy_price` / `sell_price` fold the ones that apply to each line item
# through `data.resolve_bonus` -- the same typed-bonus shape combat uses.

class PriceMod:
    """One contribution to a market visit's deal fraction.

    `applies(item, side)` -- side is "buy" or "sell" -- scopes the mod to some
    line items (default: everything). `kind` feeds `data.resolve_bonus`: the same
    kind does not stack, `None` stacks (and every penalty stacks).
    """

    def __init__(self, amount, label, *, kind=None, applies=None):
        self.amount = amount
        self.label = label
        self.kind = kind
        self._applies = applies

    def applies(self, item, side):
        return self._applies is None or self._applies(item, side)


def _haggle_fraction(party, vendor_language, vendor_alignment, leader=None):
    """The base deal for the whole party: only members who share the vendor's
    language haggle. Among those, the party's **leader** speaks (see
    `Group.leader`, `guild.py`) if they're eligible; otherwise -- no leader
    passed in, or the leader doesn't share the tongue -- the highest Charisma
    modifier does. Their Charisma narrows the spread; alignment distance
    nudges it (same bent = a break, opposite = a premium)."""
    speakers = [m for m in party if vendor_alignment is not None
                and vendor_language in m.languages]
    if not speakers:
        return 0.0
    if leader is not None and leader in speakers:
        voice = leader
    else:
        voice = max(speakers, key=lambda m: (m.haggle_charisma_mod,
                    -data.alignment_distance(m.alignment, vendor_alignment)))
    cha = max(0, voice.haggle_charisma_mod) * CHA_DEAL_STEP
    align = _ALIGN_DEAL[data.alignment_distance(voice.alignment, vendor_alignment)]
    return round(max(DEAL_MIN, min(DEAL_MAX, cha + align)), 3)


def market_deal(party, vendor_language, vendor_alignment, leader=None):
    """The single scalar deal (base haggle only). Kept for callers that just want
    the headline number; per-item pricing goes through `deal_mods` + `buy_price`.
    """
    return _haggle_fraction(party, vendor_language, vendor_alignment, leader)


def deal_mods(party, vendor_language, vendor_alignment, leader=None):
    """Every `PriceMod` in play for this visit: the base haggle plus each
    shopper's talent contributions. Hand the list to `buy_price` / `sell_price`.
    """
    mods = []
    base = _haggle_fraction(party, vendor_language, vendor_alignment, leader)
    if base:
        mods.append(PriceMod(base, "haggle"))
    for m in party:
        mods.extend(m.price_mods())
    return mods


def _as_mods(mods):
    """Accept the `PriceMod` list, or the old scalar deal (tests / callers)."""
    if isinstance(mods, (int, float)):
        return [PriceMod(float(mods), "deal")] if mods else []
    return list(mods)


def deal_value(mods, item, side):
    """Net deal fraction for one line item (`side` = "buy" | "sell"), clamped.
    `item` None = the general deal, ignoring item-scoped mods."""
    contribs = [(m.amount, m.kind, m.label) for m in _as_mods(mods)
                if m.applies(item, side)]
    total, _ = data.resolve_bonus(contribs)
    return round(max(DEAL_MIN, min(DEAL_MAX, total)), 3)


def lumber_level(unit):
    """The lumber yard's job level for this worker: 0 with the foreman's lent
    axe, 1 once they show up swinging their own Axe. Gates work-XP the same
    way `progression.xp_award` gates combat XP -- see `work_xp_hours`."""
    return LUMBER_LEVEL_OWN_AXE if unit.equipped_weapon == "Axe" else 0


def lumber_pay(hours, level=0):
    """Wage for `hours` at the lumber yard, paid by the whole block, leftover
    hours unpaid. Your own Axe (`level` >= LUMBER_LEVEL_OWN_AXE) cuts faster,
    for a better wage."""
    wage = LUMBER_WAGE_OWN_AXE if level >= LUMBER_LEVEL_OWN_AXE else LUMBER_WAGE
    return wage * (int(hours) // LUMBER_BLOCK_HOURS)


def _base_price(name):
    return PRICES.get(name, max(1, round(data.item_weight(name) * 2)))


def buy_price(name, mods=()):
    """What the market charges for `name` (fallback: a token price by weight).
    `mods` is a `PriceMod` list (from `deal_mods`) or a bare deal fraction."""
    return max(1, round(_base_price(name) * (1 - deal_value(mods, name, "buy"))))


def sell_price(name, mods=()):
    """What the market pays for `name` -- kept a fraction of the buy price, so
    resale is a loss even after a good haggle (`deal` up to `DEAL_MAX` = 0.25
    keeps the two factors 0.15 apart)."""
    return max(1, round(_base_price(name) * (SELL_FACTOR + 0.4 * deal_value(mods, name, "sell"))))
