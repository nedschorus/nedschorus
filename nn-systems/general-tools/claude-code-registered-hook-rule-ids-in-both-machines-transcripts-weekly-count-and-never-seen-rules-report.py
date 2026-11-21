#!/usr/bin/env python3
"""Count each registered hook's rule IDs in both machines' transcripts, and write one report listing
the rules not seen since their IDs were added.

    python3 <this file> [--transcript-directory <directory> ...] [--report-directory <directory>]

The rules are those whose `[rule <id>]` the hooks .claude/settings.json registers write in their
source, in this program's own checkout, as
nn-systems/general-tools/claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py
finds them. Each is counted in the transcripts under each --transcript-directory, by default the two
copies scripts/transcript-mirror-to-log-store.py keeps in the log-store on ned-box:
/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/mac/projects, the Mac's, and
/home/nedlern/nedsnodes-logs/agent-session-files-by-machine/ned-box/projects, ned-box's. Subagents' transcripts below them are read too.

What counts as a firing: an ID in text a hook handed the agent, and nowhere else, so a transcript in
which an agent reads, tests or quotes a hook's source counts nothing. Within that text, only an ID that
opens the text or one of its lines counts, as a rule's message starts with its ID; a refusal's leading
`<event>... hook error: `, such as `PreToolUse:Bash hook error: `, and any `[command hook <n>]: `
after it are stripped first, so the ID after them opens the text. An ID further into a line, such as
one in a diff of a hook's source that another hook's reminder carries, does not count. That text is the content of an attachment record of type hook_additional_context, the blockingError of one of type
hook_blocking_error, and a tool result whose text starts `<event>... hook error:`, which is how a
PreToolUse refusal reaches the agent. hook_success records and `Stop hook feedback:` messages are not
read at all, since they repeat that text. A firing counts when its record's timestamp is no earlier
than the commit that added its rule's ID, and only transcripts whose file modification time (mtime) is
no earlier than the earliest of all the rules' ID commits are read.

When a rule's ID was added: the oldest commit in this checkout's history whose added lines hold
`[rule <id>]`, searched across every file. A hook file renamed, a constant renamed or a message reworded
after that commit changes nothing here: the later commit is not the oldest, so the ID keeps its date and
its author. The search runs `git log -p` without -m or --cc, which prints a merge commit with no diff,
so a merge commit is never the commit that adds an ID: a line a merge brings in is found in the commit on
the merged branch that added it, and an ID that a merge commit's own change added, such as a conflict
resolution, is found in no commit's diff, so its rule must be listed in the .json file named under
"Who wrote the rule", and every firing of it in the transcripts read is counted, whatever its date.

Who wrote the rule: two kinds of rule are listed in
nn-systems/general-tools/claude-code-registered-hook-rule-id-to-origin-commit-pr-and-agent-seat-of-rules-whose-message-predates-its-id.json,
each with the commit that first wrote its message, the pull request that brought that commit, or null
when the commit went onto main without one, and the agent-seat that wrote it. The first kind are the
rules whose messages were written before their IDs existed, which got their IDs all at once in the pull
request that added the IDs: git cannot find the commit that wrote the message from the ID, which came
after the message, nor from the message's words or its constant's name, which in many hooks were changed
after the message was first written. The second kind are rules whose ID a merge commit's own change
added, as above, as the merge's author need not be who wrote the rule. Any other rule was written with
its ID, so the commit that added the ID wrote the rule, and the pull request and agent-seat come from
that commit:
- A commit on this checkout's first-parent history whose subject ends `(#<number>)` is a pull request
  squash-merged on GitHub: the pull request is that number, and the agent-seat is not known, as the
  commit carries the name of whoever merged it; the report says to read the pull request's description.
- A commit on the first-parent history whose subject does not end so was committed straight to main: no
  pull request, and the agent-seat is the commit's author name.
- A commit a merge commit brought in from another branch was brought by the oldest merge on the
  first-parent history that holds it: the pull request is read
  from that merge's subject `Merge pull request #<number> from ...`, and the agent-seat is the commit's
  author name, the name that agent-seat commits under.

The report goes to <report directory>/<job name>-<YYYY-MM-DD>-report.md, the job name being this
file's name without .py and the date UTC, replacing a report written earlier the same day; the default
report directory is the directory the environment variable NEDSNODES_MAINTENANCE_JOB_REPORTS_DIRECTORY
names when it is set, as the test sets it, and otherwise the log-store's
/home/nedlern/nedsnodes-logs/maintenance-job-reports. The report lists the rules not seen, each
with its hook, the date its ID was added, the agent-seat that wrote it and its pull request, as
candidates to question, not verdicts: a guard against a rare, permanent harm may rightly never fire.
It then gives every rule's count, and the IDs found in transcripts that no registered hook writes. It
keeps no state: each run counts again from each ID's commit. The program prints the report's path.

It runs once a week on ned-box, from the table nn-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nn-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    30 5 * * 1 /usr/bin/python3 /home/nedlern/Projects/nedsnodes/nn-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py >> /home/nedlern/.claude/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.log 2>&1

Not counted: a firing in a transcript the mirror has not copied yet, about a minute behind; a rule
written only in prose, such as in CLAUDE.md; a rule whose message carries no ID, such as text built
outside a message constant.

Exit status: 0 when the report was written and every transcript directory, transcript and git lookup
was read. 1 when a transcript directory, a transcript or a git lookup could not be read: the report is
still written, and says which, since its never-seen list may then be wrong; when a registered hook
writes an ID that no commit's diff in `git log -p` adds and whose rule the .json file named under "Who
wrote the rule" does not list, so who wrote the rule cannot be found: the report is still written, and a
FAILED line on stderr names each such ID; or when the report could not be written, which is printed
on stderr. 2 for a bad command line.

What to do about each problem is printed on stderr after the problem lines: one block after all the
`not read:` lines, covering each kind of `not read:` line; and one block after all the FAILED lines that
name an ID, giving for each ID only the case that applies, which the program finds with git in this
checkout: a merge commit's own change added the ID, so the step names no writer and says to ask the user
for the rule's .json entry; or the ID is in
an edit not yet committed, on main, on a detached HEAD, on a branch pushed to origin, or on a branch not
pushed. When a git command that finds the case fails, the block quotes that command and its error
instead. The FAILED line for a report not written says what to do itself.
"""
import argparse
import datetime
import getpass
import importlib.util
import json
import mmap
import os
import re
import shlex
import socket
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
JOB_NAME = Path(__file__).stem
LOG_STORE = Path("/home/nedlern/nedsnodes-logs")
DEFAULT_TRANSCRIPT_DIRECTORIES = (LOG_STORE / "agent-session-files-by-machine" / "mac" / "projects",
                                  LOG_STORE / "agent-session-files-by-machine" / "ned-box" / "projects")
