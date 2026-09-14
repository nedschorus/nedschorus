#!/usr/bin/env python3
"""Tests for install-restart-live-seats-at-login-launch-agent.py
(nedschorus#116, build step 4).

Every case writes under a throwaway LaunchAgents directory and runs launchctl
through a stub that records what it was asked, so no case touches
~/Library/LaunchAgents or this login session's launchd.

Run: python3 scripts/install-restart-live-seats-at-login-launch-agent-test.py
"""

import importlib.util
import io
import os
import plistlib
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("install-restart-live-seats-at-login-launch-agent.py")
_spec = importlib.util.spec_from_file_location("install_launch_agent", SCRIPT_PATH)
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail != "":
            print(f"      {detail}")


class LaunchctlStub:
    """Records every launchctl command; answers bootstrap with the exit code
    it was given and everything else with success."""

    def __init__(self, bootstrap_exit_code=0):
        self.commands, self.bootstrap_exit_code = [], bootstrap_exit_code

    def __call__(self, command, stdout=None, stderr=None):
        self.commands.append(list(command))
        code = self.bootstrap_exit_code if command[1] == "bootstrap" else 0
        return subprocess.CompletedProcess(command, code)


def run_main(arguments, launch_agents_directory, platform="darwin", launchctl=None):
    printed, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(printed), redirect_stderr(errors):
        try:
            exit_code = installer.main(arguments, platform=platform,
                                       launch_agents_directory=launch_agents_directory,
                                       run=launchctl or LaunchctlStub())
        except SystemExit as stop_request:
            exit_code = stop_request.code
    return exit_code, printed.getvalue(), errors.getvalue()


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    checkout = root / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "scripts" / "restart-live-seats-at-login.py").write_text("# program\n")
    home = root / "home"

    # The plist itself.
    plist = installer.launch_agent_plist("com.nedschorus.restart-live-seats-at-login",
                                         checkout, None, home=home)
    check("the program is run by the system python from the checkout's scripts/",
          plist["ProgramArguments"]
          == ["/usr/bin/python3", str(checkout / "scripts" / "restart-live-seats-at-login.py")],
          plist["ProgramArguments"])
    check("it runs at load, which at login is once per login",
          plist["RunAtLoad"] is True and "KeepAlive" not in plist
          and "StartInterval" not in plist, plist)
    check("only in the graphical session: it opens windows",
          plist["LimitLoadToSessionType"] == "Aqua", plist)
    check("PATH names claude's, tmux's and gh's directories, because launchd's own is bare",
          plist["EnvironmentVariables"]["PATH"].split(":")[:3]
          == [str(home / ".local" / "bin"), "/opt/homebrew/bin", "/usr/local/bin"]
          and "/usr/bin" in plist["EnvironmentVariables"]["PATH"].split(":"),
          plist["EnvironmentVariables"])
    check("output goes to a file beside the run log: there is no terminal at login",
          plist["StandardOutPath"] == plist["StandardErrorPath"]
          == str(home / ".claude" / "handoffs" / "restart-live-seats-at-login-launchd-output.txt"),
          plist)
    check("the label is the plist's and the default is the project's",
          plist["Label"] == installer.DEFAULT_LABEL
          == "com.nedschorus.restart-live-seats-at-login", plist["Label"])

    # A test install points the program and its output at a throwaway
    # handoff directory, so the real run log and the real seats are untouched.
    throwaway = root / "throwaway-handoffs"
    plist = installer.launch_agent_plist("com.nedschorus.test", checkout, throwaway, home=home)
    check("a handoff directory is passed to the program and holds the output file",
          plist["ProgramArguments"][2:] == ["--handoff-dir", str(throwaway)]
          and plist["StandardOutPath"]
          == str(throwaway / "restart-live-seats-at-login-launchd-output.txt"),
          plist)

    # A relative --checkout or --handoff-dir is written absolute: launchd
    # starts the job in /, where a relative path names nothing.
    working_directory_before = os.getcwd()
    os.chdir(root)
    try:
        plist = installer.launch_agent_plist("com.nedschorus.test", Path("checkout"),
                                             Path("throwaway-handoffs"), home=home)
        exit_code, printed, errors = run_main(
            ["--checkout", "checkout", "--label", "com.nedschorus.relative"],
            root / "LaunchAgents-relative")
    finally:
        os.chdir(working_directory_before)
    # Compared resolved: on macOS the temporary root is under /var, an alias
    # of /private/var, and the working directory reads back as the latter.
    check("a relative checkout and handoff directory are written absolute, because launchd "
          "starts the job in /",
          plist["ProgramArguments"][1]
          == str(checkout.resolve() / "scripts" / "restart-live-seats-at-login.py")
          and plist["ProgramArguments"][3] == str(throwaway.resolve())
          and plist["StandardOutPath"].startswith(str(throwaway.resolve())),
          plist)
    check("and an install typed with a relative checkout finds the program and writes it absolute",
          exit_code == 0
          and plistlib.loads((root / "LaunchAgents-relative" / "com.nedschorus.relative.plist")
                             .read_bytes())["ProgramArguments"][1]
          == str(checkout.resolve() / "scripts" / "restart-live-seats-at-login.py"),
          (exit_code, printed, errors))

    # --print writes nothing.
    agents_directory = root / "LaunchAgents-print"
    exit_code, printed, errors = run_main(
        ["--print", "--checkout", str(checkout)], agents_directory)
    check("--print prints a plist launchd would read, and writes nothing",
          exit_code == 0 and not agents_directory.exists()
          and plistlib.loads(printed.encode("utf-8"))["Label"] == installer.DEFAULT_LABEL,
          (exit_code, printed[:200], errors))

    # Install without bootstrap: the plist is written, launchctl is not run.
    agents_directory = root / "LaunchAgents-install"
    launchctl = LaunchctlStub()
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout)], agents_directory, launchctl=launchctl)
    written = agents_directory / f"{installer.DEFAULT_LABEL}.plist"
    check("an install writes the plist under the LaunchAgents directory, creating it",
          exit_code == 0 and written.is_file()
          and plistlib.loads(written.read_bytes())["ProgramArguments"][1]
          == str(checkout / "scripts" / "restart-live-seats-at-login.py"),
          (exit_code, printed, errors))
    check("and does not load it: it takes effect at the next login",
          launchctl.commands == [] and "next login" in printed and "nothing runs now" in printed,
          (launchctl.commands, printed))

    # --bootstrap-now loads it into this login session, after booting out
    # any earlier load of the label.
    agents_directory = root / "LaunchAgents-bootstrap"
    launchctl = LaunchctlStub()
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--label", "com.nedschorus.test", "--handoff-dir",
         str(throwaway), "--bootstrap-now"], agents_directory, launchctl=launchctl)
    domain = f"gui/{os.getuid()}"
    check("--bootstrap-now boots out the label, then bootstraps the written plist",
          exit_code == 0 and launchctl.commands == [
              ["launchctl", "bootout", f"{domain}/com.nedschorus.test"],
              ["launchctl", "bootstrap", domain,
               str(agents_directory / "com.nedschorus.test.plist")]]
          and "running now" in printed,
          (exit_code, launchctl.commands, printed, errors))

    launchctl = LaunchctlStub(bootstrap_exit_code=5)
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout), "--label", "com.nedschorus.test", "--bootstrap-now"],
        agents_directory, launchctl=launchctl)
    check("a bootstrap that fails is reported with its exit code, and the run exits 1",
          exit_code == 1 and "bootstrap failed (exit 5)" in errors
          and (agents_directory / "com.nedschorus.test.plist").is_file(),
          (exit_code, printed, errors))

    # --remove boots the label out and deletes its plist.
    launchctl = LaunchctlStub()
    exit_code, printed, errors = run_main(
        ["--label", "com.nedschorus.test", "--remove"], agents_directory, launchctl=launchctl)
    check("--remove boots out the label and deletes its plist",
          exit_code == 0
          and launchctl.commands == [["launchctl", "bootout", f"{domain}/com.nedschorus.test"]]
          and not (agents_directory / "com.nedschorus.test.plist").exists()
          and "removed" in printed,
          (exit_code, launchctl.commands, printed))
    exit_code, printed, errors = run_main(
        ["--label", "com.nedschorus.test", "--remove"], agents_directory)
    check("removing a label with no plist still boots it out and says there was none",
          exit_code == 0 and "no " in printed and "to remove" in printed, printed)

    # A checkout without the program is refused: the plist would point at
    # nothing and fail silently at every login.
    agents_directory = root / "LaunchAgents-bad-checkout"
    exit_code, printed, errors = run_main(
        ["--checkout", str(root / "not-a-checkout")], agents_directory)
    check("a checkout without the program is refused, and nothing is written",
          exit_code == 1 and "no restart-live-seats-at-login.py under" in errors
          and not agents_directory.exists(),
          (exit_code, printed, errors))

    # Not the box.
    exit_code, printed, errors = run_main(
        ["--checkout", str(checkout)], root / "LaunchAgents-linux", platform="linux")
    check("on the box the installer refuses: LaunchAgents are macOS",
          exit_code == 2 and "macOS" in errors, (exit_code, errors))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
