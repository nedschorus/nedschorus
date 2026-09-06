# Claude Code changes relevant to nedschorus, 2026-08-17 to 2026-08-31

Scope: Claude Code CLI releases only. Anthropic API and model-side changes in
the same window were not surveyed.

Window: versions 2.1.234 (published 2026-08-17) through 2.1.252 (published
2026-08-31). Version-to-date mapping from the npm registry
(`npm view @anthropic-ai/claude-code time --json`); entry text from
`https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md`.

## 0. Which of these you actually have

Measured 2026-08-31:

| Where | Version | Published | Missing |
|---|---|---|---|
| Mac (`/opt/homebrew/bin/claude`, Homebrew cask) | 2.1.241 | 2026-08-22 | 2.1.243 onward — 8 releases |
| Ubuntu box (`~/.local/bin/claude`) | 2.1.246 | 2026-08-25 | 2.1.247 onward — 5 releases |
| Latest published | 2.1.252 | 2026-08-31 | — |

The box additionally has 2.1.243, 2.1.245 and 2.1.246; neither machine has
2.1.247 onward. A seat's behavior therefore depends on which machine it runs
on.

Two facts about the Mac worth checking before the next launch:

- The Mac's `claude` is a Homebrew cask (`/opt/homebrew/bin/claude` ->
  `/opt/homebrew/Caskroom/claude-code@latest/2.1.241/claude`). That cask has not
  moved since 2026-08-24 even though `scripts/launch-claude-mac:155` runs
  `claude update` at every launch. Open question, not yet tested: whether
  `claude update` can advance a Homebrew-cask install at all. Worth settling
  before the next Mac seat launch — but running `claude update` changes what
  every subsequent Mac session runs, merge-lane included, so it is your call,
  not a seat's.
- `~/.local/bin` precedes `/opt/homebrew/bin` in PATH and currently holds no
  `claude`. If `claude update` ever installs there, it shadows the cask and the
  Mac silently switches install paths mid-fleet.

The launch-time update is the fleet's only update moment
(`DISABLE_AUTOUPDATER=1` in `.claude/settings.json`, user-ruled 2026-08-22),
so a machine whose `claude update` is a no-op stops advancing entirely.

## 1. Fixes to things this project recorded as problems

### Already on both machines (2.1.234-2.1.241)

- **2.1.238 — custom, project, and plugin output styles no longer drift back to
  the default voice mid-session.** This project sets
  `"outputStyle": "Zero-Context Explanation"` in `.claude/settings.json`, so
  every seat was exposed to this.
- **2.1.239 — hooks no longer fail with `posix_spawn ENOENT` after the
  session's working directory is deleted; they run from the project root or
  home directory instead.** Seat homes are git worktrees, and a worktree
  removed under a live session is a named fleet hazard
  (`docs/cross-project/fleet-git-worktree-working-model.md`).
- **2.1.239 — a session whose title starts with `/` was unaddressable by
  `SendMessage` and showed as "(untitled)" in `ListAgents`.** Seat-session
  names are the fleet's SendMessage addresses
  (`docs/wiki/queue/213-project-vocabulary.md:92`).
- **2.1.239 — `ListAgents` now tells a session its own name**, the one peers use
  to reach it, and `SendMessage` to your own name says so instead of "no agent
  named …". The same vocabulary entry records seat-session naming as a live
  convention with no written rule, so a seat that can state its own address is
  operationally useful here.
- **2.1.234-2.1.238 — cross-session messaging stopped failing silently.** Four
  separate silent-drop paths now report: a session that refuses inbound
  messages reports "refused" instead of a false success (2.1.238); an inbox
  that drops messages on rate limit or a full queue tells the sender (2.1.238);
  oversized messages are refused up front instead of vanishing (2.1.235); a
  burst that would exceed the recipient's inbox is refused up front (2.1.236);
  and `ListAgents`/`SendMessage` now say when the account's session list was too
  long to check completely rather than treating unseen sessions as absent
  (2.1.234).
- **2.1.238 — unbounded memory growth in long interactive sessions** (subagent
  tool results are released once they leave the display window). Seats are
  long-lived by design.
- **2.1.236 — terminal tab titles jumping in tmux under iTerm's tmux
  integration**, previously re-animated every 960ms. The launchers set
  `set-titles-string '#S'` (`scripts/launch-claude-mac:345`).
- **2.1.234 — Claude Code continues a session automatically when a claude.ai
  usage limit resets.** Matters for unattended seats; turn it off in `/config`
  if a supervisor should own that decision instead.

### On the box only (2.1.243-2.1.246) — the Mac does not have these

- **2.1.243 — sessions going silent for 10+ minutes when the Anthropic API
  never starts a response.** The request now times out after ~3 minutes,
  retries once, then shows `API Error: No response from API`. This is one
  concrete cause of the wedged-session class in
  `docs/issues/queue/27-wedged-session-never-recycles.md`, removed at the
  source.
- **2.1.243 — hook `if` conditions like `Bash(cat *)` firing on unrelated Bash
  commands** when the command contained `$()` or backticks followed by more
  arguments. This project matches PreToolUse hooks on `Bash`.
