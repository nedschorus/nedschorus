---
issue: "[Backup strategy for state outside git (Time Machine covers today; inventory + restore drill when the boss teaches it)](https://github.com/nedschorus/nedschorus/issues/7)"
---

# Backup strategy for state outside git (Time Machine covers today; inventory + restore drill when the boss teaches it)

## Ruled 2026-09-07: transcripts get off-machine coverage in the log-store on ned-box

The user, in the MD-skills seat's walk on where cold-read records live: "I think we should backup our transcripts to the nedbox." This decides scope item 2 below for one class — Claude session transcripts — and is the first authorization to build anything under this issue. The rest of the scope (the other classes, the restore drill) stands as before.

**Where they go.** The log-store is the directory on ned-box for the byproducts of the work that are not the system, ruled the same evening: `/home/nedlern/nedschorus-logs/`, one subdirectory per kind (`cold-read-records/`, `walk/`), a file there cited with its host in scp form so an agent on either machine knows the command. Transcripts are the third kind, one subdirectory per machine, keeping Claude Code's own layout underneath so a transcript is found the same way it is found locally:

```
/home/nedlern/nedschorus-logs/transcripts/mac/projects/<project-key>/<session-id>.jsonl
/home/nedlern/nedschorus-logs/transcripts/mac/handoffs/<file>
/home/nedlern/nedschorus-logs/transcripts/ned-box/projects/...
/home/nedlern/nedschorus-logs/transcripts/ned-box/handoffs/...
```

`mac` and `ned-box` are the names CLAUDE.md uses for the two machines. The project-key directory (`-Users-el-agents-MD-skills`) already encodes the seat, so there is no per-seat layer. `~/.claude/projects/` also holds the memory store (`<project-key>/memory/`), so mirroring it covers memories too. ned-box's own transcripts are already on its disk inside Timeshift's coverage (its include list ends with `+ /home/nedlern/**`, checked 2026-09-07); copying them in as well makes the store the one place to look for any session from either machine.

