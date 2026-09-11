"""GARTOK Tactical shell: window, main loop and screen switching.

The screens do the work: `MenuScreen` (save slots), `DraftScreen` (building the
starting guild), `MapScreen` (the hub -- give groups orders and advance the
world), `GuildScreen` (roster + gear), `SquadScreen` (who fights), `BattleScreen`
(the fight) and `LootScreen` (split the spoils). Each exposes `handle_event`,
`update(dt)`, `draw(surface)` and reads `self.mouse` (canvas-space cursor).

Campaign loop: menu -> draft -> MAP <-> guild
                       MAP: pick a group, click a place -> travel order
                            (or an on-node action). There is no manual
                            "advance" button -- the moment no group is left
                            idle, `_advance` fires on its own and keeps
                            chasing the clock (`campaign.advance`) to the
                            soonest order, resolving travel/work silently,
                            until either a group goes idle again (back to the
                            map, pointed at it) or something needs the
                            player's screen, handed back here as `_pending`:
                            squad -> battle -> loot -> [next pending] -> MAP
                            party -> market -> [next pending] -> MAP
                            party -> taverna (recruit) -> [next pending] -> MAP
                            party -> the wilds (hunt) -> [next pending] -> MAP
`persist` autosaves after the draft, on every return to the map and after every
battle. Permadeath: a member who does not survive is dropped; a full wipe ends
the campaign.

Every scene is `native`: it draws straight to the real (resizable) window and
lays itself out from `screen.get_size()`. `WIN_W x WIN_H` (theme.py) is just the
opening window size and the battle screen's fixed board canvas.
"""

import pygame

