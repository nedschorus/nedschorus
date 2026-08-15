<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md -->

# Title and unlabeled opening paragraph

1. The document's title means: this document is an inventory of the currently-unfinished work spread across the fleet of agent sessions on the Ubuntu box, together with a map showing where the historical context ("thread") for each piece of work can be found.
2. This is a point-in-time snapshot recorded on 2026-08-13, made in connection with GitHub issue #45 in the nedschorus repository, for the purpose of dividing the open work on the box among a small number of agents that have each been given a distinct name.
3. It was written because multiple parallel sessions had been piling up faster than anyone was keeping track of them: sessions were "forked" (branched off from a parent conversation) as a way to set aside context to return to later; successors who picked up that context wrote handoff documents describing their *own* state at the time they wrote the handoff, rather than describing the state of things at the moment the fork occurred; and, as a result of this, several separate threads of work ended up covering overlapping ground.
4. This document is meant as a snapshot of the operational situation, not as a fixed/permanent design document — the rows describing pull requests and issues will become outdated as those items are completed and merged, but the map of threads and the file paths to each one's context will remain useful over time.

# 0. State as of 2026-08-13, late evening

1. This subsection is presented as the fastest way for a reader to get up to speed.
2. Two agents ("seats"), named gatekeeper and sanity-checker, are currently running on the box; each lives in its own directory of the form `~/agents/<seat-name>`, each works on its own separate git branch, and each has already completed the first action it was assigned (neither is still waiting to begin).
3. The gatekeeper seat has finished reporting its results and is now waiting for a decision ("ruling") before it can proceed further; meanwhile, the sanity-checker seat is currently sorting/prioritizing four findings it produced and writing documents meant for a work queue, in order to route each finding to wherever it needs to go next.
4. The reader is directed to section 6a for details of how these two seats were started, and for a description of a single pitfall ("trap") connected with that startup process.
5. Every document belonging to a seat (i.e., each seat's brief/instructions) has gone through a review process called "md-review" — twelve such documents in total — and, for each one, the issues identified by its review have already been incorporated as corrections into that same document.
6. The reviews were harsh in their criticism but valuable: the review of the gatekeeper's brief found 23 issues, the review of a document called "the seat model" found 28 issues, the review of the sanity-checker's brief found 30 issues, and the review of "the fleet brief" found 26 issues; and, for each of these first four documents, the verdict on which of their sections were free of issues was "none" — i.e., no section of any of them came through clean.
7. The corrections resulting from those reviews are recorded in pull request #58.
8. The single largest category of problems found was related to terminology: the various briefs used the terms "pile," "walked approval," "instruction-class," "slice," and something called "the C-numbers" as though they were already commonly understood/agreed-upon, but in fact none of these terms was actually defined anywhere in those documents. (I cannot supply meanings for these terms myself — the sentence's own point is precisely that they were never defined anywhere.)
9. The document called "the seat model" has now been revised so that it provides a single, one-time definition for those terms.
10. There are two corrections in particular that are worth knowing about, because they fixed factual errors rather than merely wording problems: first, every document written that day had mistakenly been dated 2026-08-14 (this happened because automated job timestamps recorded in UTC were being read as if they were local time) and has now been corrected to read 2026-08-13; second, a repair command described in the "seat-first-prompt" document could not actually have worked as written — the command `git worktree add` refuses to run when its target path is not empty, and an alternate version of that command described as "dropping the `-b` flag" was also not a valid command — and this problem specifically applies to the situation where a seat is being relaunched onto a branch that already exists.
11. There remains outstanding work still owed: a second round of review needs to be done on documents that were changed after their first review (since applying fixes to a document can itself introduce new problems), beginning with the three files `seat-first-prompt.md`, `agent-seat-model.md`, and `gatekeeper-instructions.md`.

# 1. Open pull requests

1. Pull request #51 (branch `walk-and-md-review-skill-rules`): this PR establishes that items presented during a "walk" and offered as choices are to be treated as proposals rather than final decisions, and it changes the md-review skill so that it delivers its findings incrementally, tracked via a "Monitor."
2. Pull request #52 (branch `fast-handoff-findings-applied`): this PR applies the findings from a sanity-check performed on something called "fast-handoff," and it substantially strips down ("guts") an associated design document.
3. Pull request #53 (branch `sanity-checker-attack-split-experiment`): this PR adds three adversarial ("attack") prompts, adds a script at `scripts/md-drift-lint.py`, and adds twelve scored units ("cells") from an evaluation.
4. Pull request #55 (branch `claude/gatekeeper-audit-account-case-and-rulings-fold`): this PR changes an audit so that it compares account names without regard to letter case, and it merges the review decisions ("rulings") from issue #49 into the plan for the incremental build phases ("slices").
5. Pull request #57 (branch `launch-claude-machine-named-launchers`): this PR adds launcher scripts named after specific machines plus a Mac-side counterpart ("Mac twin"), a reference document of file paths across the fleet, a mechanism for a "supervisor" process to keep branches synchronized, and "session riders" (some form of supplementary attachment scoped to individual sessions).
6. Each of these five PRs is attributed to an "owner stream" — three to "choirmaster," one to "a third stream" (an unspecified/as-yet-unnamed stream distinct from the others named), and one to "gatekeeper-walk-fork."
7. All five pull requests are currently open and are waiting to be reviewed and merged by the agent/seat on the Mac side responsible for that task.
8. These five pull requests do not conflict with one another, because each one touches a different set of files and lives on a different branch.

# 2. Decisions waiting on the user

1. The first pending decision concerns "the sanity-checker grid seat": specifically, whether the sanity-checker agent should join a grid used for md-review by taking on three different adversarial postures ("cut," "mechanization," "fresh-eyes"), run across two model configurations, "Fable" and "gpt-5.6-sol," at a reasoning-effort level called "xhigh."
2. The supporting evidence for this is found in the file `md-review-records/2026-08-12-attack-split-experiment/scorecard.md` and in pull request #53; that evidence shows the split-into-three-stances approach outperformed a non-split baseline.
3. Job `ea663864` has been stalled, waiting on this decision to be made.
4. The second pending decision is a sequencing question: whether the grid-seat walkthrough described above should happen first, or whether sorting/prioritizing the new findings described in section 3 should happen first.
5. This is the same sequencing question that job `ea663864` previously raised and to which it never received an answer.
6. The third pending decision concerns the remaining path of work for the gatekeeper, all of which requires the user's sign-off at each step: first defining the evidence format for something called "walked approval" (a term used here without being defined in this document, so its exact meaning — e.g., a manually-verified, step-by-step approval process — cannot be determined with certainty from this text alone); then completing "build slice 6," described parenthetically as "the review-evidence check"; then doing the "credential work" (work presumably related to authentication credentials for the gatekeeper).
7. Until that entire sequence is completed, the gatekeeper mechanism ("the gate") will remain inactive.

# 3. Un-triaged novel findings (from the attack-split experiment)

1. The findings listed here were discovered beyond two existing reference sets of confirmed findings ("ground-truth sets"); they have not yet been shown/presented to anyone; and each one needs to be checked against the current, live state of the code before being included in any walkthrough, because the evaluation units ("cells") that produced them were working from archived, frozen snapshots of the code rather than its present state.
2. There is a rule in the gatekeeper's specification stating that "when a test suite exists, the tests run here" — meaning that once a test suite is present, the gatekeeper should run it — but this rule has never actually triggered in practice, even though a test suite now exists; consequently, the gatekeeper currently performs no checks at all.
3. There is no safeguard in place to prevent the gatekeeper mechanism from being used to modify itself.
4. There is a proposal under which whichever agent writes something would itself automatically insert the correct reference identifier ("the pin"), instead of requiring agents to manually type out full 40-character SHA (git commit hash) values by hand — the goal being to stop agents from hand-writing those values.
5. There is a described scenario, "the wedged-but-light session," in which a session becomes stuck but its resource usage stays low enough to remain below the threshold that would normally trigger it to be recycled/restarted, meaning no automatic monitoring mechanism ("watchdog") catches or addresses the stall.

# 4. Open issues, grouped

1. There are twenty-four open issues in total.
2. These issues are organized below by theme, for the purpose of splitting/dividing them up among agents.
3. Under the theme "Fleet and sessions" are grouped: issue #45 (about named agents), #50 (about hygiene of files within git worktrees), #34 (about a requirement that successor sessions must state their git context), #37 (about equivalents to "turn" and "steer," concepts not otherwise explained in this document), #27 (about inserting into a console and detecting a "stuck" state), and #40 (about hardening/securing the box).
4. Under the theme "Review and skills" are grouped: #24 (draining a work queue), #23 ("eval-agent-change"), #22 ("review-change"), #21 ("diagnose-failure"), #20 ("implement-with-evidence"), #19 ("attack-artifact"), #18 (writing a test plan), #17 ("design-change"), #38 ("watch-your-back"), #36 (mutual oversight between agents), and #26 (a dynamic model for teams of agents).
5. Under the theme "GHI and tooling" are grouped: #46 ("ghi-info"), #41 (a command-line tool for running an agent), #42 (a checker for reference integrity), and #39 (instrumentation for memory).
6. Under the theme "Doctrine and research" are grouped: #44 (doctrine about tracking imports), #35 ("usage-vs-expectation"), #33 (a "fast-handoff pickup" approach that has since been superseded), #32 (what an unexplained abbreviation "NC" preserves), #31 (requirements for a review system), #30 ("trigger-first" delivery), #29 and #28 (bundles of research), and #25 (timing of "check-in").

# 5. Thread map — where each thread's context lives

1. The saved transcripts (logs) of past sessions are what provides lasting, persistent context.
2. A newly started session can be pointed at any of the transcripts/context sources listed in the table below, regardless of what agent name that new session itself runs under; instructions for how to do this are given in section 6.
3. The thread combining "gatekeeper" and "launchers" (this current stream, job `ec9045a3`) is currently active; its pull request, #57, is open; and a handoff document exists for it at the given file path.
4. The current choirmaster stream (job `ea663864`) is currently active, but is stalled, waiting on the ruling discussed in section 2.
5. The predecessor/earlier choirmaster stream (job `49e0a3cf`) has been retired, and the handoff document it produced has already been read/used by its successor.
6. The thread concerning drafting a code-review prompt (no job ID given) is unclaimed by any agent, contains a substantial amount of context, and currently has no active/live session.
7. The sanity-checker thread (job `d9eda3ec`) has been retired, and a handoff document has been written for it.
8. The "login session" (job `3d8bf995`) never had any task assigned to it, and the recommendation is that it be deleted.
9. The "tmux seat" thread (job `f741668d`) is a duplicate of the choirmaster stream, and the note is that it should be reconciled against job `ea663864`.

## Complete transcript sweep (2026-08-13)

1. As part of this sweep, all 35 session transcripts larger than 30 kilobytes were examined for their titles, not merely the ones that were already known about beforehand.
2. What follows is what this sweep found that was not already captured in the table given earlier in section 5.
3. This introduces two threads that have substantial content but no assigned owner.
4. There is a transcript identified as `29d66917`, 3.67 megabytes in size, last written to at 20:30 on 2026-08-13, titled "Draft code review prompt for reliability improvement"; it represents substantial drafting work located within the `~/agents/choirmaster` directory; it has no currently active session; and it is not referenced in any handoff document.
5. The most fitting place for this thread's work is whichever seat ends up being assigned the review-and-skills work.
6. The second unowned thread is an entirely separate project called "nedsmessenger," located under `~/.claude/projects/-home-nedlern-agent-nedsmessenger/`; it consists of five sessions dated 2026-08-03 or 2026-08-04, totaling roughly 4 megabytes; these sessions are titled "Reorganize GitHub repos and GitHub Apps" (1.15 MB), "Create Samba links for Typora file access" (1.38 MB), "Review backup alert system improvements" (1.13 MB), "Merge PR #37 and resolve branch conflicts with main," and one further thread consisting of test messages.
7. This nedsmessenger project has not been touched for ten days (counting back from the 2026-08-13 snapshot date).
8. Whether this project is still considered active is a decision only the user can make; it is not part of the nedschorus project; and if it were resumed, it would need its own dedicated seat rather than being folded into an existing one.
9. This states that, aside from the two unowned threads just described, every other transcript found by the sweep has been accounted for and does not require an owner.
10. The remaining transcripts fall into three groups, none of which needs an owner: (1) earlier-generation versions of the two currently-live thread streams, specifically transcripts `5a7d955e`, `d9eda3ec`, `49e0a3cf`, `574972e0`, `1caf1c51`, and `ccc79ae5`, plus three transcripts specific to the gatekeeper worktree — `b2912831`, `27862506`, and `0550ed74`; (2) transcripts from md-review sessions and experiment evaluation units ("cells") whose resulting findings are already recorded in the `md-review-records/` directory — namely `3766ca30`, `84a8a260`, `946596c0`, and `0f34ff59` from a grid run on 2026-08-09; `832f3b95`, `9cd26c95`, `0e711797`, and `99a2f1a4` from a draft review of the sanity-checker; and `8d89bd09`, `83e22b1a`, `849436bf`, `9aae839c`, `cd59239a`, and `82f21e87` from the attack-split experiment run on 2026-08-12; and (3) two sessions concerned with maintaining the box itself from July — `bab1c2b3` (a security audit) and `c75a8d63` (an upgrade).
11. There are also preserved handoff documents and dialog excerpts, all stored under `~/.claude/handoffs/`: the handoff documents for the choirmaster and gatekeeper-walk-fork threads, earlier numbered versions of those same handoffs, and corresponding files containing "-dialog-" in their names that carry the most recent portion of each session's conversation.

# 6. How to give a new agent someone else's handoff

1. A component called "the supervisor" reads a handoff file located at `~/.claude/handoffs/<agent>-handoff.md`, where `<agent>` is substituted with whatever name was passed to the launcher; as a result, by default, a given agent only has access to its own handoff document.
2. There are two officially supported ways of getting around this default limitation, and both are already implemented (built and working, not merely proposed).
3. The first method is to pass a `--first-prompt-file <path>` option to the launcher; the launcher forwards this through to the supervisor, which reads that file's contents and uses them as the new session's very first prompt, after which the session proceeds through its normal startup process.
4. This mechanism is the intended way of initializing ("seeding") a session with any chosen context — for example, by pointing it at another thread's handoff document, at that thread's dialog-extract file, or at a document written specifically to serve as a briefing.
5. The second method is to copy an existing agent's handoff file to a new filename matching the new agent's name — using a command of the form `cp ~/.claude/handoffs/<old>-handoff.md ~/.claude/handoffs/<new>-handoff.md` — before launching the new agent; that new agent's supervisor will then read the copied file as though it were its own.
6. Either way, it should be understood that a handoff written by a session that was itself created as a fork describes that forking session's own state at the moment it wrote the handoff, not the state of the original conversation at the point where the fork occurred.
7. When what actually matters is the state of things at the moment of the fork, the new session should instead be pointed at the corresponding dialog-extract file or the full transcript, and the first prompt given to the new session should explicitly state which portion of that history is the relevant subject.

# 6a. Seats launched 2026-08-13, and how

1. The gatekeeper and sanity-checker agents are currently running on the box, each in its own `~/agents/<seat-name>` directory, each on its own branch, each reading the versions of its brief that have already been through the review-and-correction process described in section 0.
2. Both were confirmed to have started correctly: their branches were confirmed, and a status line was observed to be present — this status line's presence serves as evidence that the project-level settings loaded correctly, which in turn implies that a "recycle hook" mechanism and an "instruction-file guard" mechanism also loaded successfully.
3. These two agents were **not** started via the standard documented launch procedure, because that procedure currently cannot succeed: it reads a specific file, `docs/agents/seat-first-prompt.md`, from the version of the main branch checked out on the box, but that file — along with every other md-review correction to the briefs — currently exists only inside pull request #58 and has not yet been merged into main.
4. If the agents had instead been launched from the current state of main, they would have started up using the older, uncorrected versions of their documents — the ones that, per section 0, still carried between twenty and thirty unresolved findings each.
5. What follows describes what was actually done instead, and what should be undone once pull request #58 is merged.
6. For each seat, its git worktree was created starting from the pull-request branch (`seat-launch-first-prompt`) rather than from main, using a command of the form `git worktree add ~/agents/<seat> -b <seat> seat-launch-first-prompt`.
7. The launcher script skips its own step of creating a home directory when that directory is already a git checkout, so creating the worktree manually beforehand simply preempts/bypasses that automatic step.
8. The launcher was then run using the `seat-first-prompt.md` file located within that seat's own newly-created checkout, via a command of the form `sh scripts/launch-claude-mac <seat> --no-attach --first-prompt-file /home/nedlern/agents/<seat>/docs/agents/seat-first-prompt.md`.
9. The "Mac twin" launcher script can be run directly on the Ubuntu box itself, and behaves functionally identically to the regular Ubuntu launcher except that it omits the step of connecting via SSH to a remote machine — it is this omission that makes it usable from a session already running on the box.
10. One should expect the following consequence: because each seat's branch includes pull request #58's commits (having been branched from that PR's branch), the supervisor's branch-synchronization process will find the branch to be ahead of main and will make no changes to it.
11. Once pull request #58 is merged, those branches will become strictly behind main and will be able to be updated via an ordinary, conflict-free "fast-forward" merge.
12. No further action is needed unless pull request #58 changes substantially before it is merged, in which case the seats should instead be relaunched fresh from main after that merge.
13. This introduces a pitfall that should be thought through carefully before being agreed to.
14. The gatekeeper agent itself noticed, within minutes of starting, that its branch had this unusual history, and proposed running `git reset --hard origin/main` to reset its branch to a state matching main — reasoning that makes sense from the gatekeeper's own limited perspective, but which would be the wrong action to take at this point in time.
15. If that reset command were run, the `docs/agents/` directory within the gatekeeper's checkout would revert to the older, uncorrected briefs, and any later session running in that seat would end up reading the version of the gatekeeper's brief that still carried its original twenty-three findings.
16. The recommended course of action is to wait until pull request #58 merges, at which point the reset becomes unnecessary because the branch will catch up to main automatically via fast-forward.
17. If a seat absolutely must be cleaned up before that merge happens, the correct way to do so is to relaunch it from the pull-request branch, not by resetting it to main.

# 7. Proposed split into named agents

1. Three seats are being proposed, chosen specifically so that no two of them need to touch the same files or work on the same branch.
2. The first proposed seat, "gatekeeper," would take on: the remaining sequence of gatekeeper work (evidence format, then build slice 6, then credential work, in that order); pull request #55; pull request #57; and the fleet/session issues #45, #50, and #34.
3. This seat's background context would be the transcript and handoff document belonging to this current stream (the one that produced this document).
4. The second proposed seat, "reviewer," would take on: the decision about whether the sanity-checker joins the md-review grid; triaging the novel findings from section 3; pull requests #51, #52, and #53; and the candidate-skill issues numbered #17 through #23.
5. This seat's background context would be job `ea663864`'s transcript, plus transcript `29d66917` specifically for the code-review-prompt drafting work.
6. The third proposed seat, "ghi," would take on the "ghi-info" issue (#46) along with its related issues #41, #42, and #39.
7. This seat's background context would be the design documents relating to "ghi" that already exist in the repository.
8. Each seat is given its own dedicated home directory and, consequently, its own separate branch, and it is this separation that prevents the seats from interfering with one another.
9. If launching all three seats at once turns out to be more than can be managed simultaneously, it is acceptable to start with only two, leaving the third to begin later.

