#!/usr/bin/env python3
"""The fields of one idle-sweep verdict, the JSON object scripts/agent-seat-idle-sweep-verdicts-print.py
prints for each agent-seat, and the values its rule, decision and sentences may take.

Not a program to run. The printing program takes eight field names from here, rule, decision,
text, if_every_sentence_backed, last_turn_ending_message, last_tool_call_at,
tool_calls_since_start_of_earliest_turn_with_sentence_to_judge and
open_tasks_with_prerequisites_or_blocked_by, and every value it prints for
decision, kind and code_reading; it writes the other field names as literals. Its test checks every verdict it prints with
verdict_field_problems(), and the program that judges and sends reads verdicts by these names, so
a field renamed in one place and not the other fails a test instead of being read as missing.
"""

AGENT_SEAT = "agent_seat"
SESSION_ID = "session_id"
TRANSCRIPT_PATH = "transcript_path"
CHECKED_AT = "checked_at"
ERRORS = "errors"
RULE = "rule"
DECISION = "decision"
NOT_CHECKED = "not_checked"
SUPERVISOR_LAST_POLL_AT = "supervisor_last_poll_at"
LAST_ACTIVITY = "last_activity"            # {"time": ISO time or null, "source": path or null}
# ISO time of the newest tool call in the agent-session's own transcript, or null
LAST_TOOL_CALL_AT = "last_tool_call_at"
TURN_ENDED = "turn_ended"
# [{"walk_minutes": path, "next_to_present": value}]
APPROVAL_WALK_ITEMS_WAITING_ON_THE_USER = "approval_walk_items_waiting_on_the_user"
IDLE = "idle"
NOT_IDLE_BECAUSE = "not_idle_because"      # [reason]
RUNNING = "running"  # {"subagents": [{"id", "started"}], "background_commands": [{"id", "started"}]}
# Keys a running subagent entry also carries when the subagent has stopped and reported, and is
# counted only because background commands it launched still run: when it stopped (ISO time), and
# those commands, [{"id", "started"}].
SUBAGENT_STOPPED_AT = "stopped_at"
SUBAGENT_OWN_RUNNING_BACKGROUND_COMMANDS = "own_running_background_commands"
HANDOFF_DEFERRED_MARKER = "handoff_deferred_marker"  # path or null
USAGE_LIMIT = "usage_limit"
SENTENCES = "sentences"
OPEN_TASKS_NOTHING_HOLDS = "open_tasks_nothing_holds"  # [{"id", "subject"}]
TEXT = "text"                              # code's text to send as written, at rule 3
IF_EVERY_SENTENCE_BACKED = "if_every_sentence_backed"  # {"rule", "decision", maybe "text"}
# {"record_uuid", "time", "text"} or null, at rules 2 to 5
LAST_TURN_ENDING_MESSAGE = "last_turn_ending_message"
# [{"time", "name", "input"}]: each tool call from the start of the earliest turn holding a sentence
# the judge decides, with its input cut to TOOL_CALL_INPUT_CHARACTERS_KEPT characters of JSON
TOOL_CALLS_SINCE_START_OF_EARLIEST_TURN_WITH_SENTENCE_TO_JUDGE = (
    "tool_calls_since_start_of_earliest_turn_with_sentence_to_judge")
TOOL_CALL_INPUT_CHARACTERS_KEPT = 1500
# [{"id", "subject", "prerequisites", "blockedBy"}]: every open task of the agent-seat that waits on
# something, whenever it was created, at rule 2 when the judge decides
OPEN_TASKS_WITH_PREREQUISITES_OR_BLOCKED_BY = "open_tasks_with_prerequisites_or_blocked_by"

