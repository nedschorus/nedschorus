#!/usr/bin/env python3
"""Print, for each agent-seat on this machine, the idle sweep's verdict: whether the agent-seat is
idle and, when it is, which rule of the idle sweep decides what happens next.

This is the first build-slice of the idle sweep (docs/issues/940-tasks-raise-themselves-when-their-
due-time-passes.md, § The idle sweep). It decides only what code decides, and it acts on nothing:
it sends no message, starts no headless agent-session, writes no alert and keeps no log, so a
verdict here changes nothing on the machine. A later slice reads these verdicts, judges the cases
marked "judge", sends, and runs on a schedule.

What it reads, for each agent-seat that has a handoff-supervisor state file
(`<handoff directory>/<seat>-supervisor-state.json`):
- the agent-session the supervisor launched last, and its transcript under the projects root,
  with every transcript under that agent-session's `subagents/` folder;
- the walk-minutes in the agent-seat's `docs/walk/`, the handoff deferral marker file, the task
  list `<tasks root>/nedschorus-<seat>-tasks/`, and, for a usage limit, `oauthAccount.accountUuid`
  in `~/.claude.json`;
- GitHub, through `gh`, for the prerequisites of open tasks, only when rule 4 needs the answer.

It prints one JSON object per agent-seat, one per line. Each holds what the later slice needs
without reading anything again: the session id, the transcript path, the last time a token was
spent and the file that showed it, what is running and since when, the matched sentences with the
code's reading of each, the rule that applies and its decision.

What it does not handle: it keeps no record of earlier runs, so it cannot tell which turn-ending
messages it has already checked; by default it checks only the last one, and
--turn-ending-messages-since widens that. It does not know whether a usage limit ended by an
account change, since that needs the account recorded when the limit was first seen; it reports
the account now logged in. It reads ned-box's own files only.

How it fails: when a file it must read cannot be read, or is not UTF-8 or JSON where a whole line
is expected, or `gh` cannot answer, the agent-seat's line carries the failure under "errors" and
"rule" is null, every other agent-seat is still reported, and the program exits 1. A failure it
does not expect, such as a file that changes between two reads of it, stops the program with a
traceback and exit 1. A transcript
that does not exist is not a failure: the line says so under "not_checked". It reads whole
transcripts, which grow to tens of megabytes, so one run takes seconds.
"""

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _load(module_name, path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_SCRIPTS = Path(__file__).resolve().parent
threshold_hook = _load("handoff_context_threshold_hook",
                       _SCRIPTS / "handoff-context-threshold-hook.py")
supervisor = _load("handoff_supervisor",
                   _SCRIPTS.parent / "nc-systems" / "handoff" / "handoff-supervisor.py")
due_task_hook = _load("agent_seat_due_task_raise_hook", _SCRIPTS / "agent-seat-due-task-raise-hook.py")
fields = _load("agent_seat_idle_sweep_verdict_fields_common",
               _SCRIPTS / "agent-seat-idle-sweep-verdict-fields-common.py")
transcript_lookup = _load("claude_code_session_transcript_lookup_and_text_search_common",
                          _SCRIPTS / "claude-code-session-transcript-lookup-and-text-search-common.py")

IDLE_AFTER_SECONDS = 5 * 60
LAUNCHED_SESSION_ID_KEY = "launched_session_id"
# State files older than the key's rename still name the session under this key.
LEGACY_SESSION_ID_KEY = "session_id"
AGENT_EXIT_CODE_KEY = "agent_exit_code"
HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"
USAGE_LIMIT_API_ERROR = "usage_limit_reached"
SYNTHETIC_MODEL = "<synthetic>"
WALK_CLOSED_LINE = "#next_to_present none, closed"
WALK_NEXT_PREFIX = "#next_to_present"
WALK_PAUSED_PREFIX = "#approval_walk_paused"
TASK_TOOL_NAMES = ("TaskCreate", "TaskUpdate")
HANDOFF_PUT_OFF_TEXT = ("Your handoff was put off at {time} and nothing is running now. "
                        "Is now a good time to hand off?")

# --- Sentence kinds and the phrase lists that pick sentences out ---
# The one copy of each list, as the design's § Promises and announced actions says: change them here.
ANNOUNCED_ACTION = fields.ANNOUNCED_ACTION
PROMISE_AFTER_EVENT = fields.PROMISE_AFTER_EVENT
STANDING_RULE = fields.STANDING_RULE
HOLD = fields.HOLD
CONDITIONAL_ON_USER = fields.CONDITIONAL_ON_USER
NEGATIVE = fields.NEGATIVE
NOT_RAISED_KINDS = (CONDITIONAL_ON_USER, NEGATIVE)

PROMISE_PHRASES = (
    (CONDITIONAL_ON_USER, re.compile(r"\bsay the word,? and I'?ll\b", re.I)),
    (HOLD, re.compile(r"\bI(?:'ll| will) hold\b", re.I)),
    (STANDING_RULE, re.compile(r"\bfrom now on\b|\bgoing forward\b|\bfrom here on\b|^\W*noted\b",
                               re.I)),
    (PROMISE_AFTER_EVENT, re.compile(
        r"\bI(?:'ll| will) (?:bring you|report when|carry|pick up)\b"
        r"|\bI won'?t\b.*\buntil\b"
        r"|\bI(?:'ll| will)\b.*\b(?:when|once)\b", re.I)),
)

_VERBS = (
    "open|file|create|push|commit|run|re-?run|start|dispatch|send|launch|merge|post|"
    "write|edit|fix|check|read|look|review|rebase|update|add|delete|remove|apply|"
    "test|install|restart|kill|spawn|fork|message|tell|ask|reply|draft|make|build|"
    "fetch|pull|clone|grep|search|verify|investigate|record|save|publish|comment|"
    "close|revert|rename|move|copy|land|kick off|fire|queue|retry|rerun|amend|"
    "squash|reopen|resolve|patch|implement|scan|compare|diff|inspect|confirm|"
    "re-?dispatch|re-?push|re-?file|re-?open|relaunch|notify|ping|hand|stage"
)
_GERUNDS = (
    "opening|filing|creating|pushing|committing|running|re-?running|starting|"
    "dispatching|sending|launching|merging|posting|writing|editing|fixing|"
    "checking|reading|looking|reviewing|rebasing|updating|adding|deleting|"
    "removing|applying|testing|installing|restarting|killing|spawning|forking|"
    "messaging|telling|asking|replying|drafting|making|building|fetching|"
    "pulling|cloning|searching|verifying|investigating|recording|saving|"
    "publishing|commenting|closing|reverting|renaming|moving|copying|landing|"
    "kicking off|firing|queueing|queuing|retrying|amending|squashing|"
    "reopening|resolving|patching|implementing|scanning|comparing|inspecting|"
    "confirming|re-?dispatching|re-?pushing|relaunching|notifying|pinging|"
    "handing|staging"
)
_FILLER = (r"(?:(?:now|then|first|next|go ahead and|go|quickly|also|immediately|just|"
           r"straight away|right away|actually|instead|again)\s+)*")
_SUBJECT = (r"(?:I'?ll|I will|I'?m going to|I am going to|I'?m about to|I am about to|"
            r"let me|let's|I'?m gonna)")
RX_FUTURE = re.compile(r"\b" + _SUBJECT + r"\s+" + _FILLER + r"(?P<v>" + _VERBS + r")\b(?!-)", re.I)
RX_PROGRESSIVE = re.compile(r"\bI(?:'m| am)\s+(?:now\s+|also\s+|just\s+)?(?P<v>" + _GERUNDS
                            + r")\b(?!-)", re.I)
RX_GERUND_START = re.compile(
    r"^(?:\W*)(?:(?:now|next|then|ok|okay|good|right|done|so|and)[,.:]?\s+)*(?P<v>" + _GERUNDS
    + r")\b(?P<rest>.*)$", re.I)
RX_NEXT_STEP = re.compile(r"^\W*(?:now,?\s+)?next(?: step)?(?:,| is| up)?:?\s+(?:to\s+|I'?m\s+|"
                          r"I'?ll\s+|I will\s+)?(?P<v>" + _VERBS + "|" + _GERUNDS + r")\b(?!-)", re.I)
RX_LET_ME_NEGATED = re.compile(r"(?:n't|\bnot|\bto|\bwon't|\bwould|\bwill|\bcan|\bcould|\bshould|"
                               r"\bthey|\bit|\bhe|\byou)\s+let me\b", re.I)
RX_GERUND_NARRATIVE = re.compile(
    r"\b(showed|shows|show|was|were|is|are|would|will|could|should|might|takes|took|"
    r"failed|fails|gave|gives|found|finds|returned|returns|produced|works|worked|"
    r"broke|breaks|means|requires|needs|did|does|has|had|isn't|wasn't|won't|can't|can|may|"
    r"passes|fixes|avoids|carries|makes|leaves|keeps|helps|saves|costs|adds|gets|lets|stops|"
    r"puts|turns|matters|beats|loses|reads|catches|misses|wins|belongs|depends|happens|settles|"
    r"covers|answers|removes|closes|ends|starts|runs|says|tells|shows)\b", re.I)
RX_GERUND_NOUN = re.compile(r"^\W*\w+\s+(list|order|time|notes?|material|guide|room)\b", re.I)
RX_NOW_NEXT = re.compile(r"^\W*(?:now|next|then)\b|\bnow\b|\bnext\b", re.I)
# The user has the next move in these; an event-conditional sentence is a promise after the event.
RX_CONDITIONAL_ON_USER = re.compile(
    r"\b(?:should you|want me|would you|shall I|say the word|say go|your call|if you'?d like|"
    r"can I|may I|on your (?:go|word|approval|ok|yes|y))\b"
    r"|^\W*(?:say|tell me|reply|answer|pick|choose)\b", re.I)
RX_CONDITIONAL_ON_EVENT = re.compile(
    r"\b(?:if|once|when|whenever|after|unless|until|tomorrow|later|next session|next time|"
    r"as soon as|the moment|in a day|in an hour|by tomorrow)\b", re.I)
RX_NEGATED_ACTION = re.compile(
    r"\b(?:without|instead of|rather than|not yet|never|no longer|don't|won't|can't)\s+"
    r"(?:\w+\s+){0,2}?(?:push|pushing|commit|committing|dispatch|dispatching|fork|forking|file|"
    r"filing|open|opening|send|sending|message|messaging|start|starting|spawn|spawning)\b", re.I)


def clean_text(text):
    """Remove code, block quotes and quoted words, which are not the agent's own sentences."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"```.*", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", " CODE ", text)
    text = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith(">"))
    text = re.sub(r"“[^”]*”", " QUOTE ", text)
    return re.sub(r"\"[^\"\n]*\"", " QUOTE ", text)


def sentences(text):
    for line in clean_text(text).split("\n"):
        line = re.sub(r"^\s*(?:[-*+]|\d+[.)]|#+)\s+", "", line).strip()
        line = re.sub(r"^\*\*[^*]+\*\*:?\s*", "", line)
        if line.startswith("#"):
            continue
        line = re.sub(r"\*\*|__", "", line)
        for sentence in re.split(r"(?<=[.!?;])\s+", line):
            if sentence.strip():
                yield sentence.strip()


def _gerund_announces(sentence, match):
    rest = match.group("rest")
    if RX_GERUND_NARRATIVE.search(rest) or RX_GERUND_NOUN.search(sentence):
        return False
    if re.search(r"\b\w+ed\b", rest) or ":" in sentence.rstrip(":"):
        return False
    if RX_NOW_NEXT.search(sentence):
        return True
    return len(sentence.split()) <= 8 and sentence.rstrip().endswith((".", "…", ":"))


def _announces(sentence):
    for pattern in (RX_FUTURE, RX_PROGRESSIVE, RX_NEXT_STEP):
        if pattern.search(sentence) and not (pattern is RX_FUTURE
                                             and RX_LET_ME_NEGATED.search(sentence)):
            return True
    match = RX_GERUND_START.match(sentence)
    return bool(match and _gerund_announces(sentence, match))


def sentence_kind(sentence):
    """Return the kind of a sentence the phrase lists match, or None for a sentence they miss."""
    if sentence.endswith("?"):
        return None
    kind = next((kind for kind, pattern in PROMISE_PHRASES if pattern.search(sentence)), None)
    if kind is None:
        if not _announces(sentence):
            return None
        if RX_NEGATED_ACTION.search(sentence):
            return NEGATIVE
    # The user has the next move whatever else the sentence promises.
    if RX_CONDITIONAL_ON_USER.search(sentence):
        return CONDITIONAL_ON_USER
    if kind is not None:
        return kind
    if RX_CONDITIONAL_ON_EVENT.search(sentence):
        return PROMISE_AFTER_EVENT
    return ANNOUNCED_ACTION


# --- Reading one transcript ---

class ReadFailure(Exception):
    pass


def parse_time(stamp):
    if not isinstance(stamp, str):
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def iso(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if moment else None


def transcript_records(path):
    """Yield each record of a transcript, oldest first.

    The last line may be one Claude Code is still writing, so a last line without a newline that
    does not parse is skipped; any other line that is not UTF-8 JSON raises ReadFailure."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ReadFailure(f"{path} could not be read: {error}") from error
    lines = data.split(b"\n")
    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        is_unfinished_last_line = number == len(lines)
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            if is_unfinished_last_line:
                continue
            raise ReadFailure(f"{path} line {number} is not UTF-8 JSON: {error}") from error
        if isinstance(record, dict):
            yield record


def spends_tokens(record):
    if record.get("type") != "assistant":
        return False
    message = record.get("message") or {}
    if message.get("model") == SYNTHETIC_MODEL:
        return False
    usage = message.get("usage")
    return isinstance(usage, dict) and threshold_hook.used_tokens_of(usage) + int(
        usage.get("output_tokens") or 0) > 0


def is_model_turn_record(record):
    """A user or assistant record: a request to the model or its answer."""
    return record.get("type") in ("user", "assistant")


def is_usage_limit(record):
    return record.get("type") == "assistant" and record.get("apiError") == USAGE_LIMIT_API_ERROR


def message_text(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content
                         if isinstance(block, dict) and block.get("type") == "text")
    return ""


def tool_uses(record):
    content = (record.get("message") or {}).get("content")
    if record.get("type") != "assistant" or not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict) and block.get("type") == "tool_use"]


