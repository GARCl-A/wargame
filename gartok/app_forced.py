"""Fights nobody chose: the guard, ambushes, raids, seizures and the Claim stages.

Mixed into `app.App`. What each forced event is lives in `forced.py`; `FORCED_PLAYERS` is how
`app` plays each `ForcedEvent.play`, read into `App._ACTIVITY_OPENERS`."""

from . import (
    economy,
    encounters,
    forced,
    justice,
    world,
)
from .battle import Battle
from .justice_screen import GuardScreen
from .scenario import Scenario


class ForcedFightsMixin:
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
                        clock_day=self.guild.clock.day, aggressor="player")
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
        self._map_notices += forced.resolve_guard_prison(self.guild, group, order)
        self._after_activity()

    def _resolve_guard_flee(self, group, order):
        events, pause = forced.resolve_guard_flee(self.guild, group, order)
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
        self._start_forced_battle(group, order, list(order.pack))

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

    def _start_forced_battle(self, group, order, enemies):
        """A lethal fight the map forces on `group` rather than one the player picked.
        `order` is carried across to `_battle_end` via `self._pause_order`/`self._pause_group`,
        which settles it through `forced.resolve`."""
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
                        clock_day=self.guild.clock.day, aggressor="enemy")
        self._enter_battle(battle, node)


# ForcedEvent.play -> opener(app, group, node, order)
FORCED_PLAYERS = {
    "battle": lambda s, g, n, o: s._start_forced_battle(g, o, list(o.pack)),
    "map": lambda s, g, n, o: s._land_on_map_paused(g, o),
    "guard": lambda s, g, n, o: s._open_guard_check(g, o),
}
