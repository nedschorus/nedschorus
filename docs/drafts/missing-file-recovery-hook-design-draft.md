---
status: draft design, in md-review; the search script is built and under review (nedschorus#146, unmerged), the hook is unbuilt
design-as-of: 2026-08-23
---

# Missing-file recovery — the failure hook and the four-surface search (design)

When an agent in this fleet tries to open a file that is not there, nothing today tells it where the file went. This design makes the harness answer that question automatically: a hook fires on the failed call, a script searches the histories this fleet keeps, and what it finds arrives beside the error while the agent is still looking at it.

The search script is written and under review as [PR nedschorus#146](https://github.com/nedschorus/nedschorus/pull/146) on branch `find-deleted-path-across-backups`; it is **not on main**, so `scripts/find-deleted-path-across-backups.py` will not resolve in a checkout of main until that PR lands. The hook is designed here and unbuilt.

Costs and capabilities stated below were measured on 2026-08-23 rather than assumed, **except** those listed under [Verify at build](#verify-at-build), which names what is not yet established. Two widely-repeated claims about Time Machine were disproved while measuring — see [Measured facts](#measured-facts-this-design-rests-on).

## The failure this fixes

On 2026-08-23 an agent followed a citation in [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) to `md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md`, found nothing, and built the ghi-info ask tool without the eleven deferred review findings that file held. Five of the eleven then cost review rounds in the build. The path had been deleted on 2026-08-14 in commit `ab541cc` when review records were retired, and the citation carried no `git show <sha>` recovery pointer.

Three details make this the design's shape rather than just its motivation:

1. **The content was never lost.** It is in git, in thirteen agent transcripts across both machines, in eleven Timeshift snapshots, and in Time Machine. All four were confirmed by running the script against that exact path.
2. **git finds a deleted path, and then the obvious next step fails.** `git log -- <path>` does return the file's history — 8 commits for the path above, on this branch and on main — and the newest of them is the commit that *deleted* it. That commit's tree no longer holds the blob, so `git show <sha>:<path>` fails, and an agent that takes the newest commit and asks for its content is told the content is not there. Recovery requires walking back until a tree actually contains the blob. (`--all` additionally matters when a path survives only on refs unreachable from HEAD; `--full-history` when history simplification would prune the commits that touched it.)
3. **There was no moment of giving up.** The agent read the citation, saw nothing, and kept building. No decision to abandon the search was ever taken, so nothing was there to remind — which is why the fix has to fire on the failure itself rather than rely on the agent noticing it needs help.

A written convention was considered and rejected as the *primary* fix. This project has recorded that layer failing before — [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) is described in its own records as "this project's record of a written convention losing to trained habit", and [46-ghi-info-agent-design.md](../issues/46-ghi-info-agent-design.md) demotes CLAUDE.md to ambient documentation. That is evidence against relying on a note, not proof that no instruction could ever work.

**A gap this design must close, raised by PR #146's review:** the script is currently referenced nowhere outside its own two files, so the argument "a script does not have to be remembered" is not yet true of it. The hook is what makes it true. Until the hook exists, the script needs a reference in `docs/agents/fleet-instructions.md`, where fleet tooling is named.

## The four surfaces

| surface | what it is | how it is searched | cost | privilege |
|---|---|---|---|---|
| **git** | this repository's history | one query, then a walk back to a commit whose tree holds the blob | **95 ms** to ask, **70 ms** to recover | none |
| **Timeshift** | snapshots on ned-box under `/mnt/backup/timeshift/snapshots`, reached over ssh as `nedlern@ned-box` | snapshots are ordinary directories — test the path inside each of 133 | **1.3 s** | none |
| **transcripts** | agent session JSONL under `~/.claude/projects` on the Mac **and** on ned-box | grep 530 files | **4.2 s** | none |
| **Time Machine** | APFS snapshots on the Mac's external backup disk | see below — not like the others | **160 ms** to enumerate; **8.4 s** to mount; ordinary filesystem cost to read once mounted | root to mount only |

Transcripts earn their place for a reason the other three cannot cover: a transcript holds what a tool call *returned*, so it can hold the content of a file that was never committed and never survived to a snapshot. It is not immune to loss — output can be truncated, and transcripts are themselves deletable — but it is the only surface fed by reading rather than by storing.

## Time Machine, specifically

Time Machine is the surface this project got wrong, including two claims it repeated until they were tested. Both are false:

- **"Reading a Time Machine snapshot needs root."** It does not. Reading inside a mounted snapshot needs no privilege, and neither does unmounting (`diskutil unmount` succeeds as an ordinary user). Root is required for one operation in the measured path: `mount_apfs`.
- **"Backup content is protected by Full Disk Access."** It is not. The appearance of protection came from the `<date>.previous` trees on the backup volume, which are **sparse remnants** — one inspected tree contained only `Library` under the user's home, so `Projects` returned "No such file or directory" because it genuinely was not there. `sudo` fails identically, which is the tell. **No Full Disk Access grant is needed and none should be requested.** (Full Disk Access relaxes macOS privacy controls for an application across the machine; it does not override file ownership or ACLs. It is still far broader than this design requires, which is the point.)

What is actually true, on the configuration measured:

- **"The backup volume"** below means the external Time Machine disk mounted at `/Volumes/<destination name>`, as distinct from the Mac's own boot disk.
- The backup **disk** may fail to automount when plugged in. Remounting it is `diskutil mount "<destination name>"` and works **unprivileged**, so the script does it without asking. The destination name comes from `tmutil destinationinfo`; **if that reports no destination, or more than one, the script reports the surface UNAVAILABLE and names what it found rather than guessing.**
- The **complete** backup tree is the `<date>.backup` directory *inside* a mounted snapshot. Its `Data/Users/<user>/` holds that user's full home directory.
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

1. **Signature.** The error contains `No such file or directory` (the shape produced by `ls`, `cat`, `wc`, `cd`, `env`, `git fatal:` and Python's `FileNotFoundError` alike) or the Read tool's `File does not exist`. Everything else exits immediately. This is a substring test rather than a per-program list because the census showed the substring crosses programs; it will still miss wordings outside those two, which is an accepted residual rather than a claim of completeness.
2. **Transient paths.** Skip paths under `/tmp` and `/private/tmp`, the per-session scratchpad directory the harness provides, `node_modules`, anything inside a `.git` directory, and `__pycache__`. A missing file in those is expected.

A missing **program** (`env: python3`) passes the signature test and is an accepted residual: the search will simply find nothing, at the cost of one git query.

An earlier proposal added a third filter reading the *command's intent* — skip `ls`, `test`, `cd`. It was measured and **rejected**: of the 8 failures that filter would have passed through to a search, roughly 3 were real losses, and it missed shapes whose wording did not match its patterns (`bash: line 1: cd:`, `python3: can't open file`). A proposal to gate on "has git ever tracked this path" was also **rejected**, for a better reason: three of the four surfaces are cheap and unprivileged, so gating them saves little.

## What the hook does when it fires

**git first, alone.** It costs 95 ms, and its answer bounds which Time Machine snapshot is worth mounting. **The bound is the date the file was deleted, not the date it was last modified** — the newest commit whose tree still holds the blob is usually older than the deletion, and using it selects a snapshot from before the last useful one. The deletion date comes from the `--diff-filter=D` commit for that path.

**Then Timeshift, transcripts and Time Machine in parallel.** They are independent, so they overlap rather than sum.

Parallelism beyond this is unnecessary for a known path: because one mount exposes every retained tree, testing a path across them is a `stat` per tree, not a search. It would matter for a bare filename with unknown location, where each tree needs a `find` — measured at about 11 s limited to four directory levels. **Version 1 does not run that fan-out**; a fragment search is answered from git, Timeshift and transcripts, and the Time Machine branch reports UNAVAILABLE with the reason.

## What it hands back

**One copy, plus an agreement line.** Every copy found is checksummed with SHA-256 — the full digest is compared, an abbreviation is displayed — and the surfaces are compared:

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

## Path resolution

The same file has several names, and getting this wrong is already a live defect: two findings on PR #146 are exactly this — the documented absolute-path form makes git report NOT FOUND with a confidently false message, and a dotfile fragment can return a FOUND pointing at an unrelated file.

The rules, made possible by the payload carrying `cwd`:

- Resolve a relative path against the failing call's `cwd`. Expand a leading `~` against the home directory **of the account the failing call ran as** — which for a box-side path is the box account, not the Mac's.
- Keep **two forms** and use each where it belongs: the form **relative to the repository root** for git — both for `git log` pathspecs and for `git show <sha>:<path>` tree-object syntax, neither of which accepts an absolute path — and the **absolute** form for filesystem backups.
- **Re-anchor across machines.** `/Users/el/agents/mac-ubuntu-bridge/X` on the Mac is `/home/nedlern/Projects/nedschorus/X` on ned-box, and the same relative path exists under several seat directories there. All configured roots are searched and **every hit is reported with its full path**, newest first, rather than one being chosen — a hit under a different seat is a different file and the reader must see which.
- Match fragments as **trailing path suffixes at component boundaries**, so `notes.md` does not match `my-notes.md`. Multiple matches are all reported, newest first.

## Where a model is used, and where it is not

The transcript triage described above — is there a large block of text beside this match, is this our own session id — is arithmetic, so it is plain Python. A model would add latency, cost and nondeterminism to questions arithmetic answers, in a tool whose contract is an honest, reproducible report.

One case is genuine judgment and is deferred: a **fragment search returning several differently-named candidate paths**, where something must decide which was meant. Version 1's answer is to report them all rather than choose. A small fast model is appropriate there and is built only if real use shows the ambiguity is common enough to be worth it.

## Deliberately not in version 1

- **A CLAUDE.md note as the primary fix.** The hook executes rather than advises, and this project has watched the written-convention layer lose to trained habit before.
- **Blocking the agent to wait for a password.** The hook prints the command; the script waits when a person runs it.
- **A Full Disk Access grant.** Shown unnecessary, and broader than this design needs.
- **The `find` fan-out across every dated tree** for fragment searches on Time Machine.
- **The model-based fragment disambiguator.** Deferred; version 1 reports all candidates.

## Verify at build

These are **not** established by the measurements below; they are what the build must show.

- `PostToolUseFailure` fires and injects its text **in a real session**, not only in the probe harness.
- The signature test exits before any git or ssh call on a non-matching failure, and the hook's added wall-clock on such a failure stays **under 50 ms**.
- The trigger and search corpora run as one suite that reports false positives and false negatives **separately**.
- A surface that cannot be searched renders as UNAVAILABLE, never NOT FOUND, for every input form the tool accepts: repository-relative, absolute, and fragment.
- Nothing writes to backup state. The state changes are: `diskutil mount` of the backup volume (an ordinary mount of a disk the user attached), a read-only snapshot mount, and its unmount.

## Measured facts this design rests on

All measured 2026-08-23 on this Mac and ned-box; re-measure after a macOS or Claude Code upgrade by re-running the commands named here.

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
| Full Disk Access required | **no** — sparse `.previous` trees explain the apparent block | `ls -la` on the tree, plus the same read under `sudo` |
| paths git has ever deleted | 294 distinct | `git log --all --full-history --diff-filter=D --name-only --format=` piped through `sort -u` |
