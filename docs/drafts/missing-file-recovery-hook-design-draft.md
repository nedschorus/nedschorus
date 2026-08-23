---
status: draft design, awaiting md-review; not built
design-as-of: 2026-08-23
---

# Missing-file recovery — the failure hook and the four-surface search (design)

When an agent in this fleet tries to open a file that is not there, nothing today tells it where the file went. This design makes the harness answer that question automatically: a hook fires on the failed call, a script searches every history the fleet keeps, and the answer arrives beside the error while the agent is still looking at it. The script half is built ([find-deleted-path-across-backups.py](../../scripts/find-deleted-path-across-backups.py), PR nedschorus#146); the hook half is designed here and unbuilt.

Every cost and capability below was measured on 2026-08-23 rather than assumed, and two widely-repeated claims about Time Machine were disproved in the process — see [Measured facts](#measured-facts-this-design-rests-on).

## The failure this fixes

On 2026-08-23 an agent followed a citation in [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) to `md-review-records/2026-08-11-ghi-info-agent-design/dispositions.md`, found nothing, and built the ghi-info ask tool without the eleven deferred review findings that file held. Five of the eleven then cost review rounds in the build. The path had been deleted on 2026-08-14 in commit `ab541cc` when review records were retired, and the citation carried no `git show <sha>` recovery pointer.

Three details make this the design's shape rather than just its motivation:

1. **The content was never lost.** It is in git, in thirteen agent transcripts across both machines, in eleven Timeshift snapshots, and in Time Machine. All four were confirmed by running the script against that exact path.
2. **The agent did reach for git — and git is the one surface agents get wrong.** For a deleted path, `git log -- <path>` returns nothing, because history simplification prunes commits that do not affect the current tree. It needs `--all --full-history`, and then the newest commit touching the path is normally the one that *deleted* it, whose tree no longer holds the content, so `git show <sha>:<path>` fails too. Recovery requires walking back until a tree actually contains the blob.
3. **There was no moment of giving up.** The agent read the citation, saw nothing, and kept building. No decision to abandon the search was ever taken, which is why instruction-style fixes ("try harder", "remember to check backups") cannot reach this failure. Nothing was there to remind.

A written convention was considered and rejected as the primary fix. This project has already recorded that layer failing — [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) is described in its own records as "this project's record of a written convention losing to trained habit", and [46-ghi-info-agent-design.md](../issues/46-ghi-info-agent-design.md) demotes CLAUDE.md to ambient documentation. A hook does not need to be remembered by the agent that needs it.

## The four surfaces

| surface | what it is | how it is searched | cost | privilege |
|---|---|---|---|---|
| **git** | this repository's full history, all refs | one query, then a walk back to a commit whose tree holds the blob | **95 ms** to ask, **70 ms** to recover | none |
| **Timeshift** | snapshots on ned-box, `/mnt/backup/timeshift/snapshots` | snapshots are ordinary directories — test the path inside each of 133 | **1.3 s** over ssh | none |
| **transcripts** | agent session JSONL under `~/.claude/projects`, **both machines** | grep 530 files | **4.2 s** | none |
| **Time Machine** | APFS snapshots on the Mac's backup disk | see below — not like the others | **160 ms** to enumerate; **8.4 s** to mount; free to read once mounted | root to mount only |

Transcripts deserve their place: a transcript holds what a tool call returned, so a file any agent read survives there verbatim. It is the only surface that survives a repository history rewrite.

## Time Machine, specifically

Time Machine is the surface people get wrong, including two claims this project repeated until they were tested. Both are false:

- **"Reading a Time Machine snapshot needs root."** It does not. Reading inside a mounted snapshot needs no privilege at all. So does unmounting (`diskutil unmount` succeeds as an ordinary user). Root is required for exactly one operation: `mount_apfs`.
- **"Backup content is protected by Full Disk Access."** It is not. The appearance of protection came from the `<date>.previous` trees on the live volume, which are **sparse remnants** — one inspected tree contained only `Library` under the user's home, so `Projects` returned "No such file or directory" because it genuinely was not there. `sudo` fails identically, which is the tell. **No Full Disk Access grant is needed, and none should be requested** — it is a broad read-write permission over the whole machine and this design does not require it.

What is actually true:

- The backup **disk** may fail to automount when plugged in. Remounting it is `diskutil mount "<volume name>"` and works **unprivileged**, so the script does it silently.
- The **complete** backup tree is the `<date>.backup` directory *inside* a mounted snapshot. Its `Data/Users/<user>/` holds the full home directory.
- **One mount exposes the whole history.** A mounted snapshot's root holds 91 dated trees. There is never a need to mount per backup, and a "search backwards through snapshots" is not what happens.
- A **failed** mount is cleanly distinguishable: exit 66, `mount_apfs: volume could not be mounted: No such file or directory`. Attempting to mount an already-mounted snapshot gives `Resource busy`.
- **Device nodes must be resolved at runtime** from the destination name reported by `tmutil destinationinfo`. `/dev/disk5s2` was the backup volume on 2026-08-23; a replug renumbers it.
- The live volume's retained dates are thinned — on 2026-08-23 they jumped from 2026-07-27 to 2026-08-23 — so a file deleted on 2026-08-14 is genuinely unreachable without mounting an older snapshot.

End to end, with the 2026-08-13 snapshot mounted read-only, the file deleted on 2026-08-14 was read back unprivileged: 109 lines, byte-identical to what git returns.

## What fires the hook

The event is **`PostToolUseFailure`**, not `PostToolUse`: a missing path is a *failed* call. This was probed on 2026-08-23 because the event's payload had never been captured in this fleet, and both unknowns resolved favourably:

- It fires for a **Read** tool miss **and** for a **Bash** command that exits nonzero. The Bash case is essential here, because under bypass permissions agents are instructed to read files with `cat` and `sed` rather than the Read tool — a Read-only hook would miss the way this fleet actually reads.
- The payload carries `tool_name`, `tool_input`, `error`, `cwd`, `session_id` and `transcript_path`. For a Read failure the path arrives directly as `tool_input.file_path`. For a Bash failure it must be parsed out of `error`.

Because the event fires on **every** nonzero exit — `grep` finding nothing, `test -f` on a missing file, `git diff --quiet` signalling changes — the hook must filter or it runs constantly. A census of 486 transcripts found 66 missing-file failures across 27 distinct error shapes, and most are not lost files at all: existence probes (`ls AGENTS.md`, `ls .walk-approved`), a mistyped `cd`, and missing *programs* (`env: python3`).

Two filters, in order, both free:

1. **Signature.** The error contains `No such file or directory` or `File does not exist`. Everything else exits immediately. The census showed this substring appears in nearly every shape regardless of program — `ls:`, `cat:`, `wc:`, `cd:`, `env:`, `git fatal:`, Python's `FileNotFoundError` — so it is a substring test, not a per-program list.
2. **Transient paths.** Skip `/tmp`, the session scratchpad, `node_modules`, `.git` internals, build output. A missing file there is expected.

An earlier proposal added a third filter reading the *command's intent* — skip `ls`, `test`, `cd`. It was measured and **rejected**: of 8 cases it would have fired on, roughly 3 were real losses, and it missed shapes whose wording did not match its patterns (`bash: line 1: cd:`, `python3: can't open file`). A proposal to gate on "has git ever tracked this path" was also **rejected**, for a better reason: three of the four surfaces are cheap and unprivileged, so gating them saves nothing worth having.

## What the hook does when it fires

**git first, alone.** It costs 95 ms, and its answer — the last date the file existed — is what tells the Time Machine branch *which* snapshot to mount. Without it, that branch guesses and usually picks a snapshot from after the deletion.

**Then Timeshift, transcripts and Time Machine in parallel.** They are independent; concurrently they cost about 8.4 s against roughly 14 s serial. Parallelism beyond this is not needed: because one mount exposes all 91 dated trees, testing a known path across them is a `stat` per tree, not a search. It would matter only for a bare filename with unknown location, where each tree needs a `find` (about 11 s at depth 4).

**The hook never blocks.** It fires inside a failed tool call with an agent stopped behind it, and the operator is usually working in another window. So when Time Machine would need a snapshot mounted, the hook reports what the cheap surfaces found and prints the mount command rather than waiting. The willingness to wait — up to 100 seconds — belongs in the **script**, when a person runs it deliberately. Summoning the operator with a password window is an explicit flag, never the default: a password prompt appearing unbidden during someone else's work is charming once and infuriating by Thursday.

## What it hands back

**One copy, plus an agreement line.** Every copy found is checksummed and the surfaces are compared:

```
git          2026-08-12  109 lines  sha 3f2a91…
timeshift    2026-08-14  109 lines  sha 3f2a91…
timemachine  2026-08-13  109 lines  sha 3f2a91…
→ all three surfaces agree.
```

This answers the question that "return the latest three copies" was reaching for — *is this copy partial or corrupt* — which three identical blobs cannot answer. The surfaces are genuinely independent: git is content-addressed, Timeshift is an rsync tree, Time Machine is an APFS clone. Agreement across them is strong evidence. **Variants are shown, with timestamps and sizes, only when the checksums disagree** — which is exactly when there is something to decide.

### The honesty contract

Every surface reports one of three outcomes, and the last two are never conflated:

- **FOUND** — with the exact command that recovers the content.
- **NOT FOUND** — this surface was genuinely searched and does not have it.
- **UNAVAILABLE** — this surface could not be searched, with the reason and the command that would fix it.

An agent told "not found" stops looking; an agent told "Time Machine needs a snapshot mounted, here is the command" asks for it. A surface that cannot be read must never render as empty.

### Transcripts report three states, not one

Transcripts match on the path *string*, and an agent searching for a file has usually just typed that path — so its own session always matches. Observed in testing: a lone hit that was the searching session quoting the filename. Reporting that as "found in 1 transcript" reads as recovery and is not. So:

- **content likely present** — the path appears alongside a large body of text, the shape of a tool result that read the file;
- **mentioned only** — the name appears, with no content near it;
- **the searcher's own session** — excluded entirely, by session id.

## Path resolution

The same file has several names, and getting this wrong is already a live defect: two findings on PR nedschorus#146 are exactly this — the documented absolute-path form makes git report NOT FOUND with a confidently false message, and a dotfile fragment can return a FOUND pointing at an unrelated file.

The rules, made possible by the payload carrying `cwd`:

- Resolve a relative path against the failing call's `cwd`; expand `~` against the home directory.
- Keep **two forms** and use each where it belongs: the **repo-relative** form for git, which understands only pathspecs, and the **absolute** form for filesystem backups.
- **Re-anchor across machines.** `/Users/el/agents/mac-ubuntu-bridge/X` on the Mac is `/home/nedlern/Projects/nedschorus/X` on ned-box, and the same relative path exists under several seat directories there.
- Match fragments at **path-component boundaries** only, so `notes.md` does not match `my-notes.md`.

## Where a model is used, and where it is not

The triage above is arithmetic — a size comparison and a string equality — so it is plain Python. A model would add latency, cost and nondeterminism to questions arithmetic already answers, in a tool whose entire contract is an honest, reproducible report.

One case is genuine judgment and is held in reserve: a **fragment search returning several differently-named candidate paths**, where something must decide which file was meant. A small fast model is appropriate there. It is built only if that case appears in real use, not in advance.

## Test plan

Two different things are tested, with separate corpora and separate verdicts. Conflating them yields a green suite that proves nothing: a perfect searcher behind a trigger that never fires is useless, and the reverse is noise.

**1. The trigger — does the hook fire on the right failures?**
Corpus: the 66 real missing-file error lines already extracted from 486 transcripts. Small enough to hand-label honestly, and it is real traffic rather than invented cases. **Measures false positives.**

**2. The search — given a path, is the content found?**
Corpus: the **294 distinct paths git has ever deleted** in this repository. Every one is a known real loss whose content git demonstrably still holds, so any `NOT FOUND` is a definite false negative **with no labelling required**. Ground truth is built in; this is the strongest test available.

Two further corpora:

- **Synthetic injection** — copy a file, hash it, delete the copy, run the finder, assert byte-identical recovery. Exercises the whole chain including the backup surfaces, and is repeatable rather than history-dependent.
- **Timeshift differential** — files present in an old box snapshot and absent now: real losses with known recoverability, exercising the box surface instead of using git as both question and answer.

## Deliberately not in version 1

- **A CLAUDE.md note.** Considered and ruled out: the hook executes rather than advises, and this project has watched the written-convention layer lose to trained habit before.
- **Blocking the agent to wait for a password.** The hook prints the command; the script waits when a person runs it.
- **A Full Disk Access grant.** Shown unnecessary. It would be a broad read-write permission over the whole machine.
- **Parallel mounting of multiple snapshots.** One mount exposes the whole history.
- **The model-based fragment disambiguator.** Held in reserve; built only if real use produces the ambiguity.

## Verify at build

- `PostToolUseFailure` fires and injects for both a Read miss and a nonzero Bash exit **in a real session**, not only in the probe harness.
- The hook adds no measurable latency to failures it declines — the signature test must exit before any git or ssh call.
- The two corpora above run as a suite and report false positives and false negatives separately.
- A surface that cannot be searched renders as UNAVAILABLE, never NOT FOUND, for every input form the tool documents: repo-relative, absolute, and fragment.
- Nothing writes to backup state. The only privileged call is `mount_apfs`, and the only state changes are a read-only mount and its unmount.

## Measured facts this design rests on

All measured 2026-08-23 on this Mac and ned-box; re-measure after a macOS upgrade or a Claude Code upgrade.

| fact | value | how it was established |
|---|---|---|
| `PostToolUseFailure` fires for Read misses and nonzero Bash exits | yes, both | probe hook via `claude --settings '<json>'`, payloads captured |
| payload carries the path | `tool_input.file_path` (Read); parsed from `error` (Bash) | same probe |
| missing-file failures in the field | 66 across 486 transcripts, 27 error shapes | census over `~/.claude/projects` |
| dominant error substring | `No such file or directory`, across all programs | same census |
| git query / recovery | 95 ms / 70 ms | timed |
| Timeshift, 133 snapshots | 1.3 s, unprivileged | timed |
| transcripts, 530 files, both machines | 4.2 s | timed |
| Time Machine snapshot mount | 8.4 s, root | timed in a terminal window |
| Time Machine read once mounted | unprivileged | live test |
| Time Machine unmount | unprivileged (`diskutil unmount`) | live test |
| trees exposed by one mount | 91 | live test |
| failed mount signature | exit 66, `volume could not be mounted` | live test |
| Full Disk Access required | **no** — the sparse `.previous` trees explain the apparent block | live test, `ls -la` plus `sudo` comparison |
| git-deleted paths available as ground truth | 294 distinct | `git log --all --full-history --diff-filter=D` |
