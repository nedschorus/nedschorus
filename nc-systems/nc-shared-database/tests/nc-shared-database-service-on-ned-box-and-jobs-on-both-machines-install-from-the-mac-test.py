#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac.py

The program's runner is replaced by a fake that records each (machine, command,
standard input) and answers as each case asks, so nothing is installed and no
ssh session is opened. Cases: every step runs in order and passes; the Mac's
token reaches only the accepted-tokens step, on standard input; a failing step
stops the run and reports the step, its output and its advice; ssh's exit 255
gets the reach-ned-box advice; a service answer other than the one a check needs
fails; a machine other than the Mac is refused; --print runs nothing. Two cases
run the token and accepted-tokens commands in a real shell under a temporary
HOME: a token is made once and kept, and the accepted-tokens file holds both,
and is left as it was when ned-box's token file cannot be read. One case calls
the real runner with subprocess.run replaced, to check which machine each step
runs on.

Run: python3 nc-systems/nc-shared-database/tests/nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import os
import shlex
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_PATH = (REPOSITORY_ROOT / "nc-systems" / "nc-shared-database"
                / "nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac.py")
_spec = importlib.util.spec_from_file_location(
    "nc_shared_database_service_on_ned_box_and_jobs_on_both_machines_install_from_the_mac", PROGRAM_PATH)
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


class FakeRunner:
    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, machine, command, standard_input):
        self.calls.append((machine, command, standard_input))
        number = len(self.calls)
        if number in self.answers:
            code, out, err = self.answers[number]
            return subprocess.CompletedProcess([], code, out, err)
        # Built at run time, as curl's output is, so an identity comparison would not match.
        out = "".join(["4", "12" if "Bearer" in command else "01"]) if "curl" in command else ""
        return subprocess.CompletedProcess([], 0, out, "")


def run_main(runner, arguments=(), platform="darwin"):
    installer.THIS_MACHINE_PLATFORM = platform
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = installer.main(list(arguments), run=runner)
    return code, out.getvalue(), err.getvalue()


with tempfile.TemporaryDirectory() as directory:
    mac_token_file = Path(directory) / "mac.token"
    mac_token_file.write_text("mac-secret-token\n", encoding="utf-8")
    installer.NC_SHARED_DATABASE_SERVICE_TOKEN_FILE_PATH = mac_token_file
    step_count = len(installer.install_steps())

    runner = FakeRunner()
    code, out, err = run_main(runner)
    check("every step runs in order on its machine and the run exits 0",
          code == 0 and len(runner.calls) == step_count == 13
          and [c[0] for c in runner.calls] == ["mac", "ned-box", "mac", "ned-box", "ned-box",
                                               "ned-box", "ned-box", "ned-box", "mac", "mac",
                                               "mac", "ned-box", "ned-box"]
          and "is installed" in out and err == "", (code, runner.calls, out, err))
    with_token_input = [c for c in runner.calls if c[2] is not None]
    check("the Mac's token goes only to the accepted-tokens step, on standard input, and never "
          "on a command line",
          len(with_token_input) == 1 and with_token_input[0][2] == "mac-secret-token"
          and "accepted-tokens" in with_token_input[0][1]
          and not any("mac-secret-token" in c[1] for c in runner.calls), runner.calls)
    check("the reference-checkout steps test main's rename commit",
          all(installer.MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD in runner.calls[i][1]
              and "merge-base --is-ancestor" in runner.calls[i][1] for i in (0, 1)),
          runner.calls[:2])
    check("the unit enabled is the service's unit file, which exists in the repository",
          any("systemctl --user enable --now" in c[1] for c in runner.calls)
          and (REPOSITORY_ROOT / installer.NC_SHARED_DATABASE_SERVICE_SYSTEMD_UNIT_FILE_PATH.replace(installer.REFERENCE_CHECKOUT + "/",
                                                             "")).is_file(), installer.NC_SHARED_DATABASE_SERVICE_SYSTEMD_UNIT_FILE_PATH)

    runner = FakeRunner({7: (1, "", "sudo: a password is required")})
    code, out, err = run_main(runner)
    check("a failing step stops the run, exits 1, and reports the step, its error output and "
          "its advice",
          code == 1 and len(runner.calls) == 7 and "stopped at step 7 on ned-box" in err
          and "sudo: a password is required" in err
          and installer.sudo_advice("ned-box", runner.calls[6][1]) in err
          and installer.INSTALL_RERUN_INSTRUCTION_LINE in err and installer.SUBAGENT_REPORT_TO_DISPATCHING_AGENT_INSTRUCTION_LINE in err
          and "step 6 passed" in out, (code, out, err))
    sudo_line = next(part for part in err.split("`") if part.startswith("ssh -t "))
    check("the sudo advice gives the user an ssh -t command that hands ned-box the failed command, "
          "its own quotes included, with sudo free to ask for his password",
          shlex.split(sudo_line) == ["ssh", "-t", "nedlern@ned-box",
                                     runner.calls[6][1].replace("sudo -n ", "sudo ", 1)]
          and "sudo -n" not in shlex.split(sudo_line)[3], sudo_line)

    runner = FakeRunner({2: (255, "", "ssh: connect to host ned-box port 22: No route to host")})
    code, out, err = run_main(runner)
    check("ssh's exit 255 on ned-box gets the advice to check that ssh reaches ned-box",
          code == 1 and "ssh could not reach ned-box" in err
          and "does not yet hold main's commit" not in err, err)

    runner = FakeRunner({2: (1, "", "")})
    code, out, err = run_main(runner)
    check("a ned-box reference-checkout without main's commit gets the fast-forward command, "
          "through ssh",
          code == 1 and "`ssh nedlern@ned-box 'git -C ~/Projects/nedschorus pull --ff-only'`"
          in err, err)

    runner = FakeRunner({10: (0, "401", "")})
    code, out, err = run_main(runner)
    check("a service answer other than the one the check needs fails the step",
          code == 1 and "stopped at step 10 on mac" in err and "answered 401" in err
          and "needs 412" in err and "journalctl --user -u nc-shared-database-service" in err,
          err)

    runner = FakeRunner({10: (0, "500", "")})
    code, out, err = run_main(runner)
    check("a service answer that sorts after the needed one fails the step too",
          code == 1 and "stopped at step 10 on mac" in err and "answered 500" in err, err)

    runner = FakeRunner({6: (-9, "", "")})
    code, out, err = run_main(runner)
    check("a command killed by a signal, with a negative exit code, fails the step",
          code == 1 and "stopped at step 6 on ned-box" in err and "Exit code: -9" in err, err)

    runner = FakeRunner({3: (255, "", "")})
    code, out, err = run_main(runner)
    check("exit 255 on the Mac gets the step's own advice, not the advice that ssh could not "
          "reach ned-box",
          code == 1 and "ssh could not reach ned-box" not in err
          and "Find the cause" in err, err)

    runner = FakeRunner()
    code, out, err = run_main(runner, platform="linux")
    check("a machine other than the Mac is refused with exit 2 and nothing run",
          code == 2 and runner.calls == [] and "REFUSED" in err, (code, err))

    runner = FakeRunner()
    code, out, err = run_main(runner, ["--print"], platform="linux")
    check("--print lists every step and runs nothing",
          code == 0 and runner.calls == [] and out.count(", on ") == step_count, out)

