# A wedged session trips nothing: the supervisor waits forever, and the only recycle trigger is context growth

Queued for [nedschorus#27](https://github.com/nedschorus/nedschorus/issues/27) (console text-insertion + stuck/waiting-state detection), whose captured scope already names "a wedged worker". Owned by the `fleet` seat (`docs/agents/fleet-instructions.md`), which owns the handoff supervisor and the session machinery.

Surfaced by the attack-split validation experiment of 2026-08-12 (`md-review-records/2026-08-12-attack-split-experiment/scorecard.md`, § Fresh-eyes yield), which called it "the sharpest operational gap in the set". Verified against the repository as it stands on 2026-08-13 by the `sanity-checker` seat.

## Confirmed by reading, and more definite than the finding claimed

The finding was recorded as a runtime claim that might not be settleable from code. It is settleable: the absence is structural, visible in the control flow, and does not depend on observing a stall.

**The supervisor's wait has no deadline.** `scripts/handoff-supervisor.py:402`, `wait_for_handoff`, loops on `time.sleep(HANDOFF_POLL_SECONDS)` (2.0s, line 51) with exactly two exit terms: a handoff file appearing on disk with a counter above the one already consumed, or `process.poll()` reporting the session gone. There is no third term. No elapsed-time bound, no last-activity check, no maximum. A session whose process is alive and which never writes a handoff is waited on indefinitely, by design of the loop as written.

**The heartbeat that exists measures the wrong thing.** `stamp_heartbeat` (line 93) and `supervisor_liveness` (line 99) stamp `last_poll_at` into the seat's state file every 10 seconds (`HEARTBEAT_INTERVAL_SECONDS`, line 60) and report a supervisor dead if its stamp is stale. That answers "is anyone watching this seat", which is a real question and correctly answered. It does not answer "is the watched session making progress" — the supervisor keeps stamping a healthy heartbeat while the session it watches is wedged, so the liveness signal reads green during exactly the failure this concerns.

**The only recycle trigger is context growth, and a wedged session cannot reach it.** `scripts/handoff-context-threshold-hook.py` computes the used-context share from the transcript's newest assistant record and fires the handoff skill above the threshold (default 50%, line 153). Two properties make it blind here: it fires on *context share*, so a session wedged while light never qualifies; and it is a `Stop` hook, so it runs when a turn ends — a session that never ends a turn never invokes it at all. Both halves of "wedged but under threshold" are uncovered.

Nothing else in the tree covers it. Search receipt: `grep -rln "watchdog" scripts/` returns nothing at all, and `grep -rn "wedged\|stalled\|no-progress" scripts/` returns one substantive hit, discussed next — no script anywhere bounds a session's idle time.

## The one recorded stall in the tree had a specific cause, and it was closed by diagnosis

`scripts/handoff-write-and-check-supervisor.py:95-105` documents the only stall this project has written down. A supervisor takes over a seat by killing the session and launching a successor; a console seat survives that, but the Claude desktop app's conversation pane does not, because its session process is a child of the app bundle and a successor launched by a detached supervisor has no seat at all. Observed 2026-08-11: "the successor ran its first turn and stalled at the first need for the user." The fix was not a watchdog — it was `app_hosted_ancestry`, which walks the process ancestry for `Claude.app` and refuses the takeover for panes that cannot survive it.

That instance is a wedged session in the sense this document means, so the class is not hypothetical. But it cuts against a generic detector as the first move: the one stall anyone recorded had an identifiable cause, and naming the cause produced a guard that prevents it, where an idle-timer would only have noticed it afterwards. Worth weighing when the response policy is chosen.

## What reading cannot settle, and is left open deliberately

How often sessions wedge *without* such a cause, and how long a real stall runs before someone notices. Those are runtime facts about this fleet, not properties of the code, and no code-level test manufactures them. **Frequency is the whole question of whether this deserves machinery**, because the project's standing bar is that a detector with no consumer is cost without value — and the consumer here is the user noticing a dead pane, which he already does by looking. What is established is only that the mechanism is absent; whether its absence costs anything is unmeasured.

Cheapest way to measure before building: the supervisor already writes `~/.claude/handoffs/<seat>-supervisor-state.json` on a 10-second cadence, so recording the watched session's last transcript-write time alongside the existing stamp would produce the frequency data at near-zero cost and commit to no policy. That is a measurement, not the detector.

**Next action for the `fleet` seat.** Put the frequency question to the user before designing anything, and note that #27's first-step ruling already applies: that issue records (boss-ruled 2026-07-25) that session/runtime state values are "hypotheses to test against the current runtime, not a stable contract", and that verification precedes building. A stall detector's hard part is the same one that defeated the one-session-per-directory guard in `docs/issues/queue/45-session-seat-and-isolation-riders.md` § 1 — the process table lies about what a session is doing — so the detection method, not the response policy, is where the design effort goes. If it is built, the response is the interesting choice: an idle bound that recycles resembles a timeout on a thinking agent, and killing a slow-but-working session is a worse failure than leaving a wedged one for the user to spot.
