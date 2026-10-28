# Test suite: speed and determinism (2026-10-28)

The suite is the hard gate, and it runs several times per feature: `check_backlog` opens with
the full suite, `pre-commit` runs it at step 2 and again after its own fixes, and development
runs it on top. At 2:39 a run, that was 10+ minutes per feature, most of it spent on a few
sims that check design numbers, not bugs.

## Where it stands

- ~3030 tests. Serial: ~2:25 for everything, ~59 s for `-m "not slow and not balance"`.
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
- `pytest-xdist` measured on 16 cores: the full suite in ~44 s, the fast tier in ~15 s. Not in
  `requirements-dev.txt` yet: see step 1.

## What was found

- **Tests that pass by the order they run in.** 846 `Unit(...)` calls in 120 test files roll a
  random race, occupation, attributes and kit. Earlier tests call `random.seed(...)` and leave
  the shared RNG in a fixed state, so a later test sees the same character every serial run.
  Any change of order (a new test, one file run alone, xdist) hands it another one: a Miner
  who already owns the Pick, a Treefolk who eats no ration, a caster with 1 max HP. Fixed with
  `standard_unit` in magic, mine, crafting, wagon, the house vault, the cart's study and
  the gear screen's distribute. Two weak tests went: the Iron Bar smelt (its flow is the
  generic crafting-shift test's, its recipe check only an alarm on a design change) and the
  mine's Work-XP line, folded into `test_progression::test_eligible_work_activities`. Still open, each failing about once in 12 parallel runs:
  - `test_combat_talents.py::test_gruesome_takedown_demoralizes_nearest_foe_on_down`
  - `test_objectives.py::test_the_medic_marks_its_objective`
  - `test_poison.py::test_a_bite_that_hurts_forces_a_save_and_a_failure_poisons`
  - `test_web_hub.py::test_a_trust_order_opens_the_bankers_jobs_alone`
- **Hidden dice.** A one-hour craft rolls 1d20 against a goal of 20: a natural 20 finishes the
  batch and the next assertion fails, 5% of runs. Four crafting tests now pin the roll.

## Next steps

1. **One seed per test.** An autouse fixture in `tests/conftest.py` that seeds `random` from the
   test's node id: every test sees the same dice in any order, serial or parallel. It does not
   cure a test that leans on luck, it stops luck from turning a run red. Then add
   `pytest-xdist` to `requirements-dev.txt` and run the gate with `-n auto`.
2. **The four known luck-dependent tests** (above): rebuild them on `standard_unit`.
3. **Migrate by touch.** A file whose tests are edited moves its `Unit(...)` rolls to
   `standard_unit` where the test is not about the roll; add that convention to `AGENTS.md`.
4. **The skills' gates.**
   - `pre-commit`: `-m "not slow and not balance"` (with `-n auto` once step 1 lands); add
     `-m slow` when the diff touches combat, AI, a scenario, vision or the board, and
     `-m balance` + `economy_report.py` when it touches wages, prices or loot. Its second run
     after its own fixes runs only the files those fixes touched.
   - `check_backlog`: drop the full run at the start (`main` was green at its last commit), or
     run the fast tier.
   - During development: the test files of the area being changed.
5. **The next speed tier.** ~78 tests between 0.1 s and 1 s make up about half of the fast
   tier's 59 s; the rest is pytest's per-test overhead. Look there if step 1 is not enough.
6. **The balance tier.** `test_economy_sim._rows` replays 50 battles per call and no call shares
   them; a module-level cache would cut the tier by ~10 s if it is ever run often.
7. **When occupations go** (backlog, *Remove occupations*): `standard_unit` drops its
   `set_occupation("Guide")` and must still hand back a Quarterstaff and an empty pack.
