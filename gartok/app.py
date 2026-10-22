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

from dataclasses import dataclass, field
from typing import ClassVar

import pygame

from . import (
    arena,
    campaign,
    combat_lab,
    forced,
    group_turn_screen,
    node_functions,
    orders,
    persist,
    recorder,
    settings,
    sound,
    tutorial_card,
    vocations,
    wildfire,
    world,
)
from .app_battle import BattleFlowMixin
from .app_forced import FORCED_PLAYERS, ForcedFightsMixin
from .app_hunt import HuntFlowMixin
from .app_nodes import NodeScreensMixin
from .battle_screen import BattleScreen
from .char_editor_screen import CharEditorScreen
from .combat_lab_screen import CombatLabScreen
from .combat_log import CombatLog
from .dialogue_screen import DialogueScreen
from .draft_screen import DraftScreen
from .editor_menu_screen import EditorMenuScreen
from .group_turn_screen import GroupTurnScreen
from .guild import Guild
from .guild_screen import GuildScreen
from .level_screen import LevelScreen
from .loot_screen import LootScreen
from .map_editor_screen import MapEditorScreen
from .map_screen import MapScreen
from .menu_screen import MenuScreen
from .pause_screen import PauseScreen
from .saves_screen import SavesScreen
from .settings_screen import SettingsScreen
from .start_screen import StartScreen
from .tutorial import TutorialState
from .ui.banner import set_player_color
from .ui.tokens import T
from .ui.tokens import fonts as ui_fonts
from .vocation_screen import VocationScreen
from .wiki_screen import WikiScreen

START_SIZE = (1212, 832)
TUTORIAL_DEBOUNCE_MS = 300      # clicks swallowed right after a tutorial card closes
SCENE_DEBOUNCE_MS = 250         # clicks swallowed right after landing back on the map


@dataclass
class ClockRun:
    """What one run of the clock left behind (`App._run_clock`)."""
    events: list = field(default_factory=list)
    casualties: list = field(default_factory=list)
    level_ups: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    idle: set = field(default_factory=set)     # gids that went idle on the last hop


def _pointer_hot():
    try:
        return pygame.mouse.get_cursor() == pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_HAND)
    except pygame.error:
        return False


