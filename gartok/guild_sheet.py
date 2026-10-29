"""The guild's sheet, with no pygame: the roster by band (its filters and folds), a member's
sheet (the weapon, the kit, the careers, the roles and what pressing one does), an animal's,
the charter (the bands, the notices, the holdings, the founding trade). A tone is a word
(`warn`, `bad`, `good`, or "" for plain). `web/guild_session.py` reads it.
"""

from . import magic, progression, recruit, rite, vocations, world
from .animals import STARVE_DAYS, Animal
from .constants import fmt_money
from .group import BASE_CAPACITY

FILTERS = (
    ("all", "ALL", "Every member of every group"),
    ("idle", "IDLE", "Groups waiting for orders"),
    ("busy", "BUSY", "Groups travelling, working or studying"),
    ("alerts", "ALERTS", "Members and animals that are hungry, or have a level-up waiting"),
)
ATTRIBUTE_LABELS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
                    ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))
FIGHT_DUE_TIP = "A fight is about to start -- this group can't change until it is over"


def node_label(node_id):
    if not isinstance(node_id, str):
        return "Camp"
    try:
        return world.node(node_id).name
    except KeyError:
        return node_id.replace("_", " ").title()


def is_idle(group):
    return group.order is None or group.order.kind == "idle"


def needs_attention(unit):
    return bool(unit.pending_picks) or unit.hunger_level >= 1 or unit.sick


def _days(n):
    return f"{n} day{'s' if n != 1 else ''}"


