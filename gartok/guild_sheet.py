"""The guild's sheet, with no pygame: the roster by band (its filters and folds), a member's
sheet (the weapon, the kit, the careers, the roles and what pressing one does), an animal's,
the charter (the bands, the notices, the holdings, the founding trade). A tone is a word
(`warn`, `bad`, `good`, or "" for plain). `web/guild_session.py` reads it.
"""

from . import i18n, magic, progression, recruit, rite, vocations, world
from .animals import STARVE_DAYS, Animal
from .constants import fmt_money
from .group import capacity_for

FILTERS = tuple((mode, f"guild_sheet.filter.{mode}") for mode in ("all", "idle", "busy", "alerts"))
ATTRIBUTE_LABELS = (("STR", "strength"), ("DEX", "dexterity"), ("CON", "constitution"),
                    ("INT", "intelligence"), ("WIS", "wisdom"), ("CHA", "charisma"))
FIGHT_DUE_TIP = "guild_sheet.fight_due_tip"


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
    return i18n.count("day", n)


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
        return who.name if who else i18n.t("guild_sheet.someone_long_gone")

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
            badges.append((i18n.t("guild_sheet.level_up"), "warn"))
        if unit.hunger_level >= 1:
            badges.append((i18n.lab("HUNGRY"), "bad"))
        if unit.sick:
            badges.append((i18n.lab("SICK"), "bad"))
        if unit is self.guild.leader:
            badges.append((i18n.t("guild_sheet.guild_leader"), ""))
        elif self._is_group_leader(unit):
            badges.append((i18n.t("guild_sheet.group_leader"), ""))
        return {
            "key": unit.uid, "name": unit.name, "selected": selected, "badges": badges,
            "sub": (i18n.t("guild_sheet.lv_c_w", race=unit.race_label, racial_level=unit.racial_level, combat_level=unit.combat_level, work_level=unit.work_level)),
            "hp": (max(0, unit.hp), unit.hp_max),
        }

    @staticmethod
    def _animal_data(animal, grp, selected):
        pulled = grp.pulling(animal)
        job = i18n.t("guild_sheet.pulls", lower=pulled.ref(lower=True)) if pulled else animal.role or i18n.t("guild_sheet.no_tack")
        return {
            "key": animal.uid, "name": animal.species, "selected": selected,
            "badges": [(i18n.lab("HUNGRY"), "bad")] if animal.unfed_days else [],
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
            role = i18n.t("guild_sheet.carries_up_to_kg_on", capacity=animal.capacity)
        elif animal.role == "draft":
            hitched = i18n.t("guild_sheet.hitched_to", lower=pulled.ref(lower=True)) if pulled else i18n.t("guild_sheet.not_hitched")
            role = i18n.t("guild_sheet.pulls_up_to_kg", pull=animal.pull, hitched=hitched)
        else:
            role = (i18n.t("guild_sheet.idle_pack_saddle_lets_it", back_load=animal.back_load, draw=animal.draw))
        fed = ((i18n.t("guild_sheet.hungry_day_s_starves_at", unfed_days=animal.unfed_days, starve_days=STARVE_DAYS), "bad") if animal.unfed_days
               else (i18n.lab("fed"), "good"))
        load = i18n.t("guild_sheet.kg", load=round(animal.load, 1), most=round(animal.carry_max, 1))
        return [(i18n.lab("TACK"), i18n.name("item", animal.tack) if animal.tack else i18n.lab("none"), ""), (i18n.lab("ROLE"), role, ""),
                (i18n.lab("LOAD"), load, ""), (i18n.lab("FEED"), *fed), (i18n.lab("VALUE"), fmt_money(animal.price), "")]

    @staticmethod
    def _weapon_data(unit, c, ch):
        w = ch["weapon"]
        bab = w["hit"].split("(")[0].replace("d20", "").strip()
        src = w["hit"].split("(")[-1].rstrip(")")
        dmg = w["dmg"].split("(")[0].strip()
        reach = f"{unit.weapon['range'] * 1.5:g} m" if unit.weapon and unit.weapon.get("range") else "1.5 m"
        chips = [
            ("ATTACK", bab, i18n.t("guild_sheet.attack_modifier_d_against_target", bab=bab, src=src, bonus=bab)),
            ("DAMAGE", dmg, i18n.t("guild_sheet.weapon_dice_plus_strength_on", w=w['dmg'])),
            ("REACH", reach, i18n.t("guild_sheet.distance_this_weapon_can_strike")),
        ]
        if c.needs_ammo:
            chips.append(("AMMO", str(c.ammo), i18n.t("guild_sheet.arrows_or_bolts_left_across") if c.ammo else
                          i18n.t("guild_sheet.no_arrows_or_bolts_carry")))
        return {"name": w["nm"], "tags": w["tags"], "chips": chips}

    @staticmethod
    def _gear_data(unit, c):
        offhand = getattr(unit, "equipped_offhand", None)
        if not offhand:
            offhand = "Torch" if getattr(c, "torch_hand", False) else (
                "Lantern" if getattr(c, "lantern_hand", False) else None)
        weapon = c.weapon.name
        return {
            "hands": f"{i18n.name('item', weapon)} + {i18n.name('item', offhand)}" if offhand and offhand != "None" else i18n.name("item", weapon),
            "armor": i18n.name("item", unit.armor_name) if unit.armor else i18n.lab("None"),
            "armor_note": (i18n.t("guild_sheet.ac", armor=unit.armor['ac']) + (i18n.t("guild_sheet.spd", speed_penalty=unit.armor.speed_penalty)
                                                       if unit.armor.speed_penalty else "")) if unit.armor else "",
            "coins": unit.money,
            "rations": (unit.rations, unit.ability.id == "autotroph"),
            "load": (unit.load, unit.carry_normal, unit.carry_max),
        }

    def _sponsor_line(self, unit):
        used, cap = recruit.slots_used(self.guild, unit), recruit.capacity(self.guild, unit)
        left = (i18n.t("guild_sheet.more_may_join_on_their", value=cap - used) if cap > used else i18n.t("guild_sheet.none_left"))
        return i18n.t("guild_sheet.sponsored_recruits_of", used=used, cap=cap, left=left)

    def _role_rows(self, unit, grp):
        cap = capacity_for(unit)
        band = grp.display_name if grp else i18n.t("guild_sheet.group")
        free_swap = self.guild.leader_swaps_used < 1
        rows = []
        if unit is self.guild.leader:
            rows.append({"key": "guild_leader", "title": i18n.t("guild_sheet.guild_leader_2"), "current": True,
                         "sub": i18n.t("guild_sheet.adds_cha_bonus_to_taverna"),
                         "action": None, "tip": i18n.t("guild_sheet.leads_whole_guild")})
        else:
            rows.append({"key": "guild_leader", "title": i18n.t("guild_sheet.guild_leader_2"), "current": False,
                         "sub": i18n.t("guild_sheet.free_transfer_left") if free_swap else i18n.t("guild_sheet.no_free_transfer_left"),
                         "action": (i18n.t("guild_sheet.make_guild_leader"), free_swap),
                         "tip": i18n.t("guild_sheet.make_this_member_lead_whole")})
        fight_due = self._fight_due(unit)
        if self._is_group_leader(unit):
            rows.append({"key": "group_leader", "title": i18n.t("guild_sheet.group_leader_2"), "current": True,
                         "sub": i18n.t("guild_sheet.leads_holds_up_to_members", band=band, cap=cap), "action": None,
                         "tip": i18n.t("guild_sheet.group_size_capacity_is_cha")})
        else:
            can = grp is not None and len(grp.members) > 1 and not fight_due
            rows.append({"key": "group_leader", "title": i18n.t("guild_sheet.group_leader_2"), "current": False,
                         "sub": i18n.t("guild_sheet.would_hold_up_to_members", cap=cap),
                         "action": (i18n.t("guild_sheet.make_group_leader"), can),
                         "tip": i18n.t(FIGHT_DUE_TIP) if fight_due else i18n.t("guild_sheet.make_this_member_leader_of", band=band)})
        can_share = unit.ability.id != "autotroph"
        if not can_share:
            sub = i18n.t("guild_sheet.does_not_eat_or_carry")
        elif unit.share_food:
            sub = i18n.t("guild_sheet.feeds_starving_groupmates_from_its")
        else:
            sub = i18n.t("guild_sheet.keeps_its_food_in_its")
        rows.append({"key": "share_food", "title": "Rations", "current": False, "sub": sub,
                     "action": (i18n.t("guild_sheet.stop_sharing") if unit.share_food else i18n.t("guild_sheet.share_rations"), can_share),
                     "tip": i18n.t("guild_sheet.pool_rations_so_hungry_bandmate")})
        size = len(grp.members) if grp else 1
        rows.append({"key": "distribute", "title": i18n.t("guild_sheet.pack_load"), "current": False,
                     "sub": (i18n.t("guild_sheet.even_out_pack_items_across", size=size) if size > 1
                             else i18n.t("guild_sheet.needs_two_or_more_members")),
                     "action": (i18n.lab("DISTRIBUTE"), size > 1 and not fight_due),
                     "tip": i18n.t(FIGHT_DUE_TIP) if fight_due else i18n.t("guild_sheet.rebalances_unlocked_pack_items_by")})
        return rows

    @staticmethod
    def _tracks(unit):
        into_c, span_c = progression.to_next(progression.COMBAT_XP_THRESHOLDS, unit.combat_xp)
        into_w, span_w = progression.to_next(progression.WORK_XP_THRESHOLDS, unit.work_xp)
        into_r, span_r = progression.to_next(progression.RACIAL_XP_THRESHOLDS, unit.racial_xp)
        jobs = progression.eligible_work_activities(unit.work_level, unit)
        nxt = progression.next_racial_pick(unit.racial_level)
        racial = (i18n.t("guild_sheet.combat_work_levels_hit_die", combat_level=unit.combat_level, work_level=unit.work_level)
                  + (i18n.t("guild_sheet.next_racial_talent_at_lv", nxt=nxt, value=nxt - unit.racial_level)
                     if nxt else i18n.t("guild_sheet.every_racial_talent_earned")))
        tracks = [
            {"label": i18n.t("guild_sheet.combat_career"), "value": i18n.t("guild_sheet.lvl_xp", combat_level=unit.combat_level, into_c=into_c, span_c=span_c) if span_c
             else i18n.t("guild_sheet.lvl_max", combat_level=unit.combat_level),
             "frac": into_c / span_c if span_c else 0,
             "text": i18n.t("guild_sheet.down_standing_enemies_of_lv", combat_level=unit.combat_level),
             "tip": (i18n.t("guild_sheet.downing_enemy_grants_enemy_level", combat_level=unit.combat_level, level=unit.combat_level))},
            {"label": i18n.t("guild_sheet.base_labor_work"), "value": i18n.t("guild_sheet.lvl_xp_2", work_level=unit.work_level, into_w=into_w, span_w=span_w) if span_w
             else i18n.t("guild_sheet.lvl_max_2", work_level=unit.work_level),
             "frac": into_w / span_w if span_w else 0,
             "text": (i18n.t("guild_sheet.facility_labor") + ", ".join(jobs)) if jobs
             else i18n.t("guild_sheet.no_standard_facilities_teach_past", work_level=unit.work_level),
             "tip": (i18n.t("guild_sheet.mark_per_hours_of_facility", work_level=unit.work_level))},
            {"label": i18n.t("guild_sheet.racial_maturity"), "value": i18n.t("guild_sheet.lvl", racial_level=unit.racial_level, into_r=into_r, span_r=span_r) if span_r
             else i18n.t("guild_sheet.lvl_max_3", racial_level=unit.racial_level),
             "frac": into_r / span_r if span_r else 0, "text": racial,
             "tip": i18n.t("guild_sheet.racial_xp_is_sum_of")},
        ]
        if unit.study_target:
            lesson = magic.SPELLS.get(unit.study_target) or magic.recipe_of(unit.study_target)
            name = lesson.name if lesson else unit.study_target
            need = magic.points_to_learn(lesson.level if lesson else 0)
            cur = min(unit.study_progress.get(unit.study_target, 0), need)
            tracks.append({"label": i18n.t("guild_sheet.academic_study"), "value": i18n.t("guild_sheet.pts", name=name, cur=cur, need=need),
                           "frac": cur / need if need else 0,
                           "text": i18n.t("guild_sheet.studying_at_taverna_daily_progress"),
                           "tip": i18n.t("guild_sheet.rolls_d_int_per_day", cur=cur, need=need)})
        if unit.rite_school:
            label, done, total = rite.stage(unit, unit.rite_school)
            unit_word = "days" if label == "blood test" else "pts"
            tracks.append({"label": i18n.t("guild_sheet.rite", title=unit.rite_school.title()), "value": f"{label}  ({done}/{total} {unit_word})",
                           "frac": done / total if total else 0,
                           "text": i18n.t("guild_sheet.boarding_at_sanctuary_daily_progress"),
                           "tip": i18n.t("guild_sheet.rolls_d_int_per_day_2", done=done, total=total, unit_word=unit_word)})
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
                notice[self.guild.group_of(u).gid] = i18n.t("guild_sheet.notice_leaves_guild_in", name=u.name, days=_days(left[u.uid]))
        return [{"name": g.display_name, "where": node_label(g.node), "task": self._group_task(g),
                 "size": len(g.members), "capacity": g.capacity, "over": g.overextension,
                 "note": notice.get(g.gid, "")} for g in self.guild.groups]

    def _notices(self):
        """Whoever is about to walk out (bad), then any overextended group nobody has
        given notice from yet (warn), then a herd about to stray (warn)."""
        left = self._notice_days()
        out = [(i18n.t("guild_sheet.has_given_notice_and_leaves", name=u.name, days=_days(left[u.uid]))
                + i18n.t("guild_sheet.is_over_capacity_with_no", display_name=self.guild.group_of(u).display_name), "bad")
               for u in self.roster if u.uid in left]
        warned = {self.guild.group_of(u) for u in self.roster if u.uid in left}
        if not self.guild.free_slots:
            out += [(i18n.t("guild_sheet.is_over_capacity_and_guild", display_name=g.display_name)
                     + i18n.t("guild_sheet.its_weakest_member_may_give"), "warn")
                    for g in self.guild.groups if g.overextension and g not in warned]
        day = self.guild.clock.day
        out += [(i18n.t("guild_sheet.cannot_control_its_herd_animal", display_name=g.display_name)
                 + f"{_days(max(0, g.herd_notice - day))}.", "warn")
                for g in self.guild.groups if g.herd_notice is not None]
        return out

    def _holdings(self):
        guild, house = self.guild, self.guild.house
        out = []
        if not house.owned:
            out.append((i18n.t("guild_sheet.city_house"), i18n.t("guild_sheet.not_owned"), "muted", i18n.t("guild_sheet.buy_one_from_bankers_in")))
        elif house.squatting:
            out.append((i18n.t("guild_sheet.city_house"), "SQUATTED", "bad", i18n.t("guild_sheet.unpaid_tax_guard_raids_it")))
        elif house.missed_payments:
            out.append((i18n.t("guild_sheet.city_house"), i18n.t("guild_sheet.behind_on_tax"), "warn",
                        i18n.plural("guild_sheet.missed_payment", house.missed_payments)))
        else:
            out.append((i18n.t("guild_sheet.city_house"), "OWNED", "good", i18n.t("guild_sheet.tax_paid_up")))

        stage = guild.wilds_claim_stage
        held = any(g.node == world.WILDS_TERRITORY_NODE and g.order is not None
                   and g.order.kind == "garrison" and not g.empty for g in guild.groups)
        if stage == "NONE":
            out.append((i18n.t("guild_sheet.claim"), i18n.t("guild_sheet.not_claimed"), "muted", i18n.t("guild_sheet.scout_it_from_wilds_to")))
        elif stage == "ESTABLISHED" and guild.wilds_claim_owner == "seized":
            out.append((i18n.t("guild_sheet.claim"), "SEIZED", "bad", i18n.t("guild_sheet.travel_there_and_beat_occupiers")))
        elif stage == "ESTABLISHED":
            out.append((i18n.t("guild_sheet.claim"), "HELD" if held else "UNGUARDED", "good" if held else "warn",
                        i18n.t("guild_sheet.garrison_stands_on_land") if held
                        else i18n.t("guild_sheet.unguarded_claim_can_be_seized")))
        else:
            left = guild.wilds_claim_sustain_days_left
            detail = (i18n.t("guild_sheet.days_to_hold_it", left=left) if stage == "SUSTAINING" and left is not None
                      else i18n.t("guild_sheet.claim_campaign_in_progress"))
            out.append((i18n.t("guild_sheet.claim"), stage.title(), "warn", detail))

        bank = guild.bank
        out.append(("Strongbox", "RENTED" if bank.open else "NONE", "good" if bank.open else "muted",
                    i18n.t("guild_sheet.kg_used", load=bank.load, capacity=bank.capacity) if bank.open
                    else i18n.t("guild_sheet.rent_one_at_bank_in")))
        return [{"name": n, "status": st, "tone": tone, "detail": d} for n, st, tone, d in out]

    def _vocation(self):
        voc = vocations.of(self.guild)
        return None if voc is None else {"name": voc.name, "perk": voc.perk, "dormant": not voc.active}