class App(NodeScreensMixin, ForcedFightsMixin, HuntFlowMixin, BattleFlowMixin):
    _left_outside = None    # (group, node, guarded): a wagon waiting outside the node the party entered
    _skirmish = None        # the Faith Order's errand (a Mission) the Battlefield fight in flight decides
    _wildfire_node = None   # the focus or fortress (a node id) the wildfire fight in flight is at

    def __init__(self):
        pygame.init()
        sound.enable()
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
        self._scene_block_until = 0          # ms: swallow clicks right after scene transition
        self._start_screen()

    @property
    def tutorial(self):
        """The tutorial's state: the guild's own once there is one (so it
        saves/loads by slot), `_draft_tutorial` before that (draft.py has no
        guild yet to hold it on)."""
        return self.guild.tutorial if self.guild is not None else self._draft_tutorial

    # ------------------------------------------------------------------ #
    # campaign flow                                                      #
    # ------------------------------------------------------------------ #
    def _start_screen(self, notice=None):
        recorder.detach()
        self.scene = StartScreen(self.ui_fonts,
                                 on_continue=self._continue_latest_game,
                                 on_new=self._new_game,
                                 on_load=self._start_menu,
                                 on_editor=self._start_editor,
                                 on_settings=self._open_settings,
                                 on_wiki=self._open_wiki,
                                 on_quit=self._quit,
                                 notice=notice)

    def _continue_latest_game(self):
        worlds = persist.list_worlds()
        if worlds:
            self._continue_game(worlds[0]["world"])

    def _open_settings(self):
        self.scene = SettingsScreen(self.ui_fonts, on_back=self._start_screen)

    def _open_wiki(self):
        self.scene = WikiScreen(self.ui_fonts, on_back=self._start_screen)

    def _start_menu(self, notice=None):
        recorder.detach()
        self.scene = MenuScreen(self.ui_fonts, on_new=self._new_game,
                                on_continue=self._continue_game,
                                on_saves=self._open_saves,
                                on_delete=persist.delete_world,
                                on_editor=self._start_editor, notice=notice,
                                on_back=self._start_screen)

    def _open_saves(self, world_id):
        self.scene = SavesScreen(self.ui_fonts, world_id, on_load=self._continue_game,
                                 on_back=self._start_menu)

    def _start_editor(self):
        self.scene = EditorMenuScreen(self.ui_fonts,
                                      on_character=self._open_char_editor,
                                      on_scenario=self._open_map_editor,
                                      on_combat_lab=self._open_combat_lab,
                                      on_back=self._start_screen)

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
        wildfire.sync_world(self.guild)
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
        self._focus_gid = None
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
        taken inside one would load as if the fight had never happened. The boss's line
        comes after the bout's entry is paid, so it counts as the battle."""
        scene = self.scene.resume_to if isinstance(self.scene, PauseScreen) else self.scene
        boss_talk = isinstance(scene, DialogueScreen) and scene.encounter.kind == "boss"
        return (self.guild is not None and self._hunt is None
                and not isinstance(scene, BattleScreen) and not boss_talk)

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
        self._scene_block_until = pygame.time.get_ticks() + SCENE_DEBOUNCE_MS
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
                               on_abandon=self._abandon_broken,
                               on_cook=lambda g: self._open_kitchen(g, "CAMPFIRE COOKING", self._start_map),
                               on_dialogue=self._map_dialogue,
                               on_interactive=self._open_interactive)
        if self._map_notices:
            self.scene.notices = self._map_notices
            self._map_notices = []
        self._hand_over_map()

    def _hand_over_map(self):
        """The map lands on a band other than the one the player last had in view: say so."""
        m = self.scene
        group = m.selected
        if not self._turn_moved(group, first_counts=False):
            return
        ambushed = self._pending_event is not None and self._pending_event[0] is group
        action = "AMBUSHED -- FIGHT WHEN READY" if ambushed else "AWAITS ORDERS"
        self.scene = GroupTurnScreen(self.ui_fonts, self.guild, group, action,
                                     on_go=lambda: setattr(self, "scene", m), resume_to=m, danger=ambushed)

    @staticmethod
    def _activity_label(order):
        """The hand-over card's headline for a pending order: the node button's label, the
        forced event's, or the kind itself."""
        if order.kind in forced.EVENTS:
            return forced.EVENTS[order.kind].label or order.kind.upper()
        if order.kind == "arena":
            return "ENTER THE ARENA"
        return next((f.label for f in node_functions.FUNCTIONS.values()
                     if f.order_kind == order.kind and f.label), order.kind.replace("_", " ").upper())

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
            group.order = orders.travel(group, dest, vocations.travel_mult(self.guild, group))
            self._start_map()
            return

        def leave():
            self.guild.abandon_wagon(group, wagon)
            self._map_notices.append(f"{group.display_name} leaves its broken {wagon.kind.lower()} behind.")
            self._abandon_broken(group, dest)

        def manage():
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

    def _open_guild(self, tab="members"):
        self.scene = GuildScreen(self.ui_fonts, self.guild,
                                 on_back=self._start_map, on_level=self._open_level,
                                 on_manage=lambda g: self._open_group(g, back=self._open_guild), on_bank=self._open_vault_view,
                                 tab=tab)

    def _open_vault_view(self):
        from .bank_view_screen import BankViewScreen
        self.scene = BankViewScreen(self.ui_fonts, self.guild, on_done=self._open_guild)

    def _open_group(self, group, back=None):
        if group.fight_due:
            return
        from .group_screen import GroupScreen
        self.scene = GroupScreen(self.ui_fonts, self.guild, group, on_back=back or self._after_activity,
                                 on_tick=self._tick_outside_map,
                                 on_cook=lambda: self._open_kitchen(
                                     group, "CAMPFIRE COOKING",
                                     lambda: self._open_group(group, back=back)))
    def _open_level(self, unit, on_back=None):
        self.scene = LevelScreen(self.ui_fonts, unit,
                                 on_back=on_back or self._open_guild, on_change=self._save)

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
        if isinstance(self.scene, MapScreen):
            self._focus_gid = self.scene.selected.gid
        run = self._run_clock(dt)
        if run is None:
            return
        self._map_notices += run.events
        self._settle_run(run)

    def _run_clock(self, dt=None):
        """The loop behind `_advance`: returns a `ClockRun`, or None when the guild was wiped
        (the mourning is already on screen)."""
        run = ClockRun()
        while True:
            busy_before = {g.gid for g in self.guild.groups if g.busy}
            result = campaign.advance(self.guild, dt=dt)
            run.events += result.events
            run.casualties += result.casualties
            run.level_ups += result.level_ups
            if result.wiped:
                self._hunt = None
                self._mourn(run.casualties, self._campaign_over)
                return None
            run.pending = list(result.pending)
            run.idle = {g.gid for g in self.guild.groups if g.gid in busy_before and not g.busy}
            if dt is not None or result.pending:
                return run
            if run.idle or not any(g.busy for g in self.guild.groups):
                return run

    def _settle_run(self, run, nxt=None):
        self._pending = run.pending
        self._report_casualties(
            run.casualties,
            lambda: self._chain_level_ups(run.level_ups, nxt or self._after_activity),
        )

    def _work_shift(self, group, order):
        """WORK on a work node's tab: the clock runs as the map's would, and the tab stays up
        when the shift's end is all that stopped it. Anything else that falls due on the way
        (another group idle, a fight, a death) plays out on the map's usual path, the shift
        still running there. With another group still idle the clock waits for its order,
        as it does on the map."""
        hub = self.scene
        group.order = order
        self._focus_gid = group.gid
        if self.guild.needs_orders:
            self._start_map()
            return
        run = self._run_clock()
        if run is None:
            return
        if group.busy or run.pending or run.casualties or run.idle - {group.gid}:
            self._map_notices += run.events
            self._settle_run(run)
            return
        self._save()
        hub.active_screen().report = run.events

        def back():
            self.scene = hub
        self._settle_run(run, back)

    def _chain_level_ups(self, level_ups, nxt):
        from .level_up_screen import LevelUpScreen

        def step(i=0):
            if i >= len(level_ups):
                nxt()
                return
            lu = level_ups[i]

            def cont():
                step(i + 1)
            self.scene = LevelUpScreen(self.ui_fonts, lu, cont,
                                       on_talents=lambda: self._open_level(lu.unit, on_back=cont),
                                       index=i, total=len(level_ups))
        step()

    def _mourn(self, casualties, nxt):
        """A memorial card for each of `casualties` lost off the field, then `nxt`."""
        from . import aftermath, memorial_screen
        cards = [getattr(u, "memorial", None) or aftermath.starved(u, day=self.guild.clock.day)
                 for u in casualties]
        memorial_screen.chain(self, cards, nxt, resume_to=self.scene)

    def _report_casualties(self, casualties, nxt):
        """Whoever starved in the last stretch of clock: a memorial card each, then the loot
        screen for what they carried, then `nxt`. No popup for hunger itself --
        COMMAND's alert icon (map_screen._messages) covers it every frame the map is up."""
        if casualties:
            def show_starvation_loot():
                from . import loot
                pool = []
                for u in casualties:
                    pool += loot.worn_by(u) + loot.carried_by(u)
                if pool and self.guild.roster:
                    from .loot_screen import LootScreen
                    self.scene = LootScreen(self.ui_fonts, self.guild, self.guild.roster, pool, on_done=nxt)
                else:
                    nxt()

            self._mourn(casualties, show_starvation_loot)
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
            dead, self._screen_dead = self._screen_dead, ()
            self._mourn(dead, self._campaign_over)
        return result.events, result.casualties

    def _map_dialogue(self, group, encounter, done):
        """A talk the map starts (a Wildfire focus): the dialogue screen, then back to that same
        map, which applies the result."""
        behind = self.scene

        def finish(result):
            self.scene = behind
            done(result)

        self.scene = DialogueScreen(self.ui_fonts, self.guild, group, encounter, on_done=finish)

    def _land_on_map_paused(self, group, order):
        # No more "AMBUSH! [FIGHT]" popup -- land back on the map with this
        # group paused (already idle, see forced.arrival_pause) and let
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
    _focus_gid = None                      # the group the player last had in view: the hand-over card fires off it

    # node function id (node_functions.FUNCTIONS) -> the screen that plays it
    _FUNCTION_OPENERS: ClassVar[dict] = {
        "shop": lambda s, g, n, o: s._open_market_stalls(list(g.members), n, None, group=g),
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
        "carpenter": lambda s, g, n, o: s._open_carpenter(g, n, None),
        "apothecary": lambda s, g, n, o: s._open_apothecary(g, n, None),
        "library": lambda s, g, n, o: s._open_library(g, n, None),
        "stable": lambda s, g, n, o: s._open_stables(g),
        "ancient_ruins": lambda s, g, n, o: s._enter_ancient_ruins(g, n),
        "serpents_nest": lambda s, g, n, o: s._enter_nest(g, n),
        "dragon_lair": lambda s, g, n, o: s._enter_lair(g, n),
        "skirmish": lambda s, g, n, o: s._enter_skirmish(g, n),
        "camp_fight": lambda s, g, n, o: s._enter_wildfire_fight(g, n),
        "ogre_fight": lambda s, g, n, o: s._enter_wildfire_fight(g, n),
        "shrine": lambda s, g, n, o: s._open_shrine(g, n),
    }

    # order.kind -> opener: the node functions' kinds, the arena and the forced events
    _ACTIVITY_OPENERS: ClassVar[dict] = {
        **{node_functions.FUNCTIONS[fid].order_kind: opener
           for fid, opener in _FUNCTION_OPENERS.items()},
        "arena": lambda s, g, n, o: s._open_arena(g, n),
        **{kind: FORCED_PLAYERS[event.play] for kind, event in forced.EVENTS.items()},
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
                self._hand_over(group, order, lambda: handler(self, group, node, order))
            return
        self._start_map()

    def _turn_moved(self, group, first_counts=True):
        """Bring `group` into view; true when that moves the player off another group and
        there is more than one. `first_counts` False: nothing in view yet is no move."""
        moved = group.gid != self._focus_gid and (first_counts or self._focus_gid is not None)
        self._focus_gid = group.gid
        return moved and group_turn_screen.needed(self.guild)

    def _hand_over(self, group, order, go):
        """Open `group`'s pending screen, behind a hand-over card when the clock moved the
        player off the group they had in view."""
        if not self._turn_moved(group):
            go()
            return
        behind = self.scene if isinstance(self.scene, MapScreen) else None
        self.scene = GroupTurnScreen(self.ui_fonts, self.guild, group, self._activity_label(order), go,
                                     resume_to=behind, danger=order.kind in forced.EVENTS)

    # ------------------------------------------------------------------ #
    def _toggle_pause(self):
        """Esc: into / out of the pause menu. On the main menu Esc quits; there
        is no in-game quick exit -- leaving is a deliberate step from the menu."""
        if isinstance(self.scene, PauseScreen):
            self._resume_from_pause()
        elif isinstance(self.scene, StartScreen):
            self._running = False
        elif isinstance(self.scene, (MenuScreen, SettingsScreen)):
            self._start_screen()
        elif isinstance(self.scene, WikiScreen):
            self.scene.handle_escape()
        else:
            self.scene = PauseScreen(self.ui_fonts, self.scene,
                                     on_resume=self._resume_from_pause,
                                     on_menu=self._pause_to_menu,
                                     on_quit=self._quit,
                                     tutorial=self.tutorial,
                                     on_tutorial_toggle=self._toggle_tutorial,
                                     on_tutorial_reset=self._reset_tutorial,
                                     on_save_as=self._save_as,
                                     can_save=self._can_save(),
                                     on_wiki=self._pause_to_wiki)

    def _pause_to_wiki(self):
        prev_scene = self.scene.resume_to if isinstance(self.scene, PauseScreen) else self.scene
        self.scene = WikiScreen(self.ui_fonts, on_back=lambda: self._return_to_scene(prev_scene))

    def _return_to_scene(self, scene):
        self.scene = scene

    def _save_as(self, name):
        persist.save_game(self.world, self.guild, kind="manual", label=name)

    def _resume_from_pause(self):
        if isinstance(self.scene, PauseScreen):
            self.scene = self.scene.resume_to

    def _pause_to_menu(self):
        if self._can_save():
            self._save()
        self._start_screen()

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
            self._dismiss_tutorial(key)
            self._debounce_tutorial_click()
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                          pygame.K_SPACE):
            self._dismiss_tutorial(key)
            return True
        return event.type in mouse or event.type == pygame.KEYDOWN

    def _dismiss_tutorial(self, key):
        """The map's card is the first one after the draft: its first close takes the
        player to the objectives instead of leaving them on an empty map."""
        first = key not in self.tutorial.seen
        self.tutorial.dismiss(key)
        if key == "map" and first and self.guild is not None:
            self._open_guild(tab="reputations")

    def _dispatch(self, event):
        """Hand `event` to the scene with its sounds: a click on something clickable (the hand
        cursor is up) clicks, and coins chink when the guild's money moved."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and _pointer_hot():
            sound.play("click")
        guild = self.guild
        before = guild.money if guild is not None else None
        self.scene.handle_event(event)
        if guild is not None and self.guild is guild and guild.money != before:
            sound.play("coins")

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
                elif (event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
                      and pygame.time.get_ticks() < self._scene_block_until):
                    pass
                else:
                    self._dispatch(event)

            self.scene.update(dt)
            self.window.fill(T.TABLE)
            self.scene.draw(self.window)          # every scene draws at real window size
            self._tutorial_card_rect, self._tutorial_badge_rect = tutorial_card.draw(
                self.window, self.ui_fonts, self.scene, self.tutorial)
            self._tutorial_rect_scene = self.scene
            pygame.display.flip()
        pygame.quit()
