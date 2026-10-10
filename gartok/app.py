"""GARTOK Tactical shell: window, main loop and screen switching.

The screens do the work: `MenuScreen` (guilds and their saves), `DraftScreen`
(building the starting guild), `MapScreen` (the hub -- give groups orders and advance the
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
                            (any arrival) -> the guard (justice.py) -> prison |
                              [battle -> loot] | flee -> [next pending] -> MAP
                            (any arrival at an unsafe node) -> ambush -> MAP
                              (a red CTA replaces the "!" popup -- the group
                              sits paused right there until the player clicks
                              it) -> [battle -> loot] -> [next pending] -> MAP
`persist` autosaves after the draft, on every return to the map and after every
battle. Permadeath: a member who does not survive is dropped; a full wipe ends
the campaign.

Every scene is `native`: it draws straight to the real (resizable) window and
lays itself out from `screen.get_size()`. `START_SIZE` is just the
opening window size.
"""

from typing import ClassVar

import pygame

from . import (
    arena,
    campaign,
    combat_lab,
    economy,
    encounters,
    hunt,
    justice,
    matchup,
    missions,
    node_functions,
    orders,
    persist,
    recorder,
    settings,
    tutorial_card,
    vocations,
    wagon_watch,
    world,
)
from .battle import Battle
from .battle_screen import BattleScreen
from .char_editor_screen import CharEditorScreen
from .city_property_screen import CityPropertyScreen, RepossessionScreen
from .combat_lab_screen import CombatLabScreen
from .combat_log import CombatLog
from .constants import fmt_money
from .draft_screen import DraftScreen
from .editor_menu_screen import EditorMenuScreen
from .gear_screen import GearScreen
from .group import NORMAL
from .guild import Guild
from .guild_screen import GuildScreen
from .hunt_screen import HuntScreen, TrackScreen
from .justice_screen import GuardScreen
from .ledger_screen import LedgerScreen
from .level_screen import LevelScreen
from .loot_screen import LootScreen
from .map_editor_screen import MapEditorScreen
from .map_screen import MapScreen
from .market_screen import MarketScreen
from .menu_screen import MenuScreen
from .pause_screen import PauseScreen
from .reward_screen import RewardScreen
from .saves_screen import SavesScreen
from .scenario import Scenario
from .squad_screen import SquadScreen
from .tanner_screen import TannerScreen
from .taverna_screen import TavernaScreen
from .tutorial import TutorialState
from .ui.banner import set_player_color
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .vocation_screen import VocationScreen
from .watch_screen import WatchScreen
from .wilds_claim_screen import WildsClaimScreen

START_SIZE = (1212, 832)
TUTORIAL_DEBOUNCE_MS = 300      # clicks swallowed right after a tutorial card closes


