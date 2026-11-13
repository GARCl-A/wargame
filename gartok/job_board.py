"""A giver's jobs board with no window: which jobs it shows, which are on offer, the leader signing for one,
the turn-in and its notice, each card's line and button. `Board` is what every giver shares; `TannerBoard`,
`ApothecaryBoard`, `LibraryBoard`, `ShrineBoard`, `TrustBoard` and `LedgerBoard` say what each one asks for and pays.
`web/jobs_tab.py` draws them.
"""

from . import factions, i18n, lair, missions, wildfire, world
from .constants import fmt_money

TAG_TONE = {"economic": "money", "trust": "money", "bankers": "money", "apothecary": "good", "ruins": "bad"}


def _item(name):
    return i18n.name("item", name)


def _item_names(names):
    return ", ".join(i18n.name("item", n) for n in names)


class Board:
    accept_label = "job_board.accept_job"

    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.notice = None

    def hub_cards(self):
        """The jobs board's cards: how many jobs are up, how many the guild holds here."""
        templates = self.get_templates()
        ids = {t.id for t in templates}
        held = sum(1 for m in self.guild.missions if m.template_id in ids and m.state == "active")
        purse = sum(u.money for u in self.group.members)
        return [{"label": i18n.t("job_board.jobs_on_board"), "value": str(len(templates))},
                {"label": i18n.t("job_board.taken"), "value": str(held)},
                {"label": i18n.t("job_board.party_purse"), "value": fmt_money(purse), "tone": "money"}]

    @property
    def subtitle_text(self):
        raise NotImplementedError

    def get_template(self):
        raise NotImplementedError

    def get_templates(self):
        """Every job the board shows, top to bottom. The default is the one
        `get_template` picks; a giver with several jobs at once overrides this."""
        t = self.get_template()
        return [] if t is None else [t]

    def get_req_str(self, t):
        raise NotImplementedError

    def get_status_str(self, t, progress, ready, days_left):
        raise NotImplementedError

    def get_turn_in_label(self, t, progress, ready):
        return i18n.t("job_board.turn_in") if ready else i18n.t("job_board.need_more", value=t.goal_qty - progress)

    def footer_action(self):
        """`(label, enabled)` for a second button beside the leave one (a keeper buying
        something), or None for none."""
        return

    def run_footer_action(self):
        """Press the footer action: -> the notice to show."""
        return

    def get_success_notice(self, reward):
        return i18n.t("job_board.paid_out_split_across_group", fmt_money=fmt_money(reward))

    @property
    def _template(self):
        """The first job on the board."""
        return next(iter(self.get_templates()), None)

    def _is_offered(self, t):
        """Whether `t` can be freshly accepted here right now
        (`missions.offers_at` -- the "one job out at a time" rule)."""
        return t in missions.offers_at(self.guild, self.group.node)

    def _active_of(self, t):
        """`t`'s job out right now, if any, regardless of who's holding it."""
        return next((m for m in self.guild.missions
                     if m.template_id == t.id and m.state == "active"), None)

    def _completed_of(self, t):
        return any(m.template_id == t.id and m.state in ("done", "failed")
                   for m in self.guild.missions)

    def _mission_of(self, t):
        """`t`'s active job, but only if the group standing here right now is
        the one sharing it (its signer is one of `self.group.members`)."""
        m = self._active_of(t)
        if m is None:
            return None
        return m if any(u.uid == m.unit_uid for u in self.group.members) else None

    @property
    def _offered(self):
        t = self._template
        return t is not None and self._is_offered(t)

    @property
    def _active(self):
        t = self._template
        return None if t is None else self._active_of(t)

    @property
    def _completed(self):
        t = self._template
        return t is not None and self._completed_of(t)

    @property
    def _mission(self):
        t = self._template
        return None if t is None else self._mission_of(t)

    def accept(self, t):
        """The leader signs for `t` when it is on offer here: -> whether they did."""
        if not self._is_offered(t):
            return False
        missions.accept(self.guild, self.group.leader, t)
        self.notice = None
        return True

    def turn_in(self, t):
        """Hand over `t`'s goal when this band holds the job and carries it: -> whether it was paid."""
        m = self._mission_of(t)
        if m is None or not missions.can_turn_in(self.guild, m):
            return False
        earned = missions.turn_in(self.guild, m)
        self.notice = self.get_success_notice(t.reward)
        if t.reward_recipe:
            self.notice += i18n.t("job_board.group_learns_to_craft", reward_recipe=t.reward_recipe)
        if t.reward_items:
            self.notice += i18n.t("job_board.you_are_given", reward_item=_item_names(t.reward_items))
        for d in earned:
            self.notice += "  ·  " + factions.deed_notice(d)
        return True

    def _job_button(self, t, m, lay):
        """`(key, label, enabled)` of the button at the foot of `t`'s card."""
        if m is not None:
            ready = lay["ready"]
            return ("turn_in", t.id), self.get_turn_in_label(t, lay["progress"], ready), ready
        offered = self._is_offered(t)
        wait = missions.retry_in(self.guild, t)
        if wait:
            label = i18n.plural("job_board.retry_in", wait)
        elif missions.closed(self.guild, t):
            label = i18n.t("job_board.failed_it_went_to_another")
        elif self._completed_of(t):
            done = any(x.template_id == t.id and x.state == "done" for x in self.guild.missions)
            label = i18n.t("job_board.job_completed") if done else i18n.t("job_board.job_failed")
        elif offered:
            label = i18n.t(self.accept_label)
        else:
            label = i18n.t("job_board.out_with_another_group")
        return ("accept", t.id), label, offered


