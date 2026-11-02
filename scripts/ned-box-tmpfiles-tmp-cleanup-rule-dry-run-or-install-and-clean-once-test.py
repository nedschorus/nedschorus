#!/usr/bin/env python3
"""Tests for ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once.py.

Every case but the last runs commands through a stub that records them and answers
with canned results, so no case runs sudo or touches /etc or /tmp. The last case
parses the repository's rule file with the real systemd-tmpfiles against an empty
root directory, and is skipped where systemd-tmpfiles is not installed.

Run: python3 scripts/ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once-test.py
"""

import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name(
    "ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once.py")
_spec = importlib.util.spec_from_file_location("tmp_cleanup_rule_installer", SCRIPT_PATH)
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)

RULE = Path("/checkout/config/rule.conf")
failures = []

# What a non-root dry run on ned-box prints: removals, a directory it cannot open,
# a nested removal, and a file name holding a newline, split over two lines.
DRY_RUN_OUTPUT_AS_NON_ROOT = (
    'Opening directory "/tmp/timeshift-QrHrzamN" failed, ignoring: Permission denied\n'
    'Would remove directory "/tmp/merge-gate-abc/sub"\n'
    'Would remove directory "/tmp/merge-gate-abc"\n'
    'Would remove "/tmp/tmp.t5kA0l0Tli"\n'
    'Would remove directory "/tmp/worktrees/nl\n'
    'fake"\n'
    'Would restore access and modification time for "/tmp/kept"\n')


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


class CommandStub:
    """Records each command; answers the dry run with dry_run_result (or raises
    dry_run_raises), and each sudo command with failing_exit_code when its second word
    is in failing_sudo_commands, else 0. A negative exit code is how subprocess reports a
    command killed by a signal."""

    def __init__(self, dry_run_result=(73, DRY_RUN_OUTPUT_AS_NON_ROOT), dry_run_raises=None,
                 failing_sudo_commands=(), failing_exit_code=1):
        self.commands, self.failing_exit_code = [], failing_exit_code
        self.dry_run_result, self.dry_run_raises = dry_run_result, dry_run_raises
        self.failing_sudo_commands = set(failing_sudo_commands)

    def __call__(self, command, stdout=None, stderr=None, text=None):
        self.commands.append(list(command))
        if command[0] == "systemd-tmpfiles":
            if self.dry_run_raises:
                raise self.dry_run_raises
            code, output = self.dry_run_result
            return subprocess.CompletedProcess(command, code, stdout="", stderr=output)
        return subprocess.CompletedProcess(
            command, self.failing_exit_code if command[1] in self.failing_sudo_commands else 0)

    @property
    def sudo_commands(self):
        return [command for command in self.commands if command[0] == "sudo"]


def run_main(arguments, stub):
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        exit_code = installer.main(arguments, rule_file=RULE, run=stub)
    return exit_code, printed.getvalue(), errors.getvalue()


stub = CommandStub()
exit_code, printed, errors = run_main([], stub)
check("dry run as non-root: exit 0 although systemd-tmpfiles exits 73 for unopenable "
      "directories", exit_code == 0, errors)
check("dry run counts only entries directly inside /tmp, one per top-level path",
      "would remove 2 entries directly inside" in printed, printed)
check("dry run counts every removal line in the total", "(4 paths," in printed, printed)
check("dry run samples the top-level paths",
      "  /tmp/merge-gate-abc\n" in printed and "  /tmp/tmp.t5kA0l0Tli\n" in printed
      and "/tmp/merge-gate-abc/sub" not in printed, printed)
check("dry run reports the directories it could not open",
      "1 directories could not be opened without root" in printed, printed)
check("dry run runs systemd-tmpfiles on the rule file and nothing else",
      stub.commands == [["systemd-tmpfiles", "--dry-run", "--clean", str(RULE)]],
      stub.commands)
check("dry run says how to install", "--install-and-clean-once" in printed, printed)

stub = CommandStub(dry_run_result=(0, ""))
exit_code, printed, errors = run_main([], stub)
check("dry run with nothing to remove: exit 0 and a count of 0",
      exit_code == 0 and "would remove 0 entries" in printed, printed + errors)

invalid_rule_line = f"{RULE}:1: Invalid age-by 'abcmBMZ'."
stub = CommandStub(dry_run_result=(65, invalid_rule_line + "\n"))
exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
check("dry run that systemd-tmpfiles rejects: exit 1", exit_code == 1, printed + errors)
check("rejected dry run names the exit code and passes on systemd-tmpfiles' line",
      "dry run failed" in errors and "exited 65" in errors and invalid_rule_line in errors
      and f"When a line above names {RULE}, correct that line of the rule file." in errors,
      errors)
