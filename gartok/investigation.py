"""Asking around: an hour in a place's Jobs tab spent finding out what its people know about a job the guild
holds. Each (job, place) pair is answered once; a place that knows nothing about the job says so, and that
answers it too. A clue found adds to the job's count (`Guild.investigation`), and each reader of the count
brings its own multiplier (`bonus`): the next ask-around adds `ASK_PER_CLUE` a clue, a search of the land
adds its own. The roll is Charisma, the band's best talker.
"""

from . import checks, data, i18n

ASK_HOURS = 1
GATHER_DC = 10
ASK_PER_CLUE = 1

# job id -> the place -> the catalog key of what that place can tell
CLUES = {
    "farmer_daughter": {
        "faith_cathedral": "investigation.clue.farmer_daughter.faith_cathedral",
        "ledger_hold": "investigation.clue.farmer_daughter.ledger_hold",
    },
}


def _entry(guild, job_id):
    return guild.investigation.setdefault(job_id, {"clues": 0, "asked": []})


def clues(guild, job_id):
    return guild.investigation.get(job_id, {}).get("clues", 0)


def bonus(guild, job_id, per_clue):
    """What a reader of `job_id`'s clue count adds to its roll, at its own `per_clue`."""
    return per_clue * clues(guild, job_id)


def asked(guild, job_id, node_id):
    return node_id in guild.investigation.get(job_id, {}).get("asked", ())


def answer(job_id, node_id):
    """What `node_id` tells about `job_id`, nobody-knows when it has nothing."""
    key = CLUES.get(job_id, {}).get(node_id)
    return i18n.t(key) if key else i18n.t("investigation.nobody_knows")


def speaker(group):
    return max(group.members, key=lambda u: u.mod_charisma)


def ask(guild, group, job_id):
    """The hour's roll at `group`'s place about `job_id`: -> the lines it says."""
    node_id = group.node
    if asked(guild, job_id, node_id):
        return [answer(job_id, node_id)]
    who = speaker(group)
    nat = data.d20()
    extra = bonus(guild, job_id, ASK_PER_CLUE)
    total = nat + who.mod_charisma + extra
    checks.put(guild, checks.Check(who.name, nat, who.mod_charisma + extra, total, GATHER_DC, total >= GATHER_DC,
                                   i18n.t("checks.ask")))
    if total < GATHER_DC:
        return [i18n.t("investigation.no_luck", name=who.name, nat=nat, mod=f"{who.mod_charisma:+}", extra=extra,
                       total=total, dc=GATHER_DC)]
    if job_id not in CLUES or node_id not in CLUES[job_id]:
        _entry(guild, job_id)["asked"].append(node_id)      # a place with nothing to tell is learned the same way
        return [i18n.t("investigation.nobody_knows")]
    entry = _entry(guild, job_id)
    entry["asked"].append(node_id)
    entry["clues"] += 1
    return [i18n.t("investigation.found", name=who.name), answer(job_id, node_id)]
