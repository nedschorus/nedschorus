---
status: draft design, in md-review; the search script is built and under review (nedschorus#146, unmerged), the hook is unbuilt
design-as-of: 2026-08-23
---

# Missing-file recovery — the failure hook and the five-surface search (design)

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

## The five surfaces

| surface | what it is | how it is searched | cost | privilege |
|---|---|---|---|---|
| **local snapshots** | hourly Time Machine snapshots on the Mac's **internal** disk, present whether or not the backup disk is attached | mount one read-only and test the path inside | one mount, **no privilege** | none |
| **git** | this repository's history | one query, then a walk back to a commit whose tree holds the blob | **95 ms** to ask, **70 ms** to recover | none |
| **Timeshift** | snapshots on ned-box under `/mnt/backup/timeshift/snapshots`, reached over ssh as `nedlern@ned-box` | snapshots are ordinary directories — test the path inside each of 133 | **1.3 s** | none |
| **transcripts** | agent session JSONL under `~/.claude/projects` on the Mac **and** on ned-box | grep 530 files | **4.2 s** | none |
| **Time Machine** | APFS snapshots on the Mac's external backup disk | see below — not like the others | **160 ms** to enumerate; **8.4 s** to mount; ordinary filesystem cost to read once mounted | root to mount only |

Transcripts earn their place for a reason the other three cannot cover: a transcript holds what a tool call *returned*, so it can hold the content of a file that was never committed and never survived to a snapshot. It is not immune to loss — output can be truncated, and transcripts are themselves deletable — but it is the only surface fed by reading rather than by storing.

## Local snapshots — the cheapest surface, and the shortest memory

macOS keeps Time Machine snapshots on the Mac's own internal disk, hourly (`AutoBackupInterval = 3600`), independent of whether the external backup disk is attached. They are the only Mac-side surface that needs **no privilege and no external disk**: `mount_apfs -o ro` against the Data volume, reading inside, and `diskutil unmount` all succeed as an ordinary user.

Two mechanics a builder will otherwise get wrong:

- The **Data** volume carries them. `diskutil apfs listSnapshots /` lists only `com.apple.os.update-*` snapshots for the root volume; the user-file snapshots are on `/System/Volumes/Data`, whose device must be resolved at runtime. `tmutil listlocalsnapshotdates /` lists the dates.
- Their names end `.local`, distinguishing them from the `.backup` snapshots on the external destination.

**Its memory is short, and that bounds what it can be trusted for.** Retention measured 2026-08-23: 24 snapshots — 15 from that day, 5 from the day before, and two each from 27 and 28 July, with nothing at all in between. So it covers roughly the last day and a half densely and keeps a few older survivors by luck. **It would not have recovered the 2026-08-14 file this design exists for.** It is the right first place to look for something lost minutes or hours ago, and no substitute for the archive surfaces.

Nothing this fleet cares about is excluded from it: `tmutil isexcluded` reports `~/Projects`, `~/agents`, `~/.claude` and `~/Documents` all `[Included]`.

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

An earlier proposal added a third filter reading the *command's intent* — skip `ls`, `test`, `cd`. It was measured and **rejected**: of the 8 failures that filter would have passed through to a search, roughly 3 were real losses, and it missed shapes whose wording did not match its patterns (`bash: line 1: cd:`, `python3: can't open file`). A proposal to gate on "has git ever tracked this path" was also **rejected**, for a better reason: four of the five surfaces are cheap and unprivileged, so gating them saves little.

## What the hook does when it fires

When both filters pass, the search runs in this order:

1. **Local snapshots.** No network, no privilege, and they answer the "deleted it minutes ago" case outright.
2. **git.** Its answer bounds which Time Machine snapshot is worth mounting. **The bound is the date the file was deleted, not the date it was last modified** — the newest commit whose tree still holds the blob is usually older than the deletion, and using it selects a snapshot from before the last useful one. The deletion date comes from the `--diff-filter=D` commit for that path.
3. **Timeshift, transcripts and Time Machine, concurrently** — they are independent, so they overlap rather than sum.

The failed tool call stays open while this runs. A surface that does not answer within its command timeout is reported UNAVAILABLE with the timeout as the reason, so an unreachable machine cannot hold the call open.

No step waits on a person. If Time Machine needs a snapshot mounted, the report says so and gives the command rather than prompting. The willingness to wait belongs to the script, when someone runs it deliberately, and summoning the operator with a password window is an explicit flag rather than the default.

Finer-grained parallelism is unnecessary for a known path: because one mount exposes every retained tree, testing a path across them is a `stat` per tree rather than a search. It would matter for a bare filename with no known directory, where every tree needs a `find`. **Version 1 does not run that fan-out**; a fragment search is answered from git, Timeshift and transcripts, and the Time Machine branch reports UNAVAILABLE with the reason.

## The hook, specified

Settled here so the build has no interface left to invent. The one thing deliberately left open is named at the end.

### Where it lives and how it is wired

`.claude/hooks/missing-file-recovery-injector.py`, registered in `.claude/settings.json` beside the existing guards — which makes adding it a guarded change needing the user's walked approval, like every other `.claude/` edit:

```json
"PostToolUseFailure": [
  {
    "matcher": "Read|Edit|Bash",
    "hooks": [
      { "type": "command",
        "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/missing-file-recovery-injector.py" }
    ]
  }
]
```

`Edit` is included because an edit against a deleted path fails the same way and is the same loss. Other tools are excluded: their failures are not missing files.

### What it reads

From the payload, measured 2026-08-23: `tool_name`, `error`, `cwd`, `session_id`, and `tool_input` — `file_path` for `Read` and `Edit`, `command` for `Bash`. `session_id` is what excludes the running session's own transcript from the transcript surface.

### What it returns

One JSON object on stdout, exit 0:

```json
{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure",
                        "additionalContext": "<the note>"}}
