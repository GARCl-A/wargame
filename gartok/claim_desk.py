"""The Wilds Claim's work with no window: scouting, the Lumber hauled for the fences and the fences raised, the
garrison and its job, the hearth (campfire or oven), and the Lumber the garrison banks. The two fights (CLEAR,
SWEEP) are the front-end's to play (`guild_claim` says what they are). pygame's `WildsClaimScreen` and
`web/claim_tab.py` are the windows over `ClaimDesk`.
"""

from . import economy, items, orders


class ClaimDesk:
    def __init__(self, guild, group):
        self.guild, self.group = guild, group
        self.notice = None

    def _carriers(self):
        return [*self.group.members, *self.group.wagons, *self.group.herd]

    def _party_lumber(self):
        return sum(m.count_of("Lumber") for m in self._carriers())

    def _deposit_lumber(self):
        total = 0
        for m in self._carriers():
            n = m.count_of("Lumber")
            if n:
                m.remove_named("Lumber", n)
                total += n
                m._derive_combat()
        if total:
            self.guild.wilds_claim_deposit_lumber(total)
            self.notice = f"deposited {total} Lumber toward the fences."
        else:
            self.notice = "nobody here is carrying Lumber."

    def _collect_lumber(self):
        stock = self.guild.garrison_stock.setdefault(self.group.node, [])
        taken = 0
        for m in self.group.members:
            while stock and m.load + items.item_weight("Lumber") <= m.carry_max:
                stock.pop()
                m.give_to_pack("Lumber")
                m._derive_combat()
                taken += 1
        self.notice = (f"collected {taken} Lumber." if taken
                       else "no room to carry any Lumber right now.")

    def _scout(self):
        events, _ = self.guild.pass_time(economy.WILDS_CLAIM_SCOUT_HOURS, busy=self.group.members)
        self.guild.wilds_claim_scout()
        self.notice = "  ".join(["the land is scouted -- ready to clear."] + events)

    def _build_fences(self):
        if self.guild.wilds_claim_fence_lumber < economy.WILDS_CLAIM_FENCE_LUMBER:
            return
        events, _ = self.guild.pass_time(economy.WILDS_CLAIM_FENCE_HOURS, busy=self.group.members)
        self.guild.wilds_claim_build_fences()
        self.notice = "  ".join(["the fences go up -- time to sweep the region."] + events)

    def _light_campfire(self):
        self._built(self.guild.wilds_claim_light_campfire(self.group.members)[1])

    def _build_oven(self):
        self._built(self.guild.claim_build_oven(self.group.members)[1])

    def _built(self, events):
        self.notice = "  ".join(events)
        for m in self.group.members:
            m._derive_combat()

    def _start_garrison(self):
        self.group.order = orders.garrison("lumber")
        self.guild.wilds_claim_start_sustaining()

    def _toggle_garrison_job(self):
        order = self.group.order
        if order is None or order.kind != "garrison":
            return
        order.job = "lumber" if order.job == "hold" else "hold"

    def _leave_garrison(self):
        if self.group.order is not None and self.group.order.kind == "garrison":
            self.group.order = orders.idle()
        self.notice = "the garrison stands down -- sustaining the claim starts over."
