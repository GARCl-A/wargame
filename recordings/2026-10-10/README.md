# Recorded play, 2026-10-10

Two longer campaign saves, recorded with the `PLAY RECORDER` setting. Copied from
`saves/<world>/play.jsonl` (`saves/` is gitignored, this is the kept copy). Their fights are
in `combat_lab/campaign/<guild>-<world id>/`. **Not analysed yet**: with the two runs of 2026-10-08 they make four.

| file | days (last row) | ambushes | what it adds |
|---|---|---|---|
| `Gozatron-702d9d89.jsonl` | ~95 | 4 | Old Road ambushes, which neither 2026-10-08 run touched |
| `GreenSex-a846750e.jsonl` | ~65 | 3 | same; also the Defend the Title bouts |

Feed them to `scripts/play_analysis.py` with the 2026-10-08 runs for the `human` profile
(see *Feed the recorded runs to the economy sim* in the backlog).
