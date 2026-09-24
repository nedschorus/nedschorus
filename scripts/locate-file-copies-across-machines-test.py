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


def commit_files(repository, files, message="Add the files"):
    """Write `files` ({path inside: text}) into `repository`, a git work
    tree (made one first when it is not), and commit them, so git tracks
    them there."""
    if not (repository / ".git").exists():
        repository.mkdir(parents=True, exist_ok=True)
        git(repository, "init", "-q")
    for relative, text in files.items():
        write(repository / relative, text)
    git(repository, "add", *files)
    git(repository, "commit", "-q", "-m", message)


def make_plan(base, other="ssh", timeout_seconds=20, extra_mac_roots=()):
    """Both machines' plans under `base`, laid out as production lays them
    out: this repository's main clone is <machine>/Projects/nedschorus, seat
    checkouts are children of <machine>/agents, and <machine>/tmp is the
    scratch tree. The Mac spells its tmp also as mac/private/tmp, and ned-box's
    home, `base/box`, as mac/Volumes/nedhome."""
    mac = {"machine": "mac", "surfaces": [
        {"name": "checkouts",
         "roots": [str(base / "mac" / "agents"), str(base / "mac" / "Projects"),
                   str(base / "mac" / "tmp")],
         "git": True},
        {"name": "handoffs",
         "roots": [str(base / "mac" / "handoffs"), *extra_mac_roots]},
    ], "this_repository": {
        "clones": [str(base / "mac" / "Projects" / "nedschorus")],
        "checkout_parents": [str(base / "mac" / "agents")],
        "scratch_trees": [str(base / "mac" / "tmp")],
    }, "spellings": [[str(base / "mac" / "private" / "tmp"),
                      str(base / "mac" / "tmp")]]}
    box = {"machine": "ned-box", "surfaces": [
        {"name": "checkouts",
         "roots": [str(base / "box" / "agents"), str(base / "box" / "Projects"),
                   str(base / "box" / "tmp")],
         "git": True},
        {"name": "log-store", "roots": [str(base / "box" / "logs")],
         "prune": [str(base / "box" / "logs" / "transcripts")]},
        {"name": "handoffs", "roots": [str(base / "box" / "handoffs")]},
    ], "this_repository": {
        "clones": [str(base / "box" / "Projects" / "nedschorus")],
        "checkout_parents": [str(base / "box" / "agents")],
        "scratch_trees": [str(base / "box" / "tmp")],
    }, "spellings": [[str(base / "mac" / "Volumes" / "nedhome"),
                      str(base / "box")]]}
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


def program_environment(base, mode="ok", plan=None):
    """The environment one run of the program gets: the plan, the stand-in
    ssh first on PATH, and no variable that points git elsewhere."""
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_VARIABLES:
        environment.pop(variable, None)
    environment[PLAN_VARIABLE] = json.dumps(plan or make_plan(base))
    environment["PATH"] = f"{base / 'stand-in-bin'}{os.pathsep}{environment['PATH']}"
    environment["FAKE_SSH_MODE"] = mode
    environment["FAKE_SSH_ARGV_LOG"] = str(base / "ssh-argv.log")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run(base, query, mode="ok", plan=None, cwd=None):
    """(exit code, stdout, stderr) of one run of the program, from `cwd`
    (`base` by default)."""
    environment = program_environment(base, mode, plan)
    result = subprocess.run([sys.executable, str(PROGRAM), query],
                            capture_output=True, text=True, cwd=cwd or base,
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


def raises(exception, function, *arguments):
    try:
        function(*arguments)
    except exception:
        return True
    return False


def shlex_quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


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
    same, other, _ = sections(stdout)
    leads = entry_lines(same)
    # PR 703, Codex's P2 in review 5299487158: grouping by content ran before
    # the found copies were set apart, so this renamed copy printed as "same
    # content" under the found list.
    check("a renamed copy with the same bytes as a found copy stays a "
          "candidate, not a same-content line in the found list",
          "lead-case-copy.md" not in same and "lead-case-copy.md" in other,
          stdout)
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

# --- A query with directories is found only at its own path ---------------------
# The log-store reuses generic names across records (40 dispositions.md on
# 2026-09-24), so a same-name copy in another directory is a candidate.
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    write(base / "box" / "logs" / "cold-read-records" / "other-record"
          / "path-probe.md", "an unrelated record", NOW - 5)
    code, stdout, stderr = run(base, "nowhere/never-existed/path-probe.md")
    same, other, _ = sections(stdout)
    check("a query with directories is not found by a same-name copy in "
          "another directory: exit 1, the copy listed as a candidate",
          code == 1 and not same and "other-record/path-probe.md" in other,
          stdout + stderr)
    check("the instruction names the path that was not found, made absolute "
          "from the current directory",
          f"No copy at {base / 'nowhere' / 'never-existed' / 'path-probe.md'} "
          f"was found: the files above are candidates only" in stdout, stdout)
    stored = base / "box" / "logs" / "s" / "wanted" / "dir" / "path-probe.md"
    write(stored, "the real one", NOW - 500)
    write(base / "mac" / "agents" / "s" / "path-probe-notes.md", "stem only",
          NOW - 1)
    code, stdout, stderr = run(base, str(stored))
    same, other, _ = sections(stdout)
    check("a copy at the query's own path is found, under a same-path heading",
          code == 0 and f"Same path ({stored})" in stdout
          and "/logs/s/wanted/dir/path-probe.md" in same
          and "other-record" not in same, stdout + stderr)
    check("a same-name candidate is listed before a newer stem-only one",
          len(entry_lines(other)) == 2
          and "other-record/path-probe.md" in entry_lines(other)[0]
          and "path-probe-notes.md" in entry_lines(other)[1], other)
    code, stdout, stderr = run(base, "wanted/dir/path-probe.md",
                               cwd=base / "box" / "logs" / "s")
    check("the same path asked relative to the directory that holds it is "
          "found there",
          code == 0 and "/logs/s/wanted/dir/path-probe.md" in sections(stdout)[0],
          stdout + stderr)
    code, stdout, stderr = run(base, "wanted/DIR/Path-Probe.md",
                               cwd=base / "box" / "logs" / "s")
    check("the path is compared without regard to case",
          code == 0 and "/logs/s/wanted/dir/path-probe.md" in sections(stdout)[0],
          stdout + stderr)
    code, stdout, stderr = run(base, "anted/dir/path-probe.md",
                               cwd=base / "box" / "logs" / "s")
    check("the path is compared on whole components, not characters",
          code == 1 and not sections(stdout)[0], stdout + stderr)
    code, stdout, stderr = run(base, "wanted/dir/path-probe.md")
    check("a relative path is not matched against the ends of other paths: "
          "asked from elsewhere, the stored copy is a candidate",
          code == 1 and not sections(stdout)[0]
          and "/logs/s/wanted/dir/path-probe.md" in sections(stdout)[1],
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "s" / "suffixless-probe.md", "the file")
    code, stdout, stderr = run(base, "suffixless-probe")
    check("a query with no suffix is found by a file of that stem",
          code == 0 and "/s/suffixless-probe.md" in sections(stdout)[0],
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "box" / "logs" / "x" / "lead-probe.md", "the same bytes",
          NOW - 500)
    write(base / "mac" / "agents" / "s" / "lead-probe-renamed.md",
          "the same bytes", NOW - 5)
    code, stdout, stderr = run(base, "nowhere/lead-probe.md")
    _, other, _ = sections(stdout)
    check("a candidate group is led by its same-name copy, not by a newer "
          "renamed copy of the same content",
          code == 1 and len(entry_lines(other)) == 1
          and "/x/lead-probe.md" in entry_lines(other)[0]
          and "same content" in other and "lead-probe-renamed.md" in other,
          stdout + stderr)

# --- The query may be written as it is cited -------------------------------------
# CLAUDE.md prescribes nedlern@ned-box:<path> for log-store citations; PR 703
# review 5299114606 measured that form never found, even at its exact path.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    stored = write(base / "box" / "logs" / "seats" / "s" / "scp-probe-report.md",
                   "the report")
    write(base / "box" / "logs" / "seats" / "t" / "scp-probe-report.md",
          "another seat's", NOW + 5)
    code, stdout, stderr = run(base, f"nedlern@{FAKE_BOX}:{stored}")
    same, other, _ = sections(stdout)
    check("a query in the scp citation form is found at its exact path",
          code == 0 and "/seats/s/scp-probe-report.md" in same
          and "/seats/t/scp-probe-report.md" in other, stdout + stderr)
    code, stdout, stderr = run(base, f"ned-box:{stored}")
    check("a query naming ned-box without a user is found the same way",
          code == 0 and "/seats/s/scp-probe-report.md" in sections(stdout)[0],
          stdout + stderr)

