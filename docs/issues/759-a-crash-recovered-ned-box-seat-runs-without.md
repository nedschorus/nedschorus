---
issue: "[A crash-recovered ned-box seat runs without its own GitHub token, and the Mac launcher warns of a missing token when it only attaches](https://github.com/nedschorus/nedschorus/issues/759)"
---

# A crash-recovered ned-box seat runs without its own GitHub token, and the Mac launcher warns of a missing token when it only attaches

Agent-filed by merge-lane-2 on 2026-09-28, on the user's "Y" at 2026-09-28T16:01:20Z to item 11 of the walk merge-lane-2-meta-walk-open-items-2026-09-23. Both gaps were found by reading the code in the review of PR [Each seat authenticates to GitHub as its own account, not the keyring's](https://github.com/nedschorus/nedschorus/pull/658) (`ned-review-merge` review 5285626707, non-blocking findings 1 and 3), and neither has been reproduced by a run. Line numbers are on main at `65addd77`, 2026-09-28.

## Gap 1: a box seat brought back by crash recovery or at login does not get its token

Since PR 658, each seat acts on GitHub as its own account. On ned-box the launcher does this: `scripts/launch-claude-ubuntu:255` puts a prefix into the seat's pane command that reads `~/.config/nedschorus/<account>.token` into `GH_TOKEN` when the file is there and leaves `GH_TOKEN` unset when it is not. A box seat's account is `ubuntu-claude` unless `NEDSCHORUS_SEAT_GITHUB_ACCOUNT` names another (`scripts/launch-claude-ubuntu:148`).

`scripts/recover-crashed-seats.py` does not go through that launcher on the box. Its `launch_seat` (`scripts/recover-crashed-seats.py:758`) composes the pane command itself (from `:819`), carrying the task-list binding and the seat's git identity, but no token prefix. The word "token" does not occur anywhere in the file. So a box seat recovered after a crash, or restarted at login, acts as whatever `gh` finds: the keyring's login on the box, which `scripts/launch-claude-ubuntu:136-141` records as `ubuntu-claude` with a CLASSIC token carrying `read:org`, `repo` and `workflow`; or a `GH_TOKEN` the recovering shell had exported, since the per-seat tmux server copies the caller's environment.

**Why it matters now.** When PR 658 merged, ned-box had no `ubuntu-claude.token`, so every box launch took the no-token branch and recovery lost nothing by skipping it. The file is on ned-box now (`~/.config/nedschorus/ubuntu-claude.token`, checked 2026-09-28), so an ordinary launch acts with the fine-grained repository-only token while a recovered seat falls back to the classic all-repository one, which credential ruling C4 in `nc-systems/main-gatekeeper/main-gatekeeper-design.md` says an agent host must not use.

The same gap reaches every box seat brought back after a reboot. `scripts/restart-live-seats-at-login.py` hands each seat to `scripts/recover-crashed-seats.py` (`scripts/restart-live-seats-at-login.py:522`), which on the box composes that same pane command, and the login service is enabled on ned-box (`restart-live-seats-at-login.service`, checked 2026-09-28). `scripts/resupervise-seat.py` is not affected: it relaunches through the launchers.

## Gap 2: the Mac launcher's "NO SEAT TOKEN" warning fires on a plain attach

`scripts/launch-claude-mac:481-490` prints the "NO SEAT TOKEN — <seat> will NOT act as <account>" block whenever the token file is missing, before the launcher decides whether it is creating a session or attaching to one. When the seat is already running, `new-session -A` at `:580` attaches and ignores the command it was given, so nothing is launched and no credential is chosen; the warning is then false. The box twin puts its warning in the prepare step (`scripts/launch-claude-ubuntu:419`), which an attach skips.

## Next action

One pull request, with a test for each half:
1. `scripts/recover-crashed-seats.py`'s box branch carries the same token prefix `scripts/launch-claude-ubuntu:255` composes, for the same account, so a box seat recovered after a crash or restarted at login reads its token file exactly as a launched one does; its test checks the composed pane command, as `scripts/launch-claude-ubuntu-test.py` checks the launcher's.
2. `scripts/launch-claude-mac` prints the warning only when it is about to create the session, not when it attaches to a running one.
