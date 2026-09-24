#!/usr/bin/env python3
"""Tests for scripts/locate-file-copies-across-machines.py: what it finds on
each machine, what it leaves out, how it ranks and collapses copies, the git
surface's reflog and deleted-file hits, every way the other machine can fail
to answer, and the exit code each outcome gives.

Every case runs against scratch trees. The program's surfaces are replaced
through LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN, and the other machine is a
stand-in `ssh` on PATH that runs the remote command locally, so the remote
half -- the program sent on stdin to `python3 -` -- runs for real without a
network. A `python3` on the same PATH points at this interpreter, so both
halves run under the Python the suite was started with. Nothing here touches
ned-box or the real checkouts.

LOCATE_FILE_COPIES_PROGRAM_UNDER_TEST names a different copy of the program
to test; a mutation run points it at a copy with one guard removed.

Run: python3 scripts/locate-file-copies-across-machines-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import time

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROGRAM = pathlib.Path(
    os.environ.get("LOCATE_FILE_COPIES_PROGRAM_UNDER_TEST")
    or SCRIPTS_DIR / "locate-file-copies-across-machines.py")
PLAN_VARIABLE = "LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN"
FAKE_BOX = "fake-box"
# The variables that point git at another repository, stripped from every git
# this suite runs: the same set scripts/run-all-test-suites.py strips, so the
# suite is as safe run directly as it is under the runner.
GIT_REDIRECTING_VARIABLES = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

STAND_IN_SSH = """#!/usr/bin/env python3
import json, os, subprocess, sys, time
arguments = sys.argv[1:]
with open(os.environ["FAKE_SSH_ARGV_LOG"], "a") as log:
    log.write(json.dumps(arguments) + "\\n")
mode = os.environ.get("FAKE_SSH_MODE", "ok")
if mode == "unreachable":
    sys.stderr.write("ssh: connect to host fake-box port 22: No route to host\\n")
    sys.exit(255)
if mode == "hang":
    time.sleep(30)
    sys.exit(0)
if mode == "garbage":
    sys.stdin.read()
    print("Welcome to fake-box!")
    sys.exit(0)
if mode == "remote-fails":
    sys.stdin.read()
    sys.stderr.write("python3: command not found\\n")
    sys.exit(127)
index = 0
while arguments[index] == "-o":
    index += 2
command = " ".join(arguments[index + 1:])
sys.exit(subprocess.run(["sh", "-c", command]).returncode)
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"ok    {case_name}")
    else:
        print(f"FAIL  {case_name}")
        if detail:
            print("      " + str(detail).replace("\n", "\n      "))
        failures.append(case_name)


def load_program(module_name):
    spec = importlib.util.spec_from_file_location(module_name, PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


program = load_program("locate_file_copies_under_test")


def write(path, text, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def git(cwd, *arguments):
    """git in a scratch repository, with the user's global configuration
    (hooks, signing) kept out of it."""
    environment = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_CONFIG_NOSYSTEM="1")
    for variable in GIT_REDIRECTING_VARIABLES:
        environment.pop(variable, None)
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main",
         *arguments],
        cwd=cwd, env=environment, capture_output=True, text=True, check=True,
    ).stdout.strip()


def make_plan(base, other="ssh", timeout_seconds=20, extra_mac_roots=()):
    mac = {"machine": "mac", "surfaces": [
        {"name": "checkouts",
         "roots": [str(base / "mac" / "agents"), str(base / "mac" / "Projects"),
                   str(base / "mac" / "tmp")],
         "git": True},
        {"name": "handoffs",
         "roots": [str(base / "mac" / "handoffs"), *extra_mac_roots]},
    ]}
    box = {"machine": "ned-box", "surfaces": [
        {"name": "checkouts",
         "roots": [str(base / "box" / "agents"), str(base / "box" / "Projects")],
         "git": True},
        {"name": "log-store", "roots": [str(base / "box" / "logs")],
         "prune": [str(base / "box" / "logs" / "transcripts")]},
        {"name": "handoffs", "roots": [str(base / "box" / "handoffs")]},
    ]}
    for machine in (mac, box):
        for surface in machine["surfaces"]:
            for root in surface["roots"]:
                if "absent" not in root:
                    pathlib.Path(root).mkdir(parents=True, exist_ok=True)
    if other == "ssh":
        other_plan = dict(box, ssh_target=FAKE_BOX,
                          timeout_seconds=timeout_seconds)
    else:
        other_plan = dict(box, not_searched_because=other)
    return {"this": mac, "other": other_plan}