from . import arena, campaign, hunt, matchup, persist, world
from .bank_screen import BankScreen
from .battle import Battle
from .battle_screen import BattleScreen
from .char_editor_screen import CharEditorScreen
from .draft_screen import DraftScreen
from .editor_menu_screen import EditorMenuScreen
from .gear_screen import GearScreen
from .guild import Guild
from .guild_screen import GuildScreen
from .hunt_screen import HuntScreen
from .level_screen import LevelScreen
from .loot_screen import LootScreen
from .map_editor_screen import MapEditorScreen
from .map_screen import MapScreen
from .market_screen import MarketScreen
from .menu_screen import MenuScreen
from .pause_screen import PauseScreen
from .reward_screen import RewardScreen
from .squad_screen import SquadScreen
from .taverna_screen import TavernaScreen
from .theme import BG, Fonts, WIN_H, WIN_W


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
        self._arena_offer = None             # world.Bout for the current arena fight, or None
        self._hunt = None                    # live hunt.HuntState -- carried across ambush battles
        self._map_notices = []               # lines for the next MapScreen (title forfeit, ...)
        self._pending = []                   # [(Group, Order)] left to resolve from the last tick
        self._start_menu()

    # ------------------------------------------------------------------ #
    # campaign flow                                                      #
    # ------------------------------------------------------------------ #
    def _start_menu(self):
        self.scene = MenuScreen(self.fonts, on_new=self._new_game,
                                on_continue=self._continue_game,
                                on_delete=persist.delete_slot,
                                on_editor=self._start_editor)

    def _start_editor(self):
        self.scene = EditorMenuScreen(self.fonts,
                                      on_character=self._open_char_editor,
                                      on_scenario=self._open_map_editor,
                                      on_back=self._start_menu)

    def _open_char_editor(self):
        self.scene = CharEditorScreen(self.fonts, on_back=self._start_editor)

    def _open_map_editor(self):
        self.scene = MapEditorScreen(self.fonts, on_back=self._start_editor)

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
        valid = {n.id for n in world.NODES}
        for g in self.guild.groups:            # a stale/removed node id: drop back to the start
            if g.node not in valid:
                g.node = world.START_NODE
        self._start_map()

    def _save(self):
        persist.save_game(self.slot, self.guild)

    def _start_map(self):
        """Land on the map -- unless every group already has an order and
        none is idle, in which case there's nothing for the player to do yet:
        keep the clock running (`_advance`) instead of stopping here."""
        self._pending = []
        if self.guild.can_auto_advance:
            self._advance()
            return
        self._map_notices += arena.sync(self.guild)
        self._save()
        self.scene = MapScreen(self.fonts, self.guild,
                               on_guild=self._open_guild,
                               on_wipe=self._campaign_over,
                               on_advance=self._advance)
        if self._map_notices:
            self.scene.notices = self._map_notices
            self._map_notices = []

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

    # ------------------------------------------------------------------ #
    # the tick: MapScreen issues orders on groups; the clock plays them out #
    # ------------------------------------------------------------------ #
    def _advance(self, dt=None):
        """`dt=None` is the default, self-driven tick: jump to the soonest
        order, then keep chasing the next one on its own -- silent hops (a
        multi-leg travel order stopping at a waypoint) don't need a fresh
        click, so this loops through them and only stops once a group
        actually goes idle (needs a new order) or comes back `pending` (needs
        its screen played). A forced `dt` (MAINTENANCE) is one deliberate
        jump, no chasing. Auto orders (travel/work) already happened by the
        time this returns; anything else comes back as `self._pending` for
        `_after_activity`."""
        chase = dt is None
        while True:
            busy_before = {g.gid for g in self.guild.groups if g.busy}
            result = campaign.advance(self.guild, dt=dt)
            self._map_notices += result.events
            if result.wiped:
                self._hunt = None
                self._campaign_over()
                return
            if not chase or result.pending:
                break
            went_idle = any(g.gid in busy_before and not g.busy for g in self.guild.groups)
            if went_idle or not any(g.busy for g in self.guild.groups):
                break
        self._pending = list(result.pending)
        self._after_activity()

    def _after_activity(self):
        """Continue draining the last tick's pending orders, or return to the
        map once there are none left. Every activity screen's on_done/on_back
        routes here instead of straight back to the map."""
        while self._pending:
            group, order = self._pending.pop(0)
            if group.empty:
                # Not just belt-and-suspenders against campaign.advance's own
                # empty-group guard: HuntScreen calls guild.pass_time directly
                # while playing out an already-dequeued hunt order, which can
                # starve a DIFFERENT group still waiting right here in
                # self._pending. Skip it -- no one left to open a screen for.
                continue
            node = world.node(group.node)
            if order.kind == "arena":
                self._open_arena(group, node)
            elif order.kind == "market":
                self._open_market_stalls(list(group.members), node, None)
            elif order.kind == "bank":
                self._open_bank_vault(list(group.members), node, None)
            elif order.kind == "recruit":
                self._open_taverna(list(group.members), node, None)
            elif order.kind == "hunt":
                self._open_hunt_ground(list(group.members), node, None)
            return
        self._start_map()

    def _open_arena(self, group, node):
        if arena.defense_due(self.guild):
            self._start_title_defense(node)
            return
        offers = list(world.arena_offers(self.guild.arena_reputation))
        if "arena_dethrone" not in self.guild.deeds_done:
            offers.append(arena.champion_bout())
        else:                                   # champion beaten: the Games are open
            offers += [arena.brawl_bout(), arena.ctf_bout(), arena.boss_bout()]
        disabled = {u for u in group.members if u.incapacitated}
        self.scene = SquadScreen(self.fonts, group.members, node,
                                 on_confirm=self._start_battle, on_back=self._after_activity,
                                 arena_offers=offers, disabled=disabled,
                                 confirm_label="STAKE AND FIGHT")

    def _open_market_stalls(self, shoppers, node, _offer):
        self.scene = MarketScreen(self.fonts, self.guild, shoppers, node,
                                  on_done=self._after_activity)

    def _open_bank_vault(self, party, node, _offer):
        self.scene = BankScreen(self.fonts, self.guild, party,
                                on_done=self._after_activity)

    # ------------------------------------------------------------------ #
    # hunting the wilds -- an activity that can spring a fight            #
    # ------------------------------------------------------------------ #
    def _open_hunt_ground(self, party, node, _offer):
        self._hunt = hunt.HuntState(list(party), node, hours_left=0)
        self.scene = HuntScreen(self.fonts, self.guild, self._hunt, phase="setup",
                                on_ambush=self._start_hunt_battle, on_done=self._end_hunt)

    def _start_hunt_battle(self, state, pack):
        self._battle_squad = list(state.party)
        self._battle_node = state.node
        self._arena_offer = None
        battle = Battle(state.party, pack, scenario=state.node.scenario(),
                        daylight=self.guild.clock.is_daylight,
                        lethal=state.node.lethal, arena=False)
        self.scene = BattleScreen(self.fonts, battle, on_battle_end=self._battle_end)

    def _resume_hunt(self):
        """Back from a won ambush with daylight still to spend."""
        self._save()
        self.scene = HuntScreen(self.fonts, self.guild, self._hunt, phase="interlude",
                                on_ambush=self._start_hunt_battle, on_done=self._end_hunt)

    def _finish_hunt(self):
        """The hunt is over (dark, driven off, or the party is spent) -- the
        screen banks the haul on entering its wrap-up phase."""
        self._save()
        self.scene = HuntScreen(self.fonts, self.guild, self._hunt, phase="done",
                                on_ambush=self._start_hunt_battle, on_done=self._end_hunt)

    def _end_hunt(self):
        self._hunt = None
        if self.guild.empty:
            self._campaign_over()
        else:
            self._after_activity()

    def _open_taverna(self, party, node, _offer):
        self.scene = TavernaScreen(self.fonts, self.guild, party, node,
                                   on_done=self._after_activity)

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
            self._charge(squad, offer.entry * len(squad))
        enemies, scenario = matchup.build(node, offer, squad_size=len(squad),
                                          guild=self.guild)
        battle = Battle(squad, enemies, scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=node.lethal,
                        arena=node.arena)
        self.scene = BattleScreen(self.fonts, battle, on_battle_end=self._battle_end)

    def _start_title_defense(self, node):
        """A due title challenge: the champion alone against one scaled newcomer."""
        champ = arena.champion_of(self.guild)
        offer = arena.defense_bout()
        self._battle_squad = [champ]
        self._battle_node = node
        self._arena_offer = offer
        enemies, scenario = matchup.build(node, offer, squad_size=1, guild=self.guild)
        battle = Battle([champ], enemies, scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=False, arena=True)
        self.scene = BattleScreen(self.fonts, battle, on_battle_end=self._battle_end)

    def _battle_end(self, battle):
        hunt_state = self._hunt
        outcome = campaign.absorb_battle(self.guild, self._battle_squad, battle,
                                         node=self._battle_node,
                                         arena_offer=self._arena_offer)
        self._battle_squad = []
        self._battle_node = None
        self._arena_offer = None
        note = outcome.arena_title_event

        if outcome.campaign_over:             # full wipe: campaign over
            self._hunt = None
            self._campaign_over()
            return

        if hunt_state is not None:            # an ambush during a hunt
            hunt_state.party = [u for u in outcome.survivors if u in self.guild.roster]
            won = battle.winner == "player"
            resume = won and hunt_state.party and hunt_state.hours_left > 0
            nxt = self._resume_hunt if resume else self._finish_hunt
            if outcome.loot_pool and outcome.survivors:
                self._save()
                self.scene = LootScreen(self.fonts, self.guild, outcome.survivors,
                                        outcome.loot_pool, on_done=nxt)
                return
            nxt()
            return

        if outcome.arena_reward is not None:  # arena bout won: hand out the purse
            self._save()
            self.scene = RewardScreen(self.fonts, self.guild, outcome.survivors,
                                      outcome.arena_reward, on_done=self._after_activity,
                                      deeds=outcome.deeds_earned, note=note)
            return

        if note:                             # lost defense / vacant title: no purse screen
            self._map_notices.append(note)

        if outcome.loot_pool and outcome.survivors:
            self._save()
            self.scene = LootScreen(self.fonts, self.guild, outcome.survivors,
                                    outcome.loot_pool, on_done=self._after_activity)
            return
        self._after_activity()

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
                    if not self.scene.handle_escape():
                        self._toggle_pause()
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)
            self.window.fill(BG)
            self.scene.draw(self.window)          # every scene draws at real window size
            pygame.display.flip()
        pygame.quit()
