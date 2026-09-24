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
    for variable in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
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
    for variable in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
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


def sections(stdout):
    """(same-name list, other-names list, everything from Searched on)."""
    same = other = ""
    head, _, tail = stdout.partition("\nSearched:")
    if "Other names containing" in head:
        head, _, other = head.partition("Other names containing")
    if "Same name (" in head:
        same = head.split("Same name (", 1)[1]
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
    plan = make_plan(base, extra_mac_roots=[str(base / "absent-root")])
    code, stdout, stderr = run(base, "nothing-anywhere.md", plan=plan)
    check("nothing found with every surface searched exits 1",
          code == 1, stdout + stderr)
    check("a .git directory with no HEAD is skipped, not reported as a "
          "failure", "git log in" not in stdout and "NOT searched" not in stdout,
          stdout)
    check("a root that does not exist is shown as absent, not as a failure",
          f"{base / 'absent-root'} (absent)" in stdout, stdout)
    check("nothing found names the backup search as the next command",
          "run next `scripts/find-deleted-path-across-backups.py "
          "nothing-anywhere.md`" in stdout, stdout)
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
    print("skip  an unreadable directory (running as root reads everything)")
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
