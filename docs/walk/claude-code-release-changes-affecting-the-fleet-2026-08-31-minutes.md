# Minutes: Claude Code release changes affecting the fleet, 2026-08-31

## Item 1 — the two machines run different versions, and both are behind

open 2026-08-31 — item's claim revised mid-discussion; awaiting a ruling on
whether to run `brew upgrade --cask claude-code@latest` on the Mac.

Established in discussion:

- `claude update` was run at the start of this session. The Mac's only `claude`
  is the Homebrew cask, still 2.1.241, unchanged since 2026-08-24 12:49. The
  update therefore did not advance it. Measured 2026-08-31 18:36 PDT.
- A running session is unaffected by an update; code loads at session start.
  The item's claim is about what the NEXT Mac launch gets, not about live
  sessions.
- Why background auto-update is off: two separate decisions, not one. Issue #62's
  auto-update defect theory was RETRACTED on 2026-08-17 and the flag removed.
  The current `DISABLE_AUTOUPDATER=1` is a later, user-ruled decision of
  2026-08-22 on a different rationale — with launch-time updates the background
  check is redundant and its mid-session banner is clutter. It deliberately
  leaves explicit `claude update` working. Recorded at
  docs/cross-project/fleet-git-worktree-working-model.md lines 353-355 and
  527-539.

### Proven 2026-08-31 — `claude update` cannot advance this Mac, and reports success

Ran `claude update` on the Mac at the user's direction. Full output:

```
Current version: 2.1.241
Checking for updates to latest version...

Claude is managed by Homebrew.
Update available: 2.1.241 → 2.1.252

To update, run:
  brew upgrade claude-code@latest
```

Exit status: 0.

Two findings, the second previously unrecorded:

1. `claude update` will not install over a Homebrew-managed copy. It detects the
   new version, names the remedy, and declines. The Mac has therefore been
   frozen at 2.1.241 since 2026-08-24 while every launch appeared to update it.
2. It exits 0 when it declines. `scripts/launch-claude-mac:155-156` guards the
   update step with `|| echo "... failed or timed out ..."`, which fires only on
   a non-zero status. So the launcher prints NO warning in this case: the update
   step is silently inert on every Mac launch. The same guard is in
   `scripts/launch-claude-ubuntu`. Owned by the `fleet` seat.

Remedy for the Mac: `brew upgrade claude-code@latest`. Does not affect running
sessions; changes what the next session starts with.

processed 2026-08-31 → accepted, acted on.

`brew upgrade claude-code@latest` run at the user's direction. Result:
2.1.241 -> 2.1.252, binary relinked at /opt/homebrew/bin/claude, verified by
`claude --version`. Running sessions keep 2.1.241 until they restart; the next
Mac seat launch starts on 2.1.252.

Confirmed by grep that no launcher runs `brew`: the only update command in
either launcher is `claude update` (launch-claude-mac:155,
launch-claude-ubuntu:222), which is the command this Mac's install declines.

Remaining, carried into the walk as a new item: the exit-0 masking defect in
both launchers. The Ubuntu box is separately still on 2.1.246 with a native
install at ~/.local/bin/claude, where `claude update` should work; it needs a
relaunch, not a fix.

## Item 2 — both launchers treat a refused update as a successful one

processed 2026-08-31 → revised, then accepted and acted on.

The item as first presented proposed detecting the failed update in the
launcher. The user rejected that framing: an update should not fail. Correct
repair is to remove the mismatch, not to report it. Item rewritten around that.

Ruled and executed on the Mac, in this order, at the user's direction:

1. `curl -fsSL https://claude.ai/install.sh | bash -s latest` — installed the
   native build, 2.1.252, at ~/.local/bin/claude.
2. Verified `command -v claude` resolved to ~/.local/bin/claude before removing
   anything, so no window existed in which a spawning session would find no
   binary.
3. `brew uninstall --cask claude-code@latest` — removed the Homebrew copy.

Verified afterwards: one install remains; `claude update` now reports "Claude
Code is up to date (2.1.252)" instead of declining. The launcher's update step
works on the Mac with no edit to the script.

Supporting facts established:

- `~/.local/bin` is the location the fleet already assumed: launch-claude-mac
  line 291 exports PATH="$HOME/.local/bin:$PATH" for every supervisor. The
  Homebrew copy was the deviation, not the native one.
- `autoUpdatesChannel` is unset in user, project and ~/.claude.json settings, so
  the default channel `latest` applies. The alternative, `stable`, trails by
  about a week. The Homebrew cask's `@latest` suffix is Homebrew naming and is
  unrelated to the channel.