def make_stand_in_bin(base):
    bin_dir = base / "stand-in-bin"
    bin_dir.mkdir()
    ssh = bin_dir / "ssh"
    ssh.write_text(STAND_IN_SSH, encoding="utf-8")
    ssh.chmod(0o755)
    (bin_dir / "python3").symlink_to(sys.executable)
    return bin_dir


def run(base, query, mode="ok", plan=None):
    """(exit code, stdout, stderr) of one run of the program."""
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_VARIABLES:
        environment.pop(variable, None)
    environment[PLAN_VARIABLE] = json.dumps(plan or make_plan(base))
    environment["PATH"] = f"{base / 'stand-in-bin'}{os.pathsep}{environment['PATH']}"
    environment["FAKE_SSH_MODE"] = mode
    environment["FAKE_SSH_ARGV_LOG"] = str(base / "ssh-argv.log")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(PROGRAM), query],
                            capture_output=True, text=True, cwd=base,
                            env=environment, timeout=120)
    return result.returncode, result.stdout, result.stderr


CANDIDATES_HEADING = "Candidates only, not counted as found"


def sections(stdout):
    """(found list, candidates list, everything from Searched on)."""
    same = other = ""
    head, _, tail = stdout.partition("\nSearched:")
    if CANDIDATES_HEADING in head:
        head, _, other = head.partition(CANDIDATES_HEADING)
    for marker in ("Same name (", "Same path ("):
        if marker in head:
            same = head.split(marker, 1)[1]
    return same, other, "Searched:" + tail


def entry_lines(listing):
    """The lines of a list that start an entry (not "same content" lines)."""
    return [line for line in listing.splitlines()
            if re.match(r"  \d{4}-\d\d-\d\d \d\d:\d\dZ", line)]


def read_command_of(stdout, commit):
    for line in stdout.splitlines():
        if "read it: " in line and commit[:12] in line:
            return line.split("read it: ", 1)[1]
    return None


def scratch():
    return tempfile.TemporaryDirectory(prefix="locate-file-copies-test-")


NOW = time.time()

# --- What is found, where, and in what order ---------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base)
    write(base / "mac/agents/seat-a/docs/drafts/Report-Draft.md", "alpha",
          NOW - 100)
    write(base / "mac/tmp/scratch/report-draft.md", "alpha", NOW - 50)
    write(base / "mac/Projects/old/report-draft.md", "beta", NOW - 1000)
    write(base / "box/logs/seats/x/report-draft-from-origin-x.md", "gamma",
          NOW - 10)
    write(base / "box/handoffs/report-draft-handoff.md", "zeta", NOW - 20)
    write(base / "box/logs/transcripts/report-draft.md", "delta")
    write(base / "mac/agents/seat-a/node_modules/pkg/report-draft.md", "eps")
    write(base / "mac/Projects/old/.git/report-draft-in-git-dir.md", "eta")
    write(base / "mac/Projects/a-report-draft-dir/notes.md", "theta")
    write(base / "outside/target.md", "iota")
    (base / "mac/tmp/report-draft-link.md").symlink_to(base / "outside/target.md")
    code, stdout, stderr = run(base, "report-draft.md", plan=plan)
    same, other, searched = sections(stdout)
    check("a copy found on either machine exits 0", code == 0, stdout + stderr)
    check("the same-name list leads with the newest same-name copy",
          entry_lines(same)[:1]
          and "/mac/tmp/scratch/report-draft.md" in entry_lines(same)[0],
          same)
    check("an identical copy is collapsed under the newest one as a "
          "same-content line, matched case-insensitively",
          "same content" in same
          and "/mac/agents/seat-a/docs/drafts/Report-Draft.md" in same
          and len(entry_lines(same)) == 2, same)
    check("copies with different content are separate entries, newest first",
          len(entry_lines(same)) == 2
          and "/mac/Projects/old/report-draft.md" in entry_lines(same)[1],
          same)
    check("a renamed copy on ned-box, found through the ssh stand-in, is "
          "listed under other names",
          "ned-box" in other
          and "/box/logs/seats/x/report-draft-from-origin-x.md" in other, other)
    check("the other-names list is newest first",
          len(entry_lines(other)) == 2
          and "report-draft-from-origin-x.md" in entry_lines(other)[0]
          and "report-draft-handoff.md" in entry_lines(other)[1], other)
    check("a file directly in a root is found",
          "/box/handoffs/report-draft-handoff.md" in other, other)
    check("each entry carries its size",
          "(5 bytes)" in stdout and "(4 bytes)" in stdout, stdout)
    check("the log-store's transcripts directory is not searched",
          "/box/logs/transcripts/" not in same + other, stdout)
    check("a node_modules tree is not searched",
          "node_modules" not in same + other, stdout)
    check("nothing inside a .git directory is listed",
          "report-draft-in-git-dir" not in stdout, stdout)
    check("a directory whose name holds the stem is not listed, nor its "
          "other files",
          "a-report-draft-dir" not in stdout and "notes.md" not in stdout,
          stdout)
    check("a symbolic link is not listed as a copy",
          "report-draft-link.md" not in stdout, stdout)
    check("the searched lines name every surface on both machines, and the "
          "log-store's exception",
          "mac checkouts:" in searched and "mac handoffs:" in searched
          and "ned-box log-store:" in searched
          and f"except {base / 'box/logs/transcripts'}" in searched
          and "ned-box handoffs:" in searched and "mac git:" in searched,
          searched)
    check("a complete search prints no instruction to tell the user anything",
          "Tell the user" not in stdout, stdout)
    argv_log = (base / "ssh-argv.log").read_text(encoding="utf-8").splitlines()
    first = json.loads(argv_log[0]) if argv_log else []
    check("ned-box is searched in one ssh call, in batch mode with a short "
          "connect timeout",
          len(argv_log) == 1
          and first[:4] == ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
          and first[4] == FAKE_BOX
          and first[5].startswith("python3 - --this-machine-json "),
          argv_log)

