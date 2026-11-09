#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/throwaway-folders-of-user-approved-kinds-delete.py.

Each case builds scratch places, a scratch approved-kinds file, a scratch process table, a scratch
home for the user-alerts and a stub `gh` in a temporary directory, never the real /tmp, ~/.cache,
/proc or ~/.local/state, and runs the program on them.

Run: python3 nc-systems/general-tools/tests/throwaway-folders-of-user-approved-kinds-delete-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parents[1]
PROGRAM = GENERAL_TOOLS / "throwaway-folders-of-user-approved-kinds-delete.py"
_specification = importlib.util.spec_from_file_location("throwaway_folders_of_user_approved_kinds_delete",
                                                        PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)
_scratch_specification = importlib.util.spec_from_file_location(
    "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common",
    GENERAL_TOOLS / "test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py")
scratch_common = importlib.util.module_from_spec(_scratch_specification)
_scratch_specification.loader.exec_module(scratch_common)

TWO_DAYS_AGO = time.time() - 2 * 86400
APPROVED = "the user, in this test"

failures = []


def check(name, condition, detail=""):
    print(("ok   " if condition else "FAIL ") + name + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


def age(path: Path, when=TWO_DAYS_AGO):
    for parent, subdirectories, files in os.walk(path):
        for name in subdirectories + files:
            os.utime(os.path.join(parent, name), (when, when), follow_symlinks=False)
    os.utime(path, (when, when), follow_symlinks=False)


class Scene:
    """A scratch machine: a tmp place, a reviewer place, a process table, a home and a stub gh."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix="throwaway-folders-delete-test-", dir=WORKSPACE))
        self.tmp = self.base / "tmp"
        self.reviewers = self.base / "reviewer-scratch"
        self.proc = self.base / "proc"
        self.home = self.base / "home"
        self.bin = self.base / "bin"
        for directory in (self.tmp, self.reviewers, self.proc, self.home, self.bin):
            directory.mkdir()
        self.kinds_file = self.base / "approved-kinds.json"
        self.kinds = [
            {"kind": "test-scratch", "place": str(self.tmp), "name": "tmp[a-z0-9_]{8}",
             "holding": "stub-bin", "only_once_its_pull_request_is_merged_or_closed": False,
             "approved": APPROVED},
            {"kind": "reviewer-scratch", "place": str(self.reviewers), "name": "rv(?P<pull_request>[0-9]+).*",
             "holding": None, "only_once_its_pull_request_is_merged_or_closed": True,
             "approved": APPROVED}]
        self.write_kinds()
        self.gh('[{"number": 100, "state": "MERGED"}, {"number": 101, "state": "OPEN"}, '
                '{"number": 102, "state": "CLOSED"}]')

    def write_kinds(self, content=None):
        self.kinds_file.write_text(content if content is not None else json.dumps({"kinds": self.kinds}))

    def gh(self, stdout, exit_status=0):
        script = self.bin / "gh"
        script.write_text(f"#!/bin/sh\ncat <<'END'\n{stdout}\nEND\necho gh says no >&2\nexit {exit_status}\n")
        script.chmod(0o755)

    def test_folder(self, name="tmpab12cd34", holding="stub-bin", old=True):
        folder = self.tmp / name
        (folder / holding).mkdir(parents=True) if holding else folder.mkdir()
        (folder / "checkout-1" / "deep").mkdir(parents=True)
        (folder / "checkout-1" / "deep" / "file").write_text("x" * 10)
        if old:
            age(folder)
        return folder

    def reviewer_folder(self, name, old=True):
        folder = self.reviewers / name
        folder.mkdir()
        (folder / "notes.md").write_text("notes")
        if old:
            age(folder)
        return folder

    def process(self, pid, cwd=None, fds=(), maps=()):
        directory = self.proc / str(pid)
        (directory / "fd").mkdir(parents=True)
        os.symlink(str(cwd or "/"), directory / "cwd")
        os.symlink("/", directory / "root")
        os.symlink("/usr/bin/python3", directory / "exe")
        for number, target in enumerate(fds):
            os.symlink(str(target), directory / "fd" / str(number))
        (directory / "maps").write_text("".join(
            f"7f00-7f01 r--p 00000000 08:01 1234                       {path}\n" for path in maps)
            + "7f02-7f03 rw-p 00000000 00:00 0 \n")

    def run(self, *extra):
        environment = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run([sys.executable, str(PROGRAM), "--approved-kinds-file", str(self.kinds_file),
                               "--proc-filesystem-directory", str(self.proc), *extra],
                              capture_output=True, text=True, timeout=120, env=environment)

    def alerts(self):
        pending = self.home / program.user_alerts.USER_ALERTS_RELATIVE_TO_HOME / "pending"
        return [json.loads(path.read_text()) for path in sorted(pending.glob("*.json"))] if pending.is_dir() else []

    def shown(self):
        path = self.home / program.KINDS_SHOWN_STATE_FILE_RELATIVE_TO_HOME
        return json.loads(path.read_text()) if path.exists() else None


def run_test_scratch_cases():
    s = Scene()
    old = s.test_folder("tmpab12cd34")
    recent = s.test_folder("tmpab12cd35", old=False)
    deep_change = s.test_folder("tmpab12cd36")
    (deep_change / "checkout-1" / "deep" / "file").write_text("changed now")
    future = s.test_folder("tmpab12cd37")
    age(future, time.time() + 60 * 86400)
    by_cwd = s.test_folder("tmpab12cd38")
    by_fd = s.test_folder("tmpab12cd39")
    by_map = s.test_folder("tmpab12cd3a")
    s.process(500, cwd=f"{by_cwd}/checkout-1 (deleted)")
    s.process(501, fds=[by_fd / "checkout-1" / "deep" / "file"])
    s.process(502, maps=[by_map / "checkout-1" / "deep" / "file"])
    # A process whose open files cannot be read is passed over, not a failure.
    s.process(503)
    (s.proc / "503" / "fd").chmod(0)
    target = s.base / "outside-target"
    (target / "stub-bin").mkdir(parents=True)
    age(target)
    os.symlink(target, s.tmp / "tmpab12cd3b")
    # A sibling whose name starts with an approved folder's name is not inside it.
    s.process(504, cwd=f"{old}-other")
    result = s.run()
    check("a test scratch directory unchanged for 24 hours, owned and unused is deleted, and the "
          "deletion is logged", not old.exists() and f"deleting {old} (kind test-scratch)" in result.stdout
          and result.returncode == 0, result.stdout + result.stderr)
    check("a folder changed in the last 24 hours is kept", recent.is_dir())
    check("a folder whose newest change is deep inside it is kept", deep_change.is_dir())
    check("a folder with a modification time in the future is kept", future.is_dir())
    check("a folder a process has as its working directory, even deleted, is kept", by_cwd.is_dir())
    check("a folder holding a file a process has open is kept", by_fd.is_dir())
    check("a folder holding a file a process has mapped into memory is kept", by_map.is_dir())
    check("the summary counts the deleted and the in-use folders",
          "throwaway folders deleted: 1;" in result.stdout and "kept because a process uses them: 3;" in result.stdout,
          result.stdout)
    check("a symbolic link named as an approved folder is not followed and not deleted",
          (s.tmp / "tmpab12cd3b").is_symlink() and (target / "stub-bin").is_dir())

    s = Scene()
    no_stub = s.test_folder("tmpab12cd34", holding=None)
    result = s.run()
    check("a folder of the approved name that does not hold the named entry is kept, as an unapproved kind",
          no_stub.is_dir() and f"kept, of the unapproved kind tmp* in {s.tmp}: 1 folders" in result.stdout,
          result.stdout)

    s = Scene()
    folder = s.test_folder()
    result = s.run("--dry-run")
    check("--dry-run deletes nothing, writes no user-alert and records no kind",
          folder.is_dir() and f"would delete {folder}" in result.stdout and s.alerts() == []
          and s.shown() is None and "that would be deleted: 1" in result.stdout, result.stdout)


def run_reviewer_cases():
    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    merged_other_tag = s.reviewer_folder("rv100-r2")
    still_open = s.reviewer_folder("rv101")
    closed = s.reviewer_folder("rv102m")
    unknown = s.reviewer_folder("rv999")
    recent_merged = s.reviewer_folder("rv100r3", old=False)
    result = s.run()
    check("a reviewer scratch directory whose pull request is merged or closed is deleted",
          not merged.exists() and not merged_other_tag.exists() and not closed.exists(),
          result.stdout + result.stderr)
    check("a reviewer scratch directory whose pull request is open is kept and counted",
          still_open.is_dir() and "kept because their pull request is open: 1;" in result.stdout, result.stdout)
    check("a reviewer scratch directory of a merged pull request changed in the last 24 hours is kept",
          recent_merged.is_dir())
    check("a pull request the listing does not hold keeps its folder, is a failure and exits 1",
          unknown.is_dir() and f"{unknown} was kept: pull request 999" in result.stderr
          and result.returncode == 1, result.stderr)

    for name, stdout, exit_status, expected in (
            ("exits 1", "", 1, "exited 1: gh says no"),
            ("prints something other than a list", '{"not": "a list"}', 0, "printed something other than"),
            ("prints entries without a state", '[{"number": 100}]', 0, "printed something other than")):
        s = Scene()
        s.gh(stdout, exit_status)
        merged = s.reviewer_folder("rv100r1")
        test_folder = s.test_folder()
        result = s.run()
        check(f"when gh {name}, every reviewer scratch directory is kept, the failure says why, the other "
              "kinds are still deleted, and the run exits 1",
              merged.is_dir() and expected in result.stderr and "its pull request's state could not be "
              "looked up" in result.stderr and not test_folder.exists() and result.returncode == 1
              and program.FAILURES_INSTRUCTION in result.stderr, result.stderr)

    s = Scene()
    s.test_folder()
    shutil.rmtree(s.bin)
    s.bin.mkdir()
    result = s.run()
    check("no gh is asked for when no reviewer scratch directory is a candidate", result.returncode == 0,
          result.stderr)

    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    environment = dict(os.environ, HOME=str(s.home), PATH="/nonexistent")
    result = subprocess.run([sys.executable, str(PROGRAM), "--approved-kinds-file", str(s.kinds_file),
                             "--proc-filesystem-directory", str(s.proc)],
                            capture_output=True, text=True, timeout=120, env=environment)
    check("when gh cannot be run, the reviewer scratch directory is kept and the failure says so",
          merged.is_dir() and "could not be run" in result.stderr and result.returncode == 1, result.stderr)


def run_kinds_file_cases():
    s = Scene()
    folder = s.test_folder()
    good = json.loads(s.kinds_file.read_text())

    def variant(change):
        content = json.loads(json.dumps(good))
        change(content["kinds"][1])
        return json.dumps(content)
    for name, content, expected in (
            ("not JSON", "{", "could not be read as JSON"),
            ("with no kinds list", '{"kinds": {}}', "holds no `kinds` list"),
            ("a JSON list", "[]", "holds no `kinds` list"),
            ("with a kind lacking a field", variant(lambda kind: kind.pop("approved")), "does not have exactly"),
            ("with a kind with an extra field", variant(lambda kind: kind.update(extra=1)), "does not have exactly"),
            ("with a bad expression", variant(lambda kind: kind.update(name="rv(")), "is not a regular expression"),
            ("with a pull request condition and no group",
             variant(lambda kind: kind.update(name="rv[0-9]+")), "has no group `pull_request`"),
            ("with a condition that is not true or false",
             variant(lambda kind: kind.update(only_once_its_pull_request_is_merged_or_closed="yes")),
             "must be true or false"),
            ("with a place that is not a string", variant(lambda kind: kind.update(place=3)), "`place` must be"),
            ("with a holding that is not a string or null", variant(lambda kind: kind.update(holding=[])),
             "`place` must be")):
        s.write_kinds(content)
        result = s.run()
        check(f"an approved-kinds file {name} deletes nothing and exits 1",
              folder.is_dir() and f"nothing was deleted: " in result.stderr and expected in result.stderr
              and result.returncode == 1, result.stderr)
    s.kinds_file.unlink()
    result = s.run()
    check("a missing approved-kinds file deletes nothing and exits 1",
          folder.is_dir() and "could not be read as JSON" in result.stderr and result.returncode == 1)

    kinds = program.approved_kinds_read(GENERAL_TOOLS / "throwaway-folder-kinds-the-user-approved-for-deletion.json")
    check("the approved-kinds file in the repository is well formed and holds the two approved kinds",
          [kind["kind"] for kind in kinds] == ["cold-read-test-scratch-directory-in-tmp",
                                               "merge-lane-pull-request-reviewer-scratch-directory"]
          and kinds[1]["place_path"] == Path.home() / ".cache" / "merge-lane-pull-request-reviewer-scratch-directories"
          and kinds[0]["pattern"].fullmatch("tmp0_cehx43") and not kinds[0]["pattern"].fullmatch("tmp.0_cehx43")
          and kinds[1]["pattern"].fullmatch("rv1644r2b").group("pull_request") == "1644",
          str(kinds))


def run_unreadable_cases():
    s = Scene()
    unreadable = s.test_folder("tmpab12cd34")
    readable = s.test_folder("tmpab12cd35")
    (unreadable / "checkout-1").chmod(0)
    result = s.run()
    (unreadable / "checkout-1").chmod(0o755)
    check("a folder whose tree cannot be read in full is kept, named as a failure, and the others go on",
          unreadable.is_dir() and f"{unreadable} was kept: it could not be read in full" in result.stderr
          and not readable.exists() and result.returncode == 1, result.stderr)

    s = Scene()
    folder = s.test_folder()
    (folder / "checkout-1").chmod(0o555)
    result = s.run()
    (folder / "checkout-1").chmod(0o755)
    check("a folder that cannot be deleted in full is a failure and exits 1",
          f"{folder} could not be deleted in full" in result.stderr and result.returncode == 1, result.stderr)

    s = Scene()
    folder = s.reviewer_folder("rv100r1")
    s.tmp.rmdir()
    result = s.run()
    check("a place that cannot be listed is named as not checked, and the places after it go on",
          f"{s.tmp} was not checked: it could not be listed" in result.stderr and not folder.exists()
          and result.returncode == 1, result.stderr)

    s = Scene()
    vanishing, after = s.test_folder("tmpab12cd34"), s.test_folder("tmpab12cd35")
    tree_measure = program.tree_measure

    def gone_during_the_run(folder):
        if folder == vanishing:
            raise FileNotFoundError(2, "No such file or directory", str(folder))
        return tree_measure(folder)
    program.tree_measure = gone_during_the_run
    try:
        result = program.throwaway_folders_of_user_approved_kinds_delete(
            s.kinds_file, s.base / "shown.json", s.proc, dry_run=False)
    finally:
        program.tree_measure = tree_measure
    check("a folder that disappears during the run is passed over, and the folders after it go on",
          vanishing.is_dir() and not after.exists() and result["failures"] == [] and result["deleted"] == 1,
          str(result))

    s = Scene()
    s.gh("[]", 1)
    (s.bin / "gh").write_text("#!/bin/sh\nkill -9 $$\n")
    folder = s.reviewer_folder("rv100r1")
    result = s.run()
    check("a gh killed by a signal keeps the reviewer scratch directory and is a failure",
          folder.is_dir() and "exited -9" in result.stderr and result.returncode == 1, result.stderr)

    s = Scene()
    (s.bin / "gh").write_text("#!/bin/sh\nprintf 'x%.0s' $(seq 300) >&2\nexit 1\n")
    s.reviewer_folder("rv100r1")
    result = s.run()
    check("gh's error text is quoted up to 200 characters",
          "x" * 200 in result.stderr and "x" * 201 not in result.stderr, result.stderr)

    s = Scene()
    used = s.test_folder("tmpab12cd34")
    # Pid 100 has no working directory, root, executable or memory map to read; pid 200 uses the folder.
    (s.proc / "100" / "fd").mkdir(parents=True)
    os.symlink(str(used / "stub-bin"), s.proc / "100" / "fd" / "0")
    s.process(200, cwd=used)
    result = s.run()
    check("a process whose links or memory map cannot be read is passed over, and its other links and "
          "the processes after it are still read", used.is_dir() and "kept because a process uses them: 1;"
          in result.stdout, result.stdout + result.stderr)

    s = Scene()
    folder = s.test_folder()
    shutil.rmtree(s.proc)
    result = s.run()
    check("a process table that cannot be listed deletes nothing and exits 1",
          folder.is_dir() and "nothing was deleted and no kind was shown: the process table" in result.stderr
          and result.returncode == 1, result.stderr)

    s = Scene()
    s.test_folder()
    getuid = os.getuid
    os.getuid = lambda: getuid() + 1
    try:
        result = program.throwaway_folders_of_user_approved_kinds_delete(
            s.kinds_file, s.base / "shown.json", s.proc, dry_run=True)
    finally:
        os.getuid = getuid
    check("a folder another account owns is neither deleted nor shown",
          result["deleted"] == 0 and result["unapproved"] == {} and result["failures"] == [], str(result))


def run_unapproved_kind_cases():
    s = Scene()
    for name in ("pymp-a1b2c3d4", "pymp-zz99yy88", "meaning-check-test-0a1b2c3d", "rv2144-probe-x",
                 "claude-" + str(os.getuid()), "run-all-test-suites-a1b2c3d4", "rts-a1b2c3d4"):
        folder = s.tmp / name
        folder.mkdir()
        age(folder)
    in_use = s.tmp / "pymp-inuse123"
    in_use.mkdir()
    age(in_use)
    s.process(600, cwd=in_use)
    young = s.tmp / "young-test-a1b2c3d4"
    young.mkdir()
    result = s.run()
    check("unapproved leftovers are kept and printed by kind, with counts",
          f"kept, of the unapproved kind pymp-* in {s.tmp}: 2 folders, 2 files" in result.stdout
          and f"kept, of the unapproved kind meaning-check-test-* in {s.tmp}: 1 folders" in result.stdout
          and f"kept, of the unapproved kind rv* in {s.tmp}: 1 folders" in result.stdout
          and "unapproved kinds: 3;" in result.stdout and (s.tmp / "pymp-a1b2c3d4").is_dir(), result.stdout)
    check("folders another program removes, folders in use and young folders are not shown",
          "claude-" not in result.stdout.replace("kinds", "") and "run-all-test-suites" not in result.stdout
          and "rts-" not in result.stdout and "pymp-inuse" not in result.stdout and "young" not in result.stdout,
          result.stdout)
    alerts = s.alerts()
    check("each new unapproved kind is raised in one user-alert, with its place, count and size",
          len(alerts) == 3 and any(alert["title"].endswith(f"pymp-* in {s.tmp}") and "2 folders" in alert["alert_text"]
                                   and "pymp-a1b2c3d4, pymp-zz99yy88" in alert["alert_text"]
                                   and alert["action"] == program.ALERT_ACTION_TEXT for alert in alerts),
          json.dumps(alerts))
    check("each raised kind is recorded as shown",
          sorted(s.shown()) == sorted(f"{s.tmp}/{kind}" for kind in ("pymp-*", "meaning-check-test-*", "rv*")),
          str(s.shown()))
    (s.tmp / "new-kind-test-a1b2c3d4").mkdir()
    age(s.tmp / "new-kind-test-a1b2c3d4")
    result = s.run()
    check("a second run raises only the kind it had not raised before",
          len(s.alerts()) == 4 and "unapproved kinds: 4;" in result.stdout and result.returncode == 0,
          result.stdout + result.stderr)

    check("the kind rule replaces mkdtemp's and mktemp's suffixes, else cuts at the first digit",
          [program.unapproved_kind_of(name) for name in (
              "pymp-a1b2c3d4", "tmpab_12cde", "find-copies-test_a1b2c3d4", "tmp.Xq3vT9aBcD",
              "rv2144r1", "cold-read-research-ghi", "xtmpab_12cde", "tmpab_12cdef")]
          == ["pymp-*", "tmp*", "find-copies-test_*", "tmp.*", "rv*", "cold-read-research-ghi", "xtmpab_*",
              "tmpab_*"])

    s = Scene()
    folder = s.tmp / "pymp-a1b2c3d4"
    folder.mkdir()
    age(folder)
    state = s.home / program.KINDS_SHOWN_STATE_FILE_RELATIVE_TO_HOME
    state.parent.mkdir(parents=True)
    state.write_text("[]")
    result = s.run()
    check("a state file that holds no JSON object writes no user-alert and is a failure",
          s.alerts() == [] and "no user-alert was written for a new kind: the state file" in result.stderr
          and result.returncode == 1, result.stderr)
    state.write_text("{")
    result = s.run()
    check("a state file that is not JSON writes no user-alert and is a failure",
          s.alerts() == [] and "could not be read as JSON" in result.stderr and result.returncode == 1,
          result.stderr)

    s = Scene()
    folder = s.tmp / "pymp-a1b2c3d4"
    folder.mkdir()
    age(folder)
    alerts_directory = s.home / program.user_alerts.USER_ALERTS_RELATIVE_TO_HOME
    alerts_directory.mkdir(parents=True)
    alerts_directory.chmod(0o555)
    result = s.run()
    alerts_directory.chmod(0o755)
    check("a user-alert that cannot be written is a failure, and the kind is not recorded as shown",
          "the user-alert for kind" in result.stderr and s.shown() is None and result.returncode == 1,
          result.stderr)


WORKSPACE = scratch_common.scratch_directory_after_removing_ones_killed_runs_left(
    "throwaway-folders-delete-test-workspace-")
try:
    run_test_scratch_cases()
    run_reviewer_cases()
    run_kinds_file_cases()
    run_unreadable_cases()
    run_unapproved_kind_cases()
finally:
    for directory, subdirectories, _ in os.walk(WORKSPACE):
        for name in subdirectories:
            try:
                os.chmod(os.path.join(directory, name), 0o755, follow_symlinks=False)
            except (OSError, NotImplementedError):
                pass
    shutil.rmtree(WORKSPACE, ignore_errors=True)

print(f"{len(failures)} failures" if failures else "all cases passed")
sys.exit(1 if failures else 0)
