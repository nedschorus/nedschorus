#!/usr/bin/env python3
"""Raise an agent-seat's own tasks when they come due, at the end of each turn.

Wired as a Stop hook in .claude/settings.json.

WHAT A TASK IS. A Claude Code task is the file
`~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>/<id>.json`, with the keys
activeForm, blockedBy, blocks, description, id, metadata, status and subject
(activeForm and metadata are optional, and a few files carry `owner`). An
agent-seat's list id is `nedschorus-<seat>-tasks`, read from the environment
variable CLAUDE_CODE_TASK_LIST_ID, which the hook inherits from the session;
a session without one prints nothing. Only `*.json` files are read, because
the list directory also holds the harness's `.lock`. Task files are never
written.

WHAT MAKES A TASK DUE. Two optional keys in a task's `metadata`:

  due_utc   an ISO 8601 time in UTC, such as "2026-10-03T09:00:00Z". A time
            with no offset is read as UTC. Passed means at or before now.
  waits_on  a non-empty list of conditions on the repository
            nedschorus/nedschorus, each {"pr_merged": <number>} or
            {"issue_closed": <number>}. Met means every condition is met. An
            empty list is never met: "every one of nothing" would raise a
            task nobody set a prerequisite on. A list with any entry this
            hook cannot read is never met.

An open task (status pending or in_progress) is raised when its due time has
passed or its waits_on is met, and only when every task in its blockedBy is
completed. A blockedBy id with no task file does not hold the task: a deleted
task can never complete, and holding on it would silence the task for good.
A blocker file that exists but cannot be read does hold it, because its
status is unknown.

RAISED ONCE. The hook records, per task, the due_utc and waits_on values it
raised the task for, and does not raise the task again for the same value;
changing either lets the task be raised again. The Stop hook's
additionalContext continues the conversation, so a hook that said the same
thing at every turn boundary would never let the agent stop. The record is
written atomically BEFORE anything is printed, and nothing is printed if the
write fails, so a raise whose record was lost cannot happen.

THE STATE FILE is
`~/.local/state/claude/agent-seat-due-task-raise-state/<list id>.json`,
outside the task directory so the harness's handling of that directory never
meets it; ~/.local/state/claude/ exists on both machines. Its `raised`
entries are pruned to the task files that still exist, and its `checks`
entries to the conditions an open task still names. A state file that cannot
be parsed is treated as empty and replaced on the next write, because
silence on any fault would mute the hook for good after one torn file. Two
sessions sharing one list id that stop at the same instant could each raise
the same task once; that is not locked against.

GITHUB, and only for waits_on. A condition is checked with `gh pr view` or
`gh issue view` (read-only), GH_TOKEN removed from the environment so gh
uses its keyring login, stdin closed, each call bounded by
GH_CALL_TIMEOUT_SECONDS and all of a run's calls together by
GH_CALLS_TOTAL_BUDGET_SECONDS. A condition checked within
CONDITION_RECHECK_INTERVAL_SECONDS is answered from the state file. A failed,
timed-out or unparsable check is "not met", recorded with its time so it too
waits the interval, and is never reported. No condition is checked for a
task already raised for its current waits_on, or held by blockedBy, so an
agent-seat whose tasks have no waits_on makes no network call. The same call
fetches the title and URL the raise line cites; a condition gh never
answered is cited by its number alone.

OUTPUT. Something to raise: one JSON object,
{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}},
which Claude Code delivers to the model as non-error feedback while the
conversation continues. No `decision` field and no `systemMessage`: the text
is for the agent. The text is one instruction per due task, then the
instruction for a task that cannot be acted on yet. Nothing to raise, or any
fault: nothing printed, exit 0. The hook never exits nonzero: a fault here
must not stop a turn ending.

ONLY THE AGENT-SEAT'S OWN SESSION IS RAISED, never a headless `claude -p`
child an agent-seat's program starts. A child inherits the agent-seat's
environment, CLAUDE_CODE_TASK_LIST_ID included, and the raise text would be
the last thing the child says, which its caller reads as the answer. Two
signals silence the hook:

  NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER set, the variable
      scripts/ghi-info-ask.py sets for its child and the handoff hook also
      honours.
  CLAUDE_CODE_SESSION_ATTENDED == "0". Claude Code sets this for every hook
      it runs: "1" in an interactive session, "0" in a `claude -p` child,
      even when the child inherited "1" from the agent-seat. The Stop payload
      carries no field that tells the two apart. A missing variable does not
      silence the hook, so a Claude Code that stops setting it costs the
      headless guard, not the agent-seat's reminders.

The project's own headless Claude callers run no project hook at all: the
cold-read Claude cell, and the restater-judge cell through it, pass
`--settings` with disableAllHooks; scripts/ghi-info-ask.py and
scripts/sanity-check-attacks.py pass `--setting-sources user`. The two
signals cover a child started any other way.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

TASK_LIST_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"
TASKS_ROOT_UNDER_HOME = Path(".claude") / "tasks"
STATE_DIRECTORY_UNDER_HOME = (Path(".local") / "state" / "claude"
                              / "agent-seat-due-task-raise-state")
OPEN_TASK_STATUSES = ("pending", "in_progress")
COMPLETED_TASK_STATUS = "completed"

FRACTIONAL_SECONDS_PATTERN = re.compile(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)(.*)$")

GITHUB_REPOSITORY = "nedschorus/nedschorus"
CONDITION_RECHECK_INTERVAL_SECONDS = 300
GH_CALL_TIMEOUT_SECONDS = 8
GH_CALLS_TOTAL_BUDGET_SECONDS = 20

# condition kind -> (gh subcommand, the gh state that means met, the ID-type
# written in the raise line, the word for met in the raise line)
CONDITION_KINDS = {
    "pr_merged": ("pr", "MERGED", "PR", "merged"),
    "issue_closed": ("issue", "CLOSED", "GHI", "closed"),
}

DEFER_INSTRUCTION = (
    "If a task above cannot be acted on yet, give it a later metadata.due_utc, "
    "a new metadata.waits_on, or both, with TaskUpdate instead."
)


def single_line(text) -> str:
    """Collapse any whitespace run, newlines included, to one space."""
    return " ".join(str(text).split())


def task_list_directory(home: Path, environment) -> "Path | None":
    list_id = environment.get(TASK_LIST_ID_ENVIRONMENT_VARIABLE, "")
    if not list_id or "/" in list_id or list_id in (".", ".."):
        return None
    return home / TASKS_ROOT_UNDER_HOME / list_id


def state_file_path(home: Path, list_id: str) -> Path:
    return home / STATE_DIRECTORY_UNDER_HOME / f"{list_id}.json"


def read_tasks(directory: Path) -> dict:
    """Every readable task in the list, by id; a malformed file is skipped."""
    tasks = {}
    for path in sorted(directory.glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        tasks[task_id] = task
    return tasks


def blocker_holds(blocker_id, tasks: dict, directory: Path) -> bool:
    """True while this blockedBy entry keeps its task from being raised."""
    if not isinstance(blocker_id, str):
        return True
    if blocker_id in tasks:
        return tasks[blocker_id].get("status") != COMPLETED_TASK_STATUS
    # Not among the readable tasks: held if the file exists but would not
    # read, free if the task is gone.
    return (directory / f"{blocker_id}.json").exists()


def is_held_by_blockers(task: dict, tasks: dict, directory: Path) -> bool:
    blocked_by = task.get("blockedBy") or []
    if not isinstance(blocked_by, list):
        return True
    return any(blocker_holds(blocker, tasks, directory) for blocker in blocked_by)


def parse_due_utc(text) -> "datetime | None":
    """The instant a due_utc string names, or None when it names none."""
    if not isinstance(text, str) or not text.strip():
        return None
    normalized = text.strip()
    if normalized[-1] in "Zz":
        normalized = normalized[:-1] + "+00:00"
    # Python 3.9's fromisoformat, the Mac's system Python, takes a fraction
    # of exactly three or six digits; written times use any number.
    fraction = FRACTIONAL_SECONDS_PATTERN.match(normalized)
    if fraction:
        normalized = (fraction.group(1) + "." + fraction.group(2)[:6].ljust(6, "0")
                      + fraction.group(3))
    try:
        instant = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant


def parse_waits_on(value) -> "list | None":
    """The waits_on list as [(kind, number), ...], or None if any entry is unreadable."""
    if not isinstance(value, list) or not value:
        return None
    conditions = []
    for entry in value:
        if not isinstance(entry, dict) or len(entry) != 1:
            return None
        (kind, number), = entry.items()
        if kind not in CONDITION_KINDS:
            return None
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            return None
        conditions.append((kind, number))
    return conditions


def condition_key(kind: str, number: int) -> str:
    return f"{kind}:{number}"


def canonical_waits_on(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    raised = state.get("raised")
    checks = state.get("checks")
    return {
        "raised": raised if isinstance(raised, dict) else {},
        "checks": checks if isinstance(checks, dict) else {},
    }


def write_state_atomically(path: Path, state: dict) -> bool:
    """Replace the state file in one rename; True only when it landed."""
    temporary_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, str(path))
        return True
    except OSError:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        return False


class GitHubConditionChecker:
    """Answers waits_on conditions from the cache or from gh, within a budget."""

    def __init__(self, checks: dict, now_epoch: float):
        self.checks = checks
        self.now_epoch = now_epoch
        self.started = time.monotonic()
        self.changed = False

    def answer(self, kind: str, number: int) -> dict:
        key = condition_key(kind, number)
        cached = self.checks.get(key)
        if (isinstance(cached, dict)
                and isinstance(cached.get("checked_at_epoch"), (int, float))
                and 0 <= self.now_epoch - cached["checked_at_epoch"]
                < CONDITION_RECHECK_INTERVAL_SECONDS):
            return cached
        remaining = GH_CALLS_TOTAL_BUDGET_SECONDS - (time.monotonic() - self.started)
        if remaining <= 0:
            # Out of budget: not met this run, and not recorded, so the next
            # run checks it.
            return {"met": False}
        fresh = self.ask_gh(kind, number, min(GH_CALL_TIMEOUT_SECONDS, remaining))
        fresh["checked_at_epoch"] = self.now_epoch
        previous = cached if isinstance(cached, dict) else {}
        for citation_field in ("title", "url"):
            if citation_field not in fresh and isinstance(previous.get(citation_field), str):
                fresh[citation_field] = previous[citation_field]
        self.checks[key] = fresh
        self.changed = True
        return fresh

    @staticmethod
    def ask_gh(kind: str, number: int, timeout_seconds: float) -> dict:
        subcommand, met_state, _, _ = CONDITION_KINDS[kind]
        environment = dict(os.environ)
        environment.pop("GH_TOKEN", None)
        try:
            completed = subprocess.run(
                ["gh", subcommand, "view", str(number), "--repo", GITHUB_REPOSITORY,
                 "--json", "state,title,url"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=timeout_seconds, env=environment, check=False)
        except (OSError, subprocess.SubprocessError):
            return {"met": False}
        if completed.returncode != 0:
            return {"met": False}
        try:
            answer = json.loads(completed.stdout)
        except ValueError:
            return {"met": False}
        if not isinstance(answer, dict):
            return {"met": False}
        result = {"met": answer.get("state") == met_state}
        for citation_field in ("title", "url"):
            if isinstance(answer.get(citation_field), str):
                result[citation_field] = answer[citation_field]
        return result


def condition_citation(kind: str, number: int, answer: dict) -> str:
    _, _, id_type, met_word = CONDITION_KINDS[kind]
    title = answer.get("title")
    url = answer.get("url")
    if isinstance(title, str) and title.strip() and isinstance(url, str) and url:
        return f'{id_type} "{single_line(title)}" ({url}) is {met_word}'
    return f"{id_type} {number} is {met_word}"


def raise_line(task: dict, due_text, met_citations) -> str:
    reasons = []
    if due_text is not None:
        reasons.append(f"its due time {single_line(due_text)} has passed")
    if met_citations is not None:
        reasons.append("its prerequisites are met: " + "; ".join(met_citations))
    return (f'Act on task {task["id"]} "{single_line(task.get("subject", ""))}" '
            f"now: {', and '.join(reasons)}.")


def due_task_lines(tasks: dict, directory: Path, state: dict, now: datetime) -> "tuple[list, bool]":
    """The raise lines for this run, and whether the state changed.

    Mutates `state` to record every raise it returns and to prune entries
    for tasks and conditions that no longer need them.
    """
    raised = state["raised"]
    checker = GitHubConditionChecker(state["checks"], now.timestamp())
    lines = []
    state_changed = False
    conditions_still_named = set()

    for task_id in sorted(tasks, key=lambda text: (len(text), text)):
        task = tasks[task_id]
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        metadata = task.get("metadata")
        if not isinstance(metadata, dict):
            continue
        due_text = metadata.get("due_utc")
        waits_on_value = metadata.get("waits_on")
        conditions = parse_waits_on(waits_on_value)
        if conditions is not None:
            conditions_still_named.update(condition_key(k, n) for k, n in conditions)
        if is_held_by_blockers(task, tasks, directory):
            continue
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}

        due_reason = None
        due_instant = parse_due_utc(due_text)
        if (due_instant is not None and due_instant <= now
                and record.get("due_utc") != due_text):
            due_reason = due_text

        prerequisite_citations = None
        if conditions is not None:
            waits_on_record = canonical_waits_on(waits_on_value)
            if record.get("waits_on") != waits_on_record:
                answers = [(kind, number, checker.answer(kind, number))
                           for kind, number in conditions]
                if all(answer.get("met") is True for _, _, answer in answers):
                    prerequisite_citations = [
                        condition_citation(kind, number, answer)
                        for kind, number, answer in answers]

        if due_reason is None and prerequisite_citations is None:
            continue
        new_record = dict(record)
        if due_reason is not None:
            new_record["due_utc"] = due_text
        if prerequisite_citations is not None:
            new_record["waits_on"] = canonical_waits_on(waits_on_value)
        raised[task_id] = new_record
        state_changed = True
        lines.append(raise_line(task, due_reason, prerequisite_citations))

    for task_id in list(raised):
        if task_id not in tasks:
            del raised[task_id]
            state_changed = True
    for key in list(state["checks"]):
        if key not in conditions_still_named:
            del state["checks"][key]
            state_changed = True
    return lines, state_changed or checker.changed


def run(stdin_text: str, environment, home: Path, now: datetime) -> "str | None":
    """The JSON to print, or None for silence."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        return None
    if environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):
        return None  # a caller's headless child: the raise would replace its answer
    if environment.get(SESSION_ATTENDED_VARIABLE) == SESSION_UNATTENDED_VALUE:
        return None  # a `claude -p` child, not the agent-seat's own session
    directory = task_list_directory(home, environment)
    if directory is None or not directory.is_dir():
        return None
    tasks = read_tasks(directory)
    state_path = state_file_path(home, directory.name)
    state = read_state(state_path)
    lines, state_changed = due_task_lines(tasks, directory, state, now)
    if state_changed and not write_state_atomically(state_path, state):
        return None
    if not lines:
        return None
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "\n".join(lines + [DEFER_INSTRUCTION]),
        }
    }, ensure_ascii=False)


def main() -> int:
    try:
        output = run(sys.stdin.read(), os.environ, Path.home(),
                     datetime.now(timezone.utc))
    except Exception:
        return 0
    if output is not None:
        try:
            print(output)
        except Exception:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