with tempfile.TemporaryDirectory() as home:
    environment = {**os.environ, "HOME": home}

    def shell(command, standard_input=None):
        return subprocess.run(["sh", "-c", command], input=standard_input, capture_output=True,
                              text=True, env=environment)

    token_path = Path(home) / ".config" / "nedschorus" / "nc-shared-database-service.token"
    first = shell(installer.service_token_file_create_unless_present_shell_command())
    made = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else ""
    second = shell(installer.service_token_file_create_unless_present_shell_command())
    check("the token command makes a 64-character token, private to the user, and keeps it "
          "when run again",
          first.returncode == 0 and second.returncode == 0 and len(made) == 64
          and token_path.read_text(encoding="utf-8").strip() == made
          and (token_path.stat().st_mode & 0o077) == 0, (first, second, made))

    written = shell(installer.service_accepted_tokens_file_rewrite_shell_command(), "mac-secret-token")
    accepted_path = (Path(home) / ".config" / "nedschorus"
                     / "nc-shared-database-service-accepted-tokens")
    lines = accepted_path.read_text(encoding="utf-8").splitlines() if accepted_path.exists() else []
    check("the accepted-tokens command writes both tokens, one per line, private to the user",
          written.returncode == 0 and lines == ["mac-secret-token", made]
          and (accepted_path.stat().st_mode & 0o077) == 0, (written, lines))

    token_path.chmod(0)
    unreadable = shell(installer.service_accepted_tokens_file_rewrite_shell_command(), "mac-secret-token")
    token_path.chmod(0o600)
    after = accepted_path.read_text(encoding="utf-8").splitlines()
    check("when ned-box's token file cannot be read, the accepted-tokens command fails and leaves "
          "the old accepted-tokens file in place",
          unreadable.returncode != 0 and after == ["mac-secret-token", made], (unreadable, after))

recorded = []


def fake_subprocess_run(words, **keywords):
    recorded.append((words, keywords))
    return subprocess.CompletedProcess(words, 0, "", "")


real_subprocess_run = installer.subprocess.run
installer.subprocess.run = fake_subprocess_run
try:
    installer.run_on("mac", "echo mac step", None)
    installer.run_on("ned-box", "echo ned-box step", "a token")
finally:
    installer.subprocess.run = real_subprocess_run
check("a Mac step runs in a local shell and a ned-box step through ssh to ned-box, each with "
      "its standard input",
      [r[0] for r in recorded] == [["sh", "-c", "echo mac step"],
                                   ["ssh", "nedlern@ned-box", "echo ned-box step"]]
      and [r[1].get("input") for r in recorded] == [None, "a token"], recorded)

raise SystemExit(1 if failures else 0)
