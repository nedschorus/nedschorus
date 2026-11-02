#!/usr/bin/env python3
"""Raise an agent-seat's own tasks when what they wait on is done, at the end of each turn,
and keep an idle agent-seat from stopping with nothing for the user to answer.

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

WHAT MAKES A TASK DUE. One optional key in a task's `metadata`:

  prerequisites  a non-empty list of conditions on the repository
                 nedschorus/nedschorus, each {"pr_merged": <number>} or
                 {"issue_closed": <number>}. Met means every condition is
                 met. An empty list is never met: "every one of nothing"
                 would raise a task nobody set a prerequisite on. A list
                 with any entry this hook cannot read is never met.

THE OLD KEYS. `waits_on` is the old name of `prerequisites`, and is read in
its place when a task has no `prerequisites`, so a task not yet moved to the
new key is not skipped. `due_utc` held a due time, and is no longer read. An
open task that still carries either key, even one blockedBy holds, is named
once, in the same text as any raise, with what its agent must change with
TaskUpdate.

An open task (status pending or in_progress) is raised when its
prerequisites are met, and only when every task in its blockedBy is
completed. A blockedBy id with no task file does not hold the task: a deleted
task can never complete, and holding on it would silence the task for good.
A blocker file that exists but cannot be read does hold it, because its
status is unknown. An open task with no prerequisites, or one already
raised for its current prerequisites, whose blockedBy is a non-empty list of
tasks that all exist and are completed, is raised too: an agent told to
record a prerequisite task with addBlockedBy, at TaskCreate or after a
raise, is told this hook raises the task when that prerequisite is done. A
raise for prerequisites also records the completed blockedBy list, so the
same blockers do not raise the task a second time. A deleted blocker frees such
a task without raising it, because nothing it waited on was done.

RAISED ONCE. The hook records, per task, the prerequisites list it raised
the task for, or for a task raised because its blockers completed, its
blockedBy list, and does not raise the task again for the same value;
changing either lets the task be raised again. A record written under the
old key name `waits_on` counts as the same record, so moving a list to the
new key unchanged raises nothing again. The old keys a task was named for
are recorded too, so it is named again only when the old keys it carries
change. The Stop hook's
additionalContext continues the conversation, so a hook that said the same
thing at every turn boundary would never let the agent stop. The record is
written atomically BEFORE anything is printed, and no raise is printed if the
write fails, so a raise whose record was lost cannot happen; the failed write
is reported as a fault instead, as OUTPUT says.

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

GITHUB, and only for prerequisites. A condition is checked with `gh pr view` or
`gh issue view` (read-only), GH_TOKEN removed from the environment so gh
uses its keyring login, stdin closed, each call bounded by
GH_CALL_TIMEOUT_SECONDS and all of a run's calls together by
GH_CALLS_TOTAL_BUDGET_SECONDS. A condition checked within
CONDITION_RECHECK_INTERVAL_SECONDS is answered from the state file. A check
gh could not answer, because gh is missing, failed, timed out or printed no
JSON object, is not an answer: no task waiting on it is raised, it is
recorded as a failure with its time so it too waits the interval, and the
stop that asked reports it, as OUTPUT says. No condition is checked for a
task already raised for its current prerequisites, or held by blockedBy, so
an agent-seat whose tasks have no prerequisites makes no network call. The same call
fetches the title and URL the raise line cites; a condition gh never
answered is cited by its number alone.

THE NEXT-ACTION PROMPT. At a stop that raises no task and names no old key,
the hook hands the agent NEXT_ACTION_INSTRUCTIONS, which tell it to start
subagents on ready work and build an approval-walk, when every one of these
holds; otherwise it says nothing about it:
  - the payload names a session, a transcript that exists, and a cwd inside
    a git checkout that has docs/walk/;
  - no walk-minutes there has an unclosed `#next_to_present` line, paused
    or not, as the walk-me-through finder module reads it;
  - neither the handoff hook's asked marker nor its deferred marker exists
    for the session;
  - the handoff hook's work_in_flight finds no subagent or background task
    running; a transcript it cannot fully read counts as work running;
  - the session has run a tool since this hook last handed it the prompt.
    The state file's `next_action_prompt` entry holds the session id and the
    id of the newest tool call the transcript held when the prompt was
    handed; a stop that finds both unchanged is silent, so an agent that
    stops again without running a tool is let stop, and the hook never
    loops.
Code gathers what it can for the agent: the open tasks no blockedBy or
unmet prerequisite holds back (prerequisites are answered by the same gh
checker, and one gh could not answer holds its task), the count of the
held ones, and every walk-minutes line marked `<open>`, each list cut at a
limit with a count of the rest. Which listed task is ready, which needs the
user, and what the walk holds is the agent's judgment. The entry is written
with the rest of the state, before the prompt is printed. A fault while
deciding, such as a walk-minutes file that cannot be read, is reported on
stderr with exit 1, saying the tasks were checked, and writes no state.

OUTPUT. Something to raise, a task to name, or the next-action prompt: one JSON object,
{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}},
which Claude Code delivers to the model as non-error feedback while the
conversation continues. No `decision` field and no `systemMessage`: the text
is for the agent. The text is one instruction per due task, then, when any
task was raised, the instruction for a task that cannot be acted on yet,
then the lines for each task still carrying an old key, then the
next-action prompt's lines, then one line per condition gh could not answer
at this stop. Nothing to raise, no task to name for an old key and no
next-action prompt: nothing printed, exit 0. A fault, such as a payload
that is not a JSON object, a state file that cannot be written, a condition
gh could not answer at a stop with nothing else to print, or any exception:
one line on stderr naming the hook and the fault, nothing on stdout, exit 1.
The line for a failed state write says how many due tasks went unraised, or
that none was due, and how many tasks carrying an old key went unnamed, and
that the first stop after the state file can be written raises and names
them; the line for a condition gh could not answer quotes gh's failure; the
line for any other fault says no task was checked. Claude Code records a
Stop hook's exit 1 as a non-blocking error and still ends the turn. Exit 2 and additionalContext would both continue the conversation, and a
fault that recurs at every stop would then never let the agent stop.

ONLY THE AGENT-SEAT'S OWN SESSION IS RAISED, never a headless `claude -p`
child an agent-seat's program starts. A child inherits the agent-seat's
environment, CLAUDE_CODE_TASK_LIST_ID included, and the raise text would be
the last thing the child says, which its caller reads as the answer. Two
signals silence the hook:

  NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER set, the variable
      scripts/ghi-guide-agent-ask.py sets for its child and the handoff hook also
      honours.
  CLAUDE_CODE_SESSION_ATTENDED == "0". Claude Code sets this for every hook
      it runs: "1" in an interactive session, "0" in a `claude -p` child,
      even when the child inherited "1" from the agent-seat. The Stop payload
      carries no field that tells the two apart. A missing variable does not
      silence the hook, so a Claude Code that stops setting it costs the
      headless guard, not the agent-seat's reminders.

The project's own headless Claude callers run no project hook at all: the
cold-read Claude cell, and the restater-judge cell through it, pass
`--settings` with disableAllHooks; scripts/ghi-guide-agent-ask.py and
scripts/sanity-check-adversarial-prompts.py pass `--setting-sources user`. The two
signals cover a child started any other way.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Every Stop hook obeys this rule first: see the module's docstring.
_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

_HOOK_DIRECTORY = Path(__file__).resolve().parent


def _load_module_by_path(module_name: str, path: Path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


TASK_LIST_ID_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"
TASKS_ROOT_UNDER_HOME = Path(".claude") / "tasks"
STATE_DIRECTORY_UNDER_HOME = (Path(".local") / "state" / "claude"
                              / "agent-seat-due-task-raise-state")
OPEN_TASK_STATUSES = ("pending", "in_progress")
COMPLETED_TASK_STATUS = "completed"

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

PREREQUISITES_KEY = "prerequisites"
PREREQUISITES_OLD_KEY = "waits_on"
DUE_TIME_OLD_KEY = "due_utc"

DEFER_INSTRUCTION = (
    "If a task above cannot be acted on yet, record what it now waits on with TaskUpdate "
    "instead: a pull request or a GHI in a new metadata.prerequisites, or a task with "
    "addBlockedBy."
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


def completed_blockers(task: dict, tasks: dict) -> "list | None":
    """The blockedBy ids, sorted, when every one names a completed task; else None.

    Called only for a task is_held_by_blockers let through, so every blocker
    that exists is completed and only a deleted one is left to rule out.
    """
    blocked_by = task.get("blockedBy")
    if not isinstance(blocked_by, list) or not blocked_by:
        return None
    if not all(blocker in tasks for blocker in blocked_by):
        return None
    return sorted(set(blocked_by), key=lambda text: (len(text), text))


def is_held_by_blockers(task: dict, tasks: dict, directory: Path) -> bool:
    blocked_by = task.get("blockedBy") or []
    if not isinstance(blocked_by, list):
        return True
    return any(blocker_holds(blocker, tasks, directory) for blocker in blocked_by)


def parse_prerequisites(value) -> "list | None":
    """The prerequisites list as [(kind, number), ...], or None if any entry is unreadable."""
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


def canonical_prerequisites(value) -> str:
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
    result = {
        "raised": raised if isinstance(raised, dict) else {},
        "checks": checks if isinstance(checks, dict) else {},
    }
    if isinstance(state.get(NEXT_ACTION_STATE_KEY), dict):
        result[NEXT_ACTION_STATE_KEY] = state[NEXT_ACTION_STATE_KEY]
    return result


def write_state_atomically(path: Path, state: dict) -> None:
    """Replace the state file in one rename; raises OSError when it did not land."""
    temporary_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, str(path))
    except OSError:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise


class GitHubConditionChecker:
    """Answers prerequisite conditions from the cache or from gh, within a budget."""

    def __init__(self, checks: dict, now_epoch: float):
        self.checks = checks
        self.now_epoch = now_epoch
        self.started = time.monotonic()
        self.changed = False
        self.gh_failures = []

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
        if "gh_failure" in fresh:
            self.gh_failures.append((kind, number, fresh["gh_failure"]))
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
        """Return {"met": ..., "title": ..., "url": ...}, or {"gh_failure": <cause>} when gh did not answer."""
        subcommand, met_state, _, _ = CONDITION_KINDS[kind]
        environment = dict(os.environ)
        environment.pop("GH_TOKEN", None)
        command = ["gh", subcommand, "view", str(number), "--repo", GITHUB_REPOSITORY,
                   "--json", "state,title,url"]
        command_text = f"`{' '.join(command)}`"
        try:
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=timeout_seconds, env=environment, check=False)
        except subprocess.TimeoutExpired:
            return {"gh_failure": f"{command_text} did not answer within "
                                  f"{timeout_seconds:g} seconds"}
        except (OSError, subprocess.SubprocessError) as error:
            return {"gh_failure": f"{command_text} could not be run: {error}"}
        if completed.returncode != 0:
            return {"gh_failure": f"{command_text} exited {completed.returncode}: "
                                  f"{single_line(completed.stderr) or 'with nothing on stderr'}"}
        try:
            answer = json.loads(completed.stdout)
        except ValueError:
            answer = None
        if not isinstance(answer, dict):
            return {"gh_failure": f"{command_text} exited 0 without printing a JSON object"}
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


def gh_failure_line(kind: str, number: int, cause: str) -> str:
    _, _, id_type, met_word = CONDITION_KINDS[kind]
    return (f"This hook could not ask GitHub whether {id_type} {number} is {met_word}, so no "
            f"task waiting on it was raised: {cause}. It asks again at the first stop at least "
            f"{CONDITION_RECHECK_INTERVAL_SECONDS // 60} minutes from now. If gh's error says "
            f"{id_type} {number} does not exist, correct the metadata.prerequisites that names it "
            f"with TaskUpdate. If it says gh is not logged in or its credentials are bad, ask "
            f"the user to run `gh auth login` on this machine.")


def raise_line(task: dict, met_citations, done_blockers=None) -> str:
    reasons = []
    if met_citations is not None:
        reasons.append("its prerequisites are met: " + "; ".join(met_citations))
    if done_blockers is not None:
        reasons.append("the tasks it waited on are completed: "
                       + ", ".join(f"task {single_line(blocker)}" for blocker in done_blockers))
    return (f'Act on task {task["id"]} "{single_line(task.get("subject", ""))}" '
            f"now: {', and '.join(reasons)}.")


def old_keys_line(task: dict, old_keys: dict) -> str:
    """What the agent must change with TaskUpdate for each old key the task carries."""
    changes = []
    if PREREQUISITES_OLD_KEY in old_keys:
        changes.append(
            f"metadata.{PREREQUISITES_OLD_KEY} is the old name of metadata.{PREREQUISITES_KEY}: "
            f"set metadata.{PREREQUISITES_KEY} to the same list, unless metadata."
            f"{PREREQUISITES_KEY} already holds what the task waits on, then set metadata."
            f"{PREREQUISITES_OLD_KEY} to null")
    if DUE_TIME_OLD_KEY in old_keys:
        changes.append(
            f"metadata.{DUE_TIME_OLD_KEY} held a due time, which no hook reads any more: set "
            f"metadata.{DUE_TIME_OLD_KEY} to null, and if the task waits on a pull request or "
            f"a GHI, record it in metadata.{PREREQUISITES_KEY}, or on a task, with addBlockedBy")
    return (f'Task {task["id"]} "{single_line(task.get("subject", ""))}" still carries an old '
            f"metadata key; change it with TaskUpdate: {'; and '.join(changes)}.")


def due_task_lines(tasks: dict, directory: Path, state: dict, now: datetime) -> "tuple[list, list, bool, list]":
    """The raise lines, the old-key lines, whether the state changed, and the gh failure lines.

    Mutates `state` to record every raise and every old-key line it returns,
    and to prune entries for tasks and conditions that no longer need them.
    """
    raised = state["raised"]
    checker = GitHubConditionChecker(state["checks"], now.timestamp())
    lines = []
    old_key_lines = []
    state_changed = False
    conditions_still_named = set()

    for task_id in sorted(tasks, key=lambda text: (len(text), text)):
        task = tasks[task_id]
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        metadata = task.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            continue
        record = raised.get(task_id) if isinstance(raised.get(task_id), dict) else {}
        new_record = dict(record)

        old_keys = {key: metadata[key] for key in (PREREQUISITES_OLD_KEY, DUE_TIME_OLD_KEY)
                    if key in metadata}
        old_keys_record = canonical_prerequisites(old_keys) if old_keys else None
        if record.get("old_keys") != old_keys_record:
            if old_keys_record is None:
                del new_record["old_keys"]
            else:
                new_record["old_keys"] = old_keys_record
                old_key_lines.append(old_keys_line(task, old_keys))

        prerequisites_value = metadata.get(PREREQUISITES_KEY)
        if prerequisites_value is None:
            prerequisites_value = metadata.get(PREREQUISITES_OLD_KEY)
        conditions = parse_prerequisites(prerequisites_value)
        if conditions is not None:
            conditions_still_named.update(condition_key(k, n) for k, n in conditions)

        prerequisite_citations = None
        done_blockers = None
        if not is_held_by_blockers(task, tasks, directory):
            blockers = completed_blockers(task, tasks)
            already_raised_for_prerequisites = False
            if conditions is not None:
                prerequisites_record = canonical_prerequisites(prerequisites_value)
                recorded = record.get(PREREQUISITES_KEY, record.get(PREREQUISITES_OLD_KEY))
                already_raised_for_prerequisites = recorded == prerequisites_record
                if not already_raised_for_prerequisites:
                    answers = [(kind, number, checker.answer(kind, number))
                               for kind, number in conditions]
                    if all(answer.get("met") is True for _, _, answer in answers):
                        prerequisite_citations = [
                            condition_citation(kind, number, answer)
                            for kind, number, answer in answers]
                        new_record.pop(PREREQUISITES_OLD_KEY, None)
                        new_record[PREREQUISITES_KEY] = prerequisites_record
                        if blockers is not None:
                            new_record["blocked_by"] = blockers
            if ((prerequisites_value is None or already_raised_for_prerequisites)
                    and blockers is not None and record.get("blocked_by") != blockers):
                done_blockers = blockers
                new_record["blocked_by"] = blockers
            if prerequisite_citations is not None or done_blockers is not None:
                lines.append(raise_line(task, prerequisite_citations, done_blockers))

        if new_record != record:
            if new_record:
                raised[task_id] = new_record
            else:
                del raised[task_id]
            state_changed = True

    for task_id in list(raised):
        if task_id not in tasks:
            del raised[task_id]
            state_changed = True
    for key in list(state["checks"]):
        if key not in conditions_still_named:
            del state["checks"][key]
            state_changed = True
    return lines, old_key_lines, state_changed or checker.changed, [
        gh_failure_line(kind, number, cause) for kind, number, cause in checker.gh_failures]


WALK_FINDER_FILE = (_HOOK_DIRECTORY.parent / "nc-systems" / "skills" / "walk-me-through"
                    / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")
HANDOFF_THRESHOLD_HOOK_FILE = _HOOK_DIRECTORY / "handoff-context-threshold-hook.py"
TRANSCRIPT_RECORDS_FILE = _HOOK_DIRECTORY / "claude-code-session-transcript-records-read-backward-common.py"
NEXT_ACTION_STATE_KEY = "next_action_prompt"
OPEN_OUTCOME_MARK = "<open>"
NEXT_ACTION_LISTED_TASKS_LIMIT = 40
NEXT_ACTION_LISTED_OPEN_ITEMS_LIMIT = 15
NEXT_ACTION_LISTED_LINE_CHARACTERS = 160

NEXT_ACTION_INSTRUCTIONS = (
    "No approval-walk is open and none of your work is running, so do not stop here.",
    "Tell the user in one line that you are building a new approval-walk.",
    "Start subagents now on every ready task that needs no review or approval from the user.",
    "Build an approval-walk of 8 to 16 items, more than 16 only for one large thing with many "
    "parts, from your loose-ends, open questions, concerns, suggestions and tasks that need the "
    "user; put first what makes the user's interaction easier and what makes agents or the "
    "process faster or cheaper.",
    "If you have none of these at all, ask ghi-guide-agent for 3 to 5 GHIs to work on, with "
    "`python3 scripts/ghi-guide-agent-ask.py \"Which 3 to 5 open GHIs would most improve how "
    "easy the user's interaction with agents is, or how fast or cheap agents and the "
    "development process are?\"`, choose among them the same way, and make them the walk's "
    "items.",
)
NEXT_ACTION_UNHELD_TASKS_HEADER = (
    "Your open tasks that no recorded prerequisite or blocker holds back; which of them are "
    "ready, and which need the user, is yours to judge:")
NEXT_ACTION_HELD_TASKS_LINE = (
    "{count} more open task(s) wait on a prerequisite or blocker that is not done, or that "
    "GitHub could not answer for, so they are not listed.")
NEXT_ACTION_OPEN_ITEMS_HEADER = (
    "Lines your walk-minutes mark <open>; each is a loose-end unless a task, GHI, pull request "
    "or later walk now holds it:")
NEXT_ACTION_MORE_LINE = "and {count} more."
NEXT_ACTION_STOP_AGAIN_LINE = (
    "If you end your turn again without running a tool, this hook lets the turn end.")


def shortened(text: str) -> str:
    text = single_line(text)
    if len(text) <= NEXT_ACTION_LISTED_LINE_CHARACTERS:
        return text
    return text[:NEXT_ACTION_LISTED_LINE_CHARACTERS - 3] + "..."


def newest_tool_use_id(records) -> "str | None":
    """The id of the newest tool call the transcript records, or None when it records none."""
    for record in records:
        message = record.get("message")
        if record.get("type") != "assistant" or not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return str(block.get("id"))
    return None


def open_outcome_lines(walk_directory: Path) -> list:
    """`<file>:<line>: <text>` for each walk-minutes line marked <open>, oldest file first."""
    found = []
    minutes_files = sorted(walk_directory.glob("*-minutes.md"),
                           key=lambda path: (path.stat().st_mtime, path.name))
    for minutes in minutes_files:
        for number, line in enumerate(minutes.read_text(encoding="utf-8").splitlines(), 1):
            if OPEN_OUTCOME_MARK in line:
                found.append(f"{minutes.name}:{number}: {shortened(line)}")
    return found


def unheld_and_held_tasks(tasks: dict, directory: Path, checker) -> "tuple[list, int]":
    """Open tasks nothing recorded holds back, oldest first, and the count of those held."""
    unheld = []
    held = 0
    for task_id in sorted(tasks, key=lambda text: (len(text), text)):
        task = tasks[task_id]
        if task.get("status") not in OPEN_TASK_STATUSES:
            continue
        if is_held_by_blockers(task, tasks, directory):
            held += 1
            continue
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        prerequisites_value = metadata.get(PREREQUISITES_KEY)
        if prerequisites_value is None:
            prerequisites_value = metadata.get(PREREQUISITES_OLD_KEY)
        if prerequisites_value is not None:
            conditions = parse_prerequisites(prerequisites_value)
            if conditions is None or not all(
                    checker.answer(kind, number).get("met") is True for kind, number in conditions):
                held += 1
                continue
        unheld.append(f'task {task_id} "{shortened(task.get("subject", ""))}"')
    return unheld, held


def listed_with_limit(header: str, entries: list, limit: int) -> list:
    if not entries:
        return []
    lines = [header] + [f"- {entry}" for entry in entries[:limit]]
    if len(entries) > limit:
        lines.append(NEXT_ACTION_MORE_LINE.format(count=len(entries) - limit))
    return lines


def next_action_prompt_lines(payload: dict, tasks: dict, directory: Path, state: dict,
                             now: datetime) -> "list | None":
    """The next-action prompt's lines, or None when the hook stays silent about it.

    Silent when the session cannot be told idle: no readable transcript, no
    checkout with a walk directory, an approval-walk open or paused, a
    handoff asked or deferred, work in flight or work that cannot be counted,
    or no tool run since this hook last gave the prompt in this session.
    Records the prompt in `state` when it returns lines.
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    cwd = payload.get("cwd")
    if not session_id or not transcript_path or not cwd:
        return None
    transcript = Path(transcript_path).expanduser()
    if not transcript.is_file():
        return None
    walk_finder = _load_module_by_path(
        "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
        WALK_FINDER_FILE)
    top = walk_finder.checkout_top(Path(cwd))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    walk_directory = top / walk_finder.WALK_DIRECTORY
    if walk_finder.newest_unclosed_approval_walk_including_paused(
            walk_directory, walk_finder.markdown_parser()) is not None:
        return None
    handoff = _load_module_by_path("handoff_context_threshold_hook", HANDOFF_THRESHOLD_HOOK_FILE)
    if (handoff.fired_marker_path(session_id).exists()
            or handoff.deferred_marker_path(session_id).exists()):
        return None
    try:
        if handoff.work_in_flight(str(transcript),
                                  handoff.DEFAULT_BACKGROUND_TASK_WAIT_MINUTES * 60, now=now):
            return None
    except handoff.TranscriptCouldNotBeFullyRead:
        return None  # running work that cannot be counted is not idleness
    records = _load_module_by_path("claude_code_session_transcript_records_read_backward_common",
                                   TRANSCRIPT_RECORDS_FILE).records_newest_first(transcript)
    tool_use_id = newest_tool_use_id(records)
    recorded = state.get(NEXT_ACTION_STATE_KEY)
    this_prompt = {"session_id": session_id, "newest_tool_use_id": tool_use_id}
    if recorded == this_prompt:
        return None
    state[NEXT_ACTION_STATE_KEY] = this_prompt

    checker = GitHubConditionChecker(state["checks"], now.timestamp())
    unheld, held = unheld_and_held_tasks(tasks, directory, checker)
    lines = list(NEXT_ACTION_INSTRUCTIONS)
    lines += listed_with_limit(NEXT_ACTION_UNHELD_TASKS_HEADER, unheld,
                               NEXT_ACTION_LISTED_TASKS_LIMIT)
    if held:
        lines.append(NEXT_ACTION_HELD_TASKS_LINE.format(count=held))
    lines += listed_with_limit(NEXT_ACTION_OPEN_ITEMS_HEADER, open_outcome_lines(walk_directory),
                               NEXT_ACTION_LISTED_OPEN_ITEMS_LIMIT)
    lines.append(NEXT_ACTION_STOP_AGAIN_LINE)
    return lines


