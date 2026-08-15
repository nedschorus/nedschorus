<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

## Ubuntu fleet — open work inventory and thread map

1. This document is a snapshot made on August 13, 2026, for GitHub issue #45. Its purpose is to divide the unfinished work on the machine—the “box”—among a small number of explicitly named agents.

2. It was written because parallel sessions were accumulating faster than anyone could track them: forks were being used to save context for later, successor sessions were documenting their state when they wrote their handoffs rather than their state at the fork point, and several work threads began overlapping.

3. This is an operational snapshot rather than a permanent design. Pull-request and issue entries will become outdated as the work lands, but the thread map and paths to context files should remain useful.

## 0. State as of 2026-08-13, late evening

1. This section is intended to be the quickest way for someone to become current on the situation.

2. Two agent seats are currently running on the machine: `gatekeeper` and `sanity-checker`. Each is in its own branch and in a separate directory under `~/agents/<seat>`, and each has already performed its first action.

3. The `gatekeeper` seat has reported its result and is waiting for a decision from the user, while the `sanity-checker` seat is sorting through four findings and writing queue documents so those findings can be routed.

4. The instructions for launching those seats, including one associated pitfall, are in section 6a.

5. All twelve seat documents have gone through the `md-review` process, and the findings from each review have been applied to the document that was reviewed.

6. The reviews were severe but useful: the gatekeeper brief had 23 findings, the seat model had 28, the sanity-checker brief had 30, and the fleet brief had 26; none of the first four documents had a section that reviewers considered clean.

7. The corrections resulting from those reviews are contained in PR #58.

8. The biggest category of defect was undefined vocabulary. The briefs used the terms “pile,” “walked approval,” “instruction-class,” “slice,” and the C-number labels as though everyone already knew what they meant, even though none of those terms had been defined anywhere. The seat model now defines each of them once.

9. Two factual, rather than merely editorial, corrections are especially important: every document written that day had incorrectly been dated August 14, 2026 because UTC job timestamps were treated as local dates, and those dates have now been corrected to August 13; also, the repair command in `seat-first-prompt.md` could not work because `git worktree add` rejects a non-empty destination, while the version with `-b` removed was invalid on the branch-already-exists path that a relaunched seat would take.

10. A second review pass is still needed for documents that changed after their first review, because applying findings can create new findings. The first documents to review again are `seat-first-prompt.md`, `agent-seat-model.md`, and `gatekeeper-instructions.md`.

## 1. Open pull requests

1. PR #51, on branch `walk-and-md-review-skill-rules`, changes the walk so that selectable items are treated as proposals, and has `md-review` deliver its work incrementally under the supervision of a Monitor. Its owner stream is `choirmaster`.

2. PR #52, on branch `fast-handoff-findings-applied`, applies the sanity-check findings to the fast-handoff work and substantially removes the original design document. Its owner stream is `choirmaster`.

3. PR #53, on branch `sanity-checker-attack-split-experiment`, contains three attack prompts, the script `scripts/md-drift-lint.py`, and twelve scored evaluation cells. Its owner stream is `choirmaster`.

4. PR #55, on branch `claude/gatekeeper-audit-account-case-and-rulings-fold`, makes the audit compare account names without regard to letter case and incorporates the review rulings from issue #49 into the slice plan. It belongs to a third stream.

5. PR #57, on branch `launch-claude-machine-named-launchers`, contains machine-named launchers and their Mac counterpart, a reference to fleet paths, supervisor branch synchronization, and session-rider changes. Its owner stream is `gatekeeper-walk-fork`.

6. All five pull requests are still open and are waiting for a seat operating on the Mac side to review and merge them.

7. The five pull requests are not expected to conflict because they modify different files and are on different branches.

## 2. Decisions waiting on the user

1. The first decision is whether the `sanity-checker` should become a grid seat in the `md-review` experiment, using three kinds of attacks—cut, mechanization, and fresh-eyes—across Fable and `gpt-5.6-sol` at `xhigh`.

