#!/usr/bin/env python3
"""Tests for nc-systems/nc-shared-database/nc-shared-database-service-install-on-both-machines-from-the-mac.py

The program's runner is replaced by a fake that records each (machine, command,
standard input) and answers as each case asks, so nothing is installed and no
ssh session is opened. Cases: every step runs in order and passes; the Mac's
token reaches only the accepted-tokens step, on standard input; a failing step
stops the run and reports the step, its output and its advice; ssh's exit 255
gets the reach-ned-box advice; a service answer other than the one a check needs
fails; a machine other than the Mac is refused; --print runs nothing. Two cases
run the token and accepted-tokens commands in a real shell under a temporary
HOME: a token is made once and kept, and the accepted-tokens file holds both.

Run: python3 nc-systems/nc-shared-database/tests/nc-shared-database-service-install-on-both-machines-from-the-mac-test.py
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
                / "nc-shared-database-service-install-on-both-machines-from-the-mac.py")
_spec = importlib.util.spec_from_file_location(
    "nc_shared_database_service_install_on_both_machines_from_the_mac", PROGRAM_PATH)
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
        out = "412" if "Bearer" in command else "401" if "curl" in command else ""
        return subprocess.CompletedProcess([], 0, out, "")


def run_main(runner, arguments=(), platform="darwin"):
    installer.PLATFORM = platform
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = installer.main(list(arguments), run=runner)
    return code, out.getvalue(), err.getvalue()


with tempfile.TemporaryDirectory() as directory:
    mac_token_file = Path(directory) / "mac.token"
    mac_token_file.write_text("mac-secret-token\n", encoding="utf-8")
    installer.MAC_TOKEN_FILE_PATH = mac_token_file
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
          all(installer.FIRST_MAIN_COMMIT_WITH_THESE_FILES in runner.calls[i][1]
              and "merge-base --is-ancestor" in runner.calls[i][1] for i in (0, 1)),
          runner.calls[:2])
    check("the unit enabled is the service's unit file, which exists in the repository",
          any("systemctl --user enable --now" in c[1] for c in runner.calls)
          and (REPOSITORY_ROOT / installer.UNIT_FILE.replace(installer.REFERENCE_CHECKOUT + "/",
                                                             "")).is_file(), installer.UNIT_FILE)

    runner = FakeRunner({7: (1, "", "sudo: a password is required")})
    code, out, err = run_main(runner)
    check("a failing step stops the run, exits 1, and reports the step, its error output and "
          "its advice",
          code == 1 and len(runner.calls) == 7 and "stopped at step 7," in err
          and "sudo: a password is required" in err
          and installer.sudo_advice("ned-box", runner.calls[6][1]) in err
          and installer.RERUN_LINE in err and installer.SUBAGENT_LINE in err
          and "step 6 passed" in out, (code, out, err))
    sudo_line = installer.command_for_the_mac("ned-box", runner.calls[6][1])
    check("the sudo advice's ssh command hands ned-box the failed command unchanged, its own "
          "quotes included",
          shlex.split(sudo_line) == ["ssh", "-t", "nedlern@ned-box", runner.calls[6][1]],
          sudo_line)

    runner = FakeRunner({2: (255, "", "ssh: connect to host ned-box port 22: No route to host")})
    code, out, err = run_main(runner)
    check("ssh's exit 255 on ned-box gets the advice to check that ssh reaches ned-box",
          code == 1 and "ssh could not reach ned-box" in err
          and "does not yet hold main's commit" not in err, err)

    runner = FakeRunner({2: (1, "", "")})
    code, out, err = run_main(runner)
    check("a ned-box reference-checkout without main's commit gets the fast-forward command, "
          "through ssh",
          code == 1 and "ssh -t nedlern@ned-box 'git -C ~/Projects/nedschorus pull --ff-only'"
          in err, err)

    runner = FakeRunner({10: (0, "401", "")})
    code, out, err = run_main(runner)
    check("a service answer other than the one the check needs fails the step",
          code == 1 and "stopped at step 10," in err and "answered 401" in err
          and "needs 412" in err and "journalctl --user -u nc-shared-database-service" in err,
          err)

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
    first = shell(installer.token_file_made_unless_present_command())
    made = token_path.read_text(encoding="utf-8").strip() if token_path.exists() else ""
    second = shell(installer.token_file_made_unless_present_command())
    check("the token command makes a 64-character token, private to the user, and keeps it "
          "when run again",
          first.returncode == 0 and second.returncode == 0 and len(made) == 64
          and token_path.read_text(encoding="utf-8").strip() == made
          and (token_path.stat().st_mode & 0o077) == 0, (first, second, made))

    written = shell(installer.accepted_tokens_file_written_command(), "mac-secret-token")
    accepted_path = (Path(home) / ".config" / "nedschorus"
                     / "nc-shared-database-service-accepted-tokens")
    lines = accepted_path.read_text(encoding="utf-8").splitlines() if accepted_path.exists() else []
    check("the accepted-tokens command writes both tokens, one per line, private to the user",
          written.returncode == 0 and lines == ["mac-secret-token", made]
          and (accepted_path.stat().st_mode & 0o077) == 0, (written, lines))

raise SystemExit(1 if failures else 0)