- Deleting a running program's file does not disturb the running process on
  macOS; the risk is only to processes spawned afterwards. Install-then-remove
  ordering removes that risk.

Residual, undecided: the launcher's `||` guard still cannot see an update that
fails while reporting success. No longer triggered on either machine, but latent
if any install becomes package-managed again. Owner would be the `fleet` seat.

Loose end: the Ubuntu box is still on 2.1.246 with a working native install. It
needs a relaunch, not a repair.

## Side work arising from items 1 and 2 — all user-ruled 2026-08-31

The walk paused after item 2 while the machine problems it uncovered were
fixed. Nine changelog items remain unpresented.

### Machines

- Mac: Homebrew cask removed, native build installed on the `latest` channel,
  2.1.252 at ~/.local/bin/claude. `claude update` now works there.
- Ubuntu box: already a native install and needing no repair; one `claude
  update` took it 2.1.246 -> 2.1.252.
- Both machines are on 2.1.252. Running sessions keep their old version until
  they restart; that is expected and was verified rather than assumed.
- The box was idle as the user said. Its two tmux sessions, `fleet-anchor` and
  `prof`, hold only after-exit bash shells — dead seats still holding their
  names. Not cleaned up; the user's call.

### PR #229 — launchers report only the failure they can see

https://github.com/nedschorus/nedschorus/pull/229

`|| echo "...failed or timed out..."` removed from both launchers: it fires
only on a non-zero exit, and `claude update` exits 0 when it declines to
overwrite a package-managed copy. The timeout is kept as the one case the
launcher can honestly report, discriminated by measured status — 142 on the
Mac's perl alarm, 124 from GNU timeout on the box. Timeout default raised
45 -> 120 seconds. The `||` itself is load-bearing under `set -eu` and under the
box's `&&` chain, so it stays.

### PR #230 — the Mac launcher updates the claude the seat will run

https://github.com/nedschorus/nedschorus/pull/230

`export PATH="$HOME/.local/bin:$PATH"` added above the prerequisite checks. The
launcher exported it for the supervisor but not for its own check and update,
so it updated one copy while the seat ran another. Reviewed as merging cleanly
and coherently with #229.

### The catch-up hook — landed merge reclassified as an attention state

Branch `catch-up-hook-reports-a-landed-merge-to-the-agent`, in review.

`scripts/checkout-freshness-catch-up.py` merged origin/main into this seat's
topic branch at a turn end; a following `git commit --amend` landed on the
merge commit and absorbed PR #227's file into this session's authorship. Caught
by reading a diffstat, which is not a control.

The hook's message was already correct and already addressed to the agent. It
was printed to the display, which the hook's own docstring records the agent
never reads. A landed merge is now an attention state (decision:block), the
message names the amend hazard, and hook stdout is queued and dispatched on one
channel — a JSON object plus a plain line is neither, and the reference
checkout always has something to say on exactly the runs where a merge lands.
The pre-existing failed-abort attention state had that same defect.

## Walk resumed 2026-09-01 at item 3 of 11

Item 3's version-currency sentence was corrected before presenting: it claimed
neither machine had 2.1.247 or 2.1.251, which the night's machine work made
false. Both now run 2.1.252.

## Item 3 — three causes of a wedged session fixed upstream

processed 2026-09-01 → rejected. No note added to
docs/issues/queue/27-wedged-session-never-recycles.md. The three fixes
(2.1.243 API-silence timeout, 2.1.247 hook-output overflow, 2.1.251
thinking-only turn) are recorded here and in the walk's findings companion;
nothing was written to the issue queue. Nothing else to capture.

## Item 4 — cross-session messaging stopped failing silently