2. The evidence for that decision is in `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and PR #53, and it indicates that splitting the attacks performed better than the unsplit baseline.

3. Job `ea663864` is blocked because this decision has not yet been made.

4. The second decision is which activity should happen first: the grid-seat walk for the sanity-checker, or triage of the novel findings listed in the next section.

5. This ordering question was asked by job `ea663864` and has never received an answer.

6. The third decision concerns the remaining gatekeeper work, all of which requires user approval: deciding the evidence format for walked approval, implementing build slice 6—the review-evidence check—and then doing the credential work.

7. Until the user authorizes those gatekeeper steps, the gatekeeper remains inactive.

## 3. Un-triaged novel findings (from the attack-split experiment)

1. These findings appeared outside both existing ground-truth sets, have not yet been presented to the user, and each must be checked against the current code before any walk takes place. The experiment cells were based on archived snapshots rather than the current code.

2. The gatekeeper specification says that, when a test suite exists, the tests run at that point, but this behavior was never observed even though a test suite now exists; therefore, the gate currently performs no checks.

3. There is no safeguard preventing the gate itself from editing or altering the gate.

4. One proposed solution is for a writer or tool to stamp the pin automatically, preventing agents from manually entering 40-character commit SHA values.

5. There is a session state in which the session is stalled but still below the threshold that would trigger recycling, and there is no watchdog to detect or recover it.

## 4. Open issues, grouped

1. There are 24 open issues, grouped by theme so that the work can be divided among agents.

2. The fleet-and-sessions group contains issue #45 about named agents, #50 about worktree file hygiene, #34 about successors stating their Git context, #37 about equivalents of turn and steer operations, #27 about console insertion and stuck-state detection, and #40 about hardening the machine.

3. The review-and-skills group contains #24 about draining the queue, #23 about evaluating agent changes, #22 about reviewing changes, #21 about diagnosing failures, #20 about implementing with evidence, #19 about attack artifacts, #18 about writing test plans, #17 about design changes, #38 about “watch your back,” #36 about mutual oversight, and #26 about a dynamic agent-team model.

4. The GHI-and-tooling group contains #46 about `ghi-info`, #41 about the run-agent CLI, #42 about a reference-integrity checker, and #39 about memory instrumentation.

5. The doctrine-and-research group contains #44 about import-tracking doctrine, #35 about usage versus expectation, #33 about the superseded fast-handoff pickup, #32 about what NC preserves, #31 about review-system requirements, #30 about trigger-first delivery, #29 and #28 about research bundles, and #25 about check-in timing.

## 5. Thread map — where each thread’s context lives

1. Transcripts are treated as the durable record of a thread’s context.

2. A new session can be directed to any of the listed context files regardless of which agent name it is running under; the mechanism for doing that is described in section 6.

3. The thread called “gatekeeper + launchers (this stream)” has job ID `ec9045a3`. Its transcript is at `~/.claude/projects/-home-nedlern-Projects-nedschorus--claude-worktrees-gatekeeper-walk-fork-continuation/ec9045a3-6202-4cdc-9fb2-d855d62585cc.jsonl`. It is live, PR #57 is open, and its handoff is at `~/.claude/handoffs/gatekeeper-walk-fork-handoff.md`.

4. The current `choirmaster` stream has job ID `ea663864`. Its transcript is at `~/.claude/projects/-home-nedlern-agents-choirmaster/ea663864-8dd4-4734-a0e7-a0c65d5eb1de.jsonl`, and it is live but blocked on the decision described above.

5. The predecessor `choirmaster` stream has job ID `49e0a3cf`. Its transcript is at `~/.claude/projects/-home-nedlern-agents-choirmaster/49e0a3cf-4ebc-41d9-9417-3edafe0e2aa8.jsonl`, is about 3.6 MB, and is retired because its handoff has already been consumed.

6. The code-review-prompt-drafting thread has no job ID. Its transcript is at `~/.claude/projects/-home-nedlern-agents-choirmaster/29d66917-9767-47cb-a221-d4876d8014cd.jsonl`, is about 3.6 MB, and is titled “Draft code review prompt for reliability improvement.” It is unclaimed and contains substantial context, but no live session.

7. The `sanity-checker` thread has job ID `d9eda3ec`. Its transcript is represented by `~/.claude/projects/-home-nedlern-agents-choirmaster/d9eda3ec-*.jsonl`; it is retired and has a written handoff.

8. The login-session thread has job ID `3d8bf995`. Its transcript is represented by `~/.claude/projects/-home-nedlern/3d8bf995-*.jsonl`; it never had a task and is marked for deletion.

9. The tmux-seat thread has job ID `f741668d`. Its transcript is represented by `~/.claude/projects/-home-nedlern-agents-choirmaster/f741668d-*.jsonl`; it duplicates the `choirmaster` stream and should be reconciled with `ea663864`.

### Complete transcript sweep (2026-08-13)

1. All 35 transcripts larger than 30 KB were checked for their titles, not only the transcripts already known.

2. The sweep added information beyond what was in the preceding table.

3. There are two unowned threads containing substantive work.

4. Thread `29d66917` is 3.67 MB, was last written on August 13, 2026 at 20:30, and is titled “Draft code review prompt for reliability improvement.” It contains substantial drafting work in `~/agents/choirmaster`, has no live session, and is not mentioned in any handoff.

5. The natural owner of thread `29d66917` is whichever seat takes responsibility for review-and-skills work.

6. The other unowned content belongs to a separate project named `nedsmessenger`, stored under `~/.claude/projects/-home-nedlern-agent-nedsmessenger/`.

7. That project has five sessions from August 3 and 4, 2026, totaling approximately 4 MB. Their topics were reorganizing GitHub repositories and GitHub Apps, creating Samba links for Typora file access, reviewing improvements to a backup alert system, merging PR #37 and resolving branch conflicts with `main`, and testing messages.

8. The `nedsmessenger` project has not been touched for ten days.

9. The user must decide whether `nedsmessenger` is still active. It is separate from `nedschorus` work and would need its own seat if it is revived.

10. Everything else in the transcript collection has been accounted for.

11. The remaining transcripts fall into three groups, and none of those groups needs an owner: predecessor generations of the two live streams; `md-review` and experiment cells whose findings are already recorded in `md-review-records/`; and two July machine-maintenance sessions, one for a security audit and one for an upgrade.

12. The predecessor-generation transcripts are `5a7d955e`, `d9eda3ec`, `49e0a3cf`, `574972e0`, `1caf1c51`, and `ccc79ae5`, along with `b2912831`, `27862506`, and `0550ed74` from the gatekeeper worktree.

13. The `md-review` and experiment transcripts are `3766ca30`, `84a8a260`, `946596c0`, and `0f34ff59` from the August 9 grid; `832f3b95`, `9cd26c95`, `0e711797`, and `99a2f1a4` from the sanity-checker draft review; and `8d89bd09`, `83e22b1a`, `849436bf`, `9aae839c`, `cd59239a`, and `82f21e87` from the August 12 attack-split experiment.

14. The two July maintenance sessions are `bab1c2b3`, which performed a security audit, and `c75a8d63`, which performed an upgrade.

15. The preserved handoffs and dialog extracts are all under `~/.claude/handoffs/`. They include the `choirmaster` and `gatekeeper-walk-fork` handoffs and their numbered generations, plus corresponding `-dialog-` files containing the end portion of each session’s conversation.

## 6. How to give a new agent someone else’s handoff

1. The supervisor reads `~/.claude/handoffs/<agent>-handoff.md`, where `<agent>` is the name supplied to the launcher. Consequently, a newly launched agent normally sees only the handoff belonging to its own name.

2. There are two already-implemented ways to make another handoff available.

3. With `--first-prompt-file <path>`, the launcher tells the supervisor to read the specified file as the new session’s first prompt, after which the supervisor returns to its normal startup behavior.

4. This first-prompt-file mechanism is intended for supplying arbitrary context, such as another thread’s handoff, its dialog extract, or a specially written brief.

5. The second method is to copy the old handoff to the new agent name before launching it: `cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md`. The supervisor for the new name will then treat the copied file as its own handoff.

6. In both cases, a handoff written by a forked session records that session’s state at the time it wrote the handoff, not the state at which it was forked.

7. If the fork point is the relevant context, the new session should instead be directed to the `-dialog-` extract or the full transcript, and its first prompt should specify which part of the history matters.

## 6a. Seats launched 2026-08-13, and how

1. `gatekeeper` and `sanity-checker` are running on the machine, each in `~/agents/<seat>` and on its own branch, and each is reading the reviewed version of its brief.

2. Both seats were confirmed to start correctly: their branch was verified and a status line appeared, which indicates that project settings loaded and therefore that both the recycle hook and the instruction-file guard loaded as well.

3. The seats were not launched using the documented recipe because that recipe cannot work yet: it reads `docs/agents/seat-first-prompt.md` from the machine’s checkout of `main`, while that file—and all of the `md-review` corrections to the briefs—still exists only in PR #58.

4. Launching from `main` would therefore have started both seats with the pre-review documents, each of which still contained between twenty and thirty findings.

5. The workaround used, and the change that should be undone after PR #58 merges, is as follows.

6. Each seat’s worktree was created from the PR branch rather than from `main`, using `git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`. Because the launcher does not create an agent home when that location is already a checkout, this pre-created worktree prevents the launcher from trying to create it.

7. The launcher was then run with the prompt file from the seat’s own checkout: `sh scripts/launch-claude-mac <seat> --no-attach --first-prompt-file /home/nedlern/agents/<seat>/docs/agents/seat-first-prompt.md`.

8. The Mac version runs locally on the machine and is mechanically the same as the Ubuntu launcher except that it omits the SSH hop, which is why it can be used from a session on the machine itself.

9. Each seat’s branch contains the commits from PR #58, so supervisor branch synchronization will report that the branch is ahead of `main` and will make no changes.

10. After PR #58 merges, those seat branches will instead be strictly behind `main`, and ordinary fast-forward synchronization should bring them up to date.

11. No action is needed unless PR #58 changes substantially before it merges; if it does, the seats should be relaunched from the version of `main` that includes the merged PR.

12. There is a trap that must be resolved before approving the tempting cleanup action.

13. Within minutes, the `gatekeeper` seat recognized the branch lineage and proposed `git reset --hard origin/main` to make its branch clean. That reasoning is understandable from the seat’s perspective, but performing the reset now would be wrong.

14. Resetting now would replace the seat’s reviewed `docs/agents/` files with the pre-review briefs, so a later session using that seat would again read documents containing 23 findings.

15. The reset should wait until PR #58 merges; after the merge it will be unnecessary because the branch will fast-forward by itself.

16. If a seat must be cleaned before PR #58 merges, it should be relaunched from the PR branch rather than reset to `main`.

## 7. Proposed split into named agents

1. The proposal is to use three seats, selected so that no two seats modify the same files or branches.

2. The `gatekeeper` seat would handle the gatekeeper’s remaining sequence of work—evidence format, then slice 6, then credential work—as well as PR #55, PR #57, and fleet and session issues #45, #50, and #34. Its context would come from the transcript and handoff for the current stream.

3. The `reviewer` seat would handle the decision about making the sanity-checker a grid seat, triage the novel findings, work on PRs #51, #52, and #53, and handle candidate-skill issues #17 through #23. Its context would come from `ea663864` and from `29d66917` for the code-review-prompt work.

4. The `ghi` seat would handle issue #46 concerning `ghi-info` and its neighboring issues #41, #42, and #39. Its context would be the GHI design documents already in the repository.

5. Each seat would have its own agent home and therefore its own branch; that separation is what prevents the seats from colliding with one another.

6. Work can begin with only two seats if running three simultaneously is too much; the third seat can be started later.
