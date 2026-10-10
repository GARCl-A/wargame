"""Paid work and crafting shifts, resolved right now against the campaign clock.

Mixed into `guild.Guild`. The tick/orders engine uses `_pay_shift` alone,
since it advances the clock itself.
"""

from collections import Counter

from . import economy, items, recorder, vocations, world
from .constants import fmt_money
from .unit_loadout import pooled_unlocked


class LaborMixin:
    def work_speedup(self, crew):
        """The clock-time multiplier a work shift actually takes: 1.0 unless
        someone on `crew` has Brisk Hands, in which case the whole guild moves
        on only once the SLOWEST worker is done -- so the saving lands only
        when nobody on the crew is dragging."""
        if not crew:
            return 1.0
        goblins = sum(1 for u in crew if u.race["name"] == "Goblin")
        mults = []
        for u in crew:
            speed = u.talent_bonus("activity_speed")
            if u.has_talent("swarm_logic"):
                speed += 0.10 * max(0, goblins - 1)
            mults.append(1 - speed)
        return max(mults)

    def work_shift(self, workers, hours, node_id="lumber_yard"):
        """A stint at a work node (the lumber yard outside the walls, the Mine), done right now:
        advances the campaign clock through `pass_time` (a long shift can cross
        midnight and run the daily meal -- a starving worker may not live to be
        paid) and then pays the crew. See `_pay_shift` for the pay/XP step alone
        (used by the tick/orders engine, which advances the clock itself)."""
        hours = int(hours)
        crew = [u for u in workers if u in self.roster]
        clock_hours = hours * self.work_speedup(crew)
        events, casualties = self.pass_time(clock_hours, busy=crew)
        events += self._pay_shift(workers, hours, clock_hours, node_id)
        return events, casualties

    def _pay_shift(self, workers, hours, clock_hours, node_id="lumber_yard"):
        """Pay + bank work-XP for a completed shift -- no clock advance, the
        caller already ran `pass_time`. `hours` is the nominal shift length
        (what pay/XP are based on); `clock_hours` is how long it actually took
        (Brisk Hands can shrink it), used only for the "done early" note."""
        earners = [u for u in workers if u in self.roster]   # a long shift can starve one
        paid = []
        events = []
        for u in earners:
            level = economy.work_level(u, node_id)
            pay = vocations.gather_pay(self, economy.work_pay(node_id, hours, level))
            paid.append(self._pay_worker(u, pay, hours, level, events))
        if earners:
            names = ", ".join(u.name for u in earners)
            wage = (f"+{fmt_money(paid[0])} each" if len(set(paid)) == 1
                    else f"+{fmt_money(sum(paid))} total")
            note = f"{world.node(node_id).name}: {names} worked {hours} h ({wage})."
            if clock_hours < hours:
                note += f"  Brisk Hands: crew done in {clock_hours:g} h."
            events.append(note)
        return events

    def _pay_worker(self, u, pay, hours, activity_level, events):
        """Pay `u` (coin_gain applies) and bank the work-XP, noting it in `events`.
        Returns the copper actually paid."""
        gain = round(pay * (1 + u.talent_bonus("coin_gain")))
        u.money += gain
        events += u.bank_work(hours, activity_level)
        return gain

    def perform_shift(self, performers, hours):
        """A show on the tavern stage, done right now: the clock runs through
        `pass_time`, then each performer is tipped by their own Charisma
        (an hourly Charisma test, `economy.perform_pay`). Anyone without an instrument sits it out."""
        hours = int(hours)
        crew = [u for u in performers if u in self.roster and economy.can_perform(u)]
        if not crew:
            return ["Nobody here has an instrument to play."], []
        clock_hours = hours * self.work_speedup(crew)
        events, casualties = self.pass_time(clock_hours, busy=crew)
        shows = []
        xp_lines = []
        for u in (u for u in crew if u in self.roster):     # a long show can starve one
            pay = economy.perform_pay(hours, u.mod_charisma)
            shows.append((u, self._pay_worker(u, pay, hours, economy.PERFORM_LEVEL, xp_lines)))
        if shows:
            tips = ", ".join(f"{u.name} {fmt_money(g)}" for u, g in shows)
            events.append(f"Tavern stage: played {hours} h ({tips}).")
            events += xp_lines
        return events, casualties

    def send_alone(self, group, unit, order, name):
        """Put `unit` on `order` apart from the rest of `group`: a lone group takes it as it is,
        a bigger one splits `unit` off into a group of their own. None, with nothing changed,
        when there is no free group slot for the split."""
        if len(group.members) == 1:
            ward = group
        elif self.free_slots:
            ward = self.split_group(group, [unit], name=name)
        else:
            return None
        ward.order = order
        return ward

    def craft_blocker(self, unit, recipe, pool):
        """Why `unit` cannot start or carry on crafting `recipe` from the packs of `pool`,
        or None when they can. Takes nothing."""
        if recipe not in items.CRAFTING_RECIPES:
            return f"Unknown recipe {recipe}."
        data = items.CRAFTING_RECIPES[recipe]
        lacking = items.missing_tools(data, pool)
        if lacking:
            return f"{unit.name} can't craft {recipe} -- needs a {', '.join(lacking)}."
        need = Counter(data["materials"])
        if unit.crafting_target != recipe and any(pooled_unlocked(pool, m) < q for m, q in need.items()):
            return f"{unit.name} can't craft {recipe} -- missing materials."
        return None

    def crafting_shift(self, unit, recipe, hours, pool=None):
        """A stint at the forge/workbench, done right now:
        advances the campaign clock through `pass_time` and rolls progress.
        `pool` is the units whose packs feed the craft as one (the crafter's
        own first); without it only the crafter's pack counts. Padlocked
        items are never used."""
        pool = [unit] + [u for u in pool or () if u is not unit]
        hours = int(hours)
        blocked = self.craft_blocker(unit, recipe, pool)
        if blocked:
            return [blocked], []
        worked, made, progress_total = self.craft_hours(unit, recipe, hours, pool)
        events, casualties = self.pass_time(worked * self.work_speedup([unit]), busy=[unit])
        return events + self.craft_report(unit, recipe, hours, worked, made, progress_total), casualties

    def craft_hours(self, unit, recipe, hours, pool):
        """Roll up to `hours` of crafting, starting a batch if none is under way and moving on to
        the next while materials last. Returns `(hours worked, batches made, progress rolled)`;
        the clock is the caller's."""
        if unit.crafting_target != recipe:
            self._start_batch(unit, recipe, pool=pool)
        progress_total = made = worked = 0
        for _ in range(hours):
            before = unit.crafting_progress
            p, done = unit.progress_crafting()
            worked += 1
            progress_total += p
            if not done:
                continue
            made += 1
            overflow = before + p - unit.crafting_goal(recipe)
            if not self._start_batch(unit, recipe, overflow, pool):
                break
        return worked, made, progress_total

    def craft_report(self, unit, recipe, hours, worked, made, progress_total):
        """Bank the work-XP of a craft and tell what came of it."""
        recipe_data = items.CRAFTING_RECIPES[recipe]
        events = unit.bank_work(worked, recipe_data.level)
        recorder.emit("craft", unit=unit.name, recipe=recipe, hours=worked, made=made * recipe_data.yield_qty)

        if made:
            total = made * recipe_data.yield_qty
            more = f" -- out of materials after {worked}h" if worked < hours and not unit.crafting_target else ""
            events.append(f"{unit.name} finished crafting: {recipe}"
                          f"{f' x{total}' if total > 1 else ''}!{more}")
        else:
            events.append(f"{unit.name} worked on {recipe} for {worked}h (+{progress_total} progress).")
        return events

    def _start_batch(self, unit, recipe, progress=0, pool=None):
        """Take one batch's materials from the `pool` of packs (the crafter's first) and begin
        it with `progress` carried over from the last batch. False, with every pack untouched,
        when the pool is missing any."""
        pool = pool or [unit]
        need = Counter(items.CRAFTING_RECIPES[recipe]["materials"])
        if any(pooled_unlocked(pool, mat) < qty for mat, qty in need.items()):
            return False
        for mat, qty in need.items():
            for holder in pool:
                qty -= holder.remove_named(mat, min(qty, holder.unlocked_of(mat)))
        unit.crafting_target = recipe
        unit.crafting_progress = progress
        return True
