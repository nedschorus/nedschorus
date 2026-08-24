---
status: draft design, in md-review; the search script is built and under review (nedschorus#146, unmerged), the hook is unbuilt
design-as-of: 2026-08-23
---

# Missing-file recovery — the failure hook and the five-surface search (design)

When an agent in this fleet tries to open a file that is not there, nothing today tells it where the file went. This design makes the harness answer that question automatically: a hook fires on the failed call, a script searches the histories this fleet keeps, and what it finds arrives beside the error while the agent is still looking at it.

The search script is written and under review as [PR nedschorus#146](https://github.com/nedschorus/nedschorus/pull/146) on branch `find-deleted-path-across-backups`; it is **not on main**, so `scripts/find-deleted-path-across-backups.py` will not resolve in a checkout of main until that PR lands. The hook is designed here and unbuilt.

Costs and capabilities stated below were measured on 2026-08-23 rather than assumed, **except** those listed under [Verify at build](#verify-at-build) and the open items at the end of [The hook, specified](#the-hook-specified). Where a figure is absent — the cost of a local-snapshot mount, for one — it was not measured, and its absence is the signal rather than an omission. Two widely-repeated claims about Time Machine were disproved while measuring — see [Measured facts](#measured-facts-this-design-rests-on).

## The failure this fixes

On 2026-08-23 an agent followed a citation in [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) to `md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md`, found nothing, and built the ghi-info ask tool without the eleven deferred review findings that file held. Five of the eleven then cost review rounds in the build. The path had been deleted on 2026-08-14 in commit `ab541cc` when review records were retired, and the citation carried no `git show <sha>` recovery pointer.

Three details make this the design's shape rather than just its motivation:

1. **The content was never lost.** It is in git, in thirteen agent transcripts across both machines, in eleven Timeshift snapshots, and in Time Machine — four of the five surfaces, each confirmed by running the script against that exact path. The fifth, local snapshots, does **not** have it: their retention does not reach back to 2026-08-14 (see below). The Time Machine confirmation required a snapshot to be mounted first, which a person did; the script read it, but did not mount it.
2. **git finds a deleted path, and then the obvious next step fails.** `git log -- <path>` does return the file's history — 8 commits for the path above, on this branch and on main — and the newest of them is the commit that *deleted* it. That commit's tree no longer holds the blob, so `git show <sha>:<path>` fails, and an agent that takes the newest commit and asks for its content is told the content is not there. Recovery requires walking back until a tree actually contains the blob. (`--all` additionally matters when a path survives only on refs unreachable from HEAD; `--full-history` when history simplification would prune the commits that touched it.)
3. **There was no moment of giving up.** The agent read the citation, saw nothing, and kept building. No decision to abandon the search was ever taken, so nothing was there to remind — which is why the fix has to fire on the failure itself rather than rely on the agent noticing it needs help.

A written convention was considered and rejected as the *primary* fix. This project has recorded that layer failing before — [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) is described in its own records as "this project's record of a written convention losing to trained habit", and [46-ghi-info-agent-design.md](../issues/46-ghi-info-agent-design.md) demotes CLAUDE.md to ambient documentation. That is evidence against relying on a note, not proof that no instruction could ever work.

**A gap this design must close, raised by PR #146's review:** the script is currently referenced nowhere outside `scripts/find-deleted-path-across-backups.py` and its own test file, so the argument "a script does not have to be remembered" is not yet true of it. The hook is what makes it true. Until the hook exists, the script needs a reference in `docs/agents/fleet-instructions.md`, where fleet tooling is named — added in the same PR that lands the script, and left in place afterwards, since a hook that fires only on tool failures still leaves a person searching by hand with nothing to find.

## The five surfaces

| surface | what it is | how it is searched | cost | privilege |
|---|---|---|---|---|
| **local snapshots** | hourly Time Machine snapshots on the Mac's **internal** disk, present whether or not the backup disk is attached | mount one read-only and test the path inside | one mount, **no privilege** | none |
| **git** | this repository's history | one query, then a walk back to a commit whose tree holds the blob | **95 ms** to ask, **70 ms** to recover | none |
| **Timeshift** | snapshots on ned-box under `/mnt/backup/timeshift/snapshots`, reached over ssh as `nedlern@ned-box` | snapshots are ordinary directories — test the path inside each of 133 | **1.3 s** | none |
| **transcripts** | agent session JSONL under `~/.claude/projects` on the Mac **and** on ned-box | grep 530 files — the Mac's 486 plus the box's | **4.2 s** | none |
| **Time Machine** | APFS snapshots on the Mac's external backup disk | see below — not like the others | **160 ms** to enumerate; **8.4 s** to mount; ordinary filesystem cost to read once mounted | root to mount only |

Transcripts earn their place for a reason none of the other four can cover: a transcript holds what a tool call *returned*, so it can hold the content of a file that was never committed and never survived to a snapshot. It is not immune to loss — output can be truncated, and transcripts are themselves deletable — but it is the only surface fed by reading rather than by storing.

## Local snapshots — the cheapest surface, and the shortest memory

macOS keeps Time Machine snapshots on the Mac's own internal disk, hourly (`AutoBackupInterval = 3600`), independent of whether the external backup disk is attached. They need **no privilege and no external disk**: `mount_apfs -o ro` against the Data volume, reading inside, and `diskutil unmount` all succeed as an ordinary user. git and the Mac-side transcripts are cheap and unprivileged too — what is distinctive here is that this is the only surface offering a **point-in-time copy of the working tree** without a password or an attached drive.

Two mechanics a builder will otherwise get wrong:

- The **Data** volume carries them. `diskutil apfs listSnapshots /` lists only `com.apple.os.update-*` snapshots for the root volume; the user-file snapshots are on `/System/Volumes/Data`, whose device comes from `diskutil info /System/Volumes/Data` — the `Device Node` line — resolved at runtime rather than remembered, for the same reason as the backup volume's. `tmutil listlocalsnapshotdates /` lists the dates.
- Their names end `.local`, distinguishing them from the `.backup` snapshots on the external destination.

**Its memory is short, and that bounds what it can be trusted for.** Retention measured 2026-08-23: 24 snapshots — 15 from that day, 5 from the day before, and two each from 27 and 28 July, with nothing at all in between. So it covers roughly the last day and a half densely and keeps a few older survivors by luck. **It would not have recovered the 2026-08-14 file this design exists for.** It is the right first place to look for something lost minutes or hours ago, and no substitute for the archive surfaces.

The four Mac-side locations this fleet works in are not excluded from it: `tmutil isexcluded` reports `~/Projects`, `~/agents`, `~/.claude` and `~/Documents` all `[Included]`. That is the extent of what was checked — it says nothing about other Mac paths, and nothing at all about ned-box, which Time Machine does not back up.

## Time Machine, specifically

Time Machine is the surface this project got wrong, including two claims it repeated until they were tested. Both are false:

- **"Reading a Time Machine snapshot needs root."** It does not. Reading inside a mounted snapshot needs no privilege, and neither does unmounting (`diskutil unmount` succeeds as an ordinary user). Root is required for one operation: `mount_apfs` **against the external backup volume**. The same binary runs unprivileged against the **internal Data volume**, which is why local snapshots need no password at all — the difference is the volume, not the command, and a builder who generalises either way gets it wrong. A hook has no terminal, so it can never satisfy an interactive password prompt.
- **"Backup content is protected by Full Disk Access."** It is not. The appearance of protection came from the `<timestamp>.previous` trees on the backup volume, which are **sparse remnants** — one inspected tree contained only `Library` under the user's home, so `Projects` returned "No such file or directory" because it genuinely was not there. `sudo` fails identically, which is the tell. **No Full Disk Access grant is needed and none should be requested.** (Full Disk Access relaxes macOS privacy controls for an application across the machine; it does not override file ownership or ACLs. It is still far broader than this design requires, which is the point.)

What is actually true, on the configuration measured:

- **"The backup volume"** below means the external Time Machine disk mounted at `/Volumes/<destination name>`, as distinct from the Mac's own boot disk.
- The backup **disk** may fail to automount when plugged in. Remounting it is `diskutil mount "<destination name>"` and works **unprivileged**, so the script does it without asking. The destination name comes from `tmutil destinationinfo`; **if that reports no destination, or more than one, the script reports the surface UNAVAILABLE and names what it found rather than guessing.**
- The **complete** backup tree is the `<timestamp>.backup` directory *inside* a mounted snapshot. Its `Data/Users/<user>/` holds that user's full home directory. Both names carry a time as well as a day — `2026-08-23-192723` — and the design keeps that precision rather than truncating it; see the bound below.
- **One mount exposes every dated tree retained in that snapshot** — 91 of them in the measured case, spanning months. So reaching many backup dates costs one mount, not one mount per date. It cannot, of course, expose backups made after the snapshot was taken.
- **Mount failures are reported, not classified.** The observed signature is exit 66 with `mount_apfs: volume could not be mounted: No such file or directory`, and an already-mounted snapshot gives `Resource busy`. Because other failures (permissions, a bad device, a busy mount point) are reachable and were not enumerated, **any nonzero exit from `mount_apfs` makes the surface UNAVAILABLE, carrying the exit code and message verbatim** — never NOT FOUND.
- **Device nodes must be resolved at runtime** from the destination name. `/dev/disk5s2` was the backup volume on 2026-08-23; a replug renumbers it.
- The backup volume's retained dates are thinned — on 2026-08-23 they jumped from 2026-07-27 to 2026-08-23 — so a file deleted on 2026-08-14 is genuinely unreachable without mounting an older snapshot.

End to end, with the 2026-08-13 snapshot mounted read-only, the file deleted on 2026-08-14 was read back unprivileged: 109 lines, byte-identical to what git returns.

## What fires the hook

The event is **`PostToolUseFailure`**, not `PostToolUse`: a missing path the caller did not tolerate is a *failed* call. (A tolerated one — `rm -f missing`, `cmd || true` — produces no failure event and is correctly invisible to this design.) The event was probed on 2026-08-23 because its payload had never been captured in this fleet, and both unknowns resolved favourably:

- It fires for a **Read** tool miss **and** for a **Bash** command that exits nonzero. The Bash case is essential here: under *bypass permissions* — the mode in which this fleet's agents run, where tool calls are not individually approved and agents are instructed to read files with `cat` and `sed` rather than the Read tool — a hook that watched only the Read tool would miss the way files are actually read.
- The payload carries `tool_name`, `tool_input`, `error`, `cwd`, `session_id` and `transcript_path`. For a Read failure the path arrives directly as `tool_input.file_path`. For a Bash failure it must be extracted from `error`.

Because the event fires on every tool call the harness records as failed, and most nonzero shell exits are ordinary, the hook must filter or it runs constantly. A census of 486 transcripts found 66 missing-file failures across 27 distinct error shapes, and most are not lost files: existence probes (`ls AGENTS.md`, `ls .walk-approved`), a mistyped `cd`, and missing *programs* (`env: python3`).

Two filters, in order, both free:

1. **Signature.** The error contains, **case-insensitively**, one of:

   | substring | produced by |
   |---|---|
   | `no such file or directory` | `ls`, `cat`, `wc`, bash `cd`, `env`, Python's `FileNotFoundError` — and zsh's `cd`, which is **lowercase**, which is why the test cannot be case-sensitive |
   | `file does not exist` | the `Read` and `Edit` tools |
   | `did not match any file` | `git add`, `git ls-files --error-unmatch` |
   | `does not exist in` | `git show <sha>:<path>` |

   Everything else exits immediately. The first row crosses programs, which is why it is a substring test rather than a per-program list; the git rows are separate because **git never emits the first string at all** — `git add docs/nope.md` says `fatal: pathspec 'docs/nope.md' did not match any files`. An earlier draft of this design listed git under the first row, which made the `pathspec` extraction pattern below unreachable. Wordings outside this table are an accepted residual, not a claim of completeness.
2. **Regenerable locations.** Skip paths inside `node_modules`, inside a `.git` directory, and inside `__pycache__`. What those share is not that they are temporary but that a command regenerates their contents — `npm install`, a recompile, objects derived from other objects — so nothing anyone wrote is lost. **That is the test, and it is what a builder applies to a directory this list does not name**; the list is the property's current membership, not the rule.

   `/tmp`, `/private/tmp` and the per-session scratchpad directory are **not** skipped. An earlier draft skipped all three under the heading *transient paths*, which tested the wrong property: where a file sits does not say whether losing it costs anything. The harness instructs every agent to write intermediate work to the scratchpad, git never tracks that work, and `tmutil isexcluded` reports the scratchpad root `[Excluded]`, so a local snapshot or a transcript holds the only copy there is. A file an agent wrote to `/tmp` proper is lost the same way. The residual cost is a search returning NOT FOUND for the sockets and probe files that also live there — the same price the rejected git-tracking gate below is judged against, and accepted for the same reason.

A missing **program** (`env: python3`) passes the signature test and is an accepted residual: the search will simply find nothing, at the cost of one git query.

An earlier proposal added a third filter reading the *command's intent* — skip `ls`, `test`, `cd`. It was measured and **rejected**, for two separate reasons. It did not remove much noise: with the filter in place, 8 failures still reached the search stage and only about 3 of them were real losses. And it discarded real losses whose wording did not match its patterns, `bash: line 1: cd:` and `python3: can't open file` among them. So it was both imprecise and lossy. A proposal to gate on "has git ever tracked this path" was also **rejected**, for a better reason: four of the five surfaces need no privilege, and the signature filter above already removes the bulk of ordinary failures on its own, so a further gate buys little. "Cheap" here means unprivileged and local-ish, not instantaneous — transcripts cost seconds, and the failed tool call stays open for them. That is the price of the design, and the filters rather than a gate are what keep it from being paid on every `grep` that finds nothing.

## What the hook does when it fires

When both filters pass, the search runs in this order:

1. **Local snapshots.** No network, no privilege, and they answer the "deleted it minutes ago" case outright.
2. **git.** Its answer bounds which Time Machine snapshot is worth mounting. When git has never heard of the path — the case transcripts exist for, a file never committed — there is no bound, and the Time Machine branch reports UNAVAILABLE naming that as the reason rather than mounting a snapshot chosen at random. **The bound is when the file was deleted, not when it was last modified** — the newest commit whose tree still holds the blob is usually older than the deletion, and using it selects a snapshot from before the last useful one. It comes from the `--diff-filter=D` commit for that path.

   **The bound is a timestamp, never a date.** A date cannot order a deletion against the snapshots taken the same day, and same-day snapshots are the normal case, not an edge: 7 of the volume's 62 backups share 2026-08-23, and local snapshot retention keeps 15 from a single day. So the bound is the commit's full committer timestamp (`git log -1 --format=%cI --diff-filter=D -- <path>`), and candidates are walked **newest-first among those predating it**.

   **One residual this exposes, which a date hid.** A commit timestamp is when the deletion was *recorded*, which is later — sometimes much later — than when the file left the disk. So the newest snapshot predating the commit can still be missing the file. The walk therefore continues to the next older candidate on a miss rather than concluding NOT FOUND on the first one, and NOT FOUND means every candidate predating the bound was tested.
3. **Timeshift, transcripts and Time Machine, concurrently** — they are independent, so they overlap rather than sum.

**The hook never mounts an external Time Machine snapshot itself.** That needs root, and a hook has no terminal to prompt on. Its Time Machine step is: search if a snapshot is *already* mounted; otherwise report UNAVAILABLE carrying the resolved `mount_apfs` command — and, when the four conditions above are met, ask through the agent and wait `ROOT_MOUNT_WAIT_SECONDS` for someone else to run it, then search if it appeared. The hook still never holds the credential and never issues the mount; what changed is that it asks and waits rather than reporting and moving on. The 8.4-second mount in the surfaces table is a cost the **script** pays when a person runs it, never the hook. The script, which does have a terminal, takes **`--prompt-for-root`**: without it the script prints the resolved `sudo mount_apfs` command and carries on; with it the script runs that command itself, so `sudo` prompts in the terminal the person is already sitting at. It is off by default and exists only on the script — a flag that opened a password window from a hook would be a window with no terminal behind it. Local snapshots are the opposite case and the hook does mount those, because that mount is unprivileged.

The failed tool call stays open while this runs. A surface that does not answer within its timeout is reported UNAVAILABLE with the timeout as the reason, so an unreachable machine cannot hold the call open. The timeouts are the script's, and the script states them rather than this document: today `SHORT_TIMEOUT_SECONDS` for ordinary commands and `LONG_TIMEOUT_SECONDS` for history walks and ssh. Naming values here would duplicate them into two places that then drift. `ROOT_MOUNT_WAIT_SECONDS` is the deliberate exception: its value is 100 because the operator ruled that number, so the document carries it as provenance the script cannot supply, and the script takes it from here rather than the reverse.

**Two different passwords, and only one of them is this design's problem.** The backup volume is encrypted — `diskutil info` reports `FileVault: Yes` — but its key lives in the keychain, so macOS mounts it without asking anyone, and `diskutil mount "<destination>"` runs unprivileged. That password never appears here. The one that does is `sudo`, for `mount_apfs` against that volume, which is the single privileged operation in the whole design. A reader who conflates the two concludes the design needs the operator to unlock a disk, and it does not.

**The hook asks for that `sudo` password, through the agent, and waits a bounded time for it.** This reverses an earlier decision that the hook never waits on a person; the reversal is deliberate, and the reason is that the alternative is silence about the one surface that still holds the file. The step runs only when all four of these hold, which is what keeps it rare:

1. every free surface has already missed;
2. `tmutil listbackups -d "<destination>"` — **unprivileged**, 62 backups on the measured volume — shows a backup whose timestamp predates the deletion. When none does, the password cannot help, and the hook says nothing rather than sending someone after it;
3. `sudo -n true` fails, meaning no credential is cached. It exits 1 without prompting, so probing costs nothing and never summons a password window by accident;
4. the search is for a known path, not a fragment.

A path git has never tracked cannot satisfy condition 2 — there is no deletion commit, so there is no bound, so no backup can be shown to predate anything. The wait and the `say` line therefore never fire for a never-committed file, which is the case transcripts and local snapshots exist to answer. That follows from the no-bound rule above, and is stated here because a builder reading only this list would not derive it.

It then resolves the full command — `sudo mount_apfs -o ro -s <snapshot> <device> <mountpoint>`, every field substituted, nothing left for a person to work out — and holds the failed tool call for `ROOT_MOUNT_WAIT_SECONDS`, **100 on the operator's ruling**. If the mount appears within that window the search completes and the note carries the recovered location. If it does not, the note is returned unchanged. **Declining costs the operator nothing**, which is why waiting is acceptable at all. The hook's own entry in `.claude/settings.json` needs an explicit `timeout` above that wait, or the harness ends the hook before the wait does; that file already uses the field.

**Two channels, because one of them can be swallowed.** The note reaches the model through `additionalContext` and is written *to the agent*, instructing it to put the command in front of the operator rather than consume it silently — the operator runs it with the CLI's `!` prefix. But an agent can read a note and move on, so the hook also speaks: one `say` line naming the seat and the file. That is the only channel here that does not depend on the agent cooperating, which is its whole justification.

**`say` is macOS-only, and on ned-box nothing should replace it.** The hook's configuration lives in `.claude/settings.json`, which is committed, so a copy of this hook can run on ned-box as well as on the Mac. The reason it stays silent there is not that Linux lacks a speech binary — it is that the box is headless and nobody sits at it. Speech addresses a person in the room, and on ned-box there is no room. So the call is guarded on a **platform check**, not on whether a binary happens to be installed: the check records the intent, where a missing binary would only record a crash.

**In version 1 the box has no BLOCKED case at all**, so the guard costs nothing. BLOCKED arises only for the Mac's external Time Machine, and Time Machine does not back up ned-box. The single route by which a box-side miss could reach the Mac's backups is the cross-machine re-anchoring described below, whose list of roots version 1 does not have. Stated here so a later reader does not mistake the box's silence for an oversight.

**When re-anchoring does land, the channel is still on the Mac** — `say` there, reached over ssh — because that is where the operator is. A future builder should not go looking for a Linux speech package.

**The assumption underneath all of this, stated so it can be found when it breaks:** the operator is at a Mac. That holds for this fleet today and it is what makes one `say` line the right second channel. It stops holding the moment a collaborator without a Mac joins — Windows especially — which is a known future direction and deliberately not version 1's problem.

Finer-grained parallelism is unnecessary for a known path: because one mount exposes every retained tree, testing a path across them is a `stat` per tree rather than a search. It would matter for a bare filename with no known directory, where every tree needs a `find`. **Version 1 does not run that fan-out** on either snapshot surface: a fragment search is answered from git, Timeshift and transcripts, and **both** Time Machine and local snapshots report UNAVAILABLE naming the fan-out as the reason. Local snapshots face the identical problem — a bare filename needs a `find` across mounted trees, not a `stat` — so they are excluded on the same grounds rather than left undefined.

## The hook, specified

Settled here so the build invents as little as possible. What remains open is named at the end — and it is more than one item, because a claim of completeness would be the same kind of unearned absolute this document has had to remove elsewhere.

### Where it lives and how it is wired

`.claude/hooks/missing-file-recovery-notice.py`, registered in `.claude/settings.json`, which already holds this project's `PreToolUse` guard hooks. Editing that file is itself guarded: `.claude/hooks/instruction-file-guard.py` blocks writes anywhere under `.claude/` unless the user has approved them item by item in a review session (this project calls that a *walk*). So landing this hook requires his approval as a separate step, and cannot be done as a side effect of the build:

```json
"PostToolUseFailure": [
  {
    "matcher": "Read|Edit|Bash",
    "hooks": [
      { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/missing-file-recovery-notice.py" }
    ]
  }
]
```

`Edit` is included because an edit against a deleted path fails the same way and is the same loss. Other tools are excluded **as a judgment, not because their failures cannot be missing files** — a `Write` into a directory that does not exist, or a `Grep` given a deleted `path`, both fail on a missing path. They are left out because their failures are dominated by other causes and the matcher is cheaper to widen later than to narrow. A future agent revisiting this is looking at a decision, not a fact.

### What it reads

From the payload, measured 2026-08-23: `tool_name`, `error`, `cwd`, `session_id`, and `tool_input` — `file_path` for `Read` and `Edit`, `command` for `Bash`. `session_id` is what excludes the running session's own transcript from the transcript surface.

### What it returns

Exit 0 always. **When it has something to say**, one JSON object on stdout:

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure",
                        "additionalContext": "<the note>"}}
```

**Silence is the default.** When no surface has the file, the hook prints nothing and exits 0. A hook that speaks on every failure becomes noise, and noise is what agents learn to skip. **One branch is exempt**, and it is the only one: when a backup predating the deletion exists but is locked behind a `sudo` password, no surface *has* the file yet the hook is not entitled to be silent — silence there is indistinguishable from "it is gone", when in fact it is reachable and nobody was told. That branch emits its note whether or not the wait succeeds. Its four conditions are what keep the exemption from swallowing the rule.

**The note carries provenance, never content.** Measured 2026-08-23: a note saying *"deleted in `ab541cc`, recover with `git show 65b382a01:<path>`"* was acted on — the agent ran the command itself and recovered the file. A note pointing at a copy the hook had already placed in a scratch directory was refused as a prompt injection, correctly, because an unexplained file appearing on disk is indistinguishable from an attack. So the note names a source the agent can verify and the command that reads it. **The hook never copies a file anywhere.**

**This is the hook's note.** The fuller table under [What it hands back](#what-it-hands-back) is what the *script* prints when a person runs it, and the `--json` mode carries the same fields for both. One line per surface that found it, plus — for the locked-backup branch alone — one BLOCKED line, which carries the resolved command and is addressed to the agent rather than describing a result:

```
missing-file recovery: <path> was deleted <timestamp> in <commit>.
  git        git show <sha>:<path>
  timeshift  scp nedlern@ned-box:<snapshot path> .
  local      mount_apfs -o ro -s <snapshot> <data-device> <mp> && cat <mp>/<path>
  sha256: git, timeshift and local agree
```

The blocked form, which is what the operator hears about:

```
missing-file recovery: <path> is not in git, timeshift, transcripts or local snapshots.
  timemachine  BLOCKED — backup <timestamp> predates the deletion and very likely holds it,
               but reading it needs root. Ask the operator to run this, then retry:
               sudo mount_apfs -o ro -s <snapshot> <device> <mountpoint>
```

**BLOCKED is a fourth outcome, and the set becomes FOUND, NOT FOUND, UNAVAILABLE, BLOCKED.** The three were an honesty contract — never report NOT FOUND for a surface that was not actually consulted — and this case does not fit any of them: the surface was not consulted, and it *could* be. Filing it as UNAVAILABLE tells the operator nothing is being asked of him, which here is false, and it is the one branch where the hook is permitted to break its silence rule and interrupt him. A state the code already branches on belongs in the contract that describes the code.

**The line between BLOCKED and UNAVAILABLE is whether the surface was attempted.** BLOCKED means it was not attempted because a named action would be needed first, and that action is carried with it, resolved to something runnable. UNAVAILABLE means it was attempted and failed, or could not be reached at all — including every nonzero `mount_apfs` exit, which stays UNAVAILABLE and never becomes BLOCKED, since a mount that was tried and failed is not waiting on anybody.

**Sequencing, the same as `--json` above and for the same reason:** the fourth outcome lands as a follow-on to PR nedschorus#146 rather than inside it. That PR is reviewing the three-outcome implementation now, and a second topic must not ride along on it.

### Fail-open, structurally

Any error inside the hook — an unparseable payload, a crashed subprocess, a missing script — exits 0 with no stdout and one line appended to `~/.claude/missing-file-recovery-notice.log`. The name avoids `injector`: this document uses *injection* for the attack an agent must be suspicious of, and the most-grepped string this design creates should not carry that sense. **A hook that can block a tool call is a hook that can wedge the fleet**, and this one has no reason to block anything. A deliberately-crashing build of it must demonstrably let the tool call through; that is a test, not an aspiration.

### How it calls the search

`scripts/find-deleted-path-across-backups.py` prints prose for a human. The hook needs machine-readable results, so the script gains a **`--json` mode** emitting one object per surface with its outcome, path, timestamp, sha256 and recovery command. The prose renderer becomes a formatter over that same structure, which stops the two disagreeing about a field they both render — it does not stop a field being added to the JSON and never surfaced in prose, so the renderer needs its own test. **Sequencing:** `--json` lands as a follow-on to PR nedschorus#146 rather than inside it, so this design is not blocked on that PR merging, but the hook is.

### Extracting the path from a Bash failure

`Read` and `Edit` hand the path over directly. `Bash` does not: it sits inside the error text, positioned differently by each program. These patterns, applied in order to each line of `error`, cover every shape the 486-transcript census produced:

| pattern | the shape it catches |
|---|---|
| `cannot access '(.+?)'` | `ls: cannot access '/x/y': No such file or directory` |
| `can't open file '(.+?)'` | `python3: can't open file '/x/y': [Errno 2] ...` |
| `No such file or directory: '(.+?)'` | `FileNotFoundError: [Errno 2] No such file or directory: '/x/y'` |
| `pathspec '(.+?)' did not match` | `fatal: pathspec 'docs/x' did not match any files` |
| `^\S+: (.+?): open: No such file` | `wc: /x/y: open: No such file or directory` |
| `cd: (.+?): [Nn]o such file or directory` | bash only: `bash: line 1: cd: /x/y: No such file or directory` |
| `no such file or directory: (.+?)$` | zsh, which puts the path **after** the message: `zsh:cd:1: no such file or directory: /x/y`. A single `cd:`-anchored pattern cannot serve both shells — against zsh it captures the line number, `1`, and the hook then searches five surfaces for a file called `1`. |
| `^\S+: (.+?): No such file or directory` | `cat: /x/y: No such file or directory` — the general last resort |

The rules around them:

- **First match wins**, in the order above, so the specific patterns run before the general one and `ls: cannot access '/x'` is not mis-read by the last row.
- **No match means silence.** The hook exits 0 without searching rather than guessing.
- **A missing program is not a missing file.** `env: python3: No such file or directory` matches the last row and yields `python3`. Discriminate on the error itself rather than on the candidate: a line beginning `env: `, or containing `command not found`, is a program lookup and is skipped before extraction. Testing the candidate instead does not work — "names no existing entry" is true of every genuinely missing file, which is the whole point.
- **Two different orderings, and they compose in this order.** Within one line, the first *pattern* that matches wins. Across a multi-line error — a Python traceback, a script failing several commands — the first *line* that yields a candidate wins, and later lines are not searched. The note names the path it searched, so a reader can see what was looked for and infer what was not.

These patterns are a build artifact with a test rather than prose to be re-derived. The corpus is the 66 census lines, but the assertion is not "the right path" for all of them — most are not lost files. Each line is labelled with one of three expected outcomes and the test asserts that: **a path** (a genuine missing-file Bash failure), **skipped** (a program lookup, or a Read/Edit failure where the path arrives in `tool_input` and no extraction happens), or **no match** (a wording outside the table, which must produce silence rather than a guess).

### Deliberately left to the build

- The **thresholds inside the transcript classifier** — how large a neighbouring block of text must count as "content likely present". No measurement exists to set them and none of the four corpora below is the right evidence: they hold error lines and git paths, not labelled transcript excerpts. So the build owes a fifth, small corpus — transcript hits hand-labelled *content present* / *mentioned only* — and the threshold is tuned against that. A number invented here would be an unmeasured claim of exactly the kind this document has had to remove.
- The **`--json` envelope**: the field names are listed above, the object's outer shape and how the four outcomes are encoded are not.
- The **root list** for cross-machine re-anchoring, below — no configuration mechanism for it exists yet.

## What it hands back

**This is the script's report to a person**, not the hook's note above. Locations and an agreement line — not a copy. Every copy found is checksummed with SHA-256 where it lies — the full digest is compared, an abbreviation is displayed — and the surfaces are compared:

```
git          2026-08-12  109 lines  sha256 3f2a91…
timeshift    2026-08-14  109 lines  sha256 3f2a91…
timemachine  2026-08-13  109 lines  sha256 3f2a91…
→ all three surfaces agree.
```

This addresses the concern behind an earlier idea of returning the latest three copies — *is this copy partial or damaged* — which three copies presented without comparison do not answer on their own.

**What agreement does and does not establish.** The surfaces store independently: git is content-addressed, Timeshift is an rsync tree, Time Machine is an APFS clone. Agreement across them is therefore strong evidence against corruption introduced *in storage or transfer*. It is not evidence about the original: all three copy from the same source, so a file that was already truncated when it was committed and backed up will agree with itself everywhere. **Variants, with timestamps and sizes, are shown when the checksums disagree** — that is when there is a version to choose between.

### The honesty contract

Every surface reports one of three outcomes, and the last two are never conflated:

- **FOUND** — with the exact command that recovers the content.
- **NOT FOUND** — this surface was genuinely searched and does not have it.
- **UNAVAILABLE** — this surface could not be searched, with the reason, and the command that would fix it *when a command would*. Some obstacles — a disconnected disk, a sleeping machine — need an action rather than a command, and the reason is then stated without one.

An agent told "not found" stops looking; an agent told "Time Machine needs a snapshot mounted, here is the command" asks for it. A surface that cannot be read must never render as empty.

**A surface with more than one location reports the honest combination.** Transcripts live on this Mac *and* on ned-box; Timeshift is reached over ssh. The rule: FOUND if any location found it; otherwise UNAVAILABLE if any location could not be searched, naming which one and stating what the searched locations returned; otherwise NOT FOUND. Without this, a run that searched the Mac and could not reach the box reports NOT FOUND — the exact dishonesty this contract exists to prevent. (The built script has this defect today: it reports the transcripts surface as NOT FOUND when the Mac was searched and ned-box was unreachable. Raised in PR nedschorus#146's review as F6.)

### Transcripts report three states, not one

Transcripts match on the path *string*, and an agent searching for a file has usually just typed that path — so its own session usually matches. Not always: path resolution converts what was typed into other forms, and an agent that typed `notes.md` against a search issued for the absolute path does not self-match at all. Observed in testing: a lone hit that was the searching session quoting the filename. Reporting that as "found in 1 transcript" reads as recovery and is not. So:

- **content likely present** — the path appears alongside a large body of text, the shape of a tool result that read the file. Reported as **FOUND**.
- **mentioned only** — the name appears, with no content near it. Reported as **NOT FOUND**, with the mentions listed underneath as leads: the surface was searched and does not hold the content, and a name turning up is worth seeing without being recovery.
- **the searcher's own session** — excluded by session id, but **only when it classifies as "mentioned only"**. That is the noise case: the agent typed the path a moment ago and its own transcript echoes it. An own-session hit carrying *content* is kept, because it is the one case this surface exists for — an agent that read a never-committed file at 10:00 and finds it gone at 11:00 has the whole tool result sitting in its own transcript, and excluding by session id alone would silently throw away the only copy in existence.

These are a refinement of what "has the content" means for a surface that can hold a filename without holding the file. They do not replace the three outcomes above; every transcript result still resolves to exactly one of them.

## Path resolution

The same file has several names, and getting this wrong is already a live defect: two defects of exactly this kind are open against the built script (PR nedschorus#146, findings F3 and F5). Given an absolute path, git reports NOT FOUND with a confidently false message, because `git cat-file` cannot address a blob by absolute path. And a dotfile fragment can return FOUND pointing at an unrelated file, because the fragment normaliser strips leading dots along with leading slashes.

The rules, made possible by the payload carrying `cwd`:

- Resolve a relative path against the failing call's `cwd`, and expand a leading `~` against **this Mac's** home directory. Nothing in the payload says which account a call ran as, so a rule keyed on that would not be implementable: a Bash call that reached the box did so inside a command string this design does not parse. Box-side paths arrive already absolute in practice, which is why this is a tolerable simplification rather than a silent one.
- Keep **two forms** and use each where it belongs: the form **relative to the repository root** for git, and the **absolute** form for filesystem backups. The reason is narrower than it looks and worth stating exactly, because a builder who tests the wrong half will conclude the rule is unnecessary: `git log` *does* accept an absolute pathspec inside the worktree (it rejects one outside, with a different message). `git show <sha>:<path>` does **not** — it takes tree-object syntax and answers an absolute path with `fatal: path '…' exists on disk, but not in '<sha>'`. Since `git show` is the command the note hands to the agent, the repository-relative form is the one that must be carried.
- **Re-anchor across machines.** `/Users/el/agents/mac-ubuntu-bridge/X` on the Mac corresponds to `/home/nedlern/Projects/nedschorus/X` on ned-box. The mapping is many-to-one in both directions and the document should not pretend otherwise: this Mac path is a git worktree, so several Mac-side checkouts map to the same box path, and the box runs one seat per directory, so the same relative path exists under several seat roots there. Every root is searched and **every hit is reported with its full path**, newest first, rather than one being chosen — a hit under a different seat is a different file and the reader must see which. The list of roots is configuration the build must introduce; it does not exist today, and hard-coding today's paths would rot at the next seat.
- Match fragments as **trailing path suffixes at component boundaries**, so `notes.md` does not match `my-notes.md`. Multiple matches are all reported, newest first.

## Where a model is used, and where it is not

The transcript triage described above — is there a large block of text beside this match, is this our own session id — is arithmetic, so it is plain Python. A model would add latency, cost and nondeterminism to questions arithmetic answers, in a tool whose contract is an honest, reproducible report.

One case is genuine judgment and is deferred: a **fragment search returning several differently-named candidate paths**, where something must decide which was meant. Version 1's answer is to report them all rather than choose. A small fast model is appropriate there and is built only if real use shows the ambiguity is common enough to be worth it.

## Test plan

Two different things are tested, with separate corpora and separate verdicts. Conflating them yields a green suite that proves nothing: a perfect searcher behind a trigger that never fires is useless, and the reverse is noise.

**1. The trigger — does the hook fire on the right failures?**
Corpus: the 66 real missing-file error lines already extracted from 486 transcripts. Small enough to hand-label honestly, and it is real traffic rather than invented cases. **Measures false positives.**

**2. The search — given a path, is the content found?**
Corpus: the **294 distinct paths git has ever deleted** in this repository, unfiltered — and the reason not to filter is the interesting part. An earlier draft proposed removing renames and re-adds on the grounds that a `NOT FOUND` on them is correct. That is backwards. This design recovers by walking back until a tree holds the blob, and for a rename, a re-add or a deliberate removal **the old blob is still in history**, so the correct answer for every one of the 294 is FOUND. A `NOT FOUND` on any of them means the walk is broken — so the paths the filter would have removed are precisely the ones that catch the core mechanism failing. The corpus needs no labelling because its expected answer is uniform.

Two limits, stated because the corpus is easy to overclaim:

- **It establishes the git surface only.** Finding content in git's history says nothing about whether Timeshift, local snapshots, Time Machine or transcripts would have found it. The other surfaces get their coverage from the Timeshift differential and the per-surface synthetic tests below.
- **It shares provenance with what it tests.** The corpus is produced by the same history queries the search uses, so a mistake in how history is queried could yield a corpus that agrees with itself. That is the reason the other corpora must not also be git-derived.

Two further corpora:

- **Synthetic injection**, scoped per surface by how fast that surface ingests. The naive form — copy a file, delete it, expect recovery — cannot work: a file created and deleted minutes later is in no history at all, so the finder correctly reports nothing and the test proves nothing. The file must enter a history first, and how long that takes differs:
  - **git** — commit it, delete it, assert byte-identical recovery. Seconds; belongs in the ordinary suite.
  - **local snapshots** — the same cycle after one hourly snapshot. A slow test, not a CI test.
  - **Timeshift** — the same, after one 10-minute box snapshot. Slow test.
  - **Time Machine** — needs a backup run to complete, which is hours. **Not a CI test**, which is a scheduling constraint rather than an automation barrier; the fleet already runs long-latency work on a schedule. Its trigger is the same one the measured-facts table names: run it after a macOS upgrade, and whenever the Time Machine branch is changed.
- **Timeshift differential** — files present in an old box snapshot and absent now. This escapes git's circularity but reproduces the same shape one surface over: a corpus drawn from Timeshift, tested against Timeshift, agrees with itself if snapshot enumeration is systematically wrong. It is only worth running if each candidate's recoverability is confirmed against a *different* surface first — git or Time Machine — which is what makes it evidence rather than an echo.

## Deliberately not in version 1

- **A CLAUDE.md note as the primary fix.** The hook executes rather than advises, and this project has watched the written-convention layer lose to trained habit before.
- **Blocking the agent to wait for a password *unconditionally*.** The bounded wait above is in version 1, but only behind all four of its conditions. A hook that holds a tool call open whenever any surface might want a password is not.
- **A Full Disk Access grant.** Shown unnecessary, and broader than this design needs.
- **The `find` fan-out across every dated tree** for fragment searches on Time Machine.
- **The model-based fragment disambiguator.** Deferred; version 1 reports all candidates.

## Verify at build

These are **not** established by the measurements below; they are what the build must show.

- The Bash path-extraction patterns extract the right path for all 66 census lines.
- A deliberately-crashing build of the hook lets the failed tool call through unchanged.
- The signature test exits before any git or ssh call on a non-matching failure — checkable directly, without a latency threshold to argue about.
- The trigger and search corpora run as one suite that reports false positives and false negatives **separately**.
- A surface that cannot be searched renders as UNAVAILABLE, never NOT FOUND, for every input form the tool accepts: repository-relative, absolute, and fragment.
- Nothing writes to backup state. The state changes are: `diskutil mount` of the backup volume (an ordinary mount of a disk the user attached), a read-only snapshot mount, and its unmount.
- **Whether `diskutil mount` of the destination starts a backup.** Auto-backup is on and hourly, and mounting a destination macOS has been waiting for is a plausible trigger; a backup writes backup state, runs for hours, and holds the volume busy. This was not measured and the claim above is not closed until it is. If it does trigger one, the silent auto-mount is the wrong default and becomes an explicit flag.

## Measured facts this design rests on

All measured 2026-08-23 on this Mac and ned-box; re-measure after a macOS or Claude Code upgrade. Rows whose method reads "timed" or "live test" record a single observation on a warm system and name no repeatable command — they are order-of-magnitude evidence, not benchmarks, and a re-measurement will not be strictly comparable. Making them comparable means writing the timing harness the build does not yet have.

| fact | value | how it was established |
|---|---|---|
| `PostToolUseFailure` fires for Read misses and nonzero Bash exits | yes, both | probe hook registered via `claude --settings <file>`, payloads captured to a log |
| payload carries the path | `tool_input.file_path` (Read); in `error` (Bash) | same probe |
| missing-file failures in the field | 66 across 486 transcripts, 27 error shapes | census of `is_error` tool results under `~/.claude/projects` |
| dominant error substring | `No such file or directory`, across all programs | same census |
| git query / recovery | 95 ms / 70 ms | timed |
| Timeshift, 133 snapshots | 1.3 s, unprivileged | timed |
| transcripts, 530 files, both machines | 4.2 s | timed |
| Time Machine snapshot mount | 8.4 s, root | timed in a terminal window |
| Time Machine read once mounted | unprivileged | live test |
| Time Machine unmount | unprivileged (`diskutil unmount`) | live test |
| dated trees exposed by one mount | 91 | live test |
| observed failed-mount signature | exit 66, `volume could not be mounted` | live test |
| backup destination is encrypted, and unlocks without a prompt | `FileVault: Yes`, volume mounted with nothing typed — the key is in the keychain | `tmutil destinationinfo`, then `diskutil info "My Passport for Mac"` |
| backup dates and times enumerable without root | 62 backups, `2025-11-13-103029` .. `2026-08-23-192723` | `tmutil listbackups -d "<destination>"` as uid 501, exit 0 |
| the paths `listbackups` prints are names, not mounts | reading one gives `No such file or directory`, and nothing mounts | `ls` on the returned `/Volumes/.timemachine/...` path as uid 501 |
| a cached root credential can be probed without prompting | `sudo -n true` exits 1, prints `a password is required`, opens no window | run as uid 501 |
| backups sharing a single calendar date | 7 on 2026-08-23, of 62 across 56 distinct dates | same `listbackups` output |
| why a date cannot name a snapshot | up to 15 candidates share one day (local snapshots), up to 7 (external backups) | the retention row above and the `listbackups` count |
| Full Disk Access required | **no** — sparse `.previous` trees explain the apparent block | `ls -la` on the tree, plus the same read under `sudo` |
| local snapshots mount, read and unmount | all three unprivileged | `mount_apfs -o ro` against the Data volume as the ordinary user, read `CLAUDE.md`, `diskutil unmount` |
| local snapshot retention | 24 kept: 15 same-day, 5 previous day, 2 each on 2026-07-27 and 07-28, nothing between | `tmutil listlocalsnapshotdates /` |
| Time Machine backup interval | hourly (`AutoBackupInterval = 3600`), `AutoBackup = 1` | `defaults read /Library/Preferences/com.apple.TimeMachine.plist`, readable unprivileged |
| fleet paths excluded from backup | `~/Projects`, `~/agents`, `~/.claude`, `~/Documents` all `[Included]`; **the scratchpad root `/private/tmp/claude-501` is `[Excluded]`** while `/private/tmp` itself is `[Included]` | `tmutil isexcluded` |
| scratchpad content inside a local snapshot | 35,150 files under `/private/tmp/claude-501` — so the exclusion above does not reach local snapshots | `find` inside snapshot `com.apple.TimeMachine.2026-08-23-192233.local`, mounted `mount_apfs -o ro` as the ordinary user |
| failures whose path is in `/tmp` or a scratchpad | 8 of 34 | census of short (≤400 char) `is_error` results matching filter 1 across 552 transcripts, 2026-08-23 — a stricter cut than the 66/486 census above, not a restatement of it |
| macOS version these hold for | 26.5 | `sw_vers` |
| a hook's `additionalContext` reaches the model on `PostToolUseFailure` | yes — quoted back verbatim, delivered next to the tool result | probe hook returning `hookSpecificOutput.additionalContext`, `claude -p` asked to quote what it saw |
| a provenance-shaped note is acted on | yes — the agent ran `git show <sha>:<path>` itself and recovered the file | same probe, real repository |
| a note pointing at a pre-fetched copy is refused | yes — the agent called it a prompt injection | same probe, scratch-directory copy |
| paths git has ever deleted | 294 distinct | `git log --all --full-history --diff-filter=D --name-only --format=` piped through `sort -u` |