# --- Ranking inside the same-name list ------------------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac/agents/s/lead-case.md", "same bytes", NOW - 500)
    write(base / "box/logs/seats/lead-case-copy.md", "same bytes", NOW - 5)
    write(base / "mac/tmp/other/lead-case.md", "different bytes", NOW - 100)
    code, stdout, _ = run(base, "lead-case.md")
    same, _, _ = sections(stdout)
    leads = entry_lines(same)
    check("a same-name group is led by its same-name copy even when a "
          "renamed identical copy is newer",
          any("/mac/agents/s/lead-case.md" in line for line in leads)
          and not any("lead-case-copy.md" in line for line in leads)
          and "lead-case-copy.md" in same, same)
    check("the same-name list is ordered by the copy that leads each entry",
          len(leads) == 2 and "/mac/tmp/other/lead-case.md" in leads[0]
          and "/mac/agents/s/lead-case.md" in leads[1], same)

# --- The git surface: a commit only a worktree's HEAD reflog reaches ------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base)
    clone = base / "elsewhere" / "repo"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    write(clone / "README.md", "readme")
    git(clone, "add", "README.md")
    git(clone, "commit", "-q", "-m", "Start")
    worktree = base / "mac" / "agents" / "seat-w"
    git(clone, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
    write(worktree / "docs" / "reflog-only-note.md", "reflog content")
    git(worktree, "add", "docs/reflog-only-note.md")
    git(worktree, "commit", "-q", "-m", "Add the reflog-only note")
    commit = git(worktree, "rev-parse", "HEAD")
    git(worktree, "checkout", "-q", "--detach", "HEAD~1")
    reachable = git(clone, "log", "--all", "--format=%H").split()
    check("scenario: the commit is reachable from no branch and the file is "
          "gone from disk",
          commit not in reachable
          and not (worktree / "docs" / "reflog-only-note.md").exists(),
          reachable)
    code, stdout, stderr = run(base, "reflog-only-note.md", plan=plan)
    check("a commit only a worktree's HEAD reflog reaches is found, through "
          "a clone outside every root, named as commit <hash> (\"<subject>\")",
          code == 0
          and f'commit {commit[:12]} ("Add the reflog-only note")' in stdout
          and "docs/reflog-only-note.md, added" in stdout,
          stdout + stderr)
    command = read_command_of(stdout, commit)
    shown = subprocess.run(["sh", "-c", command or "false"],
                           capture_output=True, text=True)
    check("its read-it command prints the file's content at that commit",
          shown.returncode == 0 and shown.stdout == "reflog content",
          f"{command!r}: {shown.stdout!r} {shown.stderr!r}")

# --- The git surface: a deleted file, collapsed with a copy on disk -------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    repo = base / "mac" / "Projects" / "repo2"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    write(repo / "docs" / "gone-note.md", "gone content")
    git(repo, "add", "docs/gone-note.md")
    git(repo, "commit", "-q", "-m", "Add the gone note")
    git(repo, "rm", "-q", "docs/gone-note.md")
    git(repo, "commit", "-q", "-m", "Remove the gone note")
    deletion = git(repo, "rev-parse", "HEAD")
    write(base / "mac" / "tmp" / "copy" / "gone-note.md", "gone content",
          978307200)
    code, stdout, stderr = run(base, "gone-note.md")
    check("a file deleted in history is found at its deleting commit",
          code == 0
          and f'commit {deletion[:12]} ("Remove the gone note")' in stdout
          and "docs/gone-note.md, deleted" in stdout, stdout + stderr)
    command = read_command_of(stdout, deletion)
    shown = subprocess.run(["sh", "-c", command or "false"],
                           capture_output=True, text=True)
    check("a deleted file's read-it command reads the parent, where the "
          "content still is",
          command is not None and "^:" in command
          and shown.returncode == 0 and shown.stdout == "gone content",
          f"{command!r}: {shown.stdout!r} {shown.stderr!r}")
    same, _, _ = sections(stdout)
    check("a copy on disk with the deleted content collapses under the "
          "deleting commit",
          len(entry_lines(same)) == 1 and "same content" in same
          and "/mac/tmp/copy/gone-note.md" in same, same)

# --- Nothing found, everything searched -----------------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "mac" / "Projects" / "broken" / ".git" / "objects").mkdir(
        parents=True)
    no_objects = base / "mac" / "Projects" / "no-objects" / ".git"
    (no_objects / "refs").mkdir(parents=True)
    (no_objects / "HEAD").write_text("ref: refs/heads/main\n")
    plan = make_plan(base, extra_mac_roots=[str(base / "absent-root")])
    code, stdout, stderr = run(base, "nothing-anywhere.md", plan=plan)
    check("nothing found with every surface searched exits 1",
          code == 1, stdout + stderr)
    check("a .git directory with no HEAD, or with no objects/, is skipped, "
          "not reported as a failure",
          "git log in" not in stdout and "NOT searched" not in stdout,
          stdout)
    check("a root that does not exist is shown as absent, not as a failure",
          f"{base / 'absent-root'} (absent)" in stdout, stdout)
    backup_search = PROGRAM.resolve().parent / "find-deleted-path-across-backups.py"
    check("nothing found names the backup search as the next command, run "
          "with python3 by its absolute path",
          f"Nothing was found: run next `python3 {backup_search} "
          "nothing-anywhere.md`" in stdout, stdout)
    if backup_search.is_file():
        helped = subprocess.run([sys.executable, str(backup_search), "--help"],
                                capture_output=True, text=True, cwd="/")
        check("the command as printed runs from any directory",
              helped.returncode == 0, helped.stderr)
    check("nothing found tells the agent to say where it looked, not that "
          "the file does not exist",
          "say where you looked" in stdout
          and "do not say the file does not exist" in stdout, stdout)

