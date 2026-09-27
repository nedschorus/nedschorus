---
issue: "[The Mac's transcript mirror reports \"mirrored\" every hour while grown transcripts stay un-copied on ned-box](https://github.com/nedschorus/nedschorus/issues/735)"
---

# The Mac's transcript mirror reports "mirrored" every hour while grown transcripts stay un-copied on ned-box

Agent-filed by merge-lane-2 on 2026-09-27, from a reproduced finding. The reproduction is first; the cause is not yet known, and the next action is to find it on the Mac.

## Reproduction

`scripts/transcript-mirror-to-log-store.py` runs hourly at :17 from cron on the Mac. It copies `~/.claude/projects/` to `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/mac/projects/`.

One transcript, the cold-read-research seat's session `8a00a4e5-6823-45ff-84c2-5becb95a8daa.jsonl` under `-Users-el-agents-cold-read-research/`, measured on 2026-09-27:

| | size | lines | newest record | mtime |
|---|---|---|---|---|
| the Mac's file (read by cold-read-research at ~20:55Z) | 7,395,399 bytes | 2,229 | 2026-09-27T20:53:40Z | 2026-09-27 13:53:40 PDT |
| ned-box's copy (read by merge-lane-2 at ~20:50Z) | 5,417,539 bytes | 1,655 | 2026-09-24T21:34:15Z | 2026-09-27 12:59:08 PDT |

About 574 lines written since 2026-09-24T21:34Z are on the Mac and not on ned-box. They include the user's typed rulings from 2026-09-27. The copy's mtime moved to 2026-09-27, but its content did not.

The same holds across the whole Mac copy on ned-box. The newest record in any file under `transcripts/mac/projects/` is 2026-09-24T21:42:34Z, though Mac seats were active through 2026-09-27. No new file has appeared there since 2026-09-24.

Meanwhile, the Mac's log `~/.claude/transcript-mirror.log`, read by cold-read-research at ~20:40Z on 2026-09-27, was last written at 13:17 PDT (the 20:17Z run). Its last 15 lines alternate, identically:

    mirrored: handoffs — local 548 files, store 1001 files
    mirrored: projects — local 4538 files, store 5309 files

There are no error lines. The counts do not change between runs, and no line carries the "(some files vanished mid-run: a session ended)" note, which means rsync exited 0.

The ned-box half of the mirror is not affected. ned-box's own copy of merge-lane-2's session `34e2bc2c-032f-4896-b323-374a223dd6ca.jsonl` matched its source as of the 20:17Z run. That half runs GNU rsync 3.4.1, locally.

## Why it matters

- The log-store copy is the only place a ned-box seat can read what the user typed to a Mac seat. The merge seat verifies every prose pull request's ruling there. Since 2026-09-24 no ruling given to a Mac seat can be verified. PRs [The withdrawn task-list rule's draft and its docstring paragraph are removed](https://github.com/nedschorus/nedschorus/pull/731) and [The commit guard's refusal covers amending and hand commits under the tripwire](https://github.com/nedschorus/nedschorus/pull/728) hit this on 2026-09-27.
- It is the backup the user asked for on 2026-09-07 (recorded on GHI [Backup strategy for state outside git](https://github.com/nedschorus/nedschorus/issues/7)). It has been silently three days behind while reporting success.

## Cause

Not yet known. What is known:
- **openrsync rewrites each grown file every hour, with its old content.** On ned-box, `stat -c '%w'` shows that the 20:17Z run on 2026-09-27 created six Mac copies anew, between 13:17:03 and 13:17:05 PDT. The cold-read-research file above has inode 2311422. Each copy has the Mac source's current mtime, and a size and content that still end on 2026-09-24. Found by `mac-claude` reviewing this file's pull request, and re-measured by merge-lane-2. So the files are not being skipped: something in how openrsync rebuilds a changed file writes out the old content.
- The Mac's rsync is `/usr/bin/rsync`, which is openrsync (`rsync_vanished_exit_code`, `scripts/transcript-mirror-to-log-store.py:106-121`).
- The command is `rsync -a --timeout …`, built at line 155. It never uses `--delete` or `--inplace`.
- The program trusts an exit of 0, and prints "mirrored" with counts of files. It never compares sizes or content (lines 201-214), so a run that copies nothing new looks the same as a run that copies everything.

## Next action

On the Mac, find why openrsync leaves a grown file's content behind:
1. Run the program's own rsync command for `projects` by hand, verbosely, and read its stderr.
2. Compare one grown file's size on both sides before and after the run.

Then fix the mirror so that it copies grown files. One candidate, to be tested and not assumed: GNU rsync from Homebrew instead of `/usr/bin/rsync`. Finally, make a run whose copy is short of its source report FAILED instead of "mirrored". For example, compare the byte totals of a sample of recently modified files on both sides after the run.
