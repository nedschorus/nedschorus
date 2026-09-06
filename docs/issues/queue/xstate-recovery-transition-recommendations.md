---
status: research recommendations
research-as-of: 2026-09-06
disposition: queued for user review
---

# XState: separate recovery decisions from their effects

**Borrow the pure transition idea in Python. Adding a JavaScript state-machine dependency to the existing recovery scripts is not the smallest change.**

The concrete consumers are the six ruled changes in [#242](https://github.com/nedschorus/nedschorus/issues/242) and the login-recovery program in [#116](https://github.com/nedschorus/nedschorus/issues/116). The first records observed failures: recently killed supervisors are misclassified by heartbeat age; clean exits and crashes need distinct handling; and a successful launcher exit can be mistaken for a successfully resumed seat.

The exact external reference is [XState's pure transition functions](https://stately.ai/docs/pure-transitions). Its transition function computes a new state and a list of intended actions without executing those actions. Its [event objects](https://stately.ai/docs/transitions#event-objects) carry a type and optional data. Those are useful structural examples; NC does not need XState's full actor lifecycle to use them.

The local attachment points are [scripts/recover-crashed-seats.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/recover-crashed-seats.py) — assess_seat, recover_seat, and launch_seat — and [scripts/handoff-supervisor.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/handoff-supervisor.py) — supervisor_liveness, read_supervisor_state, and write_supervisor_state. There is already a partial separation: assess_seat returns a verdict, while recover_seat performs launches. However, assess_seat also gathers evidence by probing tmux, process locks, supervisor state, occupancy, and transcripts.

As the existing recovery changes are built, collect the relevant observations into one record and let a small decision function choose the action. Keep observation collection and action execution outside that function. This makes the same decision logic usable by the manual recovery command and login recovery without duplicating their policy.

The observations come from the approved design: verified process identity, clean-exit record, parked marker, unconsumed handoff, and available transcript. The candidate action names should use existing project terminology. This note does not define new precedence among conflicting observations; the governing [recovery design](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/120-recover-crashed-seats-design.md) and [login-recovery design](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/docs/issues/116-fleet-survives-machine-restart-design.md) decide that.

This boundary is valuable for the observed failure class. A stale heartbeat can be presented to the decision function alongside evidence that the named process is gone. A successful launcher return is only a launch observation; the separate confirmation that the expected seat actually started supplies the success evidence required by issue 242.

**First proof.** Reuse [scripts/recover-crashed-seats-test.py](https://github.com/nedschorus/nedschorus/blob/b9655170cebbbaa78e361b7b4aeef6f3e3a31089/scripts/recover-crashed-seats-test.py) for the ruled cases, and add tests only for the changed behavior. Pure decision checks can cover policy combinations without launching seats; environment-facing checks still need to show that process identity and successful startup are measured correctly. A fixture cannot establish those external facts by agreeing with the implementation.

This is an incremental factoring inside already requested work. There is no recommendation to rewrite every controller as a statechart or create a general state-machine library.
