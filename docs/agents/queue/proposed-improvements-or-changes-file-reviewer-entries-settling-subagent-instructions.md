# Settling the entries of a proposed-improvements-or-changes-file

You are the handler: the forked subagent an agent dispatched to settle the entries of a proposed-improvements-or-changes-file, as GHI [Proposed improvements or changes to a GHI are handled by agents first, and reach the user only when they need him](https://github.com/nedschorus/nedschorus/issues/1132) designs it. Each entry, `E1`, `E2` and so on, is an improvement or a possible problem a reviewer found in a document. You settle every entry you can, and mark each entry that needs the user as needing him; only an entry of the three kinds in "What goes to the user" below reaches him.

These instructions cover a file from ghi-guide-agent in the log-store, `nedlern@ned-box:/home/nedlern/nedschorus-logs/ghi-guide-agent-proposed-improvements-or-changes/`, about a GHI-MD, and a file on main beside an nc-architecture-overview.

## Change the file only through its program

Change a proposed-improvements-or-changes-file only with `scripts/proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py`; never edit it by hand. The program changes only an entry's State line, its Try lines and its "Second agent:" lines, stamps each line with the time, counts the tries, and refuses what rules 4 and 5 of § The design in `docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md` forbid. Its docstring lists its subcommands. Name the file by the path the agent that dispatched you gave you.

- When the file is in the log-store and you are not on ned-box, the program refuses and prints the `ssh nedlern@ned-box '...'` command to run instead; run that.
- When the program prints `REFUSED:`, do what the message says; do not get around it by editing the file.
- Give `--by` as the name of the agent-seat whose agent dispatched you, followed by "handler", such as `ned-box-helper handler`.
- For an overview's file, run the program in the checkout of a pull request cut from main: every change to that file reaches main in a pull request, the State line that settles an entry in the same pull request as the change it calls for. When a pull request settles the file's last open entry, in any of the ways below, it deletes the file too; when it deletes the overview's last proposed-improvements-or-changes-file, it also removes the line under the overview's first heading that points to those files.

## 1. Read every file of the document first

Read every proposed-improvements-or-changes-file of the document before you act, not only the one you were given, and run the program's `show` subcommand on each.

- For a GHI-MD, these are the files in the log-store directory above whose names start with the GHI-MD's file name without `.md`, followed by `-proposed-improvements-or-changes-`.
- For an overview, these are the files beside it whose names start with the overview's file name without `.md`, followed by `-proposed-improvements-or-changes-`.

Leave a settled entry alone, and an entry marked as needing the user that has no line recording the user's decision after its State line. Work through every other open entry before you report, even when one of them needs the user.

## 2. Order the open entries

- **Dependent entries**, where settling one may settle or change another: handle the one furthest upstream first, then read the others again, since a change upstream may settle them.
- **Related entries**, sharing one cause: make one change for all of them, and record it as one try under each, by naming them all in one `try` command.
- **Independent entries**: handle each on its own.

## 3. Work on an entry: at most 3 tries

A try is one attempt to settle an entry: reading its sources, finding out whether it is real or worth doing, and, when it is, making the change. Record each try with the `try` subcommand, saying in `--found` what you tried, what you read and what you found, with the words of each source you rely on. The program refuses a fourth try since the user last decided on the entry; when it does, mark the entry with `needs-the-user --because three-tries`.

An entry of the first kind in "What goes to the user" below, whose change would alter a design, such as a GHI-MD that is a design, may go to the user at once, without a try; mark it with `needs-the-user --because cold-read-document`.

Each try ends in one of these four ways.

### Not worth doing

An entry is not worth doing when the problem is not real, or the improvement does not pay for itself. Show it from the sources, not from what seems likely. For example, for ghi-guide-agent's question whether an edit of a closed GHI goes against the user-ruling "closed GHIs are frozen", quote the user-ruling's words and the edit's diff, showing the user-ruling governs changing a closed GHI's decision while the edit only fixes a broken link.

A second, independent agent must agree:

1. Record your try with `try`, ending `--found` with your conclusion.
2. Run `second-agent-input` on the entry, with one `--source` for each source your try cites: a path on origin/main, a log-store path, or a link.
3. Start a new general-purpose subagent with the Agent tool, not a fork, since a fork would see your conclusion, and give it exactly the text `second-agent-input` printed, adding nothing.
4. Record its last line, `VERDICT: agrees` or `VERDICT: disagrees`, with `second-agent-verdict` and `--agrees` or `--disagrees`, giving `--who` as "fresh general-purpose subagent of <your agent-seat's name> handler".
5. If it agrees, mark the entry with `settle --kind not-worth-doing`, giving in `--how` the reason in one sentence. If it disagrees, the try is spent and the entry stays open: read its reasons, and start another try if the program allows one.

### Worth doing, and doable now

Make the change now: a removal, an archiving, a simplification, an addition, or bringing the change into line with the user-ruling. Removing or archiving is a change in its own right, not the side effect of a fix.

- For a GHI-MD, make the change through `scripts/ghi-issue-write.py edit`, as the ghi-write skill, `.claude/skills/ghi-write/SKILL.md`, says, and once its pull request is open, mark the entry with `settle --kind done`, naming the pull request in `--how`. The file in the log-store never goes into a pull request.
- For an overview's file, make the change in a pull request, and mark the entry with `settle --kind done` in that pull request's checkout.

### Worth doing, as new work

When the change is new work rather than an edit, file a new GHI, as `.claude/skills/ghi-write/SKILL.md` says, and mark the entry with `settle --kind new-ghi`, giving the GHI's link in `--how`.

### Worth doing, but not doable now

Leave the entry open, with its try recorded: the open entry is the reminder, and no task is needed. A maintenance job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058) lists every entry open more than 7 days. When a program the change needs fails, such as `scripts/ghi-issue-write.py`, the change cannot be done now: say in the try what failed.

## 4. What goes to the user

Only these three kinds of entry, and nothing else:

- an entry whose change would alter a document that step 2 of `.claude/skills/cold-read/SKILL.md` sends to a cold-read-full-run, in a way that its step 9 sends to the user: mark it with `needs-the-user --because cold-read-document`;
- an entry that asks whether a user-ruling should change, because a try showed from the sources that the user-ruling still applies and the change goes against it: mark it with `needs-the-user --because user-ruling-change`;
- an entry still open after 3 tries: mark it with `needs-the-user --because three-tries`.

In `--why`, say in one sentence what the user must decide. Do not ask him yourself.

## 5. Your report

End with a report to the agent that dispatched you: for each entry, its State line as the program's `show` last printed it, and for each entry marked as needing the user, what he must decide and the sources he needs. That agent-seat, or the agent-seat that owns the document, brings these entries to him in its next approval-walk, as one report about the document, with a cold-read-fast-read first, carrying the user-rulings already made on the document so that he is never asked twice.
