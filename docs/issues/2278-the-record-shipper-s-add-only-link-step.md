---
issue: "[The record shipper's add-only link step does not report a staging directory it could not remove](https://github.com/nedschorus/nedschorus/issues/2278)"
---

# The record shipper's add-only link step does not report a staging directory it could not remove

## What is wrong

`link_staged_files_never_over_existing` in `nc-systems/cold-read/cold-read-record-ship.py` links an approval-walk's staged files into the log-store without replacing any file already there, then removes the staging directory, and returns the process and the digests the store holds. Its only caller is `ship_walk` in `scripts/walk-files-ship.py`, for add-only placing.

The step ignores whether removing the staging directory worked, on both of its paths: remotely, the sh script from `link_staged_files_never_over_existing_script` runs `rm -rf -- <staging directory>` and goes on; locally, it calls `shutil.rmtree(staging, ignore_errors=True)`. Nothing it returns says the directory is still there.

A staging directory left behind stops every later shipment of that approval-walk that runs the replace step: `replace_with_staged_files` finds another shipment's staging directory and replaces nothing until someone deletes it. `ship_walk` prints no FAILED line naming the directory, because the step looks like a success.

Found in review of PR [walk-files-ship.py reports a staging directory it cannot remove, and a bad invocation, as FAILED](https://github.com/nedschorus/nedschorus/pull/2176) (mac-claude review 5720297155, at `scripts/walk-files-ship.py` line 611). That PR reports a failed removal on every other path in `ship_walk`, and leaves the shared shipper alone as outside its topic.

## Why

Nobody notices the leftover until a later invocation of `scripts/walk-files-ship.py` fails, and that invocation's FAILED line names the leftover directory, not the invocation that left it.

## What to do

Make `link_staged_files_never_over_existing` return, beside the process and the digests, why removing the staging directory failed, or None when it worked, on both paths. On the remote path the sh script can print a line that no `sha256sum` line can be mistaken for when `rm -rf` fails, and the parser keeps the digests either way. Then make `ship_walk` report it as it reports the other failed removals: name the directory, say why removing it failed, and give the command that deletes it, through `staging_directory_left_behind_failed_line_sentences_with_path_reason_and_rm_command`. When placing itself failed, `ship_walk` already tries the removal again, so the new result matters only when placing worked.

Done when an add-only shipment whose staging directory cannot be removed prints a FAILED line naming that directory and its delete command, a test in `scripts/walk-files-ship-test.py` causes that failure, and a test in `nc-systems/cold-read/tests/cold-read-record-ship-test.py` causes it on each path and checks the reason the step returns.
