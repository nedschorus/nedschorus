---
issue: "[Test suites write into the ambient repository when GIT_DIR is set: git init's result is unchecked and the suite runner passes no environment](https://github.com/nedschorus/nedschorus/issues/639)"
---

# Test suites write into the ambient repository when GIT_DIR is set: git init's result is unchecked and the suite runner passes no environment

## Outcome

All three parts of this issue are built, and an ambient `GIT_DIR`, or any of the five other variables that point git at another repository, no longer reaches a scratch repository a suite builds:

1. **Suites the runner launches**: PR [The suite runner strips the git-redirecting environment variables](https://github.com/nedschorus/nedschorus/pull/644), merged 2026-09-22 as `2796d953`. `scripts/run-all-test-suites.py` launches each suite with the six variables removed.
2. **The runner's own git calls**: PR [The test runner's own git calls ignore an ambient GIT_DIR](https://github.com/nedschorus/nedschorus/pull/758), merged 2026-09-28 as `ba443081`. The runner's `rev-parse`, `ls-files` and `status` run with the same environment, so the suite list comes from the checkout and `status` no longer rewrites another repository's index.
3. **A suite run directly**, how the 2026-09-22 damage happened: PR [A test suite run directly takes the git-redirecting variables out of its own process before it builds a scratch repository](https://github.com/nedschorus/nedschorus/pull/921), merged 2026-10-02 as `4de59096`. Every suite or fixture that runs `git init` first calls `remove_git_redirecting_environment_variables_from_this_process()` in `scripts/git-redirecting-environment-removal-test-fixture.py`, which reads the runner's list, so both paths remove the same six variables. Measured 2026-10-01, 20 suites wrote into the repository `GIT_DIR` named, and all 20 are covered, `.claude/hooks/session-location-write-guard-test.py` among them on the user's approval. The other suites that build a scratch repository already kept git out of the named one; the check suite lists each, with how it does so. `scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py` fails when a suite runs `git init` without the call, and runs real suites with each variable naming a throwaway repository to show that repository is left unchanged.

The "Next action" section's item 2 proposed a scratch repository that checks, after `git init`, that it exists, and the 2026-09-22 notes below call that check the durable answer. Part 3 above removes the variables instead, and replaces that check: by the time such a check fails, `git init` has already run against the named repository, and `git init` alone can write the config every worktree of a clone shares.

Not done, as the next action says: the authorship of commits already on main is not repaired.

## Reproduction

Run against `origin/main` at `b9d8b4e9e4ce8af26269dc03d1df325fe16051bb`, on ned-box, git 2.53.0, Python 3.14.4. The suite used is one already on main; no pull request under review is involved.

Build a throwaway victim repository standing in for a seat's live checkout:

    V=/tmp/ghi-victim-repo; rm -rf $V; mkdir -p $V; cd $V
    git init -q -b main
    git config user.name "the real seat"
    git config user.email "real-seat@nedschorus.invalid"
    git config user.useConfigOnly true
    printf 'work\n' > real-work.txt
    git add -A && git commit -qm "the seat's real commit"

State before: HEAD `eb7f194`, 1 tracked file, 1 commit, identity `the real seat <real-seat@nedschorus.invalid>`.

Now run a suite from a detached worktree at that main, with `GIT_DIR` naming the victim:

    git worktree add --detach <path> b9d8b4e9e4ce8af26269dc03d1df325fe16051bb
    cd <path>
    GIT_DIR=/tmp/ghi-victim-repo/.git python3 -B scripts/checkout-freshness-catch-up-test.py

The suite exits 1 with `FileNotFoundError: [Errno 2] No such file or directory: '/tmp/tmp1kujkyc3/reference-clone'` — a crash about its own scratch path, saying nothing about the repository it just wrote to.

State after, in the victim:

| | before | after |
|---|---|---|
| tracked files | 1 | 2 |
| commits on `main` | 1 | 2 |
| identity | `the real seat <real-seat@nedschorus.invalid>` | `freshness test <test@example.invalid>` |

    3090297 freshness test <test@example.invalid> first commit
    eb7f194 the real seat <real-seat@nedschorus.invalid> the seat's real commit

A commit authored by the test landed on the victim's real branch, and the victim's committing identity was replaced.

## Why it happens

A suite that needs a git repository builds one with `git init` in a scratch directory and never checks that it worked — the pattern checks `commit`'s return code, not `init`'s. When `GIT_DIR` is set in the environment, `git -C <scratch> init` re-initialises the repository `GIT_DIR` names and exits 0. No repository is created at `<scratch>`, so every later `git -C <scratch> ...` call — `config user.name`, `config user.email`, `add -A`, `commit`, `worktree add -b` — resolves to the ambient repository instead. The suite keeps printing PASS lines, because each command succeeds; it simply succeeds somewhere else.

`scripts/run-all-test-suites.py:234` launches every suite with `subprocess.run([interpreter, "-u", suite], cwd=str(top), ...)` and no `env=`, so an ambient `GIT_DIR` reaches all of them.

21 suites on main run `git init`. Three are confirmed to leak under this condition: `scripts/checkout-freshness-catch-up-test.py` (reproduced above), `.claude/hooks/session-location-write-guard-test.py`, and `scripts/clean-worktrees-test.py` — the last the worst measured, leaving 10 stray branches and the identity overwritten to `clean-worktrees test`. Those two were measured by the independent reviewer of PR [The skills glossary, and the project glossary's list of system glossaries](https://github.com/nedschorus/nedschorus/pull/633) against its own throwaway victims, not by this seat.

`scripts/find-deleted-path-across-backups-test.py:793` already does `env.pop("GIT_DIR", None)`. The project has met this once, in one place, and did not generalise it.

## What it cost

On 2026-09-22 at 19:09:20Z it fired on the live `merge-lane-2` seat checkout. 14 commits authored `system-glossaries-listed test <test@nedschorus.invalid>` landed on the `merge-lane-2` branch, whose tree went from 293 files to 2; `/home/nedlern/Projects/nedschorus/.git/config` — the config shared by every worktree on that machine — had its `user.name` and `user.email` overwritten; and a worktree was registered in the shared repository. All of it is repaired.

The trigger there was a reviewer deliberately probing `GIT_DIR` behaviour, so this is not a thing that happens unprompted: with `GIT_DIR` unset, normal operation is clean, and `run-all-test-suites.py` sets no such variable itself. What the incident establishes is the blast radius, not the frequency.

The identity overwrite is the part that outlives the run. `README.md` § "Working in a fresh clone" pins a local `user.name`/`user.email` precisely so commits are not authored as the user; a suite that overwrites those leaves every later commit in that checkout misattributed, and nothing reports it. Authors on `origin/main` since 2026-09-15: 294 commits by `identity-probe <identity-probe@nedschorus.invalid>` and 222 by `Ned Lerner <nedlerner@yahoo.com>`, the second being exactly the outcome the pin exists to prevent. Those figures are what the authorship record looks like with the pin unreliable; this issue does not claim each one came from this mechanism.

## Next action

Two changes, and the first is the one that matters:

1. **Strip `GIT_DIR` and `GIT_WORK_TREE` from the environment each suite is launched with**, at `scripts/run-all-test-suites.py:234`. One place, covers all 21 suites, and needs nothing of their authors.
2. **Make a scratch repository assert itself.** After `git init`, check that `<scratch>/.git` is now a directory and fail loudly if not. This belongs in a shared helper rather than 21 copies; whether such a helper is worth building, or whether (1) alone is enough, is the open design question.

Not proposed: repairing the authorship of commits already on main. That needs a history rewrite, which this project should not do.

## Search receipt

`scripts/ghi-info-ask.py` asked 2026-09-22 with `--include-closed`, for existing coverage of suites writing into the real repository, `git init` success unchecked, `GIT_DIR`, `run-all-test-suites.py` environment, and tests overwriting `user.name`/`user.email`. Answer: no issue, open or closed, covers any of it; the only `user.name`/`user.email` hit anywhere is GHI [main-gatekeeper — the single check-in gate](https://github.com/nedschorus/nedschorus/issues/3)'s own gatekeeper build facts, which is a different matter.


## Added 2026-09-22T~20:2xZ, found while building the part-1 fix

Two limits the runner fix does **not** reach, both measured by the agent that wrote PR [The suite runner strips the git-redirecting environment variables](https://github.com/nedschorus/nedschorus/pull/644) and recorded here so they are not mistaken for covered ground once that lands.

**1. A suite run directly is not protected.** The runner fix passes a cleaned environment to the suites it launches. It does nothing for a suite a person or an agent runs by hand — which is how the 2026-09-22 damage actually happened. That is what "Next action" item 2 above is for, and it remains the durable answer.

**2. The runner's own git calls are not protected either.** Measured 2026-09-22: with `GIT_DIR` set, `git -C <top> ls-files` lists the OTHER repository's files and exits 0, while `rev-parse --show-toplevel` still answers `<top>`. So the runner can compose its list of suites from the wrong repository and report a green run over a set of files that is not the checkout's. This was deliberately left out of PR 644 to keep that change to the one thing item 1 asked for. It is not covered by item 2 either, since it is the runner rather than a suite, so it needs its own decision.

**Which variables the measurement settled**, so nobody re-derives it: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_COMMON_DIR` and `GIT_ALTERNATE_OBJECT_DIRECTORIES` each reach another repository and are stripped. `GIT_NAMESPACE` is contained — it renames refs inside one repository and does not reach another. `GIT_CEILING_DIRECTORIES` is deliberately **kept**: it bounds the upward walk that discovers a repository, so removing it widens rather than narrows where git looks.


## Item 1 is LANDED, 2026-09-22 — [PR 644, "The suite runner strips the git-redirecting environment variables"](https://github.com/nedschorus/nedschorus/pull/644)

Merged pinned to head `873662231d590ad9039d42be8d277f5d801c61ba`; main `2796d953`. `scripts/run-all-test-suites.py` now passes each suite an environment with the six redirecting variables removed, so an ambient `GIT_DIR` no longer reaches the 22 suites that build a scratch repository.

Approved by `mac-claude` (review 5283549058) after re-deriving all eight variable rows independently against throwaway repositories, and after confirming through the fixed runner — not merely directly — that the two suites which deliberately set `GIT_DIR` on their own children still pass.

**A correction to this issue's own numbers.** The body above says "21 suites on main run `git init`". Measured at main on 2026-09-22: **19 under `scripts/`, plus three outside it** — `.claude/hooks/session-location-write-guard-test.py`, `nc-systems/handoff/tests/handoff-supervisor-test.py`, `nc-systems/main-gatekeeper/tests/main-gatekeeper-test.py` — so **22**. The figure was right when written and rises whenever a suite lands, which is worth knowing before anyone treats a counted measurement here as durable.

**Item 2 is sharper than this issue first stated it, and the difference matters for whoever scopes it.** The body above says the runner's own git calls mean "the suite list itself can be wrong". Measured by PR 644's reviewer: `git status --porcelain` in `commit_and_state` does not merely *read* a repository that `GIT_DIR` redirects it to — it takes `.git/index.lock` there and **rewrites that repository's index**, with the victim's index mtime moving across the call. So the uncovered half is a write, not a read.

**Still open, unchanged:** a suite run by hand rather than through the runner is not protected by item 1, and that is how the 2026-09-22 damage actually happened. Item 2 — a scratch repository that asserts itself after `git init` — remains the durable answer and remains unbuilt. [PR 648, "The cold-read suites' scratch repository is built in one place"](https://github.com/nedschorus/nedschorus/pull/648), open at the time of writing, consolidates six copies of that builder into one shared fixture whose `git()` helper *does* raise on a non-zero return code. Whoever takes item 2 should build on that seam for those six rather than start again.