class TranscriptFacts:
    def __init__(self):
        self.last_token_spend = None
        self.last_model_turn_record = None
        self.turn_ended_after_last_model_turn_record = False
        self.turn_ending_messages = []   # (record, time)
        self.task_tool_calls = []        # (time, name, input)
        self.launch_times = {}           # subagent or background task id -> time


def read_main_transcript(path):
    facts = TranscriptFacts()
    newest_text_record = None
    for record in transcript_records(path):
        moment = parse_time(record.get("timestamp"))
        if spends_tokens(record) and moment:
            facts.last_token_spend = max(filter(None, (facts.last_token_spend, moment)))
        if is_model_turn_record(record):
            facts.last_model_turn_record = record
            facts.turn_ended_after_last_model_turn_record = False
        if record.get("type") == "assistant" and message_text(record).strip():
            newest_text_record = record
        if record.get("type") == "system" and record.get("subtype") == "turn_duration":
            facts.turn_ended_after_last_model_turn_record = True
            if newest_text_record is not None:
                facts.turn_ending_messages.append(
                    (newest_text_record, parse_time(newest_text_record.get("timestamp"))))
                newest_text_record = None
        for block in tool_uses(record):
            if block.get("name") in TASK_TOOL_NAMES:
                facts.task_tool_calls.append((moment, block.get("name"), block.get("input") or {}))
        result = record.get("toolUseResult")
        if isinstance(result, dict) and moment:
            for key in ("agentId", threshold_hook.BACKGROUND_TASK_LAUNCH_KEY):
                launched = result.get(key)
                if isinstance(launched, str) and launched not in facts.launch_times:
                    facts.launch_times[launched] = moment
    return facts