# --- A surface that fails does not read as "not found" --------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "s" / "only-local.md", "local")
    for mode, expected in (
            ("unreachable",
             f"ssh {FAKE_BOX} failed: ssh: connect to host fake-box port 22: "
             "No route to host"),
            ("hang", "it did not answer within 1 s"),
            ("garbage", "the search there printed something that is not its "
                        "answer"),
            ("remote-fails", "the search there exited 127: python3: command "
                             "not found")):
        plan = make_plan(base, timeout_seconds=1)
        code, stdout, stderr = run(base, "absent-everywhere.md", mode, plan)
        check(f"ned-box {mode}: nothing found exits 3, not 1",
              code == 3, stdout + stderr)
        check(f"ned-box {mode}: the reason is printed and the user is to be "
              "told, remedy included",
              f"Tell the user ned-box was not searched: {expected}." in stdout
              and "Give the user this remedy" in stdout
              and f"ssh {program.NED_BOX_SSH_TARGET} true" in stdout,
              stdout)
    code, stdout, stderr = run(base, "only-local.md", "unreachable",
                               make_plan(base))
    check("ned-box unreachable: a copy found on the Mac still exits 0, and "
          "the user is still to be told",
          code == 0 and "/mac/agents/s/only-local.md" in stdout
          and "Tell the user ned-box was not searched" in stdout,
          stdout + stderr)

