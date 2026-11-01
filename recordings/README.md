# Recorded play

Hand-played campaigns kept as data for the economy sim. Each `.jsonl` is a guild's `play.jsonl`
copied out of `saves/<world>/` (`saves/` is gitignored, this is the kept copy), recorded with the
`PLAY RECORDER` setting; the event format is in `gartok/recorder.py`. Every run's fights are archived in
`combat_lab/campaign/<guild>-<world id>/`. `scripts/play_analysis.py <logs> --out <profile>.json` turns
logs into the sim's day-by-day table and decision thresholds (the profiles it once made here were deleted: one
command regenerates them). Frozen: the folders only grow.

| folder | run | days | fights | what it shows |
|---|---|---|---|---|
| `2026-10-08/` | `run1-2b1db6e7` | 14 | 6 | Pit Scrapper x3 on day 5, Champion day 12, two Wilds hunts day 13, strongbox day 14 |
| | `run2-b3e84028` | 11 | 2 | Champion on day 6 (combat level 0), Wilds hunt day 7, Dictionary mission day 11 (+$250), strongbox day 11 |
| `2026-10-10/` | `Gozatron-702d9d89` | 96 | 28 | Old Road ambushes (4), which neither 2026-10-08 run touched |
| | `GreenSex-a846750e` | 65 | 34 | ambushes (3) and the Defend the Title bouts |
| `2026-10-12/` | `Caravana-Do-Homem-Verde-95ea6648` | 205 | 62 | the longest run: one row per day, order, buy/sell, fight, talent |
| `2026-10-19/` | `Olhos-de-Odin-b5b8fe2b` | 21 | 7 | Work opening, Axe purchases (d2, d5), Adelio dethroned on d12 ($120 purse), Rapiers ($130), wipe on the d21 Wilds hunt |
| | `Caneco-Mijado-ef6890c7` | 103 | 33 | 30 battles won, 9 faction deeds, Donkey + Cart ($330), split groups, Claim fenced and defended, 17 crafting shifts (Dictionary of Ankarin) |
