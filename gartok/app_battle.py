"""Entering a battle and settling it: loot, deeds, deaths, recruit offers.

Mixed into `app.App`; the dispatch tables that reach these live there."""

from . import (
    arena,
    battlefield,
    campaign,
    combat_lab,
    economy,
    factions,
    forced,
    matchup,
    missions,
    necromancer,
    persist,
    recorder,
    vocations,
    wagon_watch,
    wildfire,
)
from .battle import Battle
from .battle_screen import BattleScreen
from .combat_log import CombatLog
from .dialogue_screen import DialogueScreen
from .loot_screen import LootScreen
from .reward_screen import RewardScreen
from .taverna_screen import TavernaScreen


class BattleFlowMixin:
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
        talk = arena.boss_talk(self.guild, offer)
        if talk is not None:
            self.guild.boss_talks_seen.add(arena.boss_talk_key(offer))
            self.scene = DialogueScreen(self.ui_fonts, self.guild, self.guild.group_of(squad[0]), talk,
                                        lambda _result: self._enter_battle(battle, node), decided=talk.current())
            return
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
        battle.intel.bind("player", self.guild.bestiary, vocations.info_bonus(self.guild))
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
        was_boss_bout = bool(self._arena_offer and getattr(self._arena_offer, "boss", False))
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
        self._map_notices += outcome.captive_notes
        if self._skirmish is not None:
            if self._skirmish.template_id == missions.FAITH_NECROMANCER.id:
                notice, deeds = missions.settle_necromancer(self.guild, self._skirmish,
                                                            necromancer.errand_met(battle))
            else:
                notice, deeds = missions.settle_battlefield(self.guild, self._skirmish, outcome.won,
                                                            battlefield.soldiers_lost(battle))
            self._skirmish = None
            self._map_notices.append(notice)
            self._map_notices += [factions.deed_notice(d) for d in deeds]
        if self._wildfire_node is not None:
            self._map_notices += wildfire.settle_fight(self.guild, self._wildfire_node, outcome.won)
            self._wildfire_node = None
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
            elif was_boss_bout and outcome.won:
                self._prompt_recruit_ribbits(outcome.survivors, battle_node)
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
                self._map_notices += forced.resolve(self.guild, pause_group, pause_order, outcome)
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
        def do_recruit():
            adelio = arena.load_champion()
            adelio.arena_title = False
            adelio.arena_role = None
            adelio.side = "player"
            self.scene = TavernaScreen(self.ui_fonts, self.guild, survivors, node,
                                       on_done=self._after_activity,
                                       candidates=[adelio], title="RECRUIT ADELIO")
        self.scene = AdelioPromptScreen(self.ui_fonts, on_recruit=do_recruit, on_leave=self._after_activity)

    def _prompt_recruit_ribbits(self, survivors, node):
        from . import arena
        from .ribbit_prompt_screen import RibbitPromptScreen
        def do_recruit():
            candidates = arena.load_ribbit_brothers()
            self.scene = TavernaScreen(self.ui_fonts, self.guild, survivors, node,
                                       on_done=self._after_activity,
                                       candidates=candidates, title="RECRUIT THE RIBBIT BROTHERS",
                                       hide_tabs=True)
        self.scene = RibbitPromptScreen(self.ui_fonts, on_recruit=do_recruit, on_leave=self._after_activity)