REPORT_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSNODES_MAINTENANCE_JOB_REPORTS_DIRECTORY"
DEFAULT_REPORT_DIRECTORY = Path(os.environ.get(REPORT_DIRECTORY_ENVIRONMENT_VARIABLE)
                                or LOG_STORE / "maintenance-job-reports")
GIT_TIMEOUT_SECONDS = 60
RULE_ID_BYTES = b"[rule "
HOOK_ERROR_TOOL_RESULT_PATTERN = re.compile(r"^[A-Za-z]+(?::\S*)? hook error: ")
HOOK_ERROR_PREFIX_PATTERN = re.compile(r"^[A-Za-z]+(?::\S*)? hook error: (?:\[[^\]\n]*\]: )?")
RULES_WRITTEN_BEFORE_THEIR_IDS_PATH = Path(__file__).with_name(
    "claude-code-registered-hook-rule-id-to-origin-commit-pr-and-agent-seat-of-rules-whose-message-predates-its-id.json")
# What --format=%x00 puts before each commit line, as no diff line starts with it.
COMMIT_LINE_START = "\x00"
MERGE_SUBJECT_PATTERN = re.compile(r"^Merge pull request #(\d+) ")
SQUASH_MERGE_SUBJECT_PATTERN = re.compile(r"\(#(\d+)\)\s*$")
SQUASH_MERGED_AGENT_SEAT_NOTE = "squash-merged, so its agent-seat is in the pull request's description"
REPORT_NOTE_AUTHOR_UNKNOWN_FOR_HOOK_RULE_WHOSE_ID_IS_IN_NO_GIT_COMMIT = (
    "no commit's diff in `git log -p` adds its ID, so who wrote it is not known")
