"""Recruitment: talking a stranger into joining the guild.

There is no taverna hall, no vault, no signing bonus -- the guild *is* its roster
(see [[gartok-tactical-project]]). One guild member does the talking; whether the
stranger signs on is a Charisma contest between the two of them, and three things
drag the recruiter's side down:

- **no shared language** -> no pitch at all (you cannot talk someone into a
  contract you cannot both read);
- **alignment distance** -> -1 per step on the two alignment axes (0..4), a
  zealot and a scoundrel do not see eye to eye;
- **guild size** -> -1 per member past `FREE_SLOTS`, every mouth already at the
  table makes the next hand a harder sell.

`can_pitch` is the language gate; `convince` rolls the contest and returns a
`Pitch` with the full breakdown for the screen to show; `enlist` binds the
recruit to the roster (`recruited_by` = the recruiter's uid).

A member can only sponsor so many people (`capacity`): `BASE_RECRUIT_CAPACITY`
+ their Charisma modifier -- low-Charisma members cap out fast and become the
guild's floor. The guild leader adds their own racial level on top, a strong
standing bonus that keeps the guild growing even once everyone else is tapped
out. `recruited_by` is read live off the current roster, so a dead recruiter's
spent slots simply stop existing with them -- no bookkeeping to free by hand.

The strangers themselves live on the guild (`taverna_pool`, persisted) and
`refresh_pool` re-rolls them once a week -- so the faces are stable across visits
until `REFRESH_DAYS` pass. A recruiter who fails a pitch is barred from trying
that same stranger again until the pool turns over (`taverna_blocked`).
"""

import random
from dataclasses import dataclass, field

from . import data, i18n
from .unit import Unit

FREE_SLOTS = 2                 # a guild this small recruits with no size penalty
SIZE_PENALTY = 1               # -1 to the contest per member past FREE_SLOTS
ALIGNMENT_PENALTY = 1          # -1 to the contest per step of alignment distance

TAVERNA_SIZE = 3               # strangers in the taverna at a time
PRISON_SIZE = 3                # prisoners available for bail
REFRESH_DAYS = 7               # the pool re-rolls once this many days pass

BASE_RECRUIT_CAPACITY = 1      # + Charisma modifier -- how many people you could personally recruit


def shared_languages(recruiter, candidate):
    """The tongues the two have in common (a pitch needs at least one)."""
    return sorted(set(recruiter.languages) & set(candidate.languages))


def can_pitch(recruiter, candidate):
    return bool(shared_languages(recruiter, candidate))


def size_penalty(roster_size):
    """The recruiter's handicap from an already-crowded guild."""
    return SIZE_PENALTY * max(0, roster_size - FREE_SLOTS)


def bail_cost(candidate):
    """Cost to pay a prisoner's bail (in copper):
    (sum(attributes) * (racial_level + 1)) + 20. The `+1` keeps a level-0
    candidate's bail scaled to their attributes instead of a flat 20 copper."""
    from .unit import ATTRIBUTES
    total_attr = sum(getattr(candidate, a) for a in ATTRIBUTES)
    return (total_attr * (candidate.racial_level + 1)) + 20


# What a member's sponsoring capacity adds to `BASE_RECRUIT_CAPACITY` (the wiki's `wiki_rules.term.<label>`
# reads the same tuples, so the text cannot drift from the sum), and what the guild's leader adds besides.
SPONSOR_TERMS = (("member_cha", lambda u: u.mod_charisma),)
LEADER_SPONSOR_TERMS = (("racial_level", lambda u: u.racial_level),)


def capacity(guild, unit):
    """How many people `unit` could personally sponsor into the guild. The
    guild leader's own racial level (both XP tracks) adds on top -- the one
    mechanical thing `Guild.leader` does today, and the reason the role is
    worth holding onto beyond flavour."""
    if unit is guild.leader:
        return leader_capacity(unit)
    return max(0, BASE_RECRUIT_CAPACITY + sum(value(unit) for _, value in SPONSOR_TERMS))


def leader_capacity(unit):
    """`capacity` for the guild's leader: the racial level adds on top."""
    return max(0, BASE_RECRUIT_CAPACITY + sum(value(unit) for _, value in SPONSOR_TERMS + LEADER_SPONSOR_TERMS))


def slots_used(guild, unit):
    return sum(1 for u in guild.roster if u.recruited_by == unit.uid)


def slots_free(guild, unit):
    return capacity(guild, unit) - slots_used(guild, unit)


@dataclass
class Pitch:
    ok: bool
    recruiter_roll: int = 0                  # the recruiter's raw d20
    recruiter_total: int = 0                 # d20 + Charisma + modifiers
    candidate_roll: int = 0                  # the candidate's raw d20
    candidate_total: int = 0                 # d20 + their Charisma
    modifiers: list = field(default_factory=list)   # [(value, label)] on the recruiter's side
    language: str | None = None              # the tongue the pitch was made in
    reason: str = ""                         # why it failed (empty on success)


