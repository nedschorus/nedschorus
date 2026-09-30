---
issue: "[The backup search cannot search ned-box's Timeshift when it runs on ned-box, because it reaches \"the box\" by ssh to itself](https://github.com/nedschorus/nedschorus/issues/807)"
---

# The backup search cannot search ned-box's Timeshift when it runs on ned-box, because it reaches "the box" by ssh to itself

Filed by the merge-lane-2 seat on 2026-09-30 (UTC), from a finding it reproduced. The reproduction is first; the cause, what it causes and the next action follow it, and the outcome comes last. A line number given without a file, such as `:257`, is in `scripts/find-deleted-path-across-backups.py`.

## Reproduction

Run on ned-box on 2026-09-30 (UTC), from a checkout of main at `e09ca324`:

```
python3 scripts/find-deleted-path-across-backups.py "/tmp/ghi-probe-no-such-file-$(date +%s%N).md" --skip git --skip reflog --skip localsnapshots --skip timemachine --skip logstore
```

The name is made new at every run: the transcripts surface would otherwise find it in the transcript of the session that last ran the command, and a transcript that holds it counts as FOUND. It printed this in under a second and exited 3:

```
transcripts     UNAVAILABLE
    this Mac: searched /home/nedlern/.claude/projects, no transcript mentions it
    the box (nedlern@ned-box): unreachable — Host key verification failed.

timeshift       UNAVAILABLE
    the box (nedlern@ned-box) is unreachable — Host key verification failed.
    the snapshots are fine; this machine just cannot see them right now

No surface that could be searched has it.
Could NOT search: transcripts, timeshift — see each one's line above; those are not 'not found'.
```

The `--skip` flags leave out only the surfaces that never contact the box. Without them, `build_report` (`scripts/find-deleted-path-across-backups.py:2221`) reaches these two surfaces in the same way.

## Cause

- `--box-ssh-host` defaults to `DEFAULT_BOX_SSH_HOST`, `"nedlern@ned-box"` (`:257`; the default is applied at `:2320`), on every machine, ned-box included.
- On ned-box, an ssh to that host fails before logging in. `ssh -o BatchMode=yes -o ConnectTimeout=5 nedlern@ned-box true` prints "Host key verification failed." and exits 255: nedlern on ned-box has no `~/.ssh/known_hosts`, and `ssh -G nedlern@ned-box` reports `stricthostkeychecking ask`.
- `search_timeshift` (`:1457`) searches the snapshots only through that ssh.
- `search_transcripts` (`:1358`) first greps `~/.claude/projects` on the machine it runs on. On ned-box that is ned-box's own transcripts, though its line says "this Mac". It then greps the box's copy of the same directory through that ssh, which fails.
- `search_log_store` (`:1132`) already avoids this: it reads the store directly when `os.path.isdir(log_store_root)` is true (`:1177`), and uses ssh only otherwise.

## What it causes

- The agent seats run on ned-box. From any of them, the backup search never searches ned-box's Timeshift snapshots, although they are on ned-box's own disk (`/mnt/backup/timeshift/snapshots`, `DEFAULT_TIMESHIFT_SNAPSHOT_ROOT` at `:258`).
- Every run on ned-box that does not find the file exits 3 with "Could NOT search: transcripts, timeshift", even though ned-box's transcripts were searched.
- PR [The locator runs the backup search itself when it finds nothing](https://github.com/nedschorus/nedschorus/pull/806), open when this was filed, makes the locator, `scripts/locate-file-copies-across-machines.py`, run the backup search whenever it finds no copy. With it merged, every locator run on ned-box that finds no copy ends with those two UNAVAILABLE surfaces, and with a closing line telling the agent to tell the user which places could not be searched.

## Next action

Change `scripts/find-deleted-path-across-backups.py` so that, when it runs on ned-box:

- **Timeshift** runs the same probe, `_timeshift_probe_script` (`:1525`, a shell script), on ned-box itself instead of through ssh, and keeps its current report when the snapshot root is absent ("does not exist on ... is the backup drive mounted?").
- **Transcripts** keeps its first, local grep, which on ned-box already covers ned-box's transcripts, and drops the second grep through ssh, which would search the same directory again. Its lines name ned-box instead of "this Mac", and say that the Mac's transcripts were not searched, because the Mac cannot be reached from ned-box; the locator records the same fact as `MAC_NOT_REACHABLE_FROM_NED_BOX` (`scripts/locate-file-copies-across-machines.py:366`).

To tell that it is on ned-box, use the locator's test, `socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME` (`scripts/locate-file-copies-across-machines.py:380`). The log-store surface's test, whether its directory exists on this machine (`:1177`), also fits Timeshift, whose snapshot root exists only on ned-box, but not transcripts, whose `~/.claude/projects` exists on every machine.

Add a case to `scripts/find-deleted-path-across-backups-test.py`, which drives every surface through a stand-in runner, showing that a run on ned-box starts no ssh and still searches both surfaces.

The alternative, making ned-box's ssh to itself succeed, changes machine configuration instead of code, and every search would still log in to ned-box from ned-box.

## Outcome

Fixed on 2026-09-30 by PR [On ned-box the backup search searches Timeshift and transcripts in place](https://github.com/nedschorus/nedschorus/pull/816), merged at `0fc689ba`. The user ruled that day that the merge-lane Mac seat, not merge-lane-2, would build the fix, and the Mac seat built it. The line numbers in the sections above are at `e09ca324`, where this issue was reproduced; the fix moved them.

- **Fix.** `scripts/find-deleted-path-across-backups.py` tells ned-box by the locator's test, through a new `running_on_ned_box()`, decided once in `build_report`. On ned-box, `--box-ssh-host` is not used:
  - Timeshift runs `_timeshift_probe_script` through a local `bash -c`, the shell ssh ran it under. Its lines name ned-box, and a hit is recovered with `cp` instead of `scp`. A probe that exits with anything but 0 reads "the search on ned-box did not complete (exit N)", never "unreachable".
  - Transcripts keeps its local grep, labelled `ned-box:`, and sends nothing over ssh. It adds the line "the Mac: not searched — no route from ned-box to the Mac is documented", the locator's `MAC_NOT_REACHABLE_FROM_NED_BOX`.

  The Mac's behaviour is unchanged.
- **Exit codes on ned-box.** A file found anywhere still exits 0. A run that finds nothing still exits 3, by design, and now ends "Could NOT search: transcripts", not "transcripts, timeshift": Timeshift is searched, and transcripts stays incomplete because the Mac's transcripts cannot be searched from ned-box, which is the locator's rule too. `--skip box` leaves this unchanged: it skips ned-box's own Timeshift, and the Mac's transcripts are still unsearched.
- **Measured on ned-box, read-only,** from copies of the merged program in a temporary directory, not from a checkout:
  - the reproduction above prints timeshift NOT FOUND "on ned-box" and exits 3, naming transcripts alone;
  - `/etc/hostname` is FOUND in 136 snapshots, with a `cp` recovery line;
  - a bare-name Timeshift search took 3.0 s when it found the file (in 262 snapshots) and 2.2 s when it did not.
- **Tests.** `scripts/find-deleted-path-across-backups-test.py` gains 15 cases, 12 of which fail against the program before the fix. Every case not about which machine the program runs on is pinned to the Mac's answer, so the suite gives one answer on either machine; it passes all 318 of its cases on ned-box.
