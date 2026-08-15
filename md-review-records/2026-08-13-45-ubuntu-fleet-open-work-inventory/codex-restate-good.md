<!-- provenance: runtime=codex model=gpt-5.6-sol effort=xhigh cell=restate tier=good target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

# Ubuntu fleet — open work inventory and thread map

1. This document records the state of unfinished work on the Ubuntu machine as of August 13, 2026, for GitHub issue #45, with the purpose of assigning that work to a small set of agents that have explicit names.
2. The document was created because multiple sessions were progressing in parallel faster than anyone was keeping track of them: forks were being retained so their conversation context could be resumed later; successor sessions described the state they had reached when writing a handoff rather than the earlier state at which they had been forked; and several lines of work had begun covering some of the same territory.
3. This is a point-in-time operational record, not a permanent system design: its lists of pull requests and issues will become outdated as those items are merged or closed, while its mapping of work threads and paths to saved context files is expected to remain useful longer.

## 0. State as of 2026-08-13, late evening

1. This section is intended to be the quickest way for someone to understand the current situation.
2. Two named agent positions are actively running on the Ubuntu machine: `gatekeeper` and `sanity-checker`; each uses a separate directory of the form `~/agents/<seat>`, each is working on its own Git branch, and each has completed at least its initial action rather than merely having been launched.
3. The `gatekeeper` agent has delivered a report and is paused until someone makes a requested decision, while the `sanity-checker` agent is classifying four findings and creating issue-queue documents that will direct those findings to the appropriate future work.
4. Section 6a explains how those two agents were started and describes one important pitfall in that launch procedure.
5. All twelve documents associated with the agent seats have gone through the repository’s process called “md-review,” and the findings from each review have been incorporated into the particular document that review examined.
6. Those reviews were severe but productive: they produced 23 findings for the gatekeeper brief, 28 for the agent-seat model, 30 for the sanity-checker brief, and 26 for the fleet brief, and the reviewers marked no section as free of findings in any of those first four reviews.
7. The resulting corrections are contained in pull request #58.
8. The most common single category of defect involved unexplained terminology: the documents treated the words *pile*, *walked approval*, *instruction-class*, and *slice*, as well as identifiers referred to as C-numbers, as already established concepts even though none had been defined anywhere.
9. The agent-seat model now provides one central definition for each of those terms.
10. Two corrections matter especially because they fixed factually incorrect instructions or metadata rather than merely unclear phrasing: every document written that day originally carried the date `2026-08-14`, because timestamps produced in UTC were mistakenly treated as local calendar dates, and those dates have now been corrected to `2026-08-13`; additionally, the repair command in `seat-first-prompt.md` was unusable because `git worktree add` will not use a nonempty destination directory, while the suggested alternative of omitting `-b` did not form a valid command for the branch-already-exists situation encountered whenever a previously created seat is launched again.
11. A second review is still required for documents modified after their first review, because applying one round of findings can itself create new defects; the second pass should begin with `seat-first-prompt.md`, `agent-seat-model.md`, and `gatekeeper-instructions.md`.

## 1. Open pull requests

1. Pull request #51 comes from branch `walk-and-md-review-skill-rules`, belongs to the `choirmaster` line of work, specifies that choice items produced during a “walk” are proposals rather than automatically accepted decisions, and changes md-review so that it can deliver results incrementally while something or someone called a Monitor oversees the process.
2. Pull request #52 comes from branch `fast-handoff-findings-applied`, belongs to the `choirmaster` line of work, incorporates findings from a sanity check of the fast-handoff work, and has removed most or all of the previous substantive content from the associated design document; “gutted” indicates extensive removal, but the sentence does not specify exactly what remains.
3. Pull request #53 comes from branch `sanity-checker-attack-split-experiment`, belongs to the `choirmaster` line of work, contains three distinct adversarial review prompts, adds `scripts/md-drift-lint.py`, and records scores for twelve experimental cells, where “cells” appears to mean individual combinations or runs in the experiment.
4. Pull request #55 comes from branch `claude/gatekeeper-audit-account-case-and-rulings-fold`, belongs to an unspecified third line of work, changes an audit so account names are compared without treating uppercase and lowercase letters as different, and incorporates decisions from the review of issue #49 into the plan for incremental units called slices.
5. Pull request #57 comes from branch `launch-claude-machine-named-launchers`, belongs to the `gatekeeper-walk-fork` line of work, and contains launchers distinguished by machine name, a corresponding Mac launcher, documentation of fleet paths, synchronization of the supervisor’s branch, and additional session-related material called “riders,” whose exact form is not defined here.
6. All five listed pull requests remain open and are waiting for an agent position operating from the Mac side to review and merge them.
7. The five pull requests are expected not to create merge conflicts because they change different files on different branches.

