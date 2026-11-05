#!/usr/bin/env python3
"""Tests for scripts/new-name-three-lengths-fresh-readers-check.py, with stub readers; no model is called."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check", HERE / "new-name-three-lengths-fresh-readers-check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

FAILURES = []


def expect(condition, label):
    if not condition:
        FAILURES.append(label)
        print(f"FAIL: {label}")


def read_arguments(folder, **overrides):
    values = {"describe": "a script that ships cold-read records to the log-store",
              "full": "cold-read-record-to-log-store-ship", "medium": "cold-read-record-ship",
              "short": "record-ship", "retry_of": None, "run_file": str(folder / "run.json")}
    values.update(overrides)
    return argparse.Namespace(**values)


def stub_reader(failing_models=()):
    def reader(runtime, model, effort, name):
        if model in failing_models:
            return {"account": None, "error": "exit 1: boom", "seconds": 0.1}
        return {"account": f"DOES: ships {name}", "error": None, "seconds": 1.0}
    return reader


def quiet(function, *arguments, **keywords):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = function(*arguments, **keywords)
    return code, out.getvalue(), err.getvalue()


def all_verdicts(run, miss=()):
    return {r["reader_id"]: ("miss" if r["reader_id"] in miss else "match") for r in run["readers"] if not r["error"]}


def verdict_arguments(run_file, verdicts, choose=None, reason=None):
    return argparse.Namespace(run_file=str(run_file), verdicts=json.dumps(verdicts), choose=choose, reason=reason)


def test_name_words_and_length_rule():
    expect(check.name_words("scripts/cold-read-record-ship.py") == ["cold", "read", "record", "ship"], "words of a path")
    expect(check.name_words("runAllSuites") == ["run", "All", "Suites"], "camel case split")
    expect(check.candidate_length_problem({"full": "a-b-c", "medium": "a-b", "short": "a"}) is None, "shorter passes")
    expect("fewer words" in check.candidate_length_problem({"full": "a-b", "medium": "a-b-c", "short": "a"}), "longer medium refused")
    expect("differ" in check.candidate_length_problem({"full": "a", "medium": "a", "short": "a"}), "same names refused")


def test_read_refuses_candidates_not_shorter():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        called = []
        code, _, err = quiet(check.command_read, read_arguments(folder, medium="a-b-c-d-e-f-g"),
                             reader=lambda *a: called.append(a), log_path=str(folder / "log.jsonl"))
        expect(code == 2 and "REFUSED" in err and not called, "read refuses candidates that do not get shorter")


def test_read_runs_eighteen_fresh_readers_and_logs_each():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        log = folder / "store" / "log.jsonl"
        code, out, _ = quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(log), ssh_host=None)
        run = json.loads((folder / "run.json").read_text())
        expect(code == 0, "read exits 0")
        expect(len(run["readers"]) == 18, "eighteen readers")
        expect(len({(r["length"], r["model"]) for r in run["readers"]}) == 18, "each model reads each length once")
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        expect(len(lines) == 18 and all(line["kind"] == "reader" for line in lines), "one log line per reader")
        expect("verdicts" in out and "c3r6" in out, "prints the verdicts command with reader ids")


def test_read_reports_failed_log_store_append():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        blocker = folder / "not-a-folder"
        blocker.write_text("")
        code, out, _ = quiet(check.command_read, read_arguments(folder), reader=stub_reader(),
                             log_path=str(blocker / "log.jsonl"))
        expect(code == 1 and "FAILED" in out, "read exits 1 and says FAILED when the log-store append fails")
        expect((folder / "run.json").exists(), "the run file is still written when the append fails")


def test_verdicts_adds_reader_lines_a_failed_read_append_left_out():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        blocker = folder / "not-a-folder"
        blocker.write_text("")
        quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(blocker / "log.jsonl"))
        run = json.loads((folder / "run.json").read_text())
        expect(run["readers_logged"] is False, "the run file records the failed append")
        log = folder / "log.jsonl"
        code, _, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                           log_path=str(log))
        kinds = [json.loads(line)["kind"] for line in log.read_text().splitlines()]
        expect(code == 0 and kinds.count("reader") == 18 and kinds.count("verdict") == 18,
               "verdicts appends the readers' lines a failed read left out")
        run = json.loads((folder / "run.json").read_text())
        expect(run["readers_logged"] is True, "the run file then records the readers as logged")


def test_verdicts_reports_failed_append():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(folder / "log.jsonl"))
        run = json.loads((folder / "run.json").read_text())
        blocker = folder / "not-a-folder"
        blocker.write_text("")
        code, out, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                             log_path=str(blocker / "log.jsonl"))
        expect(code == 1 and "FAILED" in out and "Chosen" in out, "verdicts prints the outcome, then FAILED, and exits 1")


def test_append_over_ssh_reports_ssh_failure():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        stub = folder / "ssh"
        stub.write_text("#!/bin/sh\necho 'connect refused' >&2\nexit 255\n")
        stub.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{folder}:{old_path}"
        try:
            error = check.append_to_log_store([{"kind": "x"}], "/x/log.jsonl", ssh_host="host")
        finally:
            os.environ["PATH"] = old_path
        expect(error is not None and "ssh exit 255" in error, "an ssh append failure is returned as an error")


def run_and_judge(folder, verdict_maker, reader=None, **verdict_options):
    log = folder / "log.jsonl"
    quiet(check.command_read, read_arguments(folder), reader=reader or stub_reader(), log_path=str(log))
    run = json.loads((folder / "run.json").read_text())
    code, out, err = quiet(check.command_verdicts,
                           verdict_arguments(folder / "run.json", verdict_maker(run), **verdict_options),
                           log_path=str(log))
    return code, out, err, json.loads((folder / "run.json").read_text()), log


def test_shortest_passing_candidate_wins():
    with tempfile.TemporaryDirectory() as folder:
        code, out, _, run, _ = run_and_judge(pathlib.Path(folder), all_verdicts)
        expect(code == 0 and run["outcome"]["chosen"] == "short", "all pass: the short one is chosen")


def test_one_miss_fails_its_candidate():
    with tempfile.TemporaryDirectory() as folder:
        code, out, _, run, log = run_and_judge(pathlib.Path(folder), lambda run: all_verdicts(run, miss={"c3r2"}))
        expect(run["outcome"]["passing"] == ["full", "medium"] and run["outcome"]["chosen"] == "medium",
               "a miss on the short one makes the medium one win")
        only = [json.loads(l) for l in log.read_text().splitlines() if json.loads(l).get("reader_id") == "c3r2"
                and json.loads(l)["kind"] == "verdict"]
        expect(only and only[0]["only_miss"], "the lone miss is recorded as the only miss")


def test_failed_readers():
    with tempfile.TemporaryDirectory() as folder:
        code, _, _, run, _ = run_and_judge(pathlib.Path(folder), all_verdicts, reader=stub_reader({"gpt-6.1-sol"}))
        expect(run["outcome"]["chosen"] == "short", "one failed reader per candidate still lets it pass")
    with tempfile.TemporaryDirectory() as folder:
        code, out, _, run, _ = run_and_judge(pathlib.Path(folder), all_verdicts,
                                             reader=stub_reader({"gpt-6.1-sol", "gpt-6.1-terra"}))
        expect(code == 1 and run["outcome"]["passing"] == [] and "Build three new candidates" in out,
               "two failed readers fail every candidate, and a first run says to build new ones")


def test_verdicts_refuses_missing_or_extra():
    with tempfile.TemporaryDirectory() as folder:
        code, _, err, _, _ = run_and_judge(pathlib.Path(folder),
                                           lambda run: {k: v for k, v in all_verdicts(run).items() if k != "c1r1"})
        expect(code == 2 and "missing ['c1r1']" in err, "a missing verdict is refused")


def test_choose_needs_a_passing_candidate_and_reason():
    with tempfile.TemporaryDirectory() as folder:
        code, _, err, _, _ = run_and_judge(pathlib.Path(folder), all_verdicts, choose="nope", reason="x")
        expect(code == 2 and "REFUSED" in err, "--choose of a non-candidate is refused")
    with tempfile.TemporaryDirectory() as folder:
        code, _, _, run, _ = run_and_judge(pathlib.Path(folder), all_verdicts, choose="cold-read-record-ship", reason="reads better")
        expect(code == 0 and run["outcome"]["chosen"] == "medium", "--choose with a reason picks a passing one")


def test_retry_once_only():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        first = folder / "first.json"
        first.write_text(json.dumps({"retry_number": 1}))
        code, _, err = quiet(check.command_read, read_arguments(folder, retry_of=str(first)), reader=stub_reader(),
                             log_path=str(folder / "log.jsonl"))
        expect(code == 2 and "already a retry" in err, "a retry of a retry is refused")
        first.write_text(json.dumps({"retry_number": 0}))
        code, _, _ = quiet(check.command_read, read_arguments(folder, retry_of=str(first)), reader=stub_reader(),
                           log_path=str(folder / "log.jsonl"))
        run = json.loads((folder / "run.json").read_text())
        expect(code == 0 and run["retry_number"] == 1, "a first retry runs and is marked")
        code, out, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run, miss={
            "c1r1", "c2r1", "c3r1"})), log_path=str(folder / "log.jsonl"))
        expect(code == 1 and "Bring the user" in out, "a retry that passes none says to bring the user the accounts")


def test_per_model_summary():
    with tempfile.TemporaryDirectory() as folder:
        _, _, _, _, log = run_and_judge(pathlib.Path(folder), lambda run: all_verdicts(run, miss={"c3r2"}))
        summary = check.per_model_summary([json.loads(l) for l in log.read_text().splitlines()])
        expect(summary["claude-opus-5-5"]["answered"] == 3 and summary["claude-opus-5-5"]["matched"] == 2
               and summary["claude-opus-5-5"]["only_miss"] == 1, "summary counts the opus miss")
        expect(summary["gpt-6.1-sol"]["matched"] == 3, "summary counts sol's matches")


def test_reader_command_gives_each_runtime_nothing_but_the_name():
    folder = pathlib.Path("/tmp/x")
    argv, stdin_text, _ = check.reader_command("claude", "claude-sonnet-5-5", "medium", "P", folder)
    expect("--tools" in argv and argv[argv.index("--tools") + 1] == "" and argv[argv.index("--setting-sources") + 1] == ""
           and stdin_text == "P", "claude reader has no tools and no settings, prompt on stdin")
    argv, _, answer = check.reader_command("codex", "gpt-6.1-terra", "medium", "P", folder)
    expect(argv[argv.index("-s") + 1] == "read-only" and "--ephemeral" in argv and argv[-1] == "P"
           and answer == folder / "answer.txt", "codex reader is read-only, ephemeral, in the empty folder")


def test_run_reader_reports_nonzero_exit_and_timeout():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        stub = folder / "claude"
        stub.write_text("#!/bin/sh\necho 'rate limited' >&2\nexit 3\n")
        stub.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{folder}:{old_path}"
        try:
            result = check.run_reader("claude", "m", "low", "name")
            stub.write_text("#!/bin/sh\nexit 0\n")
            empty = check.run_reader("claude", "m", "low", "name")
            stub.write_text("#!/bin/sh\nsleep 5\n")
            old_timeout = check.READER_TIMEOUT_SECONDS
            check.READER_TIMEOUT_SECONDS = 1
            try:
                slow = check.run_reader("claude", "m", "low", "name")
            finally:
                check.READER_TIMEOUT_SECONDS = old_timeout
        finally:
            os.environ["PATH"] = old_path
        expect(result["error"] == "exit 3: rate limited" and result["account"] is None, "a nonzero exit is a failed reader")
        expect(empty["error"] == "printed nothing", "an empty answer is a failed reader")
        expect(slow["error"].startswith("timed out"), "a reader past the timeout is a failed reader")


for test in [value for key, value in list(globals().items()) if key.startswith("test_")]:
    test()
print(f"{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
