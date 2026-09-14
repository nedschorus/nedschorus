#!/usr/bin/env python3
"""Tests for install-restart-live-seats-at-login-systemd-unit.py
(nedschorus#116, build step 4, the box half).

Every case writes under a throwaway unit directory and runs systemctl
through a stub that records what it was asked, so no case touches
~/.config/systemd/user or a running user manager. The suite runs on either
machine: the installer's platform is passed in.

Run: python3 scripts/install-restart-live-seats-at-login-systemd-unit-test.py
"""

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("install-restart-live-seats-at-login-systemd-unit.py")
_spec = importlib.util.spec_from_file_location("install_systemd_unit", SCRIPT_PATH)
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail != "":
            print(f"      {detail}")


class SystemctlStub:
    """Records every systemctl command; answers the verbs in failing with
    exit 1, is-enabled with 0 only for the units in enabled (nonzero is
    what systemctl answers for disabled and unknown), everything else with
    success. on_start, when given, is called at the start verb so a case
    can look at the world as the manager would see it then."""

    def __init__(self, failing=(), enabled=(), on_start=None):
        self.commands, self.failing = [], set(failing)
        self.enabled, self.on_start = set(enabled), on_start

    def __call__(self, command, stdout=None, stderr=None):
        self.commands.append(list(command))
        if command[2] == "is-enabled":
            return subprocess.CompletedProcess(command, 0 if command[3] in self.enabled else 1)
        if command[2] == "start" and self.on_start is not None:
            self.on_start()
        return subprocess.CompletedProcess(command, 1 if command[2] in self.failing else 0)

    @property
    def verbs(self):
        return [command[2:] for command in self.commands]


def run_main(arguments, unit_directory, platform="linux", systemctl=None):
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        try:
            exit_code = installer.main(arguments, platform=platform,
                                       unit_directory=unit_directory,
                                       run=systemctl or SystemctlStub())
        except SystemExit as stop_request:
            exit_code = stop_request.code
    return exit_code, printed.getvalue(), errors.getvalue()


