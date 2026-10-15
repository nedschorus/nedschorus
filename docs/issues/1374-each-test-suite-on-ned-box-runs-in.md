---
issue: "[Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/issues/1374)"
---

# Each test suite on ned-box runs in its own throwaway test environment, and suites start by free CPU and memory instead of waiting for a machine-wide lock

## What happens today

Every test run on ned-box goes through `scripts/run-all-test-suites.py` (`scripts/run-suite-in-signal-sandbox.py`, which runs one suite or one mutant, uses its code), and that program takes one exclusive lock for the whole machine, `~/.claude/.run-all-test-suites.lock`. A second test run waits until the first finishes. Everyone waits on that one lock: merge-lane-2's head test run of each pull request, each author's test run before the author pushes, and each reviewer's mutation testing through `scripts/run-suite-in-signal-sandbox.py`.

The lock exists because the suites share the machine. Each suite runs inside bwrap with only its process IDs private (`bwrap --dev-bind / / --unshare-pid --die-with-parent --proc /proc`, `SIGNAL_SANDBOX_BWRAP_ARGUMENTS` in `scripts/run-all-test-suites.py`): it sees the real `/tmp`, the real home directory and the real tmux sockets. The docstring of `scripts/run-all-test-suites.py`, under "ONE RUN AT A TIME PER MACHINE", records the reproduction: on 2026-09-21, two overlapping runs of `scripts/resupervise-seat-test.py` both exited 0 and printed "all cases passed" while each had silently skipped cases, because both used the same tmux sockets under `/tmp`.

## Why it matters