class TannerBoard(Board):
    """The tanner: the group's **leader** signs (same "who speaks for the group" convention as market
    haggling), and the job then travels with that unit, not this group (see `missions.py`)."""
    GIVER = "tanner"
    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.tanner")

    def get_template(self):
        """The job to show: the one out right now, else the first still on offer, else
        the last one the guild took (a finished chain reads "JOB COMPLETED")."""
        mine = [t for t in missions.TEMPLATES.values()
                if t.giver == self.GIVER and t.node == self.group.node]
        on_offer = {t.id for t in missions.offers_at(self.guild, self.group.node)}
        out = {m.template_id for m in self.guild.missions if m.state == "active"}
        return (next((t for t in mine if t.id in out), None)
                or next((t for t in mine if t.id in on_offer), None)
                or next((t for t in reversed(mine)
                         if any(m.template_id == t.id for m in self.guild.missions)), None)
                or next(iter(mine), None))

    def get_req_str(self, t):
        pay = i18n.t("job_board.pay", fmt_money=fmt_money(t.reward)) if t.reward else ""
        due = i18n.t("job_board.no_deadline") if t.deadline_days is None else i18n.t("job_board.deadline_days", deadline_days=t.deadline_days)
        return i18n.t("job_board.goal_x", goal_qty=t.goal_qty, goal_item=_item(t.goal_item), pay=pay, due=due)

    def get_status_str(self, t, progress, ready, days_left):
        left = "" if days_left is None else i18n.t("job_board.day_s_left", days_left=days_left)
        return f"{progress} / {t.goal_qty} {_item(t.goal_item)}{left}"

    def get_success_notice(self, reward):
        if not reward:
            return i18n.t("job_board.tanner_takes_leather_and_puts")
        return super().get_success_notice(reward)


class ApothecaryBoard(Board):
    GIVER = "apothecary"
    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.apothecary")

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_req_str(self, t):
        if t.goal_any:
            return i18n.t("job_board.goal_venom_paid_in_recipe", goal_qty=t.goal_qty, deadline_days=t.deadline_days)
        return i18n.t("job_board.goal_x_pay_deadline_days", goal_qty=t.goal_qty, goal_item=_item(t.goal_item), fmt_money=fmt_money(t.reward), deadline_days=t.deadline_days)

    def get_status_str(self, t, progress, ready, days_left):
        if t.goal_any:
            return i18n.t("job_board.venom_glands_progress", progress=progress, goal_qty=t.goal_qty, days_left=days_left)
        return i18n.t("job_board.day_s_left_2", progress=progress, goal_qty=t.goal_qty, goal_item=_item(t.goal_item), days_left=days_left)

    def get_success_notice(self, reward):
        if reward:
            return super().get_success_notice(reward)
        return i18n.t("job_board.apothecary_shares_his_notes")


class LibraryBoard(Board):
    GIVER = "library"
    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.library")

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_req_str(self, t):
        if t.goal_item == "Any Dictionary":
            return i18n.t("job_board.goal_x_dictionary_unarchived_tongue", goal_qty=t.goal_qty, fmt_money=fmt_money(t.reward), deadline_days=t.deadline_days)
        return i18n.t("job_board.goal_x_pay_deadline_days", goal_qty=t.goal_qty, goal_item=_item(t.goal_item), fmt_money=fmt_money(t.reward), deadline_days=t.deadline_days)

    def get_status_str(self, t, progress, ready, days_left):
        item_label = _item("Dictionary" if t.goal_item == "Any Dictionary" else t.goal_item)
        return i18n.t("job_board.day_s_left_3", progress=progress, goal_qty=t.goal_qty, item_label=item_label, days_left=days_left)