processed 2026-09-01 → accepted, no action (the item's own recommendation).
Six silent-drop paths in SendMessage/ListAgents became reported failures
across 2.1.234-2.1.239; all were already on both machines. Nothing to
capture beyond the walk record.

## Item 5 — broken hooks now announce themselves

processed 2026-09-01 → accepted, no action (the item's own recommendation).
2.1.248's two hook fixes are live on both machines and are what make PR #231's
single-channel rule enforceable: a malformed JSON object on hook stdout is now
a reported error rather than silently treated as text. Nothing to capture
beyond the walk record and #231, which already states it.

## Item 6 — notify_when_idle, and what an arriving message does to a busy agent

processed 2026-09-01 → accepted, no action. Original recommendation (route to a
`fleet` seat) withdrawn: that seat model is theory, not a running arrangement.

Two facts established from the SendMessage tool contract rather than by
experiment, both correcting what the item first said:

- `notify_when_idle` does not delay delivery. It is a one-shot subscription for
  a notice back to the SENDER when the recipient next goes idle or exits.
  Omitting `message` subscribes without delivering anything.
- An arriving cross-session message does NOT interrupt a busy recipient.
  Messages "enqueue and drain at the receiver's next tool round" — not mid-call,
  and not held until fully idle.

User's inference, agreed with one asymmetry: an idle notice implies the message
was processed; the ABSENCE of a notice implies nothing, since the subscription
can expire unfired if the recipient stays busy, refuses inbound messages, or
ends abruptly.

Left unmeasured, offered and not taken up: how long "next tool round" can be for
an agent inside one long-running tool call. If delivery waits for that call to
return, a mid-command seat is indistinguishable from a wedged one — the same
discrimination problem as nedschorus#27. A canary seat would settle it.

## Item 7 — the custom voice no longer drifts back to default mid-session

processed 2026-09-01 → superseded by the discussion it opened, which ended in
the style being deleted (PR #232). The 2.1.238 fix stands and is on both
machines; it is simply moot for this project now.

What the side thread established, all verified from the 2.1.252 binary rather
than inferred, and captured durably in
docs/drafts/claude-code-output-styles-survey.md:

- There are five built-in styles, not three: Default, Proactive, Concise,
  Explanatory, Learning. Explanatory and Learning also exist as official plugins
  that recreate them via SessionStart hooks.
- "Default" has no prompt. It is the ABSENCE of a style — the name and its
  description are fallback values used when no style object exists.
- The per-turn reminder line is composed as `<style> output style is active.
  <turnReminder ?? generic sentence>`. Only Proactive and Concise supply a
  turnReminder.
- A custom style CANNOT supply one. The output-style frontmatter schema accepts
  exactly name, description, keep-coding-instructions, and the internal
  force-for-plugin, and is registered .strict(). `turn-reminder` does not occur
  anywhere in the binary.
- A style's text sits in the system prompt: present in every request, never
  repositioned, so it loses to recency as a session grows. The reminder's value
  is position, not repetition.
- A UserPromptSubmit hook emitting hookSpecificOutput.additionalContext can add
  a second contentful line per prompt, but cannot replace the style machinery's
  own line, and lives in settings.json rather than travelling with the style.

Ruling: the custom style is removed, leaving no style selected. Concise was
considered and not chosen. Walked approval taken and recorded.

## Item 8 — the recurring prompt-cache miss

processed 2026-09-01 → rejected. No cache-health field added to
scripts/session-statusline-command.py.

The 2.1.248 fixes themselves need nothing: the hourly cache miss and the
ScheduleWakeup resume miss both stopped on both machines with tonight's update
to 2.1.252. Only the optional status-line indicator was declined; cache health
stays invisible by choice.

## Item 9 — two new hook capabilities (PreModelSwitch/PostModelSwitch, SessionStart staleness)

processed 2026-09-01 → accepted, no action. Both are live on both machines.
Neither was proposed as work: no incident in this fleet involved a model switch,
and nothing the handoff supervisor currently decides would change if it read
session staleness or re-cache cost. Recorded only so the instruments are known
to exist if such a problem ever appears. Original routing to a `fleet` seat
withdrawn — that seat model is theory.

## Item 10 — three tmux fixes

processed 2026-09-01 → accepted, no action. All three live on both machines
(2.1.236 tab-title churn since 19 August; 2.1.251 SSH text selection and
screen-type italics as of tonight). Listed so changed tmux behavior is read as
these landing rather than as a new fault.

## Item 11 — what did not change

processed 2026-09-01 → accepted, no action. Nothing in the window addressed the
three standing problems: no stall or wedge detector (nedschorus#27 unchanged,
its structural gap intact — the recycle trigger is a Stop hook and a session
that never ends a turn never fires it), no change to push notifications
reaching the user (`say` remains the only channel), and no change to the memory
read path. Yielded no capture: the item exists to record an absence.

## Walk closed 2026-09-01

All 11 items processed. Two rejected (items 3 and 8), one superseded (item 7),
the rest accepted with no action.

Nothing is left open. One offer was made and not taken up — a canary seat to
measure how long "the receiver's next tool round" can be for an agent inside a
single long-running tool call, which bears on telling a mid-command seat from a
wedged one. It is recorded under item 6 rather than carried forward as a task,
because it was a proposal rather than an unanswered question.

The walk's substantive output was not the changelog findings, most of which were
already fixed and owed nothing. It was item 1, which sent us to look at the
machines. Four pull requests came out of that: #229, #230, #231, #232.