with scratch() as directory:
    # Resolved, because a `..` query is made absolute from the current
    # directory, which the operating system reports resolved: on macOS the
    # temporary directory sits behind the /var -> /private/var link.
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    (base / "mac" / "agents" / "seat-r" / ".git").mkdir(parents=True)
    write(base / "mac" / "agents" / "seat-r" / "docs" / "rel-probe.md", "it")
    write(base / "mac" / "agents" / "seat-q" / "notes" / "rel-probe.md", "no")
    query = f"../{base.name}/mac/agents/seat-r/docs/rel-probe.md"
    code, stdout, stderr = run(base, query)
    same, other, _ = sections(stdout)
    check("a query that climbs out with .. is found at the path it names",
          code == 0 and "/seat-r/docs/rel-probe.md" in same
          and "/seat-q/notes/rel-probe.md" in other, stdout + stderr)

# --- An absolute query into a checkout that is gone, or on the other machine ----
# PR 703 review 5299114606: the same query answered found before `git worktree
# remove` and not found after it.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    write(clone / "README.md", "the clone")
    write(clone / "tail-probe.md", "a file at the clone's root")
    git(clone, "add", "README.md", "tail-probe.md")
    git(clone, "commit", "-q", "-m", "Start")
    worktree = base / "mac" / "tmp" / "-slug" / "session" / "scratchpad" / "wt"
    git(clone, "worktree", "add", "-q", "-b", "topic", str(worktree))
    write(worktree / "docs" / "lost-draft-probe.md", "the draft")
    git(worktree, "add", "docs")
    git(worktree, "commit", "-q", "-m", "Draft")
    query = str(worktree / "docs" / "lost-draft-probe.md")
    code, stdout, stderr = run(base, query)
    check("a query into a scratch worktree is found while the worktree is "
          "there", code == 0 and "Same path (docs/lost-draft-probe.md)" in stdout,
          stdout + stderr)
    git(clone, "worktree", "remove", "--force", str(worktree))
    code, stdout, stderr = run(base, query)
    same, _, _ = sections(stdout)
    check("after the worktree is removed, its commit is still found by the "
          "query's path inside the checkout",
          code == 0 and "Same path (docs/lost-draft-probe.md)" in stdout
          and "docs/lost-draft-probe.md, added" in same, stdout + stderr)
    code, stdout, stderr = run(base, str(worktree / "docs" / "tail-probe.md"))
    same, other, _ = sections(stdout)
    check("under a scratch tree a one-component tail is not trusted: the "
          "clone's own root file is a candidate, not the file",
          code == 1 and not same and "tail-probe.md" in other,
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    clone = base / "box" / "Projects" / "nedschorus"
    clone.mkdir(parents=True)
    git(clone, "init", "-q")
    write(clone / "docs" / "box-probe.md", "on the box")
    git(clone, "add", "docs")
    git(clone, "commit", "-q", "-m", "Add the probe")
    git(clone, "rm", "-q", "-r", "docs")
    git(clone, "commit", "-q", "-m", "Remove the probe")
    query = str(base / "box" / "agents" / "absent-seat" / "docs" / "box-probe.md")
    code, stdout, stderr = run(base, query)
    check("a checkout path on the other machine, whose checkout is not here, "
          "is found by the other machine's commit at that path",
          code == 0 and "Same path (docs/box-probe.md)" in stdout
          and "docs/box-probe.md, deleted" in sections(stdout)[0],
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "mac" / "agents" / "seat-z" / ".git").mkdir(parents=True)
    nested = base / "mac" / "agents" / "seat" / ".claude" / "worktrees" / "agent-x"
    commit_files(nested, {"docs/nest-probe.md": "in a nested worktree"})
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-z" / "docs" / "nest-probe.md"))
    check("a copy in a worktree nested inside a checkout is compared by its "
          "path in that worktree",
          code == 0 and "/agent-x/docs/nest-probe.md" in sections(stdout)[0],
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "elsewhere" / "repo" / ".git").mkdir(parents=True)
    write(base / "mac" / "agents" / "s" / "docs" / "out-probe.md", "a copy")
    code, stdout, stderr = run(
        base, str(base / "elsewhere" / "repo" / "docs" / "out-probe.md"))
    same, other, _ = sections(stdout)
    check("an absolute query outside every place this repository's checkouts "
          "live is found only at that very path: this repository's copy at "
          "docs/ is a candidate",
          code == 1 and not same and "/s/docs/out-probe.md" in other,
          stdout + stderr)

# --- Every place this repository's checkouts live, present and removed ---------
# Three review rounds on PR 703 (5298686798, 5299114606, 5299440729) each found
# one more place where a path's place in its checkout went wrong. This walks
# every place the map of record and `git worktree list` show a checkout
# living, on both machines, each with the worktree there and then removed, in
# every spelling a query may use. A file committed in each is found at its own
# path while the worktree is there, and by its commit on the branch that
# still holds it once the worktree is gone.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base)
    clones = {"mac": base / "mac" / "Projects" / "nedschorus",
              "box": base / "box" / "Projects" / "nedschorus"}
    for clone in clones.values():
        clone.mkdir(parents=True)
        git(clone, "init", "-q")
        write(clone / "README.md", "the clone")
        git(clone, "add", "README.md")
        git(clone, "commit", "-q", "-m", "Start")
    mac_seat = base / "mac" / "agents" / "seat-holding-nested"
    git(clones["mac"], "worktree", "add", "-q", "-b", "seat-holding-nested",
        str(mac_seat))
    alias_home = base / "mac" / "Volumes" / "nedhome"
    layouts = [
        # (label, clone, worktree, the spellings a query may use for it)
        ("a seat's checkout on the Mac", "mac",
         base / "mac" / "agents" / "seat-row", [None]),
        ("a task worktree nested in the Mac's main clone", "mac",
         clones["mac"] / ".claude" / "worktrees" / "agent-row-a", [None]),
        ("a task worktree nested in a Mac seat's checkout", "mac",
         mac_seat / ".claude" / "worktrees" / "agent-row-b", [None]),
        ("a scratch worktree on the Mac", "mac",
         base / "mac" / "tmp" / "-Users-el-agents-x" / "session" / "scratchpad"
         / "wt", [None, ("mac/tmp", "mac/private/tmp")]),
        ("an ad-hoc worktree in the Mac's tmp", "mac",
         base / "mac" / "tmp" / "adhoc-fix", [None]),
        ("a seat's checkout on ned-box", "box",
         base / "box" / "agents" / "seat-row-b",
         [None, ("box", "mac/Volumes/nedhome")]),
        ("a task worktree nested in ned-box's main clone", "box",
         clones["box"] / ".claude" / "worktrees" / "agent-row-c", [None]),
        ("a scratch worktree on ned-box", "box",
         base / "box" / "tmp" / "-home-nedlern-agents-y" / "session"
         / "scratchpad" / "wt", [None]),
    ]
    for number, (label, machine, worktree, spellings) in enumerate(layouts):
        (base / "mac" / "private").mkdir(exist_ok=True)
        if not (base / "mac" / "private" / "tmp").exists():
            (base / "mac" / "private" / "tmp").symlink_to(base / "mac" / "tmp")
        relative = f"docs/layout-row-{number}-probe.md"
        branch = f"layout-row-{number}"
        worktree.parent.mkdir(parents=True, exist_ok=True)
        git(clones[machine], "worktree", "add", "-q", "-b", branch,
            str(worktree))
        write(worktree / relative, f"row {number}")
        git(worktree, "add", "docs")
        git(worktree, "commit", "-q", "-m", f"Add the row {number} probe")
        commit = git(worktree, "rev-parse", "HEAD")
        queries = []
        for spelling in spellings:
            query = str(worktree / relative)
            if spelling:
                query = query.replace(str(base / spelling[0]),
                                      str(base / spelling[1]), 1)
            queries.append((query, "" if spelling is None
                            else f", asked as {spelling[1]}"))
        for query, asked in queries:
            code, stdout, stderr = run(base, query, plan=plan)
            same, _, _ = sections(stdout)
            check(f"{label}{asked}, worktree there: the file is found at its "
                  f"own path",
                  code == 0 and f"Same path ({relative})" in stdout
                  and str(worktree / relative).replace(str(base), "") in same,
                  stdout + stderr)
        git(clones[machine], "worktree", "remove", "--force", str(worktree))
        for query, asked in queries:
            code, stdout, stderr = run(base, query, plan=plan)
            same, _, _ = sections(stdout)
            check(f"{label}{asked}, worktree removed: its commit on the branch "
                  f"that still holds it is found",
                  code == 0 and f"Same path ({relative})" in stdout
                  and f"commit {commit[:12]}" in same
                  and f"{relative}, added" in same, stdout + stderr)
    write(clones["mac"] / "docs" / "main-clone-probe.md", "in the main clone")
    code, stdout, stderr = run(
        base, str(clones["mac"] / "docs" / "main-clone-probe.md"), plan=plan)
    check("a file in the main clone itself is found at its own path",
          code == 0 and "Same path (docs/main-clone-probe.md)" in stdout,
          stdout + stderr)

# --- Every comparison uses one spelling of each path ----------------------------
# PR 703 review 5299440729: on the Mac a scratchpad file, in no worktree, is
# listed as /private/tmp/..., and asked for as /tmp/... it was not found at
# its own path.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base)
    (base / "mac" / "private").mkdir()
    (base / "mac" / "private" / "tmp").symlink_to(base / "mac" / "tmp")
    plan["this"]["surfaces"][0]["roots"][2] = str(base / "mac" / "private"
                                                 / "tmp")
    listed = base / "mac" / "private" / "tmp" / "-Users-el-agents-z" / "s" \
        / "scratchpad" / "spelling-probe.md"
    asked = base / "mac" / "tmp" / "-Users-el-agents-z" / "s" / "scratchpad" \
        / "spelling-probe.md"
    write(asked, "a scratchpad file")
    write(base / "mac" / "tmp" / "-Users-el-agents-z" / "t" / "scratchpad"
          / "spelling-probe.md", "another session's", NOW + 5)
    code, stdout, stderr = run(base, str(asked), plan=plan)
    same, other, _ = sections(stdout)
    check("a file the search lists under one spelling of tmp is found when "
          "asked for under the other",
          code == 0 and str(listed) in same and "/t/scratchpad/" in other,
          stdout + stderr)
    code, stdout, stderr = run(base, str(listed), plan=plan)
    check("... and the other way round",
          code == 0 and str(listed) in sections(stdout)[0], stdout + stderr)
    write(base / "box" / "logs" / "seats" / "s" / "nedhome-probe.md", "stored")
    write(base / "box" / "logs" / "seats" / "t" / "nedhome-probe.md", "other")
    code, stdout, stderr = run(
        base, str(base / "mac" / "Volumes" / "nedhome" / "logs" / "seats" / "s"
                  / "nedhome-probe.md"), plan=plan)
    same, other, _ = sections(stdout)
    check("a log-store file asked for by the Mac's /Volumes/nedhome spelling "
          "of ned-box's home is found at its own path",
          code == 0 and "/box/logs/seats/s/nedhome-probe.md" in same
          and "/box/logs/seats/t/nedhome-probe.md" in other, stdout + stderr)

# --- Only this repository counts, on either side ---------------------------------
# PR 703 review 5299487158: another project's file at the same path inside its
# checkout, such as its root README.md, was found for this repository's.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    plan = make_plan(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    sibling = base / "mac" / "Projects" / "nedlern"
    for repository in (clone, sibling):
        repository.mkdir(parents=True)
        git(repository, "init", "-q")
    write(clone / "sibling-probe.md", "this repository's", NOW - 50)
    git(clone, "add", "sibling-probe.md")
    git(clone, "commit", "-q", "-m", "Add this repository's probe")
    write(sibling / "sibling-probe.md", "the sibling's", NOW - 500)
    git(sibling, "add", "sibling-probe.md")
    git(sibling, "commit", "-q", "-m", "Add the sibling's probe")
    code, stdout, stderr = run(base, str(sibling / "sibling-probe.md"),
                               plan=plan)
    same, other, _ = sections(stdout)
    check("a query into another project under Projects is found only at that "
          "path, not by this repository's copy at the same place",
          code == 0 and "/Projects/nedlern/sibling-probe.md" in same
          and "/Projects/nedschorus/sibling-probe.md" not in same
          and "Add this repository's probe" not in same, stdout + stderr)
    write(sibling / "other-repo-probe.md", "only in the sibling")
    git(sibling, "add", "other-repo-probe.md")
    git(sibling, "commit", "-q", "-m", "Add the sibling-only probe")
    git(sibling, "rm", "-q", "other-repo-probe.md")
    git(sibling, "commit", "-q", "-m", "Remove the sibling-only probe")
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-q" / "other-repo-probe.md"),
        plan=plan)
    same, other, _ = sections(stdout)
    check("another repository's commit at the same path inside its clone is "
          "a candidate for a query into this repository, not a found copy",
          code == 1 and not same and "Remove the sibling-only probe" in other,
          stdout + stderr)
    foreign = base / "mac" / "tmp" / "probe-repo"
    foreign.mkdir(parents=True)
    git(foreign, "init", "-q")
    write(foreign / "docs" / "foreign-probe.md", "a probe repository's file")
    git(foreign, "add", "docs")
    git(foreign, "commit", "-q", "-m", "Add the foreign probe")
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-q" / "docs"
                  / "foreign-probe.md"), plan=plan)
    same, other, _ = sections(stdout)
    check("a file in a scratch-tree repository that is not this one is a "
          "candidate, not a copy of this repository's path",
          code == 1 and not same and "/probe-repo/docs/foreign-probe.md" in other,
          stdout + stderr)
    code, stdout, stderr = run(
        base, str(base / "mac" / "tmp" / "-Users-el-agents-w" / "s"
                  / "scratchpad" / "wt" / "docs" / "foreign-probe.md"),
        plan=plan)
    check("a scratch query is not anchored by another repository's copies",
          code == 1 and not sections(stdout)[0], stdout + stderr)