CANDIDATES_NOT_VERDICTS_LINE = (
    "Each rule below is a candidate to question, not a verdict: a guard against a rare, permanent harm "
    "may rightly never fire.")


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


rule_ids = _load("claude_code_registered_hook_rule_id_pattern_hook_files_list_and_source_scan_common",
                 REPOSITORY / "nn-systems" / "general-tools"
                 / "claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py")
RULE_ID_OPENING_A_LINE_PATTERN = re.compile(r"^[ \t]*" + rule_ids.RULE_ID_PATTERN.pattern, re.MULTILINE)


class GitLookupFailed(Exception):
    pass


def git(repository, *arguments):
    try:
        completed = subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True,
                                   timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitLookupFailed(f"`{shlex.join(['git', '-C', str(repository), *arguments])}` failed: {error}") from error
    if completed.returncode != 0:
        raise GitLookupFailed(f"`{shlex.join(['git', '-C', str(repository), *arguments])}` exited {completed.returncode}: "
                              f"{completed.stderr.strip()[:300]}")
    return completed.stdout


def registered_rules(repository):
    """[{id, hook, line}] for each rule ID the registered hooks write, first place only."""
    rules = []
    for hook in rule_ids.registered_hook_paths(repository / ".claude" / "settings.json"):
        try:
            source = (repository / hook).read_text(encoding="utf-8")
        except OSError:
            continue
        for rule_id, lines in sorted(rule_ids.rule_ids_in_source(source).items()):
            rules.append({"id": rule_id, "hook": hook, "line": lines[0]})
    return rules


def commits_adding_each_rule_id(repository):
    """{rule ID: (sha, committer time)} of the oldest commit whose added lines hold the ID, in any file."""
    output = git(repository, "log", "--reverse", "--format=%x00%H %cI", "--unified=0",
                 "-G", r"\[rule ", "-p", "HEAD")
    commits, current = {}, None
    for line in output.splitlines():
        if line.startswith(COMMIT_LINE_START):
            sha, when = line[1:].split(" ", 1)
            current = sha, datetime.datetime.fromisoformat(when)
        elif current and line.startswith("+") and not line.startswith("+++"):
            for rule_id in rule_ids.RULE_ID_PATTERN.findall(line):
                commits.setdefault(rule_id, current)
    return commits


def hook_rule_id_to_origin_commit_pull_request_and_agent_seat_of_rules_whose_message_predates_its_id_json_load(path=None):
    """{rule ID: {commit, pull_request, agent_seat}} from RULES_WRITTEN_BEFORE_THEIR_IDS_PATH."""
    return json.loads((path or RULES_WRITTEN_BEFORE_THEIR_IDS_PATH).read_text(encoding="utf-8"))


def first_parent_merges_oldest_first(repository):
    output = git(repository, "log", "--first-parent", "--merges", "--reverse", "--format=%H %s", "HEAD")
    return [line.split(" ", 1) for line in output.splitlines() if line]


def first_parent_commit_subjects(repository):
    """{sha: subject} of every commit on HEAD's first-parent history."""
    output = git(repository, "log", "--first-parent", "--format=%H %s", "HEAD")
    return dict(line.split(" ", 1) if " " in line else (line, "") for line in output.splitlines() if line)


