# Time Machine survey — questions for a Mac-side agent to answer

**Owner: a Mac-side agent.** Ruled by the user 2026-08-14. This is a survey, not a change: nothing here modifies anything.

## Why this exists

The nedschorus fleet spans two machines — the Ubuntu box `ned-box`, where agents run, and the user's Mac, where he sits and where branches are reviewed and merged. Backup coverage on the box is now known precisely: Timeshift, hourly, retention raised to 24 hourly / 7 daily / 5 weekly / 12 monthly, with games and caches excluded, and a health check (`scripts/backup-health-check.py`) that surfaces a stalled or failing backup in the status line.

The Mac's half is entirely unknown. No agent on the box can see it, so every statement about it would be a guess. Two documents are blocked on that: a file-recovery runbook that must give correct steps for **both** machines, and the layer design that decides what is backed up by git versus by the machine.

Answering these questions unblocks both. Report the answers; do not act on them.

## Constraints on answering

- **Read-only.** `tmutil` has destructive subcommands — `delete`, `disable`, `setdestination` — and none are needed. Running any of them would violate the standing rule in `CLAUDE.md` that agents read backup state and never write it.
- **Report, do not fix.** If Time Machine turns out to be off, or excluding something important, say so and stop. Changing it is the user's decision, brought to him as a walk item.
- Commands run **on the Mac**, natively. They are not `ssh nedlern@ned-box` commands.

## The questions

1. **Is Time Machine enabled, and what does it back up to?**
   `tmutil destinationinfo`
   An external disk, a network share, and no destination at all are three different situations with different failure modes. Name which one this is.

2. **When did a backup last complete, and how often do they happen?**
   `tmutil latestbackup`, and `tmutil listbackups` for the spacing between recent ones.
   The box warns when its newest scheduled snapshot exceeds three hours. The equivalent threshold for this Mac cannot be chosen without knowing the real interval.

3. **What is excluded?**
   `tmutil isexcluded ~/Projects ~/agents ~/.claude ~/Documents`
   The specific worry: if the Mac excludes any of the first three, the two machines have different coverage and the runbook cannot state one rule for both. Report each path's answer separately.

4. **What is the actual retention?**
   Apple's documented behaviour is roughly hourly for 24 hours, daily for a month, and weekly until the disk fills — close to the scheme now configured on the box. Confirm it for this machine and this macOS version rather than restating the general documentation, and report the destination's free space, since "weekly until full" makes free space part of the retention answer.

5. **Is the backup frequency adjustable on this macOS version, and what is it set to?**
   Recent macOS versions added a backup-frequency setting alongside the older fixed hourly behaviour. Report the macOS version, whether the setting exists, and its current value.

6. **How does a person restore one lost file here?**
   On the box the answer is that snapshots are ordinary readable directories, so recovery is a copy out of the snapshot tree and needs no special tool. State the true equivalent for this Mac — whether the backup is browsable as a filesystem, and what the reliable command-line path is. This is the sentence the runbook needs most, because it is what the user will reach for under stress.

## Where the answers go

Into the file-recovery runbook, which will carry a section per machine, and into the layer design that decides what git backs up versus what the machine backs up. Both are pending as of 2026-08-14; until they exist, record the answers on this document.
