# Walk: Claude Code release changes affecting the fleet, 2026-08-31

Subject: what Claude Code shipped between 2026-08-17 and 2026-08-31 that
touches this project, and what it fixed that we had recorded as a problem.

Source data: the published Claude Code changelog,
[Claude Code CHANGELOG](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md),
covering versions 2.1.234 through 2.1.252. Version-to-date mapping came from the
npm registry publish times. Scope is the Claude Code command-line tool only; API
and model changes in the same period were not surveyed.

Full findings, item by item, in
[the findings companion](file:///Users/el/agents/reboot-test/docs/walk/claude-code-release-changes-affecting-the-fleet-2026-08-31-findings.md).

11 items.

---

## Item 1 of 11: The two machines run different versions, and both are behind

Claude Code publishes several releases a week. I measured what each of our two
machines is running today, 2026-08-31.

- The Mac runs 2.1.241, published 2026-08-22.
- The Ubuntu box runs 2.1.246, published 2026-08-25.
- The newest published version is 2.1.252, released today.

That means the Mac is missing eight releases and the box is missing five. It
also means a seat behaves differently depending on which machine it runs on.

There is a specific reason to suspect the Mac is stuck rather than merely
lagging. The Mac's `claude` program is a Homebrew cask: the command
`/opt/homebrew/bin/claude` is a symbolic link into
`/opt/homebrew/Caskroom/claude-code@latest/2.1.241/`. That directory has not
changed since 2026-08-24. Meanwhile every Mac seat launch runs `claude update`,
at line 155 of
[launch-claude-mac](file:///Users/el/agents/reboot-test/scripts/launch-claude-mac).
Launch-time updating is the fleet's only update moment, because background
auto-update is switched off in
[project settings](file:///Users/el/agents/reboot-test/.claude/settings.json).

So one of three things is true, and I have not tested which: `claude update`
cannot advance a Homebrew-installed copy; it is failing quietly inside its
45-second timeout; or it is installing somewhere else. The third is possible
here — the directory `~/.local/bin` comes before Homebrew's on the search path
and holds no `claude` today, so a copy installed there would take over silently.

The Ubuntu box updates the same way, through `claude update` in its own
launcher, and it is five releases behind. Whatever the Mac's cause turns out to
be, the box needs a relaunch to advance.

My recommendation: I do not run `claude update` myself. It changes what every
later Mac session runs, including the merge-lane seat, so the timing is yours.
Say the word and I will run it and report what happens.

---

## Item 2 of 11: Why the Mac stopped updating, and what to do about it

Here is what happened on this Mac.

On 24 August 2026, Claude Code 2.1.241 was installed here by Homebrew.

Every seat launch since then ran `claude update` — line 155 of
[launch-claude-mac](file:///Users/el/agents/reboot-test/scripts/launch-claude-mac).
That command looked for a newer version, found one, and stopped. It printed
"Claude is managed by Homebrew" and said to run `brew upgrade` instead. Then it
reported success.

The launcher prints a warning only when that command reports failure. It saw
success, printed nothing, and started the seat on 2.1.241. Fifteen seats
launched that way today alone.

Half an hour ago we ran `brew upgrade claude-code@latest` by hand. It took
seconds. The Mac now runs 2.1.252.

The cause: a Mac can hold Claude Code two ways — Homebrew installs it, or
Claude's own installer does. `claude update` only replaces copies that Claude's
own installer put there. It refuses to overwrite Homebrew's copy deliberately:
two programs writing one file is a mess Homebrew cannot track.

The Ubuntu box holds Claude's own install, at `~/.local/bin/claude`, so
`claude update` works there. Only the Mac is mismatched.

Two ways to fix it for good:

- Remove Homebrew's copy and run Claude's own installer on the Mac. It lands in
  `~/.local/bin/claude`, which already comes first in this Mac's search path, so
  it takes over even if the Homebrew copy lingers. Confirm with `which claude`
  and `claude --version`.  The launcher then works unchanged on both machines.
- Keep Homebrew's copy, and teach the launcher to run
  `brew upgrade claude-code@latest` here.

My recommendation: the first. One install method on both machines, and no new
logic in the launcher.

---

## Item 3 of 11: Three causes of a wedged session were fixed upstream

We have an open issue about a session that stops making progress and never
recovers: nothing notices, because the only recycle trigger is context growth
and a stalled session never reaches it. The issue is
[nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27), and the
analysis lives in
[27-wedged-session-never-recycles](file:///Users/el/agents/reboot-test/docs/issues/queue/27-wedged-session-never-recycles.md).

Three separate causes of exactly that failure were fixed in this two-week
window.

1. Version 2.1.243: a session could go silent for ten minutes or more when the
   Anthropic API never began sending a response. The request now gives up after
   about three minutes, retries once, then reports `API Error: No response from
   API`.
2. Version 2.1.247: a hook or a background agent that printed megabytes of error
   output could overflow the conversation and jam the session on the error
   "Prompt is too long". This one matters here — we run six hooks.
3. Version 2.1.251: a conversation could get permanently stuck on the error
   "text content blocks must be non-empty" after a turn in which the model
   produced only thinking and no text.

None of these is a stall detector. They remove three named ways a session could
wedge; they do not close the issue.

My recommendation: add a short note to the queue document naming these three
causes and the version that fixed each. Version numbers matter, because a cause
is gone only on a machine running that version or later. Both machines now run
2.1.252, so all three are gone here — but a session started before the update
still carries the old code, and a machine can fall behind again. The note saves
whoever designs a stall detector from spending effort on causes that no longer
exist. I can write it now.

---

## Item 4 of 11: Messages between sessions stopped failing silently

Seats talk to each other with the `SendMessage` tool, addressing each other by
session name. The project vocabulary document records this as a live convention:
see
[213-project-vocabulary](file:///Users/el/agents/reboot-test/docs/wiki/queue/213-project-vocabulary.md).

Across five releases in this window, six ways that a message could vanish
without telling the sender were turned into reported failures.

- 2.1.234: `ListAgents` and `SendMessage` now say when the account's session
  list was too long to check completely, instead of reporting unseen sessions
  as absent.
- 2.1.235: a message too large to deliver is now refused up front instead of
  being dropped.
- 2.1.236: a rapid burst that would overflow the recipient's inbox is now
  refused up front instead of being reported as sent.
- 2.1.238: a session that refuses inbound messages now reports "refused" to the
  sender, instead of reporting a false success.
- 2.1.238: an inbox that drops messages because of a rate limit or a full queue
  now tells the sending session.
- 2.1.239: a session whose name begins with a slash was unreachable by
  `SendMessage` and displayed as "(untitled)".

All six are already on both machines. The practical effect: when a seat messages
another seat and gets no reply, you can now believe the tool when it says the
message was delivered.

My recommendation: no action. This is worth knowing, not worth building on.

---

## Item 5 of 11: Broken hooks now announce themselves

This project runs six hooks — small programs Claude Code executes at fixed
moments, such as before a file write or when a turn ends. They are listed in
[project settings](file:///Users/el/agents/reboot-test/.claude/settings.json).
A hook answers by printing a JSON object on its standard output.

Two of our six answer that way: the synthetic-keystroke guard, which prints a
permission decision, and the checkout-freshness catch-up.

Version 2.1.248 fixed two silent failures in that path.

- A hook that printed something starting with `{` that was not valid JSON was
  silently treated as ordinary text. The hook appeared to run and its answer was
  ignored. It is now reported as a hook error, with the parsing message.
- A background session whose permission hook printed an invalid answer used to
  wait forever with no explanation. The session row now names the hook and the
  schema error.

Two related fixes landed nearby. Version 2.1.243 stopped hook conditions such as
`Bash(cat *)` from matching unrelated commands that happened to contain a
`$(...)` substitution. Version 2.1.239 stopped hooks failing with
`posix_spawn ENOENT` when the session's working directory had been deleted —
they now run from the project root instead. That last one matters because every
seat's home is a git worktree, and a worktree removed under a live session is a
hazard we have already recorded.

Both 2.1.248 fixes went live on both machines with tonight's update to
2.1.252.

That is load-bearing for the catch-up hook change in PR #231, not incidental.
That hook now emits a JSON object on stdout, and under 2.1.248 a malformed one
is a reported hook error rather than silently treated as text. The stricter
parsing is what makes the single-channel rule enforceable rather than merely
intended.

My recommendation: no action. Expect our hooks to fail more loudly than they
used to, which is the direction we want.

---

## Item 6 of 11: A seat can now be told when another seat goes idle

Version 2.1.236 added an option called `notify_when_idle` to the `SendMessage`
tool. When one session messages another session on the same machine, it can ask
to be sent a single notice the next time that session goes idle. It is opt-in,
it fires once, and it requires no polling. It works on macOS and Linux, so both
our machines qualify. Both machines already have it.

What it answers is a question this fleet asks constantly and currently answers
by hand: "is that seat finished yet?"

Three honest limits. First, "idle" means the session finished its turn and is
waiting for input. A wedged session that never finishes a turn never goes idle,
so this is not a stall detector and does not close
[nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27). Second, it
works only between sessions on the same machine. A Mac seat cannot watch a box
seat, and there is no equivalent that crosses machines — the two share no
session state at all. Third, what happens when the recipient is already idle at
the moment of the request is not stated in the release note, and I have not
tested it.

Where it would fit: a seat that has handed work to another seat and wants to
know when that seat is free, without you relaying the answer.

My recommendation: no action. My first draft routed this to a `fleet` seat to
weigh later; the seat model that names one is theory rather than a running
arrangement (user, 2026-08-31), so there is nowhere to file it. A capability
with no owner is either used or it is not, and nothing is blocked on it today.

If you want the third unknown closed, I can test `notify_when_idle` against a
throwaway session on this Mac — not a working seat — and report what happens
when the recipient is already idle. That is the only part of this I cannot tell
you from the release note.

---

## Item 7 of 11: The custom voice no longer drifts back to default mid-session

This project sets a custom output style, "Zero-Context Explanation", in
[project settings](file:///Users/el/agents/reboot-test/.claude/settings.json).
An output style is the instruction block that sets how a session writes — in our
case, standard software terminology, before-and-after text for proposed edits,
and a direct register.

Version 2.1.238 fixed a defect where custom, project, and plugin output styles
drifted back to the default voice partway through a session. The session kept
running; it simply stopped writing the way it was configured to write.

Every seat we run was exposed to this, because the style is set at the project
level and applies to all of them. The symptom would have looked like an agent
becoming chattier or vaguer as a session went on, which is easy to attribute to
the model rather than to a configuration defect.

Both machines already have this fix.

My recommendation: no action. I raise it because if you noticed seats losing
their voice over long sessions before 2026-08-20, that was a real defect and it
is now fixed.

---

## Item 8 of 11: A recurring hidden cost in long sessions was fixed

The prompt cache is the mechanism that lets a long conversation be re-sent
cheaply: unchanged leading content is billed at a reduced rate instead of in
full. When the cache misses, the whole conversation is re-processed at full
price.

Version 2.1.248 fixed a cache miss that happened roughly once an hour in long
sessions. The cause: after the sign-in token refreshed, the tool definitions
were re-rendered, which changed the leading content and invalidated the cache.
Our seats run for hours, so this was a repeated, invisible cost on every one of
them. The same release fixed a related miss where the `ScheduleWakeup` tool's
definition changed between a session and its resume, costing a full cache miss
on the resumed session's first turn.

Both fixes arrived with tonight's update to 2.1.252, so the recurring cost has
already stopped on both machines. Nothing is owed on that half.

Version 2.1.251 also added new fields that a status line script can read: a
`prompt_cache` object reporting hit ratio, misses, tokens re-cached, and whether
the cache is warm or cold. Our status line is
[session-statusline-command](file:///Users/el/agents/reboot-test/scripts/session-statusline-command.py),
and its own documentation says it reads the payload fields of versions 2.1.220
and 2.1.226. These are newer fields it could read.

My recommendation: add a cache-health field to the status line. The condition I
originally set — wait until both machines are updated — is now met, so this is
buildable today rather than deferred. Cache misses are pure cost and currently
invisible, and the status line is the one surface every seat already shows.

One constraint on the design: the script deliberately does not show everything
available to it. Line 47 lists fields it omits on purpose. Any addition has to
earn a place under that existing policy rather than be appended because the
field exists.

---

## Item 9 of 11: Two new hook events worth knowing about

Version 2.1.251 added two hook capabilities. Both machines have them as of
tonight's update, so they are available now rather than pending.

The first pair is `PreModelSwitch` and `PostModelSwitch`. A hook on these can
block, confirm, or annotate a change of model within a session. This is the same
shape as the guard we already run on file writes: the instruction-file guard
blocks edits to instruction files unless approval was recorded first. A model
switch is a comparable event — it changes which model a seat runs on, and today
nothing records or gates it.

The second is an addition to the existing `SessionStart` event. When a session
starts by resuming an earlier one, the hook now receives two new pieces of
information: how stale the session is, and the estimated cost of re-caching it.
That is directly relevant to the handoff supervisor, which launches seat
sessions and decides what to carry forward.

My recommendation: no action, and I am declining to propose either.

This project's own rule is that before proposing a guard I must name the
behavior it defends against — something these agents actually did, or concretely
will. For the model-switch hooks I cannot. No incident in this fleet involved a
model switch, and I am not going to argue for a gate from the fact that the
event now exists. The same applies to the SessionStart additions: the handoff
supervisor could read session staleness and re-cache cost, but nothing it
currently decides would change if it did.

Both are recorded here so that if a model switch or a stale resume ever does
cause a problem, the instrument is known to exist. That is the whole of what I
am proposing.

---

## Item 10 of 11: Three tmux-specific fixes

Every seat runs inside a tmux session, so terminal-level defects in tmux affect
every seat. Three were fixed in this window.

- Version 2.1.236 fixed terminal tab titles jumping under iTerm's tmux
  integration. The title had been rewritten every 960 milliseconds whether or
  not it changed; it is now written only when the text changes. Our launchers
  deliberately set the tab title to the seat name, at line 345 of
  [launch-claude-mac](file:///Users/el/agents/reboot-test/scripts/launch-claude-mac),
  so this is our configuration exactly. Already on both machines.
- Version 2.1.251 fixed selecting text inside a session running in tmux over
  SSH. The selection now copies into the tmux buffer as it does locally, rather
  than falling back to a terminal escape sequence that many setups ignore. The
  Ubuntu box is reached over SSH inside tmux, so this is our path. Live on both
  machines as of tonight.
- Version 2.1.251 fixed italic text — including the session recap line —
  rendering as highlighted blocks in tmux sessions that report themselves as
  terminal type `screen`. Live on both machines as of tonight.

My recommendation: no action. All three are already in place; I list them so
that tmux behaving differently than it did yesterday is read as these fixes
landing, not as a new fault.

---

## Item 11 of 11: What did not change

Three things this project cares about were untouched in the two-week window. I
state them so the absence is on the record rather than assumed.

First, there is still no stall or wedge detector. Issue
[nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27) stands
exactly as written. Three specific causes were removed, as covered earlier in
this walk, but the class remains, and the structural gap is unchanged: the
recycle trigger is a `Stop` hook, `Stop` fires when a turn ends, and a session
that never ends a turn never fires it.

Second, nothing changed about push notifications reaching you. The macOS `say`
command remains the only channel that gets your attention when you are working
in another seat's terminal.

Third, nothing changed about the memory read path — the recorded problem being
that memories are written and then not read at the moment they would matter.

My recommendation: no action. This item exists to close the question "did any of
this solve the things we most wanted solved?" The answer is no. What arrived is
a set of removed failure causes and better error reporting, not a new capability
in the areas we have open problems.