# --- A file at a checkout's root is found only at a checkout's root -------------
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "mac" / "agents" / "seat-a" / ".git").mkdir(parents=True)
    commit_files(base / "mac" / "agents" / "seat-b",
                 {"root-probe.md": "at the root",
                  "sub/root-probe.md": "in a subdirectory"})
    os.utime(base / "mac" / "agents" / "seat-b" / "root-probe.md",
             (NOW - 50, NOW - 50))
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-a" / "root-probe.md"))
    same, other, _ = sections(stdout)
    check("a query for a checkout's root file is found by another checkout's "
          "root copy, and a copy in a subdirectory is a candidate",
          code == 0 and "/seat-b/root-probe.md" in same
          and "/seat-b/sub/root-probe.md" in other
          and "/sub/" not in same, stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    repo = base / "mac" / "Projects" / "path-repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    write(repo / "md-records" / "a-record" / "git-path-probe.md", "record")
    git(repo, "add", "md-records")
    git(repo, "commit", "-q", "-m", "Add the record")
    git(repo, "rm", "-q", "-r", "md-records")
    git(repo, "commit", "-q", "-m", "Remove the record")
    code, stdout, stderr = run(
        base, str(repo / "md-records" / "a-record" / "git-path-probe.md"))
    check("another project's commit is found for that project's own path: a "
          "git hit's path is taken inside its clone's work tree",
          code == 0 and "md-records/a-record/git-path-probe.md, deleted"
          in sections(stdout)[0], stdout + stderr)
    code, stdout, stderr = run(base, "md-records/a-record/git-path-probe.md",
                               cwd=repo)
    check("... and asked relative to that project, the same",
          code == 0 and "md-records/a-record/git-path-probe.md, deleted"
          in sections(stdout)[0], stdout + stderr)
    code, stdout, stderr = run(base, "md-records/a-record/git-path-probe.md")
    check("... but asked from outside that project it is a candidate, since "
          "the path it names is not that project's",
          code == 1 and not sections(stdout)[0]
          and "md-records/a-record/git-path-probe.md, deleted"
          in sections(stdout)[1], stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    (base / "mac" / "agents" / "seat-x" / ".git").mkdir(parents=True)
    commit_files(base / "mac" / "agents" / "seat-y",
                 {"docs/abs-probe.md": "the copy in another checkout",
                  "other/abs-probe.md": "elsewhere"})
    query = str(base / "mac" / "agents" / "seat-x" / "docs" / "abs-probe.md")
    code, stdout, stderr = run(base, query)
    same, other, _ = sections(stdout)
    check("an absolute query inside a checkout is compared by its path "
          "within that checkout, so another checkout's copy is found",
          code == 0 and "Same path (docs/abs-probe.md)" in stdout
          and "/seat-y/docs/abs-probe.md" in same
          and "/seat-y/other/abs-probe.md" in other, stdout + stderr)

# --- A file git does not track is found only at its own path --------------------
# PR 703 review 5299970582: on ned-box, /Users/el/agents/merge-lane/
# CLAUDE.local.md exited 0 on merge-lane-2's CLAUDE.local.md. A seat's
# untracked file belongs to that seat; another checkout's file at the same
# place is a different file, while a tracked one is the same file on another
# branch.
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    plan = make_plan(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    commit_files(clone, {"README.md": "the clone"}, "Start")
    seat_a = base / "mac" / "agents" / "seat-a"
    seat_b = base / "mac" / "agents" / "seat-b"
    for seat in (seat_a, seat_b):
        git(clone, "worktree", "add", "-q", "-b", seat.name, str(seat))
    write(seat_b / "CLAUDE.local.md", "You are seat-b.", NOW - 50)
    write(seat_b / ".claude" / "settings.local.json", "{}", NOW - 50)
    write(base / "box" / "agents" / "seat-c" / "CLAUDE.local.md",
          "You are seat-c.", NOW - 40)
    write(seat_b / "docs" / "drafts" / "e13-probe-draft.md", "the draft",
          NOW - 30)
    commit_files(seat_b, {"docs/tracked-probe.md": "committed in seat-b"},
                 "Add the tracked probe")

    code, stdout, stderr = run(base, str(seat_a / "CLAUDE.local.md"),
                               plan=plan)
    same, other, _ = sections(stdout)
    check("another seat's untracked CLAUDE.local.md is not found for this "
          "seat's: exit 1, listed as a candidate on either machine",
          code == 1 and not same
          and str(seat_b / "CLAUDE.local.md") in other
          and "/box/agents/seat-c/CLAUDE.local.md" in other, stdout + stderr)
    check("the candidate is marked as a file git does not track, and the "
          "agent is told to check its content and what to run next",
          "(15 bytes, not tracked by git)" in other
          and "check a candidate's content before you say it is the file"
          in stdout and "Run next `python3 " in stdout, stdout)
    code, stdout, stderr = run(base, str(seat_b / "CLAUDE.local.md"),
                               plan=plan)
    check("an untracked file is found at its own path",
          code == 0 and str(seat_b / "CLAUDE.local.md") in sections(stdout)[0]
          and "/seat-c/CLAUDE.local.md" in sections(stdout)[1],
          stdout + stderr)
    code, stdout, stderr = run(base, "CLAUDE.local.md", plan=plan)
    check("a bare file name still finds every file of that name, tracked or "
          "not",
          code == 0 and str(seat_b / "CLAUDE.local.md") in sections(stdout)[0]
          and "/seat-c/CLAUDE.local.md" in sections(stdout)[0],
          stdout + stderr)
    code, stdout, stderr = run(base, str(seat_a / "docs" / "tracked-probe.md"),
                               plan=plan)
    check("a file git tracks in another checkout is still found by its path "
          "inside the checkout",
          code == 0 and str(seat_b / "docs" / "tracked-probe.md")
          in sections(stdout)[0], stdout + stderr)
    code, stdout, stderr = run(base, ".claude/settings.local.json", plan=plan)
    check("a relative query from outside every checkout does not find a "
          "seat's untracked file: it is a candidate",
          code == 1 and ".claude/settings.local.json" in sections(stdout)[1],
          stdout + stderr)
    code, stdout, stderr = run(base, ".claude/settings.local.json", plan=plan,
                               cwd=seat_b)
    check("a relative query from inside the checkout that holds the "
          "untracked file finds it there",
          code == 0 and str(seat_b / ".claude" / "settings.local.json")
          in sections(stdout)[0], stdout + stderr)
    # Research episode E13: a draft untracked in one seat's checkout was
    # declared "never existed" from another seat's.
    code, stdout, stderr = run(base, "e13-probe-draft.md", plan=plan,
                               cwd=seat_a)
    check("E13 asked by its bare name from another seat: found",
          code == 0 and str(seat_b / "docs" / "drafts" / "e13-probe-draft.md")
          in sections(stdout)[0], stdout + stderr)
    code, stdout, stderr = run(base, "docs/drafts/e13-probe-draft.md",
                               plan=plan, cwd=seat_a)
    check("E13 asked by its relative path from another seat: listed, as a "
          "candidate, exit 1",
          code == 1 and str(seat_b / "docs" / "drafts" / "e13-probe-draft.md")
          in sections(stdout)[1], stdout + stderr)
    code, stdout, stderr = run(
        base, str(seat_b / "docs" / "drafts" / "e13-probe-draft.md"),
        plan=plan, cwd=seat_a)
    check("E13 asked by its exact path: found",
          code == 0 and str(seat_b / "docs" / "drafts" / "e13-probe-draft.md")
          in sections(stdout)[0], stdout + stderr)
    box_plan = make_plan(base, other=program.MAC_NOT_REACHABLE_FROM_NED_BOX)
    box_plan["this"], box_plan["other"] = (
        dict(box_plan["other"], machine="ned-box"),
        dict(box_plan["this"],
             not_searched_because=program.MAC_NOT_REACHABLE_FROM_NED_BOX))
    box_plan["this"].pop("not_searched_because", None)
    code, stdout, stderr = run(base, str(seat_a / "CLAUDE.local.md"),
                               plan=box_plan)
    check("run on ned-box, a Mac seat's CLAUDE.local.md is not found at a box "
          "seat's copy: exit 3, the Mac not searched",
          code == 3 and not sections(stdout)[0]
          and "/box/agents/seat-c/CLAUDE.local.md" in sections(stdout)[1],
          stdout + stderr)

with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "seat-broken" / ".git",
          "gitdir: /nowhere/.git/worktrees/seat-broken\n")
    write(base / "mac" / "agents" / "seat-broken" / "docs" / "broken-probe.md",
          "in a checkout git cannot read")
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-q" / "docs"
                  / "broken-probe.md"))
    check("a checkout where git cannot say what it tracks is reported as "
          "searched only in part, and nothing found exits 3",
          code == 3 and "so which files it tracks is unknown" in stdout
          and "/seat-broken/docs/broken-probe.md" in sections(stdout)[1],
          stdout + stderr)
    check("a file whose tracking git could not report is labelled tracking "
          "unknown, not \"not tracked by git\"",
          "bytes, tracking unknown)" in sections(stdout)[1]
          and "not tracked by git" not in stdout, stdout)
    code, stdout, stderr = run(
        base, str(base / "mac" / "agents" / "seat-broken" / "docs"
                  / "broken-probe.md"))
    check("... and it is still found at its own path",
          code == 0 and "/seat-broken/docs/broken-probe.md"
          in sections(stdout)[0], stdout + stderr)