class HookFault(Exception):
    """A fault the hook reports on stderr instead of raising anything."""


def run(stdin_text: str, environment, home: Path, now: datetime) -> "str | None":
    """The JSON to print, or None for silence; raises on a fault."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise HookFault("the payload Claude Code sent on stdin is JSON, but not an object, "
                        "so no task was checked")
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
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
    lines, old_key_lines, state_changed, gh_failure_lines = due_task_lines(
        tasks, directory, state, now)
    next_action_lines = []
    if not lines and not old_key_lines:
        try:
            next_action_lines = next_action_prompt_lines(payload, tasks, directory, state,
                                                         now) or []
        except Exception as error:
            raise HookFault(f"every task was checked and none was due, but the check whether to "
                            f"hand the next-action prompt failed, so none was handed at this "
                            f"stop: {type(error).__name__}: {error}") from error
        state_changed = state_changed or bool(next_action_lines)
    if state_changed:
        try:
            write_state_atomically(state_path, state)
        except OSError as error:
            if lines:
                outcome = (f"so {len(lines)} due task(s) were not raised at this stop; the "
                           f"first stop after the state file can be written raises them")
            else:
                outcome = "no task was due at this stop, so none went unraised"
            if old_key_lines:
                outcome += (f", and {len(old_key_lines)} task(s) still carrying an old key were "
                            f"not named; that stop names them")
            raise HookFault(f"the state file {state_path} could not be written, and {outcome}. "
                            f"Make {state_path.parent} a directory this user can write to: "
                            f"{error}") from error
    if not lines and not old_key_lines and not next_action_lines:
        if gh_failure_lines:
            raise HookFault(" ".join(gh_failure_lines))
        return None
    defer_lines = [DEFER_INSTRUCTION] if lines else []
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "\n".join(lines + defer_lines + old_key_lines
                                           + next_action_lines + gh_failure_lines),
        }
    }, ensure_ascii=False)


def main() -> int:
    try:
        output = run(sys.stdin.read(), os.environ, Path.home(),
                     datetime.now(timezone.utc))
        if output is not None:
            print(output)
    except HookFault as error:
        print(f"agent-seat-due-task-raise-hook: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"agent-seat-due-task-raise-hook: the hook failed, so no task was checked at "
              f"this stop; the first stop without this fault raises any task that is due: "
              f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
