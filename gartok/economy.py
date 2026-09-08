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

PRICES = {
    # weapons
    "Adaga": 8, "Machadinha": 10, "Machado": 35, "Martelo Leve": 10,
    "Martelo": 35, "Clava": 6, "Bordao": 5, "Lanca Curta": 12,
    "Picareta Leve": 10, "Picareta": 30, "Besta Leve": 80,
    # armor (buy price climbs steeply with the AC it grants -- plate is a
    # long-run goal, several top-tier arena purses)
    "Gibao de couro": 20, "Couro batido": 55, "Cota de malha": 160,
    "Brunea": 400, "Armadura de placas": 950,
    # kit
    TORCH_ITEM: 2, "Aljava": 25, "Kit de primeiros socorros": 40, "Lanterna": 30,
    "Corda": 4, "Saco": 2,
    # food (a day's meal each)
    "1kg Carne": 5, "1kg Batata": 3,
}

# What the market keeps in stock to buy (fixed list for now).
MARKET_STOCK = [
    "1kg Carne", "1kg Batata",
    "Adaga", "Machadinha", "Clava", "Lanca Curta", "Machado", "Martelo",
    "Besta Leve", "Aljava",
    "Gibao de couro", "Couro batido", "Cota de malha", "Brunea", "Armadura de placas",
    TORCH_ITEM, "Kit de primeiros socorros", "Lanterna",
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