class GuildSheet:
    def __init__(self, guild):
        self.guild = guild
        self.roster = guild.roster
        pending = [u for u in self.roster if u.pending_picks]
        self.member = pending[0] if pending else (self.roster[0] if self.roster else None)
        self.collapsed_groups = set()
        self.filter_mode = "all"

    def _group_of(self, member):
        """The group holding a member -- or an animal of its herd."""
        if isinstance(member, Animal):
            return next((g for g in self.guild.groups if member in g.herd), None)
        return self.guild.group_of(member) if member is not None else None

    def _everyone(self):
        return [*self.roster, *(a for g in self.guild.groups for a in g.herd)]

    def _fight_due(self, unit):
        """The unit's group has a forced fight waiting: nothing about it may change."""
        group = self._group_of(unit)
        return group is not None and group.fight_due

    def _is_group_leader(self, unit):
        group = self.guild.group_of(unit)
        return group is not None and group.leader is unit

    def _recruited_by(self, unit):
        if not getattr(unit, "recruited_by", None):
            return None
        who = next((u for u in self.roster if u.uid == unit.recruited_by), None)
        return who.name if who else "someone long gone"

    def _press(self, key):
        m = self.member
        group = self._group_of(m)
        if m is None or isinstance(m, Animal):
            return
        if key == "share_food":
            m.share_food = not m.share_food
        elif key == "group_leader" and group:
            self.guild.set_group_leader(group, m)
        elif key == "guild_leader":
            self.guild.set_leader(m)
        elif key == "distribute" and group and len(group.members) > 1:
            group.distribute_load()

    # ------------------------------------------------------------------ #
    # the roster                                                          #
    # ------------------------------------------------------------------ #
    def _member_data(self, unit, selected):
        badges = []
        if unit.pending_picks:
            badges.append(("LEVEL UP", "warn"))
        if unit.hunger_level >= 1:
            badges.append(("HUNGRY", "bad"))
        if unit.sick:
            badges.append(("SICK", "bad"))
        if unit is self.guild.leader:
            badges.append(("GUILD LEADER", ""))
        elif self._is_group_leader(unit):
            badges.append(("GROUP LEADER", ""))
        return {
            "key": unit.uid, "name": unit.name, "selected": selected, "badges": badges,
            "sub": (f"{unit.race['name']} · Lv {unit.racial_level}"
                    f"  (C{unit.combat_level} W{unit.work_level})"),
            "hp": (max(0, unit.hp), unit.hp_max),
        }

    @staticmethod
    def _animal_data(animal, grp, selected):
        pulled = grp.pulling(animal)
        job = f"pulls {pulled.kind.lower()}" if pulled else animal.role or "no tack"
        return {
            "key": animal.uid, "name": animal.species, "selected": selected,
            "badges": [("HUNGRY", "bad")] if animal.unfed_days else [],
            "sub": f"{animal.species} · {job}", "hp": (max(0, animal.hp), animal.hp_max),
        }

    def _roster_bands(self):
        bands = []
        for grp in self.guild.groups:
            members = [m for m in grp.members if self._passes_filter(grp, m)]
            herd = [a for a in grp.herd if self._passes_filter(grp, a)]
            if not (members or herd) and self.filter_mode != "all":
                continue
            bands.append({
                "key": grp.gid, "name": grp.display_name, "where": node_label(grp.node),
                "collapsed": grp.gid in self.collapsed_groups, "count": len(members),
                "members": [self._member_data(m, m is self.member) for m in members]
                           + [self._animal_data(a, grp, a is self.member) for a in herd],
            })
        return bands

    def _passes_filter(self, grp, unit):
        mode = self.filter_mode
        if mode == "idle":
            return is_idle(grp)
        if mode == "busy":
            return not is_idle(grp)
        if mode == "alerts":
            return bool(unit.unfed_days) if isinstance(unit, Animal) else needs_attention(unit)
        return True

    # ------------------------------------------------------------------ #
    # a member's sheet                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _animal_work_rows(animal, pulled):
        if animal.role == "pack":
            role = f"carries up to {animal.capacity:g} kg on its back"
        elif animal.role == "draft":
            hitched = f" -- hitched to the {pulled.kind.lower()}" if pulled else " -- not hitched"
            role = f"pulls up to {animal.pull:g} kg{hitched}"
        else:
            role = (f"idle: a Pack Saddle lets it carry {animal.back_load:g} kg, "
                    f"a Harness lets it pull {animal.draw:g} kg")
        fed = ((f"hungry {animal.unfed_days} day(s) -- starves at {STARVE_DAYS}", "bad") if animal.unfed_days
               else ("fed", "good"))
        load = f"{round(animal.load, 1):g} / {round(animal.carry_max, 1):g} kg"
        return [("TACK", animal.tack or "none", ""), ("ROLE", role, ""), ("LOAD", load, ""),
                ("FEED", *fed), ("VALUE", fmt_money(animal.price), "")]

    @staticmethod
    def _weapon_data(unit, c, ch):
        w = ch["weapon"]
        bab = w["hit"].split("(")[0].replace("d20", "").strip()
        src = w["hit"].split("(")[-1].rstrip(")")
        dmg = w["dmg"].split("(")[0].strip()
        reach = f"{unit.weapon['range'] * 1.5:g} m" if unit.weapon and unit.weapon.get("range") else "1.5 m"
        return {
            "name": w["nm"], "tags": w["tags"],
            "chips": [
                ("ATTACK", bab, f"Attack modifier {bab} ({src}): d20 {bab} against the target's armor class"),
                ("DAMAGE", dmg, f"{w['dmg']}: weapon dice plus strength on a hit"),
                ("REACH", reach, "Distance this weapon can strike"),
            ],
        }

    @staticmethod
    def _gear_data(unit, c):
        offhand = getattr(unit, "equipped_offhand", None)
        if not offhand:
            offhand = "Torch" if getattr(c, "torch_hand", False) else (
                "Lantern" if getattr(c, "lantern_hand", False) else None)
        weapon = c.weapon_name or unit.ability.natural_weapon or "Unarmed"
        return {
            "hands": f"{weapon} + {offhand}" if offhand and offhand != "None" else weapon,
            "armor": unit.armor_name if unit.armor else "None",
            "armor_note": (f"+{unit.armor['ac']} AC" + (f"  -{unit.armor.speed_penalty} SPD"
                                                       if unit.armor.speed_penalty else "")) if unit.armor else "",
            "coins": unit.money,
            "rations": (unit.rations, unit.ability.id == "autotroph"),
            "load": (unit.load, unit.carry_normal, unit.carry_max),
        }

    def _sponsor_line(self, unit):
        used, cap = recruit.slots_used(self.guild, unit), recruit.capacity(self.guild, unit)
        left = (f"{cap - used} more may join on their word" if cap > used else "none left")
        return f"Sponsored recruits: {used} of {cap} -- {left}"

    def _role_rows(self, unit, grp):
        cap = BASE_CAPACITY + unit.mod_charisma + (unit.racial_level // 2)
        band = grp.display_name if grp else "the group"
        free_swap = self.guild.leader_swaps_used < 1
        rows = []
        if unit is self.guild.leader:
            rows.append({"key": "guild_leader", "title": "Guild leader", "current": True,
                         "sub": "Adds a CHA bonus to taverna recruitment",
                         "action": None, "tip": "Leads the whole guild"})
        else:
            rows.append({"key": "guild_leader", "title": "Guild leader", "current": False,
                         "sub": "1 free transfer left" if free_swap else "No free transfer left",
                         "action": ("MAKE GUILD LEADER", free_swap),
                         "tip": "Make this member lead the whole guild"})
        fight_due = self._fight_due(unit)
        if self._is_group_leader(unit):
            rows.append({"key": "group_leader", "title": "Group leader", "current": True,
                         "sub": f"Leads {band} -- holds up to {cap} members", "action": None,
                         "tip": "Group size capacity is 3 + CHA modifier + half racial level"})
        else:
            can = grp is not None and len(grp.members) > 1 and not fight_due
            rows.append({"key": "group_leader", "title": "Group leader", "current": False,
                         "sub": f"Would hold up to {cap} members",
                         "action": ("MAKE GROUP LEADER", can),
                         "tip": FIGHT_DUE_TIP if fight_due else f"Make this member the leader of {band}"})
        can_share = unit.ability.id != "autotroph"
        if not can_share:
            sub = "Does not eat or carry rations"
        elif unit.share_food:
            sub = "Feeds starving groupmates from its pack"
        else:
            sub = "Keeps its food in its own pack"
        rows.append({"key": "share_food", "title": "Rations", "current": False, "sub": sub,
                     "action": ("STOP SHARING" if unit.share_food else "SHARE RATIONS", can_share),
                     "tip": "Pool rations so a hungry bandmate is fed first, or keep them private"})
        size = len(grp.members) if grp else 1
        rows.append({"key": "distribute", "title": "Pack load", "current": False,
                     "sub": (f"Even out pack items across {size} members" if size > 1
                             else "Needs two or more members in the group"),
                     "action": ("DISTRIBUTE", size > 1 and not fight_due),
                     "tip": FIGHT_DUE_TIP if fight_due else "Rebalances unlocked pack items by free carrying capacity"})
        return rows

    @staticmethod
    def _tracks(unit):
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        into_w, span_w = progression.to_next(progression.WORK_XP_THRESHOLDS, unit.work_xp)
        into_r, span_r = progression.to_next(progression.RACIAL_XP_THRESHOLDS, unit.racial_xp)
        jobs = progression.eligible_work_activities(unit.work_level, unit)
        nxt = progression.next_racial_pick(unit.racial_level)
        racial = (f"Combat {unit.combat_level} + Work {unit.work_level} levels. +1 hit die per level. "
                  + (f"Next racial talent at Lv {nxt} ({nxt - unit.racial_level} to go)."
                     if nxt else "Every racial talent earned."))
        tracks = [
            {"label": "Combat career", "value": f"LVL {unit.combat_level}  ({into_c}/{span_c} XP)" if span_c
             else f"LVL {unit.combat_level}  (MAX)",
             "frac": into_c / span_c if span_c else 0,
             "text": f"Down standing enemies of Lv {unit.combat_level}+ (Arena, Wilds, Ambushes).",
             "tip": (f"Downing an enemy grants (enemy level - {unit.combat_level}) + 1 XP; "
                     f"enemies below Lv {unit.combat_level} grant none.")},
            {"label": "Base labor & work", "value": f"LVL {unit.work_level}  ({into_w}/{span_w} XP)" if span_w
             else f"LVL {unit.work_level}  (MAX)",
             "frac": into_w / span_w if span_w else 0,
             "text": ("Facility labor: " + ", ".join(jobs)) if jobs
             else f"No standard facilities teach past Lv {unit.work_level} yet.",
             "tip": (f"1 mark per 16 hours of facility day-labour. Activity level must be at least "
                     f"Lv {unit.work_level} to teach.")},
            {"label": "Racial maturity", "value": f"LVL {unit.racial_level}  ({into_r}/{span_r})" if span_r
             else f"LVL {unit.racial_level}  (MAX)",
             "frac": into_r / span_r if span_r else 0, "text": racial,
             "tip": "Racial XP is the sum of combat and work levels."},
        ]
        if unit.study_target:
            spell = magic.SPELLS.get(unit.study_target)
            name = spell.name if spell else unit.study_target
            need = magic.points_to_learn(spell.level if spell else 0)
            cur = min(unit.study_progress, need)
            tracks.append({"label": "Academic study", "value": f"{name}  ({cur}/{need} pts)",
                           "frac": cur / need if need else 0,
                           "text": "Studying at the taverna: daily progress toward mastery.",
                           "tip": f"Rolls 1d20 + INT per day on a Study order. {cur}/{need} points."})
        if unit.rite_school:
            label, done, total = rite.stage(unit, unit.rite_school)
            unit_word = "days" if label == "blood test" else "pts"
            tracks.append({"label": f"{unit.rite_school.title()} rite", "value": f"{label}  ({done}/{total} {unit_word})",
                           "frac": done / total if total else 0,
                           "text": "Boarding at the sanctuary: daily progress toward initiation.",
                           "tip": f"Rolls 1d20 + INT per day while boarding. {done}/{total} {unit_word}."})
        return tracks

    # ------------------------------------------------------------------ #
    # the charter                                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _group_task(grp):
        if is_idle(grp):
            return "Idle"
        order = grp.order
        if order.kind == "garrison":
            job = getattr(order, "job", None)
            return f"Garrison ({job})" if job else "Garrison"
        return order.kind.title()

    def _notice_days(self):
        """`{uid: days left}` for everyone who has given notice."""
        day = self.guild.clock.day
        return {uid: max(0, due - day) for uid, due in self.guild.leaving.items()}

    def _group_rows(self):
        left = self._notice_days()
        notice = {}
        for u in self.roster:
            if u.uid in left:
                notice[self.guild.group_of(u).gid] = f"NOTICE: {u.name} leaves the guild in {_days(left[u.uid])}"
        return [{"name": g.display_name, "where": node_label(g.node), "task": self._group_task(g),
                 "size": len(g.members), "capacity": g.capacity, "over": g.overextension,
                 "note": notice.get(g.gid, "")} for g in self.guild.groups]

    def _notices(self):
        """Whoever is about to walk out (bad), then any overextended group nobody has
        given notice from yet (warn), then a herd about to stray (warn)."""
        left = self._notice_days()
        out = [(f"{u.name} has given notice and leaves the guild in {_days(left[u.uid])} -- "
                + f"{self.guild.group_of(u).display_name} is over capacity with no free slot.", "bad")
               for u in self.roster if u.uid in left]
        warned = {self.guild.group_of(u) for u in self.roster if u.uid in left}
        if not self.guild.free_slots:
            out += [(f"{g.display_name} is over capacity and the guild has no free slot: "
                     + "its weakest member may give notice any day.", "warn")
                    for g in self.guild.groups if g.overextension and g not in warned]
        day = self.guild.clock.day
        out += [(f"{g.display_name} cannot control its herd: an animal strays in "
                 + f"{_days(max(0, g.herd_notice - day))}.", "warn")
                for g in self.guild.groups if g.herd_notice is not None]
        return out

    def _holdings(self):
        guild, house = self.guild, self.guild.house
        out = []
        if not house.owned:
            out.append(("City house", "NOT OWNED", "muted", "Buy one from the Bankers in the City."))
        elif house.squatting:
            out.append(("City house", "SQUATTED", "bad", "Unpaid tax: the guard raids it."))
        elif house.missed_payments:
            out.append(("City house", "BEHIND ON TAX", "warn",
                        f"{house.missed_payments} missed payment{'s' if house.missed_payments != 1 else ''}."))
        else:
            out.append(("City house", "OWNED", "good", "Tax paid up."))

        stage = guild.wilds_claim_stage
        held = any(g.node == world.WILDS_TERRITORY_NODE and g.order is not None
                   and g.order.kind == "garrison" and not g.empty for g in guild.groups)
        if stage == "NONE":
            out.append(("The Claim", "NOT CLAIMED", "muted", "Scout it from the Wilds to start."))
        elif stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
            out.append(("The Claim", "SEIZED", "bad", "Travel there and beat the occupiers to retake it."))
        elif stage == "ESTABLISHED":
            out.append(("The Claim", "HELD" if held else "UNGUARDED", "good" if held else "warn",
                        "A garrison stands on the land." if held
                        else "An unguarded claim can be seized without a fight."))
        else:
            left = guild.wilds_claim_sustain_days_left
            detail = (f"{left} days to hold it" if stage == "SUSTAINING" and left is not None
                      else "Claim campaign in progress.")
            out.append(("The Claim", stage.title(), "warn", detail))

        bank = guild.bank
        out.append(("Strongbox", "RENTED" if bank.open else "NONE", "good" if bank.open else "muted",
                    f"{bank.load:g}/{bank.capacity:g} kg used" if bank.open
                    else "Rent one at the bank in the City."))
        return [{"name": n, "status": st, "tone": tone, "detail": d} for n, st, tone, d in out]

    def _vocation(self):
        voc = vocations.of(self.guild)
        return None if voc is None else {"name": voc.name, "perk": voc.perk, "dormant": not voc.active}