**How, as built and landed.** `scripts/transcript-mirror-to-log-store.py` with `scripts/transcript-mirror-to-log-store-test.py`, 20 cases, merged in PR [transcript-mirror-to-log-store.py: mirror ~/.claude/projects and handoffs into the log-store on ned-box, hourly by cron](https://github.com/nedschorus/nedschorus/pull/289) on 2026-09-08. `rsync -a` of the two directories, over ssh in batch mode from the Mac and locally on ned-box, never `--delete`, so a transcript that vanishes locally stays in the store. This is a mirror, not a record: a live session's transcript grows between runs and rsync sends the delta, so the record shipper's no-overwrite rule does not apply. The script's own docstring carries the rest, including why files vanishing mid-run are not a failure and why that exit code differs between the Mac's openrsync and ned-box's GNU rsync.

**Scheduled 2026-09-10, hourly by cron on both machines.** Not launchd on the Mac: the project's escaped-bug dataset records that launchd never fires StartInterval jobs on this Mac. Cron does, verified the same day with a one-minute canary line that fired on time and was then removed. Both reference checkouts were brought to main first; ned-box's was 132 commits behind and did not have the script. The two lines, one per machine:

```
Mac:     17 * * * * /opt/homebrew/opt/python@3.13/libexec/bin/python3 /Users/el/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py >> /Users/el/.claude/transcript-mirror.log 2>&1
ned-box: 17 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/transcript-mirror-to-log-store.py >> /home/nedlern/.claude/transcript-mirror.log 2>&1
```

To remove either, `crontab -l | grep -v transcript-mirror-to-log-store | crontab -` on that machine.

**First pass by hand, 2026-09-10, both exit 0.** Mac: 3,236 project files, and 158 handoffs against the store's 167, the nine extra being files the store kept after the Mac dropped them, which is the never-delete rule working. ned-box: 278 project files and 21 handoffs, matching exactly.

**Next action.** Read `~/.claude/transcript-mirror.log` on each machine after the next few ticks at 17 minutes past the hour and confirm the hourly run stays quiet and exits 0. Then this class of scope item 2 is done and only the recovered archive below is unruled.

## Added 2026-09-08 (cold-read-research): the recovered Time Machine merge is a fourth class, and a mirror will never pick it up

The 2026-09-07 ruling covers the two live trees. It does not cover a recovered archive, and one now exists that is the only copy of transcripts which no longer exist anywhere else.

**What it is.** `/Users/el/claude-transcripts-backup-2026-09-05/` on the Mac, 3.1 GB, holding a copy of `~/.claude/projects` plus `from-time-machine/` — 3,342 transcripts across 186 project directories, merged from 31 Time Machine backups covering July to early September 2026, never overwriting. It was assembled on 2026-09-05 while mining raw first drafts for the reviewer test set.

**Why it cannot wait for the mirror.** `rsync -a` of `~/.claude/projects` will never see it, because it does not live there. The transcripts in it that matter most are precisely the ones the 30-day cleanup had already deleted from the live tree: the four early-August new-vp sessions named in early-August commits, among them `5b66b6d0-5582-4532-a300-fafa0713910a`, which wrote the first draft of the ghi-write skill. That session was resumed successfully on 2026-09-08 to prove the resumed-author test arm is possible; the proof depended on a file that exists in the recovered merge and in Time Machine, and nowhere else on the live disk.

**Why this class matters beyond backup.** Two pieces of work now read old transcripts as source material rather than as logs. The reviewer test set's raw first drafts are recovered from them, and the resumed-author arm resumes them. So a deleted transcript is not a lost log, it is a lost test case and a lost experiment.

**Proposed disposition, not yet ruled:** one-time upload to `/home/nedlern/nedschorus-logs/transcripts/recovered/from-time-machine-2026-09-05/`, kept separate from the `mac/` and `ned-box/` mirrors because it is an archive rather than a mirror — nothing on the Mac will keep changing it, and it must never be pruned to match a live tree. About 3.1 GB against 3.3 TB free on the store's disk.

**Measured 2026-09-08, for whoever builds the mirror:** the store already holds 714 `.jsonl` files, 335 MB, under `transcripts/mac/projects/`; the Mac's live tree holds 1,861. That was a partial copy made by hand, before the mirror script existed. The script landed on 2026-09-08 and both machines' subtrees are now in the store; the counts are in the section above.

**Also worth recording, because a claim in this issue reads the other way to a fresh reader:** the log-store's own durability is Timeshift on ned-box, verified 2026-09-08 — snapshots of `/home/nedlern` every ten minutes to `/mnt/backup` on a separate 3.6 TB disk, 3.3 TB free. The store is not on a network drive and has no network mount; it is the box's internal disk, snapshotted to a second disk in the same machine.


## Measured 2026-10-01: the Mac's Time Machine backup, six questions answered

The Mac-side survey, ruled 2026-08-14, asked six questions about the Mac's backup that no agent on ned-box could answer. Its questions are at `git show 773d118c:docs/issues/queue/mac-side-time-machine-survey.md`; the file is removed from the queue now that this section answers them. Measured on the Mac on 2026-10-01 (last at 19:59 PDT), read-only, with the backup drive connected; item 27 of the walk queue-and-drafts-drain-2026-09-22 ruled that the answers are recorded here (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/queue-and-drafts-drain-2026-09-22-minutes.md`).

1. **Destination.** `tmutil destinationinfo`: one destination, "My Passport for Mac", Kind Local, an external disk mounted at `/Volumes/My Passport for Mac`, 3.6 TB.
2. **Last backup and spacing.** `tmutil latestbackup`: 2026-10-01 18:58 PDT. `tmutil listbackups`: about one backup an hour while the drive is attached; none from 2026-09-26 to 2026-09-29, and the drive was found unplugged during that gap.
3. **Exclusions.** `tmutil isexcluded` reports `[Included]` for `~/Projects`, `~/agents`, `~/.claude` and `~/Documents`. So `~/Projects`, `~/agents` and `~/.claude` are backed up on both machines: on ned-box by Timeshift, whose include list ends with `+ /home/nedlern/**`.
4. **Retention.** `tmutil listbackups` holds 79 backups, the oldest from 2025-11-13: hourly within the last day, one a day within the last month, and two to five a month before that, with none at all in June 2026. `df -h` on the drive: 1.2 TB of 3.6 TB used, 32%. Time Machine deletes its oldest backups only when the drive fills, so at this level nothing has yet been deleted for space.
5. **Frequency.** `defaults read /Library/Preferences/com.apple.TimeMachine`: `AutoBackup` is 1 (automatic backups on) and `AutoBackupInterval` is 3600 (hourly), on macOS 26.6.2 (`sw_vers -productVersion`). The interval is a setting on this version, and it is at its hourly value.
6. **Restoring one file.** The backups can be listed without privilege, but not read in place: the path `tmutil latestbackup` prints does not open for an ordinary user, and reading inside a backup takes a read-only `mount_apfs`, which needs root. `scripts/find-deleted-path-across-backups.py <path>` searches Time Machine as one of its surfaces and prints the exact recovery command, or UNAVAILABLE with the command that needs the password. The tight sudoers rule it is built around ships in the repository as `config/sudoers-mount-apfs-readonly-for-backup-recovery`; a file named `nedschorus-mount-apfs-readonly` is present in `/etc/sudoers.d/` on the Mac (its content was not read: that needs root).

**Next action.** None from these answers. Scope item 3 below, testing one restore path, now has a command-line route to test: `scripts/find-deleted-path-across-backups.py` against a file known to be in a Mac backup.

---

Boss-raised 2026-07-21: is a backup strategy for state that matters but is not in git worth a GHI? Ruling implicit in this issue's existence: yes, as future work — the machine currently has Time Machine coverage (boss-operated; no agent has been taught to use it), so nothing is unprotected today; what is missing is a ruled inventory and tested restore paths.

Scope when picked up:
1. Inventory machine-local state that matters and is outside git: Claude session JSONLs and the memory store (`~/.claude/projects/...`), Codex rollouts (`~/.codex/sessions/...`), the old system's SQLite (`~/Projects/nedlern/db/messages.sqlite`), future nedschorus bridge logs (gitignored by design), credentials/keyring.
2. Decide per class: covered-by-Time-Machine-is-enough vs needs off-machine or committed coverage. — Claude session transcripts and the memory store: decided 2026-09-07, off-machine to the log-store, above. A fourth class, the recovered Time Machine merge, is described in the 2026-09-08 section above and is not yet ruled.
3. Test one restore path (the boss teaches Time Machine use — trigger for picking this issue up).

Legacy references (existence verified 2026-07-21, contents NOT vetted — the boss flags they may be obsolete; verification is part of this work):
- `~/Projects/nedlern/docs/working/proposed/unified-non-git-backup-2026-06-28.md`
- `~/Projects/nedlern/docs/working/proposed/agent-state-outside-git-design.md`
- `~/Projects/nedlern/docs/working/proposed/nedlern-machine-state-repo-and-sweep-2026-07-17.md`

Ladder position: the transcript mirror is authorized (2026-09-07) and now built and scheduled (2026-09-10); the Mac's Time Machine survey is answered (2026-10-01, above); nothing else under this issue is authorized.

—
Session: f5081355-c3fd-4271-956c-68ffeb99e4ae (new-vp); revised 2026-09-10 by md-skills-9e; Time Machine answers added 2026-10-01 by cold-read-research
