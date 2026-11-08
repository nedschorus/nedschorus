# Migration inventory for GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224)

Measured on origin/main at commit [27a0ef30](https://github.com/nedschorus/nedschorus/commit/27a0ef30), 2026-09-29, read-only, against `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md` and the GHI-MD's rulings of 2026-09-23 to 2026-09-29. Per-file counts: `counts.txt` / `counts.json` beside this report (scratchpad; `mapping.py` is the old→new table they were computed from).

**How counted.** "Path cites" = tracked files on origin/main, other than the file itself, containing the full old path (`git grep -l -F`), unioned with citations of the moving directory (`nc-systems/cold-read`, `scripts/design-to-main`, …). "Bare" adds the basename; it is an upper bound (`pre-push`, `launch-claude-mac` also match their tests and prose). Neither catches **constructed paths** (`REPO_ROOT / "nc-systems" / "cold-read" / "…py"`, `Path(__file__).with_name(…)`), the ones a `git mv` breaks silently; those are listed separately in §2.

## 1. Candidate systems and what moves

`scripts/` holds 175 files: 59 programs, 63 tests, 53 data files. Every one is assigned below; `nc-systems/` holds 36, of which 31 move (5 handoff files stay, edited).

| system → target (name status) | programs | tests | designs / docs | prompts | embedded prompts | data / config | files |
|---|---|---|---|---|---|---|---|
| design-to-main → `nc-systems/design-to-main/` (ruled) | 6 | 8 | 1 design, 1 glossary | 12 agent-instructions (UNRULED) | 0 | 4 scenarios | 32 |
| ↳ main-gatekeeper → `…/design-to-main/main-gatekeeper/` (ruled) | 2 | 2 | 2 designs, 2 docs | 0 | 0 | 0 | 8 |
| skills root → `nc-systems/skills/` (ruled) | 0 | 0 | skills-glossary.md | 0 | 0 | 0 | 1 |
| ↳ cold-read → `nc-systems/skills/cold-read/` (ruled) | 12 | 12 | 2 designs | 4 (rename `-prompt.md`) | 1 (see note) | 4 reviewer test cases | 34 |
| ↳ sanity-check → `nc-systems/skills/sanity-check/` | 2 | 2 | 0 | 3 | 0 | 0 | 7 |
| ↳ walk-me-through → `nc-systems/skills/walk-me-through/` | 1 | 2 | 0 | 0 | 0 | 0 | 3 |
| handoff → `nc-systems/handoff/` (exists) | 13 | 14 | 3 (1 in place → `docs/`, 2 from `docs/issues/`) | 0 | 4 constants + 3 texts (judgment) | 0 | 30 |
| GitHub issues → `nc-systems/github-issues/` (name UNRULED) | 5 | 5 | 1 design | 0 | 1 | 0 | 11 |
| getting work onto main → `nc-systems/getting-work-onto-main/` (name UNRULED) | 14 | 13 | 0 | 0 | 0 | 39 captured responses | 66 |
| backup and recovery → `nc-systems/backup-and-recovery/` (name from the 2026-08-31 table in that GHI's GHI-MD, not ruled) | 4 | 4 | 0 | 0 | 0 | 1 sudoers config | 9 |
| leftovers → `nc-systems/general-tools/` (ruled) | 13 | 14 | 0 | 0 | 0 | 10 fixtures | 37 |

Total 238 files. 16 of them have an unruled placement (12 agent-instructions, 4 reviewer test cases), on top of the unruled directory names. Skills with nothing outside `SKILL.md`: handoff, ghi-write (if its tool stays with GitHub issues), pull-request-review-write.

**design-to-main.** `scripts/design-to-main/design-to-main-{git-record,run-state,scenario-runner,state-diagram-generator,state-machine,state-tables}.py` → `nc-systems/design-to-main/`; `scripts/design-to-main/tests/*` (8, incl. `design-to-main-test-fixture.py`) → `…/tests/`; `scripts/design-to-main/scenarios/*.yaml` (4) → `…/scenarios/` (or `tests/scenarios/`: unruled); `docs/design-to-main/design-to-main-state-machine-design.md` and `…-glossary.md` → `…/docs/`. `docs/agents/queue/design-to-main-*-agent-instructions.md` (11 + README): the standard's agent-instructions row says `docs/agents/queue/`, the 2026-09-07/08 proposal says an `agent-instructions/` subdirectory: UNRULED. Main-gatekeeper: `nc-systems/main-gatekeeper/main-gatekeeper.py` → `…/design-to-main/main-gatekeeper/`, test → `…/tests/`, `main-gatekeeper-design.md` and `main-gatekeeper-first-live-check-in-record.md` → `…/docs/`; my judgment adds `docs/issues/3-main-gatekeeper-build-slice-plan.md`, `docs/issues/3-dismiss-stale-reviews-experiment-design.md` (pinned) and `scripts/protection-experiment-dismiss-stale-reviews.py` (+test). `3-credential-work-measured-state-and-rulings.md` and `3-slice-6-review-evidence-not-built.md` are left in `docs/issues/`.

**cold-read.** `nc-systems/cold-read/*.py|.sh` (12) → `nc-systems/skills/cold-read/`; `tests/` (12) → `…/tests/`; `cold-read-design.md`, `cold-read-grid-cell-failure-handling-design.md` → `…/docs/`; `.claude/skills/cold-read/prompts/{defect-hunt,fast-clarify,restate,terminology}.md` → `…/cold-read/<pass>-prompt.md`; `cold-read-reviewer-test-cases/` (top-level, 4 files, "Measured data. Do not edit") → `…/tests/cold-read-reviewer-test-cases/` (UNRULED). Embedded: `FAST_CLARIFY_PROMPT_TEMPLATE` (`cold-read-fast-read.py:148`) is a verbatim copy of `prompts/fast-clarify.md`, kept in the program by a user ruling its docstring records ("THE REVIEWER'S INSTRUCTIONS LIVE IN THIS FILE (user ruling)"). Extracting it reverses that ruling.

**sanity-check.** `scripts/sanity-check-attacks.py`, `sanity-check-record-ship.py` (+2 tests); `docs/agents/sanity-checker-{cut,fresh-eyes,mechanization}-attack-prompt.md` → `nc-systems/skills/sanity-check/{cut,fresh-eyes,mechanization}-attack-prompt.md` (paths hard-coded in `ATTACK_PROMPT_FILES`, `sanity-check-attacks.py:255`). `docs/agents/sanity-checker-instructions.md` is a retired seat's brief; it stays. **walk-me-through:** `scripts/walk-files-ship.py` (+test), `scripts/walk-file-endings-match-the-skill-test.py`.

**handoff.** Moving from `scripts/`: `handoff-context-threshold-hook.py`, `handoff-extract-conversation.py`, `post-compaction-session-continues-hook.py`, `seat-transcript-worth-resuming.py` (no test of its own), `resupervise-seat.py`, `recover-crashed-seats.py`, `restart-live-seats-at-login.py`, `install-restart-live-seats-at-login-{launch-agent,systemd-unit}.py`, `launch-claude-mac`, `launch-claude-ubuntu`, `open-iterm-window-running-command`, `agent-binary-update-under-lock.py` (no test); 14 tests incl. `launch-claude-pre-trust-step-test.py`, `launch-claude-update-step-test.sh`, `supervisor-file-names-defined-once-test.py`. Designs: `nc-systems/handoff/handoff-design.md` → `…/docs/`; `docs/issues/120-recover-crashed-seats-design.md` (GHI closed) and `docs/issues/116-fleet-survives-machine-restart-design.md` (GHI open, partly built) → `…/docs/handoff-<subject>-design.md`. They stay but get edited: `handoff-supervisor.py`, `handoff-write-and-check-supervisor.py`, `handoff-census-user-record-shapes.py`, and 2 tests. Successor first-prompt text, composed with runtime insertions and pinned by equality in tests (judgment, not clearly "a model prompt"): `RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF` (:136, whose opening `recover-crashed-seats.py` matches), `BRANCH_STATE_INSTRUCTION` (:270), `OVERVIEW_REFRESH_DUE_INSTRUCTION_TEMPLATE` (:305), `ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE` (:342); also `CONTINUE_INSTRUCTION_LINES` (post-compaction hook :127) and the inline `"You are {name}…"` f-strings at `handoff-supervisor.py:2213`, `recover-crashed-seats.py:743`.

**GitHub issues.** `scripts/ghi-{info-ask,mirror-refresh,issue-write,issue-body-edit,prose-body-migration}.py` (+5 tests); `docs/issues/46-ghi-info-agent-design.md` (pinned, landed) → `…/docs/ghi-info-agent-design.md`. Embedded model prompt: `COLD_START_PROMPT_TEMPLATE` (`ghi-info-ask.py:181`) → `ghi-info-cold-start-prompt.md`. Whether `ghi-issue-write.py` (the tool the ghi-write skill runs) belongs here or in `nc-systems/skills/ghi-write/` is unruled.

**Getting work onto main.** `merge-gate.sh`, `watch-open-pull-requests.py`, `compose-pull-request-reviewer-brief.py`, `code-review-codex-cell.py`, `branch-conflict-check.py`, `git-client-side-hooks-pre-push-conflict-check.py`, `git-client-side-hooks/{pre-commit,pre-merge-commit,pre-push,prepare-commit-msg}`, `force-push-with-open-pull-request-guard-hook.py`, `checkout-freshness-catch-up.py`, `obsolete-file-edit-warning-hook.py`, `clean-worktrees.py`; 13 tests incl. `pr-reviewer-instructions-copies-test.py`; `merge-gate-test-captured-github-responses/` (39). **Backup and recovery:** `backup-health-check.py`, `find-deleted-path-across-backups.py`, `transcript-mirror-to-log-store.py` (the GHI [Backup strategy for state outside git…](https://github.com/nedschorus/nedschorus/issues/7) build), `locate-file-copies-across-machines.py` (+4 tests); `config/sudoers-mount-apfs-readonly-for-backup-recovery`.

**Hooks: the standard contradicts the dispatcher.** The page's Hook row puts every hook in `.claude/hooks/` with its test beside it; point 4 of GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) has each system own its hook behind a dispatcher. Six `scripts/*-hook.py` plus `checkout-freshness-catch-up.py` (a Stop hook and a launcher CLI) are affected. Reading A, `.claude/hooks/`: 7 programs + 7 tests move under `.claude/`, all guarded writes. It also splits the post-compaction hook from the extractor and threshold hook it loads with `with_name`. Reading B, system directories: the table above assumes this. Under either reading, every path change in `.claude/settings.json` is a guarded write.

**Departures from that GHI's 2026-08-31 table.** The statusline and both dialog watchers left "running and recycling seats" for general-tools. "Reviewing documents" split four ways: cold-read, sanity-check, `code-review-codex-cell` to getting work onto main, and the two lints to general-tools. `agent-binary-update-under-lock.py` and `open-iterm-window-running-command` were added to handoff, and `locate-file-copies-across-machines.py` and `transcript-mirror-to-log-store.py` to backup and recovery. `git-gatekeeper` no longer exists; `main-gatekeeper` nests in design-to-main by ruling.

## 2. Citation load per system

| system | moving files | path cites (distinct files) | of those, outside the system's own files | with bare names | guarded citers | constructed-path loads that break |
|---|---|---|---|---|---|---|
| design-to-main | 32 | 42 | 17 | 48 | 0 | intra-directory only (4 × `with_name("design-to-main-state-tables.py")`, scenario-runner → `tests/…fixture.py`; 2 tests read the design by path) |
| main-gatekeeper | 8 | 58 | 51 | 65 | 0 | `handoff-write-and-check-supervisor.py:622` (handoff) builds `nc-systems/main-gatekeeper/main-gatekeeper.py`; `GATEKEEPER_SOURCE_PATH` (`main-gatekeeper.py:122`) is behaviour, and its test asserts it |
| design-to-main + main-gatekeeper, one PR | 40 | 89 | — | — | 0 | as above |
| skills root | 1 | 3 | 3 | 3 | 0 | none |
| cold-read | 34 | 72 | 44 | 88 | 3 (cold-read, walk-me-through SKILL.md; skills-glossary) | **hub**: `cold-read-cell-common.py` ← `code-review-codex-cell.py`, `sanity-check-attacks.py`; `cold-read-record-ship.py` ← `sanity-check-record-ship.py`, `seat-shared-file-ship.py`, `walk-files-ship.py`; `PROMPTS_DIR` + `f"{cell}.md"` (`cell-common.py:121,567`); `REPO_ROOT = parent.parent.parent` in 6 programs goes one level deeper |
| sanity-check | 7 | 20 | 13 | 20 | 1 | loads cold-read hub (2) |
| walk-me-through | 3 | 9 | 7 | 9 | 1 (its SKILL.md) | loads cold-read hub (1); nothing loads it |
| handoff | 30 | 78 | 59 | 113 | 1 (`settings.json`) | supervisor `EXTRACTOR_PATH`, `SCRIPTS_DIRECTORY` loads of worth-resuming / agent-binary lock; census → extractor; post-compaction → extractor + threshold hook; `ghi-info-ask.py` → threshold hook; recover → resupervise, worth-resuming, iterm opener, `LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT`; restart-at-login → recover, `launch-claude-ubuntu`; installers → `checkout/"scripts"` |
| GitHub issues | 11 | 44 | 35 | 48 | 3 (ghi-write SKILL.md; `ghi-issue-write-redirect.py` + test) | ask → mirror-refresh; migration → issue-write; ask loads `watch-agent-dialogs.py` and the threshold hook |
| getting work onto main | 66 | 54 | 36 | 70 | 2 (`settings.json`; `session-location-write-guard-test.py`) | supervisor `CLEAN_WORKTREES_PATH`; both launchers → clean-worktrees, checkout-freshness; obsolete-file hook → checkout-freshness; `pre-push` → `../git-client-side-hooks-pre-push-conflict-check.py` → branch-conflict-check; force-push guard → synthetic-keystroke guard |
| backup and recovery | 9 | 15 | 9 | 18 | 1 (`CLAUDE.md`) | statusline → `backup-health-check.py`; locate-file-copies → find-deleted (sibling) |
| general-tools | 37 | 49 | 36 | 62 | 2 (`settings.json`; `ghi-issue-write-redirect.py`) | supervisor → `stale-code-citation-check.py` → `md-drift-lint.py`; dangling-path check → md-drift-lint; `ghi-issue-write-redirect.py:114` → `scripts/synthetic-keystroke-guard-hook.py` |

The heaviest single files by path cites are `main-gatekeeper-design.md` 42, `ghi-info-ask.py` 27, `launch-claude-mac` 26, `launch-claude-ubuntu` 25, `cold-read-grid.py` 24, `handoff-design.md` 22, `main-gatekeeper.py` 21, `design-to-main-state-machine-design.md` 21, `recover-crashed-seats.py` 20, and `cold-read-cell-common.py` 20. **GHI-MDs among the citers.** `docs/issues/` files among each system's outside citers: main-gatekeeper 26, handoff 25, GitHub issues 19, getting work onto main 15, general-tools 14, cold-read 9, design-to-main 6, backup and recovery 6, sanity-check 4, walk-me-through 1. A GHI-MD is its issue's substance, and the ghi-write skill triggers on changing what an issue says. Whether repointing a path in a GHI-MD is a plain edit inside the move's commit or a ghi-write edit is not settled here. That choice decides whether "repoint every citation in the same commit" is one commit or dozens of tool runs.

Of the 55 loose tests in `scripts/`, 44 find their program with `with_name`/`dirname`, so moving a test into `tests/` edits its loader. Test discovery survives the moves: `run-all-test-suites.py` runs every `*-test.py` git lists, wherever it sits. It already skips `launch-claude-update-step-test.sh` today; the moves do not cause that.

## 3. Hooks and wiring

**In git, guarded by `.claude/hooks/instruction-file-guard.py`,** which protects all of `.claude/` plus `CLAUDE.md` and `CLAUDE.local.md`:
- `.claude/settings.json` runs 8 `scripts/` programs. `session-statusline-command.py` (general) is the statusLine. `post-compaction-session-continues-hook.py` is SessionStart, and `handoff-context-threshold-hook.py` and `checkout-freshness-catch-up.py` are Stop. `synthetic-keystroke-guard-hook.py` and `force-push-with-open-pull-request-guard-hook.py` are PreToolUse. `obsolete-file-edit-warning-hook.py` and `file-name-collision-warning-hook.py` are PostToolUse. That makes 3 edits for getting work onto main, 2 for handoff and 3 for general-tools.
- `.claude/hooks/ghi-issue-write-redirect.py` loads `scripts/synthetic-keystroke-guard-hook.py` by constructed path and cites `scripts/ghi-issue-write.py` and `scripts/ghi-info-ask.py`. Its test cites `ghi-issue-write.py`.
- SKILL.md citers: cold-read (fast-read, grid, record-ship, the prompt `terminology.md`); sanity-check (attacks, record-ship, the cut prompt); walk-me-through (`walk-files-ship.py`, `cold-read-fast-read.py`); ghi-write (`ghi-issue-write.py`, `ghi-info-ask.py`, `docs/issues/46-ghi-info-agent-design.md`, the design of GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)). `.claude/skills/skills-glossary.md` cites fast-read and grid.
- `CLAUDE.md` cites `scripts/locate-file-copies-across-machines.py` and `scripts/pr-reviewer-instructions-copies-test.py` (whose copy check is against CLAUDE.md). `AGENTS.md` (unguarded) cites `scripts/code-review-codex-cell.py`.
- `skills-glossary.md` leaving `.claude/` drops it out of the guard. The extended guard covers only the `-prompt.md` and `-instructions.md` endings.

**Outside git (per machine, not repointed by any commit):**
- The Mac LaunchAgent `~/Library/LaunchAgents/com.nedschorus.restart-live-seats-at-login.plist` and the ned-box user unit `~/.config/systemd/user/restart-live-seats-at-login.service` both name `…/Projects/nedschorus/scripts/restart-live-seats-at-login.py`. The fix is to re-run both installers, which themselves hard-code `checkout / "scripts"` (`install-…-launch-agent.py:76,100`; `…-systemd-unit.py:88,129`).
- Both crontabs run `…/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py` at :17 hourly. The paths are also quoted in its docstring (:53-54).
- `core.hooksPath` is set in both reference clones' `.git/config` (shared by every worktree) to the absolute `…/Projects/nedschorus/scripts/git-client-side-hooks`. If that directory moves, git runs no hooks, silently: the identity pre-commit check, the session-trailer stamp and the pre-push conflict check all stop.
- Cross-machine hard paths:
  - `launch-claude-ubuntu:260,325,387,393` (supervisor, agent-binary lock, clean-worktrees, checkout-freshness);
  - `resupervise-seat.py:278` `BOX_SCRIPT_PATH`;
  - `watch-agent-dialog-alerts.py:164` (ssh to `~/Projects/nedschorus/scripts/watch-agent-dialogs.py`);
  - `ghi-info-ask.py:~750` runs `python3 scripts/ghi-info-ask.py` inside ned-box's `~/agents/ghi-info` checkout.
  
  Each breaks while the two machines' checkouts disagree.
- `compose-pull-request-reviewer-brief.py:62` hard-codes `/Users/el/Projects/nedschorus/docs/agents/pr-reviewer-instructions.md`. That file does not move.
- The sudoers file installed on the Mac (`/etc/sudoers.d/nedschorus-mount-apfs-readonly`) names only `/sbin/mount_apfs`, not a script, so moving the config does not break it.
- Standing instructions in live handoff text name `scripts/merge-gate.sh`, `scripts/watch-open-pull-requests.py`, `scripts/md-drift-lint.py` and `scripts/search-user-messages-in-transcripts.py`. merge-lane-2's current first prompt on ned-box, seen via `ps`, is one example.

**Running now:**
- Seven handoff-supervisors are running: 6 on the Mac (cold-read-research, fleet-restart-at-login, MD-skills, merge-lane, merge-lane-backlog, reboot-test) and 1 on ned-box (merge-lane-2). All run from `~/Projects/nedschorus/nc-systems/handoff/handoff-supervisor.py`.
- Each resolved `EXTRACTOR_PATH` and `CLEAN_WORKTREES_PATH` to `scripts/` when it started. A handoff replaces the session, not the supervisor.
- After a reference clone fast-forwards past the move, which `launch-claude-mac:336` and `launch-claude-ubuntu:393` do at every launch, an unrestarted supervisor's next handoff fails in one of two ways:
  - The extractor is missing: `handoff-supervisor.py:2147-2153` prints "extraction failed; not relaunching" and the seat goes dark.
  - The cleaner is missing: its result is reported and the handoff goes on (`:1640-1650`).
- Also running: `watch-agent-dialog-alerts.py` ×2 on the Mac with a ned-box `watch-agent-dialogs.py` child, and `watch-open-pull-requests.py` on ned-box by relative path.

## 4. Collision risk

- `gh pr list --state open`: **0 open pull requests** at 2026-09-29 ~23:45Z. Every remote-tracking branch is merged except two stale fetch refs, `pr/154` and `pr156`, from August (no `pr` remote exists).
- Churn is the proxy for collision risk. Non-merge commits touching each system's old paths, since 09-22 / since 09-15:

  | system | since 09-22 | since 09-15 |
  |---|---|---|
  | handoff | 25 | 86 |
  | general-tools | 25 | 70 |
  | cold-read | 24 | 27 |
  | getting work onto main | 19 | 44 |
  | GitHub issues | 12 | 34 |
  | backup and recovery | 12 | 12 |
  | walk-me-through | 7 | 15 |
  | sanity-check | 6 | 17 |
  | design-to-main | 3 | 19 |
  | main-gatekeeper | 2 | 14 |
  | skills root | 1 | 2 |

## 5. Leftovers → `nc-systems/general-tools/`

Three clusters that no ruled system owns. The first two could become systems if ruled, since a system "earns its directory".
- **Citation and drift checks:** `md-drift-lint.py`, `dangling-path-citation-check.py`, `stale-code-citation-check.py`, `file-name-collision-warning-hook.py` (hook), `unvalidated-negative-result-check.py` + `unvalidated-negative-result-check-fixtures/` (10). The docstring of `md-drift-lint.py` calls it "the lint half of the sanity-check", but three general programs load it.
- **Seat oversight:** `watch-agent-dialogs.py`, `watch-agent-dialog-alerts.py`, `session-statusline-command.py`, `synthetic-keystroke-guard-hook.py` (hook), `seat-task-list-read.py`, `search-user-messages-in-transcripts.py` (no test). The 2026-08-31 table in GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) put the statusline and dialog watcher with handoff, and `recover-crashed-seats.py` loads `watch-agent-dialogs.py`.
- **Other:** `seat-shared-file-ship.py`, `run-all-test-suites.py`, `nedschorus-glossary-alphabetical-order-test.py`, `system-glossaries-listed-on-the-project-glossary-test.py`. Each has a test except the last two, which are tests themselves.

**Designs in `docs/issues/` whose code has landed:**
- No design named `-design.md` is left without a system; the four with landed code are mapped above: `46-ghi-info-agent-design.md`, `3-dismiss-stale-reviews-experiment-design.md`, `116-fleet-survives-machine-restart-design.md`, `120-recover-crashed-seats-design.md`.
- GHI-MDs of **closed** issues whose fix landed, if they count as designs:
  - [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324) and [The merge gate refuses a merge when the merge account's own review carries inline comments stamped a second later](https://github.com/nedschorus/nedschorus/issues/729): getting work onto main.
  - [The handoff-supervisor resumes a session that died without a handoff…](https://github.com/nedschorus/nedschorus/issues/613) and [recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout…](https://github.com/nedschorus/nedschorus/issues/659): handoff.
  - [The Mac's transcript mirror reports "mirrored" every hour…](https://github.com/nedschorus/nedschorus/issues/735): backup and recovery.
- Open GHIs whose code partly landed in general-tools: [Reference-integrity checker…](https://github.com/nedschorus/nedschorus/issues/42), [Cite files by name, not by path](https://github.com/nedschorus/nedschorus/issues/610), [Test suites write into the ambient repository…](https://github.com/nedschorus/nedschorus/issues/639), and [Console text-insertion + stuck/waiting-state detection…](https://github.com/nedschorus/nedschorus/issues/27). The standard's "when its code lands" does not say what happens for a partial landing.

## 6. Ordering considerations (facts, not a ruling)

- **Step 0 gates the prompts:** extend `instruction-file-guard.py` to `nc-systems/skills/` (the `-prompt.md` and `-instructions.md` endings). This is a `.claude/hooks/` edit that needs the approval marker. It blocks cold-read's 4 prompts and sanity-check's 3. It does not block walk-me-through, design-to-main, handoff or the other systems.
- **Self-contained:**
  - walk-me-through: 3 files, 9 citers, 1 guarded (its SKILL.md). It loads cold-read's hub, and nothing loads it.
  - The skills root: 1 file, 3 citers.
  - design-to-main + main-gatekeeper: no settings.json, no live process, and no other system loads its code. One cross-system edit (`handoff-write-and-check-supervisor.py:622`, whose failure is non-fatal: "audit-failed"). It has the largest prose load (89 citing files), the glossary move touches the project glossary and `system-glossaries-listed-on-the-project-glossary-test.py`, and the 12 agent-instructions are unruled.
- **Cold-read is a hub,** so its PR must edit files in three other systems: sanity-check ×2, walk-me-through, general-tools (`seat-shared-file-ship`), and getting work onto main (`code-review-codex-cell`). Moving walk-me-through and sanity-check first means their loaders are edited twice. It also carries the depth change (`parent.parent.parent` → one more level) and the `PROMPTS_DIR` / `f"{cell}-prompt.md"` change. The pass tokens in record names come from `--cell`, not from the file name, so record names are unaffected.
- **Live-critical, needing a restart or a fallback:**
  - handoff: the extractor, the settings.json hooks, the LaunchAgent and systemd unit, the cross-machine launcher.
  - getting work onto main: `clean-worktrees.py` held by 7 supervisors; `core.hooksPath` on 2 clones; the Stop hook; merge-lane-2's standing text.
  - backup and recovery: 2 crontabs, `CLAUDE.md`. The status line's load of `backup-health-check.py` is wrapped in a try/except (`session-statusline-command.py:292-305`: missing file, empty segment). If backup moves before the status line is repointed, the line does not break, but its backup warning disappears silently.
  
  The handoff overview (`docs/nedschorus-wiki/nedschorus-handoff-system-overview.md`, "the extractor … wait[s] until no live handoff-supervisor runs from `scripts/`") has that precondition met today: all 7 run from `nc-systems/handoff/`. The next blocker is the `EXTRACTOR_PATH` resolved at import.
- **Handoff overview side effect:** `overview_refresh_due_lines` counts non-`.md` commits under `nc-systems/<system>/` (top-level directories only; template `docs/nedschorus-wiki/nedschorus-{system}-system-overview.md`, `handoff-supervisor.py:284`). Moving 13 programs in makes the line fire at every seat's next reincarnation unless the same PR re-pins the overview, which is pinned at commit [f3d0abd](https://github.com/nedschorus/nedschorus/commit/f3d0abd) now. Nested systems (`skills/cold-read`, `design-to-main/main-gatekeeper`) are never checked.
- **Dependencies between systems** (loader → loaded):
  - handoff → general-tools (stale-code-citation-check, watch-agent-dialogs) and → getting work onto main (clean-worktrees, checkout-freshness);
  - GitHub issues → handoff (threshold hook) and → general-tools (watch-agent-dialogs);
  - getting work onto main → cold-read and → general-tools (synthetic-keystroke guard);
  - sanity-check, walk-me-through and general-tools → cold-read;
  - general-tools → backup and recovery (statusline);
  - `.claude/hooks/ghi-issue-write-redirect.py` → general-tools.
  
  Whichever of each pair moves second edits the first's constructed path. No program loads anything under design-to-main except handoff's audit call.

**Open questions for the user:**
- the hook row versus the dispatcher (§1);
- the target of the 12 design-to-main agent-instructions;
- where `cold-read-reviewer-test-cases/` goes;
- whether `skills-glossary.md` moves out of the guard;
- the names `github-issues`, `getting-work-onto-main` and `backup-and-recovery`;
- `ghi-issue-write.py` with GitHub issues or with `skills/ghi-write`;
- which `docs/issues/3-*` files follow main-gatekeeper;
- whether a partly built design (`docs/issues/116-fleet-survives-machine-restart-design.md`) moves;
- whether closed-issue GHI-MDs count as designs;
- whether `FAST_CLARIFY_PROMPT_TEMPLATE` is extracted, against its ruling;
- design-to-main's `scenarios/` placement.
