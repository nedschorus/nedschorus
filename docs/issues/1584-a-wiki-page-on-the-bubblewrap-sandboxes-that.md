---
issue: "[A wiki page on the bubblewrap sandboxes that ned-box's programs run agents and test suites in](https://github.com/nedschorus/nedschorus/issues/1584)"
---

# A wiki page on the bubblewrap sandboxes that ned-box's programs run agents and test suites in

## Why

Several programs on ned-box start a bubblewrap sandbox (`bwrap`): the test runner `scripts/run-all-test-suites.py` runs each test suite in one, the cold-read grid's agy cell, `nc-systems/cold-read/cold-read-agy-cell.py`, runs in one, and the benchmark pilot of GHI [A pilot of three past bug fixes, redone by agents on the code as it stood before each fix, to learn whether a benchmark of agent-instructions and hooks can be built from the project's history](https://github.com/nedschorus/nedschorus/issues/1505) runs `claude -p` in one. What each program learned about running inside a sandbox sits today in code comments, in GHI-MDs and in log-store notes, so an agent that writes the next program that starts a sandbox, or runs one program inside another's sandbox, has no one page to read and repeats the same trials.

## What the page says

Facts that the page states, each checked on ned-box when the page is written:

- On ned-box a second bubblewrap sandbox cannot start inside a first, because `kernel.apparmor_restrict_unprivileged_userns = 1` stops an unprivileged process inside the first sandbox from making the new user namespace the second needs.
- The test runner reads the environment variable `RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX` (its constant `SIGNAL_SANDBOX_INSIDE_VARIABLE`); when a program that already runs inside a bubblewrap sandbox sets it, the test runner runs its suites without starting a sandbox of its own.
- The suites that the test runner's `SUITES_RUN_WITHOUT_ANY_SANDBOX` names fail when the test runner itself runs inside a bubblewrap sandbox, each for the reason that constant gives, so the test runner runs them outside any sandbox: most start a bubblewrap sandbox themselves, or start the test runner, whose suites need one; `scripts/mac-request-from-ned-box-forced-command-test.py` runs the real `ssh`, which refuses its configuration files when, inside the sandbox, they show as owned by nobody.
- For each program that starts a sandbox: its path, where its sandbox settings live, what the sandbox shows and hides, and how the agent inside reaches its login file; for the benchmark pilot, the real `~/.claude/.credentials.json` bound in for reading and writing, as "Step 1: the sandbox probe" in `docs/issues/1505-a-pilot-of-three-past-bug-fixes-redone.md` specifies, checked against the probe's record once the probe has run.

The page separates what was observed running, with the date and the command, from what documentation claims.

## Where the page goes

`docs/nedschorus-wiki/nedschorus-bubblewrap-sandboxes-on-ned-box.md` (no file on main has a similar name), checked again by `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md` when the page is written, with a /cold-read before it lands, as every wiki page gets.

## Next action

prime-intellect, which runs the pilot, writes the page after GHI 1505's sandbox probe has run, from the facts above and the probe's record, checking each fact on ned-box, and opens it as a pull request. The page covers the programs that exist on main when it is written. If the user stops the pilot before the probe runs, prime-intellect writes the page without the pilot's sandbox.

## Prior work

- GHI [Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374) builds the test runner's sandbox; read it for facts.
- The nesting probe of 2026-10-10: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/benchmark-sandbox-nesting-probe-2026-10-10.md`.
- GHI [run-agent: one CLI to invoke a Claude or Codex agent headlessly from any caller (Python, shell, either runtime)](https://github.com/nedschorus/nedschorus/issues/41) will start agents too, and will need the page's facts on sandbox nesting.