if hasattr(os, "geteuid") and os.geteuid() == 0:
    print("SKIP  an unreadable directory (running as root reads everything)")
else:
    with scratch() as directory:
        base = pathlib.Path(directory)
        make_stand_in_bin(base)
        locked = base / "mac" / "Projects" / "locked"
        write(locked / "inner" / "x.md", "x")
        locked.chmod(0)
        try:
            code, stdout, stderr = run(base, "absent-everywhere.md")
        finally:
            locked.chmod(0o755)
        check("a directory find cannot read makes nothing-found exit 3",
              code == 3, stdout + stderr)
        check("the directory that could not be read is named, and the user "
              "is to be told",
              "NOT searched, or searched only in part:" in stdout
              and str(locked) in stdout
              and "Tell the user which places above could not be searched"
              in stdout, stdout)

# --- Run on ned-box: the Mac is reported as not searched ------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base, other=program.MAC_NOT_REACHABLE_FROM_NED_BOX)
    plan["this"], plan["other"] = (
        dict(plan["other"], machine="ned-box"),
        dict(plan["this"],
             not_searched_because=program.MAC_NOT_REACHABLE_FROM_NED_BOX))
    plan["this"].pop("not_searched_because", None)
    code, stdout, stderr = run(base, "absent-everywhere.md", plan=plan)
    check("run on ned-box, nothing found exits 3: the Mac was not searched",
          code == 3 and "mac: no route from ned-box to the Mac is documented"
          in stdout, stdout + stderr)
    check("run on ned-box, the agent is told to run it on the Mac too",
          "To search the Mac as well, run this program on the Mac." in stdout
          and "Tell the user ned-box" not in stdout, stdout)
    check("run on ned-box, no ssh is attempted",
          not (base / "ssh-argv.log").exists(), "ssh was called")

real_gethostname = socket.gethostname
try:
    socket.gethostname = lambda: "ned-box"
    on_box = program.production_plan()
    socket.gethostname = lambda: "Els-MacBook-Pro.local"
    on_mac = program.production_plan()
finally:
    socket.gethostname = real_gethostname
check("on ned-box the production plan searches ned-box and does not reach "
      "for the Mac",
      on_box["this"]["machine"] == "ned-box"
      and "ssh_target" not in on_box["other"]
      and on_box["other"]["not_searched_because"]
      == program.MAC_NOT_REACHABLE_FROM_NED_BOX, on_box)
check("on the Mac the production plan searches ned-box over ssh as "
      "nedlern@ned-box",
      on_mac["this"]["machine"] == "mac"
      and on_mac["other"]["ssh_target"] == "nedlern@ned-box", on_mac)
log_store = [surface for surface in on_mac["other"]["surfaces"]
             if surface["name"] == "log-store"]
box_checkouts = [surface["roots"]
                 for plan_side in (on_mac["other"], on_box["this"])
                 for surface in plan_side["surfaces"]
                 if surface["name"] == "checkouts"]
check("the production plan searches ned-box's scratch worktrees, "
      "/tmp/claude-1000, as it searches the Mac's /private/tmp/claude-501",
      len(box_checkouts) == 2
      and all("/tmp/claude-1000" in roots for roots in box_checkouts),
      box_checkouts)
check("the production log-store surface leaves out transcripts/",
      log_store and log_store[0]["prune"]
      == ["/home/nedlern/nedschorus-logs/transcripts"], log_store)

# --- The query reaches the other machine intact ---------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    awkward = "we'ird $(touch PWNED) x.md"
    write(base / "box" / "logs" / "seats" / awkward, "awkward")
    code, stdout, stderr = run(base, awkward)
    check("a query with quotes and $( ) is quoted for the remote shell: "
          "found there, and nothing it names is run",
          code == 0 and "ned-box" in stdout and awkward in stdout
          and not (base / "PWNED").exists(), stdout + stderr)