class ShrineBoard(Board):
    """A hidden sanctuary's board: the school's keeper takes the Ancient Codex and whatever else that
    school asks for, the Snake Dragon among them."""
    accept_label = "job_board.take_task"

    @property
    def _giver(self):
        return next((t.giver for t in missions.TEMPLATES.values() if t.node == self.group.node), None)

    @property
    def subtitle_text(self):
        key = f"job_board.keeper.{self._giver}"
        return i18n.t(key) if i18n.has(key) else ""

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self._giver, self.group.node)

    def get_req_str(self, t):
        if t is missions.NATURE_WILDFIRE:
            return (i18n.t("job_board.goal_talk_ogre_round_or", deadline_days=t.deadline_days, REWARD=wildfire.REWARD))
        if t is missions.FAITH_NECROMANCER:
            return (i18n.t("job_board.goal_find_and_put_down", name=world.node(t.fight_at).name, deadline_days=t.deadline_days))
        if t.fight_at:
            goal = i18n.t("job_board.win_skirmish_at_every_soldier", name=world.node(t.fight_at).name)
            if t.starting_item and not any(m.template_id == t.id for m in self.guild.missions):
                goal += i18n.t("job_board.you_get_x", starting_qty=t.starting_qty, starting_item=_item(t.starting_item))
        else:
            goal = i18n.t("job_board.alive", goal_item=_item(t.goal_item)) if t.goal_captive else f"{t.goal_qty}x {_item(t.goal_item)}"
        due = i18n.t("job_board.days", deadline_days=t.deadline_days) if t.deadline_days else i18n.t("job_board.no_deadline")
        prize = i18n.t("job_board.you_get", reward_item=_item_names(t.reward_items)) if t.reward_items else ""
        return i18n.t("job_board.goal", goal=goal, due=due, prize=prize)

    def get_status_str(self, t, progress, ready, days_left):
        if t is missions.NATURE_WILDFIRE:
            state = self.guild.wildfire
            burned = i18n.t("job_board.burned", burned=state.burned) if state is not None and state.burned else ""
            due = i18n.t("job_board.day_s_left", days_left=days_left) if days_left is not None else ""
            return i18n.t("job_board.fires_burn_round_wilds", due=due, burned=burned)
        if t.fight_at:
            due = i18n.t("job_board.day_s_left", days_left=days_left) if days_left is not None else ""
            if t is missions.FAITH_NECROMANCER:
                return i18n.t("job_board.dead_rise_at_find_one", name=world.node(t.fight_at).name, due=due)
            return i18n.t("job_board.fight_at_lose_no_soldier", name=world.node(t.fight_at).name, due=due)
        return f"{progress} / {t.goal_qty} {_item(t.goal_item)}"

    def get_turn_in_label(self, t, progress, ready):
        if t.fight_at:
            return i18n.t("job_board.go_to", upper=world.node(t.fight_at).name.upper())
        return i18n.t("job_board.hand_it_over") if ready else i18n.t("job_board.need_more", value=t.goal_qty - progress)

    def get_success_notice(self, reward):
        return i18n.t("job_board.keeper_takes_it_and_speaks")

    def _egg_holder(self):
        if self._giver == "blood" and missions.pending_clutch(self.guild) is not None:
            return None                   # the first egg is the Cult's job here, not a sale
        return next((u for u in self.group.members if u.count_of(lair.EGG)), None)

    def footer_action(self):
        holder = self._egg_holder()
        if holder is None and not any(u.count_of(lair.EGG) for u in self.group.members):
            return None
        return i18n.t("job_board.sell_dragon_egg", SHRINE_EGG_PRICE=lair.SHRINE_EGG_PRICE), holder is not None

    def run_footer_action(self):
        holder = self._egg_holder()
        if holder is None:
            return None
        holder.remove_named(lair.EGG, 1)
        holder.money += lair.SHRINE_EGG_PRICE
        return i18n.t("job_board.keeper_weighs_egg_in_both", name=holder.name, SHRINE_EGG_PRICE=lair.SHRINE_EGG_PRICE)


class TrustBoard(Board):
    """The Bankers' test of trust: accepting hands the signer a sealed chest
    (`missions.TRUST_CHEST.starting_item`); the goal is the letter of receipt Field Command
    (`ledger.py`) trades for it once the band gets there safely."""
    TEMPLATE = missions.TRUST_CHEST
    accept_label = "job_board.accept_trust"
    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.trust")

    def get_template(self):
        return self.TEMPLATE

    def get_req_str(self, t):
        return i18n.t("job_board.carry_bring_back_deadline_days", starting_item=_item(t.starting_item), goal_item=_item(t.goal_item), deadline_days=t.deadline_days)

    def get_status_str(self, t, progress, ready, days_left):
        if ready:
            return i18n.t("job_board.in_hand_day_s_left", goal_item=_item(t.goal_item), days_left=days_left)
        return i18n.t("job_board.carrying_sealed_chest_to_ledger", days_left=days_left)

    def get_turn_in_label(self, t, progress, ready):
        return i18n.t("job_board.turn_in_letter") if ready else i18n.t("job_board.not_back_yet")

    def get_success_notice(self, reward):
        return i18n.t("job_board.bankers_accept_letter_your_trust")


