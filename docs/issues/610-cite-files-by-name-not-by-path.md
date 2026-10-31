---
issue: "[Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610)"
---

# Cite files by name, not by path

**Status.** Decided. The user has decided every proposal and question this file put to him; § User-rulings records each decision and the walk-minutes that hold it. How an agent writes a file reference, in his words of 2026-09-28: "Bare names are best unless I want to read them in a display message to the user". So an agent writes a file in the repository by its bare name, such as `handoff-supervisor.py`, with two limits:

- A message displayed to the user carries the file's full clickable path.
- A file in the log-store keeps the `nedlern@ned-box:/home/nedlern/nedschorus-logs/<path>` form CLAUDE.md prescribes, because that file is outside the repository and that form works from either machine.

The walk-minutes record no change to the user-ruling of 2026-09-21 that code writes a path out, "Always write paths out"; § User-rulings cites it.

**Next action.** Two pieces remain, and the provisional additions at the end of this file name the agent-seats holding them. First, CLAUDE.md has no sentence on citing a file by its bare name. Second, `dangling-path-citation-check.py` still skips every word without a `/`, so it never checks a bare name; by the user's decision of 2026-09-28 in § User-rulings, it is to be taught to fail a bare file name, a word with no `/` that ends in a file extension, that no tracked file has. Already built: the collision warning of proposal 2, by PR [A second tracked file with the same name is reported the moment it is written](https://github.com/nedschorus/nedschorus/pull/641), and bare-name lookup in the reference check that `cold-read-grid.py` runs, by PR [Cold-read grid's reference check keeps a path written after a link, checks file links, and resolves a bare name only when one file has it](https://github.com/nedschorus/nedschorus/pull/1543).

## The problem

A reference from one file to another can be written in three forms.

1. **A whole path from the repository root, as one string literal.** `GATEKEEPER_SOURCE_PATH = "nc-systems/main-gatekeeper/main-gatekeeper.py"`, in `main-gatekeeper.py`. A search for the path finds it.
2. **A directory value joined to a literal basename.** `EXTRACTOR_PATH = SCRIPTS_DIRECTORY / "handoff-extract-conversation.py"`, in `handoff-supervisor.py`; or `Path(__file__).with_name("handoff-supervisor.py")`, which means "the file of that basename beside me". The basename is written out; the whole path never appears as one string, so a search for the path does not find it, and a search for the basename does.
3. **A computed basename.** `f"{agent}{SUPERVISOR_STATE_FILE_SUFFIX}"`, in `handoff-supervisor.py`, where the constant holds `"-supervisor-state.json"`. A search finds the constant and the line that joins it. No search of the source finds the concrete name of any one agent-seat's file, because that name exists only once the program runs.

Which form a line uses is visible in the line itself. What is not visible is whether a form 2 reference still resolves after a move: that depends on whether its directory value and its target moved together.

## What went wrong, and where it is recorded

On 2026-09-21, PR [The handoff system moves into nc-systems/handoff/, except what a live seat holds](https://github.com/nedschorus/nedschorus/pull/578) moved `handoff-supervisor.py` and `handoff-write-and-check-supervisor.py` from `scripts/` to `nc-systems/handoff/`. The merge-lane agent-seat tested the condition the pull request set itself — that no current reference to the old location survived — by running `git grep 'scripts/handoff-supervisor\.py'` over the merged tree. The search returned zero and was reported as a pass.

The move was not clean. The move had left two references behind, and neither contains the string that was searched for:

- `scripts/recover-crashed-seats.py` located the handoff-supervisor in two places as `Path(__file__).with_name("handoff-supervisor.py")` — form 2, the file beside it in `scripts/`. The move updated the import's path and not the command that launches an agent-seat, so on every machine but the Mac, ned-box included, recovery launched a file that was no longer there and every recovered agent-seat reported LAUNCHED BUT DID NOT COME UP.
- `supervisor-file-names-defined-once-test.py` built the list of scripts it reads by globbing `scripts/*.py` and adding the handoff-supervisor by hand. `handoff-write-and-check-supervisor.py` left `scripts/` and was not added, so every case the test asks about `handoff-write-and-check-supervisor.py` passed by reading nothing.

An independent reviewer found both, and commit [handoff move: the two references the move left behind](https://github.com/nedschorus/nedschorus/commit/0c1c8a3832df4f8864e288aaae0767c4bf8cad24) fixed them before merge. The merge-lane recorded its own blind search in [its review on that pull request](https://github.com/nedschorus/nedschorus/pull/578#pullrequestreview-5271189106), and noted that the author's own textual sweep and `scripts/dangling-path-citation-check.py` were blind in the same way.

The search was not blind to everything: a form 1 reference left behind would have matched. The search was blind to the form that actually broke.

## Measurements

All measured at commit [Merge pull request #606 from nedschorus/ghi-terms-are-named-for-what-they-act-on](https://github.com/nedschorus/nedschorus/commit/4ed4e4918122f3a9e56c811c58a6ac4137330801), main on 2026-09-21, over the files git tracks. How each number was taken is in the appendix.

**A search for the path misses a third of the programs.** Of the 62 tracked `.py` files whose names do not end `-test.py`, 21 occur as text in other tracked `.py` files only by basename, never by their path from the repository root; 39 occur both ways; 2 occur in no other `.py` file. A basename search finds every occurrence a path search finds, because a path string contains its basename, and it finds those 21 as well.

**Basenames are already unique, apart from three that are identified by their directory.** 286 tracked files have 277 distinct basenames. Three basenames repeat: `SKILL.md` (6, the name Claude Code's skill loader requires), `README.md` (4) and `.gitkeep` (2). Each is a file whose meaning comes from the directory it sits in — a skill, a description of its directory, a placeholder that keeps its directory — so its basename was never meant to identify it. No other basename repeats. No two basenames differ only in letter case, which matters on the Mac, whose filesystem ignores case. No two share a stem and differ only in extension.

**Computed basenames come from ten suffix constants.**

| Constant | Value | Defined in |
|---|---|---|
| `SUPERVISOR_STATE_FILE_SUFFIX` | `-supervisor-state.json` | `handoff-supervisor.py` |
| `SUPERVISOR_LOCK_FILE_SUFFIX` | `-supervisor.lock` | `handoff-supervisor.py` |
| `HANDOFF_FILE_SUFFIX` | `-handoff.md` | `handoff-supervisor.py` |
| `FIRED_MARKER_SUFFIX` | `-handoff-asked` | `handoff-context-threshold-hook.py` |
| `SEAT_NAME_SUFFIX` | `-tasks` | `seat-shared-file-ship.py` |
| `MINUTES_ROLE_SUFFIX` | `-minutes` | `walk-files-ship.py` |
| `WALK_DRAFT_SUFFIX` | `-draft.md` | `cold-read-fast-read.py` |
| `WALK_SUGGESTIONS_SUFFIX` | `-suggestions.md` | `cold-read-fast-read.py` |
| `SENTENCE_ID_MARKED_COPY_SUFFIX` | `-with-sentence-ids.md` | `cold-read-fast-read.py` |
| `LOCAL_SNAPSHOT_NAME_SUFFIX` | `.local` | `find-deleted-path-across-backups.py` |

`supervisor-file-names-defined-once-test.py` reads the code and fails when a production script builds any of the first three names by hand instead of through the handoff-supervisor's helpers. The other seven have no such test.

**In production code, form 2 references are mostly anchored at the repository.** A line classifier, a one-off keyword match described in the appendix, took the 588 lines in tracked `.py` files that join a directory value to a literal file name, and sorted each by whether the directory expression names a repository anchor, such as `REPO_ROOT` or `Path(__file__)`, or an anchor set when the program runs, such as a temporary directory, a home directory or an environment variable. Test files hold most of those lines, and nearly all of the lines anchored when the program runs or undetermined:

| | Repository anchor | Anchor set when the program runs | Undetermined from the line |
|---|---|---|---|
| Test files | 46 | 86 | 390 |
| Production code | 42 | 1 | 23 |

Read one by one, the 23 undetermined production lines split evenly: 11 are anchored at the repository under a name the classifier did not know, such as `REPOSITORY_ROOT` or a singular `SCRIPT_DIRECTORY`, or with the anchor on the line above; 11 join a workspace or record directory set when the program runs to a data file, such as `workspace / "request.json"`; one is unclear. So production code holds about 53 form 2 references anchored at the repository and 12 at locations set when the program runs. The classifier is a keyword match, so these counts are approximate.

## Proposed

These are separable. Proposal 3 concerns how references are written; proposals 1 and 2 change nothing about how anything is written.

1. **Verify a move by searching for the basename, not the path.** A basename search finds every form 1 and form 2 reference, at the same cost as a path search. A basename search would have found the reference left behind in `recover-crashed-seats.py`. The proposal changes no citation.

2. **Keep basenames unique among tracked files, and test it.** No rename is needed at the measured commit. A new test in the suite lists the tracked files with `git ls-files`, compares their basenames with letter case ignored, and fails naming both paths when two collide, exempting `SKILL.md`, `README.md` and `.gitkeep`. That exemption list is the one fact the test holds rather than reads from the tree; a new basename a tool requires shows up as a failure, not a silent pass. On a collision, CLAUDE.md's naming rule applies: "if the name collides or nearly collides, add words." The GHI to carry the test: GHI [Reference-integrity checker](https://github.com/nedschorus/nedschorus/issues/42), whose title says it covers what else code can check about citations.

3. **Whether to cite files by basename in prose instead of by path.** This is the only proposal that would change how anything is written, so it is the only one that bears on the user-ruling of 2026-09-21. The measurements above bear on searching, not on citing. Citing by basename has costs. A rename breaks a basename citation as surely as a path citation. A basename citation is followed by searching, not by clicking. A file whose basename repeats, such as `SKILL.md`, would still be cited by path. And the project's two path resolvers each fail on a basename, in opposite directions:
   - The reference check `cold-read-grid.py` runs before its reviewers resolves a citation only as a path from the repository root or from the reviewed document's own directory, so the reference check reports every basename citation of a file in another directory as unresolved. This document's own cold-read-full-run showed it: the reference check reported `handoff-supervisor.py` and four other basename citations as unresolved.
   - `scripts/dangling-path-citation-check.py` drops any word with no directory separator, because "a name with no separator is not a claim about where a file sits" (a user-ruling of 2026-09-17, quoted from the script's docstring at the measured commit). A basename citation is never checked at all, and nothing says so.

   Adopting proposal 3 means teaching the first resolver to look a basename up, and deciding whether the second should check basenames, which would revisit the user-ruling of 2026-09-17.

4. **Computed basenames.** No text search finds one agent-seat's concrete file, so a test that reads the code is the only instrument, and `supervisor-file-names-defined-once-test.py` is that test for three of the ten constants. Whether the other seven need one is question 4.

Out of scope: files outside the repository. A log-store file is cited in the scp form CLAUDE.md prescribes, which works from either machine; handoff files and cold-read-records live outside the tree; nothing here changes how they are cited. Also out of scope: citations of line numbers, which go stale on the next edit however the file is named. Those are the job of `scripts/stale-code-citation-check.py`, which tests that a design document's citations of line numbers still point at the code they name.

## User-rulings

Each proposal and question this file put to the user, with his decision. The walk-minutes cited are those of the approval-walk on this file, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cite-files-by-name-not-path-2026-09-21-minutes.md`, and of the approval-walk that took over its unanswered items, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-items-this-seat-holds-2026-09-24-minutes.md`.

- **Proposal 1, verify a move by searching for the basename.** Approved 2026-09-22 ("y"), item 1 of the 2026-09-21 walk-minutes. The three repeated names, `SKILL.md`, `README.md` and `.gitkeep`, are searched by path instead.
- **Proposal 2, keep basenames unique.** Approved 2026-09-22 ("y"), item 2 of the 2026-09-21 walk-minutes, revised from a suite test alone: a PostToolUse warning hook fires as soon as an agent writes a file whose name already belongs to another tracked file, and the same comparison is also kept as a test.
- **Question 1 and proposal 3, bare name or path.** Decided 2026-09-28, item 2 of the 2026-09-24 walk-minutes, in the user's words: "Bare names are best unless I want to read them in a display message to the user". The approval-walk offered this answer as its option N, stated as "the bare name (which also means teaching the reference check to read bare names)", in the walk-document `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-items-this-seat-holds-2026-09-24.md` line 43 and the 2026-09-24 walk-minutes line 30. The MD-skills agent-seat's walk-minutes, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/claude-md-file-citation-and-drift-findings-2026-09-22-minutes.md` line 126, record what that choice requires: both reference checks, `dangling-path-citation-check.py` and the cold-read grid's reference check, must resolve bare names. So the choice also settles whether `dangling-path-citation-check.py` checks bare names: it does. Those walk-minutes add that the choice reopens the user-ruling of 2026-09-17 quoted under proposal 3. The walk-minutes record no change to the user-ruling of 2026-09-21 on code, "Always write paths out", given in the fleet-restart-at-login agent-seat's agent-session, transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-fleet-restart-at-login/072306de-41a2-4217-8d77-07554a06e263.jsonl`, in answer to whether code should write a file's path out as text or assemble it.
- **Question 2, stable and working directories.** Approved 2026-09-28 ("Y"), item 3 of 22 in the 2026-09-24 walk-minutes: nothing is built now to mark which directories are stable and which are working, as the user had suggested, and this design keeps two definitions. A stable file is tracked by git at a fixed path; a working file is created while a program runs.
- **Question 3, the collision fallback.** Approved 2026-09-22 ("y"), item 3 of the 2026-09-21 walk-minutes: when two file names collide, the project's naming rule governs, and the `-N` suffix the user had suggested, adding a number to the second file's name, is not adopted.
- **Question 4, the seven other suffix constants.** Approved 2026-09-28 ("Y"), item 4 of 22 in the 2026-09-24 walk-minutes: the seven stay without a test until an agent is caught building one of those names by hand.

## Related GHIs, not duplicates

- GHI [Reference-integrity checker](https://github.com/nedschorus/nedschorus/issues/42) — the GHI that would carry the uniqueness test. Its title says it checks that "links resolve and cited revision-paths exist", meaning citations of the form `<revision>:<path>`; it does not address citation style or uniqueness.
- GHI [Rationalize the repository layout](https://github.com/nedschorus/nedschorus/issues/224) — records an agent that followed a citation to a moved file and built the wrong thing from its absence.
- GHI [Warn an agent when its reply names a document for the user without a link the user can open on his Mac](https://github.com/nedschorus/nedschorus/issues/1213) — its hook warns an agent when a reply to the user names a document without a link he can open on his Mac.
- GHI [Sort the 60 standing md-drift-lint findings](https://github.com/nedschorus/nedschorus/issues/572) — the backlog from `scripts/md-drift-lint.py`, the project's mechanical drift lint for markdown. Proposal 3 would reduce its findings of stale paths, not its findings of stale line numbers.

## Appendix: how each number was measured

At commit `4ed4e4918122f3a9e56c811c58a6ac4137330801`, over the output of `git ls-tree -r --name-only` for that commit.

- **Basenames.** Group every tracked path by its final component; count the groups and list any holding more than one path. Repeat with the basename lowercased (collisions in letter case only: 0) and with the extension stripped (stems shared by two basenames: 0).
- **Programs.** Population: tracked paths ending `.py` and not ending `-test.py`, 62. For each, count occurrences of its basename, and separately of its path from the repository root, as substrings of every other tracked `.py` file, excluding the file itself. A file's own docstring often names its own path; counting that put seven files among those found both ways that belong elsewhere, six among those found only by basename and one among those found by neither, and gave 15 instead of 21.
- **Form 2 lines.** Lines in tracked `.py` files matching `with_name("<basename>")` or `/ "<basename>.<py|md|json>"`. Repository anchor if the line names `REPO_ROOT`, `SCRIPTS_DIRECTORY`, `NC_SYSTEMS`, `Path(__file__)`, `PROJECT_DIR` or `HANDOFF_DIRECTORY`; anchor set when the program runs if the line names a temporary, home, environment, scratch, worktree, checkout or log-store value; otherwise undetermined. A test file is a path ending `-test.py` or containing `/tests/`.
- **Suffix constants.** `git grep -nE '^[A-Z_]+_SUFFIX = '` over tracked `.py` files, less one docstring line in `supervisor-file-names-defined-once-test.py` that happens to begin the same way.

## Provisional additions (not yet vetted by the user)

- MD-skills, 2026-10-14: Once this issue's bare-name resolution and basename uniqueness checks are on main, add CLAUDE.md's sentences on citing a file by its bare name; the candidate text is `docs/drafts/claude-md-file-citation-bullet-candidate.md` in the MD-skills agent-home on ned-box, to be rebuilt onto CLAUDE.md as it then stands (MD-skills task #121).
- fleet-restart-at-login, 2026-10-14: Teach the reference checks, `dangling-path-citation-check` and the cold-read grid's reference check, to resolve a bare file name, and to fail when a bare name names no file (task #103).
- fleet-restart-at-login, 2026-10-14: When both of this issue's checks are on main, the bare-name resolution above and a uniqueness check that fails on a second file with an existing name, tell the MD-skills agent-seat (task #118).
