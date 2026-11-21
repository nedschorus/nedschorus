---
issue: "[The start-agent-seat skill's founding steps: their defects, and which of them a program should do](https://github.com/nedsnodes/nedsnodes/issues/4009)"
---

# The start-agent-seat skill's founding steps: their defects, and which of them a program should do

## What is wrong

`.claude/skills/start-agent-seat/SKILL.md` tells an agent how to found a new agent-seat on ned-box: choose its name (step 1), have the user approve its seat-brief (step 2), write the first-prompt file and the approval-words file (step 3), run `scripts/launch-claude-ubuntu` (step 4), and check that the new agent-seat started (step 5). A cold-read-full-run of the skill found the defects below. The edit that run reviewed changed only the last sentences of step 2, which say how the user approves the seat-brief in Typora; every defect below is in text that edit did not change, so it was recorded in this GHI-MD instead of being fixed in that edit. The reports and the triage are in the cold-read-record `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/SKILL-start-agent-seat-2026-11-20-3`, and the first cold-read-fast-read is in `nedlern@ned-box:/home/nedlern/nedsnodes-logs/cold-read-records/SKILL-start-agent-seat-2026-11-20-2`.

Step 1, the name:

- The uniqueness check misses a stopped agent-seat on the Mac when the check runs on ned-box. Step 1 has an agent on ned-box rely on the ListAgents tool for the Mac. ListAgents lists only agent-sessions that are running now, and lists the other machine only when Remote Control is connected. A Mac agent-seat whose agent-session is not running is not in the list, so its name passes the check.
- Step 1 says nothing of a name that starts with `-`, which the launcher refuses, or of a name too long to be a file name or a tmux socket name.

Step 3, the two files:

- The first-prompt file tells the new agent-session to "Save the text below, unchanged, as `CLAUDE.local.md`". The handoff-supervisor adds a line after the file's text: "The text above this line came from the handoff-supervisor's --first-prompt-file or --first-prompt; the user did not type it." (`FIRST_PROMPT_FROM_LAUNCH_COMMAND_NOT_TYPED_BY_THE_USER_LINE` in `nn-systems/handoff/handoff-supervisor.py`). Nothing marks where the approved text ends, so an agent that obeys the instruction word for word saves that line into its seat-brief.
- The first prompt does not say to write `.walk-approved` and `CLAUDE.local.md` with the Write tool. The instruction-file guard sees only Edit, Write and NotebookEdit calls. A seat-brief written with a shell command leaves the marker unspent, and the unspent marker then approves the agent-seat's next guarded write.
- On the Mac, "write them locally" names no directory. A file named `<name>-first-prompt.md` inside a checkout is a reusable prompt to the instruction-file guard, which refuses the Write. The local copies are never removed.

Step 4, the launch:

- When `git worktree add` fails, the launcher prints "could not make … a checkout; the agent will start without project settings" and starts the agent-seat anyway (`scripts/launch-claude-ubuntu`, the `else` branch after `git worktree add`). The skill says to stop and tell the user, but by then the new agent-session is running with no project settings and no instruction-file guard.
- The skill does not cover the launcher's other failures: "a tmux session named <name> already exists" (no new agent-seat started; exit 0 (unverified)), "preparing or starting <name> on the box failed", and "could not write agent-home-marker", after which the agent-seat starts without the marker.
- "running the launcher again brings the agent-seat back" does not say which command. The step-4 command passes `--first-prompt-file`, and step 5 moves that file into the log-store, after which the handoff-supervisor refuses the missing file and the tmux session closes.

Step 5, the check:

- When the handoff-supervisor has exited, the tmux session is gone, so `tmux -L <name> capture-pane -p` has nothing to show, and the skill names no other place to look.
- The skill does not say what to do when the printed `CLAUDE.local.md` differs from the approved text.
- Nothing creates `/home/nedlern/nedsnodes-logs/seats/<name>/` before the two files are moved into it (unverified for every new name).
- The user is told to type the bare `launch-claude-ubuntu <name>` on his Mac, while step 4 gives the launcher's full path there (unverified whether `scripts/` is on the Mac's PATH).
- Five minutes of waiting is called "never appears", and the skill does not say what to do when the file appears later.

Seat-brief content, in step 2's first sentence, which the edit did not change:

- "its first job" stays in the seat-brief after the job is done, so a later agent-session of the same agent-seat may read it as current work.
- "without dates or attributions" can mean either no citation of when and where the user said his words, or no mention that he said them at all.

## Why it matters

Each of these can leave a new agent-seat running from a seat-brief the user did not approve, running without the instruction-file guard, or not running while the user is told it is. The skill is followed rarely, so an agent meets each case without practice.

## Which steps a program should do

`CLAUDE.md` says a step that needs no judgment goes in code. Question 4 of the cold-read-full-run, in `question-4-what-should-be-code-answer.md` of the first cold-read-record above, named these steps of the skill as such steps:

1. Writing the approved seat-brief into `~/agents/<name>/CLAUDE.local.md` could be done by the launcher, for example with an option such as `--seat-brief-file`, before the tmux session starts. That would remove the first-prompt relay, the `.walk-approved` copy, the step-5 wait and the comparison.
2. The launcher could exit nonzero, without starting the agent-seat, when it cannot make the agent-home a checkout.
3. A name-check program could test the name's characters and length, and `~/agents/<name>` and the tmux sockets on ned-box. Checking `~/agents/` on the Mac from ned-box would need the existing ned-box-to-Mac request channel, `scripts/mac-request-from-ned-box-forced-command.py`, to answer a new kind of request.
4. One program could detect which machine it runs on and act for it: run the right Typora opener, write the two files and copy them to ned-box when it runs on the Mac, and set `NEDSNODES_AGENT_BOX` when it runs on ned-box.
5. If change 1 is not built, the step-5 program could compare the files with `cmp`, move the two files into the log-store on success, and on a timeout print what it found and exit nonzero. Change 1 removes the need for change 5 and for the file-writing half of change 4.

GHI #2608, which moves sixteen steps of merge-lane-2's seat-brief into programs, is the same kind of work for another document.

## Next action

Ask the user which of the five program changes above to build; change 1 is the one that removes the most steps and defects. Verify each claim marked (unverified) before fixing it. Then rewrite the skill so that it calls those programs, and fix in the same pull request each defect above that the programs do not remove. Changes to the skill need the user's approval, so the rewrite goes to him in an approval-walk.