# Under a scratch tree an untracked file sets no anchor: were it to, the
# tracked copy at the shorter path would not be found.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    commit_files(clone, {"docs/anchor-probe.md": "the tracked copy"}, "Start")
    other_worktree = base / "mac" / "tmp" / "other-wt"
    git(clone, "worktree", "add", "-q", "-b", "other-wt", str(other_worktree))
    write(other_worktree / "a" / "docs" / "anchor-probe.md", "untracked")
    code, stdout, stderr = run(
        base, str(base / "mac" / "tmp" / "gone-wt" / "a" / "docs"
                  / "anchor-probe.md"))
    same, other, _ = sections(stdout)
    check("under a scratch tree a tracked copy is found, and an untracked "
          "file at a longer path is a candidate that sets no anchor",
          code == 0 and "Same path (docs/anchor-probe.md)" in stdout
          and "/other-wt/docs/anchor-probe.md" in same
          and "/other-wt/a/docs/anchor-probe.md" in other, stdout + stderr)

# --- A relative query into a task worktree, the worktree there and removed -----
# PR 703 review 5299980640: a relative query keeping .claude/worktrees/<name>/
# was found while the worktree was there and not once it was removed. It is
# now made absolute first, so the layout list places it as it does the
# absolute spelling.
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    commit_files(clone, {"README.md": "the clone"}, "Start")
    nested = clone / ".claude" / "worktrees" / "agent-rel"
    git(clone, "worktree", "add", "-q", "-b", "agent-rel", str(nested))
    commit_files(nested, {"docs/nested-rel-probe.md": "in the task worktree"},
                 "Add the nested probe")
    query = ".claude/worktrees/agent-rel/docs/nested-rel-probe.md"
    code, stdout, stderr = run(base, query, cwd=clone)
    check("a relative query into a task worktree is found while it is there",
          code == 0 and "Same path (docs/nested-rel-probe.md)" in stdout,
          stdout + stderr)
    git(clone, "worktree", "remove", "--force", str(nested))
    code, stdout, stderr = run(base, query, cwd=clone)
    check("... and by its commit once the worktree is removed",
          code == 0 and "Same path (docs/nested-rel-probe.md)" in stdout
          and "docs/nested-rel-probe.md, added" in sections(stdout)[0],
          stdout + stderr)