ALWAYS_PRESENT = (AGENT_SEAT, SESSION_ID, TRANSCRIPT_PATH, CHECKED_AT, ERRORS, RULE)
OPTIONAL = (DECISION, NOT_CHECKED, SUPERVISOR_LAST_POLL_AT, LAST_ACTIVITY, LAST_TOOL_CALL_AT,
            TURN_ENDED,
            APPROVAL_WALK_ITEMS_WAITING_ON_THE_USER, IDLE, NOT_IDLE_BECAUSE, RUNNING,
            HANDOFF_DEFERRED_MARKER,
            USAGE_LIMIT, SENTENCES, OPEN_TASKS_NOTHING_HOLDS, TEXT, IF_EVERY_SENTENCE_BACKED,
            LAST_TURN_ENDING_MESSAGE,
            TOOL_CALLS_SINCE_START_OF_EARLIEST_TURN_WITH_SENTENCE_TO_JUDGE,
            OPEN_TASKS_WITH_PREREQUISITES_OR_BLOCKED_BY)

USAGE_LIMIT_FIELDS = ("record_uuid", "resets_at", "reset_time_passed", "account_now_logged_in")
SENTENCE_FIELDS = ("record_uuid", "time", "sentence", "kind", "code_reading")

ANNOUNCED_ACTION = "announced_action"
PROMISE_AFTER_EVENT = "promise_after_event"
STANDING_RULE = "standing_rule"
HOLD = "hold"
CONDITIONAL_ON_USER = "conditional_on_user"
NEGATIVE = "negative"
SENTENCE_KINDS = (ANNOUNCED_ACTION, PROMISE_AFTER_EVENT, STANDING_RULE, HOLD, CONDITIONAL_ON_USER,
                  NEGATIVE)

NOT_RAISED = "not_raised"
UNBACKED = "unbacked"
JUDGE = "judge"
CODE_READINGS = (NOT_RAISED, UNBACKED, JUDGE)

SESSION_LIMIT = "session_limit"
SEND_UNBACKED = "send_unbacked"
WAKE_HANDOFF_PUT_OFF = "wake_handoff_put_off"
NO_WAKE = "no_wake"
DECISIONS_BY_RULE = {1: (SESSION_LIMIT,), 2: (JUDGE, SEND_UNBACKED), 3: (WAKE_HANDOFF_PUT_OFF,),
                     4: (NO_WAKE,), 5: (JUDGE,)}


def verdict_sentences_grouped_by_code_reading(sentences) -> dict:
    """Return {code_reading: [sentence, ...]} for the sentences given, each list in their order."""
    grouped = {}
    for sentence in sentences:
        grouped.setdefault(sentence["code_reading"], []).append(sentence)
    return grouped


def verdict_field_problems(verdict) -> list:
    """Return one line for each way the verdict departs from the fields above; [] when none does."""
    if not isinstance(verdict, dict):
        return ["the verdict is not a JSON object"]
    problems = [f"field {name} is missing" for name in ALWAYS_PRESENT if name not in verdict]
    problems += [f"field {name} is not a verdict field" for name in verdict
                 if name not in ALWAYS_PRESENT + OPTIONAL]
    rule = verdict.get(RULE)
    if rule is not None and verdict.get(DECISION) not in DECISIONS_BY_RULE.get(rule, ()):
        problems.append(f"decision {verdict.get(DECISION)!r} is not one rule {rule!r} gives")
    if rule is None and DECISION in verdict:
        problems.append("a decision is given with no rule")
    fallback = verdict.get(IF_EVERY_SENTENCE_BACKED)
    if fallback is not None and (fallback.get(RULE) not in (3, 4, 5)
                                 or fallback.get(DECISION) not in DECISIONS_BY_RULE[fallback[RULE]]):
        problems.append(f"{IF_EVERY_SENTENCE_BACKED} is not a decision of rules 3 to 5: {fallback}")
    if USAGE_LIMIT in verdict and set(verdict[USAGE_LIMIT]) != set(USAGE_LIMIT_FIELDS):
        problems.append(f"{USAGE_LIMIT} fields are {sorted(verdict[USAGE_LIMIT])}")
    for sentence in verdict.get(SENTENCES, []):
        if set(sentence) != set(SENTENCE_FIELDS):
            problems.append(f"a sentence's fields are {sorted(sentence)}")
        elif sentence["kind"] not in SENTENCE_KINDS or sentence["code_reading"] not in CODE_READINGS:
            problems.append(f"a sentence has kind {sentence['kind']!r} and reading "
                            f"{sentence['code_reading']!r}")
    return problems