def pull_request_bringing(repository, sha, merges, first_parent_subjects):
    """The number of the pull request that brought the commit, or None when none did: for a commit on
    the first-parent history, the `(#<number>)` its subject ends with, as GitHub's squash merge writes
    it; for any other, the oldest merge on the first-parent history that holds it."""
    if sha in first_parent_subjects:
        match = SQUASH_MERGE_SUBJECT_PATTERN.search(first_parent_subjects[sha])
        return match.group(1) if match else None
    low, high = 0, len(merges)
    while low < high:
        middle = (low + high) // 2
        holds = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", sha, merges[middle][0]],
                               capture_output=True, timeout=GIT_TIMEOUT_SECONDS, check=False).returncode == 0
        if holds:
            high = middle
        else:
            low = middle + 1
    if low == len(merges):
        return None
    match = MERGE_SUBJECT_PATTERN.match(merges[low][1])
    return match.group(1) if match else None


def rule_origins(repository, rules, recorded_origins):
    """Fill each rule's added (time its ID was committed), seat, pull_request and origin_note; return
    the git lookups that failed. A rule whose ID is in no commit and not in recorded_origins gets the
    origin_note REPORT_NOTE_AUTHOR_UNKNOWN_FOR_HOOK_RULE_WHOSE_ID_IS_IN_NO_GIT_COMMIT."""
    failures = []
    try:
        merges = first_parent_merges_oldest_first(repository)
        first_parent_subjects = first_parent_commit_subjects(repository)
        id_commits = commits_adding_each_rule_id(repository)
    except GitLookupFailed as error:
        failures.append(str(error))
        merges, first_parent_subjects, id_commits = [], {}, None
    for rule in rules:
        rule.update(added=None, seat=None, pull_request=None, origin_note="")
        if id_commits is None:
            rule["origin_note"] = "its origin could not be read"
            continue
        id_commit = id_commits.get(rule["id"])
        rule["added"] = id_commit[1] if id_commit else None
        recorded = recorded_origins.get(rule["id"])
        if recorded:
            rule["seat"], rule["pull_request"] = recorded["agent_seat"], recorded["pull_request"]
            if not recorded["pull_request"]:
                rule["origin_note"] = "committed to main without a pull request"
            continue
        if id_commit is None:
            rule["origin_note"] = REPORT_NOTE_AUTHOR_UNKNOWN_FOR_HOOK_RULE_WHOSE_ID_IS_IN_NO_GIT_COMMIT
            continue
        try:
            rule["pull_request"] = pull_request_bringing(repository, id_commit[0], merges, first_parent_subjects)
            if id_commit[0] in first_parent_subjects and rule["pull_request"]:
                rule["origin_note"] = SQUASH_MERGED_AGENT_SEAT_NOTE
            else:
                rule["seat"] = git(repository, "log", "-1", "--format=%an", id_commit[0]).strip()
                if not rule["pull_request"] and id_commit[0] in first_parent_subjects:
                    rule["origin_note"] = "committed to main without a pull request"
        except (GitLookupFailed, subprocess.TimeoutExpired, OSError) as error:
            failures.append(f"{rule['id']}: {error}")
            rule["origin_note"] = "its origin could not be read"
    return failures


def counted_texts(record):
    """The texts in one transcript record that a hook handed the agent."""
    if record.get("type") == "attachment":
        attachment = record.get("attachment") or {}
        if attachment.get("type") == "hook_additional_context":
            content = attachment.get("content")
            return [content] if isinstance(content, str) else [c for c in content or [] if isinstance(c, str)]
        if attachment.get("type") == "hook_blocking_error":
            blocking = attachment.get("blockingError")
            if isinstance(blocking, dict):
                blocking = blocking.get("blockingError")
            return [blocking] if isinstance(blocking, str) else []
        return []
    if record.get("type") != "user":
        return []
    content = (record.get("message") or {}).get("content")
    texts = []
    for item in content if isinstance(content, list) else []:
        if not (isinstance(item, dict) and item.get("type") == "tool_result"):
            continue
        result = item.get("content")
        if isinstance(result, list):
            result = "".join(part.get("text", "") for part in result if isinstance(part, dict))
        if isinstance(result, str) and HOOK_ERROR_TOOL_RESULT_PATTERN.match(result):
            texts.append(result)
    return texts


