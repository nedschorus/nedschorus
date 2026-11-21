---
issue: "[Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop](https://github.com/nedsnodes/nedsnodes/issues/2161)"
kind: design
---

# Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop

This GHI-MD is the design of the emergency-stop skill and its hooks, filed as a GitHub issue so that the work has one record.

## Paused on 2026-11-20: what is built and what is still open

The user paused the emergency-stop work on the evening of 2026-11-20, Pacific time (2026-11-21T01:17:08Z UTC; times below are UTC), in the walk-minutes of approval-walk ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05, `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`, line 627, in his words: "We've been working on this emergency stop stuff for a long time. I think it's just I think we should pause this and save what we got and put it back into a GitHub issue. I'm also worried that we're working on the emergency stop, but we haven't defined how to restart it. And we seems like very rarely need it. So yeah, I just package all this up in or record everything we've got in a nice MD file and stick it in a GHI and pull all the related walk items out once they've been recorded. So we can move on to something more useful." This section records everything still open, so that the work can be picked up later without loss. No work on it resumes until the user says so. Two words from his quote: "restart" here means agent-seats taking up again, after a lift, the work they held back during the emergency stop; "walk items" are approval-walk items.

What is built. PR [Emergency stop: the /emergency-stop skill, its stop-file program, and the hook that shows the stop and refuses pushes and merges, with the rulings of approval-walk items 21 to 38 (replaces 3599)](https://github.com/nedsnodes/nedsnodes/pull/3605) merged on 2026-11-14 as 0440ba7c4: `.claude/skills/emergency-stop/SKILL.md`, the programs in `nn-systems/skills/emergency-stop/`, the hook registrations in `.claude/settings.json`, and the change, during an emergency stop, to two hooks of /walk-me-through that run on Claude Code's Stop event, in `nn-systems/skills/walk-me-through/`. merge-lane-2's approving review of PR 3605 left three non-blocking findings: the first, a test that `start` fails when the read-back finds another emergency-stop file in force, merged as PR [3607](https://github.com/nedsnodes/nedsnodes/pull/3607); the second is PR 3901 below; the third, whether the hook exits when its read of the emergency-stop folder hangs, is the first unseen approval-walk item below. The glossary lines of part 5 of the approval of 2026-10-30 at 15:55 (under What is decided) are in `docs/nedsnodes-wiki/nedsnodes-glossary.md`. No emergency stop appears to have been started: the folder `/home/nedlern/nedsnodes-logs/emergency-stop/` did not exist on 2026-11-20.

### Open: PR 3901, the six failure messages, and its changes-requested review

PR [Emergency stop: six failure messages say what was written, whether pushes and merges are refused, and the command to run again](https://github.com/nedsnodes/nedsnodes/pull/3901) is open as a draft, converted at the pause. Branch `emergency-stop-six-messages-say-what-was-stopped-and-what-to-do-topic-branch`, nc-head-commit 3faa82884; its worktree on ned-box, `/home/nedlern/agents/prime-intellect-worktrees/emergency-stop-six-messages`, is kept until the user decides whether PR 3901 goes on.

What it changes. It answers the second of those findings: six places where a cold-read-fast-read struggled with the messages, opening FAILED, that the program prints when it cannot write or read the emergency-stop file. In `nn-systems/skills/emergency-stop/`, each failure message of `emergency-stop-file-write-start-append-and-stop-lift.py` prints the text the user approved in items 55.1 to 55.6 of the approval-walk (his answers are in the walk-minutes, lines 357 to 393; 55.3 asked for no decision). The full approved texts are in the walk-document, `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05.md`, under the headings "Item 55.1 of 69" to "Item 55.6 of 78", and as built on PR 3901's branch. After a failed write or read-back, the program reads the folder itself and states whether a stop is in force. When `start`'s read-back does not find its stop in force, `start` writes and reads back a second time; a failed write is not retried. After the second try, `start` deletes each emergency-stop file it created that still holds only the text it wrote, and keeps one another agent-seat has added to; when the second try succeeds, it also keeps the file in force. The unreachable-folder and failed-write messages end with the exact command line to run again. The hook's test now checks the whole text of its message for an unreadable emergency-stop file (item 55.1), and each failure test compares the whole printed message. As built, 55.2's message opens "start wrote no emergency-stop file"; the text the user approved says "start wrote no stop file". The built text puts the glossary's term, "emergency-stop file", in place of his plain words (walk-minutes line 398), and the pull request's description does not mention it.

merge-lane-2's round-2 [review 5998696090](https://github.com/nedsnodes/nedsnodes/pull/3901#pullrequestreview-5998696090), CHANGES_REQUESTED at 3faa82884 on 2026-11-20, has two findings, both from Codex, which merge-lane-2's review runs as one of its reviewers, on `nn-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py`. The must-fix-now findings of its first review, that is the findings to fix before the merge, are fixed at 3faa82884, and the test run of 3faa82884 merged with main passed 21 of 21. The two findings:

- Blocking, Codex P1, lines 205-209: another agent-seat's `append` can land after `start`'s clean-up has read the stop file but before it deletes it; the file still compares as unchanged, and the clean-up deletes the other agent-seat's stop, whose command had reported its words saved. merge-lane-2 graded it must-fix-now, the same kind of finding as one of the first review's, at line 180, that the clean-up could delete an emergency-stop file another agent-seat had added to, and asked for a simplification instead of another fix-round: "The simplest shape may be for start's retry never to delete a stop file it created. ... Please send merge-lane-2 the shape you choose before pushing; if it changes the design the user approved, it goes to him first."
- Fix-next, that is in a follow-up after the merge, Codex P2, lines 206-207: no test causes the new `UnicodeDecodeError` handler; if the simplification removes the handler, the finding goes with it.

The fix the review suggested as "the simplest shape", which merge-lane-2 then reviewed as an approval-walk item and on which the user has not ruled, is approval-walk item 78: `start` never deletes a stop file, and its FAILED message tells the agent to run `status` and tell the user. It reverses the user-ruling on item 55.6 of 2026-11-17, that `start` deletes the stop files it wrote "so that a failed start can never come into force later". The user moved on from 78.1, which asked no decision, on 2026-11-21 at 01:08Z (walk-minutes line 623); 78.2 was waiting for his answer when he paused the work, and was closed unanswered (lines 627 to 629). Item 78 as the walk-document showed it, word for word, without its withdrawn versions:

> ## Item 78 of 120: Emergency-stop `start` stops deleting the stop files it wrote, so it can never delete another agent-seat's stop
> #approval_walk_item_first_entered 2026-11-20
> #approval_walk_item_in_category_must_fix_now
>
> ### Item 78.1 of 120: What `start` deletes today, and the defect the review found
>
> You ruled on 2026-11-17 (item 55.6 of [this walk](file:///Volumes/nedhome/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05.md)) that when `start` cannot find its new stop in force, it tries once more, and when both tries fail it deletes the stop files it wrote, "so that a failed start can never come into force later". Both review rounds of [PR "Emergency stop: six failure messages say what was written, whether pushes and merges are refused, and the command to run again"](https://github.com/nedsnodes/nedsnodes/pull/3901) found this defect in that delete:
>
> Agent-seat A's `start` writes a stop file, but A's read-back fails twice, say because the folder answers late. Meanwhile B's `start` finds A's file in force, adds B's words to it, and tells B "added to the emergency stop in force". Then A deletes the file: B's stop is gone, and pushes and merges are no longer refused. A reads the file just before deleting it, to see whether anyone added to it, but B's words can land between that read and the delete.
>
> The fix is to stop deleting. Only the newest stop file, by its name, the UTC time it was started, counts; `lift` adds a line to the newest and removes no file. So a stop file a failed `start` leaves in the folder counts only when it is the newest. That is the case you ruled out: the folder answers late, both tries fail, `start` prints FAILED, and then the file appears and the stop takes effect late, even after a lift. It is still a stop the user asked for, and he can lift it.
>
> No decision here; type N or next to continue.
>
> ### Item 78.2 of 120: `start` keeps every stop file, and its FAILED message says so
>
> Part 1. `start` never deletes a stop file. Its report after a successful second try drops "; it kept {paths}, the stop file its first try wrote, because another agent-seat added to it after start wrote it".
>
> Part 2. The FAILED message's "so it deleted the stop files it wrote." becomes:
>
> #new "so it left the stop files it wrote in the folder; only the newest stop file counts.\nWhen the folder can be read again, run `python3 nn-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py status`; if it prints InForce, tell the user, who decides whether to lift the stop."
>
> #case_against weak: a stop can come into force after `start` said it failed.
>
> The alternative: as offered on 2026-11-17, the agent makes the second try, and the stop files stay in the folder.
>
> The advisor and merge-lane-2 reviewed this item, and its proposed text had a fast read of its own.
>
> Recommendation: make parts 1 and 2 in PR 3901.

A further defect of the same code, noted in the walk-minutes at line 400 and never shown to the user: when `start`'s two tries each only add to another agent-seat's stop file, as after two starts in the same second, and both read-backs fail, `start` has created no file of its own, yet its FAILED message says it "deleted the stop files it wrote". At 3faa82884 the message is still built that way when nothing was created and the failure is a read-back (lines 178 to 188 and 215 to 217; read from the code, not run). Item 78.2's new text, "so it left the stop files it wrote in the folder", would be untrue in the same case, and it says what to do only when `status` prints InForce. The wording for the case where `start` created no file is the user's to approve; it goes to him with item 78, and the build makes the message from the list of files `start` created, with a test that causes that case.

### Open: two approval-walk items the user has not seen

Both were in the walk-document, not yet shown to him, when he paused the work. The second is the same matter as question 4 under Deferred-decisions below, with the same recommendation; what it adds is its case against, that an emergency may well make several agent-seats start a stop at once. Each is copied whole, word for word, and a note after each says where it no longer matches the merged code.

> ## Whether the emergency-stop hook exits when its read of the stop folder hangs
> #approval_walk_item_first_entered 2026-11-14
> #approval_walk_item_in_category_fix_during_maintenance
>
> On the Mac, the emergency-stop hook reads the stop folder on ned-box through the Mac's network share of ned-box. It gives that read 5 seconds, on a separate thread, then goes on without it. merge-lane-2 asked whether the hook really exits when the share hangs. If it did not, every Mac command the hook guards would wait too. Nobody has seen this happen.
>
> A test on ned-box can check most of it, in about 20 lines and 5 seconds of test time: it puts a named pipe with no writer, named like a stop file, in a stop folder made for the test, so the hook's read blocks for good, and checks that the hook still exits within 15 seconds: the 5 seconds plus time to start. What it cannot check is a read stuck inside the Mac's operating system on a hung share; that needs the Mac with the share deliberately hung.
>
> #case_against weak: it adds a test for a failure nobody has seen.
>
> The alternative: add no test, and change nothing until a hook is seen stalling.
>
> Recommendation: add the ned-box test to the follow-up pull request, and test the Mac case only if a hook is seen stalling there.

Note: "the follow-up pull request" in this item meant the follow-up to PR 3605 for merge-lane-2's non-blocking findings, which is now PR 3901. The hook runs at every prompt and every tool call (`.claude/settings.json`), so a hung read would hold all of a Mac agent-session's work, not only its pushes and merges, until Claude Code's hook time limit stops the hook.

> ## Two emergency stops started a second apart can hide one of them
> #approval_walk_item_first_entered 2026-11-14
> #approval_walk_item_in_category_fix_during_maintenance
>
> The emergency-stop program's `start` reads the stop folder, then writes a stop file named by the time; the newest file not lifted is in force. Two starts in the same second collide on the file name, and the second adds to the first; two starts a second apart do not.
>
> Example: A starts a stop at 12:00:07 and B at 12:00:08, each having read the folder before the other wrote. Both are told "started", but only B's file is in force: A's evidence is hidden, and the hook, which refuses pushes from every agent-seat except the one coordinating the repair, refuses A's pushes. In a second case, an agent-seat's words added to a stop just after you lift it put it back in force. prime-intellect reproduced both on main ([reproduction](file:///Volumes/nedhome/nedschorus-logs/seats/prime-intellect/emergency-stop-start-append-race-reproduction-2026-11-14/)). [PR 3608, "GHI-MD edit for issue 2161: Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop"](https://github.com/nedschorus/nedschorus/pull/3608) records the race as open in GHI 2161's design.
>
> No emergency stop has happened yet. The window is about a second, not measured, and nothing is deleted: both files stay in the stop folder for anyone to see and fix by hand.
>
> #case_against medium: an emergency may well make several agent-seats start a stop at once, and then the agent-seat that believes it coordinates the repair cannot push.
>
> The alternative: add a lock. Each write first claims a lock file, and a start that finds it taken waits, then reads the folder again. It needs a rule for a lock a crashed program leaves behind, and nobody has checked that the lock holds on the Mac, which reaches ned-box's stop folder over its network share.
>
> Recommendation: change nothing until an emergency stop shows the race.

Note: "the newest file not lifted is in force" in this item is looser than the merged reader, `nn-systems/skills/emergency-stop/emergency-stop-file-in-force-read-common.py`, which looks only at the newest emergency-stop file and counts a stop in force while that file's last line is not a lift line.

### Open decision: how work restarts after an emergency stop

The user's question, from his ruling above: "we haven't defined how to restart it". He added that a stop is very rarely needed: "we seems like very rarely need it". No design has been put to him.

What happens at a lift today, on main at 8108ca041:

- `lift` appends two lines to the stop file in force: `<time> lifted by <agent-seat>`, then `#emergency_stop_lifted <his words>` (`nn-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py`, lines 234 to 236). `hand-over-lift` records that a named agent-seat may lift on his word, and does not lift.
- The hook, `nn-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook.py`, runs at UserPromptSubmit and at every PreToolUse (`.claude/settings.json`). After a lift it shows each agent-session once: "[rule emergency-stop-state-shown-to-every-agent-session] The emergency stop {path} was lifted: {lift_line}" and "Its rules no longer apply: resume the work you held back, and push and merge as usual." (lines 92 and 93). Its push-and-merge refusal stops.
- `.claude/skills/emergency-stop/SKILL.md`, "Lifting a stop": whoever lifts re-enables, by hand, the schedule of each scheduled job the repair brief lists as paused, asks an agent-seat on the other machine for the jobs there, and tells the user any it could not turn back on. GHI [Pause and resume scheduled jobs during an emergency stop with pause-job and resume-job commands of the emergency-stop stop-file program](https://github.com/nedsnodes/nedsnodes/issues/3075) would move those steps into code.
- The rules the hook shows during a stop say that an open approval-walk resumes at its `#next_to_present` item after the lift (hook line 78).

What nothing covers today:

- Waking agent-seats. An agent-session learns of the lift only at its next prompt or tool call. An agent-seat that obeyed "do no more work until the coordinating agent-seat or the user gives you work" and ended its turn sits idle until someone sends it a message; nothing in the skill or its programs sends one.
- What was held back. Nothing records what each agent-seat held back, or which background tasks it killed, so "resume the work you held back" rests on each agent-session's own context, which a session-handoff or a restart during the emergency stop may have lost. A killed background task is not restarted by anything.
- Checking that work restarted. No step confirms that each agent-seat saw the lift and resumed, nor reports one that did not.
- Ending the repair. Nothing says that the coordinating agent-seat's role ends at the lift, or that the repair brief records how the repair ended.
- Order. Every agent-seat may push its locally committed work at once after the lift; nothing sets an order.

The decision for the user: whether a restart needs defining before more work goes into stopping, and if so what it covers. One choice, consistent with his remark that a stop is very rarely needed, is to define no more than what is built, and decide the restart after the first real stop shows what it lacks. Pieces a restart design could use, proposed by the cold-read-fast-read of this section and not yet weighed: `lift` sends every agent-seat a message, so that none waits idle; the hook records which agent-sessions it has shown the lift notice, and `status` lists the agent-seats not yet shown; the hook records each push or merge it refused, with its directory and branch, and the lift notice lists them to the agent-seat that ran them; and GHI 3075's `pause-job` and `resume-job` become part of the restart.

### Other open emergency-stop work

- Question 4 under Deferred-decisions below, two stops started a second apart, is open; the unseen approval-walk item above carries the same choice.
- The 08:00 Pacific reminder during a stop is not built: under "Still open for the build" below, it waits for a channel a scheduled job can use. Of the files that `git grep -i -l emergency 8108ca041 -- nn-systems scripts .claude` lists, none outside `nn-systems/skills/emergency-stop/` is a program that sends it, and none inside does either. Archived prime-intellect task 131 (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/task-list-archive-2026-11-17/task-list-archive.md`, line 153) lists it as still to do.
- GHI [3075](https://github.com/nedsnodes/nedsnodes/issues/3075) is open with a placeholder body, "Filing in progress, pairing key ghipairdaa2f3116d9e03e0", although its GHI-MD, `docs/issues/3075-pause-and-resume-scheduled-jobs-during-an-emergency-stop-with-pause-job-and-resume-job-commands-of-the-emergency-stop-stop-file-program.md`, merged in PR 3076; rerunning `python3 scripts/ghi-issue-write.py create` on that file finishes its filing, as the GHI's placeholder body itself says. Its build is paused with this work.
- Question 23's completion check. On 2026-11-20 every agent-home on ned-box under `/home/nedlern/agents/` held the merge commit 0440ba7c4; the Mac's agent-homes were not checked (unverified). The Outcome section the Next action asks for has not been written.
- Older text of this GHI-MD that no longer matches the merged code or itself, found by the cold-read-full-run of 2026-11-20 (cold-read-record `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/2161-build-the-emergency-stop-skill-which-writes-one-2026-11-20-2/`), to be brought into line when the work resumes; the approved texts quoted under What is decided stay as the user approved them. "Why" says "Today" a stop reaches other agent-seats only by relayed messages, which was true before PR 3605 merged. Question 3 says the stop file lists the scheduled jobs that push or merge; the program lists every job in `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`. Question 9 names the repair brief `<stop file name>-repair-brief.md`; the program builds it from the name without `.md`, as `2026-11-14T12-00-07Z-repair-brief.md`. Question 13 says every push and merge is refused; the hook refuses only the `git push` and `gh pr merge` it sees in an agent's own Bash command, not one a program the agent runs makes, a gap the user ruled on 2026-11-11 to leave until an emergency stop shows it (item 22 part 4 of approval-walk merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08, as merge-lane-2's approving review of PR 3605 records). Question 19 gives the lift notice as one line with a time; the hook's notice is the two lines quoted under "Open decision" above. The build's settled answers say stop files are named by the UTC time a stop started; the program names a new file one second after the newest lifted file when this machine's clock is behind the one that wrote it. Question 4 paraphrases the guard rule of `CLAUDE.md` more loosely than `CLAUDE.md` words it.

## Why

When something goes wrong across many agent-seats at once, the user needs one way to stop their work that every agent-seat obeys the same way, and that says who may lift the stop. Today a stop the user gives one agent-seat reaches the others only by messages that agent-seat relays, or by the user typing it into each agent-seat's window himself. On 2026-10-28 the user stopped the work of every agent-seat. Three agent-seats relayed the stop within four minutes, each with a different scope, and each copied its own version into its session-handoff; no message said who could lift the stop, and it was lifted at about 05:45Z on 2026-10-28, by merge-lane-2, to which the user had delegated the decision. This account is the one the first version of approval-walk item 7.1.2.1.1 of 38 gave the user; its text is `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/item-7-1-2-1-1-emergency-2026-10-28/item-7-1-2-1-1-emergency-with-sentence-ids.md`.

## What is decided

On 2026-10-28, at 18:10 by the walk-minutes' clock, the user approved the text quoted below, answering A (approve) to item 7.1.2.1.1 of 38 in the approval-walk agent-instructions-editor-open-decisions-2026-10-26. He approved only that text and the definition in the paragraph after it; the rest of this GHI-MD was written afterwards, by agents. Sources:

- The walk-minutes, `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, kept in the agent-home of the agent-seat agent-instructions-editor. Search them for "item 7.1.2.1.1 of 38" or for "emergency": the walk was renumbered while it ran, and before the item that became this one took the number 7.1.2.1.1, the number belonged to a different item, about PR 1878.
- The approved text as the user saw it: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/agent-instructions-editor-open-decisions-2026-10-26-item-7-1-2-1-1-of-38-new-1-2026-10-28/agent-instructions-editor-open-decisions-2026-10-26-item-7-1-2-1-1-of-38-new-1-with-sentence-ids.md`, with a fast read of it, `fast-read.md`, in the same directory.
- The item's third version, which carries the definition below; its quoted design is an earlier wording, which was revised into the approved text before the user approved it: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/item-7-1-2-1-1-v3-2026-10-28/item-7-1-2-1-1-v3-with-sentence-ids.md`.
- The item page, https://claude.ai/artifact/2xpoLtwBJZLwXq4exswoD6, which only the user can open, and which the walk rewrites in place; the two files above are the record.

The approved text, word for word:

> An emergency stop is one file in the log-store, which the emergency-stop skill writes. The user starts the skill by typing /emergency-stop, or by telling any agent-seat, in any words, to stop the fleet's work; an agent-seat starts it on its own when an emergency, as the skill defines one, is under way and it cannot stop it alone. The file holds the user's words, or the agent-seat's evidence, with the time, and, once known, the agent-seat that coordinates the repair and a link to its brief. An agent-seat that starts a stop on its own tells the user at once by a push notification. Only the user lifts a stop: until the skill, on the user's word, adds the line `#lifted <the user's words>`, a hook shows the file to every agent-session at each turn; every agent-seat lets running work finish without pushing, takes work only from the coordinating agent-seat, asks the user nothing outside the repair and shows no walk item; and the walk-me-through hooks let every agent reply through.

The item's third version also said, and the user approved with it: "The skill's first definition of an emergency is work being lost or damaged across agent-seats; the GHI leaves a sharper definition as an open question for you."

The user's words that shaped the design, in the same approval-walk on 2026-10-28, before he approved it:

- "I'm a little concerned that if things really go wrong, I won't remember the keywords to trigger it. And I'm actually okay with agents triggering it too, if something is really terribly wrong".
- "This kind of sounds like a skill. Like if I type /emergency kind of thing. ... if it's a skill, we can try to more carefully define what an emergency is, but your first pass is decent."

On 2026-10-30 at 08:28 UTC the user answered A (approve), to all four parts, item 3 of the approval-walk prime-intellect-handed-over-items-2026-10-29 (walk-minutes `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 27; the item's text is in the walk-document beside them). The four parts he approved, word for word:

> Part 1, where the stop is kept: one file per stop, in the log-store folder `nedlern@ned-box:/home/nedlern/nedsnodes-logs/emergency-stop/`, named by the UTC time it started. A stop is in force while the newest file has no lift line. Nothing else writes or tidies that folder.
>
> Part 2, who coordinates the repair: the agent-seat that started the stop, or, when you started it, the agent-seat you told, until you name another. If that agent-seat stops and no successor of it starts, every agent-seat lets running work finish and takes no new work until you name another. Every agent-seat may still take work from you.
>
> Part 3, how a stop is lifted: you tell any agent-seat, in any words, and it runs the skill. This adds one thing to the approved "Only the user lifts a stop": you may hand the lift to a named agent-seat, as you did on 2026-10-28, and its lift then counts as your word. The line written is `#emergency_stop_lifted <your words>`, with your words lifting it or handing the lift over, in place of `#lifted`, so that a reader sees an emergency stop was lifted.
>
> Part 4, the other 20 questions: the builder settles each, taking the GHI-MD's recommendation where it gives one, and records the answers in the GHI-MD. The answers that change what you see or must do come to you together, as one approval-walk item, before that part is built.

The item's recommendation, which he approved with it, was: "approve all four parts; prime-intellect records them in the GHI-MD and builds the skill." So questions 8, 10, 11 and 17 below are settled by parts 1, 3, 2 and 3; question 20 by that recommendation, which makes prime-intellect the builder; question 21 by part 4; and questions 1 to 7, 9, 12 to 16, 18, 19 and 22 to 24 are the builder's to settle, as part 4 says.

On 2026-10-30 at 15:55 UTC the user answered "A, approve." to item 9.1.2.1 of 23 of the same approval-walk (walk-minutes lines 84 to 86), which put to him, as part 4 above asks, the builder's answers that change what he sees or must do. The five parts he approved, word for word:

> Part 1. An emergency is work being lost or damaged in several agent-seats, or in something they share, such as main or a machine. When you speak, the stop covers every agent-seat only if you name more than one, as in "everyone", or type /emergency-stop. It reaches every agent-session on both machines; scheduled jobs keep running, pushes included, listed for pausing by hand.
>
> Part 2. If the stop file cannot be written, the agent tells you and stops only its own work. A Mac agent-session that cannot read ned-box's log-store shows "emergency-stop state unknown" once and carries on.
>
> Part 3. During a stop a hook refuses every agent-session's push and merge, except those of the agent-seat coordinating the repair.
>
> Part 4. An open approval-walk pauses during a stop and resumes after you lift it. During a stop you get a push notification at 08:00 Pacific each morning.
>
> Part 5. "Emergency stop" is never abbreviated. The project glossary gains, when the skill lands: **/emergency-stop** — the skill you run to stop every agent-seat's work at once; **emergency-stop file** — the one file in the log-store that every agent-session is shown until you lift the stop.

The item's recommendation, which he approved with it, was: "approve all five parts, record them in GHI 2161, and build the skill." The builder's full answers are in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/emergency-stop-builder-answers-to-deferred-questions-2026-10-30.md`; the questions below carry them, those the user approved marked "approved 2026-10-30".

## Deferred-decisions

These were put to the user as the user's to decide. Questions 8, 10, 11, 17, 20 and 21 are settled by his approval of 2026-10-30 at 08:28 under What is decided; the builder settled the rest, as part 4 there says, and each now carries its answer, those that change what the user sees or must do approved by him on 2026-10-30 at 15:55. Question 4 is open again: the builder's answer leaves a case the merged program does not handle, and the user has not decided it. They were raised by a fast read of the approved text (record cited above), a fast read and a full cold read of this GHI-MD (`nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/emergency-stop-skill-2026-10-28/` and `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/emergency-stop-skill-2026-10-28-2/`), and, for the lift line's name, a check against `docs/nedsnodes-wiki/nedsnodes-how-to-choose-a-name-for-files-code-and-glossary-terms.md` whose report was not kept; question 10 carries its finding. Questions 20 to 24 come from findings of that full cold read which the rewrite did not settle, and from the names the reviewers proposed; each carried the recommendation of the agent that wrote this GHI-MD, and each now carries the answer that settles it.

When a stop starts:

1. What sharper definition of an emergency should the skill give? Today's is work being lost or damaged across agent-seats; it does not say whether that means the work of more than one agent-seat, or one piece of work several agent-seats depend on, nor how it combines with the approved text's "it cannot stop it alone". Settled, approved 2026-10-30 (part 1): work being lost or damaged, or about to be, in more than one agent-seat at once, or in one thing several agent-seats depend on, such as main, the log-store, GitHub access or a machine, which the agent-seat that sees it cannot stop by stopping its own work. The CPU stall on ned-box of 2026-10-28 qualifies; one agent-seat's failing test does not.
2. When the user's words to one agent-seat could mean a stop of every agent-seat, a stop of that agent-seat's own work, or a pause of an approval-walk, how does the agent-seat tell which he means? Settled, approved 2026-10-30 (part 1): the skill runs only when his words name more than the agent-seat he is talking to, such as "everyone", "all agents" or "the fleet", or he types /emergency-stop; otherwise the agent-seat stops its own work only. When unsure, it asks him one yes-or-no question: "Stop every agent-seat's work?"
3. Which work does a stop cover: only the work of agent-seats, or also scheduled jobs and other programs that run without an agent-session? Does it cover the subagents an agent-seat has dispatched, and Claude agents on the Mac that are not agent-seats? Settled, approved 2026-10-30 (part 1): every agent-session that loads this repository's hooks, that is agent-seats on both machines, their subagents, and Mac Claude agents in a nedschorus checkout. Scheduled jobs are not stopped and keep pushing; the skill lists in the stop file the jobs that push or merge, from `nn-systems/general-tools/scheduled-jobs-on-each-machine.json`, so the coordinating agent-seat can pause them by hand.
4. What happens when someone starts a stop while another is in force, or when two agent-seats start one at the same time? Open again since 2026-11-14; the user has not decided. Until he does, the merged program stays as it is and nothing waits on this question. The builder's answer was: "the skill writes no new file while a stop is in force; it appends the new words or evidence, with the time, to the file in force. When two start at once, the file is created with exclusive create, and the one that loses appends." That answer settles only two starts that pick the same file name, and file names differ by the second.
   - What the merged program does. `nn-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py`, merged in PR [Emergency stop: the /emergency-stop skill, its stop-file program, and the hook that shows the stop and refuses pushes and merges, with the rulings of approval-walk items 21 to 38 (replaces 3599)](https://github.com/nedschorus/nedschorus/pull/3605), runs `start` so: it reads the emergency-stop folder; when the newest stop file is in force, it appends to that file; otherwise it names a new file by the UTC second, writes the text to a temporary file and hard-links it to that name, so a second `start` that picks the same name finds the name taken and appends instead; then it reads the folder again and prints FAILED when the stop it wrote is not the one in force. Nothing keeps one invocation from reading the folder between another invocation's read and write.
   - Two starts in adjacent seconds. Agent-seats A and B both see main lose commits and run `start`, A at 12:00:07.9 and B at 12:00:08.0, and each reads the folder before the other's file exists. A writes `2026-11-14T12-00-07Z.md`, reads the folder back, finds its own file in force and prints "started". B then writes `2026-11-14T12-00-08Z.md` and also prints "started". The stop stays in force, but every agent-session is shown only B's file: A's evidence is not shown, and B is the coordinating agent-seat, while A has told the user by push notification that it started the stop, and the hook refuses A's pushes. A's file stays in the folder, unlifted; only the newest stop file counts, so A's file is never in force again.
   - An addition after a lift. B's `start` reads A's stop as in force; the lift line is appended; B's evidence line is then appended after the lift line. The lift line is no longer the file's last line, so the stop is in force again, although the agent-session that lifted it reported it lifted.
   - Both cases were reproduced on 2026-11-14 against main at 5afe37612, with the first read of the folder replaced by a stale answer rather than by two real concurrent invocations: `nedlern@ned-box:/home/nedlern/nedsnodes-logs/seats/prime-intellect/emergency-stop-start-append-race-reproduction-2026-11-14/`.
   - The lock design. merge-lane-2's [review](https://github.com/nedschorus/nedschorus/pull/2731#pullrequestreview-5815649863) of PR [Emergency stop: the /emergency-stop skill, its stop-file program, and the hook that shows the stop and refuses pushes and merges](https://github.com/nedschorus/nedschorus/pull/2731) graded "start and append are not serialized" as a fix-next finding, and its [review](https://github.com/nedschorus/nedschorus/pull/3599#pullrequestreview-5904401605) of PR [Emergency stop: the /emergency-stop skill, its stop-file program, and the hook that shows the stop and refuses pushes and merges, with the rulings of approval-walk items 21 to 38 (replaces 3240)](https://github.com/nedschorus/nedschorus/pull/3599), which the pull request above replaced, asked for a follow-up on the race between `start` and `append`. Under the lock design, every subcommand that writes the folder first creates a lock file in it, such as `.write.lock`, with exclusive create, keeps it from its read of the folder until its read-back, then deletes it. An invocation that finds the lock taken waits and retries for a few seconds, then reads the folder again and, as the loser, appends to the stop in force. The design needs a rule for a lock file left by an invocation that died, such as deleting one older than a minute. Whether exclusive create holds between ned-box and a Mac writing through its mount of the log-store is unverified.
   - The first alternative: change nothing until an emergency stop shows the gap, and keep both cases recorded here. No emergency stop has happened: `/home/nedlern/nedsnodes-logs/emergency-stop/` did not exist on 2026-11-14. Each case needs two invocations within the time between one invocation's read of the folder and the other's write, which is under a second on ned-box (unverified). In each case nothing is deleted, and the harm shows in the stop file and can be undone, by lifting again or by appending the hidden evidence to the file in force.
   - A second alternative, from the cold-read-fast-read of this question: no lock, but code reports each case when it happens. The hook would show every unlifted stop file newer than the newest lifted one, so A's evidence is not hidden, and `start` would read the file back after it appends and print that its line came after a lift line and put the stop back in force.
   - Recommended: the first alternative, under the project's rule in `CLAUDE.md` that a guard is added only when its failure has happened or is foreseeable within 30 days, and would lose work, stop work beyond the task that failed, or go unnoticed.
5. What does the skill do when it cannot write the stop file, for example in an agent-session on the Mac while ned-box cannot be reached? Settled, approved 2026-10-30 (part 2): the skill prints what failed, sends the push notification saying the stop could not be recorded, and the agent-seat stops only its own work; it does not retry by another route.
6. Which program sends the push notification, and what does the agent-seat do when it cannot be sent? Settled by the builder: the agent-session that runs the skill sends it with Claude Code's PushNotification tool; when it cannot be sent, the skill says so in its reply and writes that into the stop file.
7. How do the hooks of agent-sessions on the Mac read the stop file when ned-box cannot be reached? Settled, approved 2026-10-30 (part 2): the Mac hook reads `/Volumes/nedhome/nedsnodes-logs/emergency-stop/`; when that folder cannot be read it shows "emergency-stop state unknown: ned-box's log-store cannot be read" once per agent-session and lets work continue.

The stop file:

8. What is the stop file's path in the log-store, how is a lifted stop kept apart from a later stop, and how is the file kept from being moved or deleted by anything that tidies the log-store? Settled by part 1 under What is decided.
9. Is "its brief" the coordinating agent-seat's seat-brief, or a brief written for this repair, and what does "the repair" cover? Recommended: a brief written for this repair, kept in the log-store beside the stop file, since a seat-brief says nothing about the emergency. Settled by the builder, taking the recommendation: a brief written for this repair, kept beside the stop file as `<stop file name>-repair-brief.md`; "the repair" is whatever the coordinating agent-seat does to end the emergency.
10. Should the lift line be named `#emergency_stop_lifted` rather than `#lifted`? Given only `#lifted`, a fresh-reader could not tell what was lifted; `#emergency_stop_lifted` follows the snake_case of the project's other `#` lines, such as `#root_cause_not_fixed`. Recommended: yes. Settled by part 3 under What is decided: yes.

During a stop:

11. Who names the coordinating agent-seat, and what does each agent-seat do before one is named, or when the named one stops running? Until one is named, "takes work only from the coordinating agent-seat" leaves no agent-seat any work it may take; read literally, it also bars every agent-seat from taking work from the user. Settled by part 2 under What is decided.
12. What counts as running work (a command, a task, a pull request), and what does an agent-seat do when that work does not finish, or is itself what is losing or damaging work? Settled by the builder: the tool call or command already started. An agent-session finishes its current tool call and then does no more work until the coordinating agent-seat or the user gives it work. Work that is itself the damage is stopped at once: the agent-session kills its own background tasks.
13. Does "without pushing" bar only the running work's pushes, or every push until the lift, including the repair's? Does it bar merge-lane-2's merges and other writes to GitHub? What happens to finished work that was not pushed, and does pushing resume by itself after the lift? Settled, approved 2026-10-30 (part 3): every push and every merge by an agent-session is refused until the lift, except those of the agent-seat coordinating the repair, by a PreToolUse hook on `git push` and `gh pr merge`. Finished work that was not pushed stays committed locally, and pushing resumes by itself after the lift.
14. What happens to an approval-walk that is open when a stop starts, and to it after the lift? Settled, approved 2026-10-30 (part 4): it pauses, and no item is shown during the stop; after the lift the agent-seat resumes it at its `#next_to_present` item.
15. In "the walk-me-through hooks let every agent reply through", which replies are let through: an agent-session's replies to the user while an approval-walk is open, messages between agent-seats, or both? Settled by the builder: both, every reply to the user and messages between agent-seats.
16. An agent-session in the middle of a long turn, or a subagent it has dispatched, is not shown the file until a hook next runs for it. Is that acceptable, or must the stop reach running work sooner? Settled by the builder: acceptable for the first build. The stop is shown at each UserPromptSubmit and each PreToolUse, so running work sees it at its next tool call.

Lifting a stop:

17. How does the user tell the skill to lift a stop, and in which agent-session does the skill then run? May he delegate the lift to an agent-seat, as he did on 2026-10-28, and does a delegated lift count as "the user's word"? Settled by part 3 under What is decided.
18. If the user does not answer for hours after an agent-seat starts a stop on its own, for example overnight, does the stop simply last, or is he reminded? Settled, approved 2026-10-30 (part 4): the stop lasts, and a push notification reaches him at 08:00 Pacific each morning while it lasts. A scheduled job sends it, not an agent remembering to.
19. How does an agent-session learn that a stop was lifted, so that it stops following the stop's rules? Settled by the builder: the hook stops showing the file once its lift line is present, and the first hook run after the lift shows one line, "the emergency stop was lifted at <time>", once per agent-session.

The work itself:

20. Which agent-seat puts these questions to the user and records his user-rulings, which builds the skill and hooks, and does the build go through design-to-main? Recommended: agent-instructions-editor runs the approval-walk, because the skill and hooks are files the instruction-file guard protects, and the build goes through design-to-main, because this GHI-MD is an approved design. Settled under What is decided: prime-intellect builds the skill.
21. Which of questions 1 to 19 must be ruled on before the build starts? Recommended: all of them except 1 and 18, which can be sharpened after the first real stop. Settled by part 4 under What is decided: the builder settles them.
22. Until the build lands, do agent-seats follow any interim rule for a stop? Recommended: no; a stop is relayed as today, and the build is the fix. Settled by the builder, taking the recommendation: no interim rule.
23. Must the work's completion include a check that every agent-seat runs the new hooks? An agent-home can stay on an older checkout when its launch-time-git-sync cannot fast-forward it, and its agent-sessions are then never shown the stop file. Recommended: yes; the check is that each agent-home's checkout contains the merge commit. Settled by the builder, taking the recommendation: yes; the work is done when each agent-home's checkout on both machines contains the merge commit.
24. Should the name "stop" be written in full, "emergency stop", in the skill, the hooks and their messages, to keep it apart from Claude Code's Stop hook event, which the /walk-me-through hooks already use? Should the glossaries gain `/emergency-stop` (the skill) and "emergency-stop file" (the file it writes), and the SDLC-terms "incident commander" for the coordinating agent-seat and "incident response" for the repair? Recommended: yes to writing "emergency stop" in full; add `/emergency-stop` and "emergency-stop file" to the glossaries when the skill lands; no to the two SDLC-terms, since the approved text says "the agent-seat that coordinates the repair". Settled, approved 2026-10-30 (part 5): "emergency stop" is written in full in the skill, the hooks and their messages; the project glossary gains `/emergency-stop` and "emergency-stop file", worded as part 5 says, when the skill lands; neither "incident commander" nor "incident response" is used.

These are settled by the build, not by the user, and the builder settled them so:

- The hook shows the whole stop file up to 4,000 characters, and the rules agent-seats follow during a stop, every time.
- A missing folder means no stop; a file that cannot be read or parsed is shown as "emergency-stop file <path> cannot be read: <error>" and treated as a stop in force.
- Hook events: UserPromptSubmit and PreToolUse.
- Times: UTC, ISO 8601.
- The lift line counts only as the file's last line, at the start of a line the skill wrote, so words inside the user's quote cannot lift a stop.
- Only files named by the UTC time a stop started, `<YYYY-MM-DDTHH-MM-SSZ>.md`, are stop files, so the repair brief beside one is never read as the newest stop.
- An agent-session's agent-seat is the `GIT_AUTHOR_NAME` the launchers export, and the stop file names the coordinating agent-seat the same way; the push-and-merge refusal compares the two.
- Handing the lift to a named agent-seat is recorded as its own line, `#emergency_stop_lift_handed_over <agent-seat> <your words>`, which does not lift the stop; that agent-seat's later `#emergency_stop_lifted` line does.
- Still open for the build: the 08:00 Pacific reminder needs a channel a scheduled job can use, because Claude Code's PushNotification tool exists only inside an agent-session. The first build leaves the reminder out and records how it will be sent once a channel is chosen.

The questions these answer were:

- What the hook shows: the whole file or a part of it, how large the file may grow, and whether the hook also shows the rules agent-seats follow during a stop.
- What the hook does when the file is missing, unreadable or half-written, or when the hook itself fails. A behavior the build chooses here that changes what the user sees goes to him before it is built.
- Which hook event shows the file.
- What time the file records and in which time zone.
- How the lift line is kept apart from a line beginning `#emergency_stop_lifted` inside the user's words or the evidence.

## Next action

The work is paused at the user-ruling of 2026-11-20, recorded under "Paused on 2026-11-20" above; nothing here is worked on until he says to resume it. When he does, prime-intellect puts to him, in one new approval-walk made with the /walk-me-through skill, first the open decision on how work restarts after an emergency stop. If he decides the restart is to be designed first, prime-intellect writes that design into this GHI-MD, puts it to him, and the rest waits until he approves it. Otherwise the same approval-walk goes on to item 78, as the fix for PR 3901's blocking finding, with the wording for the case where `start` created no file, and then the two approval-walk items above. prime-intellect carries out his answers, and marks PR 3901 ready for review again only after what he decides on item 78 is built. It also reruns `python3 scripts/ghi-issue-write.py create` on GHI 3075's GHI-MD, and brings the older text listed under "Other open emergency-stop work" into line.

The work is done when all of these hold:

- PR 3901 has merged; or the user has decided to close it, and its approved texts of items 55.1 to 55.6 have merged in another pull request, which prime-intellect opens, or been dropped by his decision.
- Every point under "Paused on 2026-11-20" has an answer from the user or a merged pull request, an answer that changes nothing included.
- Every agent-home's checkout on both machines contains the merge commit of PR 3605 and of each emergency-stop pull request merged under this GHI before the Outcome is written.
- The outcome is recorded in an Outcome section at the top of this GHI-MD.