def convince(recruiter, candidate, roster_size, rng=random, day=1, extra_mods=None):
    """Roll the recruiter's Charisma contest against the candidate's resolve.

    `roster_size` is how many members the guild has right now (it grows as you
    recruit within one visit, so the fourth hire of a session is harder than the
    first). Returns a `Pitch`; a tie goes to the candidate.
    """
    lang = shared_languages(recruiter, candidate)
    if not lang:
        return Pitch(False, reason=i18n.t("recruit.no_shared_language"))

    mods = list(extra_mods or [])
    dist = data.alignment_distance(recruiter.alignment, candidate.alignment)
    red = int(recruiter.talent_bonus("align_distance_reduction"))
    eff_dist = max(0, dist - red)
    if eff_dist:
        mods.append((-ALIGNMENT_PENALTY * eff_dist, i18n.t("recruit.opposite_alignment", eff_dist=eff_dist)))
    pen = size_penalty(roster_size)
    if pen:
        mods.append((-pen, i18n.t("recruit.guild_of", roster_size=roster_size)))
    knack = recruiter.talent_bonus("recruit_cha")     # Fixer talent
    if knack:
        mods.append((knack, "Fixer"))

    rr, cr = rng.randint(1, 20), rng.randint(1, 20)
    r_total = rr + recruiter.mod_charisma + sum(v for v, _ in mods)
    c_total = cr + candidate.mod_charisma
    if r_total <= c_total and recruiter.can_use_luck(day):
        recruiter.use_luck(day)
        rr2 = rng.randint(1, 20)
        r_total2 = rr2 + recruiter.mod_charisma + sum(v for v, _ in mods)
        mods.append((0, i18n.t("recruit.halfling_luck_reroll")))
        rr, r_total = rr2, r_total2

    ok = r_total > c_total                       # a tie goes to the stranger: they stay put
    return Pitch(ok, rr, r_total, cr, c_total, mods, lang[0],
                 reason="" if ok else i18n.t("recruit.not_convinced"))


# --------------------------------------------------------------------------- #
# the taverna pool: whose faces are on offer, refreshed weekly                 #
# --------------------------------------------------------------------------- #

def current_week(clock):
    return (clock.day - 1) // REFRESH_DAYS


def refresh_pool(guild):
    """Make sure the guild's taverna pool belongs to the current week; re-roll a
    fresh set (and clear the failed-pitch bars) when the week has turned over or
    there is no pool yet. Returns the pool (a live list -- recruiting removes from
    it)."""
    week = current_week(guild.clock)
    if guild.taverna_pool is None or guild.taverna_week != week:
        guild.taverna_week = week
        guild.taverna_pool = [Unit("player") for _ in range(TAVERNA_SIZE)]
        guild.taverna_blocked = []
    return guild.taverna_pool


SEEN_FUNCTIONS = {"recruit": "taverna", "prison": "prison"}   # node function id -> `recruit_seen` key


def mark_seen(guild, pool_key):
    guild.recruit_seen[pool_key] = current_week(guild.clock)


def has_new_faces(guild, pool_key):
    """True while the pool has turned over since the guild last walked in."""
    return guild.recruit_seen.get(pool_key) != current_week(guild.clock)


def barred(guild, candidate, recruiter):
    """True if `recruiter` already failed to talk `candidate` into it this week."""
    return [candidate.uid, recruiter.uid] in guild.taverna_blocked


def bar(guild, candidate, recruiter):
    if not barred(guild, candidate, recruiter):
        guild.taverna_blocked.append([candidate.uid, recruiter.uid])


def enlist(guild, candidate, recruiter):
    """Bind `candidate` to the roster as `recruiter`'s recruit and take them out
    of the taverna pool. Joins `recruiter`'s own group -- the pitch only happens
    because the two are standing in the same place."""
    candidate.recruited_by = recruiter.uid
    guild.add_member(candidate, guild.group_of(recruiter))
    if guild.taverna_pool and candidate in guild.taverna_pool:
        guild.taverna_pool.remove(candidate)
    if guild.prison_pool and candidate in guild.prison_pool:
        guild.prison_pool.remove(candidate)


# --------------------------------------------------------------------------- #
# the prison pool: who can be bailed out, refreshed weekly
# --------------------------------------------------------------------------- #

def refresh_prison_pool(guild):
    week = current_week(guild.clock)
    if guild.prison_pool is None or guild.prison_week != week:
        guild.prison_week = week
        guild.prison_pool = [Unit("player") for _ in range(PRISON_SIZE)]
        guild.prison_blocked = []
    return guild.prison_pool


def prison_barred(guild, candidate, recruiter):
    return [candidate.uid, recruiter.uid] in guild.prison_blocked


def prison_bar(guild, candidate, recruiter):
    if not prison_barred(guild, candidate, recruiter):
        guild.prison_blocked.append([candidate.uid, recruiter.uid])


def overflow_warning(guild, recruiter):
    """Text warning that a recruit would overextend `recruiter`'s group, or None.
    The pitch is still allowed: `cohesion` sheds the weakest member of an
    overextended group."""
    if guild.can_absorb(guild.group_of(recruiter)):
        return None
    return i18n.t("recruit.their_group_is_full_and")


def pitch_block_reason(guild, party, candidate, is_barred=barred):
    """Why no one in `party` can pitch `candidate`.
    Returns None if at least one member is eligible, or a reason string.
    `is_barred(guild, candidate, member)` picks the pool's weekly block list."""
    eligible = [m for m in party
                if can_pitch(m, candidate) and not is_barred(guild, candidate, m)
                and slots_free(guild, m) > 0]
    if eligible:
        return None
    if not party:
        return i18n.t("recruit.party_is_empty")
    if not any(slots_free(guild, m) > 0 for m in party):
        return i18n.t("recruit.no_recruitment_slots_available")

    speakers = [m for m in party if can_pitch(m, candidate)]
    if not speakers:
        return i18n.t("recruit.no_one_in_party_can")

    barred_speakers = [m for m in speakers if is_barred(guild, candidate, m)]
    unbarred_speakers = [m for m in speakers if not is_barred(guild, candidate, m)]

    if not unbarred_speakers:
        if len(speakers) == len(party):
            return i18n.t("recruit.everyone_already_tried_this_week")
        return i18n.t("recruit.all_speakers_already_tried_this")

    if barred_speakers and unbarred_speakers:
        return i18n.t("recruit.speakers_already_tried_or_have")

    return i18n.t("recruit.speakers_have_no_sponsor_slots")

