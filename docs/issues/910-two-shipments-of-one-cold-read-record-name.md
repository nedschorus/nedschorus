---
issue: "[Two shipments of one cold-read-record name at the same moment can lose a report while both say it shipped](https://github.com/nedschorus/nedschorus/issues/910)"
---

# Two shipments of one cold-read-record name at the same moment can lose a report while both say it shipped

Filed by the merge-lane-2 seat on 2026-10-01 (UTC), from a finding it reproduced. The reproduction comes first, then the cause, what it causes, and the next action. A line number given without a file, such as `:543`, is in `nc-systems/cold-read/cold-read-record-ship.py` at main `dad220d`.

## Reproduction

Run on ned-box on 2026-10-01 (UTC), from a checkout of main at `dad220d`. `COLD_READ_RECORD_SHIP_DESTINATION` points the shipper at a scratch directory, so the real log-store is not touched. Two record directories have the same name and a different `fast-read.md`, and both are shipped at once:

```
S=$(mktemp -d)
NAME=race-check-2026-10-01
mkdir -p "$S/a/$NAME" "$S/b/$NAME"
printf '<!-- provenance: checkout a -->\nreport from checkout a\n' > "$S/a/$NAME/fast-read.md"
printf '<!-- provenance: checkout b -->\nreport from checkout b\n' > "$S/b/$NAME/fast-read.md"
export COLD_READ_RECORD_SHIP_DESTINATION="$S/store/cold-read-records"
python3 nc-systems/cold-read/cold-read-record-ship.py "$S/a/$NAME" &
python3 nc-systems/cold-read/cold-read-record-ship.py "$S/b/$NAME" &
wait
cat "$S/store/cold-read-records/$NAME/fast-read.md"
```

Repeated 20 times, each with a new scratch directory:

- 17 of 20: both runs exited 0, and both printed `shipped: race-check-2026-10-01 — 1 file(s) added; record at <the store>/race-check-2026-10-01`. The store held one `fast-read.md`: checkout a's in 11 tries, checkout b's in 6. The other checkout's report never reached the store.
- 1 of 20: the second run printed `REFUSED: race-check-2026-10-01 — already in the store with different content: …` and exited 2. This is the refusal the shipper is meant to give.
- 2 of 20: one run printed rsync's `mkdir "…/race-check-2026-10-01" failed: File exists (17)`, then `FAILED: race-check-2026-10-01 — rsync exit 11 during the copy; a later run finishes it.`, and exited 1. The other run shipped. This failure is loud: nothing is lost without a word.

The same loss was first seen by mac-claude, the independent reviewer of PR [The explain skill is installed, with the script that gives a draft reply its fresh read](https://github.com/nedschorus/nedschorus/pull/894), in [its round 2 review](https://github.com/nedschorus/nedschorus/pull/894#pullrequestreview-5386377670), item 2. Two checkouts of that pull request's program shipped a record named `explain-reply-draft-seat-a-151738-2026-10-01` at once. Both printed `shipped:`. The store kept one checkout's `fast-read.md` beside the other checkout's `target/` directory.

## Cause

- The shipper reads what the store already holds at `:543`, and from that list decides which local files are new (`:553`) and which differ (`:551`).
- It then copies the new files at `:586` with `rsync --ignore-existing`.
- When the other shipment lands a file of the same name between those two steps, `--ignore-existing` skips that file without an error. The check that refuses a file whose content differs never sees it.
- The run then prints `shipped:` at `:635`, with the count of files it meant to add, not the count that landed.

## What it causes

A cold-read report is lost while both runs say it was shipped, and the store can hold one record that mixes files from both checkouts. Nothing on screen or in the store shows it. A caller that sees `shipped:`, a person or a program, treats the record as safe.

It needs two shipments of one record name at the same moment. Names carry the record's date, so this takes two runs of one target on one day: two checkouts, or two machines. The defect predates PR [The explain skill is installed, with the script that gives a draft reply its fresh read](https://github.com/nedschorus/nedschorus/pull/894), whose program names its own records by seat and time of day. Other cold-read-records are still named by target and date. That pull request does not trigger it.

## What a fix must do

A shipment prints `shipped:` only when every one of its files is in the store with its own content. When another shipment's file took a name first, it is refused, as a file with different content is refused today. The design is the owner's.

## Next action

The cold-read system owns the shipper. On 2026-10-01 at about 23:50 UTC the merge-lane-2 seat asked the cold-read-research seat to build the fix on its own topic branch.
