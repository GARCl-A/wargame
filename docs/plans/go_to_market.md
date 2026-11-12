# Go to market: from a playtest build to a game that is sold

The order of work between today (version 0.1.9, one outside tester) and charging for the game. It is a
strategy, not a build plan: each item points to the backlog entry or the plan that builds it. Written
2026-11-12 from a commercial review of the repo and of the real screenshots in
[../photos/12112026/](../photos/12112026/).

The market numbers here (prices, wishlists, units, costs) are estimates from general knowledge of the
indie market, not researched figures. Treat them as orders of magnitude and check each before spending
money on it.

## Where the game stands

- **What it is on a store shelf:** a guild-management sandbox with turn-based tactical combat, d20 rules
  and permanent death. Its shelf neighbours are Battle Brothers, Wartales, Our Adventurer Guild, Low Magic
  Age and Kenshi.
- **What it has that they do not:** routines (secondary bands run by themselves on orders the player
  writes); no guild treasury, money and knowledge live on each character; the origin story (rebuilt from the
  character generator of a lost tabletop RPG); the engraved-bestiary look.
- **What it lacks to be sold:** proof that strangers keep playing. One outside tester played two hours.
  The backlog itself records that combat may dull, that levelling opens nothing new, and that the game
  "still lacks soul". More systems do not answer that; watching people play does.

## The path

Five gates, in order. A gate is passed when its exit test is met, not when its list is ticked. Wishlists
only start at gate 2 and grow with time, so gate 2 is worth reaching early even while gate 3 is far.

| Gate | What opens | Exit test |
|---|---|---|
| 1 | The game holds a stranger | 5 to 10 people who are not friends; median first session of 45 minutes or more; half of them open it a second time |
| 2 | Steam page, wishlists | The page is live with a trailer and at least five store-ready screenshots |
| 3 | Public demo | The demo holds a median of 30 to 45 minutes; no fault ends a session |
| 4 | Early Access, paid | 20 hours of play that does not repeat; a save survives an update; 7 to 10 thousand wishlists |
| 5 | Version 1.0 | The author's call; price goes up |

### Gate 1: the game holds a stranger (before thinking about selling)

Nothing here costs money. It is the backlog's *Before the friends' playtest* plus one thing it does not
have: testers who are not friends.

1. Finish *Before the friends' playtest* in [backlog.md](backlog.md): the combat AI's three defects, the tutorials, the pt-br pass.
2. **The first hour teaches where the decision is made.** The outside tester read neither the wiki nor the
   tutorial cards and learned food, the draft and Delay the wrong way (*Playtest notes, 2026-10-31*). Each of
   those is a small fix; the pattern is the gate.
3. **Recruit strangers.** A free build on itch.io and posts where the genre's players are (the communities
   of the neighbours above, tactical RPG forums, Brazilian indie groups). Ask for one thing: the recording
   the game already writes (`play.jsonl`, `errors.jsonl`) and how long they played.
4. **Measure, do not ask.** Session length and whether they came back say more than opinions. The recorder
   already gives days played and fights; add nothing until this is read.

