"""The Rules chapter's "Work & Money" sections: the numbers read off the modules that run them."""

from . import arena, constants, craft_level, economy, gather, hunt, i18n, progression
from .encounters import AMBUSH_CHANCE_PER_HOUR


def _lines(section, n, **fmt):
    return [i18n.t(f"wiki_rules.{section}.{i}", **fmt) for i in range(1, n + 1)]


def _pct(x):
    return round(x * 100)


def _hours(hours):
    return ", ".join(str(h) for h in hours[:-1]) + f" {i18n.t('wiki_rules.or').strip()} {hours[-1]}"


def built():
    deal = economy._ALIGN_DEAL
    c1, c2 = progression.COMBAT_XP_THRESHOLDS[0], progression.COMBAT_XP_THRESHOLDS[1]
    return {
        "bank": _lines("bank", 2, price=economy.BANK_CHEST_PRICE, kg=economy.BANK_CHEST_CAPACITY, fee=economy.GOLD_FEE,
                       rep=economy.CITY_PROPERTY_REP_GATE, house=economy.CITY_PROPERTY_PRICE,
                       house_kg=economy.CITY_PROPERTY_CAPACITY, tax=economy.CITY_PROPERTY_TAX,
                       period=economy.CITY_PROPERTY_TAX_PERIOD_DAYS, limit=economy.CITY_PROPERTY_MISSED_PAYMENTS_LIMIT,
                       grace=economy.CITY_PROPERTY_DEBT_GRACE_DAYS),
        "wages": _lines("wages", 5, wage=constants.LUMBER_WAGE, block=economy.LUMBER_BLOCK_HOURS,
                        premium=economy.MINE_WAGE_PREMIUM, shifts=_hours(economy.LUMBER_SHIFT_HOURS),
                        num=economy.LUMBER_AXE_RATIO[0], den=economy.LUMBER_AXE_RATIO[1],
                        shows=_hours(economy.PERFORM_SHIFT_HOURS), base=economy.PERFORM_TIP_BASE,
                        step=economy.PERFORM_TIP_STEP, pay=economy.SUPPLY_RUN_PAY, kg=int(economy.SUPPLY_RUN_CARGO_KG),
                        chance=_pct(economy.SUPPLY_RUN_AMBUSH_CHANCE)),
        "gathering": _lines("gathering", 3, yard=gather.LICENCE_PRICE["lumber_yard"], mine=gather.LICENCE_PRICE["mine"],
                            rate=gather.HOURS_PER_ROLL, yard_level=gather.LEVEL["lumber_yard"],
                            mine_level=gather.LEVEL["mine"],
                            yard_pct=_pct(AMBUSH_CHANCE_PER_HOUR["lumber_yard"]), mine_pct=_pct(AMBUSH_CHANCE_PER_HOUR["mine"])),
        "levels": _lines("levels", 6, c1=c1, c2=c2, mark=economy.LUMBER_XP_HOURS, own=economy.LUMBER_LEVEL_OWN_AXE,
                         stage=economy.PERFORM_LEVEL, hunt=hunt.HUNT_LEVEL, supply=economy.SUPPLY_RUN_LEVEL,
                         per=progression.RACIAL_XP_THRESHOLDS[0], pick=progression.RACIAL_PICK_EVERY),
        "crafting": _lines("crafting", 3, per=craft_level.LEVEL_PER_POINTS, short=craft_level.HOURS_STEPS[0],
                           long=craft_level.HOURS_STEPS[1], scarce_max=craft_level.SCARCE_POINTS_MAX),
        "market": _lines("market", 3, sell=_pct(economy.SELL_FACTOR), step=_pct(economy.CHA_DEAL_STEP), a0=_pct(deal[0]),
                         a1=_pct(deal[1]), a3=-_pct(deal[3]), a4=-_pct(deal[4]), low=-_pct(economy.DEAL_MIN),
                         high=_pct(economy.DEAL_MAX), share=_pct(economy.SELL_DEAL_SHARE)),
        "shop": _lines("shop", 2, start=economy.MARKET_CASH_START, regen=economy.MARKET_CASH_REGEN,
                       cap=economy.MARKET_CASH_CAP, mine=", ".join(i18n.name("item", n) for n in economy.MINE_SUPPLIES)),
        "missions": _lines("missions", 3),
        "arena": _lines("arena", 4, scrapper_entry=arena.SCRAPPER_ENTRY, scrapper_purse=arena.SCRAPPER_PURSE,
                        scrapper_foes=arena.SCRAPPER_FOES, boss_squad=arena.BOSS_SQUAD,
                        champion_entry=arena.CHAMPION_ENTRY, champion_purse=arena.CHAMPION_PURSE,
                        games_entry=arena.STAGE2_ENTRY, games_purse=arena.STAGE2_PURSE,
                        boss_entry=arena.BOSS_ENTRY, boss_purse=arena.BOSS_PURSE, cycle=arena.CHALLENGE_CYCLE,
                        grace=arena.CHALLENGE_GRACE, defense=arena.DEFENSE_PURSE),
    }

