"""GARTOK Tactical shell: window, main loop and screen switching.

The screens do the work: `MenuScreen` (save slots), `DraftScreen` (building the
starting guild), `MapScreen` (the hub -- drive the guild between places),
`GuildScreen` (roster + gear), `SquadScreen` (who fights), `BattleScreen` (the
fight) and `LootScreen` (split the spoils). Each exposes `handle_event`,
`update(dt)`, `draw(surface)` and reads `self.mouse` (canvas-space cursor).

Campaign loop: menu -> draft -> MAP <-> guild
                                    |-> squad   -> battle -> loot -> MAP
                                    |-> party   -> market -> MAP
                                    |-> party   -> taverna (recruit) -> MAP
                                    |-> workers -> lumber yard (work_shift) -> MAP
The guild roams the world map as one token (`guild.node`); travelling advances
the campaign clock, opening the guild/squad screens does not. `persist` autosaves
after the draft, on every return to the map and after every battle. Permadeath: a
member who does not survive is dropped; a full wipe ends the campaign.

Every scene is `native`: it draws straight to the real (resizable) window and
lays itself out from `screen.get_size()`. `WIN_W x WIN_H` (theme.py) is just the
opening window size and the battle screen's fixed board canvas.
"""

import pygame

from . import campaign, persist, world
from .battle import Battle
from .battle_screen import BattleScreen
from .draft_screen import DraftScreen
from .gear_screen import GearScreen
from .guild import Guild
from .guild_screen import GuildScreen
from .level_screen import LevelScreen
from .loot_screen import LootScreen
from .map_screen import MapScreen
from .market_screen import MarketScreen
from .menu_screen import MenuScreen
from .pause_screen import PauseScreen
from .reward_screen import RewardScreen
from .squad_screen import SquadScreen
from .taverna_screen import TavernaScreen
from .theme import BG, Fonts, WIN_H, WIN_W
from .unit import Unit
from .work_screen import WorkScreen


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("GARTOK Tactical")
        self.window = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()

        self.slot = None
        self.guild = None
        self._battle_squad = []              # roster units sent to the current battle
        self._battle_node = None             # world node the current battle is at
        self._arena_offer = None             # arena stake tier for the current bout, or None
        self._start_menu()

    # ------------------------------------------------------------------ #
    # campaign flow                                                      #
    # ------------------------------------------------------------------ #
    def _start_menu(self):
        self.scene = MenuScreen(self.fonts, on_new=self._new_game,
                                on_continue=self._continue_game,
                                on_delete=persist.delete_slot)

    def _new_game(self, slot):
        self.slot = slot
        self.guild = None
        self.scene = DraftScreen(self.fonts, on_done=self._draft_done)

    def _draft_done(self, picks):
        self.guild = Guild(picks, node=world.START_NODE)
        self._start_map()

    def _continue_game(self, slot):
        self.slot = slot
        self.guild = persist.load_game(slot)
        if self.guild.node not in {n.id for n in world.NODES}:
            self.guild.node = world.START_NODE
        self._start_map()

    def _save(self):
        persist.save_game(self.slot, self.guild)

    def _start_map(self):
        self._save()
        self.scene = MapScreen(self.fonts, self.guild,
                               on_battle=self._open_squad,
                               on_market=self._open_market,
                               on_recruit=self._open_recruit,
                               on_work=self._open_work,
                               on_guild=self._open_guild,
                               on_wipe=self._campaign_over)

    def _campaign_over(self):
        """Roster gone (a wipe, or the last member starved on the road)."""
        persist.delete_slot(self.slot)
        self._start_menu()

    def _open_guild(self):
        self.scene = GuildScreen(self.fonts, self.guild,
                                 on_back=self._start_map, on_level=self._open_level,
                                 on_manage=self._open_gear)

    def _open_gear(self):
        self.scene = GearScreen(self.fonts, self.guild, on_back=self._open_guild)

    def _open_level(self, unit):
        self.scene = LevelScreen(self.fonts, unit,
                                 on_back=self._open_guild, on_change=self._save)

    def _open_squad(self, node):
        offers = world.arena_offers(self.guild.arena_reputation) if node.arena else None
        disabled = {u for u in self.guild.roster if u.incapacitated}
        self.scene = SquadScreen(self.fonts, self.guild.roster, node,
                                 on_confirm=self._start_battle, on_back=self._start_map,
                                 arena_offers=offers, disabled=disabled,
                                 confirm_label="STAKE AND FIGHT" if node.arena else "CONFIRM")

    def _open_market(self, node):
        roster = self.guild.roster
        self.scene = SquadScreen(self.fonts, roster, node,
                                 on_confirm=self._open_market_stalls, on_back=self._start_map,
                                 max_pick=len(roster), title="WHO GOES TO THE MARKET",
                                 confirm_label="GO SHOPPING")

    def _open_market_stalls(self, shoppers, node, _offer):
        self.scene = MarketScreen(self.fonts, self.guild, shoppers, node,
                                  on_done=self._start_map)

    def _open_work(self, node):
        roster = self.guild.roster
        self.scene = SquadScreen(self.fonts, roster, node,
                                 on_confirm=self._open_lumber_yard, on_back=self._start_map,
                                 max_pick=len(roster), title="WHO GOES TO WORK",
                                 confirm_label="GO TO THE LUMBER YARD")

    def _open_lumber_yard(self, workers, node, _offer):
        self.scene = WorkScreen(self.fonts, self.guild, workers,
                                on_done=self._after_work, on_back=self._start_map)

    def _after_work(self):
        if self.guild.empty:
            self._campaign_over()
        else:
            self._start_map()

    def _open_recruit(self, node):
        roster = self.guild.roster
        self.scene = SquadScreen(self.fonts, roster, node,
                                 on_confirm=self._open_taverna, on_back=self._start_map,
                                 max_pick=len(roster), title="WHO GOES TO THE TAVERN",
                                 confirm_label="GO TO THE TAVERN")

    def _open_taverna(self, party, node, _offer):
        self.scene = TavernaScreen(self.fonts, self.guild, party, node,
                                   on_done=self._start_map)

    @staticmethod
    def _charge(members, amount):
        """Take `amount` copper off the party, richest first."""
        left = amount
        for m in sorted(members, key=lambda u: u.gold, reverse=True):
            paid = min(m.gold, left)
            m.gold -= paid
            left -= paid
            if left <= 0:
                break

    def _start_battle(self, squad, node, offer=None):
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = offer
        if offer:
            self._charge(squad, offer["entry"] * len(squad))
            enemy_count = offer["enemies"]
        else:
            enemy_count = len(squad)
        enemies = [Unit("enemy") for _ in range(enemy_count)]
        battle = Battle(squad, enemies, scenario=node.scenario(),
                        daylight=self.guild.clock.is_daylight, lethal=node.lethal)
        self.scene = BattleScreen(self.fonts, battle, on_battle_end=self._battle_end)

    def _battle_end(self, battle):
        outcome = campaign.absorb_battle(self.guild, self._battle_squad, battle,
                                         node=self._battle_node,
                                         arena_offer=self._arena_offer)
        self._battle_squad = []
        self._battle_node = None
        self._arena_offer = None

        if outcome.campaign_over:             # full wipe: campaign over
            self._campaign_over()
            return

        if outcome.arena_reward is not None:  # arena bout won: hand out the purse
            self._save()
            self.scene = RewardScreen(self.fonts, self.guild, outcome.survivors,
                                      outcome.arena_reward, on_done=self._start_map,
                                      deeds=outcome.deeds_earned)
            return

        if outcome.loot_pool and outcome.survivors:
            self._save()
            self.scene = LootScreen(self.fonts, self.guild, outcome.survivors,
                                    outcome.loot_pool, on_done=self._start_map)
            return
        self._start_map()

    # ------------------------------------------------------------------ #
    def _toggle_pause(self):
        """Esc: into / out of the pause menu. On the main menu Esc quits; there
        is no in-game quick exit -- leaving is a deliberate step from the menu."""
        if isinstance(self.scene, PauseScreen):
            self._resume_from_pause()
        elif isinstance(self.scene, MenuScreen):
            self._running = False
        else:
            self.scene = PauseScreen(self.fonts, self.scene,
                                     on_resume=self._resume_from_pause,
                                     on_menu=self._pause_to_menu,
                                     on_quit=self._quit)

    def _resume_from_pause(self):
        if isinstance(self.scene, PauseScreen):
            self.scene = self.scene.resume_to

    def _pause_to_menu(self):
        if self.guild is not None:
            self._save()
        self._start_menu()

    def _quit(self):
        self._running = False

    # ------------------------------------------------------------------ #
    def run(self):
        self._running = True
        while self._running:
            dt = self.clock.tick(60)
            self.scene.mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._toggle_pause()
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)
            self.window.fill(BG)
            self.scene.draw(self.window)          # every scene draws at real window size
            pygame.display.flip()
        pygame.quit()