check("rejected dry run stops before any sudo command", stub.sudo_commands == [],
      stub.commands)

stub = CommandStub(dry_run_result=(73, 'Would remove "/tmp/x"\nFailed to open something\n'))
exit_code, printed, errors = run_main([], stub)
check("dry run exiting 73 with no unopenable directory to explain it: exit 1",
      exit_code == 1 and "Failed to open something" in errors
      and 'Would remove "/tmp/x"' not in errors, printed + errors)

for code in (65, 74, -9):
    stub = CommandStub(dry_run_result=(code, DRY_RUN_OUTPUT_AS_NON_ROOT))
    exit_code, printed, errors = run_main([], stub)
    check(f"dry run exiting {code}, though it also could not open a directory: exit 1",
          exit_code == 1 and f"exited {code}" in errors, printed + errors)

many_entries = "".join(f'Would remove "/tmp/entry-{number:02}"\n' for number in range(12))
stub = CommandStub(dry_run_result=(0, many_entries))
exit_code, printed, errors = run_main([], stub)
check("dry run samples the first 10 of 12 entries",
      "The first 10:" in printed and "/tmp/entry-09\n" in printed
      and "/tmp/entry-10" not in printed, printed)

stub = CommandStub(dry_run_raises=FileNotFoundError("systemd-tmpfiles"))
exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
check("systemd-tmpfiles missing: exit 1, says so, runs no sudo command",
      exit_code == 1 and "not on PATH" in errors and f"Run `{installer.DRY_RUN_COMMAND_LINE}` on ned-box" in errors
      and stub.sudo_commands == [],
      printed + errors)

stub = CommandStub()
exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
check("install: exit 0", exit_code == 0, printed + errors)
check("install: installs the rule as /etc/tmpfiles.d/tmp.conf, then cleans with it once",
      stub.sudo_commands == [
          ["sudo", "install", "-m", "0644", "-o", "root", "-g", "root", str(RULE),
           "/etc/tmpfiles.d/tmp.conf"],
          ["sudo", "systemd-tmpfiles", "--clean", "/etc/tmpfiles.d/tmp.conf"]],
      stub.commands)

stub = CommandStub(failing_sudo_commands={"install"})
exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
check("install fails: exit 1, says the file was not written, does not clean",
      exit_code == 1 and "install failed" in errors and "was not written" in errors and installer.SUDO_NEEDS_THE_USER_LINE in errors
      and f"run `{installer.INSTALL_COMMAND_LINE}` again on ned-box" in errors
      and "If that run fails the same way, stop and give the user what sudo printed." in errors
      and len(stub.sudo_commands) == 1, printed + errors + str(stub.commands))

stub = CommandStub(failing_sudo_commands={"systemd-tmpfiles"})
exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
check("clean fails: exit 1, says the rule is installed and how to clean again",
      exit_code == 1 and "clean failed" in errors and "The rule is installed" in errors
      and "`sudo systemd-tmpfiles --clean /etc/tmpfiles.d/tmp.conf` again" in errors,
      printed + errors)

for step in ("install", "systemd-tmpfiles"):
    stub = CommandStub(failing_sudo_commands={step}, failing_exit_code=-15)
    exit_code, printed, errors = run_main(["--install-and-clean-once"], stub)
    check(f"sudo {step} killed by a signal: exit 1", exit_code == 1 and "exited -15" in errors,
          printed + errors)

rule_lines = [line.split() for line in installer.RULE_FILE.read_text().splitlines()
              if line and not line.startswith("#")]
tmp_age = next(line[5] for line in rule_lines if line[1] == "/tmp")
age_by = tmp_age.split(":")[0]
check("the /tmp rule ignores directories' access time (A) and keeps files' (a)",
      "A" not in age_by and "a" in age_by and tmp_age.endswith(":10d"), tmp_age)

if shutil.which("systemd-tmpfiles") is None:
    print("SKIP  the rule file parses: systemd-tmpfiles is not installed here")
else:
    with tempfile.TemporaryDirectory() as empty_root:
        parsed = subprocess.run(
            ["systemd-tmpfiles", f"--root={empty_root}", "--dry-run", "--clean",
             str(installer.RULE_FILE)], capture_output=True, text=True)
    check("the rule file parses: systemd-tmpfiles accepts it with nothing to report",
          parsed.returncode == 0 and parsed.stderr == "",
          f"exit {parsed.returncode}: {parsed.stderr}")

if failures:
    print(f"\n{len(failures)} failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall passed")
