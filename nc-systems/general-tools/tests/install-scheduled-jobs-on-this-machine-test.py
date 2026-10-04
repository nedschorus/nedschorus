#!/usr/bin/env python3
"""Tests for install-scheduled-jobs-on-this-machine.py and its table,
scheduled-jobs-on-each-machine.json.

Run: python3 nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-test.py

No case installs anything real. Every `crontab`, `plutil` and `launchctl`
command goes to a stand-in for subprocess.run that holds a crontab in memory
and a set of loaded launchd jobs, and records what it was asked. The table,
the two machines' home directories and clones, and the LaunchAgents directory
are made under a temporary directory. The cases that read the real table
derive lines and a plist from it and run nothing.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = GENERAL_TOOLS.parent.parent
SCRIPT_PATH = GENERAL_TOOLS / "install-scheduled-jobs-on-this-machine.py"
REAL_TABLE_PATH = GENERAL_TOOLS / "scheduled-jobs-on-each-machine.json"
_spec = importlib.util.spec_from_file_location("install_scheduled_jobs", SCRIPT_PATH)
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)

failures = []


def check(case_name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {case_name}")
    if not condition:
        failures.append(case_name)
        if detail != "":
            print(f"      {detail}")


# What each machine had installed when this program was written, measured
# with `crontab -l` on both on 2026-10-01. The table must give these lines
# byte for byte: an install on either machine then changes nothing.
NED_BOX_MIRROR_LINE = (
    "* * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/"
    "transcript-mirror-to-log-store.py --failures-only >> "
    "/home/nedlern/.claude/transcript-mirror.log 2>&1")
NED_BOX_DAILY_LINE = (
    "30 3 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/"
    "daily-full-test-run-of-main.py >> "
    "/home/nedlern/.claude/daily-full-test-run-of-main.log 2>&1")
MAC_MIRROR_LINE = (
    "* * * * * /opt/homebrew/bin/python3 /Users/el/Projects/nedschorus/scripts/"
    "transcript-mirror-to-log-store.py --failures-only >> "
    "/Users/el/.claude/transcript-mirror.log 2>&1")
NED_BOX_FOREIGN_COMMENT = (
    "# nedsmessenger stopped 2026-09-30 at the user's word: 15 3 * * * "
    "/home/nedlern/agent/nedsmessenger/scripts/nightly-backup.sh")
MAC_DAILY_PLIST = {
    "Label": "com.nedschorus.daily-full-test-run-of-main",
    "ProgramArguments": ["/opt/homebrew/bin/python3",
                         "/Users/el/Projects/nedschorus/scripts/daily-full-test-run-of-main.py"],
    "EnvironmentVariables": {
        "PATH": "/Users/el/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:"
                "/usr/sbin:/sbin"},
    "StartCalendarInterval": {"Hour": 3, "Minute": 30},
    "StandardOutPath": "/Users/el/.claude/daily-full-test-run-of-main.log",
    "StandardErrorPath": "/Users/el/.claude/daily-full-test-run-of-main.log",
}
# The daily worktree cleanup, added to the table after the two jobs above; no
# machine had it installed by hand.
NED_BOX_CLEAN_LINE = (
    "30 6 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/"
    "clean-worktrees.py --remove >> /home/nedlern/.claude/daily-clean-worktrees.log 2>&1")
MAC_CLEAN_PLIST = {
    "Label": "com.nedschorus.daily-clean-worktrees",
    "ProgramArguments": ["/opt/homebrew/bin/python3",
                         "/Users/el/Projects/nedschorus/scripts/clean-worktrees.py", "--remove"],
    "EnvironmentVariables": {
        "PATH": "/Users/el/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:"
                "/usr/sbin:/sbin"},
    "StartCalendarInterval": {"Hour": 6, "Minute": 30},
    "StandardOutPath": "/Users/el/.claude/daily-clean-worktrees.log",
    "StandardErrorPath": "/Users/el/.claude/daily-clean-worktrees.log",
}
DOMAIN = f"gui/{os.getuid()}"


class MachineStub:
    """Stands in for subprocess.run. Holds one user's crontab (None: the user
    has none) and the launchd targets that are loaded; records every command
    and every crontab written."""

    def __init__(self, crontab=None, loaded=()):
        self.crontab = crontab
        self.loaded = set(loaded)
        self.commands, self.crontab_writes = [], []
        self.crontab_list_failure = None      # (exit code, stderr bytes)
        self.exit_codes = {}                  # "crontab-write" | "lint" | "bootstrap" | "kickstart" | "bootout" | "print"
        self.bootstrap_loads_the_job = True
        # The macOS failure: `crontab` exits 0 and leaves an empty crontab.
        self.crontab_write_installs_empty_crontab = False

    def __call__(self, command, stdout=None, stderr=None, input=None):
        command = list(command)
        self.commands.append(command)
        code, out, err = 0, b"", b""
        if command[:2] == ["crontab", "-l"]:
            if self.crontab_list_failure is not None:
                code, err = self.crontab_list_failure
            elif self.crontab is None:
                code, err = 1, b"crontab: no crontab for someone\n"
            else:
                out = self.crontab
        elif command == ["crontab", "-"]:
            code = self.exit_codes.get("crontab-write", 0)
            self.crontab_writes.append(input)
            if code == 0:
                self.crontab = b"" if self.crontab_write_installs_empty_crontab else input
        elif command[:2] == ["plutil", "-lint"]:
            code = self.exit_codes.get("lint", 0)
        elif command[:2] == ["launchctl", "print"]:
            code = self.exit_codes.get("print", 0 if command[2] in self.loaded else 113)
        elif command[:2] == ["launchctl", "bootout"]:
            if "bootout" in self.exit_codes and command[2] in self.loaded:
                code, err = self.exit_codes["bootout"], b"Boot-out failed: 5: Input/output error\n"
            else:
                code = 0 if command[2] in self.loaded else 3
                self.loaded.discard(command[2])
        elif command[:2] == ["launchctl", "bootstrap"]:
            code = self.exit_codes.get("bootstrap", 0)
            if code == 0 and self.bootstrap_loads_the_job:
                self.loaded.add(f"{command[2]}/{Path(command[3]).stem}")
        elif command[:2] == ["launchctl", "kickstart"]:
            code = self.exit_codes.get("kickstart", 0)
        else:
            raise AssertionError(f"a command no case expects: {command}")
        return subprocess.CompletedProcess(command, code, stdout=out, stderr=err)

    def launchctl_verbs(self):
        return [command[1] for command in self.commands if command[0] == "launchctl"]


def run_main(arguments, machine, stub=None, table_path=None):
    """main() as one of the two fixture machines; machine is (platform, home)."""
    printed, errors = io.StringIO(), io.StringIO()
    platform, home = machine
    with redirect_stdout(printed), redirect_stderr(errors):
        try:
            exit_code = installer.main(
                arguments, platform=platform, home=home,
                table_path=table_path or FIXTURE_TABLE_PATH,
                launch_agents_directory=LAUNCH_AGENTS, run=stub or MachineStub())
        except SystemExit as stop_request:
            exit_code = stop_request.code
    return exit_code, printed.getvalue(), errors.getvalue()


# --- the real table ------------------------------------------------------

real_table = installer.load_table(REAL_TABLE_PATH)
real_jobs = {job["name"]: job for job in real_table["jobs"]}
mac, ned_box = real_table["machines"]["mac"], real_table["machines"]["ned-box"]
mirror, daily = real_jobs["transcript-mirror-to-log-store"], real_jobs["daily-full-test-run-of-main"]
clean = real_jobs["daily-clean-worktrees"]

check("the table gives ned-box the transcript mirror's cron line it has installed, byte for byte",
      installer.cron_line(ned_box, mirror, mirror["on"]["ned-box"]) == NED_BOX_MIRROR_LINE,
      installer.cron_line(ned_box, mirror, mirror["on"]["ned-box"]))
check("the table gives ned-box the daily full test run's cron line it has installed, byte for byte",
      installer.cron_line(ned_box, daily, daily["on"]["ned-box"]) == NED_BOX_DAILY_LINE,
      installer.cron_line(ned_box, daily, daily["on"]["ned-box"]))
check("the table gives the Mac the transcript mirror's cron line it has installed, byte for byte",
      installer.cron_line(mac, mirror, mirror["on"]["mac"]) == MAC_MIRROR_LINE,
      installer.cron_line(mac, mirror, mirror["on"]["mac"]))
mac_plist = installer.launch_agent_plist(mac, daily, daily["on"]["mac"])
check("the Mac's daily full test run is a launchd job at 03:30, not a cron line: a run missed "
      "while the Mac sleeps starts at the next wake",
      daily["on"]["mac"]["scheduler"] == "launchd" and mac_plist == MAC_DAILY_PLIST
      and list(mac_plist) == list(MAC_DAILY_PLIST), mac_plist)
check("the table gives ned-box the daily worktree cleanup's cron line at 06:30, two hours after "
      "the daily full test run",
      installer.cron_line(ned_box, clean, clean["on"]["ned-box"]) == NED_BOX_CLEAN_LINE,
      installer.cron_line(ned_box, clean, clean["on"]["ned-box"]))
mac_clean_plist = installer.launch_agent_plist(mac, clean, clean["on"]["mac"])
check("the Mac's daily worktree cleanup is a launchd job at 06:30, so a run missed while the Mac "
      "sleeps starts at the next wake",
      clean["on"]["mac"]["scheduler"] == "launchd" and mac_clean_plist == MAC_CLEAN_PLIST
      and list(mac_clean_plist) == list(MAC_CLEAN_PLIST), mac_clean_plist)
check("the table's jobs are the two typed by hand before this program and the daily worktree "
      "cleanup, and no other",
      sorted(real_jobs) == ["daily-clean-worktrees", "daily-full-test-run-of-main",
                            "transcript-mirror-to-log-store"],
      sorted(real_jobs))
check("every job's program is a file of this repository",
      all((REPOSITORY_ROOT / job["program"]).is_file() for job in real_table["jobs"]),
      [job["program"] for job in real_table["jobs"]])
mirror_documentation = (REPOSITORY_ROOT / mirror["program"]).read_text(encoding="utf-8")
daily_documentation = (REPOSITORY_ROOT / daily["program"]).read_text(encoding="utf-8")
clean_documentation = (REPOSITORY_ROOT / clean["program"]).read_text(encoding="utf-8")
check("the lines each program documents are the table's lines, and each names this installer",
      f"  Mac:     {MAC_MIRROR_LINE}\n" in mirror_documentation
      and f"  ned-box: {NED_BOX_MIRROR_LINE}\n" in mirror_documentation
      and f"    {NED_BOX_DAILY_LINE}\n" in daily_documentation
      and f"    {NED_BOX_CLEAN_LINE}\n" in clean_documentation
      and all("nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py" in text
              for text in (mirror_documentation, daily_documentation, clean_documentation)))

printed, errors = io.StringIO(), io.StringIO()
stub = MachineStub()
with redirect_stdout(printed), redirect_stderr(errors):
    exit_code = installer.main(["--print"], platform="linux", home=Path("/home/nedlern"), run=stub)
check("--print as ned-box prints ned-box's three cron lines from the real table and runs nothing",
      exit_code == 0 and stub.commands == []
      and printed.getvalue().splitlines() == [
          "machine: ned-box (linux, /home/nedlern)",
          "transcript-mirror-to-log-store — cron line:", NED_BOX_MIRROR_LINE,
          "daily-full-test-run-of-main — cron line:", NED_BOX_DAILY_LINE,
          "daily-clean-worktrees — cron line:", NED_BOX_CLEAN_LINE],
      (exit_code, printed.getvalue(), errors.getvalue()))
printed, errors = io.StringIO(), io.StringIO()
with redirect_stdout(printed), redirect_stderr(errors):
    exit_code = installer.main(["--print"], platform="darwin", home=Path("/Users/el"), run=stub)
mac_printed = printed.getvalue()
clean_heading = ("daily-clean-worktrees — launchd job, /Users/el/Library/LaunchAgents/"
                 "com.nedschorus.daily-clean-worktrees.plist:\n")
daily_part, _, clean_part = mac_printed.partition(clean_heading)
check("--print as the Mac prints the mirror's cron line and the two daily jobs' plists, and runs "
      "nothing",
      exit_code == 0 and stub.commands == [] and clean_part.startswith("<?xml")
      and daily_part.startswith(
          "machine: mac (darwin, /Users/el)\ntranscript-mirror-to-log-store — cron line:\n"
          f"{MAC_MIRROR_LINE}\ndaily-full-test-run-of-main — launchd job, /Users/el/Library/"
          "LaunchAgents/com.nedschorus.daily-full-test-run-of-main.plist:\n<?xml")
      and plistlib.loads(daily_part[daily_part.index("<?xml"):].encode("utf-8"))
      == MAC_DAILY_PLIST
      and plistlib.loads(clean_part.encode("utf-8")) == MAC_CLEAN_PLIST,
      (exit_code, mac_printed, errors.getvalue()))


printed, errors = io.StringIO(), io.StringIO()
with redirect_stdout(printed), redirect_stderr(errors):
    try:
        installer.main(["--help"])
        help_exit = None
    except SystemExit as stop_request:
        help_exit = stop_request.code
help_text = printed.getvalue()
check("--help ends with the docstring's exit-codes paragraph and prints nothing else of the "
      "docstring",
      help_exit == 0
      and " ".join(help_text.split()).endswith(
          "Exit codes: 0 done, or for --check every job matches; 1 a step failed after this "
          "program began changing the machine, or for --check a job differs or is not in the "
          "table; 2 not run — a bad "
          "invocation, a table this program cannot use, a machine the table does not name, a "
          "job's program missing, or a crontab that could not be read.")
      and "WHY THIS EXISTS" not in help_text and "THE TABLE is " not in help_text
      and "user-ruled" not in help_text, help_text)
check("--check's help names both reasons for exit 1",
      "exit 1 on a difference or a job not in the table" in " ".join(help_text.split()),
      help_text)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary).resolve()
    LAUNCH_AGENTS = root / "LaunchAgents"
    FIXTURE_TABLE_PATH = root / "table.json"
    fixture_table = json.loads(REAL_TABLE_PATH.read_text(encoding="utf-8"))
    # The cases below test the installer's mechanism on one cron job and one
    # launchd job per machine, so the fixture keeps the real table's first two
    # jobs; the real-table cases above cover every job the table holds.
    fixture_table["jobs"] = [job for job in fixture_table["jobs"]
                             if job["name"] in ("transcript-mirror-to-log-store",
                                                "daily-full-test-run-of-main")]
    for machine_name in ("mac", "ned-box"):
        machine_home = root / f"{machine_name}-home"
        clone = machine_home / "Projects" / "nedschorus"
        (clone / "scripts").mkdir(parents=True)
        for job in fixture_table["jobs"]:
            (clone / job["program"]).write_text("# program\n")
        fixture_table["machines"][machine_name]["home"] = str(machine_home)
        fixture_table["machines"][machine_name]["clone"] = str(clone)
    fixture_table["machines"]["mac"]["launchd_path"] = f"{root}/mac-home/.local/bin:/usr/bin:/bin"
    # A third job, placed on ned-box alone, for the cases about a job this
    # machine does not run.
    fixture_table["jobs"].append({
        "name": "runs-on-ned-box-alone", "program": "scripts/runs-on-ned-box-alone.py",
        "arguments": [], "output": ".claude/runs-on-ned-box-alone.log",
        "on": {"ned-box": {"scheduler": "cron", "schedule": "5 4 * * 0"}}})
    (root / "ned-box-home" / "Projects" / "nedschorus" / "scripts"
     / "runs-on-ned-box-alone.py").write_text("# program\n")
    FIXTURE_TABLE_PATH.write_text(json.dumps(fixture_table), encoding="utf-8")

    MAC = ("darwin", root / "mac-home")
    NED_BOX = ("linux", root / "ned-box-home")
    table = installer.load_table(FIXTURE_TABLE_PATH)
    jobs = {job["name"]: job for job in table["jobs"]}
    box = table["machines"]["ned-box"]
    box_lines = {name: installer.cron_line(box, jobs[name], jobs[name]["on"]["ned-box"])
                 for name in jobs}
    BOX_MIRROR, BOX_DAILY = (box_lines["transcript-mirror-to-log-store"],
                             box_lines["daily-full-test-run-of-main"])
    BOX_ALONE = box_lines["runs-on-ned-box-alone"]
    TWO_JOBS = ["--job", "transcript-mirror-to-log-store", "--job", "daily-full-test-run-of-main"]
    as_installed_today = f"{NED_BOX_FOREIGN_COMMENT}\n{BOX_MIRROR}\n{BOX_DAILY}\n".encode("utf-8")

    # --- cron: check and install change nothing that already matches -----
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--check"] + TWO_JOBS, NED_BOX, stub)
    check("--check on a crontab holding the table's lines says each job matches, exits 0 and "
          "writes nothing",
          exit_code == 0 and printed.count("matches: ") == 2 and "DIFFERS" not in printed
          and stub.crontab_writes == [] and stub.commands == [["crontab", "-l"]],
          (exit_code, printed, errors, stub.commands))
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("--install on a crontab holding the table's lines leaves it alone: the crontab is "
          "not written at all",
          exit_code == 0 and printed.count("unchanged: ") == 2 and stub.crontab_writes == []
          and stub.commands == [["crontab", "-l"]],
          (exit_code, printed, errors, stub.commands))

    # --- cron: a user with no crontab ------------------------------------
    stub = MachineStub(crontab=None)
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("--install for a user with no crontab writes the table's lines in one crontab call",
          exit_code == 0 and stub.crontab_writes == [f"{BOX_MIRROR}\n{BOX_DAILY}\n".encode()]
          and printed.count("installed: ") == 2
          and stub.commands == [["crontab", "-l"], ["crontab", "-"], ["crontab", "-l"]],
          (exit_code, printed, errors, stub.crontab_writes))
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("and a second --install changes nothing",
          exit_code == 0 and len(stub.crontab_writes) == 1 and printed.count("unchanged: ") == 2,
          (exit_code, printed, stub.crontab_writes))

    # --- cron: only the selected jobs' lines change -----------------------
    foreign_line = "15 2 * * * /usr/local/bin/something-else --nightly"
    differing_daily = BOX_DAILY.replace("30 3 * * *", "0 4 * * *")
    stub = MachineStub(crontab=(
        f"{NED_BOX_FOREIGN_COMMENT}\n{differing_daily}\n{foreign_line}\n").encode())
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("a differing line for a job's program is replaced where it stood, the missing job's "
          "line is added, and every other line, the comment included, goes back byte for byte",
          exit_code == 0 and stub.crontab_writes == [(
              f"{NED_BOX_FOREIGN_COMMENT}\n{BOX_DAILY}\n{foreign_line}\n{BOX_MIRROR}\n").encode()],
          (exit_code, stub.crontab_writes))
    check("and the line that was removed is printed",
          f"replaced: daily-full-test-run-of-main" in printed
          and f"  the line removed: {differing_daily}\n" in printed
          and "installed: transcript-mirror-to-log-store" in printed, printed)

    not_utf8 = b"# a comment that is not UTF-8: \xff\xfe\nMAILTO=\"\"\n" + foreign_line.encode()
    stub = MachineStub(crontab=not_utf8)        # and no newline after the last line
    exit_code, printed, errors = run_main(
        ["--install", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("bytes that are not UTF-8, a variable assignment and a last line with no newline "
          "all go back as they were, before the added line",
          exit_code == 0 and stub.crontab_writes == [not_utf8 + b"\n" + BOX_DAILY.encode() + b"\n"],
          (exit_code, stub.crontab_writes))
    stub = MachineStub(crontab=not_utf8 + b"\n" + BOX_DAILY.encode())
    exit_code, printed, errors = run_main(
        ["--install", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("a crontab that needs no change is not rewritten to add its missing last newline",
          exit_code == 0 and stub.crontab_writes == [], stub.crontab_writes)

    stub = MachineStub(crontab=f"{BOX_DAILY}\n{foreign_line}\n{BOX_DAILY}\n".encode())
    exit_code, printed, errors = run_main(
        ["--install", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("two lines for one job become one, where the first stood",
          exit_code == 0 and stub.crontab_writes == [f"{BOX_DAILY}\n{foreign_line}\n".encode()]
          and printed.count("  the line removed: ") == 2, (exit_code, printed, stub.crontab_writes))

    commented_out = f"# {BOX_DAILY}"
    other_files = "".join(
        BOX_DAILY.replace("daily-full-test-run-of-main.py", other_file_name) + "\n"
        for other_file_name in ("daily-full-test-run-of-main-test.py",
                                "daily-full-test-run-of-main.py.disabled",
                                "earlier-daily-full-test-run-of-main.py"))
    stub = MachineStub(crontab=f"{commented_out}\n{other_files}".encode())
    exit_code, printed, errors = run_main(
        ["--install", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("a commented-out line, and lines running other files whose names only begin or end "
          "with the program's, are not the job's line: all stay and the job's line is added",
          exit_code == 0 and stub.crontab_writes == [
              f"{commented_out}\n{other_files}{BOX_DAILY}\n".encode()],
          (exit_code, stub.crontab_writes))

    moved = BOX_DAILY.replace("/scripts/daily-full-test-run-of-main.py",
                              "/an-earlier-directory/daily-full-test-run-of-main.py")
    stub = MachineStub(crontab=f"{moved}\n".encode())
    exit_code, printed, errors = run_main(
        ["--install", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("a line running the program from the directory it has since left is replaced, not "
          "left beside the new line: a job's line is known by its program's file name",
          exit_code == 0 and stub.crontab_writes == [f"{BOX_DAILY}\n".encode()],
          (exit_code, stub.crontab_writes))

    # --- cron: a crontab that cannot be read or written -------------------
    stub = MachineStub(crontab=as_installed_today)
    stub.crontab_list_failure = (1, b"crontab: must be privileged to use -u\n")
    for mode in (["--install"], ["--check"], ["--remove", "--job", "daily-full-test-run-of-main"]):
        exit_code, printed, errors = run_main(mode, NED_BOX, stub)
        check(f"{mode[0]}: a `crontab -l` that fails is not taken for an empty crontab — "
              "not run, exit 2, nothing written",
              exit_code == 2 and stub.crontab_writes == []
              and "not run — `crontab -l` exited 1: crontab: must be privileged" in errors
              and "Run this again after `crontab -l` prints this machine's crontab." in errors,
              (exit_code, printed, errors, stub.crontab_writes))
    stub = MachineStub(crontab=None)
    stub.exit_codes["crontab-write"] = 1
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("a `crontab` write that fails is FAILED with its exit code, exit 1, and no job is "
          "reported installed",
          exit_code == 1 and "FAILED: `crontab -` exited 1; no cron line was changed." in errors
          and "installed:" not in printed and stub.crontab is None,
          (exit_code, printed, errors))
    stub = MachineStub(crontab=f"{NED_BOX_FOREIGN_COMMENT}\n".encode())
    stub.crontab_write_installs_empty_crontab = True
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX, stub)
    check("a `crontab -` write that exits 0 but reads back empty is FAILED, exit 1, naming the "
          "line counts, and no job is reported installed",
          exit_code == 1
          and "FAILED: `crontab -` exited 0, but `crontab -l` reads back 0 line(s) where 3 were "
              "written" in errors
          and "Run `crontab -l` to see what the crontab now holds" in errors
          and "installed:" not in printed and "replaced:" not in printed,
          (exit_code, printed, errors))
    stub = MachineStub(crontab=as_installed_today)
    stub.crontab_write_installs_empty_crontab = True
    exit_code, printed, errors = run_main(["--remove", "--job", "daily-full-test-run-of-main"],
                                          NED_BOX, stub)
    check("--remove: a write that exits 0 but reads back different is FAILED, exit 1, and no "
          "line is reported removed",
          exit_code == 1 and "FAILED: `crontab -` exited 0, but `crontab -l` reads back" in errors
          and "removed:" not in printed, (exit_code, printed, errors))
    stub = MachineStub(crontab=None)
    real_stub_call = MachineStub.__call__
    def unreadable_after_write(command, stdout=None, stderr=None, input=None):
        if command == ["crontab", "-l"] and stub.crontab_writes:
            stub.crontab_list_failure = (1, b"crontab: tmp/tmp.123: Permission denied\n")
        return real_stub_call(stub, command, stdout=stdout, stderr=stderr, input=input)
    exit_code, printed, errors = run_main(["--install"] + TWO_JOBS, NED_BOX,
                                          unreadable_after_write)
    check("a write that exits 0 but cannot be read back is FAILED, exit 1, quoting why, and no "
          "job is reported installed",
          exit_code == 1
          and "FAILED: `crontab -` exited 0, but the crontab could not be read back to confirm "
              "the write: " in errors and "Permission denied" in errors
          and "installed:" not in printed, (exit_code, printed, errors))

    # --- cron: check ------------------------------------------------------
    stub = MachineStub(crontab=f"{NED_BOX_FOREIGN_COMMENT}\n{differing_daily}\n".encode())
    exit_code, printed, errors = run_main(["--check"] + TWO_JOBS, NED_BOX, stub)
    check("--check names a missing line and a differing line, exits 1 and writes nothing",
          exit_code == 1 and stub.crontab_writes == []
          and "DIFFERS: transcript-mirror-to-log-store — the crontab holds no line for "
              "transcript-mirror-to-log-store.py" in printed
          and f"DIFFERS: daily-full-test-run-of-main — the crontab holds {differing_daily}, "
              f"not the table's line: {BOX_DAILY}.\n" in printed,
          (exit_code, printed, errors))
    check("and tells the agent what to do in each of the two cases, one instruction a line",
          printed.splitlines()[-2].startswith("When the table says what this machine should run, "
                                               "run `")
          and printed.splitlines()[-2].endswith(" --install` on this machine.")
          and printed.splitlines()[-1] == (
              "When this machine is right and the table is wrong, change "
              f"{FIXTURE_TABLE_PATH} through a pull request."), printed)
    exit_code, printed, errors = run_main(
        ["--check", "--job", "runs-on-ned-box-alone"], NED_BOX, MachineStub(crontab=None))
    check("--check for a user with no crontab reports the job's line missing, exit 1",
          exit_code == 1 and "DIFFERS: runs-on-ned-box-alone" in printed, (exit_code, printed))

    # --- cron: remove -----------------------------------------------------
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(
        ["--remove", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("--remove takes the named job's line out and leaves every other line",
          exit_code == 0 and stub.crontab_writes == [
              f"{NED_BOX_FOREIGN_COMMENT}\n{BOX_MIRROR}\n".encode()]
          and f"removed: daily-full-test-run-of-main — the line removed from the crontab: "
              f"{BOX_DAILY}" in printed, (exit_code, printed, stub.crontab_writes))
    exit_code, printed, errors = run_main(
        ["--remove", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("removing a job the crontab does not hold says so and writes nothing",
          exit_code == 0 and len(stub.crontab_writes) == 1
          and "absent: daily-full-test-run-of-main" in printed, (exit_code, printed))
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--remove"], NED_BOX, stub)
    check("--remove without --job is refused: nothing removes every job at once",
          exit_code == 2 and "--remove needs --job" in errors and stub.commands == [],
          (exit_code, errors, stub.commands))

    # --- what is refused before anything changes --------------------------
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--install", "--job", "no-such-job"], NED_BOX, stub)
    check("a --job the table lacks is refused, naming the table's jobs",
          exit_code == 2 and "has no job `no-such-job`" in errors
          and "Pass --job with one of: transcript-mirror-to-log-store, "
              "daily-full-test-run-of-main, runs-on-ned-box-alone." in errors
          and stub.commands == [], (exit_code, errors))
    exit_code, printed, errors = run_main(
        ["--install", "--job", "runs-on-ned-box-alone"], MAC, stub)
    check("a --job the table places on another machine is refused on this one",
          exit_code == 2 and "places job `runs-on-ned-box-alone` on ned-box, not on this "
                             "machine, `mac`" in errors and stub.commands == [],
          (exit_code, errors))
    exit_code, printed, errors = run_main(["--print"], ("linux", root / "somebody-else"), stub)
    check("a machine the table does not name is refused: the table's paths are another "
          "machine's",
          exit_code == 2 and "names no machine with platform `linux` and home directory" in errors
          and "Add this machine to the table through a pull request" in errors
          and stub.commands == [], (exit_code, errors))
    exit_code, printed, errors = run_main(["--print"], ("linux", root / "mac-home"), stub)
    check("the Mac's home directory on another platform is not the Mac",
          exit_code == 2 and "names no machine" in errors, (exit_code, errors))
    alone_program = root / "ned-box-home" / "Projects" / "nedschorus" / "scripts" \
        / "runs-on-ned-box-alone.py"
    alone_program.unlink()
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--install"], NED_BOX, stub)
    check("a job whose program is not a file in the clone stops the whole install before "
          "anything is read or written",
          exit_code == 2 and f"runs {alone_program}, which is not a file on this machine" in errors
          and "to current main, then run this again." in errors and stub.commands == [],
          (exit_code, errors, stub.commands))
    check("and says what to do when main has no such program either",
          errors.splitlines()[-1] == ("When main has no scripts/runs-on-ned-box-alone.py either, "
                                      "correct the table through a pull request, then run this "
                                      "again."), errors)
    exit_code, printed, errors = run_main(["--check", "--job", "runs-on-ned-box-alone"], NED_BOX,
                                          MachineStub(crontab=f"{BOX_ALONE}\n".encode()))
    check("and --check reports the missing program as a difference",
          exit_code == 1 and f"its program {alone_program} is not a file" in printed,
          (exit_code, printed))
    alone_program.write_text("# program\n")
    exit_code, printed, errors = run_main(["--install", "--print"], NED_BOX, stub)
    check("two modes at once are refused", exit_code == 2, (exit_code, errors))
    exit_code, printed, errors = run_main([], NED_BOX, stub)
    check("no mode is refused: nothing is installed by default", exit_code == 2,
          (exit_code, errors))

    # --- the table's defects ----------------------------------------------
    def table_defect(case_name, change, expected):
        defective = json.loads(FIXTURE_TABLE_PATH.read_text(encoding="utf-8"))
        change(defective)
        defective_path = root / "defective-table.json"
        defective_path.write_text(json.dumps(defective), encoding="utf-8")
        stub = MachineStub(crontab=as_installed_today)
        exit_code, printed, errors = run_main(["--install"], NED_BOX, stub, defective_path)
        check(case_name,
              exit_code == 2 and expected in errors and stub.commands == []
              and "Correct the table through a pull request, then run this again." in errors,
              (exit_code, errors, stub.commands))

    def systemd_scheduler(defective):
        defective["jobs"][0]["on"]["ned-box"]["scheduler"] = "systemd-user-unit"
    table_defect("a scheduler this program does not know is refused, naming the ones it does",
                 systemd_scheduler, "the scheduler `systemd-user-unit`; this program knows "
                                    "cron, launchd")

    def claims_the_label(defective):
        defective["jobs"][1]["on"]["mac"]["launchd_keys"]["Label"] = "another.label"
    table_defect("launchd_keys naming a key this program writes is refused",
                 claims_the_label, "name a key this program writes")

    def same_program_file(defective):
        defective["jobs"][2]["program"] = "elsewhere/daily-full-test-run-of-main.py"
    table_defect("two jobs with one program file name are refused: each would take the "
                 "other's cron line for its own",
                 same_program_file, "its program file `daily-full-test-run-of-main.py` twice")

    def arguments_not_a_list(defective):
        defective["jobs"][0]["arguments"] = "--failures-only"
    table_defect("a job field that is there with the wrong type is called wrongly typed, not "
                 "missing", arguments_not_a_list,
                 "gives job `transcript-mirror-to-log-store` a missing or wrongly typed "
                 "`program`, `arguments`, `output` or `on`")

    def four_fields(defective):
        defective["jobs"][0]["on"]["ned-box"]["schedule"] = "* * * *"
    table_defect("a cron schedule without five fields is refused", four_fields,
                 "no five-field `schedule`")

    def unknown_machine(defective):
        defective["jobs"][0]["on"]["a-third-machine"] = {"scheduler": "cron",
                                                         "schedule": "* * * * *"}
    table_defect("a job placed on a machine the table lacks is refused", unknown_machine,
                 "on `a-third-machine`, which `machines` lacks")
    not_json = root / "not-json.json"
    not_json.write_text("{ not JSON", encoding="utf-8")
    exit_code, printed, errors = run_main(["--print"], NED_BOX, None, not_json)
    check("a table that is not JSON is refused", exit_code == 2 and "is not JSON" in errors,
          (exit_code, errors))
    exit_code, printed, errors = run_main(["--print"], NED_BOX, None, root / "no-table.json")
    check("a table that is not there is refused",
          exit_code == 2 and "could not be read" in errors, (exit_code, errors))

    # --- launchd: the Mac --------------------------------------------------
    mac_machine = table["machines"]["mac"]
    daily_job = jobs["daily-full-test-run-of-main"]
    daily_placement = daily_job["on"]["mac"]
    expected_plist = installer.launch_agent_plist(mac_machine, daily_job, daily_placement)
    LABEL = "com.nedschorus.daily-full-test-run-of-main"
    TARGET = f"{DOMAIN}/{LABEL}"
    plist_path = LAUNCH_AGENTS / f"{LABEL}.plist"
    mac_mirror_line = installer.cron_line(
        mac_machine, jobs["transcript-mirror-to-log-store"],
        jobs["transcript-mirror-to-log-store"]["on"]["mac"])
    DAILY = ["--job", "daily-full-test-run-of-main"]

    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode())
    exit_code, printed, errors = run_main(["--check"], MAC, stub)
    check("--check on the Mac before the daily run is installed: the mirror matches, the "
          "launchd job is not there and not loaded, exit 1, nothing written",
          exit_code == 1 and "matches: transcript-mirror-to-log-store — cron." in printed
          and f"DIFFERS: daily-full-test-run-of-main — {plist_path} is not there." in printed
          and f"DIFFERS: daily-full-test-run-of-main — launchd has no job {LABEL} loaded in "
              f"{DOMAIN}." in printed
          and not LAUNCH_AGENTS.exists() and stub.crontab_writes == []
          and stub.launchctl_verbs() == ["print"],
          (exit_code, printed, errors, stub.commands))

    before = len(stub.commands)
    exit_code, printed, errors = run_main(["--install"], MAC, stub)
    check("--install on the Mac leaves the mirror's cron line alone and writes the daily "
          "run's plist as the table says",
          exit_code == 0 and stub.crontab_writes == []
          and "unchanged: transcript-mirror-to-log-store" in printed
          and plistlib.loads(plist_path.read_bytes()) == expected_plist
          and f"installed: daily-full-test-run-of-main — wrote {plist_path} and loaded {LABEL} "
              f"into {DOMAIN}." in printed, (exit_code, printed, errors))
    check("in this order: read the crontab, lint the plist, boot out the label, bootstrap, "
          "confirm that launchd has the job",
          stub.commands[before:] == [
              ["crontab", "-l"], ["plutil", "-lint", str(plist_path)],
              ["launchctl", "bootout", TARGET],
              ["launchctl", "bootstrap", DOMAIN, str(plist_path)],
              ["launchctl", "print", TARGET]], stub.commands)
    check("the plist: the interpreter and program of the table, the Mac's launchd PATH, the "
          "03:30 calendar interval, and both streams to the job's output file",
          expected_plist["ProgramArguments"]
          == ["/opt/homebrew/bin/python3",
              f"{root}/mac-home/Projects/nedschorus/scripts/daily-full-test-run-of-main.py"]
          and expected_plist["EnvironmentVariables"] == {
              "PATH": f"{root}/mac-home/.local/bin:/usr/bin:/bin"}
          and expected_plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 30}
          and expected_plist["StandardOutPath"] == expected_plist["StandardErrorPath"]
          == f"{root}/mac-home/.claude/daily-full-test-run-of-main.log"
          and "RunAtLoad" not in expected_plist, expected_plist)

    before = len(stub.commands)
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("a second --install finds the plist as the table says and the job loaded, and "
          "does nothing more than ask",
          exit_code == 0 and "unchanged: daily-full-test-run-of-main" in printed
          and stub.commands[before:] == [["launchctl", "print", TARGET]],
          (exit_code, printed, stub.commands[before:]))
    exit_code, printed, errors = run_main(["--check"], MAC, stub)
    check("and --check then says both jobs match, exit 0",
          exit_code == 0 and printed.count("matches: ") == 2
          and "matches: daily-full-test-run-of-main — launchd." in printed, (exit_code, printed))

    stub.loaded.clear()
    before = len(stub.commands)
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("a plist that matches with its job not loaded is loaded again",
          exit_code == 0 and "installed: daily-full-test-run-of-main" in printed
          and [command[1] for command in stub.commands[before:]]
          == ["print", "-lint", "bootout", "bootstrap", "print"], stub.commands[before:])
    plist_path.write_bytes(plistlib.dumps(dict(expected_plist, StartCalendarInterval={
        "Hour": 4, "Minute": 0}), sort_keys=False))
    exit_code, printed, errors = run_main(["--check"] + DAILY, MAC, stub)
    check("--check names a plist that does not say what the table says, and not as a missing "
          "marker line",
          exit_code == 1 and f"{plist_path} does not say what the table says" in printed
          and "lacks the line" not in printed, (exit_code, printed))
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("and --install writes the table's plist over it and loads it again",
          exit_code == 0 and plistlib.loads(plist_path.read_bytes()) == expected_plist
          and stub.launchctl_verbs()[-3:] == ["bootout", "bootstrap", "print"],
          (exit_code, printed, stub.commands[-5:]))
    plist_path.write_bytes(b"this is not a plist")
    exit_code, printed, errors = run_main(["--check"] + DAILY, MAC, stub)
    check("a file that is not a plist at all is a difference, not a crash",
          exit_code == 1 and "does not say what the table says" in printed, (exit_code, printed))
    plist_path.unlink()

    # --- launchd: --start-once ---------------------------------------------
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode())
    exit_code, printed, errors = run_main(["--install", "--start-once"] + DAILY, MAC, stub)
    check("--start-once asks launchd to run the job once, after it is installed",
          exit_code == 0 and stub.commands[-1] == ["launchctl", "kickstart", TARGET]
          and stub.launchctl_verbs() == ["bootout", "bootstrap", "print", "kickstart"]
          and f"started: daily-full-test-run-of-main — launchd is running {LABEL} once, now"
              in printed, (exit_code, printed, stub.commands))
    exit_code, printed, errors = run_main(["--install", "--start-once"] + DAILY, MAC, stub)
    check("and starts a job it found already installed as the table says",
          exit_code == 0 and "unchanged: daily-full-test-run-of-main" in printed
          and stub.commands[-2:] == [["launchctl", "print", TARGET],
                                     ["launchctl", "kickstart", TARGET]],
          (exit_code, printed, stub.commands[-3:]))
    stub.exit_codes["kickstart"] = 3
    exit_code, printed, errors = run_main(["--install", "--start-once"] + DAILY, MAC, stub)
    check("a kickstart that fails is FAILED with its exit code, exit 1",
          exit_code == 1 and f"`launchctl kickstart {TARGET}` exited 3; the job was not started"
                             in errors and "started:" not in printed, (exit_code, printed, errors))
    stub = MachineStub(crontab=as_installed_today)
    exit_code, printed, errors = run_main(["--install", "--start-once"] + TWO_JOBS, NED_BOX, stub)
    check("--start-once where no selected job is a launchd job is refused before anything "
          "is read",
          exit_code == 2 and "no selected job of this machine is one" in errors
          and "Run this again without --start-once." in errors and stub.commands == [],
          (exit_code, errors, stub.commands))
    exit_code, printed, errors = run_main(["--check", "--start-once"], MAC, stub)
    check("--start-once without --install is refused",
          exit_code == 2 and "--start-once goes with --install" in errors, (exit_code, errors))

    # --- launchd: each step that can fail ----------------------------------
    plist_path.unlink()
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode())
    stub.exit_codes["bootstrap"] = 5
    exit_code, printed, errors = run_main(["--install", "--start-once"] + DAILY, MAC, stub)
    check("a bootstrap that fails is FAILED with its exit code, exit 1, the plist left "
          "written and the job not started",
          exit_code == 1 and f"`launchctl bootstrap {DOMAIN} {plist_path}` exited 5" in errors
          and plist_path.is_file() and "kickstart" not in stub.launchctl_verbs()
          and "installed:" not in printed, (exit_code, printed, errors, stub.commands))
    check("with the instruction for an ssh session, and the one for every other cause",
          errors.splitlines()[-2] == ("When this was run over ssh, ask the user to run it again "
                                      "from a terminal in this Mac's interactive login session.")
          and errors.splitlines()[-1] == ("Otherwise read what launchctl printed above, and run "
                                          "this again after that cause is removed."), errors)
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode())
    stub.exit_codes["lint"] = 1
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("a plist that fails plutil's lint is FAILED, exit 1, and is not bootstrapped",
          exit_code == 1 and f"`plutil -lint {plist_path}` exited 1" in errors
          and "bootstrap" not in stub.launchctl_verbs(), (exit_code, errors, stub.commands))
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode())
    stub.bootstrap_loads_the_job = False
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("a bootstrap that exits 0 with the job not found afterwards is FAILED, exit 1",
          exit_code == 1 and f"`launchctl print {TARGET}` does not find the job" in errors
          and "installed:" not in printed, (exit_code, printed, errors))
    stub = MachineStub(crontab=None)
    stub.exit_codes["crontab-write"] = 1
    exit_code, printed, errors = run_main(["--install"], MAC, stub)
    check("a failed crontab write does not stop the launchd job from being installed, and "
          "the run still exits 1",
          exit_code == 1 and "FAILED: `crontab -` exited 1; no cron line was changed." in errors
          and "installed: daily-full-test-run-of-main" in printed, (exit_code, printed, errors))

    # --- launchd: remove ----------------------------------------------------
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode(), loaded=[TARGET])
    exit_code, printed, errors = run_main(["--remove"] + DAILY, MAC, stub)
    check("--remove boots the label out and deletes its plist, and leaves the crontab alone",
          exit_code == 0 and stub.commands == [["launchctl", "bootout", TARGET]]
          and not plist_path.exists() and stub.loaded == set()
          and f"removed: daily-full-test-run-of-main — deleted {plist_path}.\n" in printed, (exit_code, printed, stub.commands))
    exit_code, printed, errors = run_main(["--remove"] + DAILY, MAC, stub)
    check("removing a launchd job with no plist still boots it out and says there was none",
          exit_code == 0
          and f"absent: daily-full-test-run-of-main — there was no {plist_path}.\n" in printed,
          (exit_code, printed))
    plist_path.write_bytes(b"a plist")
    stub = MachineStub(loaded=[TARGET])
    stub.exit_codes["bootout"] = 5
    exit_code, printed, errors = run_main(["--remove"] + DAILY, MAC, stub)
    check("a bootout that fails with the job still loaded is FAILED, exit 1, and the plist is "
          "kept",
          exit_code == 1 and plist_path.is_file() and "removed:" not in printed
          and errors.endswith(
              "Boot-out failed: 5: Input/output error\n"
              f"FAILED: {LABEL} — launchctl bootout exited 5, so the job may still be loaded; "
              f"{plist_path} was kept.\n"
              "Read what launchctl printed above, and run this again after that cause is "
              "removed.\n"), (exit_code, printed, errors))
    stub = MachineStub()
    stub.exit_codes["bootout"], stub.exit_codes["print"] = 5, 1
    stub.loaded.add(TARGET)
    exit_code, printed, errors = run_main(["--remove"] + DAILY, MAC, stub)
    check("a bootout that fails while launchctl print fails with other than service-not-found "
          "is FAILED, exit 1, and the plist is kept",
          exit_code == 1 and plist_path.is_file() and "removed:" not in printed
          and f"FAILED: {LABEL} — launchctl bootout exited 5" in errors, (exit_code, errors))
    plist_path.unlink()

    # --- jobs the table does not name ----------------------------------------
    box_clone = table["machines"]["ned-box"]["clone"]
    retired_line = f"0 5 * * * /usr/bin/python3 {box_clone}/scripts/a-retired-job.py >> /tmp/x 2>&1"
    commented_retired = f"# {retired_line}"
    stub = MachineStub(crontab=(f"{NED_BOX_FOREIGN_COMMENT}\n{commented_retired}\n{BOX_MIRROR}\n"
                                f"{BOX_DAILY}\n{BOX_ALONE}\n{retired_line}\n{foreign_line}\n").encode())
    exit_code, printed, errors = run_main(["--check"], NED_BOX, stub)
    check("--check reports a cron line that runs a program from the clone and is no job's "
          "line of the table, exit 1, and writes nothing",
          exit_code == 1 and stub.crontab_writes == [] and printed.count("matches: ") == 3
          and f"NOT IN THE TABLE: the crontab line {retired_line} — no job of the table names "
              f"it for this machine.\n" in printed
          and printed.count("NOT IN THE TABLE: ") == 1 and "DIFFERS" not in printed,
          (exit_code, printed, errors))
    check("and not a commented-out line, a line running a program outside the clone, or "
          "another user's comment",
          commented_retired not in printed and foreign_line not in printed
          and "nedsmessenger" not in printed, printed)
    check("and says what to do with a job NOT IN THE TABLE, one instruction a line",
          printed.splitlines()[-4] == (
              f"When every job NOT IN THE TABLE is retired, run `{SCRIPT_PATH.resolve()} "
              "--remove-not-in-table` on this machine; it removes all of them.")
          and printed.splitlines()[-3] == (
              "When only some are retired, first add the others' entries to "
              f"{FIXTURE_TABLE_PATH} through a pull request.")
          and printed.splitlines()[-2] == (
              "When a job NOT IN THE TABLE should still run, add its entry to "
              f"{FIXTURE_TABLE_PATH} through a pull request.")
          and printed.splitlines()[-1] == (
              "To learn whether a job was retired on purpose, run "
              f"`git log -p -- {FIXTURE_TABLE_PATH}` in the clone."), printed)
    exit_code, printed, errors = run_main(["--check"] + TWO_JOBS, NED_BOX, stub)
    check("--check limited by --job does not look for jobs the table does not name",
          exit_code == 0 and "NOT IN THE TABLE" not in printed, (exit_code, printed))

    exit_code, printed, errors = run_main(["--remove-not-in-table"], NED_BOX, stub)
    check("--remove-not-in-table takes out exactly that line, in one crontab write, and "
          "leaves every other line",
          exit_code == 0 and stub.crontab_writes == [(
              f"{NED_BOX_FOREIGN_COMMENT}\n{commented_retired}\n{BOX_MIRROR}\n{BOX_DAILY}\n"
              f"{BOX_ALONE}\n{foreign_line}\n").encode()]
          and f"removed: not in the table — the line removed from the crontab: "
              f"{retired_line}\n" in printed, (exit_code, printed, stub.crontab_writes))
    exit_code, printed, errors = run_main(["--remove-not-in-table"], NED_BOX, stub)
    check("and a second run finds nothing, says so and writes nothing",
          exit_code == 0 and len(stub.crontab_writes) == 1
          and printed == ("absent: no crontab line runs a program from the clone, and no "
                          "plist this installer wrote, outside the table.\n"),
          (exit_code, printed))
    exit_code, printed, errors = run_main(["--check"], NED_BOX, stub)
    check("and --check then finds every job matching and nothing outside the table, exit 0",
          exit_code == 0 and "NOT IN THE TABLE" not in printed, (exit_code, printed))
    exit_code, printed, errors = run_main(
        ["--remove-not-in-table", "--job", "daily-full-test-run-of-main"], NED_BOX, stub)
    check("--remove-not-in-table with --job is refused before anything is read",
          exit_code == 2 and "--remove-not-in-table takes no --job: it removes every job "
                             "--check reports NOT IN THE TABLE" in errors,
          (exit_code, errors))
    stub = MachineStub(crontab=None)
    stub.exit_codes["crontab-write"] = 1
    stub.crontab = f"{retired_line}\n".encode()
    exit_code, printed, errors = run_main(["--remove-not-in-table"], NED_BOX, stub)
    check("a failed crontab write in --remove-not-in-table is FAILED, exit 1, nothing reported "
          "removed", exit_code == 1 and "FAILED: `crontab -` exited 1" in errors
          and "removed:" not in printed, (exit_code, printed, errors))

    # Which crontab lines run a program from the clone: the program is the
    # command's first word, or an interpreter's first argument; a line that
    # sets a variable, or only reads or writes a file in the clone, runs no
    # program from it, and a line that gives an interpreter or env an option
    # is not read at all, since the option may take the next word.
    path_setting = f"PATH={box_clone}/scripts:/usr/bin:/bin"
    reads_the_clone = f"0 4 * * * /usr/bin/tar czf /tmp/backup.tgz {box_clone}/data"
    writes_into_the_clone = f"0 6 * * * /usr/local/bin/other-tool >> {box_clone}/other.log 2>&1"
    runs_directly = f"0 8 * * * {box_clone}/scripts/a-retired-shell-job.sh --quiet"
    runs_through_env = (f"0 7 * * * /usr/bin/env HOME=/tmp /usr/bin/python3 "
                        f"{box_clone}/scripts/a-retired-env-job.py")
    env_option_takes_a_clone_directory = f"0 9 * * * /usr/bin/env -C {box_clone}/data /usr/bin/true"
    interpreter_option = f"0 10 * * * /usr/bin/python3 -u {box_clone}/scripts/a-retired-job.py"
    runs_at_reboot = f"@reboot /usr/bin/python3 {box_clone}/scripts/a-retired-reboot-job.py"
    check("the program a crontab line runs is its first word, or an interpreter's first "
          "argument, and nothing for a line that sets a variable or gives an interpreter or "
          "env an option",
          [installer.program_a_cron_line_runs(line) for line in (
              path_setting, reads_the_clone, writes_into_the_clone, runs_directly,
              runs_through_env, runs_at_reboot, BOX_MIRROR, "", "# 0 4 * * * x",
              env_option_takes_a_clone_directory, interpreter_option)]
          == [None, "/usr/bin/tar", "/usr/local/bin/other-tool",
              f"{box_clone}/scripts/a-retired-shell-job.sh",
              f"{box_clone}/scripts/a-retired-env-job.py",
              f"{box_clone}/scripts/a-retired-reboot-job.py",
              f"{box_clone}/scripts/transcript-mirror-to-log-store.py", None, None, None, None])
    not_runs = [path_setting, reads_the_clone, writes_into_the_clone,
                env_option_takes_a_clone_directory, interpreter_option]
    runs = [runs_directly, runs_through_env, runs_at_reboot]
    stub = MachineStub(crontab="".join(
        line + "\n" for line in [path_setting, BOX_MIRROR, BOX_DAILY, BOX_ALONE]
        + not_runs + runs).encode())
    exit_code, printed, errors = run_main(["--check"], NED_BOX, stub)
    check("--check reports a line that runs a program from the clone, directly, through env "
          "or at reboot, and not a line that sets PATH to the clone, only reads or writes "
          "a file there, or gives env or an interpreter an option such as `env -C <clone>/data`",
          exit_code == 1 and printed.count("NOT IN THE TABLE: ") == 3
          and all(f"NOT IN THE TABLE: the crontab line {line} — " in printed for line in runs)
          and not any(line in printed for line in not_runs), (exit_code, printed))
    exit_code, printed, errors = run_main(["--remove-not-in-table"], NED_BOX, stub)
    check("--remove-not-in-table takes out only those three, and keeps the PATH line, the "
          "lines that only touch a file in the clone and the lines with an option",
          exit_code == 0 and stub.crontab_writes == ["".join(
              line + "\n" for line in [path_setting, BOX_MIRROR, BOX_DAILY, BOX_ALONE]
              + not_runs).encode()], (exit_code, printed, stub.crontab_writes))

    # A retired line that runs a program file of the same name as a cron job
    # of the table is found as that job's line, the way an install finds it:
    # --check reports it as that job's DIFFERS, and --install replaces it.
    same_file_other_arguments = BOX_DAILY.replace("30 3 * * *", "0 2 * * *").replace(
        "daily-full-test-run-of-main.py", "daily-full-test-run-of-main.py --a-retired-argument")
    stub = MachineStub(crontab=(f"{BOX_MIRROR}\n{BOX_DAILY}\n{BOX_ALONE}\n"
                                f"{same_file_other_arguments}\n").encode())
    exit_code, printed, errors = run_main(["--check"], NED_BOX, stub)
    check("a retired line running a table job's program file is that job's DIFFERS, not NOT "
          "IN THE TABLE",
          exit_code == 1 and "NOT IN THE TABLE" not in printed
          and f"DIFFERS: daily-full-test-run-of-main — the crontab holds {BOX_DAILY}; "
              f"{same_file_other_arguments}, not the table's line" in printed,
          (exit_code, printed))
    exit_code, printed, errors = run_main(["--install"], NED_BOX, stub)
    check("and --install replaces both with the table's one line",
          exit_code == 0 and stub.crontab == f"{BOX_MIRROR}\n{BOX_DAILY}\n{BOX_ALONE}\n".encode(),
          (exit_code, printed, stub.crontab))

    mac_clone = table["machines"]["mac"]["clone"]
    stray_daily = installer.cron_line(mac_machine, daily_job, {"schedule": "30 3 * * *"})
    stub = MachineStub(crontab=f"{mac_mirror_line}\n{stray_daily}\n".encode())
    exit_code, printed, errors = run_main(["--check"], MAC, stub)
    check("a cron line for a job the table gives this machine as a launchd job is NOT IN THE "
          "TABLE: the table names no cron line for it here",
          exit_code == 1 and f"NOT IN THE TABLE: the crontab line {stray_daily}" in printed,
          (exit_code, printed))

    LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    retired_plist = dict(expected_plist, Label="com.nedschorus.a-retired-job")
    retired_plist_path = LAUNCH_AGENTS / "com.nedschorus.a-retired-job.plist"
    retired_plist_path.write_bytes(plistlib.dumps(retired_plist, sort_keys=False).replace(
        b"<plist ", installer.PLIST_WRITTEN_BY_THIS_PROGRAM + b"\n<plist ", 1))
    other_installer_path = LAUNCH_AGENTS / "com.nedschorus.restart-live-seats-at-login.plist"
    other_installer_path.write_bytes(plistlib.dumps(dict(
        expected_plist, Label="com.nedschorus.restart-live-seats-at-login", RunAtLoad=True)))
    unrelated_path = LAUNCH_AGENTS / "com.example.updater.plist"
    unrelated_path.write_bytes(plistlib.dumps({"Label": "com.example.updater"}))
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode(),
                       loaded=[f"{DOMAIN}/com.nedschorus.a-retired-job"])
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    exit_code, printed, errors = run_main(["--check"], MAC, stub)
    check("--check reports a plist this program wrote whose label the table does not name, "
          "exit 1",
          exit_code == 1 and f"NOT IN THE TABLE: {retired_plist_path}, label "
                             f"com.nedschorus.a-retired-job — no job of the table names it for "
                             f"this machine.\n" in printed
          and printed.count("NOT IN THE TABLE: ") == 1 and printed.count("matches: ") == 2,
          (exit_code, printed))
    check("and not a plist of the same shape and label prefix that another program wrote, "
          "or anyone else's",
          str(other_installer_path) not in printed and str(unrelated_path) not in printed, printed)
    exit_code, printed, errors = run_main(["--remove-not-in-table"], MAC, stub)
    check("--remove-not-in-table boots that label out and deletes its plist, and leaves the "
          "table's job, the other program's plist and the crontab alone",
          exit_code == 0 and not retired_plist_path.exists() and plist_path.is_file()
          and other_installer_path.is_file() and unrelated_path.is_file()
          and stub.crontab_writes == []
          and ["launchctl", "bootout", f"{DOMAIN}/com.nedschorus.a-retired-job"] in stub.commands
          and f"{DOMAIN}/com.nedschorus.a-retired-job" not in stub.loaded
          and f"removed: not in the table — deleted {retired_plist_path}.\n" in printed,
          (exit_code, printed, stub.commands))

    retired_plist_path.write_bytes(plistlib.dumps(retired_plist, sort_keys=False).replace(
        b"<plist ", installer.PLIST_WRITTEN_BY_THIS_PROGRAM + b"\n<plist ", 1))
    stub.loaded.add(f"{DOMAIN}/com.nedschorus.a-retired-job")
    stub.exit_codes["bootout"] = 5
    exit_code, printed, errors = run_main(["--remove-not-in-table"], MAC, stub)
    check("in --remove-not-in-table, a bootout that fails with the job still loaded is "
          "FAILED, exit 1, and the plist is kept",
          exit_code == 1 and retired_plist_path.is_file() and "removed:" not in printed
          and (f"FAILED: com.nedschorus.a-retired-job — launchctl bootout exited 5, so the job "
               f"may still be loaded; {retired_plist_path} was kept.\n"
               "Read what launchctl printed above, and run this again after that cause is "
               "removed.\n") in errors, (exit_code, printed, errors))
    stub.exit_codes["print"] = 1
    exit_code, printed, errors = run_main(["--remove-not-in-table"], MAC, stub)
    check("in --remove-not-in-table, a bootout that fails while launchctl print fails with "
          "other than service-not-found is FAILED, exit 1, and the plist is kept",
          exit_code == 1 and retired_plist_path.is_file() and "removed:" not in printed
          and "FAILED: com.nedschorus.a-retired-job — launchctl bootout exited 5" in errors,
          (exit_code, printed, errors))
    retired_plist_path.unlink()
    del stub.exit_codes["bootout"], stub.exit_codes["print"]

    # A table whose last launchd job was retired names none, and the plist the
    # retired job left is still found; on a machine that is not macOS, nothing
    # is looked for.
    marked_dir = root / "LaunchAgents-of-a-table-with-no-launchd-job"
    marked_dir.mkdir()
    last_retired_path = marked_dir / "com.nedschorus.the-last-launchd-job.plist"
    last_retired_path.write_bytes(plistlib.dumps(
        dict(expected_plist, Label="com.nedschorus.the-last-launchd-job"), sort_keys=False)
        .replace(b"<plist ", installer.PLIST_WRITTEN_BY_THIS_PROGRAM + b"\n<plist ", 1))
    unmarked_path = marked_dir / "com.nedschorus.written-before-the-marker.plist"
    unmarked_path.write_bytes(plistlib.dumps(
        dict(expected_plist, Label="com.nedschorus.written-before-the-marker"), sort_keys=False))
    mac_without_launchd_path = {key: value for key, value in table["machines"]["mac"].items()
                                if key != "launchd_path"}
    check("a plist this program wrote is found when the table names no launchd job and no "
          "launchd_path; a plist written before the marker line is not",
          installer.plists_not_in_table(mac_without_launchd_path, [], marked_dir)
          == [(last_retired_path, "com.nedschorus.the-last-launchd-job")])
    no_launchd_table = json.loads(FIXTURE_TABLE_PATH.read_text(encoding="utf-8"))
    for job in no_launchd_table["jobs"]:
        job["on"] = {machine_name: placement for machine_name, placement
                     in job["on"].items() if placement["scheduler"] != "launchd"}
    no_launchd_table["jobs"] = [job for job in no_launchd_table["jobs"] if job["on"]]
    no_launchd_table["machines"]["mac"].pop("launchd_path", None)
    no_launchd_table_path = root / "table-with-no-launchd-job.json"
    no_launchd_table_path.write_text(json.dumps(no_launchd_table), encoding="utf-8")
    saved_launch_agents, LAUNCH_AGENTS = LAUNCH_AGENTS, marked_dir
    stub = MachineStub(crontab=f"{mac_mirror_line}\n".encode(),
                       loaded=[f"{DOMAIN}/com.nedschorus.the-last-launchd-job"])
    exit_code, printed, errors = run_main(["--remove-not-in-table"], MAC, stub,
                                          no_launchd_table_path)
    LAUNCH_AGENTS = saved_launch_agents
    check("--remove-not-in-table under a table that names no launchd job removes the plist "
          "the last launchd job left, and not one written before the marker line",
          exit_code == 0 and not last_retired_path.exists() and unmarked_path.is_file()
          and f"removed: not in the table — deleted {last_retired_path}.\n" in printed,
          (exit_code, printed, errors))
    check("and nothing is looked for on a machine that is not macOS",
          installer.plists_not_in_table(table["machines"]["ned-box"], [], marked_dir) == [])

    plist_path.write_bytes(plistlib.dumps(expected_plist, sort_keys=False))
    stub.loaded.add(TARGET)
    exit_code, printed, errors = run_main(["--check"] + DAILY, MAC, stub)
    check("a plist that says what the table says but lacks this program's line is a "
          "difference of its own, so --install rewrites it with the line",
          exit_code == 1 and (
              f"DIFFERS: daily-full-test-run-of-main — {plist_path} says what the table says "
              "but lacks the line marking it as written by this installer; --install adds "
              "that line.\n") in printed
          and "does not say what the table says" not in printed
          and "--install` on this machine." in printed
          and "When this machine is right and the table is wrong" not in printed,
          (exit_code, printed))
    exit_code, printed, errors = run_main(["--install"] + DAILY, MAC, stub)
    check("and --install writes the line into it",
          exit_code == 0 and installer.PLIST_WRITTEN_BY_THIS_PROGRAM in plist_path.read_bytes()
          and plistlib.loads(plist_path.read_bytes()) == expected_plist, (exit_code, printed))
    check("--print shows the plist with this program's line",
          installer.PLIST_WRITTEN_BY_THIS_PROGRAM.decode() in mac_printed, mac_printed)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