def newest_token_spend_in(path):
    newest = None
    for record in transcript_records(path):
        moment = parse_time(record.get("timestamp"))
        if moment and spends_tokens(record) and (newest is None or moment > newest):
            newest = moment
    return newest


# --- Other files ---

def walk_items_waiting(seat_directory):
    """Walk-minutes files in the agent-seat's docs/walk/ whose last #next_to_present line names an
    item, with no pause recorded after it."""
    waiting = []
    walk_directory = seat_directory / "docs" / "walk"
    if not walk_directory.is_dir():
        return waiting
    for minutes in sorted(walk_directory.glob("*-minutes.md")):
        try:
            lines = minutes.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as error:
            raise ReadFailure(f"{minutes} could not be read: {error}") from error
        state = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(WALK_NEXT_PREFIX):
                state = stripped
            elif stripped.startswith(WALK_PAUSED_PREFIX):
                state = None
        if state and state != WALK_CLOSED_LINE:
            waiting.append({"walk_minutes": str(minutes), "line": state})
    return waiting


def logged_in_account(claude_json):
    try:
        data = json.loads(claude_json.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise ReadFailure(f"{claude_json} could not be read: {error}") from error
    account = data.get("oauthAccount") if isinstance(data, dict) else None
    return account.get("accountUuid") if isinstance(account, dict) else None


def open_tasks_nothing_holds(task_directory, checker):
    """Open tasks whose blockedBy tasks are all done and whose prerequisites all hold."""
    if not task_directory.is_dir():
        return []
    tasks = due_task_hook.read_tasks(task_directory)
    free = []
    for task_id, task in tasks.items():
        if task.get("status") not in due_task_hook.OPEN_TASK_STATUSES:
            continue
        if due_task_hook.is_held_by_blockers(task, tasks, task_directory):
            continue
        prerequisites = (task.get("metadata") or {}).get(due_task_hook.PREREQUISITES_KEY)
        if prerequisites:
            conditions = due_task_hook.parse_prerequisites(prerequisites)
            if conditions is None:
                continue
            answers = [checker.answer(kind, number) for kind, number in conditions]
            if checker.gh_failures:
                kind, number, cause = checker.gh_failures[0]
                raise ReadFailure(f"GitHub could not say whether {kind} {number} holds: {cause}")
            if not all(answer.get("met") for answer in answers):
                continue
        free.append({"id": task_id, "subject": task.get("subject")})
    return free


# --- One agent-seat's verdict ---

def code_reading_of_sentence(kind, sentence_time, task_tool_calls):
    """What code settles about one matched sentence: not_raised, unbacked, or judge."""
    if kind in NOT_RAISED_KINDS:
        return fields.NOT_RAISED
    if kind in (PROMISE_AFTER_EVENT, HOLD):
        backing_candidates = [call for call in task_tool_calls
                              if call[0] and sentence_time and call[0] >= sentence_time.replace(
                                  microsecond=0)
                              and ((call[2].get("metadata") or {}).get("prerequisites")
                                   or call[2].get("addBlockedBy"))]
        return fields.JUDGE if backing_candidates else fields.UNBACKED
    return fields.JUDGE


def matched_sentences(facts, since):
    messages = facts.turn_ending_messages
    if since is None:
        messages = messages[-1:]
    else:
        messages = [message for message in messages if message[1] and message[1] > since]
    found = []
    for record, moment in messages:
        for sentence in sentences(message_text(record)):
            kind = sentence_kind(sentence)
            if kind is None:
                continue
            found.append({"record_uuid": record.get("uuid"), "time": iso(moment),
                          "sentence": sentence, "kind": kind,
                          "code_reading": code_reading_of_sentence(kind, moment,
                                                                   facts.task_tool_calls)})
    return found


def rules_three_to_five(verdict, put_off_at, checker, task_directory):
    running = verdict["running"]["subagents"] or verdict["running"]["background_commands"]
    if verdict["handoff_deferred_marker"] and not running:
        return {fields.RULE: 3, fields.DECISION: fields.WAKE_HANDOFF_PUT_OFF,
                fields.TEXT: HANDOFF_PUT_OFF_TEXT.format(time=iso(put_off_at))}
    if not running and not verdict["handoff_deferred_marker"]:
        verdict["open_tasks_nothing_holds"] = open_tasks_nothing_holds(task_directory, checker)
        if not verdict["open_tasks_nothing_holds"]:
            return {fields.RULE: 4, fields.DECISION: fields.NO_WAKE}
    return {fields.RULE: 5, fields.DECISION: fields.JUDGE}


def verdict_for_seat(seat, paths, now, since, checker):
    verdict = {"agent_seat": seat, "session_id": None, "transcript_path": None,
               "checked_at": iso(now), "errors": [], "rule": None}
    try:
        state_path = supervisor.supervisor_state_path(paths.handoff_directory, seat)
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ReadFailure(f"{state_path} could not be read: {error}") from error
        if not isinstance(state, dict):
            raise ReadFailure(f"{state_path} does not hold a JSON object")
        session_id = state.get(LAUNCHED_SESSION_ID_KEY) or state.get(LEGACY_SESSION_ID_KEY)
        verdict["supervisor_last_poll_at"] = state.get("last_poll_at")
        if not isinstance(session_id, str) or not session_id:
            verdict["not_checked"] = "its handoff-supervisor has launched no agent-session"
            return verdict
        seat_directory = paths.agents_root / seat
        project_directory = transcript_lookup.project_directory_for_seat(seat_directory,
                                                                         paths.projects_root)
        transcript = project_directory / f"{session_id}.jsonl"
        verdict.update(session_id=session_id, transcript_path=str(transcript))
        if AGENT_EXIT_CODE_KEY in state:
            verdict["not_checked"] = "its agent-session has exited"
            return verdict
        if not transcript.exists():
            verdict["not_checked"] = "the agent-session's transcript does not exist"
            return verdict

        facts = read_main_transcript(transcript)
        last_spend, source = facts.last_token_spend, transcript
        subagent_directory = project_directory / session_id / "subagents"
        if subagent_directory.is_dir():
            for subagent_transcript in sorted(subagent_directory.glob("*.jsonl")):
                spent = newest_token_spend_in(subagent_transcript)
                if spent and (last_spend is None or spent > last_spend):
                    last_spend, source = spent, subagent_transcript
        verdict["last_activity"] = {"time": iso(last_spend),
                                    "source": str(source) if last_spend else None}

        last = facts.last_model_turn_record or {}
        limit = is_usage_limit(last)
        turn_ended = facts.turn_ended_after_last_model_turn_record or limit
        walk_waiting = walk_items_waiting(seat_directory)
        quiet = last_spend is None or (now - last_spend).total_seconds() >= IDLE_AFTER_SECONDS
        verdict.update(turn_ended=turn_ended, walk_items_waiting=walk_waiting)
        verdict["idle"] = quiet and turn_ended and not walk_waiting
        # Reading the transcript above already refused bytes this second read could not decode.
        flight = threshold_hook.work_in_flight(
            str(transcript), background_task_wait_seconds=float("inf"), now=now)
        verdict["running"] = {
            "subagents": [{"id": agent_id, "started": iso(facts.launch_times.get(agent_id))}
                          for agent_id in flight.subagent_ids],
            "background_commands": [{"id": task_id, "started": iso(facts.launch_times.get(task_id))}
                                    for task_id in flight.background_task_ids]}
        marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}"
        try:
            put_off_at = datetime.fromtimestamp(marker.stat().st_mtime, timezone.utc)
        except FileNotFoundError:
            put_off_at = None
        verdict["handoff_deferred_marker"] = str(marker) if put_off_at else None
        if not verdict["idle"]:
            verdict["not_idle_because"] = [
                reason for reason, holds in (
                    ("a token was spent less than 5 minutes ago", not quiet),
                    ("its last turn has not ended", not turn_ended),
                    ("an approval-walk item is waiting on the user", bool(walk_waiting)))
                if holds]
            return verdict

        if limit:
            quota = last.get("quotaLimits") or {}
            resets_at = quota.get("resetsAt")
            verdict["usage_limit"] = {
                "record_uuid": last.get("uuid"), "resets_at": resets_at,
                "reset_time_passed": isinstance(resets_at, (int, float))
                and now.timestamp() >= resets_at,
                "account_now_logged_in": logged_in_account(paths.claude_json)}
            verdict.update({fields.RULE: 1, fields.DECISION: fields.SESSION_LIMIT})
            return verdict

        verdict["sentences"] = matched_sentences(facts, since)
        raised = [item for item in verdict["sentences"] if item["code_reading"] != fields.NOT_RAISED]
        fallback = rules_three_to_five(verdict, put_off_at, checker, paths.tasks_root
                                       / f"nedschorus-{seat}-tasks")
        if raised:
            verdict.update({fields.RULE: 2, fields.DECISION: fields.JUDGE if any(
                item["code_reading"] == fields.JUDGE for item in raised) else fields.SEND_UNBACKED,
                fields.IF_EVERY_SENTENCE_BACKED: fallback})
        else:
            verdict.update(fallback)
    except ReadFailure as error:
        verdict["errors"].append(str(error))
    return verdict