```

**Silence is the default.** When no surface has the file, the hook prints nothing and exits 0. A hook that speaks on every failure becomes noise, and noise is what agents learn to skip.

**The note carries provenance, never content.** Measured 2026-08-23: a note saying *"deleted in `ab541cc`, recover with `git show 65b382a01:<path>`"* was acted on — the agent ran the command itself and recovered the file. A note pointing at a copy the hook had already placed in a scratch directory was refused as a prompt injection, correctly, because an unexplained file appearing on disk is indistinguishable from an attack. So the note names a source the agent can verify and the command that reads it. **The hook never copies a file anywhere.**

Its shape, one line per surface that found it:

```
missing-file recovery: <path> was deleted <date> in <commit>.
  git        git show <sha>:<path>
  timeshift  scp nedlern@ned-box:<snapshot path> .
  local      <path inside a mounted local snapshot>
  sha256: git, timeshift and local agree
```

### Fail-open, structurally

Any error inside the hook — an unparseable payload, a crashed subprocess, a missing script — exits 0 with no stdout and one line in its own log. **A hook that can block a tool call is a hook that can wedge the fleet**, and this one has no reason to block anything. A deliberately-crashing build of it must demonstrably let the tool call through; that is a test, not an aspiration.

### How it calls the search

`scripts/find-deleted-path-across-backups.py` prints prose for a human. The hook needs machine-readable results, so the script gains a **`--json` mode** emitting one object per surface with its outcome, path, timestamp, sha256 and recovery command. The prose renderer becomes a formatter over that same structure, so the two cannot drift apart.

### Extracting the path from a Bash failure

`Read` and `Edit` hand the path over directly. `Bash` does not: it sits inside the error text, positioned differently by each program. These patterns, applied in order to each line of `error`, cover every shape the 486-transcript census produced:

| pattern | the shape it catches |
|---|---|
| `cannot access '(.+?)'` | `ls: cannot access '/x/y': No such file or directory` |
| `can't open file '(.+?)'` | `python3: can't open file '/x/y': [Errno 2] ...` |
| `No such file or directory: '(.+?)'` | `FileNotFoundError: [Errno 2] No such file or directory: '/x/y'` |
| `pathspec '(.+?)' did not match` | `fatal: pathspec 'docs/x' did not match any files` |
| `^\S+: (.+?): open: No such file` | `wc: /x/y: open: No such file or directory` |
| `cd: ?(.+?): No such file or directory` | `bash: line 1: cd: /x/y: ...` and `(eval):cd:1: no such file or directory: /x/y` |
| `^\S+: (.+?): No such file or directory` | `cat: /x/y: No such file or directory` — the general last resort |

The rules around them:

- **First match wins**, in the order above, so the specific patterns run before the general one and `ls: cannot access '/x'` is not mis-read by the last row.
- **No match means silence.** The hook exits 0 without searching rather than guessing.
- **A missing program is not a missing file.** `env: python3: No such file or directory` matches the last row and yields `python3`; a candidate containing no `/` that names no existing directory entry is discarded.
- **Only the first candidate is searched**, and the note names which path it searched, so a reader can see what was and was not looked for.

These patterns are a build artifact with a test rather than prose to be re-derived: the 66 census lines are the corpus, and the test asserts the extracted path for each.

### Deliberately left to the build

The **thresholds inside the transcript classifier** — how large a neighbouring block of text must be to count as "content likely present". No measurement exists to set them, they are cheap to tune against the corpus once the classifier runs, and a number invented here would be an unmeasured claim of exactly the kind this document has already had to remove.

## What it hands back

**Locations and an agreement line — not a copy.** Every copy found is checksummed with SHA-256 where it lies — the full digest is compared, an abbreviation is displayed — and the surfaces are compared:

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

**A surface with more than one location reports the honest combination.** Transcripts live on this Mac *and* on ned-box; Timeshift is reached over ssh. The rule: FOUND if any location found it; otherwise UNAVAILABLE if any location could not be searched, naming which one and stating what the searched locations returned; otherwise NOT FOUND. Without this, a run that searched the Mac and could not reach the box reports NOT FOUND — the exact dishonesty this contract exists to prevent. (This is also finding F6 on PR #146, where the built script has the defect.)

### Transcripts report three states, not one

Transcripts match on the path *string*, and an agent searching for a file has usually just typed that path — so its own session always matches. Observed in testing: a lone hit that was the searching session quoting the filename. Reporting that as "found in 1 transcript" reads as recovery and is not. So:

- **content likely present** — the path appears alongside a large body of text, the shape of a tool result that read the file. Reported as **FOUND**.
- **mentioned only** — the name appears, with no content near it. Reported as **NOT FOUND**, with the mentions listed underneath as leads: the surface was searched and does not hold the content, and a name turning up is worth seeing without being recovery.
- **the searcher's own session** — excluded by session id *before* classification, so it never reaches the vocabulary at all.

These are a refinement of what "has the content" means for a surface that can hold a filename without holding the file. They do not replace the three outcomes above; every transcript result still resolves to exactly one of them.

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

## Test plan

Two different things are tested, with separate corpora and separate verdicts. Conflating them yields a green suite that proves nothing: a perfect searcher behind a trigger that never fires is useless, and the reverse is noise.

**1. The trigger — does the hook fire on the right failures?**
Corpus: the 66 real missing-file error lines already extracted from 486 transcripts. Small enough to hand-label honestly, and it is real traffic rather than invented cases. **Measures false positives.**

**2. The search — given a path, is the content found?**
Corpus: the **294 distinct paths git has ever deleted** in this repository, filtered. Unfiltered, it is not a set of losses: it contains renames (the content moved and nothing was lost), paths deleted and later re-added, and deliberate removals — a `NOT FOUND` on any of those is correct, not a false negative. Filtering out paths whose content survives under another name and paths later re-added leaves a set where git genuinely should find the content, and a `NOT FOUND` on *that* set is a real false negative with no labelling required.

Two limits, stated because the corpus is easy to overclaim:

- **It establishes the git surface only.** Finding content in git's history says nothing about whether Timeshift, local snapshots, Time Machine or transcripts would have found it. The other surfaces get their coverage from the Timeshift differential and the per-surface synthetic tests below.
- **It shares provenance with what it tests.** The corpus is produced by the same history queries the search uses, so a mistake in how history is queried could yield a corpus that agrees with itself. That is the reason the other corpora must not also be git-derived.

Two further corpora:

- **Synthetic injection**, scoped per surface by how fast that surface ingests. The naive form — copy a file, delete it, expect recovery — cannot work: a file created and deleted minutes later is in no history at all, so the finder correctly reports nothing and the test proves nothing. The file must enter a history first, and how long that takes differs:
  - **git** — commit it, delete it, assert byte-identical recovery. Seconds; belongs in the ordinary suite.
  - **local snapshots** — the same cycle after one hourly snapshot. A slow test, not a CI test.
  - **Timeshift** — the same, after one 10-minute box snapshot. Slow test.
  - **Time Machine** — needs a backup run to complete, which is hours. A manual test, run occasionally, never automated.
- **Timeshift differential** — files present in an old box snapshot and absent now: real losses with known recoverability, exercising the box surface instead of using git as both question and answer.

## Deliberately not in version 1

- **A CLAUDE.md note as the primary fix.** The hook executes rather than advises, and this project has watched the written-convention layer lose to trained habit before.
- **Blocking the agent to wait for a password.** The hook prints the command; the script waits when a person runs it.
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
| local snapshots mount, read and unmount | all three unprivileged | `mount_apfs -o ro` against the Data volume as the ordinary user, read `CLAUDE.md`, `diskutil unmount` |
| local snapshot retention | 24 kept: 15 same-day, 5 previous day, 2 each on 2026-07-27 and 07-28, nothing between | `tmutil listlocalsnapshotdates /` |
| Time Machine backup interval | hourly (`AutoBackupInterval = 3600`), `AutoBackup = 1` | `defaults read /Library/Preferences/com.apple.TimeMachine.plist`, readable unprivileged |
| fleet paths excluded from backup | none — `~/Projects`, `~/agents`, `~/.claude`, `~/Documents` all `[Included]` | `tmutil isexcluded` |
| macOS version these hold for | 26.5 | `sw_vers` |
| a hook's `additionalContext` reaches the model on `PostToolUseFailure` | yes — quoted back verbatim, delivered next to the tool result | probe hook returning `hookSpecificOutput.additionalContext`, `claude -p` asked to quote what it saw |
| a provenance-shaped note is acted on | yes — the agent ran `git show <sha>:<path>` itself and recovered the file | same probe, real repository |
| a note pointing at a pre-fetched copy is refused | yes — the agent called it a prompt injection | same probe, scratch-directory copy |
| paths git has ever deleted | 294 distinct | `git log --all --full-history --diff-filter=D --name-only --format=` piped through `sort -u` |
