"""Paid work and crafting shifts, resolved right now against the campaign clock.

Mixed into `guild.Guild`. The tick/orders engine uses `_pay_shift` alone,
since it advances the clock itself.
"""

from collections import Counter

from . import economy, items, progression
from .constants import fmt_money


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

    def work_shift(self, workers, hours):
        """A stint at the lumber yard outside the walls, done right now:
        advances the campaign clock through `pass_time` (a long shift can cross
        midnight and run the daily meal -- a starving worker may not live to be
        paid) and then pays the crew. See `_pay_shift` for the pay/XP step alone
        (used by the tick/orders engine, which advances the clock itself)."""
        hours = int(hours)
        crew = [u for u in workers if u in self.roster]
        clock_hours = hours * self.work_speedup(crew)
        events, casualties = self.pass_time(clock_hours, busy=crew)
        events += self._pay_shift(workers, hours, clock_hours)
        return events, casualties

    def _pay_shift(self, workers, hours, clock_hours):
        """Pay + bank work-XP for a completed shift -- no clock advance, the
        caller already ran `pass_time`. `hours` is the nominal shift length
        (what pay/XP are based on); `clock_hours` is how long it actually took
        (Brisk Hands can shrink it), used only for the "done early" note."""
        earners = [u for u in workers if u in self.roster]   # a long shift can starve one
        paid = []
        events = []
        for u in earners:
            old_work_lvl = u.work_level
            level = economy.lumber_level(u)
            pay = economy.lumber_pay(hours, level)
            gain = round(pay * (1 + u.talent_bonus("coin_gain")))
            u.money += gain
            u.work_hours += progression.work_xp_hours(hours, level, u.work_level)
            u.collect_levels()                 # more work marks can lift the mean level
            paid.append(gain)
            if u.work_level > old_work_lvl:
                events.append(f"{u.name} reached work level {u.work_level}!")
        if earners:
            names = ", ".join(u.name for u in earners)
            wage = (f"+{fmt_money(paid[0])} each" if len(set(paid)) == 1
                    else f"+{fmt_money(sum(paid))} total")
            note = f"Lumber yard: {names} worked {hours} h ({wage})."
            if clock_hours < hours:
                note += f"  Brisk Hands: crew done in {clock_hours:g} h."
            events.append(note)
        return events

    def crafting_shift(self, unit, recipe, hours):
        """A stint at the forge/workbench, done right now:
        advances the campaign clock through `pass_time` and rolls progress."""
        hours = int(hours)
        if unit.crafting_target != recipe:
            if recipe not in items.CRAFTING_RECIPES:
                return [f"Unknown recipe {recipe}."], []
            if not self._start_batch(unit, recipe):
                return [f"{unit.name} can't craft {recipe} -- missing materials."], []

        recipe_data = items.CRAFTING_RECIPES[recipe]
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
            if not self._start_batch(unit, recipe, overflow):
                break

        clock_hours = worked * self.work_speedup([unit])
        events, casualties = self.pass_time(clock_hours, busy=[unit])

        old_work_lvl = unit.work_level
        unit.work_hours += progression.work_xp_hours(worked, recipe_data.get("level", 1), unit.work_level)
        unit.collect_levels()
        if unit.work_level > old_work_lvl:
            events.append(f"{unit.name} reached work level {unit.work_level}!")

        if made:
            total = made * recipe_data.yield_qty
            more = f" -- out of materials after {worked}h" if worked < hours and not unit.crafting_target else ""
            events.append(f"{unit.name} finished crafting: {recipe}"
                          f"{f' x{total}' if total > 1 else ''}!{more}")
        else:
            events.append(f"{unit.name} worked on {recipe} for {worked}h (+{progress_total} progress).")
        return events, casualties

    def _start_batch(self, unit, recipe, progress=0):
        """Take one batch's materials from `unit`'s pack and begin it with `progress` carried
        over from the last batch. False, with the pack untouched, when it is missing any."""
        need = Counter(items.CRAFTING_RECIPES[recipe]["materials"])
        if any(unit.count_of(mat) < qty for mat, qty in need.items()):
            return False
        for mat, qty in need.items():
            unit.remove_named(mat, qty)
        unit.crafting_target = recipe
        unit.crafting_progress = progress
        return True
