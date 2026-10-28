"""A node's screens behind one row of tabs, in the browser: the keeper's strip, the tabs, the way back
to the map. The shop is the first tab (`shop_tab.ShopTab`), a work node adds its shifts and gathering
(`work_tab`), the Apothecary its Medic (`medic_tab`), a giver its jobs board (`jobs_tab`), a workbench its
recipes (`craft_tab`), the Farm its stables and the Carpenter its wagon yard (`stable_tab`), the Tavern its
recruits, study rooms and stage (`tavern_tab`), the City Prison its cells (`tavern_tab` with a bail), a
sanctuary its initiation (`initiation_tab`), the Bank its strongbox (`vault_tab`) beside the Bankers' jobs, the
City house its stash (`vault_tab` again), its kitchen (`craft_tab`) and its garage (`garage_tab`), the Wilds
Claim its stages (`claim_tab`) with the same kitchen and garage, Ledger Hold its desk (`ledger_tab`), and a
band's campfire in the field the same kitchen; a tab the browser does not draw yet says so
inside the frame, and its screen is played in pygame until its part of step 9 of `docs/plans/web_frontend.md`
lands.

The tabs follow the hub pygame opens for the same order (`app_nodes`, `hub_screen.TabbedHubScreen`).
"""

from typing import ClassVar

from .. import artwork, economy, orders, solo, world
from ..bank_screen import BankScreen
from ..city_property_screen import CityPropertyScreen
from ..constants import fmt_money
from ..crafting_screen import ALONE_HOURS, WAIT_HOURS
from ..hub_screen import TabbedHubScreen
from ..map_screen import node_icon
from ..work_screen import SHIFTS
from .claim_tab import ClaimTab
from .craft_tab import CRAFT_TABS, CraftTab
from .garage_tab import GarageTab
from .initiation_tab import InitiationTab
from .jobs_tab import JobsTab
from .ledger_tab import LedgerTab
from .medic_tab import MedicTab
from .session import Session, asset_url
from .shop_tab import ShopTab
from .stable_tab import StableTab, WagonTab
from .tavern_tab import TABS as TAVERN_TABS
from .tavern_tab import TavernTab
from .vault_tab import VaultTab
from .work_tab import GatherTab, WorkTab

# order kind -> its hub's tabs, where it is not the node's own list (`_node_tabs`)
HUBS = {
    "forge": (("shop", "Shop"), ("craft", "Forge")),
    "tanner": (("shop", "Shop"), ("jobs", "Jobs")),
    "apothecary": (("shop", "Shop"), ("medic", "Medic"), ("craft", "Craft"), ("jobs", "Jobs")),
    "library": (("shop", "Shop"), ("craft", "Write"), ("jobs", "Jobs")),
    "prison": (("prison", "The Cells"),),
    "bank": (("vault", "Vault"), ("jobs", "Jobs")),
    "ledger": (("ledger", "The Desk"),),
    "campfire": (("kitchen", "Campfire"),),
}
HUB_KINDS = {"market", "carpenter", "stable", "shrine", "recruit", "property", "claim", *HUBS}
# the tabs the browser draws so far
LIVE = {"shop", "work", "gather", "medic", "jobs", "stable", "wagons", "initiation", "prison", "vault", "property",
        "garage", "claim", "ledger", *CRAFT_TABS, *TAVERN_TABS}
# what a tab not drawn yet is, for its note
WHAT = {"tavern": "the tavern"}


