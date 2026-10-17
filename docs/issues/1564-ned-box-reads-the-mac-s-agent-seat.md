---
issue: "[ned-box reads the Mac's agent-seat task lists live, through the Mac's forced command for ned-box](https://github.com/nedschorus/nedschorus/issues/1564)"
---

# ned-box reads the Mac's agent-seat task lists live, through the Mac's forced command for ned-box

## Why

An agent on ned-box cannot read the task lists of the agent-seats that run on the Mac. `scripts/seat-task-list-read.py` reads every agent-seat's task list on both machines when it runs on the Mac, but run on ned-box it reads ned-box's lists alone and reports the Mac as "not read, because this machine has no route to it".

That gap now matters for citations. A rule the user is approving for design-to-main designs lets a deferred line name the event it waits on, and one kind of event is another agent-seat's task, cited by agent-seat, number and subject and found with `scripts/seat-task-list-read.py`. An agent on ned-box must be able to open such a citation when the task belongs to a Mac agent-seat.

The copy of the Mac's task lists that `scripts/transcript-mirror-to-log-store.py` keeps on ned-box, `/home/nedlern/nedschorus-logs/transcripts/mac/tasks/`, is not the answer: the user asked for the task lists themselves, not a copy, so that a citation shows a task as it stands.

## What exists

ned-box already has one constrained route into the Mac. ned-box's key `~/.ssh/id_ed25519_mac_side_action` is admitted by the Mac's `~/.ssh/authorized_keys` for one forced command only, `scripts/mac-request-from-ned-box-forced-command.py`, which accepts only the requests its docstring lists (open a window, open an agent-seat's window, open a file in Typora, open a page in the browser), logs every request, and refuses everything else. `scripts/open-mac-window-from-ned-box.py` sends those requests from ned-box, with that key, the Mac's address and a ten-second connection timeout.

On the Mac, `scripts/seat-task-list-read.py` already reads ned-box's lists as one tar stream over ssh (`tar -C "$HOME/.claude/tasks" -cf - .`) and checks that the archive is complete before trusting it.

## The change

1. The forced command accepts one more request, `read-agent-seat-task-lists`, with no words after it.
   - It logs the request as accepted before it reads anything, and logs the outcome after.
   - When `~/.claude/tasks` is missing, it refuses with an exit status of its own.
   - Otherwise it runs tar on `~/.claude/tasks`, with the Mac's extended-attribute files turned off, and writes the archive, and nothing else, to standard output; every message goes to standard error.
   - Each outcome has its own exit status, distinct from the refusal status: archive sent, task store missing, tar failed. It writes nothing on the Mac apart from its request log, and runs nothing but tar.
2. `scripts/seat-task-list-read.py`, run on ned-box, reads the Mac by sending that request through the ssh command and Mac address that `scripts/open-mac-window-from-ned-box.py` builds, imported from that program, not copied, and unpacks the archive with the checks it already applies to ned-box's archive.
   - Each failure is reported with what to do: the Mac unreachable, for example asleep (ssh exits 255, explained as `scripts/open-mac-window-from-ned-box.py` explains it); the Mac refusing the request; the Mac's task store missing; tar failing; an incomplete archive.
   - A Mac that cannot be read is a failure of the run, which exits non-zero, as an unreachable ned-box already is when the program runs on the Mac. So on ned-box, a run asking for both machines exits non-zero while the Mac is asleep; `--machine ned-box` reads ned-box alone.
3. The Mac's clone must be pulled after the change merges, because the forced command runs from the Mac's own clone. Until then the Mac's older forced command refuses the request as not starting with `open-window`, and the reader says the Mac's clone needs a pull.

## Next action

Build the change on a topic branch, with tests for the new request (accepted, refused with words after it, missing task store, tar failing) and for the reader's new route (a clean read, ssh failing, the Mac refusing the request, the Mac's older forced command, a truncated archive), and open the pull request. After it merges, the user pulls the Mac's clone.

## Related

- GHI [A small HTTP service with SQLite on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972): its build-slice 5 plans for the whole-fleet view on ned-box to read the Mac's tasks from the mirror's copy; once this change lands, that view can read them live instead.
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936): its GHI-MD says the reader, run on ned-box, reads ned-box's store alone; that sentence changes when this lands.
