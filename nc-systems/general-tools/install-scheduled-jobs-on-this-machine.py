#!/usr/bin/env python3
"""Install the project's scheduled jobs on this machine, from one table of jobs.

Usage:
  nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py
      (--print | --check | --install [--start-once] | --remove
       | --remove-not-in-table) [--job NAME ...]

  --print       print what the table gives this machine: each job's cron line
                or launchd plist. Reads nothing on the machine, changes nothing.
  --check       compare what this machine has installed with the table; exit 1
                when any job differs, or when this machine runs a job the
                table does not name. Changes nothing.
  --install     make this machine's crontab and launchd jobs what the table
                says. A job already installed as the table says is left alone.
  --start-once  with --install: after installing, ask launchd to run each
                selected launchd job once, now.
  --remove      take the named jobs off this machine. Needs --job: nothing
                removes every job at once.
  --remove-not-in-table
                take off this machine every job --check reports NOT IN THE
                TABLE. Takes no --job.
  --job NAME    limit the run to this job of the table; repeat for several.
                Without it --print, --check and --install take every job the
                table places on this machine.

WHY THIS EXISTS (user-ruled 2026-10-01, Mac session
8db2e753-65d6-4e89-bc4d-063f2a20e951). The Mac's daily full test run was about
to be installed as a plist typed by hand, as ned-box's cron line for it had
been the day before and as the transcript mirror's cron lines were on both
machines. Asked for his word on the hand install, the user answered "why not
automate?" (19:24:32Z). Told that the project then had two installers, both
for the login restart, and two jobs with none, he answered "Y - do we have
multiple installers and if so should we consolidate them" (19:29:04Z). Asked
whether to consolidate into one program with a table of jobs, in two pull
requests, he answered "y - where would be put the installer system - or is it
different systems that share an installer?" (19:33:03Z); and to the answer —
different systems share it, so it goes in nc-systems/general-tools/, with one
table beside it — "y" (19:38:29Z).

What a hand install costs: the job's program path, interpreter, PATH and time
are in no repository and under no test; nothing says which jobs each machine
should have; and every move of a program to its system's directory is followed
by someone editing crontabs by hand on two machines. With the table, a move
changes one path in the table and one run of this program reinstalls.

THE TABLE is scheduled-jobs-on-each-machine.json, beside this file. `machines`
names each machine: the platform and home directory this program recognises it
by, the interpreter its jobs run under, the reference clone they run from, and
on the Mac the PATH a launchd job is given, because launchd's own has neither
Homebrew nor ~/.local/bin. `jobs` names each job: its program, relative to the
clone; its arguments; the file under the home directory that both of its
output streams are appended to; and under `on`, for each machine that runs it,
the scheduler and the schedule. A machine a job does not name does not run it.

This program runs on whichever machine it is started on and installs only that
machine's part. A machine whose platform and home directory match no entry is
refused: the table's paths would be another machine's.

TWO SCHEDULERS, and room for more. `cron`: the placement holds `schedule`, the
five time fields, and the line is

    <schedule> <python> <clone>/<program> [<arguments>] >> <home>/<output> 2>&1

`launchd`: the placement holds `label` and `launchd_keys`, the plist keys that
say when the job runs (StartCalendarInterval for a time of day; RunAtLoad for
a login). The plist is Label, ProgramArguments, EnvironmentVariables with the
machine's PATH, those keys, and both output paths, and its file carries the
comment line PLIST_WRITTEN_BY_THIS_PROGRAM, which is how --check tells a plist
this program wrote from one another program wrote: the login restart's
installer writes a plist of the same shape, from the same clone, under the
same label prefix. The login restart's two
installers (scripts/install-restart-live-seats-at-login-launch-agent.py and
scripts/install-restart-live-seats-at-login-systemd-unit.py) join the table in
a later pull request: its launchd half fits `launchd_keys` as it stands, and
its ned-box half needs a third scheduler, a systemd user unit, added to
SCHEDULERS here.

The Mac's daily full test run is launchd and not cron because a launchd
calendar job missed while the Mac sleeps starts at the next wake, and a cron
line is skipped (user-ruled, his "y" at 2026-10-01T04:38:17Z, item 11 of the
walk open-questions-concerns-and-recommendations-2026-09-30). The Mac's
transcript mirror stays cron: scripts/transcript-mirror-to-log-store.py
records why.

WHAT A CRON INSTALL TOUCHES. Only the lines of the selected jobs. A job's line
is a line that is not a comment and names the job's program file — the file
name, not the whole path, so that after a program moves to another directory
its old line is replaced and not left beside the new one. A line already equal
to the table's is left alone, and a crontab that needs no change is not
written at all. A differing line is replaced and the line removed is printed.
Every other line, comments included, goes back byte for byte: the crontab is
read with `crontab -l` as bytes and written back whole in one
`crontab <file>` call. When `crontab -l` fails for any reason but "no crontab
for <user>", nothing is written: an unreadable crontab taken for an empty one
would be replaced by the table's lines alone.

WHAT A LAUNCHD INSTALL DOES. Writes ~/Library/LaunchAgents/<label>.plist,
checks it with `plutil -lint`, boots out a job of that label that is already
loaded (bootstrap refuses a loaded label), bootstraps the plist into the
login session, gui/<uid>, and confirms with `launchctl print`. A plist that
already says what the table says, with its job loaded, is left alone.
--start-once then runs `launchctl kickstart` on each selected launchd job,
which is how a new job is shown to run under launchd without waiting for its
hour.

RETIRING A JOB. Take it off each machine that runs it, with --remove --job
NAME, before the pull request that deletes it from the table merges: --remove
finds a job's cron line and plist through the job's entry in the table. A job
deleted from the table first stays installed, and running it every day is the
cost of forgetting the order, so --check, run without --job, also reports each
job this machine runs that no job of the table names for it, NOT IN THE TABLE:
a cron line whose command runs a program from the machine's clone, directly or
through an interpreter, and is no cron job's line of the table — not a
comment, not a line that sets a variable, and not a line that only reads or
writes a file in the clone; and a plist carrying
PLIST_WRITTEN_BY_THIS_PROGRAM whose label is no launchd job's of the table.
A plist written before that line existed is not found.
--remove-not-in-table takes exactly those off. Every cron line that runs a
program from the clone is this program's to own: a scheduled job that runs the
project's code belongs in the table, which is the reason the table exists.

Every selected job's program must be a file in the clone before anything is
installed: a job pointed at a missing file fails at every firing and says so
only in its output file.

Exit codes: 0 done, or for --check every job matches; 1 a step failed after
this program began changing the machine, or for --check a job differs or is
not in the table; 2 not run — a bad invocation, a table this program cannot
use, a machine the table does not name, a job's program missing, or a crontab
that could not be read.

Every option of main() beyond argv is a seam for
tests/install-scheduled-jobs-on-this-machine-test.py, which installs nothing
real: a stand-in for subprocess.run answers `crontab`, `plutil` and
`launchctl`, and the table, the home directory and the LaunchAgents directory
are temporary.
"""

