#!/usr/bin/env python3
"""Count each registered hook's rule IDs in both machines' transcripts, and write one report listing
the rules not seen since their IDs were added.

    python3 <this file> [--transcript-directory <directory> ...] [--report-directory <directory>]

The rules are those whose `[rule <id>]` the hooks .claude/settings.json registers write in their
source, in this program's own checkout, as
nc-systems/general-tools/claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py
finds them. Each is counted in the transcripts under each --transcript-directory, by default the two
copies scripts/transcript-mirror-to-log-store.py keeps in the log-store on ned-box:
agent-session-files-by-machine/mac/projects, the Mac's, and agent-session-files-by-machine/ned-box/projects,
ned-box's. Subagents' transcripts below them are read too.

What counts as a firing: an ID in text a hook handed the agent, and nowhere else, so a transcript in
which an agent reads, tests or quotes a hook's source counts nothing. That text is the content of an
attachment record of type hook_additional_context, the blockingError of one of type
hook_blocking_error, and a tool result whose text starts `<event>... hook error:`, which is how a
PreToolUse refusal reaches the agent. The hook_success record and the `Stop hook feedback:` message
repeat that text and are not counted again. A firing counts when its record's timestamp is no earlier
than the commit that added its rule's ID, and only transcripts changed since the earliest such commit
are read.

When a rule was added, and by whom: the module-level constant whose assignment holds the ID is found,
and the first commit whose change matches that constant's assignment is the commit that added the
rule; the agent-seat is that commit's author name, as each agent-seat commits under its own name, and
the pull request is the one whose merge first brought the commit onto this checkout's first-parent
history, read from the merge's subject `Merge pull request #<number> from ...`. When no constant holds
the ID, or no commit matches it, the commit that added the ID stands in, and the report says so. A
constant renamed since the rule was added gives the commit that renamed it.

The report goes to <report directory>/<job name>-<YYYY-MM-DD>-report.md, the job name being this
file's name without .py and the date UTC, replacing a report written earlier the same day; the default
report directory is the log-store's maintenance-job-reports. The report lists the rules not seen, each
with its hook, the date its ID was added, the agent-seat that wrote it and its pull request, as
candidates to question, not verdicts: a guard against a rare, permanent harm may rightly never fire.
It then gives every rule's count, and the IDs found in transcripts that no registered hook writes. It
keeps no state: each run counts again from each ID's commit. The program prints the report's path.

It runs once a week on ned-box, from the table nc-systems/general-tools/scheduled-jobs-on-each-machine.json,
which nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py installs as this cron line:
    30 5 * * 1 /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py >> /home/nedlern/.claude/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.log 2>&1

Not counted: a firing in a transcript the mirror has not copied yet, about a minute behind; a rule
written only in prose, such as in CLAUDE.md; a rule whose message carries no ID, such as text built
outside a message constant.

Exit status: 0 when the report was written and every transcript directory, transcript and git lookup
was read. 1 when a transcript directory, a transcript or a git lookup could not be read: the report is
still written, and says which, since its never-seen list may then be wrong; or when the report could
not be written, which is printed only, to the cron log above. 2 for a bad command line.
"""
import argparse
import datetime
import importlib.util
import json
import mmap
import os
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
JOB_NAME = Path(__file__).stem
LOG_STORE = Path("/home/nedlern/nedschorus-logs")
DEFAULT_TRANSCRIPT_DIRECTORIES = (LOG_STORE / "agent-session-files-by-machine" / "mac" / "projects",
                                  LOG_STORE / "agent-session-files-by-machine" / "ned-box" / "projects")
DEFAULT_REPORT_DIRECTORY = LOG_STORE / "maintenance-job-reports"
GIT_TIMEOUT_SECONDS = 60
RULE_ID_BYTES = b"[rule "
HOOK_ERROR_TOOL_RESULT_PATTERN = re.compile(r"^[A-Za-z]+(?::\S*)? hook error: ")
MERGE_SUBJECT_PATTERN = re.compile(r"^Merge pull request #(\d+) ")
CANDIDATES_NOT_VERDICTS_LINE = (
    "Each rule below is a candidate to question, not a verdict: a guard against a rare, permanent harm "
    "may rightly never fire.")


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


rule_ids = _load("claude_code_registered_hook_rule_id_pattern_hook_files_list_and_source_scan_common",
                 REPOSITORY / "nc-systems" / "general-tools"
                 / "claude-code-registered-hook-rule-id-pattern-hook-files-list-and-source-scan-common.py")


