#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py.

Each case builds a scratch git repository holding a registered hook, scratch transcripts and a
scratch report directory, so the real log-store and the real transcripts are never read or written.
NEDSCHORUS_MAINTENANCE_JOB_REPORTS_DIRECTORY is set to a scratch directory before the program is
loaded, so a run that loses its --report-directory still cannot write into the log-store.

Run: python3 nc-systems/general-tools/tests/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import re
import shutil
import socket
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRATCH_REPORT_DIRECTORY = Path(tempfile.mkdtemp(prefix="hook-rule-ids-weekly-reports-"))
os.environ["NEDSCHORUS_MAINTENANCE_JOB_REPORTS_DIRECTORY"] = str(SCRATCH_REPORT_DIRECTORY)
PROGRAM = (Path(__file__).resolve().parents[1]
           / "claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py")
_specification = importlib.util.spec_from_file_location("hook_rule_ids_weekly_count", PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

FAILURES = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        print(f"      {detail!r}")
        FAILURES.append(name)


def git(repository, *arguments, author="seat-a", when="2026-11-01T00:00:00+00:00"):
    environment = dict(os.environ, GIT_AUTHOR_NAME=author, GIT_AUTHOR_EMAIL=f"{author}@example.invalid",
                       GIT_COMMITTER_NAME=author, GIT_COMMITTER_EMAIL=f"{author}@example.invalid",
                       GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(["git", "-C", str(repository), *arguments], check=True, capture_output=True,
                          text=True, env=environment).stdout


def merge_branch(repository, branch, number, author, when):
    git(repository, "checkout", "-q", "main", author=author, when=when)
    git(repository, "merge", "-q", "--no-ff", "-m", f"Merge pull request #{number} from org/{branch}", branch,
        author=author, when=when)


def commit_on_branch(repository, branch, hook_text, author, when):
    git(repository, "checkout", "-q", "-B", branch, author=author, when=when)
    (repository / "hooks" / "guard-hook.py").write_text(hook_text, encoding="utf-8")
    git(repository, "add", "-A", author=author, when=when)
    git(repository, "commit", "-q", "-m", f"change by {author}", author=author, when=when)


def fixture_repository(base):
    """A repository whose registered hook gained a rule in PR 5 by seat-a, and its ID in PR 6 by seat-b,
    with a second ID written outside any constant."""
    repository = base / "repository"
    (repository / ".claude").mkdir(parents=True)
    (repository / "hooks").mkdir()
    git(repository, "init", "-q", "-b", "main")
    (repository / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
                                       "command": 'python3 "$CLAUDE_PROJECT_DIR"/hooks/guard-hook.py'}]}]}}))
    (repository / "hooks" / "guard-hook.py").write_text("X = 1\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "start")
    commit_on_branch(repository, "add-rule", 'DENY_MESSAGE = (\n    "Refused: no."\n)\n', "seat-a",
                     "2026-10-01T00:00:00+00:00")
    merge_branch(repository, "add-rule", 5, "merge-lane-2", "2026-10-01T01:00:00+00:00")
    commit_on_branch(repository, "add-ids",
                     'DENY_MESSAGE = (\n    "[rule fixture-deny] Refused: no."\n)\n\n\n'
                     'def note():\n    return "[rule fixture-inline-note] see"\n',
                     "seat-b", "2026-11-10T00:00:00+00:00")
    merge_branch(repository, "add-ids", 6, "merge-lane-2", "2026-11-10T01:00:00+00:00")
    return repository


def renamed_fixture_repository(base):
    """A repository whose hook gained rule fixture-first, written with its ID, in PR 5 by seat-a in
    hooks/old-hook.py under the constant FIRST; in PR 6 seat-b moved the file to hooks/new-hook.py and
    renamed the constant; in PR 7 seat-c added rule fixture-second, whose message opens with the same
    words as fixture-first's."""
    repository = base / "renamed-repository"
    (repository / ".claude").mkdir(parents=True)
    (repository / "hooks").mkdir()
    git(repository, "init", "-q", "-b", "main")
    (repository / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
                                       "command": 'python3 "$CLAUDE_PROJECT_DIR"/hooks/new-hook.py'}]}]}}))
    padding = "".join(f"PADDING_{number} = {number}\n" for number in range(30))
    first = '"[rule fixture-first] Refused: {name} is the first rule."\n'
    (repository / "hooks" / "old-hook.py").write_text(padding, encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "start")
    when = "2026-10-01T00:00:00+00:00"
    git(repository, "checkout", "-q", "-b", "add-first", author="seat-a", when=when)
    (repository / "hooks" / "old-hook.py").write_text(padding + "FIRST = " + first, encoding="utf-8")
    git(repository, "commit", "-q", "-am", "add the first rule", author="seat-a", when=when)
    merge_branch(repository, "add-first", 5, "merge-lane-2", "2026-10-01T01:00:00+00:00")
    when = "2026-10-10T00:00:00+00:00"
    git(repository, "checkout", "-q", "-b", "move", author="seat-b", when=when)
    git(repository, "mv", "hooks/old-hook.py", "hooks/new-hook.py", author="seat-b", when=when)
    git(repository, "commit", "-q", "-m", "move the hook", author="seat-b", when=when)
    (repository / "hooks" / "new-hook.py").write_text(padding + "FIRST_REFUSAL = " + first, encoding="utf-8")
    git(repository, "commit", "-q", "-am", "rename the constant", author="seat-b", when=when)
    merge_branch(repository, "move", 6, "merge-lane-2", "2026-10-10T01:00:00+00:00")
    when = "2026-11-10T00:00:00+00:00"
    git(repository, "checkout", "-q", "-b", "add-second", author="seat-c", when=when)
    (repository / "hooks" / "new-hook.py").write_text(
        padding + "FIRST_REFUSAL = " + first
        + 'SECOND_REFUSAL = "[rule fixture-second] Refused: {name} is the second rule."\n', encoding="utf-8")
    git(repository, "commit", "-q", "-am", "add the second rule", author="seat-c", when=when)
    merge_branch(repository, "add-second", 7, "merge-lane-2", "2026-11-10T01:00:00+00:00")
    return repository


