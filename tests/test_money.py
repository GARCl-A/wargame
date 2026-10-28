"""Money is `$`: Copper Coin = $1, Gold Coin = $100, made and melted only at the bank."""

import random

from gartok import economy, items, loot, persist, world
from gartok.constants import fmt_money
from gartok.guild import Guild
from gartok.holdings import Stash
from gartok.trade import Counter
from gartok.unit import Unit, distribute_load, flatten_pack
from gartok.vault import BankVault

COPPER, GOLD = items.COIN_ITEM, items.GOLD_ITEM


def _purse(copper=0, gold=0):
    u = Unit("player")
    u._base_inventory = []
    if copper:
        u.give_to_pack(COPPER, copper)
    if gold:
        u.give_to_pack(GOLD, gold)
    return u


def _held(holder):
    return holder.count_of(COPPER), holder.count_of(GOLD)


def test_a_gold_coin_is_a_hundred_dollars_and_weighs_like_copper():
    assert items.get(GOLD).price == 100 and items.get(COPPER).price == 1
    assert items.item_weight(GOLD) == items.item_weight(COPPER) == 0.005
    assert items.is_coin(GOLD) and items.is_coin(COPPER) and not items.is_coin("Rope")


def test_money_adds_copper_and_gold():
    assert _purse(37, 2).money == 237


def test_raising_money_mints_copper_never_gold():
    u = _purse(10, 1)
    u.money += 500
    assert _held(u) == (510, 1)


def test_spending_takes_copper_first():
    u = _purse(60, 3)
    u.money -= 50
    assert _held(u) == (10, 3)


def test_spending_past_the_copper_breaks_a_gold_coin_and_returns_change():
    u = _purse(20, 2)
    u.money -= 50                         # 20 copper + one gold broken, 70 back
    assert _held(u) == (70, 1) and u.money == 170


def test_a_payment_can_break_several_gold_coins():
    u = _purse(0, 3)
    u.money -= 250
    assert _held(u) == (50, 0) and u.money == 50


def test_change_is_exact_when_the_gold_covers_the_price_to_the_dollar():
    u = _purse(0, 2)
    u.money -= 100
    assert _held(u) == (0, 1)


def test_money_never_goes_below_zero():
    u = _purse(5, 1)
    u.money = 0
    assert u._base_inventory == [] and u.money == 0


def test_a_split_gold_stack_is_still_one_balance():
    u = _purse(0, 5)
    u.split_pack(0, 2)
    u.money -= 350
    assert u.money == 150 and _held(u) == (50, 1)


def test_fmt_money_has_a_thousands_separator():
    assert fmt_money(1250) == "$1,250" and fmt_money(0) == "$0"


def test_coins_stay_out_of_the_battle_inventory():
    assert flatten_pack(_purse(5, 5)) == []


def test_distribute_load_keeps_gold_as_gold():
    a, b = _purse(0, 40), _purse(0, 0)
    distribute_load([a, b])
    assert a.count_of(GOLD) + b.count_of(GOLD) == 40
    assert a.count_of(COPPER) + b.count_of(COPPER) == 0


def test_a_save_round_trip_keeps_gold():
    u = _purse(12, 3)
    v = Unit.from_save(persist.unit_to_dict(u))
    assert _held(v) == (12, 3) and v.money == 312


def test_a_fallen_members_gold_is_in_the_loot():
    u = _purse(7, 2)

    class Body:
        char, fled, inventory = u, False, []
        weapon_hand = torch_hand = lantern_hand = False

    class Battle:
        enemy_units, foe_units, player_units, ground = [], [], [], []

    pool = loot.field_loot(Battle(), [Body()], random.Random(0))
    assert pool.count(COPPER) == 7 and pool.count(GOLD) == 2


# ---- the bank exchange -------------------------------------------------- #
def test_minting_costs_a_dollar_over_par_per_coin():
    assert economy.gold_price(3) == 303 and economy.gold_payout(3) == 297
    u = _purse(1000)
    assert economy.buy_gold(u, 3)
    assert _held(u) == (1000 - 303, 3)


def test_melting_pays_a_dollar_under_par_per_coin():
    u = _purse(0, 3)
    assert economy.sell_gold(u, 3)
    assert _held(u) == (297, 0)


def test_a_round_trip_loses_two_dollars_a_coin():
    u = _purse(500)
    economy.buy_gold(u, 4)
    economy.sell_gold(u, 4)
    assert u.money == 500 - 4 * 2


def test_you_cannot_mint_beyond_your_copper_or_melt_beyond_your_gold():
    u = _purse(250, 1)
    assert economy.max_gold_buyable(u) == 2
    assert not economy.buy_gold(u, 3) and not economy.buy_gold(u, 0)
    assert not economy.sell_gold(u, 2) and not economy.sell_gold(u, 0)
    assert _held(u) == (250, 1)


def test_minting_draws_from_every_copper_stack():
    u = _purse(300)
    u.split_pack(0, 100)
    assert economy.buy_gold(u, 2)
    assert _held(u) == (300 - 202, 2)


def test_the_chest_exchanges_too_but_melting_must_fit_it():
    chest = Stash(1)
    chest.put(COPPER, 202)
    assert economy.buy_gold(chest, 2) and _held(chest) == (0, 2)
    tight = Stash(1)
    tight.put(GOLD, 100)                              # 0.5 kg, and each one melted adds 0.49 kg
    assert economy.max_gold_sellable(tight) == 1
    assert not economy.sell_gold(tight, 2)
    assert economy.sell_gold(tight, 1) and _held(tight) == (99, 99)


def _bank(party, chest=None):
    random.seed(5)
    guild = Guild(list(party), bank=chest if chest is not None else Stash(30))
    return BankVault(guild, list(party))


def test_minting_at_the_bank_pays_the_fee():
    u = _purse(1000)
    s = _bank([u])
    assert s._exchange(u, "buy_gold", 3)
    assert _held(u) == (1000 - 303, 3) and "minted 3 gold coins" in s.notice


def test_melting_at_the_bank_returns_copper_less_the_fee():
    u = _purse(0, 5)
    s = _bank([u])
    assert s._exchange(u, "sell_gold", 2)
    assert _held(u) == (198, 3)


def test_the_bank_cannot_mint_past_what_is_held():
    u = _purse(250)
    s = _bank([u])
    assert not s._exchange(u, "buy_gold", 3)
    assert _held(u) == (250, 0)


def test_the_chest_stack_can_be_exchanged_in_the_chest():
    chest = Stash(30)
    chest.put(COPPER, 404)
    s = _bank([_purse()], chest)
    assert s._exchange(s._holder_of(s.OWNER), "buy_gold", 4)
    assert _held(chest) == (0, 4)


def test_the_market_will_not_buy_coins():
    u = _purse(50, 5)
    u.give_to_pack("Rope")
    random.seed(2)
    s = Counter(Guild([u]), [u], world.node("city"))
    picks = [(u, i) for i in range(len(u._base_inventory))]
    assert [s._name_of(p) for p in s._goods(picks)] == ["Rope"]
