#!/usr/bin/env python3
"""Tests for scripts/agent-facing-message-follow-trial-by-two-fresh-agents.py.

No model runs: every case points FOLLOWER_LAUNCHER at a fake launcher, written
to a temporary directory, that records its arguments and either writes an
answer to --report or fails the way cold-read-claude-cell.py fails.

Run: python3 scripts/agent-facing-message-follow-trial-by-two-fresh-agents-test.py
Prints one line per case and exits 1 if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile

SCRIPT_PATH = pathlib.Path(__file__).with_name("agent-facing-message-follow-trial-by-two-fresh-agents.py")
_spec = importlib.util.spec_from_file_location("follow_trial", SCRIPT_PATH)
follow_trial = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(follow_trial)

FAKE_LAUNCHER = """import json, os, pathlib, sys
arguments = sys.argv[1:]
value = lambda flag: arguments[arguments.index(flag) + 1]
tier = value("--tier")
with open(os.environ["FAKE_LAUNCHER_LOG"], "a") as log:
    log.write(json.dumps({"arguments": arguments,
                          "target": pathlib.Path(value("--target")).read_text(),
                          "prompt": pathlib.Path(value("--prompt-file")).read_text()}) + "\\n")
if tier in os.environ.get("FAKE_FAILING_TIERS", "").split():
    print("cold-read-claude-cell: cause: logged-out: Not logged in", file=sys.stderr)
    sys.exit(1)
pathlib.Path(value("--report")).write_text(f"answer from the {tier} follower\\n")
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}  {detail}")
        failures.append(case_name)


def run_main(scratch: pathlib.Path, message: str, failing_tiers: str = "", situation_file=None):
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
    follow_trial.FOLLOWER_LAUNCHER = launcher
    sys.argv = [str(SCRIPT_PATH), "--message-file", str(message_file),
                "--situation-file", str(situation_file)]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = follow_trial.main()
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
          str(follow_trial.REPO_ROOT) in call["prompt"] and "{TARGET_PATH}" in call["prompt"]
          and "{REPORT_PATH}" in call["prompt"], call["prompt"])
    check("both followers answer: the cell label is the follower label",
          call["arguments"][call["arguments"].index("--cell") + 1] == follow_trial.FOLLOWER_CELL_LABEL,
          call["arguments"])


def test_one_follower_fails(scratch):
    exit_code, stdout, _, _ = run_main(scratch, "The push was refused on purpose.", failing_tiers="deep")
    check("one follower fails: exit 1", exit_code == 1, f"exit {exit_code}")
    check("one follower fails: the failure names its tier and the launcher's cause",
          "FAILED: the follower on cold-read-tier deep wrote no answer" in stdout
          and "cause: logged-out: Not logged in" in stdout, stdout)
    check("one follower fails: the other answer is still printed",
          "answer from the fast follower" in stdout, stdout)


def test_unreadable_input_file(scratch):
    exit_code, stdout, stderr, calls = run_main(
        scratch, "anything", situation_file=scratch / "no-such-situation.txt")
    check("unreadable input file: exit 2", exit_code == 2, f"exit {exit_code}")
    check("unreadable input file: says what failed and what to do",
          "an input file could not be read" in stderr and "no-such-situation.txt" in stderr
          and "Pass --message-file and --situation-file" in stderr, stderr)
    check("unreadable input file: no follower started", calls == [] and stdout == "", calls)


def test_named_scripts(scratch):
    helped = scratch / "helped.py"
    helped.write_text("import sys\nprint('usage: helped.py [--head HEAD] [--base BASE]')\n")
    shell = scratch / "helped.sh"
    shell.write_text("echo 'usage: helped.sh [--pull-request N]'\n")
    broken = scratch / "broken.py"
    broken.write_text("import sys\nprint('cannot start: missing module'); sys.exit(3)\n")
    hanging = scratch / "hanging.py"
    hanging.write_text("import time\ntime.sleep(30)\n")
    message = (
        f"Rerun `python3 {helped} --head HEAD --base-branch main` then `{shell} --pull-request 5`.\n"
        f"Or run {broken} --dry-run; {hanging} --wait\n"
        f"Never run {scratch}/missing.py --force.\n")
    follow_trial.HELP_TIMEOUT_SECONDS = 2
    try:
        exit_code, stdout, _, _ = run_main(scratch, message)
    finally:
        follow_trial.HELP_TIMEOUT_SECONDS = 60
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
    check("named scripts: a missing script is reported", f"`{scratch}/missing.py`: NOT FOUND" in stdout, stdout)


def test_named_scripts_parsing():
    scripts = follow_trial.named_scripts_with_flags(
        "Run scripts/a.py --x --y scripts/b.sh --z | grep --count\n"
        "Then scripts/a.py --x --w.\n"
        "Read nc-systems/cold-read/cold-read-claude-cell.py first.")
    check("parsing: flags stop at the next path and at a pipe, and repeat mentions merge",
          scripts == {"scripts/a.py": ["--x", "--y", "--w"], "scripts/b.sh": ["--z"],
                      "nc-systems/cold-read/cold-read-claude-cell.py": []}, scripts)
    check("parsing: a relative path is resolved from the checkout's top directory",
          follow_trial.named_script_check_lines("scripts/no-such-script-anywhere.py", [])
          == [f"- `scripts/no-such-script-anywhere.py`: NOT FOUND at "
              f"{follow_trial.REPO_ROOT / 'scripts/no-such-script-anywhere.py'}"])


def test_no_named_scripts(scratch):
    _, stdout, _, _ = run_main(scratch, "Ask the merge-lane to rerun the review.")
    check("no named scripts: said so", "The message names no path ending in .py or .sh." in stdout, stdout)


def main() -> int:
    for test in (test_both_followers_answer, test_one_follower_fails, test_unreadable_input_file,
                 test_named_scripts, test_no_named_scripts):
        with tempfile.TemporaryDirectory() as scratch:
            test(pathlib.Path(scratch))
    test_named_scripts_parsing()
    print(f"{len(failures)} failed" if failures else "all passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
