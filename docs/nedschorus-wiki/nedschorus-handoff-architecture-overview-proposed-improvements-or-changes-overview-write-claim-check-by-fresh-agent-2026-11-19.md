# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-19)

Assertions of the overview that the claim check against commit 6569ba50bfae51a22b297cdcd3974f3e0286be25 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/d84434da49408a7185aca817ee8aab3b3160c43f-2026-11-19T18-06-42-086951Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout leftovers-saving back-on-main program saves the checkout's leftovers to a branch it pushes, "and only then" puts the checkout back on main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `runs git switch --no-overwrite-ignore -C main origin/main ... which puts the local main at origin/main and checks it out, whether or not every push succeeded`. Also :52-55 `except a failed push of a leftovers branch ... which still lets the checkout go back on main: the unpushed branch stays in the checkout`. So the checkout goes back on main even when the push failed. Wording: "saves them to a branch and tries to push it, then puts the checkout back on main even if the push failed".
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: no program but the handoff-supervisor starts or resumes an agent-seat's agent-session, "apart from `scripts/ghi-guide-agent-ask.py`, which starts and resumes the ghi-guide-agent's agent-sessions itself".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> docs/nedschorus-wiki/nedschorus-glossary.md:66 `guide-agent — ... It is not an agent-seat: a script runs it one question at a time, with no seat-brief and no handoffs ... ghi-guide-agent is the first.` So the exception names a session that is no agent-seat's, and suggests one breach of the rule that does not exist. Other non-seat programs resume headless sessions too, e.g. scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py:394 `"--resume", session_id`. The rule itself holds. A search for `"--resume"`/`claude --resume` in non-test code found only the launchers, the handoff-supervisor, recover, resupervise and non-seat headless programs. Drop the exception, or say the guide-agent is not an agent-seat.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: When the reference-checkout will not fast-forward, the handoff-supervisor runs `put_reference_checkout_back_on_main` itself, "telling neither the successor nor the user of that branch".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> handoff-supervisor.py:2550-2552 `print("handoff-supervisor: " + reference_checkout_back_on_main.reference_checkout_back_on_main_success_line_build(REFERENCE_CHECKOUT, main_commit, leftovers_branches))`; handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:252 `f"its leftovers are saved on {', '.join(pushed)}, pushed to origin"`. The branch is named on the handoff-supervisor's terminal, the agent-seat's tmux pane. The successor is indeed not told (no successor_notice on success). Wording: "tells the successor nothing of that branch, and names it only on its own terminal". The handoff-supervisor's own docstring at handoff-supervisor.py:34-35 has the same inaccuracy.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: A first prompt given on the handoff-supervisor's command line reaches the agent-session "ending with a line the handoff-supervisor adds".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> handoff-supervisor.py:2605 adds the line at the prompt's end, but :1903-1905 `opening, next_step_heading, next_step = prompt.partition(NEXT_STEP_HEADING)` / `if not next_step_heading: return f"{prompt}\n\n{inserted}"`. A first prompt has no next-step heading, so when there are leftovers they go after the marking line, which then is not last. The reader matches the line anywhere: scripts/search-user-messages-in-transcripts.py:70 `any(phrase in text for phrase in LAUNCH_PROMPT_PHRASES)`. Wording: "carrying a line the handoff-supervisor adds after it".
State: open