import argparse
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = "install-scheduled-jobs-on-this-machine"
TABLE_FILE_NAME = "scheduled-jobs-on-each-machine.json"
SCHEDULERS = ("cron", "launchd")
# The plist keys this program writes itself; a table's launchd_keys may not
# name one, or the table and the program would each claim to say what it is.
PLIST_KEYS_THIS_PROGRAM_WRITES = (
    "Label", "ProgramArguments", "EnvironmentVariables", "StandardOutPath", "StandardErrorPath")
NO_CRONTAB_PHRASE = "no crontab for"
# The line a plist this program writes carries, before its <plist> element.
PLIST_WRITTEN_BY_THIS_PROGRAM = (
    b"<!-- written by nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py -->")


class Refusal(Exception):
    """Nothing on the machine has changed; the lines say why and what to do."""

    def __init__(self, *lines):
        super().__init__(lines[0])
        self.lines = lines


def table_refusal(table_path: Path, defect: str) -> Refusal:
    return Refusal(
        f"{PROGRAM}: not run — {table_path} {defect}.",
        "Correct the table through a pull request, then run this again.")


def load_table(table_path: Path) -> dict:
    try:
        table = json.loads(table_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise table_refusal(table_path, f"could not be read ({error.strerror})")
    except ValueError as error:
        raise table_refusal(table_path, f"is not JSON ({error})")
    if not isinstance(table, dict) or not isinstance(table.get("machines"), dict) \
            or not isinstance(table.get("jobs"), list):
        raise table_refusal(table_path, "has no `machines` object or no `jobs` list")
    for machine_name, machine in table["machines"].items():
        for key in ("platform", "home", "python", "clone"):
            if not isinstance(machine, dict) or not isinstance(machine.get(key), str):
                raise table_refusal(table_path, f"gives machine `{machine_name}` no `{key}`")
    names, program_file_names = set(), set()
    for job in table["jobs"]:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            raise table_refusal(table_path, "holds a job with no `name`")
        name = job["name"]
        if not isinstance(job.get("program"), str) or not isinstance(job.get("output"), str) \
                or not isinstance(job.get("on"), dict) \
                or not isinstance(job.get("arguments"), list) \
                or not all(isinstance(argument, str) for argument in job["arguments"]):
            raise table_refusal(
                table_path, f"gives job `{name}` a missing or wrongly typed `program`, `arguments`, "
                            f"`output` or `on`")
        # A cron line is recognised by its program's file name, so two jobs
        # sharing one would each take the other's line for its own.
        program_file_name = Path(job["program"]).name
        if name in names or program_file_name in program_file_names:
            raise table_refusal(
                table_path, f"names job `{name}` or its program file `{program_file_name}` twice")
        names.add(name)
        program_file_names.add(program_file_name)
        for machine_name, placement in job["on"].items():
            if machine_name not in table["machines"]:
                raise table_refusal(
                    table_path, f"places job `{name}` on `{machine_name}`, which `machines` lacks")
            scheduler = placement.get("scheduler") if isinstance(placement, dict) else None
            if scheduler not in SCHEDULERS:
                raise table_refusal(
                    table_path, f"gives job `{name}` on `{machine_name}` the scheduler "
                                f"`{scheduler}`; this program knows {', '.join(SCHEDULERS)}")
            if scheduler == "cron" and (not isinstance(placement.get("schedule"), str)
                                        or len(placement["schedule"].split()) != 5):
                raise table_refusal(
                    table_path, f"gives job `{name}` on `{machine_name}` no five-field `schedule`")
            if scheduler == "launchd":
                keys = placement.get("launchd_keys")
                if not isinstance(placement.get("label"), str) or not isinstance(keys, dict) \
                        or not keys or any(key in PLIST_KEYS_THIS_PROGRAM_WRITES for key in keys):
                    raise table_refusal(
                        table_path, f"gives job `{name}` on `{machine_name}` no `label`, or "
                                    f"`launchd_keys` that are empty or name a key this program "
                                    f"writes ({', '.join(PLIST_KEYS_THIS_PROGRAM_WRITES)})")
                if not isinstance(table["machines"][machine_name].get("launchd_path"), str):
                    raise table_refusal(
                        table_path, f"gives machine `{machine_name}` no `launchd_path` for "
                                    f"its launchd job `{name}`")
    return table


def machine_of_this_host(table: dict, table_path: Path, platform: str, home: Path):
    """The table's name and entry for the machine this program is running on."""
    for machine_name, machine in table["machines"].items():
        if platform.startswith(machine["platform"]) and str(home) == machine["home"]:
            return machine_name, machine
    raise Refusal(
        f"{PROGRAM}: not run — {table_path} names no machine with platform `{platform}` and "
        f"home directory `{home}`.",
        "Add this machine to the table through a pull request, then run this again.")


def jobs_placed_on(table: dict, table_path: Path, machine_name: str, selected_names):
    """(job, placement) for each selected job the table places on this machine,
    in the table's order; every placed job when none is selected."""
    known = [job["name"] for job in table["jobs"]]
    for name in selected_names or []:
        if name not in known:
            raise Refusal(
                f"{PROGRAM}: not run — {table_path} has no job `{name}`.",
                f"Pass --job with one of: {', '.join(known)}.")
        job = table["jobs"][known.index(name)]
        if machine_name not in job["on"]:
            raise Refusal(
                f"{PROGRAM}: not run — the table places job `{name}` on "
                f"{', '.join(job['on'])}, not on this machine, `{machine_name}`.",
                f"Run this on a machine the job is placed on, or pass --job with a job of "
                f"this machine.")
    return [(job, job["on"][machine_name]) for job in table["jobs"]
            if machine_name in job["on"] and (not selected_names or job["name"] in selected_names)]


def program_path_of(machine: dict, job: dict) -> str:
    return f"{machine['clone']}/{job['program']}"


def output_path_of(machine: dict, job: dict) -> str:
    return f"{machine['home']}/{job['output']}"


def cron_line(machine: dict, job: dict, placement: dict) -> str:
    command = [machine["python"], program_path_of(machine, job)] + job["arguments"]
    return (f"{placement['schedule']} {' '.join(shlex.quote(part) for part in command)} "
            f">> {shlex.quote(output_path_of(machine, job))} 2>&1")


def launch_agent_plist(machine: dict, job: dict, placement: dict) -> dict:
    """The plist as a dict, in the order plistlib writes it."""
    plist = {
        "Label": placement["label"],
        "ProgramArguments": [machine["python"], program_path_of(machine, job)] + job["arguments"],
        "EnvironmentVariables": {"PATH": machine["launchd_path"]},
    }
    plist.update(placement["launchd_keys"])
    plist["StandardOutPath"] = plist["StandardErrorPath"] = output_path_of(machine, job)
    return plist


def launch_agent_plist_bytes(machine: dict, job: dict, placement: dict) -> bytes:
    written = plistlib.dumps(launch_agent_plist(machine, job, placement), sort_keys=False)
    return written.replace(b"<plist ", PLIST_WRITTEN_BY_THIS_PROGRAM + b"\n<plist ", 1)


def launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def launchd_target(placement: dict) -> str:
    return f"{launchd_domain()}/{placement['label']}"


# --- cron ---------------------------------------------------------------

def read_crontab(run) -> str:
    """This user's crontab as text, bytes kept whatever they are; "" when the
    user has none. Refuses when `crontab -l` fails any other way."""
    finished = run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if finished.returncode == 0:
        return (finished.stdout or b"").decode("utf-8", "surrogateescape")
    said = (finished.stderr or b"").decode("utf-8", "replace").strip()
    if NO_CRONTAB_PHRASE in said:
        return ""
    raise Refusal(
        f"{PROGRAM}: not run — `crontab -l` exited {finished.returncode}: "
        f"{said.splitlines()[-1] if said else 'it printed nothing'}.",
        "Run this again after `crontab -l` prints this machine's crontab.")


def crontab_lines(text: str) -> list:
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def lines_of_job(lines: list, job: dict) -> list:
    """Indexes of the lines that run the job's program: not a comment, and
    naming the program's file as the last part of a path."""
    names_the_file = re.compile(r"/" + re.escape(Path(job["program"]).name) + r"(?=\s|$)")
    return [index for index, line in enumerate(lines)
            if not line.lstrip().startswith("#") and names_the_file.search(line)]


def crontab_with(text: str, wanted: list):
    """The crontab after installing each (job, line) of wanted, and what
    happened to each job: (job, "unchanged" | "added" | "replaced", old lines).
    The text itself comes back when nothing changes."""
    lines, outcomes = crontab_lines(text), []
    for job, line in wanted:
        held = lines_of_job(lines, job)
        if not held:
            lines.append(line)
            outcomes.append((job, "added", []))
        elif [lines[index] for index in held] == [line]:
            outcomes.append((job, "unchanged", []))
        else:
            old_lines = [lines[index] for index in held]
            lines[held[0]] = line
            for index in reversed(held[1:]):
                del lines[index]
            outcomes.append((job, "replaced", old_lines))
    if all(outcome == "unchanged" for _, outcome, _ in outcomes):
        return text, outcomes
    return "".join(line + "\n" for line in lines), outcomes


def crontab_without(text: str, jobs: list):
    """The crontab after removing each job's lines, and the lines removed."""
    lines, removed = crontab_lines(text), []
    for job in jobs:
        held = lines_of_job(lines, job)
        removed.append((job, [lines[index] for index in held]))
        for index in reversed(held):
            del lines[index]
    if not any(old_lines for _, old_lines in removed):
        return text, removed
    return "".join(line + "\n" for line in lines), removed


def write_crontab(text: str, run) -> int:
    """Replace this user's crontab with text in one `crontab <file>` call."""
    with tempfile.NamedTemporaryFile("wb", suffix=".crontab", delete=False) as crontab_file:
        crontab_file.write(text.encode("utf-8", "surrogateescape"))
    try:
        return run(["crontab", crontab_file.name]).returncode
    finally:
        os.unlink(crontab_file.name)


def report_failed_crontab_write(exit_code: int) -> None:
    print(f"FAILED: `crontab` exited {exit_code}; no cron line was changed.",
          file=sys.stderr)
    print("Read what crontab printed above, and run this again after that cause is removed.",
          file=sys.stderr)


# --- launchd ------------------------------------------------------------

def launchd_job_is_loaded(placement: dict, run) -> bool:
    return run(["launchctl", "print", launchd_target(placement)],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def installed_plist_says_what_the_table_says(plist_path: Path, machine: dict, job: dict,
                                             placement: dict) -> bool:
    try:
        return plistlib.loads(plist_path.read_bytes()) \
            == launch_agent_plist(machine, job, placement)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False


def installed_plist_carries_the_written_by_line(plist_path: Path) -> bool:
    try:
        return PLIST_WRITTEN_BY_THIS_PROGRAM in plist_path.read_bytes()
    except OSError:
        return False


def installed_plist_matches(plist_path: Path, machine: dict, job: dict, placement: dict) -> bool:
    """The plist says what the table says, and carries this program's line,
    so a plist written before the line existed is rewritten with it."""
    return installed_plist_says_what_the_table_says(plist_path, machine, job, placement) \
        and installed_plist_carries_the_written_by_line(plist_path)


# What `launchctl print` exits with when the domain has no such service.
LAUNCHCTL_PRINT_SERVICE_NOT_FOUND = 113


def booted_out_or_reported(target: str, plist_path: Path, run) -> bool:
    """Boots target out of launchd. False, with FAILED reported, when the
    bootout failed and `launchctl print` does not say the job is gone:
    deleting its plist then could leave a loaded job that no plist and no
    --check can find, so the plist is kept. A bootout that fails because the
    job was not loaded is no failure; only print's service-not-found exit
    says so, and any other exit of print leaves the job's state unknown."""
    booted = run(["launchctl", "bootout", target],
                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if booted.returncode == 0 or run(["launchctl", "print", target], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL).returncode \
            == LAUNCHCTL_PRINT_SERVICE_NOT_FOUND:
        return True
    sys.stderr.write((booted.stderr or b"").decode(errors="replace"))
    print(f"FAILED: {target.rsplit('/', 1)[-1]} — launchctl bootout exited {booted.returncode}, "
          f"so the job may still be loaded; {plist_path} was kept.", file=sys.stderr)
    print("Read what launchctl printed above, and run this again after that cause is removed.",
          file=sys.stderr)
    return False


def install_launchd_job(machine, job, placement, launch_agents_directory: Path, run) -> bool:
    """True when the job is installed as the table says when this returns."""
    name, label = job["name"], placement["label"]
    plist_path = launch_agents_directory / f"{label}.plist"
    if installed_plist_matches(plist_path, machine, job, placement) \
            and launchd_job_is_loaded(placement, run):
        print(f"unchanged: {name} — {plist_path} says what the table says, and launchd has "
              f"{label} loaded.")
        return True
    launch_agents_directory.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(launch_agent_plist_bytes(machine, job, placement))
    linted = run(["plutil", "-lint", str(plist_path)], stdout=subprocess.DEVNULL)
    if linted.returncode != 0:
        print(f"FAILED: {name} — `plutil -lint {plist_path}` exited {linted.returncode}; the "
              f"file is written and the job is not loaded.", file=sys.stderr)
        print("Read what plutil printed above, and run this again after that cause is removed.",
              file=sys.stderr)
        return False
    # bootstrap refuses a label already loaded, so an earlier load is booted
    # out first; booting out a label that is not loaded fails and is ignored.
    run(["launchctl", "bootout", launchd_target(placement)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bootstrapped = run(["launchctl", "bootstrap", launchd_domain(), str(plist_path)])
    if bootstrapped.returncode != 0:
        print(f"FAILED: {name} — `launchctl bootstrap {launchd_domain()} {plist_path}` exited "
              f"{bootstrapped.returncode}; the file is written and the job is not loaded.",
              file=sys.stderr)
        print("When this was run over ssh, ask the user to run it again from a terminal "
              "in this Mac's interactive login session.", file=sys.stderr)
        print("Otherwise read what launchctl printed above, and run this again after that "
              "cause is removed.", file=sys.stderr)
        return False
    if not launchd_job_is_loaded(placement, run):
        print(f"FAILED: {name} — bootstrap exited 0, and `launchctl print "
              f"{launchd_target(placement)}` does not find the job.", file=sys.stderr)
        print(f"Run `launchctl print {launchd_target(placement)}`, read what it prints, and "
              f"run this again after that cause is removed.", file=sys.stderr)
        return False
    print(f"installed: {name} — wrote {plist_path} and loaded {label} into {launchd_domain()}.")
    return True


def start_launchd_job_once(machine, job, placement, run) -> bool:
    started = run(["launchctl", "kickstart", launchd_target(placement)])
    if started.returncode != 0:
        print(f"FAILED: {job['name']} — `launchctl kickstart {launchd_target(placement)}` "
              f"exited {started.returncode}; the job was not started.", file=sys.stderr)
        print("Read what launchctl printed above, and run this again after that cause is "
              "removed.", file=sys.stderr)
        return False
    print(f"started: {job['name']} — launchd is running {placement['label']} once, now; its "
          f"output goes to {output_path_of(machine, job)}.")
    return True


# --- jobs the table does not name -----------------------------------------

# A crontab line that sets a variable for the lines after it, NAME=value; and
# one word of a command that does the same for that command alone.
CRON_ENVIRONMENT_ASSIGNMENT = re.compile(r"\s*[A-Za-z_][A-Za-z0-9_]*\s*=")
# A program whose first argument that is not an option is the program it runs.
INTERPRETER_PROGRAM_NAME = re.compile(r"python[0-9.]*|bash|sh|dash|zsh|perl|ruby|node|env")


def program_a_cron_line_runs(line: str):
    """The program a crontab line runs, as the line spells it: the command's
    first word, or, when that word is an interpreter or `env`, the first word
    after it that is not a NAME=value. None for a blank line, a comment, or a
    line that sets a variable; and None when an interpreter or `env` is given
    an option, because an option may take the next word as its argument
    (`env -C <dir>`), and telling which do would mean knowing every option of
    every interpreter: such a line is not reported, which only misses a job,
    where a wrong reading could remove a line that runs no program from the
    clone. A line whose command only reads
    or writes a file, such as a redirect into the clone, runs no program of
    that file, so the file is not what this returns."""
    if not line.strip() or line.lstrip().startswith("#") or CRON_ENVIRONMENT_ASSIGNMENT.match(line):
        return None
    special_schedule = line.lstrip().startswith("@")
    fields = line.split(None, 1 if special_schedule else 5)
    if len(fields) < (2 if special_schedule else 6):
        return None
    try:
        words = shlex.split(fields[-1])
    except ValueError:
        words = fields[-1].split()
    after_interpreter = False
    for word in words:
        if CRON_ENVIRONMENT_ASSIGNMENT.match(word):
            continue
        if after_interpreter and word.startswith("-"):
            return None
        if INTERPRETER_PROGRAM_NAME.fullmatch(Path(word).name):
            after_interpreter = True
            continue
        return word
    return None


def cron_lines_not_in_table(machine: dict, placed: list, lines: list) -> list:
    """Indexes of the lines whose program, as program_a_cron_line_runs finds
    it, is a file under the machine's clone, and that are no cron job's line
    of the table. A job's lines are found by its program's file name, as an
    install finds them, so a retired line that runs a file of the same name as
    a cron job of the table counts as that job's line: --check reports it as
    that job's DIFFERS, and --install replaces it with the table's line."""
    owned = set()
    for job, placement in placed:
        if placement["scheduler"] == "cron":
            owned.update(lines_of_job(lines, job))
    from_the_clone = f"{machine['clone']}/"
    return [index for index, line in enumerate(lines)
            if index not in owned
            and (program_a_cron_line_runs(line) or "").startswith(from_the_clone)]


def plists_not_in_table(machine: dict, placed: list, launch_agents_directory: Path) -> list:
    """(path, label) of each plist this program wrote whose label is no
    launchd job's of the table. Looked for on every macOS machine, including
    one whose table names no launchd job, because the job retired last leaves
    the table with none. A plist written before this program wrote
    PLIST_WRITTEN_BY_THIS_PROGRAM into its plists carries no such line, and is
    not found: --install writes the line into the plists of the jobs still in
    the table, and a job retired before that is not seen."""
    if machine["platform"] != "darwin" or not launch_agents_directory.is_dir():
        return []
    labels = {placement["label"] for _, placement in placed if placement["scheduler"] == "launchd"}
    found = []
    for plist_path in sorted(launch_agents_directory.glob("*.plist")):
        try:
            written = plist_path.read_bytes()
        except OSError:
            continue
        if PLIST_WRITTEN_BY_THIS_PROGRAM not in written:
            continue
        try:
            label = plistlib.loads(written).get("Label")
        except (ValueError, plistlib.InvalidFileException):
            label = None
        label = label if isinstance(label, str) else plist_path.stem
        if label not in labels:
            found.append((plist_path, label))
    return found


# --- the five modes -----------------------------------------------------

def print_mode(machine_name, machine, placed, launch_agents_directory: Path) -> int:
    print(f"machine: {machine_name} ({machine['platform']}, {machine['home']})")
    for job, placement in placed:
        if placement["scheduler"] == "cron":
            print(f"{job['name']} — cron line:")
            print(cron_line(machine, job, placement))
        else:
            print(f"{job['name']} — launchd job, "
                  f"{launch_agents_directory / (placement['label'] + '.plist')}:")
            sys.stdout.write(launch_agent_plist_bytes(machine, job, placement).decode("utf-8"))
    return 0


def refuse_missing_programs(machine, placed) -> None:
    for job, _ in placed:
        if not Path(program_path_of(machine, job)).is_file():
            raise Refusal(
                f"{PROGRAM}: not run — job `{job['name']}` runs "
                f"{program_path_of(machine, job)}, which is not a file on this machine.",
                f"Bring {machine['clone']} to current main, then run this again.",
                f"When main has no {job['program']} either, correct the table through a "
                f"pull request, then run this again.")


def install_mode(machine, placed, launch_agents_directory: Path, start_once: bool, run) -> int:
    launchd_jobs = [(job, placement) for job, placement in placed
                    if placement["scheduler"] == "launchd"]
    if start_once and not launchd_jobs:
        raise Refusal(
            f"{PROGRAM}: not run — --start-once starts launchd jobs, and no selected job of "
            f"this machine is one.",
            "Run this again without --start-once.")
    refuse_missing_programs(machine, placed)
    every_step_worked = True
    wanted = [(job, cron_line(machine, job, placement)) for job, placement in placed
              if placement["scheduler"] == "cron"]
    if wanted:
        installed_text = read_crontab(run)
        new_text, outcomes = crontab_with(installed_text, wanted)
        exit_code = write_crontab(new_text, run) if new_text != installed_text else 0
        if exit_code != 0:
            report_failed_crontab_write(exit_code)
            every_step_worked = False
        else:
            for (job, outcome, old_lines), (_, line) in zip(outcomes, wanted):
                if outcome == "unchanged":
                    print(f"unchanged: {job['name']} — the crontab holds the table's line.")
                elif outcome == "added":
                    print(f"installed: {job['name']} — added to the crontab: {line}")
                else:
                    print(f"replaced: {job['name']} — the crontab now holds the table's "
                          f"line: {line}")
                    for old_line in old_lines:
                        print(f"  the line removed: {old_line}")
    for job, placement in launchd_jobs:
        installed = install_launchd_job(machine, job, placement, launch_agents_directory, run)
        every_step_worked = every_step_worked and installed
        if installed and start_once:
            every_step_worked = start_launchd_job_once(machine, job, placement, run) \
                and every_step_worked
    return 0 if every_step_worked else 1


def remove_mode(machine, placed, launch_agents_directory: Path, run) -> int:
    every_step_worked = True
    cron_jobs = [job for job, placement in placed if placement["scheduler"] == "cron"]
    if cron_jobs:
        installed_text = read_crontab(run)
        new_text, removed = crontab_without(installed_text, cron_jobs)
        exit_code = write_crontab(new_text, run) if new_text != installed_text else 0
        if exit_code != 0:
            report_failed_crontab_write(exit_code)
            return 1
        for job, old_lines in removed:
            if not old_lines:
                print(f"absent: {job['name']} — the crontab held no line for "
                      f"{Path(job['program']).name}.")
            for old_line in old_lines:
                print(f"removed: {job['name']} — the line removed from the crontab: {old_line}")
    for job, placement in placed:
        if placement["scheduler"] != "launchd":
            continue
        plist_path = launch_agents_directory / f"{placement['label']}.plist"
        if not booted_out_or_reported(launchd_target(placement), plist_path, run):
            every_step_worked = False
        elif plist_path.is_file():
            plist_path.unlink()
            print(f"removed: {job['name']} — deleted {plist_path}.")
        else:
            print(f"absent: {job['name']} — there was no {plist_path}.")
    return 0 if every_step_worked else 1


def remove_not_in_table_mode(machine, placed, launch_agents_directory: Path, run) -> int:
    installed_text = read_crontab(run)
    lines = crontab_lines(installed_text)
    stray = cron_lines_not_in_table(machine, placed, lines)
    if stray:
        kept = [line for index, line in enumerate(lines) if index not in stray]
        exit_code = write_crontab("".join(line + "\n" for line in kept), run)
        if exit_code != 0:
            report_failed_crontab_write(exit_code)
            return 1
        for index in stray:
            print(f"removed: not in the table — the line removed from the crontab: "
                  f"{lines[index]}")
    plists = plists_not_in_table(machine, placed, launch_agents_directory)
    every_step_worked = True
    for plist_path, label in plists:
        if not booted_out_or_reported(f"{launchd_domain()}/{label}", plist_path, run):
            every_step_worked = False
            continue
        plist_path.unlink()
        print(f"removed: not in the table — deleted {plist_path}.")
    if not stray and not plists:
        print("absent: no crontab line runs a program from the clone, and no plist this "
              "installer wrote, outside the table.")
    return 0 if every_step_worked else 1


def check_mode(machine, placed, launch_agents_directory: Path, table_path: Path, run,
               every_job_selected: bool) -> int:
    differences = 0
    differences_only_the_marker = 0
    installed_text = None
    for job, placement in placed:
        name, differs = job["name"], []
        marker_differences_of_this_job = 0
        if not Path(program_path_of(machine, job)).is_file():
            differs.append(f"its program {program_path_of(machine, job)} is not a file on "
                           f"this machine")
        if placement["scheduler"] == "cron":
            if installed_text is None:
                installed_text = read_crontab(run)
            lines = crontab_lines(installed_text)
            held = [lines[index] for index in lines_of_job(lines, job)]
            line = cron_line(machine, job, placement)
            if not held:
                differs.append(f"the crontab holds no line for {Path(job['program']).name}; "
                               f"the table's line: {line}")
            elif held != [line]:
                differs.append(f"the crontab holds {'; '.join(held)}, not the table's "
                               f"line: {line}")
        else:
            plist_path = launch_agents_directory / f"{placement['label']}.plist"
            if not plist_path.is_file():
                differs.append(f"{plist_path} is not there")
            elif not installed_plist_says_what_the_table_says(plist_path, machine, job,
                                                              placement):
                differs.append(f"{plist_path} does not say what the table says")
            elif not installed_plist_carries_the_written_by_line(plist_path):
                differs.append(f"{plist_path} says what the table says but lacks the line "
                               f"marking it as written by this installer; --install adds that "
                               f"line")
                marker_differences_of_this_job = 1
            if not launchd_job_is_loaded(placement, run):
                differs.append(f"launchd has no job {placement['label']} loaded in "
                               f"{launchd_domain()}")
        if differs:
            differences += 1
            if len(differs) == marker_differences_of_this_job:
                differences_only_the_marker += 1
            for difference in differs:
                print(f"DIFFERS: {name} — {difference}.")
        else:
            print(f"matches: {name} — {placement['scheduler']}.")
    not_in_table = 0
    if every_job_selected:
        if installed_text is None:
            installed_text = read_crontab(run)
        lines = crontab_lines(installed_text)
        for index in cron_lines_not_in_table(machine, placed, lines):
            not_in_table += 1
            print(f"NOT IN THE TABLE: the crontab line {lines[index]} — no job of the table "
                  f"names it for this machine.")
        for plist_path, label in plists_not_in_table(machine, placed, launch_agents_directory):
            not_in_table += 1
            print(f"NOT IN THE TABLE: {plist_path}, label {label} — no job of the table "
                  f"names it for this machine.")
    if differences:
        print(f"When the table says what this machine should run, run "
              f"`{Path(__file__).resolve()} --install` on this machine.")
        # A missing marker line is never the table's fault.
        if differences > differences_only_the_marker:
            print(f"When this machine is right and the table is wrong, change {table_path} "
                  f"through a pull request.")
    if not_in_table:
        print(f"When every job NOT IN THE TABLE is retired, run "
              f"`{Path(__file__).resolve()} --remove-not-in-table` on this machine; it "
              f"removes all of them.")
        print(f"When only some are retired, first add the others' entries to {table_path} "
              f"through a pull request.")
        print(f"When a job NOT IN THE TABLE should still run, add its entry to {table_path} "
              f"through a pull request.")
        print(f"To learn whether a job was retired on purpose, run "
              f"`git log -p -- {table_path}` in the clone.")
    return 1 if differences or not_in_table else 0


def exit_codes_paragraph() -> str:
    """The docstring's paragraph on exit codes, the one part of it --help
    prints: the rest is for whoever changes this program."""
    return next(block for block in __doc__.split("\n\n") if block.startswith("Exit codes:"))


def main(argv=None, platform: str = sys.platform, home: Path = None, table_path: Path = None,
         launch_agents_directory: Path = None, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Install the project's scheduled jobs on this machine, "
                                  "from one table of jobs.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=exit_codes_paragraph())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--print", action="store_true",
                      help="print what the table gives this machine; change nothing")
    mode.add_argument("--check", action="store_true",
                      help="compare this machine with the table; exit 1 on a difference or a "
                           "job not in the table")
    mode.add_argument("--install", action="store_true",
                      help="make this machine's scheduled jobs what the table says")
    mode.add_argument("--remove", action="store_true",
                      help="take the jobs named by --job off this machine")
    mode.add_argument("--remove-not-in-table", action="store_true",
                      help="take off this machine every job --check reports NOT IN THE TABLE")
    parser.add_argument("--job", action="append", metavar="NAME",
                        help="limit the run to this job; repeat for several")
    parser.add_argument("--start-once", action="store_true",
                        help="with --install: run each selected launchd job once, now")
    arguments = parser.parse_args(argv)
    if arguments.start_once and not arguments.install:
        parser.error("--start-once goes with --install")
    if arguments.remove and not arguments.job:
        parser.error("--remove needs --job: name each job to take off this machine")
    if arguments.remove_not_in_table and arguments.job:
        parser.error("--remove-not-in-table takes no --job: it removes every job --check "
                     "reports NOT IN THE TABLE")

    home = Path(home) if home is not None else Path.home()
    table_path = Path(table_path) if table_path is not None \
        else Path(__file__).resolve().with_name(TABLE_FILE_NAME)
    if launch_agents_directory is None:
        launch_agents_directory = home / "Library" / "LaunchAgents"
    try:
        table = load_table(table_path)
        machine_name, machine = machine_of_this_host(table, table_path, platform, home)
        placed = jobs_placed_on(table, table_path, machine_name, arguments.job)
        if arguments.print:
            return print_mode(machine_name, machine, placed, launch_agents_directory)
        if arguments.check:
            return check_mode(machine, placed, launch_agents_directory, table_path, run,
                              every_job_selected=not arguments.job)
        if arguments.remove:
            return remove_mode(machine, placed, launch_agents_directory, run)
        if arguments.remove_not_in_table:
            return remove_not_in_table_mode(machine, placed, launch_agents_directory, run)
        return install_mode(machine, placed, launch_agents_directory, arguments.start_once, run)
    except Refusal as refusal:
        for line in refusal.lines:
            print(line, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
