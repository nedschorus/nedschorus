---
issue: "[Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop](https://github.com/nedschorus/nedschorus/issues/2161)"
kind: design
---

# Build the emergency-stop skill, which writes one stop file in the log-store that every agent-session is shown until the user lifts the stop

This GHI-MD is the design of the emergency-stop skill and its hooks, filed as a GitHub issue so that the work has one record.

## Why

When something goes wrong across many agent-seats at once, the user needs one way to stop their work that every agent-seat obeys the same way, and that says who may lift the stop. Today a stop the user gives one agent-seat reaches the others only by messages that agent-seat relays, or by the user typing it into each agent-seat's window himself. On 2026-10-28 the user stopped the work of every agent-seat. Three agent-seats relayed the stop within four minutes, each with a different scope, and each copied its own version into its session-handoff; no message said who could lift the stop, and it was lifted at about 05:45Z on 2026-10-28, by merge-lane-2, to which the user had delegated the decision. This account is the one the first version of approval-walk item 7.1.2.1.1 of 38 gave the user; its text is `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/item-7-1-2-1-1-emergency-2026-10-28/item-7-1-2-1-1-emergency-with-sentence-ids.md`.

## What is decided

On 2026-10-28, at 18:10 by the walk-minutes' clock, the user approved the text quoted below, answering A (approve) to item 7.1.2.1.1 of 38 in the approval-walk agent-instructions-editor-open-decisions-2026-10-26. He approved only that text and the definition in the paragraph after it; the rest of this GHI-MD was written afterwards, by agents. Sources:

- The walk-minutes, `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, kept in the agent-home of the agent-seat agent-instructions-editor. Search them for "item 7.1.2.1.1 of 38" or for "emergency": the walk was renumbered while it ran, and before the item that became this one took the number 7.1.2.1.1, the number belonged to a different item, about PR 1878.
- The approved text as the user saw it: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/agent-instructions-editor-open-decisions-2026-10-26-item-7-1-2-1-1-of-38-new-1-2026-10-28/agent-instructions-editor-open-decisions-2026-10-26-item-7-1-2-1-1-of-38-new-1-with-sentence-ids.md`, with a fast read of it, `fast-read.md`, in the same directory.
- The item's third version, which carries the definition below; its quoted design is an earlier wording, which was revised into the approved text before the user approved it: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/item-7-1-2-1-1-v3-2026-10-28/item-7-1-2-1-1-v3-with-sentence-ids.md`.
- The item page, https://claude.ai/artifact/2xpoLtwBJZLwXq4exswoD6, which only the user can open, and which the walk rewrites in place; the two files above are the record.

The approved text, word for word:

> An emergency stop is one file in the log-store, which the emergency-stop skill writes. The user starts the skill by typing /emergency-stop, or by telling any agent-seat, in any words, to stop the fleet's work; an agent-seat starts it on its own when an emergency, as the skill defines one, is under way and it cannot stop it alone. The file holds the user's words, or the agent-seat's evidence, with the time, and, once known, the agent-seat that coordinates the repair and a link to its brief. An agent-seat that starts a stop on its own tells the user at once by a push notification. Only the user lifts a stop: until the skill, on the user's word, adds the line `#lifted <the user's words>`, a hook shows the file to every agent-session at each turn; every agent-seat lets running work finish without pushing, takes work only from the coordinating agent-seat, asks the user nothing outside the repair and shows no walk item; and the walk-me-through hooks let every agent reply through.

The item's third version also said, and the user approved with it: "The skill's first definition of an emergency is work being lost or damaged across agent-seats; the GHI leaves a sharper definition as an open question for you."

The user's words that shaped the design, in the same approval-walk on 2026-10-28, before he approved it:

- "I'm a little concerned that if things really go wrong, I won't remember the keywords to trigger it. And I'm actually okay with agents triggering it too, if something is really terribly wrong".
- "This kind of sounds like a skill. Like if I type /emergency kind of thing. ... if it's a skill, we can try to more carefully define what an emergency is, but your first pass is decent."