- **2.1.243 — cross-session messaging silently turning off inside user
  namespaces and rootless containers** after the 2.1.232 socket hardening.
- **2.1.246 — resumed sessions failing every turn with a 400 when the saved
  history contains tool blocks the API does not accept.** Not the same cause as
  the advisor-in-flight-fork 400 recorded in memory (that one is a transcript
  fork, not a proxy-written block), but adjacent enough to re-test.
- **2.1.246 — `/fork` from an already-forked or backgrounded session starting
  the new session with an empty conversation.**
- **2.1.246 — the background retention sweep removing git worktrees under
  `.claude/worktrees/` that you created yourself.**
- **2.1.246 — a `keybindings.json` binding with an unknown action name silently
  deadening that key**; it is now skipped so the default keeps working.

### On neither machine yet (2.1.247-2.1.252) — the strongest set

- **2.1.247 — a hook or background agent that printed megabytes of error output
  could overflow the conversation and wedge the session on "Prompt is too
  long".** This is the most on-point item in the whole window for issue #27: a
  named, reproducible cause of a wedged session, removed. This project runs
  six hooks (two `Stop`, four `PreToolUse`).
- **2.1.248 — hooks silently treating a stdout `{…}` object that isn't valid
  JSON as plain text; it is now reported as a hook error with the parse
  message.** Two of the six hooks answer with a JSON object on stdout —
  `scripts/synthetic-keystroke-guard-hook.py` (a `permissionDecision` in
  `hookSpecificOutput`) and `scripts/checkout-freshness-catch-up.py` — so a
  malformed payload from either used to pass unnoticed.
- **2.1.248 — a prompt-cache miss roughly once an hour in long sessions**,
  caused by tool definitions being re-rendered after an OAuth token refresh.
  Silent cost on every long-running seat.
- **2.1.248 — `ScheduleWakeup`'s tool definition changing between a session and
  its `--resume`** when the account had entered usage overage, causing a full
  prompt-cache miss on the resumed session's first turn.
- **2.1.248 — an invalid `crossSessionInbound` value being silently ignored**;
  it now warns (user settings) or refuses (managed settings).
- **2.1.251 — conversations getting stuck on "text content blocks must be
  non-empty" after a turn where the model produced only thinking.** Another
  wedge cause.
- **2.1.251 — selecting text in an opened background session inside tmux over
  SSH** now copies to the tmux buffer instead of falling back to OSC 52; and
  italic text such as the session recap line no longer renders as highlighted
  blocks in tmux sessions using a `screen` terminal type. The box is reached
  over SSH inside tmux.
- **2.1.251 — file tools following a symlink swapped inside the working
  directory after the permission check**, and **Grep/Glob not applying
  `Read(...)` deny rules to files reached through a symlinked search path.**
  Relevant to the three write guards in `.claude/hooks/`.
- **2.1.252 — Bash commands failing with "task output swap refused (tasks dir
  moved or linked)" on some Macs.**
- **2.1.252 — background task notifications with very large failure output**
  making the conversation exceed the API request size limit.

## 2. New capabilities worth a decision

- **`notify_when_idle` on cross-session `SendMessage`** (2.1.236 — you have it
  on both machines). Ask another Claude Code session on this machine to send
  one notice when it next goes idle. Opt-in, one-shot, no polling, macOS and
  Linux. This is a seat-to-seat coordination primitive the fleet does not
  currently use.
- **`PreModelSwitch` and `PostModelSwitch` hook events** (2.1.251 — not yet).
  Block, confirm, or annotate a model switch. Same shape as the existing
  instruction-file guard, applied to model changes.
- **`SessionStart` resume hooks receive session staleness and the estimated
  re-cache cost** (2.1.251 — not yet). Directly usable by the handoff
  supervisor's launch path.
- **`promptCacheTtl` and `subagentPromptCacheTtl` settings** (2.1.243 — box
  only). Keep a 1-hour prompt cache on the main conversation while subagents
  stay at 5 minutes.
- **`prompt_cache` object and `rate_limits.spend_limit` for status line
  scripts** (2.1.251 — not yet). `scripts/session-statusline-command.py` is
  documented as reading the payload fields of 2.1.220 and 2.1.226; these are new
  fields it could read.
- **`--restricted` / `CLAUDE_CODE_RESTRICTED=1`** (2.1.248 — not yet). Removes
  the tools that run commands or code and `WebFetch`, keeps file tools inside
  the working directory, refuses `bypassPermissions`, ignores settings files.
  Note this project runs `bypassPermissions` by default, so it is the opposite
  posture; it would suit a read-only reviewing seat, nothing else.
- **`SendFeedback` tool** (2.1.247 — not yet). Claude drafts a feedback report
  for you to review and send from `/feedback`.

## 3. What did not change

- **No stall or wedge detector.** Issue #27 stands. The window removed three
  specific causes (API never responding, hook output overflow, thinking-only
  turn) but not the class, and the `Stop` hook still fires only at turn end, so
  a session that never ends a turn still never reaches the recycle trigger.
- **Nothing about push notifications reaching the user.** `say` remains the
  channel.
- **Nothing about the memory read path.**