def unit_fields(text: str) -> dict:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    checkout = root / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "scripts" / "restart-live-seats-at-login.py").write_text("# program\n")
    home = root / "home"
    # abspath leaves an absolute path as typed and resolves a relative one
    # against the working directory, which on macOS reads back under
    # /private/var while the temporary root is spelled under /var.
    program = checkout / "scripts" / "restart-live-seats-at-login.py"
    program_from_relative = checkout.resolve() / "scripts" / "restart-live-seats-at-login.py"

    # The unit itself.
    text = installer.unit_text("restart-live-seats-at-login", checkout, None, home=home)
    fields = unit_fields(text)
    check("the program is run by the system python from the checkout's scripts/",
          fields["ExecStart"] == f"/usr/bin/python3 {program}", fields)
    check("one run per boot: oneshot, no Restart, wanted by default.target",
          fields["Type"] == "oneshot" and "Restart" not in fields
          and fields["WantedBy"] == "default.target", fields)
    check("KillMode=process, so the tmux servers it leaves behind outlive the unit",
          fields.get("KillMode") == "process", fields)
    check("RemainAfterExit is not set: a later stop must not kill the seats",
          "RemainAfterExit" not in fields, fields)
    check("PATH names claude's and tmux's directories, because the manager's is not promised",
          fields["Environment"] == f"PATH={home / '.local' / 'bin'}:/usr/local/bin:/usr/bin:/bin",
          fields)
    check("output is appended to a file beside the run log, stderr too",
          fields.get("StandardOutput") == fields.get("StandardError")
          == f"append:{home / '.claude' / 'handoffs' / 'restart-live-seats-at-login-systemd-output.txt'}",
          fields)
    check("the default unit name is the program's",
          installer.DEFAULT_UNIT_NAME == "restart-live-seats-at-login")

    # A test install points the program and its output at a throwaway
    # handoff directory.
    throwaway = root / "throwaway-handoffs"
    fields = unit_fields(installer.unit_text("t", checkout, throwaway, home=home))
    check("a handoff directory is passed to the program and holds the output file",
          fields["ExecStart"] == f"/usr/bin/python3 {program} --handoff-dir {throwaway}"
          and fields["StandardOutput"].startswith(f"append:{throwaway}/"),
          fields)

    # Relative paths are written absolute (the #354 review's finding on the
    # Mac installer, carried over): the manager starts the job in / and
    # resolves nothing against the shell's directory.
    working_directory_before = os.getcwd()
    os.chdir(root)
    try:
        fields = unit_fields(installer.unit_text("t", Path("checkout"),
                                                 Path("throwaway-handoffs"), home=home))
    finally:
        os.chdir(working_directory_before)
    check("a relative checkout and handoff directory are written absolute",
          fields["ExecStart"]
          == f"/usr/bin/python3 {program_from_relative} --handoff-dir {throwaway.resolve()}",
          fields)

    # --print writes nothing.
    unit_directory = root / "user-print"
    exit_code, printed, errors = run_main(["--print", "--checkout", str(checkout)], unit_directory)
    check("--print prints the unit and writes nothing",
          exit_code == 0 and not unit_directory.exists()
          and "[Service]" in printed and f"ExecStart=/usr/bin/python3 {program}" in printed,
          (exit_code, printed[:200], errors))

    # The product install: write, reload, enable; nothing started.
    unit_directory = root / "user-install"
    systemctl = SystemctlStub()
    exit_code, printed, errors = run_main(["--checkout", str(checkout)], unit_directory,
                                          systemctl=systemctl)
    written = unit_directory / "restart-live-seats-at-login.service"
    check("an install writes the unit under the user unit directory, creating it",
          exit_code == 0 and written.is_file()
          and f"ExecStart=/usr/bin/python3 {program}" in written.read_text(),
          (exit_code, printed, errors))
    check("and reloads then enables it, starting nothing: it runs at the next boot",
          systemctl.verbs == [["daemon-reload"], ["enable", "restart-live-seats-at-login.service"]]
          and "next boot" in printed and "nothing runs now" in printed,
          (systemctl.verbs, printed))
    check("every systemctl call is to the user manager",
          all(command[:2] == ["systemctl", "--user"] for command in systemctl.commands),
          systemctl.commands)

    # --start-now: write, reload, start; NOT enabled, so a throwaway does not
    # run at every boot.
    unit_directory = root / "user-start-now"
    systemctl = SystemctlStub()
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--unit-name", "t", "--handoff-dir", str(throwaway),
         "--start-now"], unit_directory, systemctl=systemctl)
    check("--start-now asks whether the name is enabled, then reloads and starts without enabling",
          exit_code == 0
          and systemctl.verbs == [["is-enabled", "t.service"], ["daemon-reload"],
                                  ["start", "t.service"]]
          and "started, not enabled" in printed and "will not run at boot" in printed,
          (exit_code, systemctl.verbs, printed, errors))

    # A test start must not touch an enabled unit: start leaves the enable
    # symlink in place, so the unit would run at every boot too, and under
    # --handoff-dir the file boot runs would now point at the throwaway
    # directory (PR #358 review, items 1 and 2). The product name is refused
    # outright; any other name is refused when the manager says enabled.
    unit_directory = root / "user-start-now-product-name"
    systemctl = SystemctlStub()
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--handoff-dir", str(throwaway), "--start-now"],
        unit_directory, systemctl=systemctl)
    check("--start-now without a throwaway --unit-name is refused before anything is done",
          exit_code == 2 and "needs a throwaway --unit-name" in errors
          and not unit_directory.exists() and systemctl.commands == [],
          (exit_code, errors, systemctl.commands))
    unit_directory = root / "user-start-now-enabled-name"
    run_main(["--checkout", str(checkout), "--unit-name", "t"], unit_directory)
    before = (unit_directory / "t.service").read_text()
    systemctl = SystemctlStub(enabled=["t.service"])
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--unit-name", "t", "--handoff-dir", str(throwaway),
         "--start-now"], unit_directory, systemctl=systemctl)
    check("--start-now on a name the manager reports enabled is refused, and the unit "
          "file is not rewritten",
          exit_code == 1 and "is enabled" in errors and "--remove it first" in errors
          and (unit_directory / "t.service").read_text() == before
          and systemctl.verbs == [["is-enabled", "t.service"]],
          (exit_code, errors, systemctl.verbs))

    # The output directory is created before start: StandardOutput=append:
    # does not create it, and a start into a missing directory fails before
    # the program's own mkdir (PR #358 review, item 4).
    missing = root / "not-yet" / "handoffs"
    seen = {}
    systemctl = SystemctlStub(on_start=lambda: seen.update(exists=missing.is_dir()))
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--unit-name", "t", "--handoff-dir", str(missing),
         "--start-now"], root / "user-start-now-mkdir", systemctl=systemctl)
    check("--start-now creates the handoff directory before the start",
          exit_code == 0 and seen.get("exists") is True, (exit_code, seen, errors))

    # Failures of each systemctl step are reported with their exit code.
    for verb, arguments in (("daemon-reload", ["--checkout", str(checkout)]),
                            ("enable", ["--checkout", str(checkout)]),
                            ("start", ["--checkout", str(checkout), "--unit-name", "t",
                                       "--start-now"])):
        systemctl = SystemctlStub(failing=[verb])
        exit_code, printed, errors = run_main(arguments, root / f"user-fail-{verb}",
                                              systemctl=systemctl)
        check(f"a failed {verb} is reported with its exit code, and the run exits 1",
              exit_code == 1 and f"{verb} failed (exit 1)" in errors,
              (exit_code, printed, errors))

    # --remove: disable, delete, reload.
    unit_directory = root / "user-remove"
    run_main(["--checkout", str(checkout), "--unit-name", "t"], unit_directory)
    systemctl = SystemctlStub()
    exit_code, printed, errors = run_main(["--unit-name", "t", "--remove"], unit_directory,
                                          systemctl=systemctl)
    check("--remove disables the unit, deletes its file, and reloads",
          exit_code == 0
          and systemctl.verbs == [["disable", "t.service"], ["daemon-reload"]]
          and not (unit_directory / "t.service").exists() and "removed" in printed,
          (exit_code, systemctl.verbs, printed))
    systemctl = SystemctlStub(failing=["disable"])
    exit_code, printed, errors = run_main(["--unit-name", "t", "--remove"], unit_directory,
                                          systemctl=systemctl)
    check("removing a unit that is not there still reloads and says there was none",
          exit_code == 0 and "no " in printed and "to remove" in printed
          and systemctl.verbs[-1] == ["daemon-reload"], (printed, systemctl.verbs))

    # A checkout without the program is refused.
    unit_directory = root / "user-bad-checkout"
    systemctl = SystemctlStub()
    exit_code, printed, errors = run_main(["--checkout", str(root / "not-a-checkout")],
                                          unit_directory, systemctl=systemctl)
    check("a checkout without the program is refused, nothing written, nothing run",
          exit_code == 1 and "no restart-live-seats-at-login.py under" in errors
          and not unit_directory.exists() and systemctl.commands == [],
          (exit_code, printed, errors))

    # Not the Mac.
    exit_code, printed, errors = run_main(["--checkout", str(checkout)], root / "user-darwin",
                                          platform="darwin")
    check("on the Mac the installer refuses and names the LaunchAgent installer",
          exit_code == 2 and "launch-agent" in errors, (exit_code, errors))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