Decide here, because the later gates depend on it (see *Decisions that are the author's*): the store name,
the stance on AI art, Early Access or a finished 1.0.

### Gate 2: the store page (before wishlists)

A page is a promise made with pictures. It does not need a finished game; it needs frames that look
finished and a sentence that says what the game is.

1. **The frames.** Build [storefront_polish.md](storefront_polish.md): packages A, B, C and G are small;
   D (the fog) decides whether the Pit can be shown at all. Then retake the photos following that plan's
   last section (presentable names, no empty states, campaign fights instead of lab fights, the board zoomed).
2. **Motion and sound for a trailer:** the same plan's package E (a blow moves the token); the music is in.
   A trailer of 30 to 45 seconds: the map with two bands walking, a routine written and then running, a
   fight with the fog opening, a death and its memorial.
3. **The capsule image** (the picture in Steam's lists; it drives clicks more than anything else on the
   page). The author is not an artist; three ways, cheapest first:
   - Compose it from public-domain engravings (Doré, Dürer, old bestiaries, from museum and library
     archives) with a strong title. It matches the game's look and is not generative AI.
   - Commission only the capsule from an ink or engraving illustrator. Estimate: R$ 800 to R$ 2,500 for the
     set of sizes; ask for quotes.
   - A crowdfunding campaign to pay an artist only makes sense after the page exists and has an audience.
4. **The name and the one sentence.** "GARTOK Tactical" does not say what the game is. A subtitle or a
   tagline carries it (guild, sandbox, tactics, permanent death, in that sentence).
5. **The AI disclosure**, stated plainly as the author already intends (*Release*, in the backlog): the
   portraits and a few tree sprites are generated, the rest is composed by code. The page's capsule and key
   art should not be generated: part of this audience rejects it on sight.
6. **Steam Direct.** US$ 100 per game, paid once and returned after US$ 1,000 of revenue. There is a wait of
   about 30 days between paying and being allowed to release, and the page must be up at least two weeks
   before launch. Paying early costs nothing extra and starts the wishlist clock.
7. **The page's languages:** English and Brazilian Portuguese (both exist in `locales/`).

Not needed for this gate: a native window, Steamworks, save migration, more content.

### Gate 3: the demo

A demo is the main wishlist engine for a game without a publisher, and Steam Next Fest is where it counts
most. A game enters Next Fest once, so the demo goes in only after it passes its exit test on its own.

1. **A native window.** Today the game opens in Edge or Chrome in app mode, which reads as a web page and
   depends on the browser each machine has. Recommended: an Electron shell that starts the Python server as
   a child process and closes it on exit. It ships its own Chromium, so every player sees the same rendering,
   and it is the usual route for web games on Steam. Cost: about 100 MB more to download, and the Steam
   overlay on Chromium windows needs testing. The lighter options (pywebview, Tauri) keep the dependency on
   the system's browser engine. This replaces *Native window for the web client* under *Deprioritised* in
   the backlog.
2. **The demo's cut.** The first 10 to 15 days of a guild, or up to the first title in the Pit: enough to
   draft, travel, work, fight, lose someone and write one routine. A save from the demo should load in the
   full game.
3. **Steam Playtest first.** It is free, lives on the same page, feeds wishlists and replaces itch.io as
   the place strangers get the build. Run it before the demo to find what breaks.
4. **Faults.** The error card and `errors.jsonl` exist; add a way for a tester to send that file.
5. **Settings a stranger expects:** window size and full screen, a scale for the interface text.
6. **Then Next Fest**, in whichever edition the exit test is met before (check the dates and the sign-up
   deadline on Steamworks; sign-up closes months ahead).

### Gate 4: charging (Early Access)

Early Access fits: the game is a sandbox that grows, every neighbour above went through it, and its players
expect it. What must be true before the first sale:

1. **A save survives an update.** Today the rule is `persist.SAVE_VERSION` with no migration (`AGENTS.md`,
   *Saves*). That is right for development and unacceptable for paying players. Before the first sale:
   either migrations from the launch version on, or a stated policy that old versions stay playable as
   Steam branches. This is the largest engineering item on this list.
2. **Twenty hours that do not repeat** (the author's own bar, *Release* in the backlog). Today there is one
   region of about twenty places, twelve spells and four authored maps. The items that give a middle game:
   the production chain, Loyalty ([loyalty.md](loyalty.md)), the magic arc's later missions, more dangerous
   places with their own fights.
3. **Something to aim at.** The game has no win condition by design. A sandbox still needs arcs that pull:
   the reputations, the titles, the claim, the quests. A player at hour ten must be able to say what they
   are trying to do next.
4. **Levelling pays.** Recruiting gets harder as the guild grows, so the headcount ceiling comes early and
   the player must improve who they have. The player has to feel that it works: the new talents and body actions start it, and the playtests of gate 1 say whether it is
   enough.
5. **Steamworks:** achievements and cloud saves (achievements do not depend on the overlay; only the
   on-screen notice does).
6. **Names inherited from other games.** Some race and spell names come from Dungeons and Dragons (Kenku,
   Goliath, Grippli, several spell names). Have someone qualified confirm which are under an open licence
   and which need renaming, before money changes hands. This is not legal advice.
7. **Credits and licences** for the icons, fonts and sounds are complete on the credits screen.
8. **Receiving the money.** Brazil has no tax treaty with the United States, so Steam withholds tax on the
   part of sales made there. Whether to receive as a company or as a person changes the Brazilian tax a lot:
   talk to an accountant before the Steamworks tax interview.

Wanted, not required: Simplified Chinese. It is a large audience for this genre, but `locales/en.json` is
about 335 KB of text, so a paid translation is a few thousand dollars. Decide it with the wishlist numbers
by country in hand.

### Gate 5: version 1.0

Out of scope here. The price goes up at 1.0 and GOG becomes worth a submission (its audience fits).

## Where to sell

- **Steam first and nearly only.** It is where this genre's revenue is.
- **itch.io** as the free public build during gate 1, nothing more: it brings neither revenue nor wishlists.
  This revises *Release* in the backlog, which had itch.io as the first paid home.
- **GOG** after 1.0.
- **Not worth it:** Epic, mobile, consoles, controller and Steam Deck support. The interface is dense and
  made for a mouse.

## Price

- Early Access: US$ 14.99. Version 1.0: US$ 19.99. In Brazil, Steam's suggested regional price for each
  (roughly R$ 45 to 50, then about R$ 60).
- Above that the game competes with Battle Brothers and Wartales without their polish. Under US$ 10 the
  price says "small game" to players who pay for depth.

## What to expect

First twelve months of Early Access at US$ 14.99. Per copy, after regional prices and discounts, taxes and
refunds, Steam's 30% and the withholding, about US$ 5 reaches the author before Brazilian tax.

| Scenario | Wishlists at launch | Copies in a year | Net, about | What has to happen |
|---|---|---|---|---|
| Conservative | 1 to 2 thousand | 500 to 1,500 | US$ 2,500 to 7,000 | Launches as it is, no demo, a weak trailer |
| Realistic | 7 to 10 thousand | 4 to 7 thousand | US$ 20,000 to 35,000 | The page up six months or more before, a demo in Next Fest, the frames fixed |
| Optimistic | 30 thousand or more | 30 to 50 thousand | US$ 150,000 to 250,000 | The demo holds, a streamer of the genre adopts it, Chinese is in |

Most independent games on Steam land under the conservative row. The optimistic one needs execution and luck.

## What costs money

| Item | Estimate | Gate |
|---|---|---|
| Steam Direct fee | US$ 100, returned after US$ 1,000 of revenue | 2 |
| Capsule art, if commissioned | R$ 800 to 2,500 | 2 |
| Music, if licensed | from free (open licences) to a few hundred dollars | 2 |
| Accountant and a company to receive | varies | 4 |
| A reading of the inherited names | varies | 4 |
| Simplified Chinese | a few thousand dollars | 4, optional |

## Decisions that are the author's

1. **The store name and its subtitle.**
2. **AI art.** Keep the generated portraits and disclose them (cheapest; costs some of the audience), or
   replace them over time. Either way, not on the capsule.
3. **Early Access or a finished 1.0.** This plan assumes Early Access.
4. **The fog's look** (package D of [storefront_polish.md](storefront_polish.md)).
5. **Save policy after launch:** migrations, or old versions kept as branches.
6. **Whether to translate to Simplified Chinese**, once wishlists by country exist.

## What not to do yet

- Add systems to answer a retention problem that has not been measured.
- Enter Next Fest with a demo that has not passed its exit test: the slot does not come back.
- Spend on translation, a company or a lawyer before gate 2 shows whether anyone wishlists the game.
