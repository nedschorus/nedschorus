#!/usr/bin/env python3
"""Tests for scripts/new-name-full-medium-short-candidates-checked-by-name-only-model-readers.py, with stub readers; no model is called."""

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
spec = importlib.util.spec_from_file_location("check", HERE / "new-name-full-medium-short-candidates-checked-by-name-only-model-readers.py")
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
              "short": "record-ship", "sent_name": None, "retry_of": None, "run_file": str(folder / "run.json")}
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


def test_read_refuses_a_sent_name_left_out():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        code, _, err = quiet(check.command_read, read_arguments(folder, sent_name="cold-read-ship"),
                             reader=stub_reader(), log_path=str(folder / "log.jsonl"))
        expect(code == 2 and "not one of the three" in err and "3 words" in err, "a sent name left out is refused")
        code, _, _ = quiet(check.command_read, read_arguments(folder, sent_name="record-ship"),
                           reader=stub_reader(), log_path=str(folder / "log.jsonl"))
        expect(code == 0, "a sent name among the candidates runs")


def test_read_runs_eighteen_name_only_readers_and_logs_each():
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
        expect(code == 1 and "FAILED: the readers' results were not added" in out,
               "read exits 1 and says the results were not added when a local append fails")
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


def test_per_model_summary_reports_an_unreadable_log():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        stub = folder / "ssh"
        stub.write_text("#!/bin/sh\necho 'connect refused' >&2\nexit 255\n")
        stub.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{folder}:{old_path}"
        try:
            code, out, _ = quiet(check.command_per_model_summary, None, log_path="/x/log.jsonl", ssh_host="host")
        finally:
            os.environ["PATH"] = old_path
        expect(code == 1 and out.startswith("FAILED: could not read /x/log.jsonl") and "ssh exit 255" in out,
               "per-model-summary exits 1 with FAILED when the log cannot be read")
        code, out, _ = quiet(check.command_per_model_summary, None, log_path=str(folder / "none.jsonl"))
        expect(code == 0 and out.strip() == "model\tanswered\tmatched\tonly miss\tfailed\tmean s",
               "a log not yet written gives an empty summary")


def test_run_reader_reports_a_runtime_not_on_path():
    old_path = os.environ["PATH"]
    with tempfile.TemporaryDirectory() as folder:
        os.environ["PATH"] = folder
        try:
            result = check.run_reader("claude", "m", "low", "name")
        finally:
            os.environ["PATH"] = old_path
    expect(result["account"] is None and result["error"].startswith("could not start claude"),
           "a runtime missing from PATH is a failed reader")


def with_stub_on_path(name, script, action):
    with tempfile.TemporaryDirectory() as folder:
        stub = pathlib.Path(folder) / name
        stub.write_text(script)
        stub.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{folder}:{old_path}"
        try:
            return action()
        finally:
            os.environ["PATH"] = old_path


def test_last_line_keeps_the_last_line_with_text_cut_short():
    expect(check.last_line("first\nsecond\n\n") == "second", "the last line with text is kept")
    expect(check.last_line("x" * 400) == "x" * check.ERROR_LINE_CHARACTERS, "a long line is cut")
    expect(check.last_line("  \n") == "", "no text gives an empty line")


