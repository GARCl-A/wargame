# GuildScreen vs GroupScreen Split

## What changed
The monolithic `GuildScreen` was split into two distinct screens:
1. `GuildScreen`: A macro-level management screen focused on the Guild as a whole entity. It handles reading the total roster, managing reputations/factions, and changing Guild Leadership. It no longer handles drag-and-drop inventory, equipped gear, or physical locations.
2. `GroupScreen`: A tactical-level screen focused on a specific `Group` (a physical subset of the guild on the road). It is the new home for the `_pack_scroll` (the communal item pool), gear slots (drag-and-drop), and active `Quests` tracking.

## Why it changed
The `GuildScreen` originally tried to handle both macro state (all characters across the world) and tactical state (the backpack of items currently carried by the group). As groups started splitting to go to different nodes, it became architecturally unsound for a global `GuildScreen` to render drag-and-drop mechanics for items that belong to a specific physical location. 
By pulling out the physical/tactical gear management into `GroupScreen`, the UI matches the data model: Groups carry items and gear up; Guilds hold reputation and leadership.

## Rules for future additions
- If a mechanic affects the global progress (e.g. unlocking a new tier of mercenaries, viewing completed deeds), it goes in `GuildScreen`.
- If a mechanic affects the loadout, physical capacity, or current quests of a subset of adventurers on the road, it goes in `GroupScreen`.
- Never put drag-and-drop item management in `GuildScreen` again.