# --- Glob characters in the query are literal -----------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "e" / "notes[1].md", "bracketed")
    write(base / "mac" / "agents" / "e" / "notes1.md", "plain")
    code, stdout, stderr = run(base, "notes[1].md")
    check("glob characters in the query match themselves only",
          code == 0 and "notes[1].md  (" in stdout
          and "/e/notes1.md" not in stdout, stdout + stderr)

# --- A long answer is cut, and says how to narrow it ----------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    total = program.MAX_ENTRIES_PER_LIST + 5
    for number in range(total):
        write(base / "mac" / "agents" / "t" / f"many-{number:02d}-trunc.md",
              f"content {number}", NOW - number)
    code, stdout, _ = run(base, "trunc")
    _, other, _ = sections(stdout)
    check("more entries than a list shows are counted, not printed",
          len(entry_lines(other)) == program.MAX_ENTRIES_PER_LIST
          and "... and 5 more not shown" in stdout, stdout)
    check("a cut list tells the agent to narrow the name",
          "run again with more of the name" in stdout, stdout)

# --- The git surface: a file added and deleted on a merged topic branch --------
# Every pull request reaches main as a merge commit. With a pathspec and no
# --full-history, git log follows a merge's first parent alone when the path
# is the same there, so a file that lived only on the topic branch is never
# reached once the branch and its worktree's reflog are gone.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    clone = base / "mac" / "Projects" / "side-clone"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    write(clone / "README.md", "readme")
    git(clone, "add", "README.md")
    git(clone, "commit", "-q", "-m", "Start")
    topic = base / "elsewhere" / "topic-worktree"
    git(clone, "worktree", "add", "-q", "-b", "topic", str(topic))
    write(topic / "docs" / "drafts" / "side-branch-draft.md", "side content")
    git(topic, "add", "docs/drafts/side-branch-draft.md")
    git(topic, "commit", "-q", "-m", "Add the side-branch draft")
    git(topic, "rm", "-q", "docs/drafts/side-branch-draft.md")
    git(topic, "commit", "-q", "-m", "Remove the side-branch draft")
    removal = git(topic, "rev-parse", "HEAD")
    git(clone, "merge", "-q", "--no-ff", "-m", "Merge topic", "topic")
    git(clone, "worktree", "remove", str(topic))
    git(clone, "branch", "-q", "-D", "topic")
    simplified = git(clone, "log", "--reflog", "--all", "--format=%H", "--",
                     "docs/drafts/side-branch-draft.md")
    full = git(clone, "log", "--reflog", "--all", "--full-history",
               "--format=%H", "--", "docs/drafts/side-branch-draft.md")
    check("scenario: without --full-history git log does not reach the side "
          "branch's commits, and with it does",
          simplified == "" and removal in full.split(), (simplified, full))
    code, stdout, stderr = run(base, "side-branch-draft.md")
    check("a file that lived only on a merged topic branch is found at its "
          "deleting commit",
          code == 0
          and f'commit {removal[:12]} ("Remove the side-branch draft")' in stdout
          and "docs/drafts/side-branch-draft.md, deleted" in stdout,
          stdout + stderr)

# --- Candidates alone are not "found" ---------------------------------------------
# Measured 2026-09-24: `plan.md`, which no file is named, matched 1,767 names
# on the Mac and exited 0 with no next step.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "c" / "candidate-probe-notes.md", "n")
    write(base / "box" / "logs" / "seats" / "x" / "candidate-probe-old.md", "o")
    code, stdout, stderr = run(base, "candidate-probe.md")
    same, other, _ = sections(stdout)
    check("names that only contain the stem exit 1, not 0, when every surface "
          "was searched", code == 1, stdout + stderr)
    check("they are still listed, as candidates, under a heading that says "
          "they do not count as found",
          "candidate-probe-notes.md" in other and "candidate-probe-old.md" in other
          and CANDIDATES_HEADING in stdout and not same,
          stdout)
    check("candidates alone print the instruction to check their content and "
          "the next step",
          "No copy named candidate-probe.md was found: the files above are "
          "candidates only; check a candidate's content before you say it is "
          "the file." in stdout
          and "Run next `python3 " in stdout
          and "do not say the file does not exist" in stdout, stdout)
    code, stdout, stderr = run(base, "candidate-probe.md", "unreachable",
                               make_plan(base))
    check("candidates alone, with ned-box unreachable, exit 3",
          code == 3, stdout + stderr)