def test_ssh_append_and_read_succeed_and_fail():
    ok = "#!/bin/sh\ncat > /dev/null\necho '{\"kind\": \"reader\"}'\nexit 0\n"
    expect(with_stub_on_path("ssh", ok, lambda: check.append_to_log_store([{"kind": "x"}], "/x/l.jsonl", ssh_host="h")) == (None, False),
           "an ssh append that exits 0 is no error")
    expect(with_stub_on_path("ssh", ok, lambda: check.read_log_lines("/x/l.jsonl", ssh_host="h")) == [{"kind": "reader"}],
           "an ssh read returns the log's lines")
    bad = "#!/bin/sh\necho 'first' >&2\necho 'no route' >&2\nexit 1\n"
    error, may_have_appended = with_stub_on_path(
        "ssh", bad, lambda: check.append_to_log_store([{"kind": "x"}], "/x/l.jsonl", ssh_host="h"))
    expect(error == "could not append to h:/x/l.jsonl: ssh exit 1: no route" and not may_have_appended,
           "a remote command that exits 1 is an append error that did not append")
    try:
        with_stub_on_path("ssh", bad, lambda: check.read_log_lines("/x/l.jsonl", ssh_host="h"))
        expect(False, "an ssh read that exits 1 raises")
    except OSError as error:
        expect(str(error) == "ssh exit 1: no route", "an ssh read that exits 1 raises with its last stderr line")
    old_path = os.environ["PATH"]
    os.environ["PATH"] = "/nonexistent"
    try:
        error, may_have_appended = check.append_to_log_store([{"kind": "x"}], "/x/l.jsonl", ssh_host="h")
    finally:
        os.environ["PATH"] = old_path
    expect(error is not None and "ssh did not run" in error and not may_have_appended,
           "ssh missing from PATH is an append error that surely did not append")
    slow = "#!/bin/sh\nsleep 5\n"
    old_timeout = check.SSH_TIMEOUT_SECONDS
    check.SSH_TIMEOUT_SECONDS = 1
    try:
        error, may_have_appended = with_stub_on_path(
            "ssh", slow, lambda: check.append_to_log_store([{"kind": "x"}], "/x/l.jsonl", ssh_host="h"))
    finally:
        check.SSH_TIMEOUT_SECONDS = old_timeout
    expect(error is not None and "ssh timed out" in error and may_have_appended,
           "an ssh call past its timeout is an append error that may have appended")


def test_run_reader_keeps_seconds_only_for_an_answer_and_reads_a_signal_exit():
    answered = with_stub_on_path("claude", "#!/bin/sh\necho 'DOES: x'\n", lambda: check.run_reader("claude", "m", "low", "n"))
    expect(answered["account"] == "DOES: x" and 0 <= answered["seconds"] < 30, "an answer keeps its seconds")
    killed = with_stub_on_path("claude", "#!/bin/sh\nkill -TERM $$\n", lambda: check.run_reader("claude", "m", "low", "n"))
    expect(killed["account"] is None and killed["error"].startswith("exit -15") and killed["seconds"] is None,
           "a reader killed by a signal is a failed reader with no seconds")


def test_append_over_ssh_reports_ssh_failure():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        stub = folder / "ssh"
        stub.write_text("#!/bin/sh\necho 'connect refused' >&2\nexit 255\n")
        stub.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{folder}:{old_path}"
        try:
            error, may_have_appended = check.append_to_log_store([{"kind": "x"}], "/x/log.jsonl", ssh_host="host")
        finally:
            os.environ["PATH"] = old_path
        expect(error is not None and "ssh exit 255" in error and may_have_appended,
               "an ssh exit 255, which a dropped connection also gives, is an error that may have appended")


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
        code, out, _, run, _ = run_and_judge(pathlib.Path(folder), all_verdicts, reader=stub_reader({"gpt-6.1-sol"}))
        expect(code == 1 and run["outcome"]["passing"] == [] and "Build three new candidates" in out,
               "one failed reader fails its candidate, since all six must read it rightly; a first run says to build new ones")


EXECUTING_SSH = '#!/bin/sh\nfor argument; do remote_command=$argument; done\nexec sh -c "$remote_command"\n'


def test_ssh_read_fails_when_the_remote_cat_fails_and_reads_a_missing_log_as_empty():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        unreadable = folder / "log.jsonl"
        unreadable.write_text('{"kind": "reader"}\n')
        unreadable.chmod(0o000)
        try:
            code, out, _ = with_stub_on_path("ssh", EXECUTING_SSH, lambda: quiet(
                check.command_per_model_summary, None, log_path=str(unreadable), ssh_host="h"))
        finally:
            unreadable.chmod(0o600)
        expect(code == 1 and out.startswith("FAILED: could not read"),
               "per-model-summary exits 1 with FAILED when the remote cat of an existing log fails")
        lines = with_stub_on_path("ssh", EXECUTING_SSH,
                                  lambda: check.read_log_lines(str(folder / "absent.jsonl"), ssh_host="h"))
        expect(lines == [], "a log not yet written reads as empty over ssh")


