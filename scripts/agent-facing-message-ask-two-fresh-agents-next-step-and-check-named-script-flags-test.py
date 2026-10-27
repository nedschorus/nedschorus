#!/usr/bin/env python3
"""Tests for scripts/agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags.py.

No model runs: every case points CLAUDE_CELL_LAUNCHER at a fake launcher, written
to a temporary directory, that records its arguments and either writes an
answer to --report or fails the way cold-read-claude-cell.py fails.

Run: python3 scripts/agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags-test.py
Prints one line per case and exits 1 if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import subprocess
import tempfile

SCRIPT_PATH = pathlib.Path(__file__).with_name("agent-facing-message-ask-two-fresh-agents-next-step-and-check-named-script-flags.py")
_spec = importlib.util.spec_from_file_location("ask_two_fresh_agents", SCRIPT_PATH)
ask_two_fresh_agents = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ask_two_fresh_agents)

FAKE_LAUNCHER = """import json, os, pathlib, sys
arguments = sys.argv[1:]
value = lambda flag: arguments[arguments.index(flag) + 1]
tier = value("--tier")
with open(os.environ["FAKE_LAUNCHER_LOG"], "a") as log:
    log.write(json.dumps({"arguments": arguments,
                          "target": pathlib.Path(value("--target")).read_text(),
                          "prompt": pathlib.Path(value("--prompt-file")).read_text()}) + "\\n")
if tier in os.environ.get("FAKE_SIGNALLED_TIERS", "").split():
    os.kill(os.getpid(), 9)
if tier in os.environ.get("FAKE_FAILING_TIERS", "").split():
    print("cold-read-claude-cell: cause: logged-out: Not logged in", file=sys.stderr)
    sys.exit(1)
pathlib.Path(value("--report")).write_text(f"answer from the {tier} follower\\n")
if tier in os.environ.get("FAKE_STRAY_WRITE_TIERS", "").split():
    print(f"cold-read-claude-cell: {os.environ['FAKE_STRAY_WRITE_PHRASE']} — notes.md.", file=sys.stderr)
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}  {detail}")
        failures.append(case_name)


def run_main(scratch: pathlib.Path, message: str, failing_tiers: str = "", situation_file=None,
             signalled_tiers: str = "", stray_write_tiers: str = ""):
    """Run main() with a fake launcher; return (exit code, stdout, stderr, launcher calls)."""
    launcher = scratch / "fake-launcher.py"
    launcher.write_text(FAKE_LAUNCHER)
    log = scratch / "launcher-log.jsonl"
    log.unlink(missing_ok=True)
    message_file = scratch / "message.txt"
    message_file.write_text(message)
    if situation_file is None:
        situation_file = scratch / "situation.txt"
        situation_file.write_text("You ran `git push` to publish your topic branch.\n")
    os.environ["FAKE_LAUNCHER_LOG"] = str(log)
    os.environ["FAKE_FAILING_TIERS"] = failing_tiers
    os.environ["FAKE_SIGNALLED_TIERS"] = signalled_tiers
    os.environ["FAKE_STRAY_WRITE_TIERS"] = stray_write_tiers
    os.environ["FAKE_STRAY_WRITE_PHRASE"] = ask_two_fresh_agents.cell_common.STRAY_WRITE_PHRASE
    ask_two_fresh_agents.CLAUDE_CELL_LAUNCHER = launcher
    sys.argv = [str(SCRIPT_PATH), "--message-file", str(message_file),
                "--situation-file", str(situation_file)]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = ask_two_fresh_agents.main()
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return exit_code, stdout.getvalue(), stderr.getvalue(), calls


