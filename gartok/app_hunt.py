"""The hunt: ground, ticks, the ambush fight and how it ends.

Mixed into `app.App`; the dispatch tables that reach these live there."""

from . import (
    campaign,
    hunt,
    wagon_watch,
)
from .battle import Battle
from .group import NORMAL
from .hunt_screen import HuntScreen, TrackScreen
from .watch_screen import WatchScreen


class HuntFlowMixin:
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
        guards = [u for u in group.members if u not in party] if group is not None else []
        self._hunt = hunt.begin(self.guild, party, node, stance, target=target, guards=guards)
        self.scene = self._hunt_screen("setup")

    def _hunt_screen(self, phase, autowin=True):
        cls = TrackScreen if self._hunt.target == "ox" else HuntScreen
        return cls(self.ui_fonts, self.guild, self._hunt, phase=phase,
                   on_ambush=self._start_hunt_battle, on_done=self._end_hunt,
                   on_tick=self._hunt_tick,
                   on_autowin=self._resolve_hunt_autowin if autowin else None,
                   on_level=lambda u: self._open_level(
                       u, on_back=lambda: setattr(self, "scene", self._hunt_screen(phase, autowin=autowin))))

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
                        clock_day=self.guild.clock.day,
                        aggressor="player" if state.target == "ox" else "enemy")
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
            c.combat_xp_earned = c.magic_xp_earned = 0
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