def test_read_says_an_append_whose_connection_dropped_may_have_happened():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        dropped = "#!/bin/sh\ncat > /dev/null\necho 'Connection reset' >&2\nexit 255\n"
        code, out, _ = with_stub_on_path("ssh", dropped, lambda: quiet(
            check.command_read, read_arguments(folder), reader=stub_reader(), log_path="/x/log.jsonl", ssh_host="h"))
        expect(code == 1 and "may or may not have worked" in out and "were not added" not in out,
               "read says an append whose connection dropped may have happened")


def test_verdicts_adds_reader_lines_again_after_an_uncertain_append_and_the_summary_counts_each_once():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        log = folder / "log.jsonl"
        quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(log))
        run = json.loads((folder / "run.json").read_text())
        run["readers_logged"] = False
        (folder / "run.json").write_text(json.dumps(run))
        code, _, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                           log_path=str(log))
        code_again, _, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                                 log_path=str(log))
        kinds = [json.loads(line)["kind"] for line in log.read_text().splitlines()]
        expect(code == 0 and code_again == 0 and kinds.count("reader") == 36,
               "verdicts adds the reader lines when they are not known to be logged, even if some are there")
        summary = check.per_model_summary([json.loads(line) for line in log.read_text().splitlines()])
        expect(all(row["answered"] == 3 and row["matched"] == 3 for row in summary.values()),
               "the summary counts each reader and each judgement once")


def test_verdicts_adds_every_reader_line_when_the_log_store_holds_only_some():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        log = folder / "log.jsonl"
        quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(log))
        log.write_text("".join(log.read_text().splitlines(keepends=True)[:5]))
        run = json.loads((folder / "run.json").read_text())
        run["readers_logged"] = False
        (folder / "run.json").write_text(json.dumps(run))
        code, _, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                           log_path=str(log))
        summary = check.per_model_summary([json.loads(line) for line in log.read_text().splitlines()])
        expect(code == 0 and sum(row["answered"] for row in summary.values()) == 18,
               "a log-store holding only some reader lines ends with every reader counted once")


def test_verdicts_failed_line_says_whether_the_judgements_may_have_been_added():
    with tempfile.TemporaryDirectory() as folder:
        folder = pathlib.Path(folder)
        quiet(check.command_read, read_arguments(folder), reader=stub_reader(), log_path=str(folder / "log.jsonl"))
        run = json.loads((folder / "run.json").read_text())
        directory = folder / "a-directory"
        directory.mkdir()
        code, out, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
                             log_path=str(directory))
        expect(code == 1 and "were not added" in out and "may or may not" not in out,
               "a local append that failed says the judgements were not added")
        dropped = "#!/bin/sh\ncat > /dev/null\necho 'Connection reset' >&2\nexit 255\n"
        code, out, _ = with_stub_on_path("ssh", dropped, lambda: quiet(
            check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run)),
            log_path="/x/log.jsonl", ssh_host="h"))
        expect(code == 1 and "may or may not have been added" in out and "were not added" not in out,
               "an append whose connection dropped says the judgements may or may not have been added")


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
        quiet(check.command_read, read_arguments(folder, run_file=str(first)), reader=stub_reader(),
              log_path=str(folder / "log.jsonl"))
        first_run = json.loads(first.read_text())
        quiet(check.command_verdicts, verdict_arguments(first, all_verdicts(first_run, miss={"c1r1", "c2r1", "c3r1", "c3r2"})),
              log_path=str(folder / "log.jsonl"))
        code, _, _ = quiet(check.command_read, read_arguments(folder, retry_of=str(first)), reader=stub_reader(),
                           log_path=str(folder / "log.jsonl"))
        run = json.loads((folder / "run.json").read_text())
        expect(code == 0 and run["retry_number"] == 1, "a first retry runs and is marked")
        code, out, _ = quiet(check.command_verdicts, verdict_arguments(folder / "run.json", all_verdicts(run, miss={
            "c1r1", "c2r1", "c3r1"})), log_path=str(folder / "log.jsonl"))
        expect(code == 1 and "bring the user" in out, "a retry that passes none says to bring the user the accounts")
        expect("5 of 6: cold-read-record-to-log-store-ship" in out,
               "a retry that passes none counts matches per candidate across both runs")


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
           and stdin_text == "P" and argv[:3] == ["claude", "-p", "--strict-mcp-config"]
           and argv[argv.index("--permission-mode") + 1] == "dontAsk",
           "claude reader has no connectors, no tools and no settings, prompt on stdin")
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