# --- The program ---

class Paths:
    def __init__(self, arguments):
        self.handoff_directory = Path(arguments.handoff_directory).expanduser()
        self.agents_root = Path(arguments.agents_root).expanduser()
        self.projects_root = Path(arguments.projects_root).expanduser()
        self.tasks_root = Path(arguments.tasks_root).expanduser()
        self.claude_json = Path(arguments.claude_json).expanduser()


def agent_seats(handoff_directory):
    suffix = supervisor.SUPERVISOR_STATE_FILE_SUFFIX
    return [path.name[:-len(suffix)] for path in supervisor.supervisor_state_paths(handoff_directory)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--agent-seat", action="append", default=None,
                        help="report only this agent-seat; may be given more than once")
    parser.add_argument("--turn-ending-messages-since", default=None,
                        help="ISO time: check every turn-ending message after it, not only the last")
    parser.add_argument("--now", default=None, help="ISO time to judge at, for tests")
    parser.add_argument("--handoff-directory", default="~/.claude/handoffs")
    parser.add_argument("--agents-root", default="~/agents")
    parser.add_argument("--projects-root", default="~/.claude/projects")
    parser.add_argument("--tasks-root", default="~/.claude/tasks")
    parser.add_argument("--claude-json", default="~/.claude.json")
    arguments = parser.parse_args(argv)
    now = parse_time(arguments.now) if arguments.now else datetime.now(timezone.utc)
    since = None
    if arguments.turn_ending_messages_since:
        since = parse_time(arguments.turn_ending_messages_since)
        if since is None:
            parser.error("--turn-ending-messages-since is not an ISO time")
    if now is None:
        parser.error("--now is not an ISO time")
    paths = Paths(arguments)
    seats = arguments.agent_seat or agent_seats(paths.handoff_directory)
    checker = due_task_hook.GitHubConditionChecker({}, now.timestamp())
    failed = False
    for seat in seats:
        verdict = verdict_for_seat(seat, paths, now, since, checker)
        failed = failed or bool(verdict["errors"])
        print(json.dumps(verdict, sort_keys=True), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
