# Race and build study (combat balance)

How the combat balance of races, builds and vocations is measured. The economy axis is separate (`docs/economy_sim.md`);
combat is balanced first. Code: `scripts/race_study.py` (the fights), `scripts/race_study_builds.py` (the builds),
`scripts/mixed_study_report.py` (the report). Results land in `sim_results/<name>/` (not committed).

## The four standard tests (level 5)

Every fight is a squad of three against a squad of three, fought to elimination, side positions swapped on alternate fights.

| wave | map | the squads |
|---|---|---|
| `mb` | CTF (dark) | **clones**: 3 of one (race, build) cell against 3 of a random cell |
| `ef` | Ermos (lit) | clones, as `mb` |
| `mm` | CTF | **mixed**: 3 random cells against 3 random cells, drawn with replacement |
| `em` | Ermos | mixed, as `mm` |

The opponent is always a uniform draw over the 342 valid (race, build) cells (19 races x 18 builds): no random kit, so the
mean of every score is 50. The score is a win rate x 100 (a draw counts half), the two maps weighted half each.

- **Clones** measure a cell cleanly, so they also give the race x build table. Both sides of every fight are counted.
- **Mixed** squads are what a guild fields: they show role mixes (a squad of three casters) and check that the clones' ranking
  is not an artefact of three identical units. A cell cannot be read from them (one unit in three, too diluted).
- A mixed slot is credited with its side's result, per unit: a build twice in a winning squad scores two wins.

## Running

```
python scripts/race_study.py run --out <name> --waves mb,mm,ef,em --scale 1
python scripts/mixed_study_report.py --out <name>
```

Per cell, `mb` plays 150 clone fights and `ef` 60, times `--scale`; `mm` and `em` play 10000 mixed fights times `--scale`.
Each wave takes its own scale (`mb:0.034,mm:0.17,ef:0.12,em:0.24`: a 5 minute preview, about 8000 fights). Speed on 16 cores:
about 27 fights/s on the CTF and 38/s on the Ermos. `--chunk` is the fights per file: a wave ends with its slowest chunk, so a
short run wants a small one (30). A run never reuses another's chunks: give each a new `--out`.

Sizing, per map, for a 95% interval of +-1 point on a score near 50: about 170 thousand clone fights per build or race (about
87 thousand if both sides are counted, as the report does), 30 to 50 thousand mixed fights for a +-3 read, and for a cell
about 1.7 million. A cell in a short run is only a pattern.

## The report (`PREVIEW.md`)

- **Race, build:** clones and mixed per map, then the **total**: the mixed distance from 50 is scaled back up by a factor
  estimated from the run itself (the ratio of the two spreads, noise taken out, over all races and builds; printed in the header,
  about 2.5) and the two are averaged by inverse variance. The `clones / mixed` column beside it shows where they disagree.
- **Flexibility:** per race, the builds above 50, those above beyond the noise, and the three best builds with their mean.
- **Build x race:** the clones' matrix and its ten best and worst cells with their error.
- **Vocation:** the mean of its six races (the perk is not in a combat score). **Team composition:** mixed only.
- **Points of attention:** nerf or buff, checked against the targets below. *clear* when the whole 95% interval is outside the
  band, *probable* when only the score is: collect more fights before changing a number.

| what | band | notes |
|---|---|---|
| build | 40 to 60 | total score |
| race | 45 to 55 | total score |
| vocation | 47 to 53 | mean of its races' total |
| flexibility | at least 7 builds above 50 and the three best averaging 60 | clones; only a lower limit |
| cell | 30 to 75 | clones; 70 is the target, up to 75 for a signature combo; a cell of a flagged build or race is left to that fix |

The bands are `BANDS` and `FLEX_OK` in `scripts/mixed_study_report.py`.

## Other waves

`race_study.py` has more waves (talents, combos, weapon sweeps, variants, spells, racials, the older field waves `fd`/`fx`),
read back by `scripts/build_study_report.py`; `wave_jobs` is the list. Their output is not part of the standard score.
