<!-- provenance: runtime=codex model=gpt-5.6-terra effort=low cell=fast-clarify tier=floor duration_s=79 tokens=47237 target=docs/walk/claude-code-release-changes-affecting-the-fleet-2026-08-31-draft.md -->

# Suggestions: Claude Code release changes affecting the fleet, 2026-08-31

## 1. What it says

### Opening scope

The walk covers Claude Code CLI releases 2.1.234 through 2.1.252, published from 2026-08-17 through 2026-08-31, and excludes API and model changes. It reports ten findings about changes relevant to this project and links the full research record.

### Item 1 of 10: The two machines run different versions, and both are behind

The Mac runs 2.1.241 and is eight releases behind 2.1.252; the Ubuntu box runs 2.1.246 and is five releases behind, so seats can behave differently by machine. The Mac may be unable to update through its Homebrew installation or may time out silently during its launch-time update, and the author will test it only if the user directs that change.

### Item 2 of 10: Three causes of a wedged session were fixed upstream

Versions 2.1.243, 2.1.247, and 2.1.251 remove three particular causes of sessions wedging: an API response that never starts, excessive hook or background-agent error output, and a thinking-only turn producing an invalid empty text block. They do not provide a stall detector or close issue #27; the recommended action is to note the upstream fixes and versions in that issue’s queue document.

### Item 3 of 10: Messages between sessions stopped failing silently

Six failure modes in cross-session messaging now produce sender-visible errors rather than false success or silent loss, including incomplete session lists, oversized messages, inbox overflow, refusal, rate limiting or full queues, and slash-prefixed session names. Both machines have all of these fixes, so a reported delivery can be trusted even if the recipient does not reply; no action is recommended.

### Item 4 of 10: Broken hooks now announce themselves

Version 2.1.248 reports invalid JSON-looking hook output and explains invalid permission-hook answers that previously caused a background session to wait indefinitely; the project has two hooks that return JSON. Nearby releases also corrected hook-condition overmatching and hooks failing after their worktree disappears; the 2.1.248 fixes are not on either machine, and no action is recommended before updating.

### Item 5 of 10: A seat can now be told when another seat goes idle

The already-installed `notify_when_idle` SendMessage option can request one no-polling notification when a same-machine session next finishes its turn. It cannot identify a wedged session or work across machines; the document recommends recording it for the `fleet` seat to consider, without building anything now.

### Item 6 of 10: The custom voice no longer drifts back to default mid-session

Version 2.1.238 corrected custom project and plugin output styles reverting to the default partway through a session, a fault to which every project seat was exposed because the project sets the output style. Both machines have the fix, so no action is recommended; earlier apparent voice drift may have been this defect.

### Item 7 of 10: A recurring hidden cost in long sessions was fixed

Version 2.1.248 eliminates hourly prompt-cache misses after sign-in refresh and cache misses on the first resumed turn when the ScheduleWakeup definition changes, costs affecting the project’s long-running seats; neither fix is installed. Version 2.1.251 also exposes cache-health status fields that the status line could read, but the document recommends waiting until both machines update before considering that self-contained change.

### Item 8 of 10: Two new hook events worth knowing about

Version 2.1.251 adds hooks before and after a model switch, allowing the switch to be blocked, confirmed, or annotated, and adds resumed-session staleness and re-cache-cost data to SessionStart hooks. Neither machine has these capabilities; the `fleet` seat should be told they become available after an update, but no decision is proposed now.

### Item 9 of 10: Three tmux-specific fixes

All seats use tmux, so a fix for iTerm tmux title rewriting already applies to both machines, while fixes for SSH tmux selection and italic rendering in `screen`-type tmux sessions await an update. No action is recommended; changed tmux behavior after updating should not be treated as a new fault.

### Item 10 of 10: What did not change

The release window did not add a stall detector, improve user-facing push notifications beyond macOS `say`, or repair the path by which memories are read when relevant. Removed wedge causes and improved error reporting do not solve those open problems, so no action is recommended.

## 2. Where you stumbled

1. [question] "Full findings: [claude-code-changes-relevant-to-nedschorus](file:///private/tmp/claude-501/-Users-el-agents-reboot-test/21501c63-2dd6-4323-b38d-f7f4f58c7e6f/scratchpad/claude-code-changes-relevant-to-nedschorus-2026-08-17-to-08-31.md)" — How can a future reader with only this document access the linked temporary-path findings?

2. [question] "what a seat is" — What does “what a seat is” mean in the claim that a model switch changes it?

3. [question] "the handoff supervisor, which launches every seat session" — Does this include sessions started outside the supervisor, or only the sessions the supervisor itself launches?

## 3. What it does not cover

1. [no-rule] "So either `claude update` cannot advance a Homebrew-installed copy, or it is failing quietly inside its 45-second timeout." — What should the reader do if an update succeeds but installs or selects a different executable path, rather than fitting either stated explanation?

2. [no-rule] "Once both machines are updated" — What updates the Ubuntu box, and when, given that the document names only the Mac’s launch-time update path and asks the user only about updating the Mac?

3. [rule-conflict] "add a short note to the queue document recording these three as fixed upstream" — How should the queue note treat a cause that is fixed upstream but remains present on the Mac or both machines until their respective updates?

4. [no-rule] "it fires once" — What happens when `notify_when_idle` is requested after the recipient is already idle?

5. [no-rule] "a Mac seat cannot use it to watch a box seat" — What should a seat use when it needs the same completion notice from a seat on the other machine?

