---
issue: "[The backup search cannot search ned-box's Timeshift when it runs on ned-box, because it reaches \"the box\" by ssh to itself](https://github.com/nedschorus/nedschorus/issues/807)"
---

# The backup search cannot search ned-box's Timeshift when it runs on ned-box, because it reaches "the box" by ssh to itself

Filed by the merge-lane-2 seat on 2026-09-30 (UTC), from a finding it reproduced. The reproduction is first; the cause, what it causes and the next action follow it. A line number given without a file, such as `:257`, is in `scripts/find-deleted-path-across-backups.py`.

## Reproduction

Run on ned-box on 2026-09-30 (UTC), from a checkout of main at `e09ca324`:

```
python3 scripts/find-deleted-path-across-backups.py /tmp/ghi-probe-no-such-file-12535156543.md --skip git --skip reflog --skip localsnapshots --skip timemachine --skip logstore
```

It printed this in under a second and exited 3:

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
