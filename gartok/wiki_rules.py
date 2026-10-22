"""The wiki's RULES tab: the rules a player looks up mid-run, read off the live constants.

`sections()` is `[(title, [line, ...])]`; the numbers come from the modules that run the rule,
so the page moves with them. RULES.md stays the designer's full prose.
"""

from . import captives, cohesion, dialogue, group, recruit, wagon
from .combatant import AP_PER_TURN


def sections():
    return [
        ("TURNS & ACTION POINTS", [
            (f"Every combatant has {AP_PER_TURN} action points a turn. Attack, Walk and Defend cost 1 each, "
            "in any mix: walk + attack, attack + attack, attack + defend..."),
            "Walk: up to your speed in cells. Diagonals cost 1, then 2, then 1 again within one walk.",
            "You can cross an ally's cell but not stop on it. An enemy's cell blocks you completely.",
            "Defend: +1 AC (circumstance) until the start of your next turn.",
            ("Delay (0 points): drop to the end of the initiative order for good, once a round, before "
            "you spend anything."),
            ("Flee (1 point, ends the turn): only from the map edge, and only when you are faster than "
            "the fastest pursuer or already out of its reach."),
            ("Bonuses of the same type do not stack: Defend and another circumstance bonus to AC, "
            "only the larger counts."),
        ]),
        ("FLANKING", [
            ("A foe is flanked when you and an ally are both next to it, on opposite sides. It loses "
            "2 AC against you (1 with Peripheral Vision); the log shows [Flank -2]."),
            ("An ally merely next to the foe is not a flank. It only feeds Pack Tactics, which some "
            "races and beasts have."),
            ("Sneak Attack (Dagger) and Precise Thrust (Rapier) work only on a flanked foe: the blow "
            "lands twice over, plus +1d4 (Sneak Attack) or +2 to hit (Precise Thrust)."),
        ]),
        ("WEAPON ACTIONS (2 POINTS)", [
            ("One strike for the price of two attacks. Out of its case it is the worse buy; in its case "
            "the blow lands twice over and beats the two attacks."),
            "Cleave (Axe): a second foe beside both, each swing +2 to hit.",
            "Repel Strike (Quarterstaff): shoves the foe 1 cell; against a wall or a body, +1d4 instead.",
            ("Maiming Strike (Club, Hammers): halves the foe's speed; a foe that cannot dodge (Entangled, "
            "Sleeping, Surprised, Demoralized) takes it at +2 to hit."),
            "Armor Pierce (Picks): ignores worn armour. Power Shot (Shortbow): +STR, best at long range.",
            ("Hook Shield (Hatchet): the foe's shield gives no AC until next round. Parry & Strike "
            "(Broadsword): while Defending, with two or more foes in reach."),
        ]),
        ("TALKING BEFORE A FIGHT", [
            (f"Persuade, Bluff and Intimidate roll d20 + Charisma against {dialogue.BASE_DC} + the foes' "
            "leader's Wisdom modifier. Natural 1 and 20 are just numbers."),
            (f"In an ambush every check reads the squad's look: up to {dialogue.OUTMATCH_CAP} easier when "
            f"your hit points outweigh the pack's, up to {dialogue.OUTMATCH_CAP} harder when theirs outweigh "
            "yours."),
            (f"Persuade: {dialogue.ALIGN_SHIFT} easier with a good leader, {dialogue.ALIGN_SHIFT} harder "
            "with an evil one. A miss is a plain fight."),
            "Bluff: a miss and they strike first (your side is Surprised and loses its first turn).",
            (f"Intimidate: they start Demoralized; beat it by {dialogue.ROUT_MARGIN}+ and they run. A miss "
            f"gives them +{dialogue.INITIATIVE_EDGE} initiative."),
            f"Bribe: ${dialogue.BRIBE_PER_FOE} a foe per (its level + 1), paid by the richest first.",
            "Every answer that talks needs a language the speaker shares with their leader.",
        ]),
        ("RECRUITING", [
            ("A pitch is d20 + Charisma (yours) against d20 + Charisma (theirs); a tie goes to the "
            "stranger. You need a language in common."),
            (f"Crowd penalty: -{recruit.SIZE_PENALTY} for every member of the whole guild past "
            f"{recruit.FREE_SLOTS}, counted across every group, not the group making the pitch."),
            (f"Alignment: -{recruit.ALIGNMENT_PENALTY} per step between the recruiter's alignment and the "
            "stranger's."),
            (f"Each member can sponsor {recruit.BASE_RECRUIT_CAPACITY} + their Charisma modifier recruits; "
            "the guild leader adds their racial level."),
            ("A failed pitch bars that recruiter from that stranger until the pool turns over. Someone "
            "else may still try."),
            (f"The Tavern keeps {recruit.TAVERNA_SIZE} strangers and the Prison {recruit.PRISON_SIZE} "
            f"prisoners; both re-roll every {recruit.REFRESH_DAYS} days. Bail is paid before the pitch and "
            "adds +2 to it; lose and the bail is gone."),
        ]),
        ("GROUPS, LEADERS & FAME", [
            (f"The guild may run {group.BASE_SLOTS} groups, plus one more for every "
            f"{group.FAME_PER_SLOT} reputation summed across all factions."),
            (f"A group holds {group.BASE_CAPACITY} + its leader's Charisma modifier members, and "
            f"{group.HERD_BASE} + the leader's Wisdom modifier animals and captives."),
            ("An overextended group rolls each day against its weakest member's Mental Defense "
            "(the leaders are exempt). That member splits off into a group of their own, or with no "
            f"slot free gives {cohesion.NOTICE_DAYS} days' notice and then leaves the guild."),
            ("Who leaves takes by alignment: Lawful only what they wear, Neutral the pack too, Chaotic "
            "everything."),
        ]),
        ("CAPTIVES", [
            (f"Capture (1 point): bind an adjacent fallen foe with a {' or '.join(captives.CAPTURE_TOOLS)}, "
            "which is used up. When the last foe falls the fight runs one more round to bind the fallen."),
            (f"A captive walks with the group, takes {captives.HERD_WEIGHT} of its animal limit, never fights "
            f"or eats, and dies {captives.CAPTIVE_DAYS} days after its capture."),
            ("The group screen lists the captives with their days left and a RELEASE button. A job that "
            "wants one alive takes it straight from the group."),
        ]),
        ("WAGONS & ANIMALS", [
            (f"The road wears a wagon 1 HP every {wagon.WEAR_DISTANCE} distance; at 0 HP it is broken until "
            "repaired with Lumber."),
            ("Cargo on a wagon or on an animal's back counts for the group: food, shop sales and job "
            "deliveries read it."),
            ("Where a wagon cannot go in, anyone left outside guards it. Left alone it may be lost, cargo "
            "and animals with it."),
        ]),
        ("MONEY, FOOD & DEATH", [
            ("There is no guild treasury: money is Copper ($1) and Gold ($100) coins in the packs. They "
            "weigh, split and move like any item."),
            ("Paying spends copper first, then breaks gold and returns change. Gold only comes from the "
            "bank exchange."),
            "Everyone eats every day. Hunger lowers the attributes and brings sickness.",
            "Death is permanent. The run ends only when the whole guild is gone.",
        ]),
        ("CLEAN STOMP & AUTO-WIN", [
            ("Before an ambush the game fights it many times headless, both sides on the AI, and "
            "shows how many of those fights were a clean stomp: everyone standing, no potion, no first "
            "aid, no ammunition spent. It is not the odds of winning."),
            ("AUTO-WIN is offered only when every one of them was a clean stomp. It settles the fight "
            "at once and awards no combat XP."),
        ]),
    ]


def matching(query):
    """The sections whose title or a line contains `query` (all of them for an empty one)."""
    q = query.lower()
    return [(t, lines) for t, lines in sections()
            if not q or q in t.lower() or any(q in ln.lower() for ln in lines)]
