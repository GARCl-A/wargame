# Recorded play, 2026-10-08

Two hand-played runs from a fresh guild, recorded with the `PLAY RECORDER` setting
(`gartok/recorder.py`). Copied from `saves/<world>/play.jsonl`; `saves/` is gitignored, this is the kept copy.

| file | days played | what it shows |
|---|---|---|
| `run1-2b1db6e7.jsonl` | 14 | Pit Scrapper x3 on day 5, Champion day 12, two Wilds hunts day 13, strongbox day 14 |
| `run2-b3e84028.jsonl` | 11 | Champion on day 6 (combat level 0), Wilds hunt day 7, Dictionary mission day 11 (+$250), strongbox day 11 |

Neither reached day 30. `human_profile.json` is `scripts/play_analysis.py` over both
(`python scripts/play_analysis.py <both logs> --out human_profile.json`); feed it to
`economy_guild.py --policies human --profile`.