def _node_tabs(node):
    """The tabs `TabbedHubScreen.for_node` builds for `node`, in its order."""
    tabs = []
    if node.has("shop"):
        tabs.append(("shop", "Food & Drink" if node.id == "tavern" else "Farm" if node.id == "farm" else "Shop"))
    if node.has("recruit"):
        tabs += ((("recruits", "Recruit"), ("rooms", "Study"), ("perform", "Perform")) if node.id == "tavern"
                 else (("tavern", "Tavern"),))
    if node.has("stable"):
        tabs.append(("stable", "Stables"))
    if node.has("forge"):
        tabs.append(("forge", "Forge"))
    if node.has("carpenter"):
        tabs += (("carpenter", "Carpentry"), ("wagons", "Wagons"))
    if node.has("tanner"):
        tabs.append(("jobs", "Jobs"))
    if node.has("apothecary"):
        tabs += (("medic", "Medic"), ("jobs", "Jobs"))
    if node.has("library"):
        tabs.append(("jobs", "Jobs"))       # pygame's STUDY repeats the Library's shop, which the shop tab already is
    if node.has("shrine"):
        tabs += (("jobs", "Jobs"), ("initiation", "Initiation"))
    if node.has("work"):
        tabs.append(("work", "Work"))
        from .. import gather
        if gather.can_gather(node.id):
            tabs.append(("gather", "Gathering"))
    return tabs or [("shop", "Shop")]


def _house_tabs(guild):
    """The City house's tabs, as `CityPropertyScreen` offers them: the kitchen once it has an oven, the
    garage once it is owned."""
    house = guild.house
    return [("property", "The House"), *((("kitchen", "Kitchen"),) if house.owned and house.oven else ()),
            *((("garage", "Garage"),) if house.owned else ())]


def _claim_tabs(guild):
    """The Wilds Claim's tabs, as `WildsClaimScreen` offers them: the kitchen once the hearth can cook, the
    garage once the garrison opens it."""
    return [("claim", "The Claim"), *((("kitchen", "Kitchen"),) if guild.wilds_claim_can_cook else ()),
            *((("garage", "Garage"),) if guild.claim_garage_open else ())]


DYNAMIC = {"property": _house_tabs, "claim": _claim_tabs}


def tabs_for(kind, node):
    return list(HUBS.get(kind) or _node_tabs(node))


def opens_hub(order, node):
    """True when the browser plays `order` at `node` in a hub (the Farm's stables only beside its shop,
    as `App._open_stables` does)."""
    return order.kind in HUB_KINDS and (order.kind != "stable" or node.has("shop"))


def _shop(verb):
    """A shop verb: it acts on the shop tab and answers the whole hub."""
    def run(s, b):
        verb(s.shop, b)
        return s.state()
    return run


def _on_vault(verb):
    """A stash verb: it acts on the strongbox or the house and answers the whole hub."""
    def run(s, b):
        verb(s.vault, b)
        s.tab = s.stash_key
        return s.state()
    return run


