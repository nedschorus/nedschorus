---
issue: "[The walk shipper loses the walk-closed marker when an add-only placement fails after the minutes were replaced](https://github.com/nedschorus/nedschorus/issues/1960)"
---

# The walk shipper loses the walk-closed marker when an add-only placement fails after the minutes were replaced

## Reproduction

Run on ned-box on 2026-10-25 against main at commit `5e4918df260694daf17f06b2062c255b683a2b08`, in a detached worktree of main. The script below loads `scripts/walk-files-ship.py`, points it at a local store directory, and ships a closed walk whose minutes, walk text and draft are all new to the store. The shipper always puts minutes in place through its replacement step, even when the store has no copy yet, so the minutes go in before the add-only files whatever the store holds. Run 1 makes the add-only placement step fail, by replacing `shipper.link_staged_files_never_over_existing` with a function that returns what an ssh exit 255 returns. Run 2 restores the real function and ships again, as the run-1 FAILED line tells the agent to do.

The script is kept at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/ghi-drafts/walk-files-ship-marker-repro/repro.py`. On ned-box, run `python3 /home/nedlern/nedschorus-logs/seats/merge-lane-2/ghi-drafts/walk-files-ship-marker-repro/repro.py <a checkout of main>`; it writes its scratch files under a new directory in `/tmp/claude-1000/`.

```python
"""Reproduce: minutes replacement succeeds, add-only placement fails, walk-closed marker is never written, even on a successful retry."""
import contextlib, importlib.util, io, os, pathlib, subprocess, sys, tempfile
repo = pathlib.Path(sys.argv[1])
scratch = pathlib.Path(tempfile.mkdtemp(prefix="walk-ship-repro-", dir="/tmp/claude-1000"))
os.environ["HOME"] = str(scratch / "home")      # marker lands under $HOME/.claude/handoffs
os.environ["CLAUDE_CODE_SESSION_ID"] = "repro-session"
spec = importlib.util.spec_from_file_location("walk_files_ship", repo / "scripts" / "walk-files-ship.py")
ship = importlib.util.module_from_spec(spec); spec.loader.exec_module(ship)
walk_dir, store = scratch / "docs-walk", scratch / "store-walk"
walk_dir.mkdir(); store.mkdir()
name = "repro-walk"
(walk_dir / f"{name}-draft.md").write_text("# draft\n")
(walk_dir / f"{name}.md").write_text("# walk text\n")
(walk_dir / f"{name}-minutes.md").write_text("# minutes\n\nItem 1 ruled.\n\n#next_to_present none, closed\n")
marker = ship.threshold_hook.handoff_due_at_lower_context_threshold_after_approval_walk_closed_marker_path("repro-session")
destination = ship.WalkStoreDestination(None, None, pathlib.PurePosixPath(store))

def run(label):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ship.ship_walk(destination, name, walk_dir)
    print(f"--- {label}: exit {code}")
    print("stdout:", out.getvalue().strip())
    print("store:", sorted(p.name for p in store.iterdir() if p.is_file()))
    print("marker exists:", marker.exists(), marker)

real_link = ship.shipper.link_staged_files_never_over_existing
def failing_link(copy_host, staging_dir, walk_path, names):   # the add-only placement fails, as ssh exit 255 would
    return subprocess.CompletedProcess([], 255, "", "injected: ssh: connect to host ned-box: Connection timed out\n"), None
