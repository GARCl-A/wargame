---
name: gartok-open-world-vision
description: "GARTOK's north star: a megalomaniac open-world guild manager — recruit characters, form specialised groups, run interdependent activities, build bases. Sandbox, no win condition."
metadata: 
  node_type: memory
  type: project
  originSessionId: ac2bdc6f-81a9-4785-b1e2-5f1da2d27f3c
  modified: 2026-09-10T23:57:53.987Z
---

The long-term vision for [[gartok-tactical-project]], in the user's own words
(WhatsApp with a friend, 2026-09-10). This is the "megalomania" the other
memories keep deferring to — the shape the current systems are bridges toward.

## What the game is, ultimately

- **A megalomaniac open-world guild manager.** One player controls *many*
  characters. The base system is a d20 clone the user built years ago ("um clone
  de d20 com complicações desnecessárias"), designed from the start for one
  player running multiple characters — not a party RPG.
- **The core loop: recruit/conquer characters into your guild, then assign them
  to different activities.** The guild grows; members are spent on parallel
  work.
- **Specialised groups.** You end up with, e.g., a team specialised in
  **underwater combat** and a team specialised in **archaeology**. Groups are
  built for a purpose, not one do-everything party.
- **Emergent cross-activity play.** The archaeology team finds a wild map — a
  "treasure island". You then assemble your **water team**, sail them to the
  island, and fight there. One group's output becomes another group's mission.
- **Base building.** The guild founds one or more **bases** and upgrades them
  over time. This has a dependency chain the user finds central:
  - to build, someone has to *do the building* → a **construction group**;
  - to build, you need materials → someone has to *buy* them → a **merchant
    group**;
  - and so on. The interdependence of the specialised groups *is* the game.

## Sandbox — explicitly no win condition

**The game is a sandbox: the player explores whatever they want** (user, on the
"campaign objective" question in the project x-ray, 2026-09-10). There is no
victory screen and that is by design. The run ends only on a full wipe. Progress
is horizontal: more members, more groups, better bases, more of the world seen.
`README`'s "progress toward the game's goal is reputation with factions" is one
*track* of progress, not a finish line — don't add a campaign-win seam unless the
user asks.

## How today's systems map onto it

Everything shipped so far is a first bridge toward one piece of this:

- **Guild = roster, "roams as ONE token", `SquadScreen` = who deploys** →
  the seam for *multiple parties / specialised groups* (still one token today).
- **Activity nodes** (arena, market, tavern, lumber yard, The Wilds) →
  the *assign members to different activities* loop, still serial not parallel.
- **The bank strongbox** ([[gartok-bankers-bank-chest]]) = the guild's first
  *bem imóvel* → the seam for *bases*. The Bankers "sell quality of life".
- **`recruit.py` + `recruited_by`** = *recruit characters*; the binding is inert,
  a seam for morale / the group belonging somewhere.
- **Talent tracks (combat / work / racial)** = *characters get better at what
  they do* → specialisation.
- **`map_lib` / `npc_lib` + editors** = hand-authored world content (the
  "treasure island" maps, the NPCs you conquer).
- **Water combat** ([[gartok-map-size-water]], Swim / drowning / Amphibious) =
  the *underwater team* is already a mechanically distinct thing.
- **Factions & deeds** = one reputation track; more factions = more of the world
  to engage with. Multiple parties, base-building groups (construction, merchant)
  and inter-group missions are all still **megalomania / later**.