class App:
    _left_outside = None    # (group, node, guarded): a wagon waiting outside the node the party entered

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("GARTOK Tactical")
        self.window = pygame.display.set_mode(START_SIZE, pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
        self.clock = pygame.time.Clock()
        self.ui_fonts = ui_fonts()

        self.world = None                    # persist world id: the save folder of the running campaign
        self.guild = None
        self._battle_squad = []              # roster units sent to the current battle
        self._battle_node = None             # world node the current battle is at
        self._arena_offer = None             # world.Bout for the current arena fight, or None
        self._arena_purse = None             # who pays an arena stake: the whole group
        self._hunt = None                    # live hunt.HuntState -- carried across ambush battles
        self._pause_order = None             # in-flight "guard"/"ambush" Order -- carried across a forced battle
        self._pause_group = None             # the Group that order belongs to
        self._claim_stage_pending = None     # a Wilds claim stage ("CLEARED"/"SWEPT") a battle in flight decides
        self._map_notices = []               # lines for the next MapScreen (title forfeit, ...)
        self._pending = []                   # [(Group, Order)] left to resolve from the last tick
        self._pending_event = None           # (Group, Order) an ambush paused mid-map -- MapScreen's own CTA resolves it
        self._draft_tutorial = TutorialState()   # the tutorial, before a Guild exists to hold it
        self._tutorial_card_rect = None
        self._tutorial_badge_rect = None
        self._tutorial_rect_scene = None     # which scene those rects were drawn for
        self._tutorial_block_until = 0       # ms: swallow clicks right after a dismissal
        self._tutorial_swallow_up = False    # the release that closes the dismissing press
        self._start_menu()

    @property
    def tutorial(self):
        """The tutorial's state: the guild's own once there is one (so it
        saves/loads by slot), `_draft_tutorial` before that (draft.py has no
        guild yet to hold it on)."""
        return self.guild.tutorial if self.guild is not None else self._draft_tutorial

    # ------------------------------------------------------------------ #
    # campaign flow                                                      #
    # ------------------------------------------------------------------ #
    def _start_menu(self, notice=None):
        recorder.detach()
        self.scene = MenuScreen(self.ui_fonts, on_new=self._new_game,
                                on_continue=self._continue_game,
                                on_saves=self._open_saves,
                                on_delete=persist.delete_world,
                                on_editor=self._start_editor, notice=notice)

    def _open_saves(self, world_id):
        self.scene = SavesScreen(self.ui_fonts, world_id, on_load=self._continue_game,
                                 on_back=self._start_menu)

    def _start_editor(self):
        self.scene = EditorMenuScreen(self.ui_fonts,
                                      on_character=self._open_char_editor,
                                      on_scenario=self._open_map_editor,
                                      on_combat_lab=self._open_combat_lab,
                                      on_back=self._start_menu)

    def _open_combat_lab(self):
        self.scene = CombatLabScreen(self.ui_fonts, on_start=self._start_lab_fight,
                                     on_back=self._start_editor)

    def _start_lab_fight(self, setup):
        battle, meta = combat_lab.build(setup["fight"], setup["level"], setup["squad"])
        controllers = setup["controllers"]
        path = combat_lab.log_path(setup["name"])
        battle.record_to(CombatLog(path, {"source": "lab", "name": setup["name"], **meta}, controllers))
        self.scene = BattleScreen(self.ui_fonts, battle, on_battle_end=lambda _b: self._open_combat_lab())

    def _open_char_editor(self):
        self.scene = CharEditorScreen(self.ui_fonts, on_back=self._start_editor)

    def _open_map_editor(self):
        self.scene = MapEditorScreen(self.ui_fonts, on_back=self._start_editor)

    def _new_game(self):
        self.world = None                    # minted in `_draft_done`, once there is a guild to name it
        self.guild = None
        self._draft_tutorial = TutorialState()
        self.scene = VocationScreen(self.ui_fonts, on_done=self._vocation_done,
                                    tutorial=self._draft_tutorial)

    def _vocation_done(self, vocation):
        self.scene = DraftScreen(self.ui_fonts, on_done=self._draft_done,
                                 tutorial=self._draft_tutorial, vocation=vocation)

    def _draft_done(self, picks, leader, name, banner_color, banner_icon, vocation=None):
        self.world = persist.new_world_id()
        self.guild = Guild(picks, node=world.START_NODE, leader=leader,
                           name=name, banner_color=banner_color, banner_icon=banner_icon,
                           tutorial=self._draft_tutorial, vocation=vocation)
        set_player_color(self.guild.banner_color)
        self._record_play()
        self._start_map()

    def _continue_game(self, world_id, save_id=persist.CURRENT):
        try:
            guild = persist.load_game(world_id, save_id)
        except persist.SaveVersionError as e:
            from .alert_screen import AlertScreen
            back = self.scene
            self.scene = AlertScreen(self.ui_fonts, back, "CANNOT LOAD SAVE", [str(e)],
                                     on_done=lambda: setattr(self, "scene", back), is_danger=True)
            return
        self.world = world_id
        self.guild = guild
        self._record_play()
        self._left_outside = None
        self._pending_event = None
        if save_id != persist.CURRENT:
            self._save()                     # the snapshot becomes the live state
        set_player_color(self.guild.banner_color)
        valid = {n.id for n in world.NODES}
        for g in self.guild.groups:            # a stale/removed node id: drop back to the start
            if g.node not in valid:
                g.node = world.START_NODE
        self._resume_pending()

    def _resume_pending(self):
        """A save taken with a forced fight due (an ambush on the map, a guard
        catch, a raid) picks it back up through the same dispatch a fresh tick
        uses -- `_after_activity` drains `_pending`."""
        self._pending = [(g, g.pending) for g in self.guild.groups
                         if g.fight_due and not g.empty]
        if self._pending:
            self._after_activity()
        else:
            self._start_map()

    def _record_play(self):
        """Attach the play recorder to the guild just entered, if the player turned it on."""
        if settings.get("record_play") == "ON":
            recorder.attach(persist.world_dir(self.world), self.guild)

    def _save(self):
        persist.save_game(self.world, self.guild)

    def _can_save(self):
        """Never mid-battle or mid-hunt: neither lives in the save, so a snapshot
        taken inside one would load as if the fight had never happened."""
        scene = self.scene.resume_to if isinstance(self.scene, PauseScreen) else self.scene
        return (self.guild is not None and self._hunt is None
                and not isinstance(scene, BattleScreen))

    def _start_map(self):
        """Land on the map -- unless every group already has an order and
        none is idle, in which case there's nothing for the player to do yet:
        keep the clock running (`_advance`) instead of stopping here.

        `MapScreen` assumes at least one group exists to select -- true for
        every wipe (routed to `_campaign_over` before ever reaching here), but
        a mass ACCEPT ARREST (`justice.jail`) can empty `guild.groups` too,
        without anyone dying. That is not game over: fast-forward the clock
        (`_wait_out_the_sentence`) until the nearest release stands a fresh
        group back up, same trick `HuntScreen` uses to tick the clock outside
        the normal orders engine."""
        self._pending = []
        if not self.guild.groups:
            if not self.guild.jailed:            # truly nobody left anywhere
                self._campaign_over()
                return
            self._map_notices += self._wait_out_the_sentence()
        if self.guild.can_auto_advance:
            self._advance()
            return
        self._map_notices += arena.sync(self.guild)
        self._save()
        self.scene = MapScreen(self.ui_fonts, self.guild,
                               on_guild=self._open_guild,
                               on_wipe=self._campaign_over,
                               on_advance=self._advance,
                               on_manage_group=self._open_group,
                               pending_event=self._pending_event,
                               on_resolve_event=self._resolve_pending_event,
                               on_autowin=self._resolve_ambush_autowin,
                               on_visit_tavern=self._visit_tavern,
                               on_visit_claim=self._visit_claim,
                               on_abandon=self._abandon_broken)
        if self._map_notices:
            self.scene.notices = self._map_notices
            self._map_notices = []

    def _abandon_broken(self, group, dest):
        """The group means to travel with a broken wagon: that leaves it behind. Ask about
        each one in turn (cargo first, if the player wants to unload it); the trip goes
        ahead only once none is left."""
        if world.route(group.node, dest)[1] == float("inf"):
            self._map_notices.append(f"There is no way from here to {world.node(dest).name}.")
            self._start_map()
            return
        wagon = next((w for w in group.wagons if w.broken), None)
        if wagon is None:
            group.order = orders.travel(group, dest, vocations.travel_mult(self.guild))
            self._start_map()
            return

        def leave():
            self.guild.abandon_wagon(group, wagon)
            self._map_notices.append(f"{group.display_name} leaves its broken {wagon.kind.lower()} behind.")
            self._abandon_broken(group, dest)

        def manage():
            from .loot_screen import LootScreen
            pool = [name for name, qty in wagon.stash.items for _ in range(qty)]
            scene = LootScreen(self.ui_fonts, self.guild, group.members, pool, on_done=lambda: None)

            def back():
                left = dict(scene.pool)
                kept = []
                for inst in wagon.stash.items:
                    keep = min(inst.qty, left.get(inst.name, 0))
                    left[inst.name] = left.get(inst.name, 0) - keep
                    if keep:
                        part = inst.copy()
                        part.qty = keep
                        kept.append(part)
                wagon.stash.items[:] = kept
                self._abandon_broken(group, dest)

            scene.on_done = back
            self.scene = scene

        from .abandon_screen import AbandonScreen
        self.scene = AbandonScreen(self.ui_fonts, wagon, on_manage=manage, on_leave=leave,
                                   on_stay=self._start_map)

    def _wait_out_the_sentence(self):
        """Every group emptied out into `guild.jailed` -- nothing to show on
        the map. Advance a day at a time (`Guild.pass_time`, which is what
        runs `justice.release_due`) until someone's sentence is up."""
        events = []
        while not self.guild.groups and self.guild.jailed:
            evs, cas = self.guild.pass_time(24)
            events += evs
            if cas:
                # We could show an alert here or just discard for jailed members?
                pass
        return events

    def _campaign_over(self):
        """Roster gone (a wipe, or the last member starved on the road). The
        world stays: its last `current` and autosaves are still loadable."""
        self.guild = self.world = None
        self._start_menu(notice="The guild was wiped out. Load an earlier save to try again.")

    def _open_guild(self):
        self.scene = GuildScreen(self.ui_fonts, self.guild,
                                 on_back=self._start_map, on_level=self._open_level,
                                 on_manage=self._open_gear, on_bank=self._open_vault_view)

    def _open_vault_view(self):
        from .bank_view_screen import BankViewScreen
        self.scene = BankViewScreen(self.ui_fonts, self.guild, on_done=self._open_guild)

    def _open_gear(self, group):
        if group.fight_due:
            return
        self.scene = GearScreen(self.ui_fonts, self.guild, on_back=self._open_guild, group=group)

    def _open_group(self, group):
        if group.fight_due:
            return
        from .group_screen import GroupScreen
        self.scene = GroupScreen(self.ui_fonts, self.guild, group, on_back=self._after_activity,
                                 on_tick=self._tick_outside_map)
    def _open_level(self, unit):
        self.scene = LevelScreen(self.ui_fonts, unit,
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
        its screen played). A forced `dt` (the map's world-wide ADVANCE) is one deliberate
        jump, no chasing. Auto orders (travel/work/rest) already happened by the
        time this returns; anything else comes back as `self._pending` for
        `_after_activity`."""
        chase = dt is None
        all_casualties = []
        while True:
            busy_before = {g.gid for g in self.guild.groups if g.busy}
            result = campaign.advance(self.guild, dt=dt)
            self._map_notices += result.events
            if result.wiped:
                self._hunt = None
                self._campaign_over()
                return
            all_casualties.extend(result.casualties)

            if not chase or result.pending:
                break
            went_idle = any(g.gid in busy_before and not g.busy for g in self.guild.groups)
            if went_idle or not any(g.busy for g in self.guild.groups):
                break
        self._pending = list(result.pending)

        self._report_casualties(all_casualties, self._after_activity)

    def _report_casualties(self, casualties, nxt):
        """Whoever starved in the last stretch of clock: a death alert, then the loot
        screen for what they carried, then `nxt`. No popup for hunger itself --
        COMMAND's alert icon (map_screen._messages) covers it every frame the map is up."""
        if casualties:
            def show_starvation_loot():
                from . import loot
                pool = []
                for u in casualties:
                    pool += loot.carried_by(u)
                if pool and self.guild.roster:
                    from .loot_screen import LootScreen
                    self.scene = LootScreen(self.ui_fonts, self.guild, self.guild.roster, pool, on_done=nxt)
                else:
                    nxt()

            def show_death_alert():
                from .alert_screen import AlertScreen
                msgs = [f"{u.name} starved to death." for u in casualties]
                self.scene = AlertScreen(self.ui_fonts, self.scene, "DEATH ALERT", msgs, on_done=show_starvation_loot, is_danger=True)

            show_death_alert()
        else:
            nxt()

    def _tick_outside_map(self, hours, busy=()):
        """An hour a screen spends away from the tick/orders loop (a wagon repair): run
        it through `campaign.advance` like `_hunt_tick`, so the other groups' orders stay
        in lockstep with the clock and whatever falls due is queued for `_after_activity`.
        Returns `(events, casualties)`, the shape of `Guild.pass_time` -- the contract
        `Guild.repair_wagon`'s `tick` relies on; the dead are also reported once the
        screen is left."""
        result = campaign.advance(self.guild, dt=hours, busy=busy)
        self._pending += result.pending
        self._screen_dead = (*self._screen_dead, *result.casualties)
        if result.wiped:
            self._campaign_over()
        return result.events, result.casualties

    def _land_on_map_paused(self, group, order):
        # No more "AMBUSH! [FIGHT]" popup -- land back on the map with this
        # group paused (already idle, see campaign._arrival_pause) and let
        # MapScreen's own red CTA start the fight when the player is ready.
        # `_start_map` resets `self._pending`, so the rest of this tick's
        # queue (rare, but possible) is stashed around the call instead of
        # getting silently dropped.
        self._pending_event = (group, order)
        rest = self._pending
        self._start_map()
        self._pending = rest

    # order.kind -> opener(self, group, node, order); a new activity is one line.
    _screen_dead: ClassVar[tuple] = ()     # starved during a screen's hour, until the screen is left

    # node function id (node_functions.FUNCTIONS) -> the screen that plays it
    _FUNCTION_OPENERS: ClassVar[dict] = {
        "shop": lambda s, g, n, o: s._open_market_stalls(list(g.members), n, None),
        "bank": lambda s, g, n, o: s._open_bank_vault(g, n, None),
        "property": lambda s, g, n, o: s._open_city_property(g, n),
        "claim": lambda s, g, n, o: s._open_wilds_claim(g, n),
        "recruit": lambda s, g, n, o: s._open_taverna(list(g.members), n, None, group=g),
        "prison": lambda s, g, n, o: s._open_prison(list(g.members), n, None),
        "hunt": lambda s, g, n, o: s._open_hunt_ground(list(g.members), n, None, group=g),
        "ox_hunt": lambda s, g, n, o: s._open_hunt_ground(list(g.members), n, None, group=g, target="ox"),
        "tanner": lambda s, g, n, o: s._open_tanner_stall(g, n, None),
        "trust": lambda s, g, n, o: s._open_trust_offer(g, n, None),
        "ledger": lambda s, g, n, o: s._open_ledger_desk(g, n, None),
        "forge": lambda s, g, n, o: s._open_forge(g, n, None),
        "apothecary": lambda s, g, n, o: s._open_apothecary(g, n, None),
        "library": lambda s, g, n, o: s._open_library(g, n, None),
        "stable": lambda s, g, n, o: s._open_stables(g),
        "ancient_ruins": lambda s, g, n, o: s._enter_ancient_ruins(g, n),
    }

    # order.kind -> opener: the node functions' kinds, the arena and the forced fights
    _ACTIVITY_OPENERS: ClassVar[dict] = {
        **{node_functions.FUNCTIONS[fid].order_kind: opener
           for fid, opener in _FUNCTION_OPENERS.items()},
        "arena": lambda s, g, n, o: s._open_arena(g, n),
        "guard": lambda s, g, n, o: s._open_guard_check(g, o),
        "ambush": lambda s, g, n, o: s._land_on_map_paused(g, o),
        "eviction": lambda s, g, n, o: s._start_property_raid(g, o),
        "wilds_raid": lambda s, g, n, o: s._start_wilds_raid(g, o),
        "wilds_seizure": lambda s, g, n, o: s._start_wilds_seizure(g, o),
        "wilds_retake": lambda s, g, n, o: s._start_wilds_retake(g, o),
    }

    # forced-fight order.kind -> campaign.resolve_*(guild, group, order, outcome);
    # anything else is a road ambush.
    _FORCED_FIGHT_RESOLVERS: ClassVar[dict] = {
        "guard": campaign.resolve_guard_fight_aftermath,
        "eviction": campaign.resolve_property_raid,
        "wilds_raid": campaign.resolve_wilds_raid,
        "wilds_seizure": campaign.resolve_wilds_seizure,
        "wilds_retake": campaign.resolve_wilds_claim_retake,
    }

    def _after_activity(self):
        """Continue draining the last tick's pending orders, or return to the
        map once there are none left. Every activity screen's on_done/on_back
        routes here instead of straight back to the map."""
        if self._screen_dead:
            dead, self._screen_dead = self._screen_dead, ()
            self._report_casualties(dead, self._after_activity)
            return
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
            handler = self._ACTIVITY_OPENERS.get(order.kind)
            if handler:
                handler(self, group, node, order)
            return
        self._start_map()

    def _open_arena(self, group, node):
        if arena.defense_due(self.guild):
            self._start_title_defense(node)
            return
        offers = [arena.scrapper_bout()]
        if "arena_dethrone" not in self.guild.deeds_done:
            offers.append(arena.champion_bout())
        else:                                   # champion beaten: the Games are open
            offers += [arena.brawl_bout(), arena.ctf_bout(), arena.boss_bout()]
        disabled = {u for u in group.members if u.incapacitated}
        self._arena_purse = group.members
        self.scene = SquadScreen(self.ui_fonts, group.members, node,
                                 on_confirm=self._start_battle, on_back=self._after_activity,
                                 arena_offers=offers, disabled=disabled,
                                 confirm_label="STAKE AND FIGHT")

    def _open_market_stalls(self, shoppers, node, _offer):
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

    def _start_claim_clear_battle(self, group):
        self._start_claim_battle(group, "CLEARED", economy.WILDS_CLAIM_CLEAR_LEVEL,
                                 economy.WILDS_CLAIM_CLEAR_SIZE)

    def _start_claim_sweep_battle(self, group):
        self._start_claim_battle(group, "SWEPT", economy.WILDS_CLAIM_SWEEP_LEVEL,
                                 economy.WILDS_CLAIM_SWEEP_SIZE)

    def _start_claim_battle(self, group, stage_after, level, size):
        """A deliberate claim-stage fight (CLEAR/SWEEP) -- not a forced pause
        like a guard/ambush/raid, so `self._pause_order` stays untouched and
        `_battle_end` falls through to its normal loot/`_after_activity` path
        once `_claim_stage_pending` has done its job."""
        node = world.node(group.node)
        self._battle_squad = list(group.members)
        self._battle_node = node
        self._arena_offer = None
        self._claim_stage_pending = stage_after
        pack = [encounters.build_enemy(level) for _ in range(size)]
        battle = Battle(list(group.members), pack, scenario=node.scenario(),
                        daylight=self.guild.clock.is_daylight, lethal=True, arena=False,
                        clock_day=self.guild.clock.day)
        self._enter_battle(battle, node)

    def _open_tanner_stall(self, group, node, _offer):
        self.scene = TannerScreen(self.ui_fonts, self.guild, group,
                                  on_done=self._after_activity)

    def _open_ledger_desk(self, group, node, _offer):
        self.scene = LedgerScreen(self.ui_fonts, self.guild, group,
                                 on_done=self._after_activity)

    def _open_forge(self, group, node, _offer):
        from .crafting_screen import CraftingScreen
        self.scene = CraftingScreen(self.ui_fonts, self.guild, group,
                                    on_done=self._after_activity)

    def _open_apothecary(self, group, node, _offer):
        from .apothecary_hub_screen import ApothecaryHubScreen
        self.scene = ApothecaryHubScreen(self.ui_fonts, self.guild, group,
                                         on_done=self._after_activity)

    def _open_stables(self, group):
        from .stables_screen import StablesScreen
        self.scene = StablesScreen(self.ui_fonts, self.guild, group, on_done=self._after_activity)

    def _open_library(self, group, node, _offer):
        from .library_hub_screen import LibraryHubScreen
        self.scene = LibraryHubScreen(self.ui_fonts, self.guild, group, node,
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
                        daylight=False, lethal=True, clock_day=self.guild.clock.day)
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = None
        self._enter_battle(battle, node)

    # ------------------------------------------------------------------ #
    # the guard: a jurisdiction node just caught someone (justice.py)     #
    # ------------------------------------------------------------------ #
    def _open_guard_check(self, group, order):
        caught = [u for u in group.members if u.uid in order.caught]
        self.scene = GuardScreen(self.ui_fonts, self.guild, group, order, caught,
                                 on_prison=self._resolve_guard_prison,
                                 on_flee=self._resolve_guard_flee,
                                 on_fight=self._start_guard_battle)

    def _resolve_guard_prison(self, group, order):
        self._map_notices += campaign.resolve_guard_prison(self.guild, group, order)
        self._after_activity()

    def _resolve_guard_flee(self, group, order):
        events, pause = campaign.resolve_guard_flee(self.guild, group, order)
        self._map_notices += events
        if pause is not None:          # re-caught, or ambushed, on the way back
            self._pending.insert(0, (group, pause))
        self._after_activity()

    def _start_guard_battle(self, group, order):
        caught = [u for u in group.members if u.uid in order.caught]
        crime = max((u.crime for u in caught), default=0)
        self._start_forced_battle(group, order, justice.patrol_pack(crime))

    # ------------------------------------------------------------------ #
    # the Old Road (or any other "unsafe" node): a pack found the group    #
    # first -- no choice, straight into a lethal fight (world.py). Set as  #
    # `self._pending_event` by `_after_activity`, resolved by a click on   #
    # MapScreen's own red CTA instead of a "press OK to fight" screen.     #
    # ------------------------------------------------------------------ #
    def _resolve_pending_event(self):
        group, order = self._pending_event
        self._pending_event = None
        self._start_ambush_battle(group, order)

    def _resolve_ambush_autowin(self, group, order, autowin_result):
        self._pending_event = None
        self._autosave(f"Before a fight at {world.node(group.node).name}: {len(order.pack)} foes (auto-resolved)")
        for u in group.members:
            avg_dmg = autowin_result.avg_damage.get(u.uid, 0.0)
            u.hp = max(1, u.hp - round(avg_dmg))

        node = world.node(group.node)
        scenario = node.scenario() if node.scenario else Scenario()
        battle = Battle(list(group.members), list(order.pack), scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=True, arena=False,
                        clock_day=self.guild.clock.day)
        for c in battle.enemy_units:
            c.hp = 0
            c.status = "dead"
        for c, u in zip(battle.player_units, group.members):
            c.status = "up"
            c.hp = u.hp
            c.combat_xp_earned = 0
        battle.winner = "player"
        battle.round_no = max(1, round(autowin_result.avg_rounds))

        self._battle_squad = list(group.members)
        self._battle_node = node
        self._arena_offer = None
        self._pause_order, self._pause_group = order, group
        self._battle_end(battle)

    def _start_ambush_battle(self, group, order):
        self._start_forced_battle(group, order, list(order.pack))

    # ------------------------------------------------------------------ #
    # a squatted City property (the `property` node function): the guard comes   #
    # to clear it out (campaign._property_raid_catch)                       #
    # ------------------------------------------------------------------ #
    def _start_property_raid(self, group, order):
        self._start_forced_battle(group, order, list(order.pack))

    # ------------------------------------------------------------------ #
    # a raid on a Wilds claim mid-SUSTAINING (campaign._wilds_claim_raid_check) #
    # ------------------------------------------------------------------ #
    def _start_wilds_raid(self, group, order):
        self._start_forced_battle(group, order, list(order.pack))

    # ------------------------------------------------------------------ #
    # Sistema 4: a seizure attempt once ESTABLISHED, and retaking a seized  #
    # claim (campaign._wilds_claim_seizure_check / _wilds_claim_retake_catch) #
    # ------------------------------------------------------------------ #
    def _start_wilds_seizure(self, group, order):
        self._start_forced_battle(group, order, list(order.pack))

    def _start_wilds_retake(self, group, order):
        self._start_forced_battle(group, order, list(order.pack))

    def _start_forced_battle(self, group, order, enemies):
        """A lethal fight the map forces on `group` rather than one the
        player picked -- the guard's patrol (`order.kind == "guard"`) or a
        road ambush (`"ambush"`). `order` is carried across to `_battle_end`
        via `self._pause_order`/`self._pause_group`, which reads `order.kind`
        to know which `campaign.resolve_*` finishes it."""
        node = world.node(group.node)
        self._battle_squad = list(group.members)
        self._battle_node = node
        self._arena_offer = None
        self._pause_order, self._pause_group = order, group
        # most jurisdiction/unsafe nodes (city/market/tavern/road) carry no
        # `scenario` -- nobody fought there before these systems made it necessary.
        scenario = node.scenario() if node.scenario else Scenario()
        battle = Battle(list(group.members), enemies, scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=True, arena=False,
                        clock_day=self.guild.clock.day)
        self._enter_battle(battle, node)

    # ------------------------------------------------------------------ #
    # hunting the wilds -- an activity that can spring a fight            #
    # ------------------------------------------------------------------ #
    def _open_hunt_ground(self, party, node, _offer, group=None, target="meat"):
        if group is not None and wagon_watch.needs_watch(group):
            label = "TRACK THE OX" if target == "ox" else "GO HUNTING"
            self.scene = WatchScreen(self.ui_fonts, group, node, label,
                                     on_confirm=lambda hunters, guarded: self._begin_hunt(hunters, node, group, guarded, target),
                                     on_back=self._after_activity)
        else:
            self._begin_hunt(party, node, group, True, target)

    def _begin_hunt(self, party, node, group, guarded, target="meat"):
        self._leave_outside(group, node, guarded)
        stance = group.stance if group is not None else NORMAL
        self._hunt = hunt.begin(self.guild, party, node, stance, target=target)
        self.scene = self._hunt_screen("setup")

    def _hunt_screen(self, phase, autowin=True):
        cls = TrackScreen if self._hunt.target == "ox" else HuntScreen
        return cls(self.ui_fonts, self.guild, self._hunt, phase=phase,
                   on_ambush=self._start_hunt_battle, on_done=self._end_hunt,
                   on_tick=self._hunt_tick,
                   on_autowin=self._resolve_hunt_autowin if autowin else None)

    def _hunt_tick(self, hours):
        """A hunt stretch spends hours outside the map's tick/orders loop --
        route it through `campaign.advance` (forced dt) so any OTHER group's
        order stays in lockstep with the clock instead of drifting out of
        sync with it, and anything that comes due for another group mid-hunt
        is queued in `_pending` (drained by `_after_activity` once the hunt
        wraps up) instead of silently lost."""
        result = campaign.advance(self.guild, dt=hours, busy=self._hunt.party)
        self._pending += result.pending
        return result.events

    def _start_hunt_battle(self, state, pack):
        self._battle_squad = list(state.party)
        self._battle_node = state.node
        self._arena_offer = None
        battle = Battle(state.party, pack, scenario=state.node.scenario(),
                        daylight=self.guild.clock.is_daylight,
                        lethal=state.node.lethal, arena=False,
                        clock_day=self.guild.clock.day)
        self._enter_battle(battle, state.node)

    def _resolve_hunt_autowin(self, state, pack, autowin_result):
        self._autosave(f"Before a fight at {state.node.name}: {len(pack)} foes (auto-resolved)")
        for u in state.party:
            avg_dmg = autowin_result.avg_damage.get(u.uid, 0.0)
            u.hp = max(1, u.hp - round(avg_dmg))

        battle = Battle(state.party, pack, scenario=state.node.scenario(),
                        daylight=self.guild.clock.is_daylight,
                        lethal=state.node.lethal, arena=False,
                        clock_day=self.guild.clock.day)
        for c in battle.enemy_units:
            c.hp = 0
            c.status = "dead"
        for c, u in zip(battle.player_units, state.party):
            c.status = "up"
            c.hp = u.hp
            c.combat_xp_earned = 0
        battle.winner = "player"
        battle.round_no = max(1, round(autowin_result.avg_rounds))

        self._battle_squad = list(state.party)
        self._battle_node = state.node
        self._arena_offer = None
        self._battle_end(battle)

    def _resume_hunt(self):
        """Back from a won ambush with daylight still to spend."""
        self._save()
        self.scene = self._hunt_screen("interlude")

    def _finish_hunt(self):
        """The hunt is over (dark, driven off, or the party is spent) -- the
        screen banks the haul on entering its wrap-up phase."""
        self._save()
        self.scene = self._hunt_screen("done", autowin=False)

    def _end_hunt(self):
        self._hunt = None
        self._back_from_outside()
        if self.guild.empty:
            self._campaign_over()
        else:
            self._after_activity()

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
        self.scene = TavernaScreen(self.ui_fonts, self.guild, party, node,
                                   on_done=self._after_activity, group=group)

    def _open_prison(self, party, node, _offer):
        from .prison_screen import PrisonScreen
        self.scene = PrisonScreen(self.ui_fonts, self.guild, party, node,
                                  on_done=self._after_activity)

    def _start_battle(self, squad, node, offer=None):
        self._battle_squad = squad
        self._battle_node = node
        self._arena_offer = offer
        if offer:
            economy.charge_richest_first(self._arena_purse or squad, offer.entry * len(squad))
        enemies, scenario = matchup.build(node, offer, squad_size=len(squad),
                                          guild=self.guild)
        battle = Battle(squad, enemies, scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=node.lethal,
                        arena=node.arena, clock_day=self.guild.clock.day)
        self._enter_battle(battle, node)

    def _start_title_defense(self, node):
        """A due title challenge: the champion alone against one scaled newcomer."""
        champ = arena.champion_of(self.guild)
        offer = arena.defense_bout()
        self._battle_squad = [champ]
        self._battle_node = node
        self._arena_offer = offer
        enemies, scenario = matchup.build(node, offer, squad_size=1, guild=self.guild)
        battle = Battle([champ], enemies, scenario=scenario,
                        daylight=self.guild.clock.is_daylight, lethal=False, arena=True,
                        clock_day=self.guild.clock.day)
        self._enter_battle(battle, node)

    def _leave_outside(self, group, node, guarded):
        self._left_outside = (group, node, guarded) if group is not None and wagon_watch.needs_watch(group) else None

    def _back_from_outside(self):
        """The party is out again: roll for the wagon it left at the door. Silent on purpose."""
        left, self._left_outside = self._left_outside, None
        if left is not None:
            wagon_watch.leave_outside(*left)

    def _enter_battle(self, battle, node):
        """Every fight starts here: snapshot the world first, so a bad one can be undone."""
        self._autosave_before(battle, node)
        recorder.before_fight(self._battle_squad)
        self._log_fight(battle, node)
        self.scene = BattleScreen(self.ui_fonts, battle, on_battle_end=self._battle_end)

    def _log_fight(self, battle, node):
        """With the play recorder on, the fight's decisions go to `combat_logs/` in the world folder."""
        offer, pause = self._arena_offer, self._pause_order
        kind = pause.kind if pause is not None else "hunt" if self._hunt is not None else (
            offer.name if offer else node.id)
        day = self.guild.clock.day
        path = recorder.combat_log_path(f"d{day:03d}-{combat_lab.slug(f'{node.id}-{kind}')}")
        if path is not None:
            battle.record_to(CombatLog(path, {"source": "campaign", "node": node.id, "kind": kind, "day": day},
                                       {"player": "human", "enemy": "ai"}))

    def _autosave_before(self, battle, node):
        foes = len(battle.enemy_units)
        self._autosave(f"Before a fight at {node.name}: {foes} foe{'s' if foes != 1 else ''}")

    def _autosave(self, label):
        persist.save_game(self.world, self.guild, kind="auto", label=label)

    def _battle_end(self, battle):
        hunt_state = self._hunt
        pause_order, pause_group = self._pause_order, self._pause_group
        was_champion_bout = bool(self._arena_offer and getattr(self._arena_offer, "champion", False))
        battle_node = self._battle_node
        offer = self._arena_offer
        outcome = campaign.absorb_battle(self.guild, self._battle_squad, battle,
                                         node=self._battle_node,
                                         arena_offer=offer)
        node_id = getattr(battle_node, "id", None)
        if pause_order is not None:
            fight_kind = pause_order.kind
        elif hunt_state is not None:
            fight_kind = "hunt"
        else:
            fight_kind = offer.name if offer else node_id
        recorder.emit("fight", node=node_id, kind=fight_kind,
                      won=outcome.won, squad=outcome.squad_size, deaths=len(outcome.fallen),
                      foes=len(battle.enemy_units), xp=sum(outcome.xp_awards.values()),
                      level=round(sum(u.combat_level for u in self.guild.roster)
                                  / max(1, len(self.guild.roster)), 2))
        self._battle_squad = []
        self._battle_node = None
        self._arena_offer = None
        if pause_group is not None:           # the fight is over: a save from here on must not replay it
            pause_group.pending = None
        note = outcome.arena_title_event
        if hunt_state is None:
            self._back_from_outside()

        if outcome.campaign_over:             # full wipe: campaign over
            self._left_outside = None
            self._hunt = None
            self._pause_order = self._pause_group = None
            self._campaign_over()
            return

        def after_arena_reward():
            if was_champion_bout and outcome.won and not any(u.name.startswith("Adelio") for u in self.guild.roster):
                self._prompt_recruit_adelio(outcome.survivors, battle_node)
            else:
                self._after_activity()

        if self._claim_stage_pending is not None:   # a deliberate Wilds claim fight (CLEAR/SWEEP)
            stage, self._claim_stage_pending = self._claim_stage_pending, None
            if outcome.won:
                {"CLEARED": self.guild.wilds_claim_mark_cleared,
                 "SWEPT": self.guild.wilds_claim_mark_swept}[stage]()
                self._map_notices.append(f"The Wilds claim advances -- now {stage.title()}.")
            else:
                self._map_notices.append("The attempt fails -- the claim's stage is unchanged.")
            # falls through to the normal loot/`_after_activity` handling below --
            # a claim fight is never a pause_order/hunt/arena bout

        def do_next_step():
            if pause_order is not None:            # a forced battle: the guard's patrol, or an ambush
                self._pause_order = self._pause_group = None
                resolver = self._FORCED_FIGHT_RESOLVERS.get(pause_order.kind)
                if resolver:
                    self._map_notices += resolver(self.guild, pause_group, pause_order, outcome)
                else:
                    self._map_notices += campaign.resolve_road_ambush(self.guild, pause_group, pause_order)
                if outcome.loot_pool and outcome.survivors:
                    self._save()
                    self.scene = LootScreen(self.ui_fonts, self.guild, outcome.survivors,
                                            outcome.loot_pool, on_done=self._after_activity)
                    return
                self._after_activity()
                return

            if hunt_state is not None:            # an ambush during a hunt
                hunt_state.party = [u for u in outcome.survivors if u in self.guild.roster]
                won = battle.winner == "player"
                if hunt_state.target == "ox":
                    hunt_state.hours_left = 0          # one chase per trail found
                    if won:
                        missions.slay_ox(self.guild)
                resume = won and hunt_state.party and hunt_state.hours_left > 0
                step = self._resume_hunt if resume else self._finish_hunt

                def nxt():
                    if hunt_state.biwolf and missions.fail_if_leather_lost(self.guild):
                        self._map_notices.append(
                            "The Biwolf's leather is lost -- the tanner's job is failed for good.")
                    if hunt_state.target == "ox" and won:
                        self._map_notices.append("Aurochs, the immortal ox, is dead.")
                        if missions.fail_if_hide_lost(self.guild):
                            self._map_notices.append(
                                "The hide is lost -- the tanner's job is failed for good.")
                    step()
                if outcome.loot_pool and outcome.survivors:
                    self._save()
                    self.scene = LootScreen(self.ui_fonts, self.guild, outcome.survivors,
                                            outcome.loot_pool, on_done=nxt)
                    return
                nxt()
                return

            if outcome.arena_reward is not None:  # arena bout won: hand out the purse
                self._save()
                self.scene = RewardScreen(self.ui_fonts, self.guild, outcome.survivors,
                                          outcome.arena_reward, on_done=after_arena_reward,
                                          deeds=outcome.deeds_earned, note=note)
                return

            if note:                             # lost defense / vacant title: no purse screen
                self._map_notices.append(note)

            if outcome.loot_pool and outcome.survivors:
                self._save()
                self.scene = LootScreen(self.ui_fonts, self.guild, outcome.survivors,
                                        outcome.loot_pool, on_done=self._after_activity)
                return
            self._after_activity()

        alerts = []
        if outcome.fallen:
            msgs = [f"{u.name} was killed in combat." for u in outcome.fallen]
            alerts.append(("DEATH ALERT", msgs, True))
        if outcome.stabilized:
            msgs = [f"{u.name} was stabilized and survived unconscious." for u in outcome.stabilized]
            alerts.append(("STABILIZED", msgs, False))
        if getattr(outcome, "leveled_up", None):
            msgs = [f"{u.name} reached combat level {u.combat_level}!" for u in outcome.leveled_up]
            alerts.append(("LEVEL UP!", msgs, False))
            self._map_notices += msgs

        def run_alert(idx):
            if idx >= len(alerts):
                do_next_step()
                return
            title, msgs, is_danger = alerts[idx]
            from .alert_screen import AlertScreen
            self.scene = AlertScreen(self.ui_fonts, self.scene, title, msgs,
                                     on_done=lambda: run_alert(idx + 1),
                                     is_danger=is_danger)

        if alerts:
            run_alert(0)
        else:
            do_next_step()

    def _prompt_recruit_adelio(self, survivors, node):
        from . import arena
        from .adelio_prompt_screen import AdelioPromptScreen
        from .taverna_screen import TavernaScreen
        def do_recruit():
            adelio = arena.load_champion()
            adelio.arena_title = False
            adelio.arena_role = None
            adelio.side = "player"
            self.scene = TavernaScreen(self.ui_fonts, self.guild, survivors, node,
                                       on_done=self._after_activity,
                                       candidates=[adelio], title="RECRUIT ADELIO")
        self.scene = AdelioPromptScreen(self.ui_fonts, on_recruit=do_recruit, on_leave=self._after_activity)

    # ------------------------------------------------------------------ #
    def _toggle_pause(self):
        """Esc: into / out of the pause menu. On the main menu Esc quits; there
        is no in-game quick exit -- leaving is a deliberate step from the menu."""
        if isinstance(self.scene, PauseScreen):
            self._resume_from_pause()
        elif isinstance(self.scene, MenuScreen):
            self._running = False
        else:
            self.scene = PauseScreen(self.ui_fonts, self.scene,
                                     on_resume=self._resume_from_pause,
                                     on_menu=self._pause_to_menu,
                                     on_quit=self._quit,
                                     tutorial=self.tutorial,
                                     on_tutorial_toggle=self._toggle_tutorial,
                                     on_tutorial_reset=self._reset_tutorial,
                                     on_save_as=self._save_as,
                                     can_save=self._can_save())

    def _save_as(self, name):
        persist.save_game(self.world, self.guild, kind="manual", label=name)

    def _resume_from_pause(self):
        if isinstance(self.scene, PauseScreen):
            self.scene = self.scene.resume_to

    def _pause_to_menu(self):
        if self._can_save():
            self._save()
        self._start_menu()

    def _quit(self):
        self._running = False

    def _toggle_tutorial(self):
        self.tutorial.enabled = not self.tutorial.enabled
        if self.guild is not None:
            self._save()

    def _reset_tutorial(self):
        self.tutorial.reset()
        if self.guild is not None:
            self._save()

    # ------------------------------------------------------------------ #
    def _tutorial_click(self, event):
        """True if this click was spent on the tutorial `?` badge instead of
        reaching the scene -- checked against LAST frame's rects (`run`
        computes this frame's only after events are handled; the one-frame lag
        is invisible at 60 fps). `_tutorial_rect_scene` guards against a scene
        swap mid-batch (one event switches `self.scene`, e.g. a footer button,
        and a later event in the same `pygame.event.get()` batch would
        otherwise be checked against the OLD scene's rects): once the scene
        no longer matches, those rects are treated as absent for this event
        rather than possibly matching a same-position widget on the new one."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self._tutorial_rect_scene is not self.scene:
            return False
        key = self.scene.tutorial_key()
        if key is None:
            return False
        if self._tutorial_badge_rect and self._tutorial_badge_rect.collidepoint(event.pos):
            self.tutorial.reopen(key)
            self._debounce_tutorial_click()
            return True
        return False

    def _debounce_tutorial_click(self):
        self._tutorial_block_until = pygame.time.get_ticks() + TUTORIAL_DEBOUNCE_MS
        self._tutorial_swallow_up = True

    def _tutorial_swallow(self, event):
        """True if `event` must not reach the scene: a click or key while a
        tutorial card is up (it is dismissed by a click or Enter/Space),
        and any click inside the debounce window after a dismissal -- plus the
        release of the dismissing press -- so closing a card never also presses
        whatever was underneath it. Esc is left to `run`."""
        mouse = (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)
        if event.type == pygame.MOUSEBUTTONUP and self._tutorial_swallow_up:
            self._tutorial_swallow_up = False
            return True
        if event.type in mouse and pygame.time.get_ticks() < self._tutorial_block_until:
            return True
        key = self.scene.tutorial_key()
        if (key is None or self._tutorial_rect_scene is not self.scene
                or not self.tutorial.should_show(key)):
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.tutorial.dismiss(key)
            self._debounce_tutorial_click()
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE):
            self.tutorial.dismiss(key)
            return True
        return event.type in mouse or event.type == pygame.KEYDOWN

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
                elif self._tutorial_swallow(event) or self._tutorial_click(event):
                    pass
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)
            self.window.fill(T.TABLE)
            self.scene.draw(self.window)          # every scene draws at real window size
            self._tutorial_card_rect, self._tutorial_badge_rect = tutorial_card.draw(
                self.window, self.ui_fonts, self.scene, self.tutorial)
            self._tutorial_rect_scene = self.scene
            pygame.display.flip()
        pygame.quit()
