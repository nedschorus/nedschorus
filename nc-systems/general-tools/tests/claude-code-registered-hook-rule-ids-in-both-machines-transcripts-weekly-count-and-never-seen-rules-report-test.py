#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report.py.

Each case builds a scratch git repository holding a registered hook, scratch transcripts and a
scratch report directory, so the real log-store and the real transcripts are never read or written.

Run: python3 nc-systems/general-tools/tests/claude-code-registered-hook-rule-ids-in-both-machines-transcripts-weekly-count-and-never-seen-rules-report-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

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
                   if subprocess.run(["git", "-C", str(REAL_REPOSITORY), "cat-file", "-e", row["commit"] + "^{commit}"],
                                     capture_output=True).returncode != 0]
check("every recorded commit is in this checkout's history", missing_commits == [], missing_commits)
check("rules whose message words or constant changed since are recorded with the commit that wrote them",
      [(recorded[rule_id]["commit"][:9], recorded[rule_id]["agent_seat"], recorded[rule_id]["pull_request"])
       for rule_id in ("bash-guard-git-push-and-pr-merge-during-emergency-stop",
                       "checkout-freshness-changed-instructions-read-again",
                       "github-link-text-not-matching-item-title-warning",
                       "checkout-freshness-branch-behind-main-update")]
      == [("a2062a926", "prime-intellect", "3605"), ("f45aaaae2", "cold-read-research", "1327"),
          ("26486c5ad", "reboot-test", "1265"), ("b1ae51007", "new-vp", "87")], recorded)

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

    blocked = base / "blocked"
    blocked.write_text("a file where the report directory should be", encoding="utf-8")
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.main(["--transcript-directory", str(transcripts), "--report-directory", str(blocked)],
                              now=now)
    check("a report that cannot be written is printed as FAILED and exits 1",
          status == 1 and "FAILED: the report could not be written" in errors.getvalue(), errors.getvalue())

print()
if FAILURES:
    print(f"{len(FAILURES)} case(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("all cases passed")