def firing_rule_ids_in_hook_text(text):
    """The rule IDs that open the text, after any hook-error prefix, or open one of its lines."""
    return RULE_ID_OPENING_A_LINE_PATTERN.findall(HOOK_ERROR_PREFIX_PATTERN.sub("", text, count=1))


def record_time(record):
    try:
        return datetime.datetime.fromisoformat(str(record.get("timestamp")).replace("Z", "+00:00"))
    except ValueError:
        return None


def count_in_transcript(path, added_by_id, counts, unknown_counts):
    """Add the transcript's firings to the counts; raise OSError when it cannot be read."""
    with open(path, "rb") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            return
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            if mapped.find(RULE_ID_BYTES) < 0:
                return
            lines = mapped[:].splitlines()
    for line in lines:
        if RULE_ID_BYTES not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        when = record_time(record)
        for text in counted_texts(record):
            for rule_id in firing_rule_ids_in_hook_text(text):
                if rule_id not in added_by_id:
                    unknown_counts[rule_id] = unknown_counts.get(rule_id, 0) + 1
                elif added_by_id[rule_id] is None or (when is not None and when >= added_by_id[rule_id]):
                    counts[rule_id] = counts.get(rule_id, 0) + 1


def count_firings(directories, rules):
    """(counts, unknown_counts, transcripts_read, problems) over the transcripts changed since the
    earliest ID was added."""
    added_by_id = {rule["id"]: rule["added"] for rule in rules}
    known_times = [when for when in added_by_id.values() if when is not None]
    since = min(known_times).timestamp() if known_times else 0
    counts, unknown_counts, problems, read = {}, {}, [], 0
    for directory in directories:
        if not Path(directory).is_dir():
            problems.append(f"{directory}: not a directory this program can read, so it was not counted")
            continue
        for root, _, names in os.walk(directory, onerror=lambda error: problems.append(f"{error.filename}: {error}")):
            for name in names:
                if not name.endswith(".jsonl"):
                    continue
                path = os.path.join(root, name)
                try:
                    if os.stat(path).st_mtime < since:
                        continue
                    count_in_transcript(path, added_by_id, counts, unknown_counts)
                    read += 1
                except (OSError, ValueError) as error:
                    problems.append(f"{path}: {error}")
    return counts, unknown_counts, read, problems


def report_text(today, rules, counts, unknown_counts, directories, read, problems):
    def origin(rule):
        if rule["pull_request"]:
            pull_request = f"PR {rule['pull_request']}"
        else:
            pull_request = rule["origin_note"] or "no pull request found"
        if rule["seat"]:
            seat = rule["seat"]
        elif rule["pull_request"] and rule["origin_note"]:
            seat = f"unknown: {rule['origin_note']}"
        else:
            seat = "unknown"
        return f"{seat} | {pull_request}"

    def added(rule):
        return rule["added"].date().isoformat() if rule["added"] else "no commit adds it"

    unseen = [rule for rule in rules if not counts.get(rule["id"])]
    lines = [f"# Hook rules not seen in the transcripts since their IDs were added, {today}", "",
             f"Read {read} transcripts changed since the earliest rule ID was added, under: "
             + ", ".join(f"`{directory}`" for directory in directories) + "."]
    if problems:
        lines += ["", f"Not read, so a rule listed as not seen below may have fired there ({len(problems)}):"]
        lines += [f"- {problem}" for problem in problems[:50]]
        if len(problems) > 50:
            lines.append(f"- and {len(problems) - 50} more, in this run's cron log")
    lines += ["", f"## Rules not seen ({len(unseen)} of {len(rules)})", "", CANDIDATES_NOT_VERDICTS_LINE, ""]
    if unseen:
        lines += ["| Rule ID | Hook | ID added | Agent-seat that wrote the rule | Pull request that added it |",
                  "|---|---|---|---|---|"]
        lines += [f"| `{rule['id']}` | `{rule['hook']}` | {added(rule)} | {origin(rule)} |" for rule in unseen]
    else:
        lines.append("Every rule was seen at least once.")
    lines += ["", "## Each rule's count since its ID was added", "", "| Rule ID | Count | Hook |", "|---|---|---|"]
    lines += [f"| `{rule['id']}` | {counts.get(rule['id'], 0)} | `{rule['hook']}` |" for rule in rules]
    if unknown_counts:
        lines += ["", "## IDs seen that no registered hook writes", "",
                  "A rule removed or renamed since, or a hook on a branch that has not merged.", "",
                  "| Rule ID | Count |", "|---|---|"]
        lines += [f"| `{rule_id}` | {count} |" for rule_id, count in sorted(unknown_counts.items())]
    return "\n".join(lines) + "\n"