def test_both_followers_answer(scratch):
    exit_code, stdout, _, calls = run_main(scratch, "The push was refused on purpose.")
    check("both followers answer: exit 0", exit_code == 0, f"exit {exit_code}")
    check("both followers answer: each answer is printed",
          "answer from the fast follower" in stdout and "answer from the deep follower" in stdout, stdout)
    check("both followers answer: one launcher call per tier",
          sorted(value for call in calls for flag, value in zip(call["arguments"], call["arguments"][1:])
                 if flag == "--tier") == ["deep", "fast"], calls)
    call = calls[0]
    check("both followers answer: the target holds the situation and the message",
          "You ran `git push`" in call["target"] and "The push was refused on purpose." in call["target"],
          call["target"])
    check("both followers answer: the prompt names the checkout and keeps the launcher's placeholders",
          str(ask_two_fresh_agents.REPO_ROOT) in call["prompt"] and "{TARGET_PATH}" in call["prompt"]
          and "{REPORT_PATH}" in call["prompt"], call["prompt"])
    check("both followers answer: the cell label is the follower label",
          call["arguments"][call["arguments"].index("--cell") + 1] == ask_two_fresh_agents.FOLLOWER_ANSWER_FILE_LABEL_FOR_CELL_FLAG,
          call["arguments"])


def test_one_follower_fails(scratch):
    exit_code, stdout, _, _ = run_main(scratch, "The push was refused on purpose.", failing_tiers="deep")
    check("one follower fails: exit 1", exit_code == 1, f"exit {exit_code}")
    check("one follower fails: the failure names its tier and the launcher's cause",
          "FAILED: the fresh-agent on cold-read-tier deep wrote no answer" in stdout
          and "cause: logged-out: Not logged in" in stdout, stdout)
    check("one follower fails: says when to rerun and when to tell the user",
          "If that line names logged-out, account-limit or model-limit: tell the user" in stdout
          and f"Otherwise, or when there is no such line: rerun scripts/{SCRIPT_PATH.name} once" in stdout,
          stdout)
    check("one follower fails: the other answer is still printed",
          "answer from the fast follower" in stdout, stdout)


def test_follower_killed_by_signal(scratch):
    exit_code, stdout, _, _ = run_main(scratch, "anything", signalled_tiers="fast")
    check("follower killed by a signal: exit 1 and reported",
          exit_code == 1 and "wrote no answer, because" in stdout and "exited -9" in stdout, stdout)


def test_follower_writes_outside_its_report(scratch):
    exit_code, stdout, _, _ = run_main(scratch, "Create notes.md first.", stray_write_tiers="deep")
    check("follower writes outside its report: exit 3", exit_code == 3, f"exit {exit_code}")
    check("follower writes outside its report: the launcher's line and the warning are printed",
          f"{ask_two_fresh_agents.cell_common.STRAY_WRITE_PHRASE} — notes.md" in stdout
          and "CHECKOUT CHANGED" in stdout and "answer from the deep follower" in stdout, stdout)
    exit_code, _, _, _ = run_main(scratch, "Create notes.md first.", failing_tiers="fast",
                                  stray_write_tiers="deep")
    check("follower writes outside its report while the other fails: exit 1", exit_code == 1,
          f"exit {exit_code}")


def test_missing_flag_refused(scratch):
    for kept in ("--message-file", "--situation-file"):
        sys.argv = [str(SCRIPT_PATH), kept, str(scratch / "x.txt")]
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                ask_two_fresh_agents.main()
            exit_code = None
        except SystemExit as stop:
            exit_code = stop.code
        check(f"missing flag refused when only {kept} is given", exit_code == 2, stderr.getvalue())


def test_help_runs_as_a_program(scratch):
    completed = subprocess.run([sys.executable, str(SCRIPT_PATH), "--help"], capture_output=True,
                               text=True, cwd=scratch, check=False)
    check("--help runs as a program", completed.returncode == 0 and completed.stdout.startswith("usage"),
          completed.stdout + completed.stderr)


def test_unreadable_input_file(scratch):
    exit_code, stdout, stderr, calls = run_main(
        scratch, "anything", situation_file=scratch / "no-such-situation.txt")
    check("unreadable input file: exit 2", exit_code == 2, f"exit {exit_code}")
    check("unreadable input file: says what failed and what to do",
          "the file given to --situation-file could not be read" in stderr
          and "no-such-situation.txt" in stderr
          and f"Rerun scripts/{SCRIPT_PATH.name} with --message-file and --situation-file, "
              "--situation-file naming a readable text file." in stderr, stderr)
    check("unreadable input file: no follower started", calls == [] and stdout == "", calls)


