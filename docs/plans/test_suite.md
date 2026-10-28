# Test suite: speed and determinism (2026-10-28)

The suite is the hard gate, and it ran several times per feature: `check_backlog` opened with
the full suite, `pre-commit` ran it at step 2 and again after its own fixes, and development
ran it on top. At 2:39 a run, serial, that was 10+ minutes per feature, most of it spent on a
few sims that check design numbers, not bugs. The gate now takes ~30 s (below).

## Where it stands

- ~3050 tests. Serial: ~2:25 for everything, ~59 s for `-m "not slow and not balance"`.
  Parallel (`-n auto`, 16 cores): ~46 s for everything, ~20 s for the fast tier.
- **One seed per test.** An autouse fixture in `tests/conftest.py` seeds `random` from the test's
  node id (crc32: a str `hash()` changes per process, so per xdist worker): every test rolls
  the same dice alone, serial or parallel, whatever ran before it.
- Two markers, registered in `tests/conftest.py`:
  - `slow` (19 cases, ~34 s): real checks that take over a second — whole AI fights to their
    end (the lab fights, the boss CTF, the Aurochs chase, the encounter sweep), fast sight
    against the rule, the map layout growing, every screen drawn at three sizes, the
    `combat_pairs` replay.
  - `balance` (7 tests, ~37 s): design numbers off a sim — the whole economy report, the Wilds
    over the yard, the Scrapper's role, the walk to the Wilds, the sprint policy, the work
    talents' prices, the supply-run ambush's spread. They break when the AI or a number moves,
    with no bug. Run them (`-m balance`) with `scripts/economy_report.py` after touching
    wages, prices or loot.
- `standard_unit(team)` in `tests/helpers.py`: the one test body, rolled by nothing (a Human
  Guide, every attribute 10, 8 HP, a Quarterstaff, an empty pack, no coin). A test that is not
  about a roll starts from it and sets what it tests on top.
- `pytest-xdist` is in `requirements-dev.txt`.

## What was found

- **Tests that pass by the order they run in.** 846 `Unit(...)` calls in 120 test files roll a
  random race, occupation, attributes and kit. Earlier tests call `random.seed(...)` and leave
  the shared RNG in a fixed state, so a later test sees the same character every serial run.
  Any change of order (a new test, one file run alone, xdist) hands it another one: a Miner
  who already owns the Pick, a Treefolk who eats no ration, a caster with 1 max HP. Fixed with
  `standard_unit` in magic, mine, crafting, wagon, the house vault, the cart's study and
  the gear screen's distribute. Two weak tests went: the Iron Bar smelt (its flow is the
  generic crafting-shift test's, its recipe check only an alarm on a design change) and the
  mine's Work-XP line, folded into `test_progression::test_eligible_work_activities`. The
  per-test seed then turned three more red for good (a pitcher with no recruit slot, a
  Mercenary's own Axe at the yard, a carrier already over the line) and they moved to
  `standard_unit` too. Still leaning on luck, though their seed now holds them green:
  - `test_combat_talents.py::test_gruesome_takedown_demoralizes_nearest_foe_on_down`
  - `test_objectives.py::test_the_medic_marks_its_objective`
  - `test_poison.py::test_a_bite_that_hurts_forces_a_save_and_a_failure_poisons`
  - `test_web_hub.py::test_a_trust_order_opens_the_bankers_jobs_alone`
- **`encumbered` is a derived flag.** A pack change does not refresh it; the caller runs
  `_derive_combat()` (as `outfit.py` does after each potion). A test that reads it after
  `give_to_pack` or `money =` must derive first.
- **Hidden dice.** A one-hour craft rolls 1d20 against a goal of 20: a natural 20 finishes the
  batch and the next assertion fails, 5% of runs. Four crafting tests now pin the roll.

## The gates (2026-10-28)

- `pre-commit` runs `-n auto -m "not balance"` (~30 s: running the `slow` tier every time costs
  ~8 s and spares guessing from the diff whether it touched combat), plus `-m balance` and
  `economy_report.py --quick` when the diff touches wages, purses, prices or loot.
- `check_backlog` runs no tests: every commit passed `pre-commit`.
- During development: the test files of the area being changed.

## Next steps

1. **The four known luck-dependent tests** (above): rebuild them on `standard_unit`. A change to
   `Unit` generation reshuffles every seeded character and may turn another one red; that is
   the same disease, fixed the same way.
2. **Migrate by touch.** `AGENTS.md` now says a test that is not about a roll builds its
   characters from `standard_unit`; a file whose tests are edited moves its `Unit(...)` rolls.
3. **The next speed tier.** ~78 tests between 0.1 s and 1 s make up about half of the fast
   tier's serial 59 s; the rest is pytest's per-test overhead. Look there if `-n auto` is not
   enough.
4. **The balance tier.** `test_economy_sim._rows` replays 50 battles per call and no call shares
   them; a module-level cache would cut the tier by ~10 s if it is ever run often.
5. **When occupations go** (backlog, *Remove occupations*): `standard_unit` drops its
   `set_occupation("Guide")` and must still hand back a Quarterstaff and an empty pack.
