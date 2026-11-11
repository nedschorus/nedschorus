#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete.py.

Each case builds a scratch tmp place, a scratch reviewer scratch place, a scratch process table, a
scratch home, a scratch deleted-folders log and a stub `gh` in a temporary directory, never the
real /tmp, ~/.cache, /proc or log-store, and runs the program on them.

Run: python3 nc-systems/general-tools/tests/tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parents[1]
PROGRAM = GENERAL_TOOLS / "tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete.py"
_specification = importlib.util.spec_from_file_location(
    "tmp_and_reviewer_scratch_folders_unchanged_a_day_and_unused_delete", PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)
scratch_common = program.test_scratch

TWO_DAYS_AGO = time.time() - 2 * 86400
UNIX_SOCKET_TABLE_HEADER = "Num       RefCount Protocol Flags    Type St Inode Path\n"

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
    """A scratch machine: a tmp place, a reviewer place, a process table, a home, a log and a stub gh."""

    def __init__(self):
        # Resolved, as the program resolves each place: the test sandbox's TMPDIR is a symlink.
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix="tmp-and-reviewer-scratch-delete-test-",
                                                           dir=WORKSPACE)))
        self.tmp = self.base / "tmp"
        self.reviewers = self.base / "reviewer-scratch"
        self.proc = self.base / "proc"
        self.home = self.base / "home"
        self.bin = self.base / "bin"
        for directory in (self.tmp, self.reviewers, self.proc / "net", self.home, self.bin):
            directory.mkdir(parents=True)
        self.log = self.base / "log-store" / "deleted-log" / "ned-box.txt"
        self.sockets()
        self.gh('[{"number": 100, "state": "MERGED"}, {"number": 101, "state": "OPEN"}, '
                '{"number": 102, "state": "CLOSED"}]')

    def sockets(self, *paths):
        (self.proc / "net" / "unix").write_text(
            UNIX_SOCKET_TABLE_HEADER
            + "0000000000000000: 00000002 00000000 00010000 0001 01 14604 @abstract-socket\n"
            + "0000000000000000: 00000003 00000000 00000000 0001 03 14605\n"
            + "".join(f"0000000000000000: 00000002 00000000 00010000 0001 01 1483{number} {path}\n"
                      for number, path in enumerate(paths)))

    def gh(self, stdout, exit_status=0):
        script = self.bin / "gh"
        script.write_text(f"#!/bin/sh\ncat <<'END'\n{stdout}\nEND\necho gh says no >&2\nexit {exit_status}\n")
        script.chmod(0o755)

    def folder(self, name, place=None, old=True):
        folder = (place or self.tmp) / name
        (folder / "checkout-1" / "deep").mkdir(parents=True)
        (folder / "checkout-1" / "deep" / "file").write_text("x" * 10)
        if old:
            age(folder)
        return folder

    def reviewer_folder(self, name, old=True):
        return self.folder(name, self.reviewers, old)

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

    def arguments(self, *extra):
        return [sys.executable, str(PROGRAM), "--tmp-directory-whose-folders-are-swept", str(self.tmp),
                "--merge-lane-pull-request-reviewer-scratch-directories-parent-directory", str(self.reviewers),
                "--deleted-folders-log-file", str(self.log), "--proc-filesystem-directory", str(self.proc), *extra]

    def run(self, *extra, path=None):
        environment = dict(os.environ, HOME=str(self.home), PATH=path or f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run(self.arguments(*extra), capture_output=True, text=True, timeout=120,
                              env=environment)

    def sweep(self, dry_run=False):
        return program.tmp_and_reviewer_scratch_folders_unchanged_a_day_and_unused_delete(
            self.tmp, self.reviewers, self.log, self.proc, dry_run=dry_run)

    def logged(self):
        return [line.split("\t")[1:] for line in self.log.read_text().splitlines()] if self.log.exists() else []


def run_tmp_place_cases():
    s = Scene()
    pymp, bare, rts = s.folder("pymp-a1b2c3d4"), s.folder("x"), s.folder("rts-a1b2c3d4")
    recent = s.folder("young-test-a1b2c3d4", old=False)
    deep_change = s.folder("cold-read-research-ghi")
    (deep_change / "checkout-1" / "deep" / "file").write_text("changed now")
    future = s.folder("tmp.Xq3vT9aBcD")
    age(future, time.time() + 60 * 86400)
    by_cwd, by_fd, by_map = s.folder("by-cwd"), s.folder("by-fd"), s.folder("by-map")
    by_socket = s.folder("tmux-1000")
    s.process(500, cwd=f"{by_cwd}/checkout-1 (deleted)")
    s.process(501, fds=[by_fd / "checkout-1" / "deep" / "file"])
    s.process(502, maps=[by_map / "checkout-1" / "deep" / "file"])
    by_unnormalized_socket = s.folder("tmux-1001")
    by_socket_through_link = s.folder("tmux-1002")
    by_double_slash_socket = s.folder("tmux-1003")
    s.sockets(by_socket / "merge-lane-2", f"{s.tmp}//tmux-1001/./default",
              f"{s.tmp}/tmux-1002/link/../../default", f"/{s.tmp}/tmux-1003/default")
    # A process whose open files cannot be read is passed over, not a failure.
    s.process(503)
    (s.proc / "503" / "fd").chmod(0)
    target = s.base / "outside-target"
    target.mkdir()
    age(target)
    os.symlink(target, s.tmp / "linked")
    age(s.tmp / "linked")
    a_file = s.tmp / "a-file"
    a_file.write_text("x")
    age(a_file)
    claude_code = s.folder(f"claude-{os.getuid()}")
    # A sibling whose name starts with a deletable folder's name is not inside it.
    s.process(504, cwd=f"{pymp}-other")
    result = s.run()
    check("folders whose names match no kind, unchanged for 24 hours, owned and unused are deleted",
          not pymp.exists() and not bare.exists() and not rts.exists() and result.returncode == 0,
          result.stdout + result.stderr)
    check("each deletion is printed", all(f"deleting {folder}" in result.stdout for folder in (pymp, bare, rts)),
          result.stdout)
    check("the deleted-folders log lists each deleted folder and nothing else",
          sorted(s.logged()) == sorted(["deleting", str(folder)] for folder in (bare, pymp, rts)), str(s.logged()))
    check("no user-alert or other file is written in the home directory", list(s.home.rglob("*")) == [])
    check("a folder changed in the last 24 hours is kept", recent.is_dir())
    check("a folder whose newest change is deep inside it is kept", deep_change.is_dir())
    check("a folder with a modification time in the future is kept", future.is_dir())
    check("a folder a process has as its working directory, even deleted, is kept", by_cwd.is_dir())
    check("a folder holding a file a process has open is kept", by_fd.is_dir())
    check("a folder holding a file a process has mapped into memory is kept", by_map.is_dir())
    check("a folder holding a bound unix socket, such as tmux's, is kept", by_socket.is_dir())
    check("a folder holding a unix socket bound under a path with // or /./ in it is kept",
          by_unnormalized_socket.is_dir())
    check("a folder holding a unix socket bound through a symbolic link followed by .. is kept",
          by_socket_through_link.is_dir())
    check("a folder holding a unix socket bound under a path starting with exactly two slashes is kept",
          by_double_slash_socket.is_dir())
    check("the summary counts the deleted and the in-use folders",
          "throwaway folders deleted: 3;" in result.stdout and "kept because a process uses them: 7;" in result.stdout,
          result.stdout)
    check("a symbolic link is not followed and not deleted", (s.tmp / "linked").is_symlink() and target.is_dir())
    check("a file is not deleted", a_file.is_file())
    check("the claude-<uid> folder the first step looks after is kept", claude_code.is_dir())

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    result = s.run("--dry-run")
    check("--dry-run deletes nothing and writes nothing to the log",
          folder.is_dir() and f"would delete {folder}" in result.stdout and not s.log.exists()
          and "that would be deleted: 1" in result.stdout, result.stdout)

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    getuid = os.getuid
    os.getuid = lambda: getuid() + 1
    try:
        result = s.sweep(dry_run=True)
    finally:
        os.getuid = getuid
    check("a folder another account owns is kept", result["deleted"] == 0 and result["failures"] == [], str(result))


def run_reviewer_cases():
    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    merged_other_tag = s.reviewer_folder("rv100-r2")
    still_open = s.reviewer_folder("rv101")
    closed = s.reviewer_folder("rv102m")
    unknown = s.reviewer_folder("rv999")
    recent_merged = s.reviewer_folder("rv100r3", old=False)
    no_number = s.reviewer_folder("notes-of-a-reviewer")
    in_tmp = s.folder("rv101")
    result = s.run()
    check("a reviewer scratch directory whose pull request is merged or closed is deleted and logged",
          not merged.exists() and not merged_other_tag.exists() and not closed.exists()
          and ["deleting", str(closed)] in s.logged(), result.stdout + result.stderr)
    check("a reviewer scratch directory whose pull request is open is kept and counted",
          still_open.is_dir() and "kept because their pull request is open: 1;" in result.stdout, result.stdout)
    check("a reviewer scratch directory of a merged pull request changed in the last 24 hours is kept",
          recent_merged.is_dir())
    check("a pull request the listing does not hold keeps its folder, is a failure and exits 1",
          unknown.is_dir() and f"{unknown} was kept: pull request 999" in result.stderr
          and result.returncode == 1, result.stderr)
    check("a folder in the reviewer scratch place whose name gives no number is deleted", not no_number.exists())
    check("a folder in the tmp place named as an open pull request's reviewer folder is deleted",
          not in_tmp.exists())

    for name, stdout, exit_status, expected in (
            ("exits 1", "", 1, "exited 1: gh says no"),
            ("prints something other than a list", '{"not": "a list"}', 0, "printed something other than"),
            ("prints entries without a state", '[{"number": 100}]', 0, "printed something other than")):
        s = Scene()
        s.gh(stdout, exit_status)
        merged = s.reviewer_folder("rv100r1")
        tmp_folder = s.folder("pymp-a1b2c3d4")
        result = s.run()
        check(f"when gh {name}, every reviewer scratch directory is kept, the failure says why, the other "
              "folders are still deleted, and the run exits 1",
              merged.is_dir() and expected in result.stderr and "its pull request's state could not be "
              "looked up" in result.stderr and not tmp_folder.exists() and result.returncode == 1
              and program.FAILURES_INSTRUCTION in result.stderr, result.stderr)

    s = Scene()
    s.folder("pymp-a1b2c3d4")
    s.reviewer_folder("notes-of-a-reviewer")
    shutil.rmtree(s.bin)
    s.bin.mkdir()
    result = s.run()
    check("no gh is asked for when no folder names a pull request", result.returncode == 0, result.stderr)

    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    result = s.run(path="/nonexistent")
    check("when gh cannot be run, the reviewer scratch directory is kept and the failure says so",
          merged.is_dir() and "could not be run" in result.stderr and result.returncode == 1, result.stderr)

    # The lookup can take minutes; what happens to a folder meanwhile must still be seen.
    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    gh = s.bin / "gh"
    gh.write_text(f"#!/bin/sh\nmkdir -p '{s.proc}/300/fd'\nln -s '{merged}' '{s.proc}/300/cwd'\n"
                  + gh.read_text().split("\n", 1)[1])
    result = s.run()
    check("a process that starts using a reviewer scratch directory while its pull request is looked up "
          "keeps it", merged.is_dir() and "kept because a process uses them: 1;" in result.stdout,
          result.stdout + result.stderr)

    s = Scene()
    merged = s.reviewer_folder("rv100r1")
    gh = s.bin / "gh"
    gh.write_text(f"#!/bin/sh\necho changed > '{merged}/checkout-1/deep/file'\n" + gh.read_text().split("\n", 1)[1])
    result = s.run()
    check("a reviewer scratch directory changed while its pull request is looked up is kept",
          merged.is_dir() and "deleted: 0;" in result.stdout, result.stdout + result.stderr)

    # /proc gives each process's paths with symlinks resolved, so a place named through one must be too.
    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    linked_place = s.base / "tmp-by-a-symlink"
    os.symlink(str(s.tmp), linked_place)
    s.process(300, cwd=os.path.realpath(folder))
    result = program.tmp_and_reviewer_scratch_folders_unchanged_a_day_and_unused_delete(
        linked_place, s.reviewers, s.log, s.proc, dry_run=False)
    check("a place named through a symlink is compared with the process table's resolved paths",
          folder.is_dir() and result["kept_in_use"] == 1, str(result))


def run_unreadable_cases():
    s = Scene()
    unreadable = s.folder("pymp-a1b2c3d4")
    readable = s.folder("pymp-a1b2c3d5")
    (unreadable / "checkout-1").chmod(0)
    result = s.run()
    (unreadable / "checkout-1").chmod(0o755)
    check("a folder whose tree cannot be read in full is kept, named as a failure, and the others go on",
          unreadable.is_dir() and f"{unreadable} was kept: it could not be read in full" in result.stderr
          and not readable.exists() and result.returncode == 1, result.stderr)

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    (folder / "checkout-1").chmod(0o555)
    result = s.run()
    (folder / "checkout-1").chmod(0o755)
    check("a folder that cannot be deleted in full is a failure and exits 1",
          f"{folder} could not be deleted in full" in result.stderr and result.returncode == 1, result.stderr)

    s = Scene()
    first, second = s.folder("pymp-a1b2c3d4"), s.folder("pymp-a1b2c3d5")
    s.log.parent.mkdir(parents=True)
    s.log.parent.chmod(0o555)
    result = s.run()
    s.log.parent.chmod(0o755)
    check("a deleted-folders log that cannot be written keeps the folder and every one after it, and exits 1",
          first.is_dir() and second.is_dir() and f"{first} and every folder after it were kept: the "
          "deleted-folders log could not be written" in result.stderr and "deleted: 0;" in result.stdout
          and result.returncode == 1, result.stdout + result.stderr)

    s = Scene()
    folder = s.reviewer_folder("rv100r1")
    s.tmp.rmdir()
    result = s.run()
    check("a place that cannot be listed is named as not checked, and the places after it go on",
          f"{s.tmp} was not checked: it could not be listed" in result.stderr and not folder.exists()
          and result.returncode == 1, result.stderr)

    s = Scene()
    vanishing, after = s.folder("pymp-a1b2c3d4"), s.folder("pymp-a1b2c3d5")
    newest_modification_time_in_tree = scratch_common.newest_modification_time_in_tree

    def gone_during_the_run(folder):
        if folder == vanishing:
            raise FileNotFoundError(2, "No such file or directory", str(folder))
        return newest_modification_time_in_tree(folder)
    scratch_common.newest_modification_time_in_tree = gone_during_the_run
    try:
        result = s.sweep()
    finally:
        scratch_common.newest_modification_time_in_tree = newest_modification_time_in_tree
    check("a folder that disappears during the run is passed over, and the folders after it go on",
          vanishing.is_dir() and not after.exists() and result["failures"] == [] and result["deleted"] == 1,
          str(result))

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    scandir = os.scandir

    class EntryGoneAtItsStat:
        def __init__(self, entry):
            self.entry, self.name, self.path = entry, entry.name, entry.path

        def is_dir(self, follow_symlinks):
            raise FileNotFoundError(2, "No such file or directory", self.path)

    program.os.scandir = lambda place: [EntryGoneAtItsStat(entry) for entry in scandir(place)]
    try:
        result = s.sweep()
    finally:
        program.os.scandir = scandir
    check("an entry that disappears between the listing and its stat is passed over, not a failure",
          folder.is_dir() and result["failures"] == [] and result["deleted"] == 0, str(result))

    s = Scene()
    unstatable, after = s.folder("pymp-a1b2c3d4"), s.folder("pymp-a1b2c3d5")

    class EntryWhoseStatIsRefused:
        def __init__(self, entry):
            self.entry, self.name, self.path = entry, entry.name, entry.path

        def is_dir(self, follow_symlinks):
            return self.entry.is_dir(follow_symlinks=follow_symlinks)

        def stat(self, follow_symlinks):
            if self.path == str(unstatable):
                raise PermissionError(13, "Permission denied", self.path)
            return self.entry.stat(follow_symlinks=follow_symlinks)

    # program.os is os, which os.walk also lists with, so only the two places' listings are wrapped.
    program.os.scandir = lambda place: ([EntryWhoseStatIsRefused(entry) for entry in scandir(place)]
                                        if place in (s.tmp, s.reviewers) else scandir(place))
    try:
        result = s.sweep()
    finally:
        program.os.scandir = scandir
    check("an entry whose stat fails for another reason is kept, named as a failure, and the others go on",
          unstatable.is_dir() and not after.exists()
          and result["failures"] == [f"{unstatable} was kept: it could not be checked: Permission denied"],
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
    by_fd, by_cwd = s.folder("pymp-a1b2c3d4"), s.folder("pymp-a1b2c3d5")
    # Pid 100 has no working directory, root, executable or memory map to read, only an open file.
    (s.proc / "100" / "fd").mkdir(parents=True)
    os.symlink(str(by_fd / "checkout-1"), s.proc / "100" / "fd" / "0")
    s.process(200, cwd=by_cwd)
    result = s.run()
    check("a process whose links or memory map cannot be read is passed over, and its other links and "
          "the processes after it are still read", by_fd.is_dir() and by_cwd.is_dir()
          and "kept because a process uses them: 2;" in result.stdout, result.stdout + result.stderr)

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    shutil.rmtree(s.proc)
    result = s.run()
    check("a process table that cannot be listed deletes nothing and exits 1",
          folder.is_dir() and "nothing was deleted: the process table" in result.stderr
          and not s.log.exists() and result.returncode == 1, result.stderr)

    s = Scene()
    folder = s.folder("pymp-a1b2c3d4")
    (s.proc / "net" / "unix").unlink()
    result = s.run()
    check("a unix socket table that cannot be read deletes nothing and exits 1",
          folder.is_dir() and "nothing was deleted: the unix socket table" in result.stderr
          and not s.log.exists() and result.returncode == 1, result.stderr)


WORKSPACE = scratch_common.scratch_directory_after_removing_ones_killed_runs_left(
    "tmp-and-reviewer-scratch-delete-test-workspace-")
try:
    run_tmp_place_cases()
    run_reviewer_cases()
    run_unreadable_cases()
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