class HubSession(Session):
    screen = "hub"
    GET: ClassVar[dict] = {"state": lambda s, q: s.state()}
    POST: ClassVar[dict] = {
        "tab": lambda s, b: s.pick_tab(b["key"]),
        "back": lambda s, b: s.map.back(),
        "buy": _shop(lambda t, b: t.buy(b["name"], b.get("qty", 1), b.get("to"), b.get("zone", "pack"))),
        "move": _shop(lambda t, b: t.move(b["picks"], b["to"], b.get("zone", "pack"))),
        "sell": _shop(lambda t, b: t.sell(b["picks"])),
        "lock": _shop(lambda t, b: t.lock(b["owner"], b["name"])),
        "mark": _shop(lambda t, b: t.mark(b["name"])),
        "sell_marked": _shop(lambda t, b: t.sell_marked()),
        "distribute": _shop(lambda t, b: t.distribute()),
        "work": lambda s, b: s.work(int(b["hours"])),
        "gather": lambda s, b: s.gather(int(b["hours"])),
        "licence": lambda s, b: s.licence(),
        "patient": lambda s, b: s.patient(b["uid"]),
        "treat": lambda s, b: s.treat(),
        "accept": lambda s, b: s.on_board(JobsTab.accept, b["id"]),
        "turn_in": lambda s, b: s.on_board(JobsTab.turn_in, b["id"]),
        "sell_egg": lambda s, b: s.on_board(JobsTab.sell_egg),
        "crafter": lambda s, b: s.crafter(b["uid"]),
        "craft": lambda s, b: s.craft(b["recipe"], int(b["hours"]), bool(b.get("alone"))),
        "buy_animal": lambda s, b: s.on_yard("stable", StableTab.buy, b["species"]),
        "fit": lambda s, b: s.on_yard("stable", StableTab.fit, b["uid"], b["tack"]),
        "sell_animal": lambda s, b: s.on_yard("stable", StableTab.sell, b["uid"]),
        "buy_wagon": lambda s, b: s.on_yard("wagons", WagonTab.buy, b["kind"]),
        "sell_wagon": lambda s, b: s.on_yard("wagons", WagonTab.sell, b["uid"]),
        "candidate": lambda s, b: s.on_tavern("recruits", TavernTab.candidate, b["uid"]),
        "recruiter": lambda s, b: s.on_tavern("recruits", TavernTab.recruiter, b["uid"]),
        "convince": lambda s, b: s.on_tavern("recruits", TavernTab.convince),
        "study_target": lambda s, b: s.on_tavern("rooms", TavernTab.set_target, b["uid"], b["id"]),
        "stop_study": lambda s, b: s.on_tavern("rooms", TavernTab.stop_study, b["uid"]),
        "rent_study": lambda s, b: s.on_tavern("rooms", TavernTab.rent),
        "cancel_study": lambda s, b: s.on_tavern("rooms", TavernTab.cancel),
        "show_hours": lambda s, b: s.on_tavern("perform", TavernTab.hours, int(b["hours"])),
        "seat": lambda s, b: s.on_tavern("perform", TavernTab.seat, b["uid"]),
        "perform": lambda s, b: s.perform(),
        "novice": lambda s, b: s.novice(b["uid"]),
        "begin_rite": lambda s, b: s.begin_rite(),
        "vault_move": _on_vault(lambda t, b: t.move(b["picks"], b["to"], b.get("zone", "pack"))),
        "vault_service": _on_vault(lambda t, b: t.service(b["key"])),
        "vault_gold": _on_vault(lambda t, b: t.exchange(b["from"], b["n"], bool(b.get("melt")))),
        "vault_distribute": _on_vault(lambda t, b: t.distribute()),
        "garage_bay": lambda s, b: s.on_garage(GarageTab.bay),
        "garage_park": lambda s, b: s.on_garage(GarageTab.park, b["uid"]),
        "garage_take": lambda s, b: s.on_garage(GarageTab.take, b["uid"]),
        "garage_repair": lambda s, b: s.on_garage(GarageTab.repair, b["uid"]),
        "repossess": lambda s, b: s.repossess(b["choice"]),
        "claim": lambda s, b: s.claim_work(b["verb"]),
        "claim_garrison": lambda s, b: s.claim_garrison(),
        "claim_fight": lambda s, b: s.claim_fight(b["verb"]),
        "ledger": lambda s, b: s.ledger_act(b["key"]),
    }

    keeper = TabbedHubScreen.keeper         # reads `node` and `tab`

    def __init__(self, map_session, group, order):
        self.map = map_session
        self.guild = map_session.guild
        self.group = group
        self.order = order
        self.node = world.node(group.node)
        self._tabs = tabs_for(order.kind, self.node)
        first = "shop" if order.kind in ("market", "stable") else {"forge": "craft", "recruit": "recruits", "bank": "vault"}.get(order.kind, order.kind)
        self.tab = first if any(k == first for k, _ in self.tabs) else self.tabs[0][0]
        self._shop = None
        self._work = None
        self._gather = None
        self._medic = None
        self._jobs = None
        self._craft = None
        self._stable = None
        self._wagons = None
        self._tavern = None
        self._rite = None
        self._vault = None
        self._garage = None
        self._claim = None
        self._ledger = None

    @property
    def tabs(self):
        tabs = DYNAMIC.get(self.order.kind)
        return tabs(self.guild) if tabs else self._tabs

    @property
    def repossession_due(self):
        return self.order.kind == "property" and self.guild.house.repossession_due

    def _open(self):
        if self.repossession_due:
            raise ValueError("the Bankers want an answer about the house first")

    @property
    def shop(self):
        if not any(k == "shop" for k, _ in self.tabs):
            raise ValueError("this place has no shop")
        if self._shop is None:
            self._shop = ShopTab(self.guild, self.group, self.node)
        return self._shop

    def _tab(self, key, attr, make):
        self._open()
        if not any(k == key for k, _ in self.tabs):
            raise ValueError(f"no {key} tab here")
        if getattr(self, attr) is None:
            setattr(self, attr, make(self.guild, self.group, self.node))
        return getattr(self, attr)

    @property
    def working(self):
        return self._tab("work", "_work", WorkTab)

    @property
    def gathering(self):
        return self._tab("gather", "_gather", GatherTab)

    @property
    def ward(self):
        return self._tab("medic", "_medic", MedicTab)

    @property
    def board(self):
        return self._tab("jobs", "_jobs", JobsTab)

    @property
    def stables(self):
        return self._tab("stable", "_stable", StableTab)

    @property
    def yard(self):
        return self._tab("wagons", "_wagons", WagonTab)

    def on_yard(self, key, verb, *args):
        verb(self.stables if key == "stable" else self.yard, *args)
        if self._shop is not None:
            self._shop.m.sync_group()       # the animals and wagons shop as packs
        self.tab = key
        return self.state()

    @property
    def tavern(self):
        prison = any(k == "prison" for k, _ in self.tabs)
        if not prison and not any(k in TAVERN_TABS for k, _ in self.tabs):
            raise ValueError("no tavern here")
        if self._tavern is None:
            self._tavern = TavernTab(self.guild, self.group, self.node, prison=prison)
        return self._tavern

    def on_tavern(self, key, verb, *args):
        verb(self.tavern, *args)
        if self._shop is not None:
            self._shop.m.sync_group()       # a recruit shops beside the band
        self.map._save()
        self.tab = "prison" if self.tavern.prison else key
        return self.state()

    def perform(self):
        """A show on the stage: the clock passes its hours here, as pygame's does, and the tab stays up
        with what the crowd tipped; a death that empties the band lands on the map."""
        self.tavern.perform()
        m = self.map
        if m.wiped or not self.group.members:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "perform"
        return self.state()

    @property
    def stash_key(self):
        return "property" if self.order.kind == "property" else "vault"

    @property
    def vault(self):
        screen = CityPropertyScreen if self.order.kind == "property" else BankScreen
        return self._tab(self.stash_key, "_vault", lambda g, grp, n: VaultTab(g, grp, n, screen))

    @property
    def garage(self):
        return self._tab("garage", "_garage", lambda g, grp, n: GarageTab(g, grp, n, tick=self._tick,
                                                                       claim=self.order.kind == "claim"))

    def _tick(self, hours, busy=()):
        return self.map.tick_outside(hours, busy)

    def on_garage(self, verb, *args):
        verb(self.garage, *args)
        m = self.map
        if m.wiped or not self.group.members:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "garage"
        return self.state()

    def repossess(self, choice):
        """The Bankers' notice once too many tax cycles went unpaid: hand the house back and owe them, or
        squat in it; either way back to the map, as pygame's `RepossessionScreen` does."""
        g, m = self.guild, self.map
        if not self.repossession_due:
            raise ValueError("the Bankers want nothing of the house now")
        if choice == "return":
            g.repossess_city_property()
            m.notices.append(f"The property is returned to the Bankers -- the guild now owes {fmt_money(g.bankers_debt)}.")
        elif choice == "squat":
            g.house.squat()
            m.notices.append("The guild keeps the house without paying -- the guard won't like that.")
        else:
            raise ValueError(f"no such answer: {choice}")
        return m.back()

    @property
    def claim(self):
        return self._tab("claim", "_claim", ClaimTab)

    def claim_work(self, verb):
        """A piece of the claim's work done here: scouting, the fences and the hearth pass their hours as
        pygame's do, and the tab stays up with what came of it; a death that empties the band lands on the map."""
        self.claim.act(verb)
        m = self.map
        if m.wiped or not self.group.members:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "claim"
        return self.state()

    def claim_garrison(self):
        """Leave the band holding the claim: a garrison order, so it goes back to the map, where the clock runs."""
        self.claim.start_garrison()
        m = self.map
        m.game.open(m)
        return m._after_order()

    def claim_fight(self, verb):
        """The claim's two fights (CLEAR, SWEEP) are campaign fights: the away card says so until step 10."""
        title = self.claim.fight(verb)
        return self.map._away(self.group, None, fight=True, title=title, what="the claim's fight")

    @property
    def desk(self):
        return self._tab("ledger", "_ledger", LedgerTab)

    def ledger_act(self, key):
        """A button on Ledger Hold's desk: the supply run sends the band off on its order, back to the map where
        the clock runs; the rest is done here and the tab stays up."""
        self.desk.act(key)
        m = self.map
        if self.group.busy:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "ledger"
        return self.state()

    @property
    def rite(self):
        return self._tab("initiation", "_rite", InitiationTab)

    def novice(self, uid):
        self.rite.pick(uid)
        self.tab = "initiation"
        return self.state()

    def begin_rite(self):
        """Leave the picked one boarding for the rite. Split off into a group of their own, the tab
        stays up; a band that boards whole (a lone member, or no free group slot) goes back to the map,
        where the clock runs."""
        if not self.rite.begin():
            return self.state()
        m = self.map
        if self.group.busy:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "initiation"
        return self.state()

    @property
    def bench(self):
        self._open()
        key = next((k for k, _ in self.tabs if k in CRAFT_TABS), None)
        if key is None:
            raise ValueError("no workbench here")
        if self._craft is None:
            self._craft = CraftTab(self.guild, self.group, self.node, key)
        return self._craft

    def crafter(self, uid):
        self.bench.pick(uid)
        self.tab = self.bench.key
        return self.state()

    def craft(self, recipe, hours, alone):
        """Put `hours` into `recipe`. With the group waiting the stint is rolled now and the clock passes
        here, as pygame's does; alone, the crafter splits off on a solo task and the band goes back to the
        map, where the clock runs."""
        tab = self.bench
        recipe = tab.recipe(recipe)
        m = self.map
        if alone:
            if hours not in ALONE_HOURS:
                raise ValueError(f"no {hours} h stint alone")
            ok, lines = solo.craft(self.guild, self.group, tab.crafter, recipe, hours)
            if not ok:
                tab.notice = lines[0]
                return self.state()
            m.notices += lines
            m.game.open(m)
            return m._after_order()
        if hours not in WAIT_HOURS:
            raise ValueError(f"no {hours} h stint")
        lines, _ = self.guild.crafting_shift(tab.crafter, recipe, hours, pool=tab.s._packs)
        tab.report = lines
        if m.wiped or not self.group.members:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = tab.key
        return self.state()

    def on_board(self, verb, *args):
        verb(self.board, *args)
        self.map._save()
        self.tab = "jobs"
        return self.state()

    def _shift(self, hours, **kw):
        if hours not in SHIFTS:
            raise ValueError(f"no {hours} h shift")
        if self.group.busy:
            raise ValueError(f"{self.group.display_name} is busy")
        self.group.order = orders.work(self.guild, self.group, hours, **kw)
        self.map.focus = self.group.gid

    def work(self, hours):
        """A paid shift, as `App._work_shift` runs it: the clock runs as the map's would, and the tab
        stays up with what the shift paid when its end is all that stopped it. Anything else (another
        band idle, a screen or a fight due, a death) lands on the map, the shift still running there."""
        tab = self.working
        self._shift(hours)
        m = self.map
        if self.guild.needs_orders:
            return m.back()
        before = len(m.notices)
        idle, dead = m._advance()
        if m.wiped or self.group.busy or m.pending or dead or idle - {self.group.gid}:
            return m.back()
        tab.report = m.notices[before:]
        del m.notices[before:]
        m._save()
        self.tab = "work"
        return self.state()

    def licence(self):
        self.gathering.buy_licence()
        self.tab = "gather"
        return self.state()

    def gather(self, hours):
        """A gathering shift: the band goes back to the map and the clock runs there, as pygame's does."""
        self._tab("gather", "_gather", GatherTab)
        self._shift(hours, gather=True)
        self.map.game.open(self.map)
        return self.map._after_order()

    def patient(self, uid):
        self.ward.pick(uid)
        self.tab = "medic"
        return self.state()

    def treat(self):
        """Treat the picked patients (the clock passes their hours here, as pygame's does) or admit the
        one picked for a stay. A stay the whole band waits out is an order: the band goes back to the
        map and the clock runs there."""
        if not self.ward.treat():
            return self.state()
        m = self.map
        if m.wiped or not self.group.members or self.group.busy:
            m.game.open(m)
            return m._after_order()
        m._save()
        self.tab = "medic"
        return self.state()

    def pick_tab(self, key):
        if not any(k == key for k, _ in self.tabs):
            raise ValueError(f"no {key} tab here")
        self.tab = key
        return self.state()

    def state(self):
        c, n = self.guild.clock, self.node
        k = {} if self.order.kind == "campfire" else self.keeper()      # the band's own fire keeps no shop
        part = "night" if not c.is_daylight else "morning" if c.hour_of_day < 12 else "afternoon" if c.hour_of_day < 15 else "evening"
        keeper = {"name": k.get("name"), "caption": k.get("caption", ""), "bent": k.get("bent", ""),
                  "line": k.get("line", ""),
                  "portrait": asset_url(artwork.portrait_path(None, k["portrait"])) if k.get("portrait") else None}
        lang = getattr(n, "language", None)
        if isinstance(lang, (list, tuple)):
            lang = " or ".join(lang)
        tongue = f" · the traders speak {lang}" if lang else ""
        out = {"place": n.name, "sub": f"Day {c.day}, {part}{tongue}", "band": self.group.display_name,
               "icon": "/".join(node_icon(n.id) or ("map", "signpost")), "keeper": keeper,
               "tabs": [] if self.repossession_due else
                       [{"key": key, "label": label, "live": key in LIVE} for key, label in self.tabs],
               "tab": self.tab}
        if self.repossession_due:
            missed = self.guild.house.missed_payments
            out["repossession"] = {"missed": missed, "owed": missed * economy.CITY_PROPERTY_TAX}
        elif self.tab == "shop":
            out["shop"] = self.shop.state()
        elif self.tab == "work":
            out["work"] = self.working.state()
        elif self.tab == "gather":
            out["gather"] = self.gathering.state()
        elif self.tab == "medic":
            out["medic"] = self.ward.state()
        elif self.tab == "jobs":
            out["jobs"] = self.board.state()
        elif self.tab in CRAFT_TABS:
            out["craft"] = self.bench.state()
        elif self.tab == "stable":
            out["stable"] = self.stables.state()
        elif self.tab == "wagons":
            out["wagons"] = self.yard.state()
        elif self.tab in TAVERN_TABS:
            out["tavern"] = self.tavern.state(self.tab)
        elif self.tab == "prison":
            out["tavern"] = self.tavern.state("recruits")
        elif self.tab == "initiation":
            out["initiation"] = self.rite.state()
        elif self.tab == self.stash_key:
            out["vault"] = self.vault.state()
        elif self.tab == "garage":
            out["garage"] = self.garage.state()
        elif self.tab == "claim":
            out["claim"] = self.claim.state()
        elif self.tab == "ledger":
            out["ledger"] = self.desk.state()
        else:
            label = next(lbl for key, lbl in self.tabs if key == self.tab)
            out["away"] = {"title": label, "line": (f"{WHAT.get(self.tab, label).capitalize()} at {n.name} is played "
                                                    "in pygame for now: the hub's other tabs follow the shop in "
                                                    "step 9.")}
        return out
