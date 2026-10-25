---
issue: "[Mutation testing of a module with many dependent test suites fails before any mutant runs](https://github.com/nedschorus/nedschorus/issues/1939)"
---

# Mutation testing of a module with many dependent test suites fails before any mutant runs

## Reproduction

On ned-box, in a checkout at main e9460a4e:

```
python3 scripts/pull-request-mutation-testing-survivors.py --head 53b49b16aa116b4b84ccfcef2164cfe17bdbe9ca --base 0ca5650eabbb27cb7f30d9b81e7ee3bd65d781da --cosmic-ray-venv /tmp/cosmic-ray-venv
```

It exits 2 and prints `pull-request-mutation-testing-survivors: not run — the suites for nc-systems/general-tools/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py could not be run on the unmutated head, so no mutant can be judged`, followed by cosmic-ray's traceback, which ends `OSError: [Errno 7] Argument list too long: 'sh'`. Pull request [git_failure_next_step_lines takes program only with the misspelt-name line](https://github.com/nedschorus/nedschorus/pull/1937) changes that module at head 53b49b16, and 71 test suites depend on it. The agent-seat MD-skills hit the same failure while preparing that pull request, on 2026-10-25 UTC.

## What is wrong

`scripts/pull-request-mutation-testing-survivors.py` runs mutation testing with cosmic-ray on the lines a pull request changed. cosmic-ray runs one test command for every mutant. `test_command_for()` (lines 178 to 207 on main) builds that command: it joins the launch of every dependent suite, each wrapped in its own test sandbox prefix (a `bwrap` command line of several hundred characters), into one `sh -c` argument. Linux refuses a single argument longer than `MAX_ARG_STRLEN`, 128 KiB, so once a module has enough dependent suites the command cannot start at all. The fresh Claude reviewer of pull request 1937 located the cause in [its review](https://github.com/nedschorus/nedschorus/pull/1937#pullrequestreview-5641527453); the reproduction above confirms it.

The per-suite sandbox prefix came with pull request [run-all-test-suites: each suite in a test sandbox](https://github.com/nedschorus/nedschorus/pull/1427). Before it, one shorter prefix served all suites, so the limit was further away.

## Why it matters

CLAUDE.md requires code that handles a failure to carry a test checked by mutation testing. For a widely shared module, the shared `-common.py` files above all, the script cannot run, so the author falls back to hand-made mutants, as MD-skills did on pull request 1937 (7 mutants by hand), and the reviewer has no survivor list to check. The script does report the failure and exits 2, so nothing passes silently; the cost is the missing check.

## Next action

The agent-seat reboot-test, which wrote the per-suite test sandbox prefix in pull request 1427, changes `test_command_for()` and its caller `mutation_test_one_file()` in `scripts/pull-request-mutation-testing-survivors.py` so the command's length does not grow with the number of suites. One way: write the chain into a script file in the run's temporary directory, one file per mutated module, and give cosmic-ray `sh <that file>`. Add a case to `scripts/pull-request-mutation-testing-survivors-test.py` that builds the command for enough suites to pass 128 KiB and checks that the operating system starts it, without running real suites. Then rerun the reproduction above and record its exit code and survivor count under a new heading, Outcome, in this GHI-MD.
