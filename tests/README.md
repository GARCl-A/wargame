# The test suite

The hard gate is `python -m pytest tests/ -n auto -m "not balance"` (about 30 s on 16 cores; serial,
several minutes). `pre-commit` runs it before every commit; `check_backlog` runs nothing. While
developing, run the files of the area you change. Open work on the suite is in
[../docs/plans/backlog.md](../docs/plans/backlog.md).

## Tiers

`pytest-xdist` is in `requirements-dev.txt`. The markers are registered in `tests/conftest.py`:

- `slow`: a real check that takes over a second (whole AI fights to their end, fast sight against
  the rule, the map layout growing, every screen drawn at three sizes, the `combat_pairs` replay).
  Part of the gate: running it every time is cheaper than guessing from the diff whether it touched combat.
- `balance`: a design number off a sim (the whole economy report, the Wilds over the yard, a
  role's pay, the supply-run ambush's spread). It breaks when the AI or a number moves, with no
  bug, so it is out of the gate. Run it (`-m balance`) with `python scripts/economy_report.py --quick`
  when a diff touches wages, purses, prices or loot (`AGENTS.md`; the sims: [../docs/economy_sim.md](../docs/economy_sim.md)).

## Determinism

- **One seed per test.** An autouse fixture in `tests/conftest.py` seeds `random` from the test's
  node id (crc32: a str `hash()` changes per process, so per xdist worker). Every test rolls the
  same dice alone, serial or parallel, whatever ran before it.
- **`standard_unit(team)`** in `tests/helpers.py` is the one test body, rolled by nothing: a Human
  Guide, every attribute 10, 8 HP, a Quarterstaff, an empty pack, no coin. A test that is not about a
  roll starts from it and sets what it tests on top. A rolled `Unit(...)` makes a test pass by the
  order it runs in (a Miner who already owns the Pick, a Treefolk who eats no ration, a caster with 1
  max HP); a file whose tests are edited moves its rolls to `standard_unit`.
- **English by default.** An autouse fixture in `tests/conftest.py` sets `i18n` to `en` before and after each
  test, so a text assertion never meets the saved language. A test of another language sets it itself.
  `test_i18n.py` also fails when a `pt-br` key has no `en` twin or other placeholders (strict about gaps
  once the translation's last phase lands: `STRICT`). `test_i18n_catalog.py` checks the registries' names and
  descriptions follow the language and plays the first days under a `pt-br` whose every name is altered.
- **`encumbered` is a derived flag.** A pack change does not refresh it; the caller runs
  `_derive_combat()` (as `outfit.py` does after each potion). A test that reads it after
  `give_to_pack` or `money =` must derive first.
- **Hidden dice.** A one-hour craft rolls 1d20 against a goal of 20: a natural 20 finishes the batch
  and the next assertion fails 5% of the time. Pin the roll.

## The docs are tested too

`test_readme_map`, `test_reference`, `test_rules_doc`, `test_web_client_doc`, `test_local_readmes`
and `test_plans_docs` fail when a doc names a file, module, class or constant that no longer exists.
Fix the doc, not the test.
