# Session start is prompt-driven — a new use case for an idle-wake function

Boss observation (2026-07-22, at the day-3 successor wake): "I had to type stuff to wake up this agent. That may be the design, that agents always start in an ideal state. If that is true we have yet another use for an idle-wake function."

Verified from the successor's session JSONL (`135a4f6d`, first entries):

- `/clear` executed at `00:30:36.034Z`; the SessionStart hook (`handoff-pickup-inject.sh`) fired and its context landed as attachments at `00:30:36.2–36.4Z`.
- Zero assistant entries follow — the model was never invoked.
- The boss's typed prompt ("read handoff and continue") arrived at `00:30:48.975Z`, and only then did the first model turn start, with the hook context bundled into it.

Design fact: Claude Code turns are strictly user-initiated. A SessionStart hook injects context but cannot start a turn; the CLAUDE.md pickup line governs behavior once invoked, but nothing self-invokes. After `/clear` (or a fresh launch), the agent is dormant until a prompt arrives — the handoff-pickup automation is complete except for the first keystroke, which is still human.

Use case for the idle-wake function: at session mint (post-`/clear`, post-launch), send one synthetic first prompt (the pickup phrase suffices) so the successor boots without a human keystroke. This is the boot-ceremony analog of the retired mail-cron wake.