def unknown_origin_case(repository, rule, branch):
    """Which case holds for a rule whose ID no commit's diff adds: "merge" when HEAD's copy of the hook
    holds the ID, so a merge commit's own change added it; otherwise the ID is in an edit not committed,
    and the case is where HEAD is: "detached", "main", "pushed" for a branch origin also has, or
    "unpushed"."""
    in_head = git(repository, "ls-tree", "--name-only", "HEAD", "--", rule["hook"]).strip()
    if in_head and f"[rule {rule['id']}]" in git(repository, "show", f"HEAD:{rule['hook']}"):
        return "merge"
    if not branch:
        return "detached"
    if branch == "main":
        return "main"
    # for-each-ref matches whole path components, so origin/<branch>/<more> is listed too.
    remote = f"refs/remotes/origin/{branch}"
    if remote in git(repository, "for-each-ref", "--format=%(refname)", remote).splitlines():
        return "pushed"
    return "unpushed"


SETTINGS_PATH = ".claude/settings.json"


def uncommitted_rule_edit(repository, hook):
    """(the paths among the hook and .claude/settings.json that differ from HEAD, the path the hook was
    renamed from in the index or None). A new rule's registration in settings.json is part of the same
    edit, and a move that leaves it behind merges a rule nothing runs."""
    # Not limited to the two paths: a pathspec hides the source of a rename and shows its target as added.
    fields = git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    changed, renamed_from, index = set(), None, 0
    while index < len(fields):
        entry, index = fields[index], index + 1
        if not entry:
            continue
        changed.add(entry[3:])
        if entry[0] in "RC":
            if entry[3:] == hook and entry[0] == "R":
                renamed_from = fields[index]
            index += 1
    return [path for path in (hook, SETTINGS_PATH) if path in changed], renamed_from


def undo_of_uncommitted_edit(repository, path):
    """A command that puts path back as HEAD has it, in the index and the working tree, staged or not:
    restored from HEAD when HEAD holds it, and otherwise taken out of the index and deleted."""
    if git(repository, "ls-tree", "--name-only", "HEAD", "--", path).strip():
        return shlex.join(["git", "-C", str(repository), "restore", "--staged", "--worktree", "--source=HEAD",
                           "--", path])
    return (shlex.join(["git", "-C", str(repository), "rm", "-q", "-f", "--cached", "--ignore-unmatch", "--", path])
            + " && " + shlex.join(["rm", "--", str(Path(repository) / path)]))