## 2. Decisions waiting on the user

1. The user must decide whether the sanity-checker should become a position in the md-review grid and run three adversarial review stances—cut, mechanization, and fresh-eyes—using both Fable and `gpt-5.6-sol` at the `xhigh` reasoning setting; the text does not establish whether Fable is a model, an agent, or another execution system, only that it forms the other side of this experimental grid.
2. Supporting results are recorded in `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and pull request #53, and those results say the three separated attacks performed better than the baseline in which they were combined, although the sentence does not state the scoring metric.
3. Job `ea663864` cannot proceed until the user makes that decision.
4. The user must also decide whether to perform the proposed grid-seat walk first or instead first classify and route the newly discovered findings listed in the following section; “walk” appears to name a structured review or approval process, but its mechanics are not given here.
5. Job `ea663864` asked that sequencing question and never received an answer.
6. All remaining gatekeeper work requires user authorization at its respective gates: first a decision about the required evidence format for approval obtained through a “walk,” then implementation of planned slice 6, which is the review-evidence check, and finally unspecified credential-related work.
7. Until those user-controlled steps occur, the gatekeeper mechanism remains inactive.

## 3. Un-triaged novel findings (from the attack-split experiment)

1. These findings were discovered in addition to the findings in both established ground-truth sets, have never been shown to the user for a decision, and must each be checked against the present code before any structured “walk” is conducted because the experiment examined archived copies rather than the current files.
2. The gatekeeper specification contains a requirement meaning that, once a test suite exists, its tests should run at this point in the gate; that requirement was never activated even though a suite now exists, so the gate currently executes no checks.
3. There is no protective rule preventing the gate from editing the gate itself; this most likely means that a process governed by the gate can modify the gate’s own implementation or rules, although the exact boundary of “the gate” is not stated.
4. One proposed improvement would have the writing process automatically stamp the relevant pinned revision, so agents no longer manually enter 40-character Git commit SHAs; “pin” appears to mean the exact commit revision being recorded.
5. A session can become stuck while remaining below the system’s recycle threshold, and no watchdog detects that condition; “light” appears to mean that whatever load or usage triggers recycling remains low, but the precise measured quantity is not specified.

## 4. Open issues, grouped

1. The document states that there are twenty-four open issues.
2. The open issues are grouped by subject so their work can be divided among agents or work streams.
3. The fleet-and-sessions group contains issue #45 about named agents, #50 about file hygiene in worktrees, #34 about requiring successor sessions to state their Git context, #37 about equivalents for turns and steering, #27 about inserting content into a console and detecting stuck states, and #40 about hardening the Ubuntu machine.
4. The review-and-skills group contains #24 about draining the queue, #23 about an `eval-agent-change` capability, #22 about a `review-change` capability, #21 about diagnosing failures, #20 about implementing changes with evidence, #19 about attacking an artifact, #18 about writing a test plan, #17 about designing a change, #38 titled or summarized as “watch your back,” #36 about mutual oversight, and #26 about a dynamic agent-team model; the parenthetical labels are short issue descriptions rather than full specifications.
5. The GHI-and-tooling group contains #46 about `ghi-info`, #41 about a command-line interface for running an agent, #42 about checking reference integrity, and #39 about instrumentation for memory.
6. The doctrine-and-research group contains #44 about doctrine for tracking imports, #35 about usage compared with expectation, #33 about a now-superseded fast-handoff pickup, #32 about what “NC” preserves, #31 about requirements for the review system, #30 about trigger-first delivery, #29 and #28 about research bundles, and #25 about when to check in; the document does not expand “NC” or the other terse issue labels.

## 5. Thread map — where each thread’s context lives

1. Saved transcripts, rather than active sessions alone, are treated as the persistent source of context for these lines of work.
2. A newly started session can be directed to any of the listed transcripts regardless of the agent name assigned to that session, using the mechanism explained in section 6.
3. The live `gatekeeper + launchers` thread is job `ec9045a3`; its context is stored in the specified `ec9045a3-6202-4cdc-9fb2-d855d62585cc.jsonl` file, pull request #57 is open, and a handoff is stored at `~/.claude/handoffs/gatekeeper-walk-fork-handoff.md`.
4. The current `choirmaster` thread is job `ea663864`; its context is stored in the specified `ea663864-8dd4-4734-a0e7-a0c65d5eb1de.jsonl` file, and it is live but unable to proceed until the previously described user ruling is made.
5. The predecessor to the current `choirmaster` thread was job `49e0a3cf`; its 3.6 MB transcript is stored at the given path, the session has been retired, and its handoff has already been used by its successor.
6. The code-review-prompt drafting thread has no listed job identifier; its 3.6 MB transcript is the specified `29d66917-9767-47cb-a221-d4876d8014cd.jsonl` file, whose recorded task title is “Draft code review prompt for reliability improvement,” and the thread contains substantial work but has neither an assigned owner nor a currently running session.
7. The sanity-checker thread was job `d9eda3ec`; its transcript matches the specified wildcard path, the session is retired, and it produced a handoff.
8. The login-session thread was job `3d8bf995`; its transcript matches the specified wildcard path, it was never assigned any task, and the document directs that it be deleted.
9. The tmux-seat thread was job `f741668d`; its transcript matches the specified wildcard path, it duplicates the `choirmaster` line of work, and that duplication should be reconciled using `ea663864` as the comparison or authoritative current thread.

### Complete transcript sweep (2026-08-13)

1. All 35 transcripts larger than 30 KB were inspected sufficiently to identify their task titles, rather than limiting the inspection to transcripts already known beforehand.
2. The remainder of this subsection states what that broader inspection discovered beyond the threads already listed in the table.

### Two unowned threads with real content

1. Exactly two lines of work were found that contain substantive material but have no current owner.
2. Transcript `29d66917`, which is 3.67 MB and was last written on August 13, 2026, at 20:30, records the task “Draft code review prompt for reliability improvement”; it contains substantial drafting work performed in `~/agents/choirmaster`, has no live session, and is not referenced by any handoff.
3. The most appropriate assignment for that transcript is whichever agent position takes responsibility for review-and-skills work.
4. The other discovery is a wholly separate project named `nedsmessenger`, stored under `~/.claude/projects/-home-nedlern-agent-nedsmessenger/`; it has five sessions dated August 3 and 4, 2026, totaling about 4 MB, covering reorganization of GitHub repositories and GitHub Apps, creation of Samba links so Typora can access files, review of improvements to a backup-alert system, merging pull request #37 while resolving conflicts with `main`, and a thread used for a test message.
5. No activity has touched that project for ten days as of this snapshot.
6. The user must decide whether `nedsmessenger` is still an active project; it is separate from the `nedschorus` work described elsewhere in this document and, if restarted, should receive a separate agent position of its own.

### Everything else is accounted for

1. Every transcript not identified as one of the substantive unowned threads has an understood origin and disposition.
2. The remaining transcripts belong to three categories, none of which needs a new owner: earlier generations of the two live work streams, specifically `5a7d955e`, `d9eda3ec`, `49e0a3cf`, `574972e0`, `1caf1c51`, `ccc79ae5`, and the gatekeeper worktree’s `b2912831`, `27862506`, and `0550ed74`; md-review or experiment runs whose findings have already been preserved in `md-review-records/`, specifically the four named runs from the August 9 grid, the four runs from review of the sanity-checker draft, and the six runs from the August 12 attack-split experiment; and the July machine-maintenance sessions `bab1c2b3`, which performed a security audit, and `c75a8d63`, which performed an upgrade.
3. Preserved material under `~/.claude/handoffs/` consists of the `choirmaster` and `gatekeeper-walk-fork` handoffs, numbered earlier generations of those handoffs, and corresponding files whose names contain `-dialog-` and whose purpose is to retain the ending portion of each session’s conversation.

## 6. How to give a new agent someone else’s handoff

1. The supervisor normally reads `~/.claude/handoffs/<agent>-handoff.md`, substituting the agent name supplied to the launcher for `<agent>`; consequently, an agent normally receives only the handoff filed under its own name.
2. Two already implemented and supported mechanisms allow that default association to be bypassed.
3. With `--first-prompt-file <path>`, the launcher forwards the supplied path to the supervisor, which uses the contents of that file as the new session’s first prompt and then returns to its normal startup behavior; “ordinary ignition” means that regular startup behavior after this exceptional initial prompt.
4. This option is the intended way to initialize a session from arbitrary saved context: the path can identify another thread’s handoff, a saved extract of its dialogue, or a newly written brief created for that purpose.
5. The alternative is to copy `~/.claude/handoffs/<old>-handoff.md` to `~/.claude/handoffs/<new>-handoff.md` before launching the agent named `<new>`, causing the new agent’s supervisor to treat the copied handoff as belonging to that agent.
6. Under either mechanism, a handoff created by a session that was itself forked describes the state that forked session had when it wrote the handoff, rather than necessarily describing the earlier point in history where the fork was created.
7. If the state at the actual fork point is the relevant context, the new session should instead receive the saved `-dialog-` extract or the full transcript, and its first prompt should explicitly identify which portion of that history it is supposed to work from or examine.

## 6a. Seats launched 2026-08-13, and how

1. The named positions `gatekeeper` and `sanity-checker` are currently running on the Ubuntu machine; each uses its own `~/agents/<seat>` checkout and branch and is reading the versions of its instructions that have already undergone review.
2. Both agents were confirmed to have started successfully: each was on the intended branch and displayed the expected status line, which is used as evidence that the project settings loaded and, by implication, that the recycling hook and the guard for instruction files loaded as well.
3. The documented launch recipe was deliberately not used because it is currently incapable of launching the reviewed material: it reads `docs/agents/seat-first-prompt.md` from the machine’s checkout of `main`, while that file and every correction produced by the briefs’ md-reviews still exist only in pull request #58.
4. Starting the agents from `main` would therefore have directed both of them to the older, unreviewed documents containing between twenty and thirty findings apiece.
5. The following steps describe the temporary launch procedure actually used and identify the arrangement that should be discontinued after pull request #58 is merged.
6. Each seat’s worktree was created from the pull-request branch instead of `main`, using `git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`.
7. Because the launcher does not attempt to create an agent home when that directory is already a Git checkout, preparing the worktree first takes precedence over and prevents the launcher’s normal worktree-creation step.
8. The launcher was then invoked with `sh scripts/launch-claude-mac <seat> --no-attach --first-prompt-file /home/nedlern/agents/<seat>/docs/agents/seat-first-prompt.md`, so the initial prompt file came from that seat’s own reviewed checkout.
9. The Mac counterpart runs directly on the Ubuntu machine and is mechanically the same as the Ubuntu launcher except that it omits the SSH connection step; that omission makes it usable by a session already running on the machine.
10. An expected consequence is that each seat’s branch includes the commits from pull request #58, so the supervisor’s branch-synchronization logic will report the branch as ahead of `main` and will leave it unchanged.
11. After pull request #58 is merged, those seat branches will instead be strictly behind the updated `main` branch and will be able to fast-forward in the normal way.
12. Nothing must be done unless pull request #58 is altered substantially before it is merged; if that happens, the seats should be restarted from the final merged version of `main`.
13. There is a particular danger that must be understood before approving a proposed cleanup operation.
14. Within minutes of launch, the `gatekeeper` agent recognized that its branch descended from the pull-request branch and proposed running `git reset --hard origin/main` to give itself a branch based cleanly on `main`; that proposal is reasonable from the limited state visible to the agent but would be incorrect under the present circumstances.
15. Such a reset would replace the checkout’s `docs/agents/` files with the older pre-review briefs, causing a later session using that seat to read versions that still contain the twenty-three findings associated here with the gatekeeper brief.
16. The reset should not be performed before pull request #58 is merged; after the merge it will be unnecessary because the seat branch will fast-forward automatically.
17. If a seat has to be cleaned and restarted before that merge, it should be relaunched from the pull-request branch instead of being reset to `main`.

## 7. Proposed split into named agents

1. The proposed arrangement uses three named agent positions selected so that no pair is expected to modify the same files or branches.
2. The `gatekeeper` position would own the remaining gatekeeper sequence—deciding the evidence format, implementing slice 6, and doing the credential work—as well as pull requests #55 and #57 and the fleet-and-session issues #45, #50, and #34; its starting context would be the transcript and handoff for the work stream represented by this document.
3. The `reviewer` position would own the decision about adding the sanity-checker to the review grid, classification of the newly discovered findings, pull requests #51, #52, and #53, and the candidate-skill issues #17 through #23; its starting context would be the transcript for `ea663864` plus transcript `29d66917` for the code-review-prompt work.
4. The `ghi` position would own `ghi-info` issue #46 and the related issues #41, #42, and #39; its starting context would be the existing GHI design documents in the repository.
5. Each position receives a separate agent-home checkout and consequently a separate Git branch, which is intended to prevent the positions from interfering with one another’s work.
6. If operating all three positions simultaneously is too much, only two should be started initially and the third can remain unstarted until capacity is available.
