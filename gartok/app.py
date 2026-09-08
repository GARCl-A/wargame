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

The scene always draws to a fixed `WIN_W x WIN_H` canvas; the loop scales that to
the real window, letterboxed, so the window can be resized.
"""

import pygame

from . import campaign, persist, world
from .battle import Battle
from .battle_screen import BattleScreen
from .draft_screen import DraftScreen
from .guild import Guild
from .guild_screen import GuildScreen
from .loot_screen import LootScreen
from .map_screen import MapScreen
from .market_screen import MarketScreen
from .menu_screen import MenuScreen
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
        self.canvas = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.fonts = Fonts()
        self._view = (1.0, 0, 0)              # (scale, offset_x, offset_y)

        self.slot = None
        self.guild = None
        self._battle_squad = []              # roster units sent to the current battle
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
                               on_menu=self._start_menu,
                               on_wipe=self._campaign_over)

    def _campaign_over(self):
        """Roster gone (a wipe, or the last member starved on the road)."""
        persist.delete_slot(self.slot)
        self._start_menu()

    def _open_guild(self):
        self.scene = GuildScreen(self.fonts, self.guild,
                                 on_back=self._start_map, on_menu=self._start_menu)

    def _open_squad(self, node):
        offers = world.arena_offers(self.guild.arena_reputation) if node.arena else None
        disabled = {u for u in self.guild.roster if u.incapacitated}
        self.scene = SquadScreen(self.fonts, self.guild.roster, node,
                                 on_confirm=self._start_battle, on_back=self._start_map,
                                 arena_offers=offers, disabled=disabled,
                                 confirm_label="APOSTAR E LUTAR" if node.arena else "CONFIRMAR")

    def _open_market(self, node):
        roster = self.guild.roster
        self.scene = SquadScreen(self.fonts, roster, node,
                                 on_confirm=self._open_market_stalls, on_back=self._start_map,
                                 max_pick=len(roster), title="QUEM VAI AO MERCADO",
                                 confirm_label="IR AS COMPRAS")

    def _open_market_stalls(self, shoppers, node, _offer):
        self.scene = MarketScreen(self.fonts, self.guild, shoppers, node,
                                  on_done=self._start_map)

    def _open_work(self, node):
        roster = self.guild.roster
        self.scene = SquadScreen(self.fonts, roster, node,
                                 on_confirm=self._open_lumber_yard, on_back=self._start_map,
                                 max_pick=len(roster), title="QUEM VAI TRABALHAR",
                                 confirm_label="IR A MADEIREIRA")

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
                                 max_pick=len(roster), title="QUEM VAI A TAVERNA",
                                 confirm_label="IR A TAVERNA")

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
                                         arena_offer=self._arena_offer)
        self._battle_squad = []
        self._arena_offer = None

        if outcome.campaign_over:             # full wipe: campaign over
            self._campaign_over()
            return

        if outcome.arena_reward is not None:  # arena bout won: hand out the purse
            self._save()
            self.scene = RewardScreen(self.fonts, self.guild, outcome.survivors,
                                      outcome.arena_reward, on_done=self._start_map)
            return

        if outcome.loot_pool and outcome.survivors:
            self._save()
            self.scene = LootScreen(self.fonts, self.guild, outcome.survivors,
                                    outcome.loot_pool, on_done=self._start_map)
            return
        self._start_map()

    # ------------------------------------------------------------------ #
    def _to_canvas(self, pos):
        scale, ox, oy = self._view
        return (int((pos[0] - ox) / scale), int((pos[1] - oy) / scale))

    def _scene_pos(self, pos):
        """Cursor `pos` in the coords the current scene wants: raw window pixels
        for a `native` scene, fixed-canvas coords for the rest. Re-checked per
        call because an event may swap the scene mid-frame."""
        return pos if getattr(self.scene, "native", False) else self._to_canvas(pos)

    def _present(self):
        ww, wh = self.window.get_size()
        scale = min(ww / WIN_W, wh / WIN_H)
        sw, sh = int(WIN_W * scale), int(WIN_H * scale)
        ox, oy = (ww - sw) // 2, (wh - sh) // 2
        self._view = (scale, ox, oy)
        self.window.fill(BG)
        frame = pygame.transform.smoothscale(self.canvas, (sw, sh))
        self.window.blit(frame, (ox, oy))
        pygame.display.flip()

    def _blit_scene(self):
        """A `native` scene draws straight to the window at its real size; the
        rest draw to the fixed canvas, which `_present` scales into the window."""
        if getattr(self.scene, "native", False):
            self.window.fill(BG)
            self.scene.draw(self.window)
            pygame.display.flip()
        else:
            self.scene.draw(self.canvas)
            self._present()

    # ------------------------------------------------------------------ #
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            self.scene.mouse = self._scene_pos(pygame.mouse.get_pos())
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                    pygame.MOUSEMOTION):
                    self.scene.handle_event(pygame.event.Event(
                        event.type, {**event.dict, "pos": self._scene_pos(event.pos)}))
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)
            self._blit_scene()
        pygame.quit()
