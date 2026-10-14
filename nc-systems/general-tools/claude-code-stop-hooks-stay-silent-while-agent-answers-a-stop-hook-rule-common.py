#!/usr/bin/env python3
"""The rule every Stop and SubagentStop hook in this project obeys first.

THE RULE. A Stop or SubagentStop hook says nothing at a Stop that ends the
agent's answer to a Stop hook's output. Every such hook registered in
.claude/settings.json obeys it by making this its first act on the payload:

    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        exit 0, printing nothing and writing nothing

before it reads files, writes state, fetches, or prints. Load this module by
file path, as scripts/checkout-freshness-catch-up.py does.
scripts/registered-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-test.py fails
any registered Stop or SubagentStop hook that does not call the function.

WHY: THE LOOP. When a Stop hook prints `decision: "block"`, prints
`hookSpecificOutput.additionalContext`, or exits 2, the agent cannot stop: it
must answer what the hook said. When that answer ends, every Stop hook runs
again. A hook that speaks again then keeps the agent answering programs
instead of stopping, until Claude Code's cap of eight continuations in a row
ends the turn. Each hook's tokens and the user's screen pay for every round.

ADDITIONALCONTEXT IS NOT SAFER. A Stop hook's `additionalContext` continues
the conversation exactly as `decision: "block"` does, and the next Stop sees
`stop_hook_active` true after it. The hooks reference
(https://code.claude.com/docs/en/hooks, "Stop decision control") says
additionalContext "keeps the conversation going through the same loop
protections as `decision: "block"`, namely the `stop_hook_active` input and
the 8-consecutive-continuation cap".

THE TRAP: THE FLAG IS NOT YOURS ALONE. Claude Code sets `stop_hook_active`
true at the Stop that ends the agent's answer to ANY Stop hook's output, and
every Stop hook receives it. So a hook that obeys this rule also stays silent
after a different Stop hook spoke, even if it never spoke itself. That is
intended and costs nothing: the hook's check runs again at the next Stop, the
one that ends the next turn the user or an event starts. A hook that keeps
state, such as a once-only marker, must write none of it while silent, or the
thing it would have said is lost.

WHAT THIS DOES NOT PREVENT. A hook that speaks once every turn about
something the agent's own action makes true again, such as a reminder the
agent's fix makes due again, loops across turns instead of within one. The
flag cannot see that; the hook's own condition must clear once the agent has
acted on it.

A payload that is not a JSON object answers False, so the hook's own input
check still reports it.
"""


def stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
    """True when this Stop ends the agent's answer to a Stop hook's output: the hook must say nothing."""
    return isinstance(payload, dict) and payload.get("stop_hook_active") is True