On 2026-10-30 at 08:28 UTC the user answered A (approve), to all four parts, item 3 of the approval-walk prime-intellect-handed-over-items-2026-10-29 (walk-minutes `nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 27; the item's text is in the walk-document beside them). The four parts he approved, word for word:

> Part 1, where the stop is kept: one file per stop, in the log-store folder `nedlern@ned-box:/home/nedlern/nedschorus-logs/emergency-stop/`, named by the UTC time it started. A stop is in force while the newest file has no lift line. Nothing else writes or tidies that folder.
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

The item's recommendation, which he approved with it, was: "approve all five parts, record them in GHI 2161, and build the skill." The builder's full answers are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/prime-intellect/emergency-stop-builder-answers-to-deferred-questions-2026-10-30.md`; the questions below carry them, those the user approved marked "approved 2026-10-30".

## Deferred-decisions

These were put to the user as the user's to decide. Questions 8, 10, 11, 17, 20 and 21 are settled by his approval of 2026-10-30 at 08:28 under What is decided; the builder settled the rest, as part 4 there says, and each now carries its answer, those that change what the user sees or must do approved by him on 2026-10-30 at 15:55. They were raised by a fast read of the approved text (record cited above), a fast read and a full cold read of this GHI-MD (`nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/emergency-stop-skill-2026-10-28/` and `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/emergency-stop-skill-2026-10-28-2/`), and, for the lift line's name, a check against `docs/nedschorus-wiki/nedschorus-how-to-choose-a-name-for-files-code-and-glossary-terms.md` whose report was not kept; question 10 carries its finding. Questions 20 to 24 come from findings of that full cold read which the rewrite did not settle, and from the names the reviewers proposed; each carried the recommendation of the agent that wrote this GHI-MD, and each now carries the answer that settles it.

When a stop starts:

1. What sharper definition of an emergency should the skill give? Today's is work being lost or damaged across agent-seats; it does not say whether that means the work of more than one agent-seat, or one piece of work several agent-seats depend on, nor how it combines with the approved text's "it cannot stop it alone". Settled, approved 2026-10-30 (part 1): work being lost or damaged, or about to be, in more than one agent-seat at once, or in one thing several agent-seats depend on, such as main, the log-store, GitHub access or a machine, which the agent-seat that sees it cannot stop by stopping its own work. The CPU stall on ned-box of 2026-10-28 qualifies; one agent-seat's failing test does not.
2. When the user's words to one agent-seat could mean a stop of every agent-seat, a stop of that agent-seat's own work, or a pause of an approval-walk, how does the agent-seat tell which he means? Settled, approved 2026-10-30 (part 1): the skill runs only when his words name more than the agent-seat he is talking to, such as "everyone", "all agents" or "the fleet", or he types /emergency-stop; otherwise the agent-seat stops its own work only. When unsure, it asks him one yes-or-no question: "Stop every agent-seat's work?"
3. Which work does a stop cover: only the work of agent-seats, or also scheduled jobs and other programs that run without an agent-session? Does it cover the subagents an agent-seat has dispatched, and Claude agents on the Mac that are not agent-seats? Settled, approved 2026-10-30 (part 1): every agent-session that loads this repository's hooks, that is agent-seats on both machines, their subagents, and Mac Claude agents in a nedschorus checkout. Scheduled jobs are not stopped and keep pushing; the skill lists in the stop file the jobs that push or merge, from `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, so the coordinating agent-seat can pause them by hand.
4. What happens when someone starts a stop while another is in force, or when two agent-seats start one at the same time? Settled by the builder: the skill writes no new file while a stop is in force; it appends the new words or evidence, with the time, to the file in force. When two start at once, the file is created with exclusive create, and the one that loses appends.
5. What does the skill do when it cannot write the stop file, for example in an agent-session on the Mac while ned-box cannot be reached? Settled, approved 2026-10-30 (part 2): the skill prints what failed, sends the push notification saying the stop could not be recorded, and the agent-seat stops only its own work; it does not retry by another route.
6. Which program sends the push notification, and what does the agent-seat do when it cannot be sent? Settled by the builder: the agent-session that runs the skill sends it with Claude Code's PushNotification tool; when it cannot be sent, the skill says so in its reply and writes that into the stop file.
7. How do the hooks of agent-sessions on the Mac read the stop file when ned-box cannot be reached? Settled, approved 2026-10-30 (part 2): the Mac hook reads `/Volumes/nedhome/nedschorus-logs/emergency-stop/`; when that folder cannot be read it shows "emergency-stop state unknown: ned-box's log-store cannot be read" once per agent-session and lets work continue.

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

prime-intellect builds the emergency-stop skill under `.claude/skills/emergency-stop/`, as the answers above say: the program that writes, appends to and lifts the stop file; the hook that shows the file to every agent-session at each UserPromptSubmit and PreToolUse until its lift line; the PreToolUse refusal of `git push` and `gh pr merge` during a stop, except the coordinating agent-seat's; the change, for a stop, to the hooks of /walk-me-through, `nc-systems/skills/walk-me-through/walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py` and `nc-systems/skills/walk-me-through/walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py`; the 08:00 Pacific reminder once a channel for it is chosen, as the open point above says; and the two glossary lines of part 5. The work is done when its pull request has merged, every agent-home's checkout on both machines contains the merge commit, and the outcome is recorded in an Outcome section at the top of this GHI-MD.