class GitLookupFailed(Exception):
    pass


def git(repository, *arguments):
    try:
        completed = subprocess.run(["git", "-C", str(repository), *arguments], capture_output=True, text=True,
                                   timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitLookupFailed(f"git {' '.join(arguments[:2])} failed: {error}") from error
    if completed.returncode != 0:
        raise GitLookupFailed(f"git {' '.join(arguments[:2])} exited {completed.returncode}: "
                              f"{completed.stderr.strip()[:300]}")
    return completed.stdout


def registered_rules(repository):
    """[{id, hook, line, constant}] for each rule ID the registered hooks write, first place only."""
    rules = []
    for hook in rule_ids.registered_hook_paths(repository / ".claude" / "settings.json"):
        try:
            source = (repository / hook).read_text(encoding="utf-8")
        except OSError:
            continue
        for rule_id, lines in sorted(rule_ids.rule_ids_in_source(source).items()):
            rules.append({"id": rule_id, "hook": hook, "line": lines[0],
                          "constant": rule_ids.module_level_name_assigned_at_line(source, lines[0])})
    return rules


def first_commit(repository, hook, *pickaxe):
    """(sha, committer time) of the oldest commit whose change to the hook matches the pickaxe, or None."""
    output = git(repository, "log", "--follow", "--reverse", "--format=%H %cI", *pickaxe, "--", hook)
    first = output.splitlines()[0] if output.strip() else None
    if first is None:
        return None
    sha, when = first.split(" ", 1)
    return sha, datetime.datetime.fromisoformat(when)


def first_parent_merges_oldest_first(repository):
    output = git(repository, "log", "--first-parent", "--merges", "--reverse", "--format=%H %s", "HEAD")
    return [line.split(" ", 1) for line in output.splitlines() if line]


def pull_request_bringing(repository, sha, merges):
    """The number of the first first-parent merge holding the commit, or None when none holds it."""
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


def rule_origins(repository, rules):
    """Fill each rule's added (time its ID was committed), seat, pull_request and origin_note; return
    the git lookups that failed."""
    failures = []
    try:
        merges = first_parent_merges_oldest_first(repository)
    except GitLookupFailed as error:
        failures.append(str(error))
        merges = []
    for rule in rules:
        rule.update(added=None, seat=None, pull_request=None, origin_note="")
        try:
            id_commit = first_commit(repository, rule["hook"], "-S", f"[rule {rule['id']}]")
            if id_commit is None:
                rule["origin_note"] = "its ID is not committed"
                continue
            rule["added"] = id_commit[1]
            rule_commit = None
            if rule["constant"]:
                rule_commit = first_commit(repository, rule["hook"], "-G",
                                           rf"^\s*{re.escape(rule['constant'])}\s*[:=]")
            if rule_commit is None:
                rule_commit = id_commit
                rule["origin_note"] = "found from the commit that added its ID"
            rule["seat"] = git(repository, "log", "-1", "--format=%an", rule_commit[0]).strip()
            rule["pull_request"] = pull_request_bringing(repository, rule_commit[0], merges)
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
            for rule_id in rule_ids.RULE_ID_PATTERN.findall(text):
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
        pull_request = f"PR {rule['pull_request']}" if rule["pull_request"] else "no pull request found"
        note = f" ({rule['origin_note']})" if rule["origin_note"] else ""
        return f"{rule['seat'] or 'unknown'} | {pull_request}{note}"

    def added(rule):
        return rule["added"].date().isoformat() if rule["added"] else "not committed"

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
    arguments = parser.parse_args(argv)
    directories = arguments.transcript_directory or list(DEFAULT_TRANSCRIPT_DIRECTORIES)
    today = (now or datetime.datetime.now(datetime.timezone.utc)).date().isoformat()

    rules = registered_rules(REPOSITORY)
    git_failures = rule_origins(REPOSITORY, rules)
    counts, unknown_counts, read, problems = count_firings(directories, rules)
    problems = [f"git lookup: {failure}" for failure in git_failures] + problems
    text = report_text(today, rules, counts, unknown_counts, directories, read, problems)
    try:
        path = write_report(arguments.report_directory, today, text)
    except OSError as error:
        print(f"{JOB_NAME}: FAILED: the report could not be written to {arguments.report_directory}: {error}",
              file=sys.stderr)
        return 1
    print(path)
    for problem in problems:
        print(f"{JOB_NAME}: not read: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