def unknown_origin_next_steps(repository, rules, machine, rerun_command):
    """The block printed after the FAILED lines of rules whose writer cannot be found: for each rule,
    the next step of the one case that holds."""
    rerun = f"then run, on {machine}:\n    {rerun_command}"
    lines = [f"What to do for each ID a FAILED line above names, found with git in the checkout {repository} "
             f"on {machine}:"]
    try:
        branch = git(repository, "branch", "--show-current").strip()
        cases = []
        for rule in rules:
            case = unknown_origin_case(repository, rule, branch)
            files, renamed_from = (([], None) if case == "merge"
                                   else uncommitted_rule_edit(repository, rule["hook"]))
            # settings.json is left out: restoring it whole would drop other uncommitted edits to it.
            undo = (" && ".join(undo_of_uncommitted_edit(repository, path)
                                for path in [rule["hook"], *([renamed_from] if renamed_from else [])])
                    if case == "main" else "")
            cases.append((rule, case, files, renamed_from, undo))
    except GitLookupFailed as error:
        return (lines[0] + f"\nNot found: which case holds could not be read, because {error}. Run that git "
                f"command, as it is written there, on {machine}, to see why it failed, and fix that; {rerun}")
    for rule, case, files, renamed_from, undo in cases:
        hook, rule_id = rule["hook"], rule["id"]
        named = " and ".join(files) if files else hook
        if case == "merge":
            step = (f"HEAD's copy of {hook} holds the ID, so a merge commit's own change added it, such as a "
                    f"conflict resolution. Who wrote the rule is not known: the merge's author need not be the "
                    f"writer, and this program does not find the commit that first wrote the rule's message. Ask "
                    f"the user which commit first wrote the rule's message, which pull request brought that commit, "
                    f"and which agent-seat wrote it. Then add the rule, on a topic branch, to "
                    f"nn-systems/general-tools/{RULES_WRITTEN_BEFORE_THEIR_IDS_PATH.name}, keyed \"{rule_id}\", with "
                    f"\"commit\": that commit's full hash, \"pull_request\": the pull request's number as a string, "
                    f"or null when the commit went onto main without one, and \"agent_seat\": that agent-seat. The "
                    f"first run of this program after that change merges into main and reaches this checkout says "
                    f"who wrote the rule.")
        elif case == "main":
            registration = f"any changes that register {hook}" + (f" in place of {renamed_from}" if renamed_from else "")
            step = (f"the ID is in an edit to {named} not committed in this checkout, which is on main. If the edit "
                    f"is your work, move the edit to a topic branch: make a worktree for the branch with "
                    f"`cd {repository} && python3 scripts/agent-seat-worktree-create-with-owner-file.py <topic "
                    f"branch name>`, which prints the worktree's path; copy {repository}/{hook} to the same path "
                    f"in that worktree")
            if renamed_from:
                step += (f", run `git -C <that worktree's path> rm -q -- {renamed_from}`, as the edit renamed it to "
                         f"{hook}")
            if SETTINGS_PATH in files:
                step += (f", and make there, in {SETTINGS_PATH}, {registration}, which `git -C {repository} diff "
                         f"HEAD -- {SETTINGS_PATH}` shows; commit there and open a pull request. Then undo the edit "
                         f"here: run `{undo}`, and undo by hand those changes to {repository}/{SETTINGS_PATH}, "
                         f"keeping its other uncommitted changes, which may be another edit's")
            else:
                step += f", commit there and open a pull request, then undo the edit here with `{undo}`"
            step += (". The first run of this program after the pull request merges into main and main reaches "
                     "this checkout says who wrote the rule.\n  If the edit is not your work, leave it to whoever "
                     "is making it.")
        elif case == "detached":
            step = (f"the ID is in an edit to {named} not committed in this checkout, whose HEAD is detached, so a "
                    f"commit made here would be on no branch. If the edit is your work, put it on a branch with "
                    f"`git -C {repository} switch -c <topic branch name>`, commit it there, {rerun}\n"
                    f"  If the edit is not your work, leave it to whoever is making it.")
        else:
            step = (f"the ID is in an edit to {named} not committed on branch {branch}. If the edit is your work, "
                    f"commit it on {branch}")
            if case == "pushed":
                step += (f" as a new commit, not by amending or rebasing, because {branch} is pushed as "
                         f"origin/{branch}, and once its pull request is marked ready, its nc-head-commit is a "
                         f"frozen-head, which must not be rewritten; {rerun}")
            else:
                step += f", {rerun}"
            step += "\n  If the edit is not your work, leave it to whoever is making it."
        lines.append(f"- `[rule {rule_id}]` in {hook}: {step}")
    return "\n".join(lines)


def write_report(report_directory, today, text):
    report_directory.mkdir(parents=True, exist_ok=True)
    path = report_directory / f"{JOB_NAME}-{today}-report.md"
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
    return path