def test_named_scripts(scratch):
    helped = scratch / "helped.py"
    helped.write_text("import sys\nprint('usage: helped.py [--head HEAD] [--base BASE]')\n")
    shell = scratch / "helped.sh"
    shell.write_text("echo 'usage: helped.sh [--pull-request N]'\n")
    broken = scratch / "broken.py"
    broken.write_text("import sys\nprint('cannot start: missing module'); sys.exit(3)\n")
    signalled = scratch / "signalled.py"
    signalled.write_text("import os\nos.kill(os.getpid(), 9)\n")
    hanging = scratch / "hanging.py"
    hanging.write_text("import time\ntime.sleep(30)\n")
    message = (
        f"Rerun `python3 {helped} --head HEAD --base-branch main` then `{shell} --pull-request 5`.\n"
        f"Or run {broken} --dry-run; {hanging} --wait\n"
        f"Never run {scratch}/missing.py --force.\n"
        f"Last, {signalled} --once.\n")
    ask_two_fresh_agents.HELP_TIMEOUT_SECONDS = 2
    try:
        exit_code, stdout, _, _ = run_main(scratch, message)
    finally:
        ask_two_fresh_agents.HELP_TIMEOUT_SECONDS = 60
    check("named scripts: exit 0 although checks found problems", exit_code == 0, f"exit {exit_code}")
    check("named scripts: a flag in --help is reported in it", "`--head`: in the --help output" in stdout, stdout)
    check("named scripts: a flag only a prefix of which is in --help is reported missing",
          "`--base-branch`: NOT IN the --help output" in stdout, stdout)
    check("named scripts: a flag after a backquote belongs to the next script",
          stdout.count("`--pull-request`") == 1 and "`--pull-request`: in the --help output" in stdout, stdout)
    check("named scripts: a .sh script runs under bash", f"`{shell}`: exists; --help exited 0" in stdout, stdout)
    check("named scripts: a --help that fails is reported with its output",
          f"`{broken}`: exists; --help exited 3" in stdout and "cannot start: missing module" in stdout
          and "`--dry-run`" not in stdout, stdout)
    check("named scripts: a --help that hangs is reported",
          f"`{hanging}`: exists; --help did not finish within 2 s" in stdout, stdout)
    check("named scripts: a --help killed by a signal is reported",
          f"`{signalled}`: exists; --help exited -9" in stdout, stdout)
    check("named scripts: a missing script is reported", f"`{scratch}/missing.py`: NOT FOUND" in stdout, stdout)


def test_named_scripts_parsing():
    scripts = ask_two_fresh_agents.scripts_and_flags_named_in_agent_facing_message(
        "Run scripts/a.py --x --y scripts/b.sh --z | grep --count\n"
        "Or c.py --c1 d.py --d1 e.py --e1\n"
        "Then scripts/a.py --x --w.\n"
        "Read nc-systems/cold-read/cold-read-claude-cell.py first.")
    check("parsing: flags stop at the next path and at a pipe, and repeat mentions merge",
          scripts == {"scripts/a.py": ["--x", "--y", "--w"], "scripts/b.sh": ["--z"],
                      "c.py": ["--c1"], "d.py": ["--d1"], "e.py": ["--e1"],
                      "nc-systems/cold-read/cold-read-claude-cell.py": []}, scripts)
    check("parsing: a relative path is resolved from the checkout's top directory",
          ask_two_fresh_agents.named_script_existence_and_flags_in_help_check_report_lines("scripts/no-such-script-anywhere.py", [])
          == [f"- `scripts/no-such-script-anywhere.py`: NOT FOUND at "
              f"{ask_two_fresh_agents.REPO_ROOT / 'scripts/no-such-script-anywhere.py'}"])


def test_no_named_scripts(scratch):
    _, stdout, _, _ = run_main(scratch, "Ask the merge-lane to rerun the review.")
    check("no named scripts: said so", "The message names no path ending in .py or .sh." in stdout, stdout)


def main() -> int:
    for test in (test_both_followers_answer, test_one_follower_fails, test_follower_killed_by_signal,
                 test_follower_writes_outside_its_report, test_missing_flag_refused, test_help_runs_as_a_program, test_unreadable_input_file,
                 test_named_scripts, test_no_named_scripts):
        with tempfile.TemporaryDirectory() as scratch:
            test(pathlib.Path(scratch))
    test_named_scripts_parsing()
    print(f"{len(failures)} failed" if failures else "all passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