Measured by merge-lane-2 on 2026-10-14 from its last 40 head test run records (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/hr/*/log-store/pull-request-head-test-runs/ned-box/*.txt`, the lines "seconds waiting for the machine's lock" and "wall-clock seconds"): 15,707 seconds (4.4 hours) waiting for the lock against 22,191 seconds (6.2 hours) of testing; the longest single wait was 1,547 seconds. ned-box has 16 cores and 59 GB of memory, usually runs at a load average of 5 to 11, and showed 48 to 49 GB of memory available in every reading that day. In 13 large head test runs at `-j 16`, a median of 7.7 suites were running at any moment, and the longest suite took 94% of the run's time. The lock, not the hardware, holds the test runs back, and the queue grows with every agent-seat that tests.

The shared state is also a hazard to the running agent-seats: on 2026-10-14, a reviewer's hand mutant of `scripts/recover-crashed-seats.py` for pull request [#1315](https://github.com/nedschorus/nedschorus/pull/1315) bypassed the test's stub and ran `tmux -L seat-a has-session` and `tmux -L default has-session` against the real tmux server.

## What the user decided

The user decided each point in approval-walk ned-box-head-test-runs-in-isolated-test-environments-2026-10-14 on 2026-10-14; the walk-minutes are `docs/walk/ned-box-head-test-runs-in-isolated-test-environments-2026-10-14-minutes.md` in merge-lane-2's checkout, shipped to the log-store when the walk closes.

1. One throwaway test environment per test run, and no machine-wide one-run lock. Built as one environment per suite: every suite, including suites of the same test run, gets its own private `/tmp`, home overlay and tmux socket directory (`TMUX_TMPDIR`), created when the suite starts and deleted when it ends, because suites of one run also share those today.
2. The environment extends the existing bwrap sandbox; no Docker, no extra Unix accounts, no root. Measured on ned-box with bubblewrap 0.11.1: a suite start with a private `/tmp`, home and tmux directory took 8.7 ms against 5.8 ms today, so nothing is pre-created or cached.
3. Dynamic admission shared by every concurrent run: a new suite starts only while machine CPU use averaged over the last 5 seconds is under 50% and available memory is above 10 GB; at most 4 new suites start per second machine-wide; never more than 64 suites run at once machine-wide; every suite runs at low priority (`nice`). The runner records machine CPU, available memory and load every second, so both thresholds can be moved from evidence.
4. Timing records: the time of every test case (the suites already print one PASS or FAIL line per case; the runner timestamps them), and per suite its CPU seconds, peak memory and time spent waiting for admission, taken from a cgroup per suite (cgroup v2 `cpu.stat` and `memory.peak`), which counts every process the suite starts. A history of every failing test case, with its pull request, its commit, and whether a code change fixed it (a caught defect) or it passed on rerun (a flaky failure); a retry keeps the failed attempt's output. Later, as a step of its own, a mapping from each test case to the code it covers. Separately, one script summarizes, per agent-seat, the time spent waiting on tests, on reviews, on the user and idle, from the existing JSONL transcripts, with no new logging in the agents.
5. The home directory: each suite sees the real home through a throwaway copy-on-write overlay (`bwrap --overlay-src $HOME --tmp-overlay $HOME`; measured at 7 ms per start, and a write inside did not reach the real home). Credential files are covered with empty files, so no test can read a token: at least `~/.config/nedschorus/*.token`, `~/.claude/.credentials.json` and `~/.codex/auth.json`, listed in one constant in the runner, mounted with bwrap's `--ro-bind-try` so a missing file does not stop the suite; no scan of the whole home directory, which is what made GHI [#1323](https://github.com/nedschorus/nedschorus/issues/1323)'s test case slow. The checkout under test is a copy-on-write overlay on top, so a suite can write in it and its writes are gone after the suite (the user's "y" in reboot-test's agent-session on 2026-10-15, replacing "mounted writable"). Everything else outside the home directory, `/tmp` and the checkout is mounted read-only, with `/dev` and `/proc` as bwrap provides them and `/run` an empty tmpfs (bwrap provides no `/run`), which closes a hole that exists today. The user's condition: "It better be 100% safe", proven by the escape test below.
A suite that cannot be admitted waits, with no time limit, and the runner prints once a minute what it is waiting for (CPU, memory or the ceiling). An exception suite takes the exception lock first and an admission slot second, so it never holds a slot while it waits for the lock.
6. Three kinds of suites, and the report says which kind each suite ran as: virtualized on ned-box (the default); local on ned-box, the few suites that cannot run inside bwrap at all (four today, listed with reasons in `SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX`), which share a new lock of their own, so only one of them runs at a time on the whole machine, across every concurrent run, and each takes an admission slot; and Mac-only test cases, which skip on Linux and run on the Mac. The Mac is not used as an extra test machine for ned-box's runs. On the Mac, the runner keeps today's behaviour: the overlay and the admission are Linux features, and a Mac test run must pass before the change merges.

## Why extend our runner rather than adopt a tool

Two Codex research reports, run by merge-lane-2 on 2026-10-14 at the user's request, compared the maintained open-source options: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/codex-research-test-isolation-tools-2026-10-14.md` (bubblewrap, firejail, nsjail, minijail, systemd-run, Bazel's linux-sandbox, rootless Podman; GNU parallel, GNU make's jobserver, Bazel, Buck2, Pants, nextest, systemd slices) and `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/codex-research-test-runners-2026-10-14.md` (CTest, LLVM lit, cargo-nextest, meson test, Bazel test, Chromium's test launcher, `go test`, GNU parallel). Both recommend extending `scripts/run-all-test-suites.py` and keeping bwrap. Every test runner schedules only within one invocation of itself; none shares admission by CPU percentage and available memory across separate, unrelated runs on one machine. CTest (`--test-load`, `RESOURCE_LOCK`) and GNU parallel's `sem` come closest, but their load measure is the load average, not CPU use, and GNU parallel's `--memfree` kills and requeues running jobs. A third report on slot counts is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/codex-research-test-slots-2026-10-14.md`.

## Parts to reuse, not build

The user's direction: "make sure we pull anything we need out of these open source projects, no point reinventing good parts". The pull request uses these, and writes code only to join them:

- bubblewrap (already used) for the private `/tmp`, the tmux directory and the home overlay (`--overlay-src`, `--tmp-overlay`, available in bubblewrap 0.11.1 on ned-box).
- `systemd-run --user --scope` with CPU and memory accounting (systemd 259 on ned-box) to put each suite in its own cgroup, whose `cpu.stat` and `memory.peak` give its CPU seconds and peak memory, counting every process it starts.
- psutil (7.1.0 is installed on ned-box; pinned in `nc-systems/general-tools/python-libraries-pinned-requirements.txt`) for machine CPU use and available memory, rather than parsing `/proc`.
- `flock` on a directory of slot files for the admission ceiling and on one file for the exception suites' lock: the kernel releases the flock of a crashed run, which frees its slot; the slot file itself stays on disk.
- `nice` for low priority.
- The JUnit XML format for the per-test-case records, so that existing tools can read them, beside the runner's own records.
- coverage.py with its per-test contexts for the later coverage mapping.
- From the research: CTest's `RESOURCE_LOCK` model for the exception lock, and lit's and CTest's practice of keeping a failed attempt's output when a test is retried.

## Outcome

Built by pull request [Each test suite on ned-box runs in its own test sandbox, and suites start by free CPU and memory instead of waiting for a machine-wide lock](https://github.com/nedschorus/nedschorus/pull/1427), merged as 3fff6093 on 2026-10-15. The user chose the name "test sandbox" for what this GHI-MD calls the throwaway test environment; its entry in `docs/nedschorus-wiki/nedschorus-sdlc-terms.md` is still to be written and brought to the user. The pull request's description lists every escape the pre-push review showed and the escape-test case that now fails on each.

Where the build differs from the points above:

- **Home directory (point 5):** an empty tmpfs, not an overlay of the real home. Only the paths in `TEST_SANDBOX_HOME_PATHS_SHOWN_READ_ONLY` in `scripts/run-all-test-suites.py` are bound into it, read-only, each with its reason, so no credential file is there to cover. The escape test checks the home canary and every credential file against this empty home. The change came from the first review, which found that a list of covered credential files misses whatever it does not name, such as `~/.local/share/keyrings`. The user accepted the empty home in place of point 5's overlay on 2026-10-15 (UTC), item 1 of the approval-walk whose minutes are `docs/walk/reboot-test-open-decisions-2026-10-15-minutes.md` in agent-seat reboot-test's checkout.
- **Checkout under test (point 5):** a copy-on-write overlay, as corrected above. The repository's git directory is read-only, except for the suites in `SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY`, which get an overlay of it.
- **More than point 5 named:** every listening Unix socket on the machine, every directory this account can write (such as `/var/tmp`), and `/mnt`, `/media` and `/var/snap` are hidden. The network, System V IPC and process IDs are private. The variables that name a socket outside or carry a credential are removed. Before these, a suite could reach `/run/docker.sock`, the system bus and the backup drive's copies of the home directory.
- **Admission (point 3):** built as decided, with the 64-suite ceiling held by an `flock` on one of 64 slot files. A failed machine reading, or a record of suite starts that cannot be read, stops the run with exit 2 rather than letting admission decide on old or missing readings.
- **Records (point 4):** per-test-case times, per-suite CPU seconds, peak memory and admission wait, the per-second machine readings, JUnit XML and a history of failing test cases with commit and branch are built. Not built, and not scheduled: whether a failure was a caught defect or a flaky failure (that needs passes recorded across runs), keeping a failed attempt's output (the runner has no retry), and the pull request number in the history (it records the branch); each needs its own decision before it is built. A run nested inside a test sandbox has no cgroup scope, so its suites' CPU and memory figures are missing, and its report says so.
- **The machine lock:** still taken where suites do not run in test sandboxes: on the Mac, on Linux without bwrap, and in a run nested inside a sandbox.
- **Names:** the existing "signal sandbox" names (`SIGNAL_SANDBOX_*`, `SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX`, `scripts/run-suite-in-signal-sandbox.py`) are unchanged; a follow-up pull request by reboot-test renames them to the test-sandbox wording.

Not yet done, each its own later work, as the next action said: the script that summarizes agent time from the JSONL transcripts, the mapping from test cases to the code they cover, and merge-lane-2's measurement one week after the merge.

## Next action

Points 1 to 6 are built. What remains: merge-lane-2 measures the admission waits and the suite durations one week after the merge and records them in this GHI-MD; the script that summarizes agent time from the JSONL transcripts and the mapping from test cases to the code they cover are each a pull request of their own, not yet started.

## Done when

- A permanent escape test runs inside a test environment and fails to do each of these: write, delete, rename or change the permissions of a file in the real home directory, checked from outside afterwards; read any credential file; reach the real tmux server or any real agent-seat's tmux socket; signal a process outside the environment; write anywhere outside the home overlay, the private `/tmp` and the checkout under test. The same test shows that a write inside the checkout under test, like a write anywhere else in the home directory, is gone after the suite.
- Each protection, removed in turn by a hand mutant, makes the escape test fail.
- A test runs the 2026-09-21 collision, two runs of `scripts/resupervise-seat-test.py` at once, and both report every case run, with no case dropped to SKIP.
- Two test runs started together both proceed without waiting for each other, and their run records show per-test-case times, per-suite CPU seconds, peak memory and admission wait, and the per-second machine readings.
- No more than 64 suites ever run at once, and no new suite starts while CPU use is at or above 50% or available memory is at or below 10 GB, shown by a test with stubbed readings.
- A test run on the Mac passes, unchanged in behaviour.
- One week after the merge, merge-lane-2 measures the lock and admission waits and the suite durations again and records them in this GHI-MD.

## Related

GHI [#1112](https://github.com/nedschorus/nedschorus/issues/1112) and GHI [#1323](https://github.com/nedschorus/nedschorus/issues/1323) are test cases that fail on a busy machine; admission under 50% CPU is meant not to make them worse, and the timing records will show it. Pull request [#1372](https://github.com/nedschorus/nedschorus/pull/1372), open on 2026-10-14, makes every push run the selective test run, so every push also waits on today's lock until this is built.
