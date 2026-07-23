# Session start is prompt-driven — a new use case for an idle-wake function

Boss observation (2026-07-22, at the day-3 successor wake): "I had to type stuff to wake up this agent. That may be the design, that agents always start in an ideal state. If that is true we have yet another use for an idle-wake function."

Verified from the successor's session JSONL (`135a4f6d`, first entries):

- `/clear` executed at `00:30:36.034Z`; the SessionStart hook (`handoff-pickup-inject.sh`) fired and its context landed as attachments at `00:30:36.2–36.4Z`.
- Zero assistant entries follow — the model was never invoked.
- The boss's typed prompt ("read handoff and continue") arrived at `00:30:48.975Z`, and only then did the first model turn start, with the hook context bundled into it.

Design fact: Claude Code turns are strictly user-initiated. A SessionStart hook injects context but cannot start a turn; the CLAUDE.md pickup line governs behavior once invoked, but nothing self-invokes. After `/clear` (or a fresh launch), the agent is dormant until a prompt arrives — the handoff-pickup automation is complete except for the first keystroke, which is still human.

Use case for the idle-wake function: at session mint (post-`/clear`, post-launch), send one synthetic first prompt (the pickup phrase suffices) so the successor boots without a human keystroke. This is the boot-ceremony analog of the retired mail-cron wake.

Prior art (old system): this is the known upstream idle-wake bug [anthropics/claude-code#44380](https://github.com/anthropics/claude-code/issues/44380) (OPEN, no fix) — an injected message is not processed by the idle REPL until a keystroke arrives. The old system's interim stand-in was per-session check-mail crons (currently off by boss order). See nedlern `docs/wiki/agent-runtime/session-lifecycle.md` § Mail delivery.

Second specimen, same day (evening, CDX side) — the ACK-then-idle variant: cgit accepted a T1 work order by postal ACK with a correct readback, ended its turn, and went dormant without beginning the accepted work; the boss had to prompt it ("is there a reason you are idle?") to resume. cgit's own assessment: "No valid reason. I stopped after sending the required acceptance instead of beginning the accepted T1 work order." Same structural gap in a second form: nothing re-invokes a dormant agent between turns, so an accepted-but-unfinished work order does not keep its agent running. Contributing cause, owned by the dispatcher (new-vp): the work order stated the response tier ("T1: at a clean stop, respond before new work of your own") but no work-start priority phrase — the tier governs response timing, not work start, and the canonical phrase for this case ("ASAP / preempt other work") was omitted. An idle-wake mechanism must not assume dispatch messages are well-formed; conversely, dispatcher discipline (explicit start priority in the body) shrinks but does not close the gap. The idle-wake use-case list so far: (a) session mint — boot the successor without a human keystroke; (b) resume-after-accept — re-invoke an agent whose last turn accepted or was assigned work that remains unfinished.