# --- A query with directories is found only by a copy at that path -------------
# The log-store reuses generic names across records (40 dispositions.md on
# 2026-09-24), so a same-name copy in another directory is a candidate.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "box" / "logs" / "cold-read-records" / "other-record"
          / "path-probe.md", "an unrelated record", NOW - 5)
    code, stdout, stderr = run(base, "nowhere/never-existed/path-probe.md")
    same, other, _ = sections(stdout)
    check("a query with directories is not found by a same-name copy in "
          "another directory: exit 1, the copy listed as a candidate",
          code == 1 and not same and "other-record/path-probe.md" in other,
          stdout + stderr)
    check("the instruction names the path that was not found",
          "No copy at nowhere/never-existed/path-probe.md was found: the files "
          "above are candidates only" in stdout, stdout)
    write(base / "mac" / "agents" / "s" / "wanted" / "dir" / "path-probe.md",
          "the real one", NOW - 500)
    write(base / "mac" / "agents" / "s" / "path-probe-notes.md", "stem only",
          NOW - 1)
    code, stdout, stderr = run(base, "wanted/dir/path-probe.md")
    same, other, _ = sections(stdout)
    check("a copy whose path ends with the query's path is found, under a "
          "same-path heading",
          code == 0 and "Same path (wanted/dir/path-probe.md)" in stdout
          and "/s/wanted/dir/path-probe.md" in same
          and "other-record" not in same, stdout + stderr)
    check("a same-name candidate is listed before a newer stem-only one",
          len(entry_lines(other)) == 2
          and "other-record/path-probe.md" in entry_lines(other)[0]
          and "path-probe-notes.md" in entry_lines(other)[1], other)
    code, stdout, stderr = run(base, "wanted/DIR/Path-Probe.md")
    check("the path is compared without regard to case",
          code == 0 and "/s/wanted/dir/path-probe.md" in sections(stdout)[0],
          stdout + stderr)
    code, stdout, stderr = run(base, "anted/dir/path-probe.md")
    check("the path is compared on whole components, not characters",
          code == 1 and not sections(stdout)[0], stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    repo = base / "mac" / "Projects" / "path-repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    write(repo / "md-records" / "a-record" / "git-path-probe.md", "record")
    git(repo, "add", "md-records")
    git(repo, "commit", "-q", "-m", "Add the record")
    git(repo, "rm", "-q", "-r", "md-records")
    git(repo, "commit", "-q", "-m", "Remove the record")
    code, stdout, stderr = run(base, "md-records/a-record/git-path-probe.md")
    check("a git hit, whose path is relative to its clone, is found by a "
          "query with that path",
          code == 0 and "md-records/a-record/git-path-probe.md, deleted"
          in sections(stdout)[0], stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "mac" / "agents" / "seat-x" / ".git").mkdir(parents=True)
    write(base / "mac" / "agents" / "seat-y" / "docs" / "abs-probe.md",
          "the copy in another checkout", NOW - 50)
    write(base / "mac" / "agents" / "seat-y" / "other" / "abs-probe.md",
          "elsewhere", NOW - 10)
    query = str(base / "mac" / "agents" / "seat-x" / "docs" / "abs-probe.md")
    code, stdout, stderr = run(base, query)
    same, other, _ = sections(stdout)
    check("an absolute query inside a checkout is compared by its path "
          "within that checkout, so another checkout's copy is found",
          code == 0 and "Same path (docs/abs-probe.md)" in stdout
          and "/seat-y/docs/abs-probe.md" in same
          and "/seat-y/other/abs-probe.md" in other, stdout + stderr)

# --- A same-name copy is never cut by the per-machine caps ----------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    for number in range(program.MAX_FILE_HITS_PER_MACHINE + 1):
        write(base / "mac" / "agents" / "many" / f"cap-file-probe-{number:03d}.md",
              f"candidate {number}", NOW - 10 - number)
    write(base / "mac" / "Projects" / "old" / "cap-file-probe.md", "the copy",
          NOW - 100000)
    code, stdout, stderr = run(base, "cap-file-probe.md")
    same, _, searched = sections(stdout)
    check("an older same-name file is kept when more than the cap of newer "
          "candidates match",
          code == 0 and "/mac/Projects/old/cap-file-probe.md" in same,
          stdout + stderr)
    check("the cut is reported as a cut of the others only",
          f"every one named cap-file-probe.md was kept, and only the newest "
          f"{program.MAX_FILE_HITS_PER_MACHINE} of the others" in searched,
          searched)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    for number in range(program.MAX_FILE_HITS_PER_MACHINE):
        write(base / "mac" / "agents" / "full" / f"no-cut-probe-{number:03d}.md",
              f"candidate {number}", NOW - 10 - number)
    write(base / "mac" / "Projects" / "old" / "no-cut-probe.md", "the copy",
          NOW - 100000)
    code, stdout, stderr = run(base, "no-cut-probe.md")
    _, _, searched = sections(stdout)
    check("no cut is reported when only the same-name copies take the total "
          "past the cap",
          code == 0 and "were considered" not in searched, searched)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    repo = base / "mac" / "Projects" / "cap-repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    write(repo / "cap-git-probe.md", "the git copy")
    git(repo, "add", "cap-git-probe.md")
    git(repo, "commit", "-q", "-m", "Add the probe")
    git(repo, "rm", "-q", "cap-git-probe.md")
    git(repo, "commit", "-q", "-m", "Remove the probe")
    removal = git(repo, "rev-parse", "HEAD")
    for number in range(program.MAX_GIT_PATHS_PER_CLONE + 1):
        write(repo / "many" / f"cap-git-probe-{number:03d}.md", f"c {number}")
    git(repo, "add", "many")
    git(repo, "commit", "-q", "-m", "Add the candidates")
    code, stdout, stderr = run(base, "cap-git-probe.md")
    same, _, _ = sections(stdout)
    check("an older same-name path in git is kept when more than the cap of "
          "newer candidate paths match",
          code == 0 and f"commit {removal[:12]}" in same
          and "cap-git-probe.md, deleted" in same, stdout + stderr)

# --- Every same-name copy is printed ---------------------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    total = program.MAX_ENTRIES_PER_LIST + 5
    for number in range(total):
        write(base / "mac" / "agents" / f"s{number:02d}" / "every-copy.md",
              f"content {number}", NOW - number)
    code, stdout, _ = run(base, "every-copy.md")
    same, _, _ = sections(stdout)
    check("the same-name list prints every copy, not only the first "
          f"{program.MAX_ENTRIES_PER_LIST}",
          code == 0 and len(entry_lines(same)) == total
          and "more not shown" not in same, same)

# --- Usage -----------------------------------------------------------------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    code, _, stderr = run(base, "/")
    check("a query with no file name is a usage error, exit 2",
          code == 2 and "no file name" in stderr, stderr)

# --- The pieces, in process -------------------------------------------------------
blob_a = "a" * 40
blob_b = "b" * 40
crafted = (
    b"\x01" + b"1" * 40 + b"\x001700000000\x00Touch two files\x00\n"
    + b":100644 100644 " + blob_a.encode() + b" " + blob_b.encode()
    + b" M\x00dir-with-stem/other.md\x00"
    + b":100644 000000 " + blob_a.encode() + b" " + b"0" * 40
    + b" D\x00x/stem-file.md\x00"
)
parsed = program.parse_git_log(crafted, "stem")
check("a git path under a directory named after the stem is not a hit",
      "dir-with-stem/other.md" not in parsed, parsed)
check("a git path whose own name holds the stem is a hit, and a deletion "
      "keeps the blob it deleted",
      parsed.get("x/stem-file.md", {}).get("blob") == blob_a
      and parsed["x/stem-file.md"]["status"] == "D", parsed)

with scratch() as directory:
    sample = write(pathlib.Path(directory) / "sample.md", "some bytes\n")
    expected_blob = git(directory, "hash-object", str(sample))
    check("a file's id is git's blob id for its bytes",
          program.git_blob_id(str(sample), sample.stat().st_size)
          == expected_blob, expected_blob)
    saved_limit = program.HASH_SIZE_LIMIT_BYTES
    program.HASH_SIZE_LIMIT_BYTES = 3
    try:
        check("a file above the hash size limit is not hashed",
              program.git_blob_id(str(sample), sample.stat().st_size) is None)
    finally:
        program.HASH_SIZE_LIMIT_BYTES = saved_limit

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
