---
issue: "[Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)](https://github.com/nedschorus/nedschorus/issues/27)"
---

# Console text-insertion + stuck/waiting-state detection (operator tooling; captured from the comms backlog)

## What this captures

Two related operator-tooling capabilities from the communications backlog (pair GHI [Working ideas and research backlog — capture pair (Decided / Candidate / Research / Reference)](https://github.com/nedschorus/nedschorus/issues/10), dispersed at walk item 17 cluster 1, boss-ruled 2026-07-25). Captured, not scheduled.

1. **Safe console text-insertion** — a vetted function that inserts text into the *correct* agent console (the legacy fleet's manual equivalent was error-prone: wrong window, lost keystrokes). Prerequisite for any mechanism that lets an observer or the boss inject a message into a working agent's session.
2. **Stuck/waiting-state detection** — detect interruptions and waiting states that require intervention: an agent that announced an action and went idle, a session waiting on input nobody knows about, a wedged worker. The smallest operator question ("which agent needs attention, and why?") depends on this.

## Relations

- The observers in the dynamic agent-team model (https://github.com/nedschorus/nedschorus/issues/26) need both halves: spies detect the stuck state; insertion is one delivery path for an expert's intervention.
- The Monitor-tool idle-wake verification probe (pair GHI [Dynamic agent-team model: sparring pairs, on-tap domain experts, spy-triaged oversight (design capture; research pending)](https://github.com/nedschorus/nedschorus/issues/26) § Open) overlaps: a verified wake mechanism may subsume part of the insertion need.
- Source material: pair GHI [Working ideas and research backlog — capture pair (Decided / Candidate / Research / Reference)](https://github.com/nedschorus/nedschorus/issues/10) § Status/monitoring backlog holds the sibling investigation notes.

## Added scope (walk 17 cluster 2, boss-ruled 2026-07-25)

- The announce-an-action-then-go-idle failure: legacy agents repeatedly announced work, went idle, and needed a second wake — investigate the mechanism as part of stuck/waiting detection (it is the highest-frequency observed instance of the class).
- First step of the detection work: VERIFY supported session/runtime state before building anything — the `~/.claude/sessions/<pid>.json` values (idle/busy/shell/waiting) are hypotheses to test against the current runtime, not a stable contract; prefer supported APIs or a versioned adapter.

## Close condition

Closes when both capabilities exist as tested tools, or when the team-model build supersedes the need.

—
Session: 23789ca5-e422-422a-bb1d-f03616746770 (new-vp)



**Operator-console rule (2026-08-17, learned twice in one day):** never synthesize keystrokes into a surface the operator may be typing at — the keystrokes race his and splice. This killed a box-seat catch-up via tmux `paste-buffer` (rule there: inject only when `#{session_attached}` is 0, evidence on GHI [Claude turn/start and turn/steer equivalents: inject a message into an idle session, steer an active turn](https://github.com/nedschorus/nedschorus/issues/37)) and corrupted an iTerm2 window-open on the Mac the same day (`activate` + `write text` typed into the user's live cursor). The safe form passes the command as an argument, never as typing: iTerm's `create window with default profile command "…"` runs it as the session's process; tmux's `new-session`/`respawn-pane` take the command the same way.

**The rule is enforced machinery since 2026-08-17** (PR https://github.com/nedschorus/nedschorus/pull/82, on main at 55cbb23, hardened across three merge-lane review rounds): `scripts/synthetic-keystroke-guard-hook.py`, a PreToolUse Bash hook wired in `.claude/settings.json`, denies AppleScript synthetic typing (`write text`, System Events `keystroke`/`key code`) and tmux keystroke writes at attached or unverifiable targets, teaching the safe form in each error; `scripts/open-iterm-window-running-command` is the vetted window-opener (capability 1's window-opening slice, delivered). Open edges, disclosed in the guard's docstring and left by choice — the guard corrects habit, it does not defend against evasion: custom xargs placeholders (`-I@` probes the literal text; only `{}` is recognized as a placeholder) and scripts fed to a shell's stdin (`echo ... | sh`) pass through.