def main(argv=None, now=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transcript-directory", action="append", type=Path,
                        help="a directory of transcripts to count in; repeatable; default: both machines' "
                             "copies in the log-store")
    parser.add_argument("--report-directory", type=Path, default=DEFAULT_REPORT_DIRECTORY,
                        help=f"where the report goes; default: {DEFAULT_REPORT_DIRECTORY}")
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    # Absolute, so the commands printed below work from any directory.
    arguments.report_directory = arguments.report_directory.absolute()
    directories = [directory.absolute() for directory in arguments.transcript_directory or []]
    rerun_arguments = [part for directory in directories for part in ("--transcript-directory", str(directory))]
    if arguments.report_directory != DEFAULT_REPORT_DIRECTORY.absolute():
        rerun_arguments += ["--report-directory", str(arguments.report_directory)]
    rerun_command = "python3 " + shlex.join([str(Path(__file__).resolve()), *rerun_arguments])
    machine = socket.gethostname()
    directories = directories or list(DEFAULT_TRANSCRIPT_DIRECTORIES)
    today = (now or datetime.datetime.now(datetime.timezone.utc)).date().isoformat()

    rules = registered_rules(REPOSITORY)
    git_failures = rule_origins(REPOSITORY, rules, hook_rule_id_to_origin_commit_pull_request_and_agent_seat_of_rules_whose_message_predates_its_id_json_load())
    counts, unknown_counts, read, problems = count_firings(directories, rules)
    problems = [f"git lookup: {failure}" for failure in git_failures] + problems
    text = report_text(today, rules, counts, unknown_counts, directories, read, problems)
    try:
        path = write_report(arguments.report_directory, today, text)
    except OSError as error:
        print(f"{JOB_NAME}: FAILED: the report could not be written to {arguments.report_directory}: {error}. "
              f"No report was written, so no list of the rules not seen since their IDs were added was made.\n"
              f"Make {arguments.report_directory} a directory that user {getpass.getuser()}, who ran this program, "
              f"can write to on {machine}: if nothing is at that path, create it with "
              f"`mkdir -p {arguments.report_directory}`; if a file that is not a directory is there, find out "
              f"what wrote it before you move it; if the directory exists, give that user write permission to it.\n"
              f"Then run, on {machine}:\n    {rerun_command}", file=sys.stderr)
        return 1
    print(path)
    for problem in problems:
        print(f"{JOB_NAME}: not read: {problem}", file=sys.stderr)
    if problems:
        print(f"{JOB_NAME}: the report at {path} was still written, but a rule it lists as not seen may have "
              f"fired in what was not read.\n"
              f"For each `not read:` line above that names a transcript or a directory: run `ls -ld <that path>` "
              f"on {machine}, to see whether it exists and user {getpass.getuser()}, who "
              f"ran this program, can read it, and fix what stops the read. A machine's directory that "
              f"scripts/transcript-mirror-to-log-store.py has not made yet needs no fix.\n"
              f"For each `not read: git lookup:` line above: run the git command it quotes, as it is written there, "
              f"to see why it failed, and fix that.\n"
              f"Then run, on {machine}:\n    {rerun_command}", file=sys.stderr)
    unknown_origins = [rule for rule in rules if rule["origin_note"] == REPORT_NOTE_AUTHOR_UNKNOWN_FOR_HOOK_RULE_WHOSE_ID_IS_IN_NO_GIT_COMMIT]
    for rule in unknown_origins:
        print(f"{JOB_NAME}: FAILED: {rule['hook']} writes `[rule {rule['id']}]`, which no commit's diff in "
              f"`git log -p` in the history of this checkout, {REPOSITORY}, adds and "
              f"nn-systems/general-tools/{RULES_WRITTEN_BEFORE_THEIR_IDS_PATH.name} does not list, so the report "
              f"cannot say who wrote the rule; the report was still written, with that rule's agent-seat unknown, "
              f"to {path}. The lines after the last FAILED line say what to do.", file=sys.stderr)
    if unknown_origins:
        print(unknown_origin_next_steps(REPOSITORY, unknown_origins, machine, rerun_command), file=sys.stderr)
    return 1 if problems or unknown_origins else 0


if __name__ == "__main__":
    sys.exit(main())
