---
issue: "[The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts](https://github.com/nedschorus/nedschorus/issues/2259)"
---

# The test runner `scripts/run-all-test-suites.py` records which code each test case covers, using coverage.py's per-test contexts

## What this GHI asks for

A mapping from each test case to the lines and branches of code it executes, recorded by the test runner, `scripts/run-all-test-suites.py`, when it runs the test suites. coverage.py can record, for each line it measures, which test executed it, through its dynamic contexts; coverage 7.16.2 is pinned in `nc-systems/general-tools/python-libraries-pinned-requirements.txt`, and the runner does not use it today.

This GHI is a placeholder: no design exists yet. The design answers these questions:

1. How the test case boundaries reach coverage.py. A suite here is a script, in Python or shell, that prints one PASS or FAIL line per test case after the case ends, rather than a pytest file, and coverage.py's dynamic contexts need to be told when each case starts, in the process being measured.
2. What is recorded for a suite that is not in Python, for the programs a suite starts, and for a suite that crashes, times out or prints no PASS or FAIL line.
3. Which test runs record the mapping, given that measuring coverage slows a suite; how each suite's coverage data leaves its nc-test-sandbox, whose `/tmp` and checkout overlay are thrown away when the suite ends; and how the data of suites run at once is combined.
4. Where the mapping is stored and for how long, and what the readers named under Related need from it, such as branches rather than only lines.

## Why

The user decided the mapping on 2026-10-14, as part of point 4 of the approval-walk ned-box-head-test-runs-in-isolated-test-environments-2026-10-14, recorded in GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374), whose GHI-MD is `docs/issues/1374-each-test-suite-on-ned-box-runs-in.md`. Point 4 reads: "Later, as a step of its own, a mapping from each test case to the code it covers." That GHI-MD's list of parts to reuse names "coverage.py with its per-test contexts for the later coverage mapping". The build of that GHI did not include the mapping, and that GHI closes with this GHI carrying the work.

## Related

On 2026-10-30, `scripts/ghi-guide-agent-ask.py --include-closed`, asked for a GHI that builds this mapping, found none. Three GHIs would read such a mapping without building it: GHI [#18](https://github.com/nedschorus/nedschorus/issues/18) (`docs/issues/18-write-test-plan-riders-and-test-evidence-rules.md`), whose rule 2 has each planned test declare the code paths it reaches and compares them with the paths coverage.py measures; GHI [#35](https://github.com/nedschorus/nedschorus/issues/35) (`docs/issues/35-declaration-vs-reality-posit-ladder.md`), a research thread whose point 3 makes the same comparison for every test; and GHI [#2135](https://github.com/nedschorus/nedschorus/issues/2135) (`docs/issues/2135-mutation-testing-before-push-mutates-only-failure-handling.md`), which decides what code mutation testing mutates, and could use the mapping to choose the test suites that run against each mutant. The design reads all three, so that one mapping serves them.

## Next action

Write the design in this GHI-MD, answering the four questions above after reading the three GHI-MDs under Related; then add the line `kind: design` to the front matter at the top of this GHI-MD, between its `---` lines, and build the mapping in its own pull request.