ship.shipper.link_staged_files_never_over_existing = failing_link
run("run 1, add-only placement injected to fail")
ship.shipper.link_staged_files_never_over_existing = real_link
run("run 2, retry with nothing injected")
```

What it printed:

```
--- run 1, add-only placement injected to fail: exit 1
stdout: FAILED: repro-walk — ned-box unreachable while putting the copied files in place; a later run finishes it.
store: ['repro-walk-minutes.md']
marker exists: False /tmp/claude-1000/walk-ship-repro-w9pm6_jh/home/.claude/handoffs/repro-session-handoff-due-at-lower-context-threshold-after-approval-walk-closed
--- run 2, retry with nothing injected: exit 0
stdout: shipped: repro-walk — 2 file(s) added (repro-walk-draft.md, repro-walk.md); 1 already there unchanged; minutes at /tmp/claude-1000/walk-ship-repro-w9pm6_jh/store-walk/repro-walk-minutes.md
store: ['repro-walk-draft.md', 'repro-walk-minutes.md', 'repro-walk.md']
marker exists: False /tmp/claude-1000/walk-ship-repro-w9pm6_jh/home/.claude/handoffs/repro-session-handoff-due-at-lower-context-threshold-after-approval-walk-closed
```

As a control, the same walk shipped once with nothing injected prints `shipped: repro-walk — 3 file(s) added (repro-walk-draft.md, repro-walk.md, repro-walk-minutes.md)` and the marker exists afterwards. So the closed minutes reached the store in run 1, run 2 finished the shipment and exited 0, and no run wrote the walk-closed marker.

## What is wrong

`ship_walk` in `scripts/walk-files-ship.py` puts the files it replaces (minutes, dispositions, a walk text that only grew) in place first, then places the add-only files. When the add-only placement fails (`after is None`), the function prints its FAILED line and returns at once. The block that writes the walk-closed marker comes later in the function, so it never runs, although the closed minutes are already in the store. A retry lists the store, finds the minutes unchanged, and the marker block writes a marker only when the minutes were added or replaced in this run, so the retry skips it too. The marker for that walk close is lost for good: the Stop hook in `scripts/handoff-context-threshold-hook.py` never sees it and never asks for /handoff at the 20% threshold after the close.

The program's own docstring, section THE WALK-CLOSED MARKER, says the marker is written on a `FAILED:` run whose closed minutes did reach the store, "since the closed minutes are the close and a re-run finds them unchanged". The code does not do that on this path. The early return when `shipper.replace_with_staged_files` returns `outcomes is None` can leave the minutes replaced as well, because that function's remote script renames file by file and can stop partway; whoever fixes this should cover that path too. The `OtherShipmentStaging` return cannot, because that function returns it before it renames anything.

The code came from pull request [#1943](https://github.com/nedschorus/nedschorus/pull/1943), commit `9bdf99607`. Codex found the defect while reviewing pull request [#1948](https://github.com/nedschorus/nedschorus/pull/1948), which does not trigger it; its report is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr1948-119b04a7/codex-code-review-report.md`.

## Why it matters

The walk-closed marker is what makes an agent-session hand off at 20% context after an approval-walk closes, instead of at the ordinary threshold. When the marker is lost, nothing tells the agent: run 1's stdout says "a later run finishes it", and run 2 says `shipped:` and exits 0, so the agent believes the close is complete and keeps working past the point where it should have handed off.

## What to do

fleet-restart-at-login, the agent-seat that wrote pull request #1943, fixes the root cause in `scripts/walk-files-ship.py`: once the closed minutes are in the store, the marker must be written whatever later step fails, as the docstring already promises. One way is to decide the marker right after the replacement step, from whether the minutes are among the files it replaced and whether their last `#next_to_present` line says the walk is closed, and write it before any later step can return. That alone does not cover a run that stops before it writes the marker, such as one killed or one whose replacement step returned `outcomes is None`: the retry finds the minutes unchanged and, under the docstring's rule that a run finding the closed minutes already in the store writes no marker, writes none. The fix must decide how a retry learns that the close's marker was never written. Add a test to `scripts/walk-files-ship-test.py` that injects the failure of the add-only placement, as the reproduction does, and checks that the marker exists after run 1; check it with mutation testing.

## Outcome

Not planned: the defect can no longer happen. Pull request [Approval-walks continue across a handoff, with no 20% handoff after a walk closes, and items checked against the user's earlier rulings](https://github.com/nedschorus/nedschorus/pull/2063), merged on 2026-10-28 as commit `9d25344f`, removed the walk-closed marker and the 20% threshold it fed, at the user's approval of item 11.1 of approval-walk reboot-test-carried-items-2026-10-27. `scripts/walk-files-ship.py` no longer writes the marker, and `scripts/handoff-context-threshold-hook.py` no longer reads it, so no marker can be lost.
