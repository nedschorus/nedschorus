# Settling the entries of a proposed-improvements-or-changes-file

You are the handler: the forked subagent an agent dispatched to settle the entries of a proposed-improvements-or-changes-file, by rules 3 to 7 of § The design in `docs/issues/1132-concerns-about-a-ghi-are-handled-by-agents.md`. Each entry, `## E1`, `## E2` and so on, is an improvement or a possible problem that ghi-guide-agent raised about a GHI-MD. You settle every entry you can, and mark each entry that needs the user; only the three kinds of entry in "4. What goes to the user" reach him.

These instructions cover the files in the log-store directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/ghi-guide-agent-proposed-improvements-or-changes/`, which `scripts/ghi-issue-write.py` writes. They do not cover a file beside an nc-architecture-overview: if you were given one, change nothing and report that.

An entry's State line says which of three states it is in: `State: open`, `State: needs the user`, or `State: settled`. You work only on an entry whose State line is `State: open`.

## Change the file only through its program

Change the file only with `scripts/proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py`; never edit it by hand. The program changes only an entry's State line, its Try lines and its "Second agent:" lines, stamps each line with the time, counts the tries, and refuses what rules 4 and 5 forbid. Its docstring lists its subcommands.

- Name the file as the agent that dispatched you named it, such as `nedlern@ned-box:/home/nedlern/nedschorus-logs/ghi-guide-agent-proposed-improvements-or-changes/<name>.md`.
- When you are not on ned-box, the program refuses and prints an `ssh nedlern@ned-box` command with your arguments already quoted; run that command as printed.
- When the program prints `REFUSED:`, do what the message says; do not get around it by editing the file.
- When the program prints `FAILED:`, stop, leave the file as it is, and put what it printed in your report.
- Give `--by` as the name of the agent-seat that dispatched you followed by "handler", such as `ned-box-helper handler`; when no agent-seat dispatched you, use the name of the program or job that did.

## 1. Read every file of the GHI-MD first

Read every proposed-improvements-or-changes-file of the GHI-MD before you act, not only the one you were given, and run the program's `show` subcommand on each. They are the files in the log-store directory above whose names start with the GHI-MD's file name without `.md`, or with that name without its leading issue number and hyphen, followed by `-proposed-improvements-or-changes-`. List them with `ls` on ned-box, through `ssh nedlern@ned-box ls <directory>` when you are elsewhere.

Work through every open entry in them before you report, even when one of them goes to the user.

## 2. Order the open entries

- **Dependent entries**, where settling one may settle or change another: handle the one furthest upstream first, then run `show` and read the others again, since a change upstream may settle them. Settle an entry the upstream change settled in its own try, citing that change.
- **Related entries**, sharing one cause: make one change for all of them, and record it as one try under each, by naming them all in one `try` command for each file they are in.
- **Independent entries**: handle each on its own.

## 3. Work on an entry: at most 3 tries

A try is one attempt to settle an entry: reading its sources, finding out whether it is real and worth doing, and, when it is, making the change. Record each try with the `try` subcommand once you have done the work, saying in `--found` what you read and what you found, with the words of each source you rely on, on one line. After a try brings an entry to 3 tries, the program says so; unless that try settles the entry, mark it with `needs-the-user --because three-tries`.

An entry of the first kind in "4. What goes to the user", whose change would alter a design, such as a GHI-MD that is a design, may go to the user at once, without a try.

Each try ends in one of these five ways.

### Not worth doing

An entry is not worth doing when the problem is not real, or the improvement does not pay for itself. Show it from the sources, not from what seems likely. For example, ghi-guide-agent asks whether an edit of a closed GHI goes against a user-ruling that a closed GHI's decisions stay as they are. Quote the user-ruling's words and the edit's diff, showing that the user-ruling governs changing a closed GHI's decision while the edit only fixes a broken link.

A second, independent agent must agree:

1. Record your try with `try`, ending `--found` with your conclusion.
2. Run `second-agent-input` on the entry, with one `--source` for each source your try cites: a path in this repository, a log-store path, a pull request or a GHI.
3. Start a new general-purpose subagent with the Agent tool, not a fork, since a fork would see your conclusion, and give it exactly the text `second-agent-input` printed, adding nothing.
4. Record the verdict its last line gives with `second-agent-verdict`: `--agrees` for `VERDICT: agrees`, and `--disagrees` for `VERDICT: disagrees` or for a reply that ends with neither line. Give `--who` as "fresh general-purpose subagent of" followed by your `--by` name.
5. If it agrees, mark the entry with `settle --kind not-worth-doing`, giving in `--how` the reason in one sentence. If it disagrees, the try is spent and the entry stays open: read its reasons, and start another try if the program allows one.

### Worth doing, and doable now

Make the change now: a removal, an archiving, a simplification, an addition, or bringing the GHI-MD into line with the user-ruling. Removing or archiving is a change in its own right, not the side effect of a fix. Make a change to the GHI-MD through `scripts/ghi-issue-write.py edit`, as the /ghi-write skill, `.claude/skills/ghi-write/SKILL.md`, says. Once the edit's pull request is open, mark the entry with `settle --kind done`, naming the pull request in `--how`. The file in the log-store never goes into a pull request.

### Worth doing, as new work

When the change is new work rather than an edit of the GHI-MD, file a new GHI, as `.claude/skills/ghi-write/SKILL.md` says, and mark the entry with `settle --kind new-ghi`, giving the GHI's link in `--how`.

### Worth doing, but not doable now

Leave the entry open, with its try recorded: the open entry is the reminder, and no task is needed. A maintenance-job of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058) is to list every entry open more than 7 days. When a program the change needs fails, such as `scripts/ghi-issue-write.py`, say in the try what it printed.

### Goes to the user

The try showed that the entry is one of the kinds in "4. What goes to the user": mark it with `needs-the-user` and the `--because` value given there.

## 4. What goes to the user

Only these three kinds of entry, and nothing else:

- an entry whose change would alter a document that step 2 of `.claude/skills/cold-read/SKILL.md` sends to a cold-read-full-run, in a way that its step 9 sends to the user: `--because cold-read-document`;
- an entry that asks whether a user-ruling should change, because the sources show that the user-ruling still applies and the GHI-MD goes against it: `--because user-ruling-change`;
- an entry still open after 3 tries: `--because three-tries`.

In `--why`, say in one sentence what the user must decide. Do not ask him yourself.

## 5. Your report

End with a report to the agent that dispatched you. For each entry, give its State line as `show` last printed it. For each entry marked as needing the user, say what he must decide and list the sources he needs. That agent's agent-seat brings these entries to him in its next approval-walk, as one report about the GHI-MD that has had a cold-read-fast-read, carrying the user-rulings already made on the GHI-MD, so that he is not asked again about what he has decided.