class LedgerBoard(Board):
    """Field Command's one job, Commander Varkas's Treefolk mentorship: signing for it hands the band the
    recruit, and the turn-in is the recruit trained to racial level 2 and standing in this band."""
    GIVER = "ledger_hold"
    accept_label = "ledger.accept_recruit"

    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.ledger")

    def get_templates(self):
        for m in self.guild.missions:
            if m.template_id == missions.LEDGER_TREEFOLK.id and m.state == "active" and self._recruit(m) is None:
                m.state = "failed"
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def _recruit(self, mission):
        return next((u for u in self.guild.roster if u.uid == mission.recruit_uid), None)

    def accept(self, t):
        if not self._is_offered(t):
            return False
        recruit = missions.make_treefolk_recruit()
        self.guild.add_member(recruit, self.group)
        missions.accept_treefolk_mentorship(self.guild, self.group.leader, recruit)
        self.notice = i18n.t("ledger.treefolk_joins_your_group_for", name=recruit.name)
        return True

    def get_req_str(self, t):
        return i18n.t("ledger.offer_req", fmt_money=fmt_money(t.reward))

    def get_status_str(self, t, progress, ready, days_left):
        m = self._active_of(t)
        recruit = None if m is None else self._recruit(m)
        if recruit is None:
            return i18n.t("ledger.treefolk_recruit_fell_in_battle")
        return i18n.t("ledger.racial_level", lvl=recruit.racial_level)

    def get_turn_in_label(self, t, progress, ready):
        return i18n.t("ledger.deliver_recruit")

    def get_success_notice(self, reward):
        return i18n.t("ledger.recruit_steps_into_garrison", fmt_money=fmt_money(reward))


class FarmerBoard(Board):
    """The Farm's one job: Edric Ashvale's daughter. The goal is the girl herself, brought home alive."""
    GIVER = "farmer"

    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.farmer")

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_req_str(self, t):
        return i18n.t("job_board.farmer_req", deadline_days=t.deadline_days, fmt_money=fmt_money(t.reward),
                      reward_item=_item_names(t.reward_items))

    def get_status_str(self, t, progress, ready, days_left):
        return i18n.t("job_board.farmer_status", progress=progress, goal_qty=t.goal_qty, days_left=days_left)

    def get_turn_in_label(self, t, progress, ready):
        return i18n.t("job_board.hand_it_over") if ready else i18n.t("job_board.not_back_yet")

    def get_success_notice(self, reward):
        return i18n.t("job_board.farmer_thanks", fmt_money=fmt_money(reward))


class TavernBoard(Board):
    """The Tavern's one job: three Potatoes from the Farm. The innkeeper warns the band off eating them, which
    is the lesson: food in the pack is eaten by the day, so carry something else to eat on the way."""
    GIVER = "innkeeper"

    @property
    def subtitle_text(self):
        return i18n.t("job_board.subtitle.innkeeper")

    def get_template(self):
        return next(iter(self.get_templates()), None)

    def get_templates(self):
        return missions.board(self.guild, self.GIVER, self.group.node)

    def get_req_str(self, t):
        return i18n.t("job_board.tavern_req", goal_qty=t.goal_qty, deadline_days=t.deadline_days,
                      fmt_money=fmt_money(t.reward))

    def get_status_str(self, t, progress, ready, days_left):
        return i18n.t("job_board.tavern_status", progress=progress, goal_qty=t.goal_qty, days_left=days_left)

    def get_success_notice(self, reward):
        return i18n.t("job_board.tavern_thanks", fmt_money=fmt_money(reward))

    def accept(self, t):
        taken = super().accept(t)
        if taken:
            self.notice = i18n.t("job_board.tavern_warning")
        return taken


# a node's function -> its giver's board, in the order a node's tabs list them
BOARDS = (("innkeeper", TavernBoard), ("tanner", TannerBoard), ("apothecary", ApothecaryBoard), ("library", LibraryBoard),
          ("shrine", ShrineBoard), ("trust", TrustBoard), ("ledger", LedgerBoard), ("farmer", FarmerBoard))
