"""The screens a node's functions open (arena, shops, bank, property, Claim, hubs, Ruins, tavern, prison).

Mixed into `app.App`; the dispatch tables that reach these live there."""

from . import (
    arena,
    battlefield,
    missions,
    node_functions,
    serpent_nest,
    wagon_watch,
    world,
)
from .battle import Battle
from .city_property_screen import CityPropertyScreen, RepossessionScreen
from .constants import fmt_money
from .ledger_screen import LedgerScreen
from .market_screen import MarketScreen
from .squad_screen import SquadScreen
from .tanner_hub_screen import TannerHubScreen
from .taverna_screen import TavernaScreen
from .watch_screen import WatchScreen
from .wilds_claim_screen import WildsClaimScreen


class NodeScreensMixin:
    def _open_arena(self, group, node):
        if arena.defense_due(self.guild):
            self._start_title_defense(node)
            return
        offers = [arena.scrapper_bout()]
        if "arena_dethrone" not in self.guild.deeds_done:
            offers.append(arena.champion_bout())
        else:                                   # champion beaten: the Games are open
            offers += [arena.brawl_bout(), arena.ctf_bout()]
            if "arena_ribbit_brothers" not in self.guild.deeds_done:
                offers.append(arena.boss_bout())
        disabled = {u for u in group.members if u.incapacitated}
        self._arena_purse = group.members
        self.scene = SquadScreen(self.ui_fonts, group.members, node,
                                 on_confirm=self._start_battle, on_back=self._after_activity,
                                 arena_offers=offers, disabled=disabled,
                                 confirm_label="STAKE AND FIGHT")

    def _open_market_stalls(self, shoppers, node, _offer):
        group = next((g for g in self.guild.groups if g.node == node.id), None) or (self.guild.groups[0] if self.guild.groups else None)
        if group is not None and len(node.functions) > 1 and len(node_functions.offered(node)) <= 1:
            from .hub_screen import TabbedHubScreen
            self.scene = TabbedHubScreen.for_node(self.ui_fonts, self.guild, group, node,
                                                  on_done=self._after_activity, first="shop")
        else:
            self.scene = MarketScreen(self.ui_fonts, self.guild, shoppers, node,
                                      on_done=self._after_activity)

    def _open_bank_vault(self, group, node, _offer):
        from .bank_hub_screen import BankHubScreen
        self.scene = BankHubScreen(self.ui_fonts, self.guild, group,
                                   on_done=self._after_activity)

    def _open_city_property(self, group, node):
        """`RepossessionScreen` pre-empts the normal property screen once too
        many tax cycles are missed -- same shape as `_open_arena` checking
        `arena.defense_due` before the normal squad picker."""
        if self.guild.house.repossession_due:
            self.scene = RepossessionScreen(self.ui_fonts, self.guild,
                                            on_return=self._resolve_repossession_return,
                                            on_squat=self._resolve_repossession_squat)
            return
        self.scene = CityPropertyScreen(self.ui_fonts, self.guild, list(group.members),
                                        on_done=self._after_activity,
                                        on_cook=lambda: self._open_kitchen(
                                            group, "THE HOUSE KITCHEN",
                                            lambda: self._open_city_property(group, node)),
                                        on_garage=lambda: self._open_garage(group, node))

    def _open_garage(self, group, node):
        from .garage_screen import GarageScreen
        self.scene = GarageScreen(self.ui_fonts, self.guild, group, on_tick=self._tick_outside_map,
                                  on_done=lambda: self._open_city_property(group, node))

    def _resolve_repossession_return(self):
        self.guild.repossess_city_property()
        self._map_notices.append("The property is returned to the Bankers -- the guild "
                                 f"now owes {fmt_money(self.guild.bankers_debt)}.")
        self._after_activity()

    def _resolve_repossession_squat(self):
        self.guild.house.squat()
        self._map_notices.append("The guild keeps the house without paying -- the guard "
                                 "won't like that.")
        self._after_activity()

    # ------------------------------------------------------------------ #
    # the Wilds claim (the `claim` node function, wilds_claim_screen.py)           #
    # ------------------------------------------------------------------ #
    def _open_kitchen(self, group, title, on_back):
        from .crafting_screen import CraftingScreen
        self.scene = CraftingScreen(self.ui_fonts, self.guild, group, on_done=on_back,
                                    title=title, station="cooking",
                                    subtitle="cook what the pack carries  ·  everyone knows the basics")

    def _open_wilds_claim(self, group, node):
        self.scene = WildsClaimScreen(self.ui_fonts, self.guild, group,
                                      on_done=self._after_activity,
                                      on_cook=lambda: self._open_kitchen(
                                          group, "THE CLAIM KITCHEN",
                                          lambda: self._open_wilds_claim(group, node)),
                                      on_garage=lambda: self._open_claim_garage(group, node),
                                      on_fight_clear=self._start_claim_clear_battle,
                                      on_fight_sweep=self._start_claim_sweep_battle)

    def _open_claim_garage(self, group, node):
        from .garage_screen import GarageScreen
        self.scene = GarageScreen(self.ui_fonts, self.guild, group, claim=True, on_tick=self._tick_outside_map,
                                  on_done=lambda: self._open_wilds_claim(group, node))

    def _open_tanner_stall(self, group, node, _offer):
        self.scene = TannerHubScreen(self.ui_fonts, self.guild, group, node,
                                     on_done=self._after_activity)

    def _open_trust_offer(self, group, node, _offer):
        from .trust_screen import TrustScreen
        self.scene = TrustScreen(self.ui_fonts, self.guild, group,
                                 on_done=self._after_activity)

    def _open_ledger_desk(self, group, node, _offer):
        self.scene = LedgerScreen(self.ui_fonts, self.guild, group,
                                 on_done=self._after_activity)

    def _open_forge(self, group, node, _offer):
        from .forge_hub_screen import ForgeHubScreen
        self.scene = ForgeHubScreen(self.ui_fonts, self.guild, group, node,
                                    on_done=self._after_activity)

    def _open_apothecary(self, group, node, _offer):
        from .apothecary_hub_screen import ApothecaryHubScreen
        self.scene = ApothecaryHubScreen(self.ui_fonts, self.guild, group,
                                         on_done=self._after_activity, node=node)

    def _open_stables(self, group):
        node = world.node(group.node) if group.node else None
        if node is not None and node.has("shop"):
            from .hub_screen import TabbedHubScreen
            self.scene = TabbedHubScreen.for_node(self.ui_fonts, self.guild, group, node,
                                                  on_done=self._after_activity, first="stable")
        else:
            from .stables_screen import StablesScreen
            self.scene = StablesScreen(self.ui_fonts, self.guild, group, on_done=self._after_activity)

    def _open_library(self, group, node, _offer):
        from .library_hub_screen import LibraryHubScreen
        self.scene = LibraryHubScreen(self.ui_fonts, self.guild, group, node,
                                      on_done=self._after_activity)

    def _open_shrine(self, group, node):
        from .hub_screen import TabbedHubScreen
        self.scene = TabbedHubScreen.for_node(self.ui_fonts, self.guild, group, node,
                                              on_done=self._after_activity)

    def _enter_ancient_ruins(self, group, node):
        if wagon_watch.needs_watch(group):
            self.scene = WatchScreen(self.ui_fonts, group, node, "ENTER THE RUINS",
                                     on_confirm=lambda party, guarded: self._delve(group, node, party, guarded),
                                     on_back=self._after_activity)
        else:
            self._delve(group, node, list(group.members), True)

    def _delve(self, group, node, squad, guarded):
        from .scenario import AncientRuinsScenario
        self._leave_outside(group, node, guarded)
        scenario = AncientRuinsScenario()
        battle = Battle(squad, scenario.enemies, scenario=scenario,
                        daylight=False, lethal=True, clock_day=self.guild.clock.day, aggressor="player")
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = None
        self._enter_battle(battle, node)

    def _enter_nest(self, group, node):
        if wagon_watch.needs_watch(group):
            self.scene = WatchScreen(self.ui_fonts, group, node, "ENTER THE NEST",
                                     on_confirm=lambda party, guarded: self._delve_nest(group, node, party, guarded),
                                     on_back=self._after_activity)
        else:
            self._delve_nest(group, node, list(group.members), True)

    def _delve_nest(self, group, node, squad, guarded):
        self._leave_outside(group, node, guarded)
        level = max(1, round(sum(u.mean_level for u in squad) / len(squad)))
        scenario = serpent_nest.NestScenario(level, dragon=serpent_nest.dragon_home(self.guild))
        battle = Battle(squad, scenario.enemies, scenario=scenario,
                        daylight=False, lethal=True, clock_day=self.guild.clock.day, aggressor="player")
        dragon = serpent_nest.dragon_of(battle)
        if dragon is not None and missions.snake_wanted_alive(self.guild):
            battle.wanted_alive.add(dragon)
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = None
        self._enter_battle(battle, node)

    def _enter_skirmish(self, group, node):
        if missions.pending_battlefield(self.guild, group) is None:
            self._after_activity()
            return
        if wagon_watch.needs_watch(group):
            self.scene = WatchScreen(self.ui_fonts, group, node, "JOIN THE SKIRMISH",
                                     on_confirm=lambda party, guarded: self._skirmish_fight(group, node, party, guarded),
                                     on_back=self._after_activity)
        else:
            self._skirmish_fight(group, node, list(group.members), True)

    def _skirmish_fight(self, group, node, squad, guarded):
        self._leave_outside(group, node, guarded)
        scenario = battlefield.BattlefieldScenario(squad)
        battle = Battle(squad, scenario.enemies, scenario=scenario, allies=scenario.allies,
                        daylight=self.guild.clock.is_daylight, lethal=True,
                        clock_day=self.guild.clock.day, aggressor="enemy")
        self._skirmish = missions.pending_battlefield(self.guild, group)
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = None
        self._enter_battle(battle, node)

    def _visit_tavern(self, group):
        self._pending = []
        self._open_taverna(list(group.members), world.node(group.node), None, group=group)

    def _visit_claim(self, group):
        node = world.node(group.node)
        if not node.has("claim"):
            return
        self._pending = []
        self._open_wilds_claim(group, node)

    def _open_taverna(self, party, node, _offer, group=None):
        grp = group or (self.guild.groups[0] if self.guild.groups else None)
        if grp is not None and node is not None and node.has("shop"):
            from .hub_screen import TabbedHubScreen
            self.scene = TabbedHubScreen.for_node(self.ui_fonts, self.guild, grp, node,
                                                  on_done=self._after_activity, first="tavern")
        else:
            self.scene = TavernaScreen(self.ui_fonts, self.guild, party, node,
                                       on_done=self._after_activity, group=group)

    def _open_prison(self, party, node, _offer):
        from .prison_screen import PrisonScreen
        self.scene = PrisonScreen(self.ui_fonts, self.guild, party, node,
                                  on_done=self._after_activity)