# --- A relative query gets exactly its absolute spelling's answer ---------------
# PR 703 review 5307849568: relative queries had their own code path, and it
# reached the fault the untracked rule closed. `.claude/settings.local.json`
# from a seat whose own copy was absent exited 0 on another project's file
# (mac-claude, inline at :1185), and `./CLAUDE.local.md` became the bare name
# and found every seat's (Codex P1, :413-415). Every relative query is now
# made absolute before it is classified; this table holds that to be so for
# each kind of place.
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    plan = make_plan(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    commit_files(clone, {"README.md": "the clone",
                         "docs/rel-tracked-probe.md": "tracked"}, "Start")
    seat_a = base / "mac" / "agents" / "rel-seat-a"
    seat_b = base / "mac" / "agents" / "rel-seat-b"
    for seat in (seat_a, seat_b):
        git(clone, "worktree", "add", "-q", "-b", seat.name, str(seat))
    write(seat_b / "CLAUDE.local.md", "You are rel-seat-b.", NOW - 60)
    write(seat_b / ".claude" / "settings.local.json", "{}", NOW - 60)
    write(seat_b / "docs" / "drafts" / "rel-untracked-probe.md", "draft",
          NOW - 50)
    other_project = base / "mac" / "Projects" / "rel-other-project"
    write(other_project / ".claude" / "settings.local.json",
          "another project's settings", NOW - 40)
    nested = clone / ".claude" / "worktrees" / "rel-agent"
    git(clone, "worktree", "add", "-q", "-b", "rel-agent", str(nested))
    commit_files(nested, {"docs/rel-nested-probe.md": "in the task worktree"},
                 "Add the nested relative probe")
    rows = [
        # (label, current directory, relative query, expected exit code)
        ("a seat whose own untracked settings file is absent", seat_a,
         ".claude/settings.local.json", 1),
        ("./ before a seat's own untracked file, absent there", seat_a,
         "./CLAUDE.local.md", 1),
        ("./ before an untracked file the seat holds", seat_b,
         "./CLAUDE.local.md", 0),
        ("an untracked file another seat holds", seat_a,
         "docs/drafts/rel-untracked-probe.md", 1),
        ("an untracked file the seat itself holds", seat_b,
         "docs/drafts/rel-untracked-probe.md", 0),
        ("a tracked file", seat_a, "docs/rel-tracked-probe.md", 0),
        ("../ out of a subdirectory to a tracked file", seat_a / "docs",
         "../docs/rel-tracked-probe.md", 0),
        ("a task worktree nested in the main clone", clone,
         ".claude/worktrees/rel-agent/docs/rel-nested-probe.md", 0),
    ]
    for label, cwd, query, expected in rows:
        absolute = str(pathlib.Path(os.path.normpath(cwd / query)))
        code_r, stdout_r, stderr_r = run(base, query, plan=plan, cwd=cwd)
        code_a, stdout_a, stderr_a = run(base, absolute, plan=plan, cwd=cwd)
        same_r, other_r, _ = sections(stdout_r)
        same_a, other_a, _ = sections(stdout_a)
        check(f"relative and absolute agree, {label}: exit {expected}, the "
              f"same copies found and the same candidates",
              code_r == code_a == expected
              and entry_lines(same_r) == entry_lines(same_a)
              and entry_lines(other_r) == entry_lines(other_a),
              f"relative {query!r} from {cwd}: exit {code_r}\n{stdout_r}"
              f"{stderr_r}\nabsolute {absolute}: exit {code_a}\n{stdout_a}"
              f"{stderr_a}")
    code, stdout, stderr = run(base, ".claude/settings.local.json", plan=plan,
                               cwd=seat_a)
    check("another project's untracked settings file is a candidate for a "
          "seat's own path, never the copy found",
          code == 1 and not sections(stdout)[0]
          and "/rel-other-project/.claude/settings.local.json"
          in sections(stdout)[1], stdout + stderr)

# --- A relative query from a directory that no longer exists --------------------
# PR 703 review 5307798976, inline at :635: the program searched both machines
# and then died on os.getcwd() with a traceback and exit 1, the code for "not
# found, every surface searched". Agents' shells do stand in removed
# directories; two transcripts show `pwd: error retrieving current directory`.
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    make_stand_in_bin(base)
    write(base / "mac" / "agents" / "s" / "docs" / "gone-dir-probe.md",
          "a copy")
    gone = base / "removed-worktree"

    def run_in_removed_directory(query):
        gone.mkdir()
        script = (f"cd {shlex_quote(str(gone))} && rmdir "
                  f"{shlex_quote(str(gone))} && exec "
                  f"{shlex_quote(sys.executable)} "
                  f"{shlex_quote(str(PROGRAM))} {shlex_quote(query)}")
        result = subprocess.run(["sh", "-c", script], capture_output=True,
                                text=True, env=program_environment(base),
                                timeout=120)
        return result.returncode, result.stdout, result.stderr

    code, stdout, stderr = run_in_removed_directory("docs/gone-dir-probe.md")
    check("a relative query from a removed directory exits 3, says why, and "
          "searches nothing",
          code == 3 and "the current directory no longer exists" in stdout
          and "Run again with the file's absolute path" in stdout
          and "Searched:" not in stdout and "Traceback" not in stderr,
          f"exit {code}\n{stdout}{stderr}")
    code, stdout, stderr = run_in_removed_directory("./gone-dir-probe.md")
    check("... and so does ./ before a bare name",
          code == 3 and "the current directory no longer exists" in stdout,
          f"exit {code}\n{stdout}{stderr}")
    code, stdout, stderr = run_in_removed_directory("gone-dir-probe.md")
    check("a bare name needs no current directory, and is still searched "
          "from a removed one",
          code == 0 and "/agents/s/docs/gone-dir-probe.md"
          in sections(stdout)[0] and "Traceback" not in stderr,
          f"exit {code}\n{stdout}{stderr}")

# --- Which files git tracks is asked of the checkout, not of a caller's GIT_DIR --
# A leaked GIT_DIR would make `git ls-files` answer for another repository, so
# tracked_in_checkout drops the variables that point git elsewhere. The suite's
# run() drops them too, so only a call made with them set can see the strip
# go (PR 703 review 5307849568: removing it failed no case).
with scratch() as directory:
    base = pathlib.Path(directory).resolve()
    checkout = base / "checkout"
    commit_files(checkout, {"README.md": "the checkout"}, "Start")
    write(checkout / "strip-probe.md", "untracked here")
    decoy = base / "decoy"
    commit_files(decoy, {"strip-probe.md": "tracked in the decoy"}, "Decoy")
    saved = {name: os.environ.get(name) for name in GIT_REDIRECTING_VARIABLES}
    os.environ["GIT_DIR"] = str(decoy / ".git")
    os.environ["GIT_WORK_TREE"] = str(decoy)
    try:
        tracked, failure = program.tracked_in_checkout(str(checkout),
                                                       ["strip-probe.md"])
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    check("with GIT_DIR pointing at another repository, the checkout's own "
          "answer is given: the file is not tracked there",
          tracked == set() and failure is None, (tracked, failure))

# --- A worktree the main clone lists outside every root is searched ------------
# PR 703 review 5299980640: an ad-hoc worktree directly under /tmp, such as
# ned-box's /tmp/pr619-fix-round-baseline, was never searched.
with scratch() as directory:
    base = pathlib.Path(directory)
    make_stand_in_bin(base)
    clone = base / "mac" / "Projects" / "nedschorus"
    commit_files(clone, {"README.md": "the clone"}, "Start")
    adhoc = base / "elsewhere" / "adhoc-listed"
    git(clone, "worktree", "add", "-q", "-b", "adhoc-listed", str(adhoc))
    write(adhoc / "notes" / "adhoc-listed-probe.md", "only here")
    seat = base / "mac" / "agents" / "seat-listed"
    git(clone, "worktree", "add", "-q", "-b", "seat-listed", str(seat))
    write(seat / "seat-listed-probe.md", "under a root")
    gone = base / "elsewhere" / "gone-wt"
    git(clone, "worktree", "add", "-q", "-b", "gone-wt", str(gone))
    subprocess.run(["rm", "-rf", str(gone)], check=True)
    code, stdout, stderr = run(base, "adhoc-listed-probe.md")
    check("a file in a worktree the main clone lists outside every root is "
          "found, and the worktree is named in the searched lines",
          code == 0 and "/adhoc-listed/notes/adhoc-listed-probe.md"
          in sections(stdout)[0]
          and f"lists outside them: {adhoc.resolve()}" in stdout,
          stdout + stderr)
    check("a listed worktree whose directory is gone is skipped, not "
          "reported as a place not searched",
          "NOT searched" not in stdout and str(gone) not in stdout, stdout)
    code, stdout, stderr = run(base, "seat-listed-probe.md")
    check("a listed worktree under a root is searched once, not twice",
          code == 0 and len(entry_lines(sections(stdout)[0])) == 1
          and "same content" not in stdout, stdout + stderr)

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
    check("the git cap's cut is reported, with the way to narrow the answer",
          "1 older candidate path(s) were cut, past the newest "
          f"{program.MAX_GIT_PATHS_PER_CLONE} per clone" in stdout
          and "run again with more of the name" in stdout, stdout)

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
# How a query written as it is cited is read (PR 703 review 5299114606).
check("the scp form is read as the path after the colon",
      program.resolve_query("nedlern@ned-box:/home/nedlern/nedschorus-logs/a.md")
      == "/home/nedlern/nedschorus-logs/a.md")
check("a bare known host is read the same way, and its ~ is its home",
      program.resolve_query("ned-box:~/nedschorus-logs/a.md")
      == "/home/nedlern/nedschorus-logs/a.md"
      and program.resolve_query("ned-box:agents/a.md")
      == "/home/nedlern/agents/a.md")
check("a file name that merely holds a colon is left alone",
      program.resolve_query("notes:12.md") == "notes:12.md"
      and program.resolve_query("docs/at-12:30.md", cwd="/c")
      == "/c/docs/at-12:30.md")
check("a relative path after a host whose home is not known is refused, "
      "not guessed on this machine; a bare name there is still a name",
      raises(ValueError, program.resolve_query, "el@elsewhere:docs/a.md")
      and program.resolve_query("el@elsewhere:a.md") == "a.md")
check("a colon after a slash is part of a local path, not a host",
      program.resolve_query("/a/b@c:d.md") == "/a/b@c:d.md")
spellings = [spelling for machine in (program.MAC_SURFACES,
                                      program.NED_BOX_SURFACES)
             for spelling in machine["spellings"]]
check("the production spellings put /private/tmp and /Volumes/nedhome in "
      "the one spelling every comparison uses",
      program.canonical_path("/private/tmp/claude-501/a.md", spellings)
      == "/tmp/claude-501/a.md"
      and program.canonical_path("/tmp/claude-501/a.md", spellings)
      == "/tmp/claude-501/a.md"
      and program.canonical_path("/Volumes/nedhome/agents/s/a.md", spellings)
      == "/home/nedlern/agents/s/a.md"
      and program.canonical_path("/private/tmpfoo/a.md", spellings)
      == "/private/tmpfoo/a.md", spellings)
layouts = [program.MAC_SURFACES["this_repository"],
           program.NED_BOX_SURFACES["this_repository"]]
check("the production layout places each of the fleet's checkout places",
      program.place_in_this_repository(
          "/Users/el/Projects/nedschorus/.claude/worktrees/agent-a/docs/a.md",
          layouts) == ("checkout", ["docs", "a.md"])
      and program.place_in_this_repository(
          "/home/nedlern/agents/prof/.claude/worktrees/x/docs/a.md", layouts)
      == ("checkout", ["docs", "a.md"])
      and program.place_in_this_repository(
          "/Users/el/agents/merge-lane/CLAUDE.md", layouts)
      == ("checkout", ["CLAUDE.md"])
      and program.place_in_this_repository(
          "/tmp/pr619-fix-round-baseline/docs/a.md", layouts)
      == ("scratch", ["pr619-fix-round-baseline", "docs", "a.md"])
      and program.place_in_this_repository(
          "/Users/el/Projects/nedlern/README.md", layouts) is None
      and program.place_in_this_repository(
          "/home/nedlern/nedschorus-logs/seats/a.md", layouts) is None)
check("a ~ with no host is this machine's home",
      program.resolve_query("~/a.md") == os.path.expanduser("~/a.md"))
check("a path that climbs out with .. is made absolute from the current "
      "directory",
      program.resolve_query("../docs/a.md", cwd="/x/checkout/scripts")
      == "/x/checkout/docs/a.md")
check("every relative path with a / is made absolute, ./ and a plain "
      "directory path alike, and only a bare name is left as a name",
      program.resolve_query("./CLAUDE.local.md", cwd="/x/seat")
      == "/x/seat/CLAUDE.local.md"
      and program.resolve_query(".claude/settings.local.json", cwd="/x/seat")
      == "/x/seat/.claude/settings.local.json"
      and program.resolve_query("CLAUDE.local.md", cwd="/x/seat")
      == "CLAUDE.local.md")
check("a relative query's target is the same as its absolute spelling's",
      program.query_target(program.resolve_query(
          ".claude/worktrees/a/docs/b.md", cwd="/Users/el/agents/s"),
          layouts, spellings)
      == program.query_target("/Users/el/agents/s/.claude/worktrees/a/docs/b.md",
                              layouts, spellings)
      == {"kind": "checkout", "parts": ["docs", "b.md"],
          "path": "/Users/el/agents/s/.claude/worktrees/a/docs/b.md",
          "canonical": "/Users/el/agents/s/.claude/worktrees/a/docs/b.md"})

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
