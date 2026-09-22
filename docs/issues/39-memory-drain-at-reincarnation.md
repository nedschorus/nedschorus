# Memory: agents write freely, and each reincarnation drains the new entries in a walk with the user

The working document of issue [Memory: agents write freely, and each reincarnation drains the new entries in a walk with the user](https://github.com/nedschorus/nedschorus/issues/39), which the issue body links to. It replaces that issue's original plan, two hooks echoing every memory read and write to the console, with the policy the user ruled on 2026-09-17 in the five-seat-briefs walk; those minutes are in the log-store, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/five-seat-briefs-cold-read-findings-2026-09-16-minutes.md`, where CLAUDE.md's log rule puts walk files. The memory-maintenance thread of issue [Runtime-behavior research bundle: instruction compression + deliberate scrub, instruction precedence, output styles, context clearing, names reviewer, memory maintenance](https://github.com/nedschorus/nedschorus/issues/29) asks the wider research question; this settles the operating rule. Agent-seat, and the `fleet` seat's ownership of hooks and session machinery, are defined in `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`; a seat's brief is the file `docs/agents/<seat>-instructions.md`.

## What the user ruled, 2026-09-17

- **Agents may write memories without asking first.** His words, on memories: "I'm fine with agents writing memories, as long as they are maintained on reincarnation."
- **Maintenance is a walk with him at each reincarnation.** "The way to do that is to walk them with me."
- **Memories are not separate per agent.** "Memories should not be separate. This makes reviews more common and easier. That should work for all agents." One store per machine, every agent writing into it, headless runs included.
- **Cadence:** every reincarnation. **Scope:** nedschorus only; the Mac's other stores, such as the 60 entries under `route-spectrum`, are untouched.

## The store

Claude Code keys a memory store to the repository root, not to the working directory: the directory name is that root's path with each `/` turned into `-`. So every worktree of this repository on a machine shares one store, and the two are `~/.claude/projects/-Users-el-Projects-nedschorus/memory/` on the Mac and `~/.claude/projects/-home-nedlern-Projects-nedschorus/memory/` on ned-box. A session in `/Users/el/agents/cold-read-research`, a worktree, writes to the first of those.

`MEMORY.md`, the index whose one-line entries are injected at session start, sits inside that same `memory/` directory. Nothing regenerates it: whoever adds or removes an entry updates its line, whether that is the agent writing the entry or the drain removing it.

Each store has a **drain marker** beside it, at `last-memory-drain.json` in the same project directory as the `memory/` folder above. It holds the timestamp of the last drain and, per entry still in the store, the drains it has survived and the reads counted against it. The drain runs on the Mac, and reads and writes ned-box's store, index and marker through `ssh nedlern@ned-box`. Entries are never copied between the two machines.

## What one drain does

1. **Fixes its boundary timestamp**, so an entry written while the walk is in progress belongs to the next drain and cannot be marked drained unwalked. No lock is needed.
2. **Counts reads.** Transcripts are filed by working directory, not by repository root, so a seat working in `~/agents/cold-read-research` writes its transcript under `~/.claude/projects/-Users-el-agents-cold-read-research/` while its memories go to the repository's store. The drain therefore scans every `~/.claude/projects/*/` directory on the machine, taking only transcripts changed since the marker's timestamp — not only the last session's — so reads by sessions that came and went between drains, headless ones included, are not lost. A read is a `Read` tool call whose path is an entry in the store, which is what ties a transcript to this repository's memories; the injected index is not a tool call and never counts, and a shell `cat` is not counted either.
3. **Lists** every entry whose file is newer than the marker's timestamp, with the session that wrote it, from the `originSessionId` its frontmatter carries; an entry without one is listed as unattributed rather than skipped.
4. **Walks** the list with the user, in the shape below.
5. **Writes both markers:** the new timestamp, the accumulated read counts, and each surviving entry's incremented survival count. A drain that shows nothing still does this, so the counts do not freeze.

**If ned-box cannot be reached,** the drain covers the machine it can reach, names the one it could not, and leaves that store's marker untouched. The counts are not lost: they are read from transcripts, which are still there when the machine comes back.

## The drain walk's shape, ruled 2026-09-17

The user's words: "the tricky part is how to make the walk efficient. I think i'd list all the previously walked and approved items first in a big list, then walk each new item." So a drain has two parts:

1. **One list of the entries already approved**, one line each — the line `MEMORY.md` already carries — with the drains it has survived and the reads counted against it. Nothing is re-decided here; the list is there so he can prune on evidence, and an entry read zero times across a dozen sessions is the case for deleting it.
2. **Then the new entries**, each with its proposed home and a recommendation: promote, keep, or delete. Where a drain has three or fewer new entries, both stores counted together, they come as one item with a recommendation each: "y" accepts all of them, and any other answer walks them one at a time. More than three are walked one at a time from the start. The session running the drain writes the recommendations; they are its judgment, not a script's.

**Retention follows from the shape:** an approved entry stays until he says otherwise. Surviving drains is not a reason to drop it; the counts are shown so he can decide.

**Each entry ends one of three ways,** carried out by the session that walked it:

- **Promoted:** that session writes the text into its real home — a CLAUDE.md line, a wiki page, or an issue — the way any change reaches that home: a repository file through a topic branch and a pull request, an issue through `ghi-write`. The entry leaves the store and the index when the promotion lands, not before. A CLAUDE.md promotion needs the instruction-file guard's `.walk-approved` marker, and this drain walk is the approval it quotes.
- **Kept** as it is.
- **Deleted**, with its index line.

## Walking a ned-box drain from the Mac

The user sits at the Mac; the seats run on ned-box. Two things follow.

**A drain is only complete when it runs from the Mac.** The Mac reaches ned-box over `ssh nedlern@ned-box`, so a Mac-side session lists and changes both stores. Nothing gives ned-box a way back to the Mac, so a drain run in a ned-box session covers ned-box's store alone and says so.

**He does not have to be on the machine that wrote an entry.** Every entry is listed with its origin session, so ned-box's entries come up in whatever session he is already talking to, and a deletion or an edit he approves there is carried out over that same SSH connection.

**When the drain he wants is inside a ned-box seat's own session**, he reaches it from the Mac the ordinary way, with `scripts/launch-claude-ubuntu <seat>`: it attaches to that seat's existing tmux session on the box rather than starting a second one, and the drain list appears in the pane he is then in. `ssh nedlern@ned-box -t 'claude agents'` lists the box's sessions when he wants to see what is running first.

## Why the console echo goes

The issue's original plan was two hooks printing a line whenever memory was read or written. That is worth little now:

- **Writes are already gated and rare.** The instruction-file guard has protected `~/.claude/projects/*/memory` since 2026-08-11, and CLAUDE.md has required the user's approval per write since 2026-08-12. The two stores hold six entries between them, and ned-box's newest is dated 2026-08-12, the day that rule landed.
- **The read path that works is the index**, because it is injected at session start. The bodies are what nobody opens, which is the user's own verdict of 2026-08-14: "Memory is almost useless… you don't know when to check it."
- **What is still invisible is whether an entry is ever read.** The transcript count above answers that, in headless runs as well as interactive ones.

## What has to change

1. `.claude/hooks/instruction-file-guard.py` stops protecting `~/.claude/projects/*/memory`, the index inside it included. A hook change, so it must be approved-by-walk; the `fleet` seat builds it.
2. CLAUDE.md's memory rule changes from approve-each-write to write-then-drain. A walked change.
3. A script does steps 1, 2, 3 and 5 of a drain for both stores. The `fleet` seat owns it, with the session machinery.
4. Every incoming session counts and lists at its start; only a session with the user at the console walks the list and writes the markers, which is what makes a headless agent's entries reviewable at all. The seat briefs say so.

## Test plan

1. **Fixture tier:** a store with two entries, one newer than the marker — the lister names only the newer one, with its origin session; an entry with no `originSessionId` is listed as unattributed.
2. **Cross-machine tier:** an entry written on ned-box appears in a drain run from the Mac; with ned-box unreachable, the run reports the Mac's entries, names ned-box as not reached, and leaves ned-box's marker unchanged.
3. **Transcript tier:** two transcripts changed since the marker, each reading one entry body, report two reads against that entry; a `cat` of an entry and the injected index report none.
4. **Marker tier:** a drain with nothing new still advances the timestamp and the survival counts.
5. **Guard tier:** after the guard change, a Write to a memory file and to its index succeeds, and a Write to CLAUDE.md is still blocked.