def squash_and_direct_fixture_repository(base):
    """A repository whose hook gained rule fixture-squashed in a commit on main that GitHub squash-merged
    from PR 8, committed under the merging user's two-word name; then a direct commit by seat-d on main
    added rule fixture-direct; then PR 9 merged an unrelated change."""
    repository = base / "squash-repository"
    (repository / ".claude").mkdir(parents=True)
    (repository / "hooks").mkdir()
    git(repository, "init", "-q", "-b", "main")
    (repository / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
                                       "command": 'python3 "$CLAUDE_PROJECT_DIR"/hooks/guard-hook.py'}]}]}}))
    hook = repository / "hooks" / "guard-hook.py"
    hook.write_text("X = 1\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "start")
    squashed = 'SQUASHED_REFUSAL = "[rule fixture-squashed] Refused: squashed."\n'
    hook.write_text("X = 1\n" + squashed, encoding="utf-8")
    git(repository, "commit", "-q", "-am", "Add the squashed rule (#8)", author="Merging User",
        when="2026-10-01T00:00:00+00:00")
    hook.write_text("X = 1\n" + squashed + 'DIRECT_NOTE = "[rule fixture-direct] see."\n', encoding="utf-8")
    git(repository, "commit", "-q", "-am", "Add the direct rule", author="seat-d", when="2026-10-02T00:00:00+00:00")
    git(repository, "checkout", "-q", "-b", "unrelated", author="seat-e", when="2026-10-03T00:00:00+00:00")
    (repository / "other.txt").write_text("other\n", encoding="utf-8")
    git(repository, "add", "-A", author="seat-e", when="2026-10-03T00:00:00+00:00")
    git(repository, "commit", "-q", "-m", "unrelated", author="seat-e", when="2026-10-03T00:00:00+00:00")
    merge_branch(repository, "unrelated", 9, "merge-lane-2", "2026-10-03T01:00:00+00:00")
    return repository


def merge_resolution_fixture_repository(base):
    """A repository where branch-side, by seat-f, and main both changed the hook's first line, and merge-lane-2's
    resolution of that conflict added rule fixture-merge-added, which no other commit adds."""
    repository = base / "merge-resolution-repository"
    (repository / ".claude").mkdir(parents=True)
    (repository / "hooks").mkdir()
    git(repository, "init", "-q", "-b", "main")
    (repository / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command",
                                       "command": 'python3 "$CLAUDE_PROJECT_DIR"/hooks/guard-hook.py'}]}]}}))
    hook = repository / "hooks" / "guard-hook.py"
    hook.write_text("X = 1\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "start")
    commit_on_branch(repository, "branch-side", "X = 2\n", "seat-f", "2026-10-01T00:00:00+00:00")
    git(repository, "checkout", "-q", "main")
    hook.write_text("X = 3\n", encoding="utf-8")
    git(repository, "commit", "-q", "-am", "main side", author="seat-g", when="2026-10-02T00:00:00+00:00")
    subprocess.run(["git", "-C", str(repository), "merge", "-q", "--no-ff", "--no-commit", "branch-side"],
                   capture_output=True)
    hook.write_text('X = 4\nMERGED = "[rule fixture-merge-added] Refused: merged."\n', encoding="utf-8")
    git(repository, "add", "-A", author="merge-lane-2", when="2026-10-03T00:00:00+00:00")
    git(repository, "commit", "-q", "-m", "Merge pull request #11 from org/branch-side", author="merge-lane-2",
        when="2026-10-03T00:00:00+00:00")
    return repository


def run_program(arguments, now):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(arguments, now=now)
    return status, output.getvalue(), errors.getvalue()


def record(kind, when, **fields):
    return json.dumps({"type": kind, "timestamp": when, **fields})


def write_transcript(path, records, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


AFTER = "2026-11-12T00:00:00Z"
BEFORE = "2026-11-05T00:00:00Z"


# Which records count: only the text a hook handed the agent.
check("hook_additional_context content counts",
      program.counted_texts(json.loads(record("attachment", AFTER, attachment={
          "type": "hook_additional_context", "content": ["[rule a-b] note", 7]}))) == ["[rule a-b] note"])
check("hook_blocking_error's blockingError counts",
      program.counted_texts(json.loads(record("attachment", AFTER, attachment={
          "type": "hook_blocking_error", "blockingError": {"blockingError": "[rule a-b] stop"}}))) == ["[rule a-b] stop"])
check("hook_success, which repeats hook_additional_context, does not count",
      program.counted_texts(json.loads(record("attachment", AFTER, attachment={
          "type": "hook_success", "stdout": "[rule a-b] note", "content": "[rule a-b] note"}))) == [])
check("a PreToolUse refusal's tool result counts, as a string or as text parts",
      program.counted_texts(json.loads(record("user", AFTER, message={"content": [
          {"type": "tool_result", "content": "PreToolUse:Bash hook error: [rule a-b] Refused"},
          {"type": "tool_result", "content": [{"type": "text", "text": "PreToolUse:Edit hook error: [command hook 3]: "
                                                                       "[rule c-d] Refused"}]}]})))
      == ["PreToolUse:Bash hook error: [rule a-b] Refused",
          "PreToolUse:Edit hook error: [command hook 3]: [rule c-d] Refused"])
check("a tool result showing a hook's source does not count",
      program.counted_texts(json.loads(record("user", AFTER, message={"content": [
          {"type": "tool_result", "content": '1\tDENY = "[rule a-b] Refused"'}]}))) == [])
check("the Stop hook feedback message, which repeats hook_blocking_error, does not count",
      program.counted_texts(json.loads(record("user", AFTER, message={
          "content": "Stop hook feedback:\n[rule a-b] stop"}))) == [])

# Which IDs in a hook's text are firings: only one opening the text or a line.
check("an ID opening the text, a line, or a refusal after its hook-error prefix is a firing",
      program.firing_rule_ids_in_hook_text("[rule a-b] note\n  [rule c-d] more") == ["a-b", "c-d"]
      and program.firing_rule_ids_in_hook_text("PreToolUse:Edit hook error: [command hook 3]: [rule e-f] Refused") == ["e-f"])
check("an ID further into a line, as in a quoted diff of a hook's source, is not a firing",
      program.firing_rule_ids_in_hook_text('[rule a-b] a changed hook:\n+    DENY = "[rule c-d] Refused"\nsee [rule e-f]')
      == ["a-b"])

# The recorded origins of the rules written before their IDs, checked against this checkout.
REAL_REPOSITORY = PROGRAM.parents[2]
recorded = program.hook_rule_id_to_origin_commit_pull_request_and_agent_seat_of_rules_whose_message_predates_its_id_json_load()
registered_ids = {rule["id"] for rule in program.registered_rules(REAL_REPOSITORY)}
check("every recorded rule's ID still opens a message of a registered hook",
      set(recorded) <= registered_ids, sorted(set(recorded) - registered_ids))
check("every recorded rule names its commit, its pull request or null, and its agent-seat",
      all(set(row) == {"commit", "pull_request", "agent_seat"} and row["agent_seat"]
          and (row["pull_request"] is None or row["pull_request"].isdigit()) for row in recorded.values()),
      recorded)
missing_commits = [rule_id for rule_id, row in recorded.items()
                   if subprocess.run(["git", "-C", str(REAL_REPOSITORY), "merge-base", "--is-ancestor", row["commit"], "HEAD"],
                                     capture_output=True).returncode != 0]
check("every recorded commit is in this checkout's history", missing_commits == [], missing_commits)
real_first_parent = subprocess.run(["git", "-C", str(REAL_REPOSITORY), "log", "--first-parent", "--format=%H %s", "HEAD"],
                                   capture_output=True, text=True, check=True).stdout
real_first_parent_subjects = dict(line.split(" ", 1) for line in real_first_parent.splitlines() if " " in line)
wrong_squash_rows = {}
for rule_id, row in recorded.items():
    if row["commit"] in real_first_parent_subjects:
        subject_number = re.search(r"\(#(\d+)\)\s*$", real_first_parent_subjects[row["commit"]])
        if row["pull_request"] != (subject_number.group(1) if subject_number else None):
            wrong_squash_rows[rule_id] = (row, real_first_parent_subjects[row["commit"]])
check("a recorded commit on main's first-parent history names the pull request its subject's (#<number>) "
      "names, or null when the subject names none", wrong_squash_rows == {}, wrong_squash_rows)
# docs/nedschorus-wiki/nedschorus-agent-seat-model.md: an agent-seat name is one word; a person's git name is not.
not_one_word_seats = {rule_id: row["agent_seat"] for rule_id, row in recorded.items() if not row["agent_seat"]
                      or any(character.isspace() for character in row["agent_seat"])}
check("every recorded agent-seat is one word, as an agent-seat name is", not_one_word_seats == {}, not_one_word_seats)
check("rules whose message words or constant changed since are recorded with the commit that wrote them",
      [(recorded[rule_id]["commit"][:9], recorded[rule_id]["agent_seat"], recorded[rule_id]["pull_request"])
       for rule_id in ("bash-guard-git-push-and-pr-merge-during-emergency-stop",
                       "checkout-freshness-changed-instructions-read-again",
                       "github-link-text-not-matching-item-title-warning",
                       "checkout-freshness-branch-behind-main-update")]
      == [("a2062a926", "prime-intellect", "3605"), ("f45aaaae2", "cold-read-research", "1327"),
          ("26486c5ad", "reboot-test", "1265"), ("b1ae51007", "new-vp", "87")], recorded)

SQUASH_NOTE = "squash-merged, so its agent-seat is in the pull request's description"
with tempfile.TemporaryDirectory() as scratch:
    squash_repository = squash_and_direct_fixture_repository(Path(scratch))
    squash_rules = program.registered_rules(squash_repository)
    squash_failures = program.rule_origins(squash_repository, squash_rules, {})
    squash_by_id = {rule["id"]: rule for rule in squash_rules}
    squashed, direct = squash_by_id.get("fixture-squashed", {}), squash_by_id.get("fixture-direct", {})
    check("a rule added by a squash merge on main is credited to the pull request its subject names, not to "
          "the next merge, and its agent-seat is not taken from the merging user's name",
          squash_failures == [] and (squashed.get("pull_request"), squashed.get("seat")) == ("8", None)
          and squashed.get("origin_note") == SQUASH_NOTE and "unknown: " + SQUASH_NOTE + " | PR 8"
          in program.report_text("2026-11-16", [squashed], {}, {}, [], 0, []), (squash_failures, squash_rules))
    check("a rule added by a commit straight to main has no pull request, and its author as agent-seat",
          (direct.get("pull_request"), direct.get("seat"), direct.get("origin_note"))
          == (None, "seat-d", "committed to main without a pull request"), squash_rules)

with tempfile.TemporaryDirectory() as scratch:
    base = Path(scratch)
    renamed = renamed_fixture_repository(base)
    renamed_rules = program.registered_rules(renamed)
    failures = program.rule_origins(renamed, renamed_rules, {})
    by_id = {rule["id"]: rule for rule in renamed_rules}
    first, second = by_id.get("fixture-first", {}), by_id.get("fixture-second", {})
    check("in a hook renamed in its history, a rule written with its ID is dated and credited by the commit "
          "that added the ID, though its constant was renamed since",
          failures == [] and first.get("added") == datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
          and (first.get("seat"), first.get("pull_request"), first.get("origin_note")) == ("seat-a", "5", ""),
          (failures, renamed_rules))
    check("a later rule whose message opens with an earlier rule's words is credited to its own commit",
          (second.get("seat"), second.get("pull_request")) == ("seat-c", "7"), renamed_rules)

with tempfile.TemporaryDirectory() as scratch:
    base = Path(scratch)
    repository = fixture_repository(base)
    rules = program.registered_rules(repository)
    check("the registered hook's two rule IDs are found",
          [rule["id"] for rule in rules] == ["fixture-deny", "fixture-inline-note"], rules)
    message_commit = git(repository, "log", "--format=%H", "--author=seat-a", "-1", "add-rule").strip()
    failures = program.rule_origins(repository, rules, {
        "fixture-deny": {"commit": message_commit, "pull_request": "5", "agent_seat": "seat-a"}})
    by_id = {rule["id"]: rule for rule in rules}
    deny = by_id["fixture-deny"]
    check("no git lookup fails on the fixture", failures == [], failures)
    check("a recorded rule's agent-seat and pull request come from its recorded origin, not its ID's commit",
          (deny["seat"], deny["pull_request"], deny["origin_note"]) == ("seat-a", "5", ""), deny)
    check("a rule's ID is dated by the commit that added the ID",
          deny["added"] == datetime.datetime(2026, 11, 10, tzinfo=datetime.timezone.utc), deny["added"])
    inline = by_id["fixture-inline-note"]
    check("a rule not recorded is credited to the commit that added its ID",
          (inline["seat"], inline["pull_request"], inline["origin_note"]) == ("seat-b", "6", ""), inline)
    no_pull_request_rules = program.registered_rules(repository)
    program.rule_origins(repository, no_pull_request_rules, {
        "fixture-deny": {"commit": message_commit, "pull_request": None, "agent_seat": "seat-a"}})
    check("a recorded rule committed to main without a pull request says so",
          no_pull_request_rules[0]["origin_note"] == "committed to main without a pull request"
          and "seat-a | committed to main without a pull request"
          in program.report_text("2026-11-16", no_pull_request_rules, {}, {}, [], 0, []), no_pull_request_rules)

    transcripts = base / "transcripts"
    write_transcript(transcripts / "-seat" / "one.jsonl", [
        record("attachment", AFTER, attachment={"type": "hook_blocking_error",
                                               "blockingError": {"blockingError": "[rule fixture-deny] Refused"}}),
        record("user", AFTER, message={"content": "Stop hook feedback:\n[rule fixture-deny] Refused"}),
        record("attachment", BEFORE, attachment={"type": "hook_additional_context",
                                                "content": ["[rule fixture-deny] before the ID was added"]}),
        record("attachment", AFTER, attachment={"type": "hook_additional_context",
                                               "content": ["[rule removed-rule] old"]}),
        record("attachment", AFTER, attachment={"type": "hook_additional_context", "content": [
            '[rule removed-rule] a changed hook:\n+    NOTE = "[rule fixture-inline-note] see"']}),
        "not json [rule fixture-deny]",
    ])
    write_transcript(transcripts / "-seat" / "sub" / "subagents" / "agent-x.jsonl", [
        record("user", AFTER, message={"content": [
            {"type": "tool_result", "content": "PreToolUse:Bash hook error: [rule fixture-deny] Refused"}]})])
    write_transcript(transcripts / "-seat" / "old.jsonl", [
        record("attachment", AFTER, attachment={"type": "hook_additional_context",
                                               "content": ["[rule fixture-inline-note] see"]})],
        mtime=datetime.datetime(2026, 11, 1).timestamp())
    write_transcript(transcripts / "-seat" / "empty.jsonl", [])
    (transcripts / "-seat" / "empty.jsonl").write_text("", encoding="utf-8")
    counts, unknown, read, problems = program.count_firings([transcripts], rules)
    check("firings count once each, in subagents' transcripts too, and not before the ID was added",
          counts == {"fixture-deny": 2}, counts)
    check("an ID no registered hook writes is counted apart, and an ID quoted in a hook's text is not counted",
          unknown == {"removed-rule": 2} and "fixture-inline-note" not in counts, (unknown, counts))
    check("a transcript last changed before the earliest ID was added is not read", read == 3, read)
    check("a clean scan reports no problem", problems == [], problems)

    missing = base / "no-such-directory"
    _, _, _, problems = program.count_firings([missing], rules)
    check("a missing transcript directory is reported, not taken as no firings",
          len(problems) == 1 and str(missing) in problems[0], problems)

    unreadable = transcripts / "-seat" / "unreadable.jsonl"
    write_transcript(unreadable, [record("attachment", AFTER, attachment={})])
    os.chmod(unreadable, 0)
    try:
        readable_anyway = os.access(unreadable, os.R_OK)
        _, _, _, problems = program.count_firings([transcripts], rules)
        check("a transcript that cannot be read is reported",
              readable_anyway or any(str(unreadable) in problem for problem in problems), problems)
    finally:
        os.chmod(unreadable, 0o644)
        unreadable.unlink()

    not_a_repository = base / "plain"
    not_a_repository.mkdir()
    plain_rules = [{"id": "x-y", "hook": "hooks/h.py", "line": 1}]
    failures = program.rule_origins(not_a_repository, plain_rules, {})
    check("a git lookup that fails is returned, and the rule's origin says it could not be read",
          failures and plain_rules[0]["origin_note"] == "its origin could not be read", (failures, plain_rules))
    check("a git lookup that fails quotes the whole git command, so it can be run again by hand",
          failures and failures[0].startswith(f"`git -C {not_a_repository} log --first-parent --merges --reverse "),
          failures)

    text = program.report_text("2026-11-16", rules, counts, unknown, [transcripts], read, [])
    unseen_section = text.split("## Each rule's count")[0]
    check("the report lists the rule never seen, with its agent-seat and pull request, and not the rule seen",
          "| `fixture-inline-note` | `hooks/guard-hook.py` | 2026-11-10 | seat-b | PR 6" in unseen_section
          and "`fixture-deny`" not in unseen_section, text)
    check("the report calls the rules not seen candidates, not verdicts",
          program.CANDIDATES_NOT_VERDICTS_LINE in text, text)
    check("the report lists the ID no registered hook writes", "| `removed-rule` | 2 |" in text, text)

    # The whole program, on the fixture repository.
    program.REPOSITORY = repository
    reports = base / "reports"
    now = datetime.datetime(2026, 11, 16, 5, 30, tzinfo=datetime.timezone.utc)
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(["--transcript-directory", str(transcripts), "--report-directory", str(reports)], now=now)
    report = reports / f"{program.JOB_NAME}-2026-11-16-report.md"
    check("a clean run exits 0, writes the dated report and prints its path",
          status == 0 and report.is_file() and output.getvalue().strip() == str(report), (status, errors.getvalue()))

    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(["--transcript-directory", str(transcripts), "--transcript-directory", str(missing),
                               "--report-directory", str(reports)], now=now)
    check("a run that cannot read a transcript directory still writes the report, says so in it, and exits 1",
          status == 1 and str(missing) in report.read_text(encoding="utf-8")
          and str(missing) in errors.getvalue(), (status, errors.getvalue()))
    rerun = (f"python3 {Path(program.__file__).resolve()} --transcript-directory {transcripts} "
             f"--transcript-directory {missing} --report-directory {reports}")
    check("a run that cannot read a transcript directory gives a next step for each kind of line and the exact "
          "command to run again",
          "For each `not read:` line above that names a transcript or a directory: run `ls -ld <that path>`" in errors.getvalue()
          and "For each `not read: git lookup:` line above: run the git command it quotes" in errors.getvalue()
          and f"Then run, on {socket.gethostname()}:\n    {rerun}" in errors.getvalue(), errors.getvalue())

    hook_file = repository / "hooks" / "guard-hook.py"
    committed_hook = hook_file.read_text(encoding="utf-8")
    hook_file.write_text(committed_hook + 'LATER = "[rule fixture-uncommitted] later"\n', encoding="utf-8")
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(["--transcript-directory", str(transcripts), "--report-directory", str(reports)], now=now)
    hook_file.write_text(committed_hook, encoding="utf-8")
    check("a rule whose ID is in no commit and not recorded fails the run loudly, and the report says so",
          status == 1 and "FAILED: hooks/guard-hook.py writes `[rule fixture-uncommitted]`" in errors.getvalue()
          and program.REPORT_NOTE_AUTHOR_UNKNOWN_FOR_HOOK_RULE_WHOSE_ID_IS_IN_NO_GIT_COMMIT in report.read_text(encoding="utf-8"), (status, errors.getvalue()))
    rerun = f"python3 {Path(program.__file__).resolve()} --transcript-directory {transcripts} --report-directory {reports}"
    arguments = ["--transcript-directory", str(transcripts), "--report-directory", str(reports)]
    case_openings = {"merge": "HEAD's copy of hooks/guard-hook.py holds the ID",
                     "main": "which is on main.", "detached": "whose HEAD is detached",
                     "branch": "not committed on branch topic.", "pushed": "not by amending or rebasing"}

    def only_case(errors, *cases):
        return (all(case_openings[case] in errors for case in cases)
                and not any(opening in errors for case, opening in case_openings.items() if case not in cases)
                and "git rebase" not in errors and "rebase origin" not in errors)

    hook_file.write_text(committed_hook + 'LATER = "[rule fixture-uncommitted] later"\n', encoding="utf-8")
    status, _, errors = run_program(arguments, now)
    check("an uncommitted edit holding the ID, on main, gets only the main case: commit on a topic branch, "
          "or leave another's edit",
          status == 1 and only_case(errors, "main") and "scripts/agent-seat-worktree-create-with-owner-file.py <topic branch name>" in errors
          and f"git -C {repository} restore --staged --worktree --source=HEAD -- hooks/guard-hook.py" in errors
          and "leave it to whoever is making it" in errors, errors)

    def printed_undo(errors):
        found = re.search(r"undo the edit here with `([^`]*)`", errors)
        return found.group(1) if found else None

    def run_printed_undo(errors):
        undo = printed_undo(errors)
        return undo is not None and subprocess.run(["bash", "-c", undo], capture_output=True).returncode == 0

    git(repository, "add", "hooks/guard-hook.py")
    status, _, errors = run_program(arguments, now)
    undone = run_printed_undo(errors)
    check("an edit already staged on main gets an undo that, run as printed, puts the hook back as HEAD has it "
          "in both the index and the working tree",
          status == 1 and only_case(errors, "main") and undone
          and hook_file.read_text(encoding="utf-8") == committed_hook
          and git(repository, "status", "--porcelain").strip() == "", (errors, git(repository, "status", "--porcelain")))

    settings_file = repository / ".claude" / "settings.json"
    committed_settings = settings_file.read_text(encoding="utf-8")
    new_hook = repository / "hooks" / "new-hook.py"
    new_hook.write_text('NEW = "[rule fixture-new-hook] new"\n', encoding="utf-8")
    registered = json.loads(committed_settings)
    registered["hooks"]["PreToolUse"][0]["hooks"].append(
        {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR"/hooks/new-hook.py'})
    settings_file.write_text(json.dumps(registered), encoding="utf-8")
    status, _, errors = run_program(arguments, now)
    undone = run_printed_undo(errors)
    check("a new, untracked hook registered by an uncommitted settings.json edit, on main, is moved with its "
          "registration, and its undo, run as printed, deletes the hook and restores settings.json",
          status == 1 and only_case(errors, "main") and undone
          and f"copy {repository}/hooks/new-hook.py and {repository}/.claude/settings.json to the same path" in errors
          and not new_hook.exists() and settings_file.read_text(encoding="utf-8") == committed_settings
          and git(repository, "status", "--porcelain").strip() == "", (errors, git(repository, "status", "--porcelain")))
    hook_file.write_text(committed_hook + 'LATER = "[rule fixture-uncommitted] later"\n', encoding="utf-8")

    git(repository, "checkout", "-q", "-b", "topic")
    status, _, errors = run_program(arguments, now)
    check("an uncommitted edit holding the ID, on a branch not pushed, gets only the commit-and-run-again step",
          status == 1 and only_case(errors, "branch")
          and f"commit it on topic, then run, on {socket.gethostname()}:\n    {rerun}" in errors, errors)

    git(repository, "update-ref", "refs/remotes/origin/topic", "HEAD")
    status, _, errors = run_program(arguments, now)
    check("an uncommitted edit holding the ID, on a pushed pull-request branch, says to add a new commit and "
          "never to rebase or amend the frozen-head",
          status == 1 and only_case(errors, "branch", "pushed")
          and "pushed as origin/topic" in errors and "frozen-head" in errors, errors)

    git(repository, "checkout", "-q", "--detach")
    status, _, errors = run_program(arguments, now)
    check("an uncommitted edit holding the ID, on a detached HEAD, says to put the edit on a branch first",
          status == 1 and only_case(errors, "detached")
          and f"git -C {repository} switch -c <topic branch name>" in errors, errors)
    git(repository, "checkout", "-q", "main")

    real_git = program.git

    def git_failing_on_branch(repository_path, *git_arguments):
        if git_arguments[:1] == ("branch",):
            raise program.GitLookupFailed("`git branch --show-current` exited 128: injected")
        return real_git(repository_path, *git_arguments)

    program.git = git_failing_on_branch
    try:
        status, _, errors = run_program(arguments, now)
    finally:
        program.git = real_git
    hook_file.write_text(committed_hook, encoding="utf-8")
    check("a git failure while choosing the case is printed with its command and the rerun, and no case is guessed",
          status == 1 and "which case holds could not be read, because `git branch --show-current` exited 128" in errors
          and f"Then run, on {socket.gethostname()}:\n    {rerun}".lower() in errors.lower()
          and not any(opening in errors for opening in case_openings.values()), errors)

    merged = merge_resolution_fixture_repository(base)
    program.REPOSITORY = merged
    check("an ID that only a merge's conflict resolution added is found in no commit by the ID search",
          "fixture-merge-added" not in program.commits_adding_each_rule_id(merged))
    merged_hook = merged / "hooks" / "guard-hook.py"
    merged_hook.write_text(merged_hook.read_text(encoding="utf-8") + "# an unrelated edit\n", encoding="utf-8")
    status, _, errors = run_program(arguments, now)
    check("an ID added by a merge's own change, with an uncommitted edit to the hook that does not hold the ID, "
          "gets only the step to add the rule to the .json origin table",
          status == 1 and only_case(errors, "merge")
          and f"to nc-systems/general-tools/{program.RULES_WRITTEN_BEFORE_THEIR_IDS_PATH.name}, keyed "
              f"\"fixture-merge-added\"" in errors
          and f"git -C {merged} log --follow --reverse --format='%H %an %s' -S \"<a phrase from the rule's message>\" "
              f"-- hooks/guard-hook.py" in errors, errors)
    own_subject = f"`git -C {merged} log -1 --format=%s <that commit>`"
    descendants = f"`git -C {merged} log --first-parent --merges --reverse --ancestry-path --format=%s <that commit>..HEAD`"
    check("the merge case reads the commit's own subject before its descendants', so a rule first written in a "
          "merge commit gets that merge's pull request, not a later one",
          own_subject in errors and descendants in errors and errors.index(own_subject) < errors.index(descendants),
          errors)
    origin_table = base / "origin-table.json"
    origin_table.write_text(json.dumps({"fixture-merge-added": {
        "commit": git(merged, "rev-parse", "HEAD").strip(), "pull_request": "11", "agent_seat": "seat-h"}}),
        encoding="utf-8")
    real_origin_table = program.RULES_WRITTEN_BEFORE_THEIR_IDS_PATH
    program.RULES_WRITTEN_BEFORE_THEIR_IDS_PATH = origin_table
    try:
        status, _, errors = run_program(arguments, now)
    finally:
        program.RULES_WRITTEN_BEFORE_THEIR_IDS_PATH = real_origin_table
    check("once the merge-added rule is in the .json origin table, the run exits 0 and the report names its "
          "agent-seat and pull request",
          status == 0 and "| `fixture-merge-added` | `hooks/guard-hook.py` | no commit adds it | seat-h | PR 11 |"
          in report.read_text(encoding="utf-8"), (status, errors))
    program.REPOSITORY = repository

    check("the default report directory is the one NEDSCHORUS_MAINTENANCE_JOB_REPORTS_DIRECTORY names",
          program.DEFAULT_REPORT_DIRECTORY == SCRATCH_REPORT_DIRECTORY, program.DEFAULT_REPORT_DIRECTORY)
    if program.DEFAULT_REPORT_DIRECTORY == SCRATCH_REPORT_DIRECTORY:
        status, output, _ = run_program(["--transcript-directory", str(transcripts)], now)
        check("a run without --report-directory writes into the directory the environment variable names",
              status == 0 and output.strip() == str(SCRATCH_REPORT_DIRECTORY / report.name), (status, output))

    blocked = base / "blocked"
    blocked.write_text("a file where the report directory should be", encoding="utf-8")
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(["--transcript-directory", str(transcripts), "--report-directory", str(blocked)],
                              now=now)
    check("a report that cannot be written is printed as FAILED and exits 1",
          status == 1 and "FAILED: the report could not be written" in errors.getvalue(), errors.getvalue())
    rerun = f"python3 {Path(program.__file__).resolve()} --transcript-directory {transcripts} --report-directory {blocked}"
    check("a report that cannot be written gives the next step and the exact command to run again",
          f"Make {blocked} a directory that user" in errors.getvalue()
          and "if a file that is not a directory is there, find out what wrote it" in errors.getvalue()
          and f"Then run, on {socket.gethostname()}:\n    {rerun}" in errors.getvalue(), errors.getvalue())

shutil.rmtree(SCRATCH_REPORT_DIRECTORY, ignore_errors=True)
print()
if FAILURES:
    print(f"{len(FAILURES)} case(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("all cases passed")
