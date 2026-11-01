# Loyalty, the oath and who the members are

Status: **design talk of 2026-10-23, no code.** Backlog: *Needs more information -> Loyalty* (its
first concrete step, *Remove occupations*, is *Ready to do*). Moved here from the backlog so the
backlog keeps tasks and this keeps the design; when a decision below is built, its prose moves to
`RULES.md` and leaves this file.

Replaces the 2026-10-22 "drama engine" and the oath of the old *Found-the-guild charter* entry. Its first concrete
step is *Remove occupations* in [backlog.md](backlog.md).

**The problem.** "No soul, it is all one big calculator": a character is a statblock plus an
alignment that only serves recruitment and shops; nobody wants anything. Several systems were built
each for a piece of the same need (vocation: "the guild must have something"; alignment: "alike people
like each other"; the oath: "why the member stays"; leadership and cohesion: a limit on growth) and
none of them talks to the others. The author's worry: piling up subsystems of friction ("making a
duck"). The aim is fewer concepts covering those roles, not more content. The test: after an hour
of play the player tells a story with a character's name in it.

**Decided.**
- **The player is the guild**, an entity outside the groups; that is why it commands several groups
  at once. No avatar: an avatar dies to a wolf in a game built on a disposable early squad. Members
  are **partners, not employees** (no wages, no treasury: the guild has to be worth it to them).
  The guild leader and the group leaders are managerial roles, not a hierarchy.
- **A member is a statblock + named traits + an aspiration.**
  - **Occupations go** (a classless game; an occupation is only a preset of the random item roll).
  - **The aspiration** is what the member wants to become: a mage, famous, rich (their own coins), to
    see the world, a quiet life, to serve faction X. The main loyalty input, and it ties loyalty to
    progression: a talent or an initiation spent on them is spent toward what they want. A fulfilled
    aspiration is a story beat (a new one, or they retire a legend).
  - **Alignment becomes named traits.** The two axes stay underneath, shown as words (proposed:
    Steadfast / Fickle on the law axis, Merciful / Ruthless on the moral one). What alignment does
    today, in the author's words: keeping one's word, holding the formation (law); not killing, not
    stealing (moral). The traits carry both halves: how the member **behaves** when the player is not
    in control (`ai/`'s temper, what a deserter takes, `dialogue.py`) and what they **value**
    (loyalty inputs: a Merciful one suffers a captive left to die). Further personality traits, if
    ever, are more inputs of the same bar.
- **Loyalty: one bar per member, shown as a number** (the author likes a transparent game). Inputs:
  doing what they want, their relations with the other members, killing when they did not want to,
  progressing when they wanted to, the oath kept or broken. At 0% they announce they are leaving
  (reuse `cohesion.py`'s 7-day notice, the window where the player can still react).
  - **It accelerates**: the more loyal, the more they tolerate (losses are dampened); the less loyal,
    the faster it falls.
  - **Founders start at ~70%**: they founded the guild. Recruits start mid-bar (~50%), whatever the
    pitch; one who has little in common with the guild simply falls fast, with no special rule.
  - **A group past its leader's capacity costs the group leader loyalty**, in place of `cohesion.py`
    rolling against the weakest member's Mental Defense (absorbs the leadership open problem).
- **Relations between members are in**, and they are also a reason to run more than one group
  (keeping two who cannot stand each other apart). How the player manages them is open.
- **Recruiting is one person convincing another**, never the guild recruiting. The recruiter pitches
  who the guild is and its oath ("this is us, this is the oath, you in?"); CHA still matters, it covers
  the gap between what the guild offers and what the candidate wants ("not exactly what you want, but
  close: try it?"). The recruiter's traits against the candidate's can stay (alike people get along);
  the guild-vs-candidate alignment distance goes.
- **The tavern is the world.** Who drinks there is there on their own; the player has no say in who
  shows up. (Rejected: a "races the guild welcomes" list steering the tavern or the draft. It locks the
  player out of the Grippli they meet later and fights world-first.)
- **The draft stays, as the founding**, not a recruitment: nobody convinced anybody. Choosing a
  starting crew among random strangers is common in the genre and liked (RimWorld's colonists,
  Wildermyth); attachment comes from what happens to a character, not from picking them (XCOM).
  Today's draft is a numbers pick; once candidates show traits and an aspiration it becomes a choice
  between people.
- **The oath** (pf2e's edicts and anathemas):
  - **Composed by the player, choice by choice**, along axes with trade-offs (e.g. killing: everyone
    must die / free / nobody dies). The guild is as complex as the player wants it to be.
  - **Every clause points at an event the game already records**, or it is abstract. "Get rich" alone
    is no trade-off (every player wants it); it works as an edict loyalty reads. Candidates from the
    talk: "nobody is left behind" (a downed ally or body abandoned), "no blood for nothing" (killing
    one who surrendered, a captive left to die), "we come home alive" (withdrawing is never shameful),
    "we keep the City's law" (a crime, `justice.py`).
  - **Binds every member**, founders and recruits alike.
  - **Can never be changed**: the guild is the player, and the oath is the commitment the player makes
    by starting the run.
  - **Factions and NPCs do not react to the oath**, only to what the guild does.
- **Vocation stays for now, on probation.** It is cut, merged or diluted into another system as soon
  as one does its job better. Today it is six races + one perk; that coupling makes a fan of one race
  pick a perk they do not want, and the author only ever plays Caravan or Delvers: those two touch
  something done every day (travel, gathering), the other four rare events (the cohesion roll, a
  Cautious ambush, the opening read, every 10th day's food). If it is reworked, each perk acts on a
  daily loop.

**Rules of thumb for every input and output.** An input is an event the game already has (a death,
hunger, days at the Yard, the loot, a withdrawal, a crime); an output is a mechanism that already
exists (leaving, recruiting, maybe combat morale); nothing needs a new screen to manage, it shows as a
line in the log or a one-off request ("Brakka wants a double share or leaves with their own"); it
produces a decision (profit against a person, a person against a person), not only an upkeep like
hunger. And not everything feeds loyalty: if perk, oath, aspiration and trait only move the same bar,
loyalty becomes the new calculator.

**Proposed, not yet answered.**
- **Origins** (a starting situation in place of a perk: "a wagon and a debt to the Bankers",
  "survivors of a Ruins expedition") are the form the genre likes best for a founding; new content, so
  noted, not now. A candidate for what the vocation could become.

**Open (closes with play or numbers).**
- How far each input moves the bar, the acceleration curve, what high loyalty buys besides tolerance.
- The aspiration list and how each one is read off existing state.
- The oath's axes and the steps on each.
- How the player sees and manages relations between members.
- What the economy sim (`economy_guild.py`) and `cohesion.py` must learn.
- Presentation, later: a founding charter that writes itself line by line, signed with the banner and
  the oath, the first entry of the guild's chronicle.
