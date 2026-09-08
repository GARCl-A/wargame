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

# The lumber yard outside the walls: day-labour for anyone who is broke. You
# borrow the foreman's axe and fell trees on land that is not yours, so you keep
# no wood -- just a flat wage for the hours. Kept deliberately meagre: a full
# 16 h day feeds you and leaves a little over, while a won arena bout or a wilds
# haul pays several times better. It is a floor, not a living.
LUMBER_WAGE = 3                         # copper earned per whole block worked
LUMBER_BLOCK_HOURS = 4                  # ...one block is four hours at the yard
LUMBER_XP_HOURS = 16                    # hours of labour banked per work-XP mark
LUMBER_SHIFT_HOURS = (4, 8, 12, 16)     # shift lengths the foreman offers

PRICES = {
    # weapons
    "Dagger": 8, "Hatchet": 10, "Axe": 35, "Light Hammer": 10,
    "Hammer": 35, "Club": 6, "Quarterstaff": 5, "Shortspear": 12,
    "Light Pick": 10, "Pick": 30, "Light Crossbow": 80,
    # armor (buy price climbs steeply with the AC it grants -- plate is a
    # long-run goal, several top-tier arena purses)
    "Leather Jerkin": 20, "Studded Leather": 55, "Chainmail": 160,
    "Brigandine": 400, "Plate Armor": 950,
    # kit
    TORCH_ITEM: 2, "Quiver": 25, "First Aid Kit": 40, "Lantern": 30,
    "Rope": 4, "Sack": 2,
    # food (a day's meal each)
    "1kg Meat": 5, "1kg Potato": 3,
}

# What the market keeps in stock to buy (fixed list for now).
MARKET_STOCK = [
    "1kg Meat", "1kg Potato",
    "Dagger", "Hatchet", "Club", "Shortspear", "Axe", "Hammer",
    "Light Crossbow", "Quiver",
    "Leather Jerkin", "Studded Leather", "Chainmail", "Brigandine", "Plate Armor",
    TORCH_ITEM, "First Aid Kit", "Lantern",
]

DEAL_MIN, DEAL_MAX = -0.15, 0.25
_ALIGN_DEAL = {0: 0.10, 1: 0.05, 2: 0.0, 3: -0.05, 4: -0.10}   # keyed by alignment_distance


def market_deal(party, vendor_language, vendor_alignment):
    """Best deal `party` can strike with a vendor of this language and alignment.

    Only members who share the vendor's language can haggle at all; among those,
    the one with the highest Charisma modifier speaks for the group. Their
    Charisma narrows the spread; how close their alignment sits to the vendor's
    nudges it further (same bent = a break, opposite = a premium).
    """
    speakers = [m for m in party if vendor_alignment is not None
                and vendor_language in m.languages]
    if not speakers:
        return 0.0
    voice = max(speakers, key=lambda m: (m.mod_charisma,
                -data.alignment_distance(m.alignment, vendor_alignment)))
    cha = max(0, voice.mod_charisma) * 0.04
    align = _ALIGN_DEAL[data.alignment_distance(voice.alignment, vendor_alignment)]
    return round(max(DEAL_MIN, min(DEAL_MAX, cha + align)), 3)


def lumber_pay(hours):
    """Flat wage for `hours` at the lumber yard: `LUMBER_WAGE` per whole block,
    leftover hours unpaid (you are paid by the block, not the minute)."""
    return LUMBER_WAGE * (int(hours) // LUMBER_BLOCK_HOURS)


def buy_price(name, deal=0.0):
    """What the market charges for `name` (fallback: a token price by weight)."""
    base = PRICES.get(name, max(1, round(data.item_weight(name) * 2)))
    return max(1, round(base * (1 - deal)))


def sell_price(name, deal=0.0):
    """What the market pays for `name` -- kept a fraction of the buy price, so
    resale is a loss even after a good haggle (`deal` up to `DEAL_MAX` = 0.25
    keeps the two factors 0.15 apart)."""
    base = PRICES.get(name, max(1, round(data.item_weight(name) * 2)))
    return max(1, round(base * (SELL_FACTOR + 0.4 * deal)))
