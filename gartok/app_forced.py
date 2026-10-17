"""Fights nobody chose: the guard, ambushes, raids, seizures and the Claim stages.

Mixed into `app.App`. What each forced event is lives in `forced.py`; `FORCED_PLAYERS` is how
`app` plays each `ForcedEvent.play`, read into `App._ACTIVITY_OPENERS`."""

from . import (
    dialogue,
    economy,
    encounters,
    forced,
    recorder,
    world,
)
from .battle import Battle
from .dialogue_screen import DialogueScreen
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
    # the talk before a forced fight (dialogue.py): the guard, ambushes    #
    # ------------------------------------------------------------------ #
    def _open_dialogue(self, group, order):
        """The foes talk first: the dialogue screen, or straight to the fight when nobody in the
        pack speaks. A talk already rolled (a reload) opens on its result."""
        enc = forced.encounter(self.guild, group, order)
        if enc is None:
            self._start_forced_battle(group, order, list(order.pack))
            return
        decided = dialogue.Result.from_dict(order.parley) if order.parley else None

        def decide(result):
            order.parley = result.to_dict()
            recorder.emit("talk", kind=order.kind, result=result.kind, paid=result.paid)

        self.scene = DialogueScreen(self.ui_fonts, self.guild, group, enc,
                                    on_done=lambda r: self._dialogue_done(group, order, r),
                                    on_decided=decide, decided=decided)

    def _dialogue_done(self, group, order, result):
        if result.kind == "fight":
            self._start_forced_battle(group, order, list(order.pack), opening=result.opening)
        elif result.kind == "surrender":
            self._resolve_guard_prison(group, order)
        elif result.kind == "leave":
            self._resolve_guard_flee(group, order)
        else:
            self._map_notices += [result.text, *forced.settle_talk(self.guild, group, order)]
            self._after_activity()

    def _resolve_guard_prison(self, group, order):
        self._map_notices += forced.resolve_guard_prison(self.guild, group, order)
        self._after_activity()

    def _resolve_guard_flee(self, group, order):
        events, pause = forced.resolve_guard_flee(self.guild, group, order)
        self._map_notices += events
        if pause is not None:          # re-caught, or ambushed, on the way back
            self._pending.insert(0, (group, pause))
        self._after_activity()

    # ------------------------------------------------------------------ #
    # the Old Road (or any other "unsafe" node): a pack found the group    #
    # first (world.py). Set as `self._pending_event` by `_after_activity`, #
    # resolved by a click on MapScreen's own red CTA: the talk, or the     #
    # fight when nobody in the pack speaks.                                #
    # ------------------------------------------------------------------ #
    def _resolve_pending_event(self):
        group, order = self._pending_event
        self._pending_event = None
        self._open_dialogue(group, order)

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
            c.combat_xp_earned = c.magic_xp_earned = 0
        battle.winner = "player"
        battle.round_no = max(1, round(autowin_result.avg_rounds))

        self._battle_squad = list(group.members)
        self._battle_node = node
        self._arena_offer = None
        self._pause_order, self._pause_group = order, group
        self._battle_end(battle)

    def _start_forced_battle(self, group, order, enemies, opening=None):
        """A lethal fight the map forces on `group` rather than one the player picked.
        `order` is carried across to `_battle_end` via `self._pause_order`/`self._pause_group`,
        which settles it through `forced.resolve`. `opening` is how the talk before it ended
        (`dialogue.Opening`)."""
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
        if opening is not None:
            battle.open_with(**opening.to_dict())
        self._enter_battle(battle, node)


# ForcedEvent.play -> opener(app, group, node, order)
FORCED_PLAYERS = {
    "battle": lambda s, g, n, o: s._start_forced_battle(g, o, list(o.pack)),
    "map": lambda s, g, n, o: s._land_on_map_paused(g, o),
    "talk": lambda s, g, n, o: s._open_dialogue(g, o),
}
