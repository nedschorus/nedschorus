#!/usr/bin/env python3
"""Work-snapshots: copies of a worktree's uncommitted changes that outlive a crash.

Design: nc-systems/handoff/handoff-uncommitted-work-snapshots-across-crashes-design.md.

A work-snapshot is a commit in the clone's shared object store under
refs/work-snapshots/<owner key>/<SHA-1 of the worktree's path>, holding every
change `git add -A` would stage, with the worktree's HEAD as its parent. The
owner key names the `claude` process that wrote it, so a work-snapshot whose
owner is gone is a leftover. A leftover is lost work only when its worktree
is gone or no longer holds its changes; a session-handoff, a quota stop or a
logout leaves the files in place, and those leftovers are not listed.
Three callers share this module:
scripts/uncommitted-work-snapshot-hook.py writes and deletes work-snapshots,
nc-systems/handoff/handoff-supervisor.py lists an agent-seat's lost work in
the first prompt of every agent-session it starts, each entry ending with the
restore or discard command that handles it, and scripts/clean-worktrees.py
deletes a listed leftover first listed more than
LEFTOVER_DELETED_DAYS_AFTER_FIRST_LISTING days ago and still lost, and a
leftover a newer leftover of the same worktree duplicates exactly, and marks
completed the task a restore opened once its restore commit is on origin/main
or held by no ref.

Usage:
  uncommitted-work-snapshots.py list [--agent-seat NAME] [--repo PATH]
      every leftover work-snapshot holding lost work, or the agent-seat's;
      exit 0, 1 when a work-snapshot could not be compared with its worktree,
      2 when listing failed
  uncommitted-work-snapshots.py restore REF --keep FILE [FILE ...] [--repo PATH]
      commits the kept files' changes on a new branch, restored-<the ref's
      last two parts joined by a hyphen>, in a new worktree of that name
      under <clone>/.claude/worktrees/, made from the work-snapshot's parent
      and given an owner file naming the agent-seat GIT_AUTHOR_NAME names;
      opens a task naming the branch on the task list
      ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>; deletes the ref
  uncommitted-work-snapshots.py discard REF [--repo PATH]
      deletes the ref and prints its list entry
  Both refuse, changing nothing, when the ref does not exist; restore also
  refuses an empty --keep, a kept path the work-snapshot did not change, a
  work-snapshot taken during a merge, rebase, cherry-pick, revert or am, an
  existing branch or worktree directory of the restored name, and an unset
  CLAUDE_CODE_TASK_LIST_ID or GIT_AUTHOR_NAME. When a restore step fails:
  before the commit, the worktree and branch it made are removed and the ref
  is kept; opening the task, the task's text is printed for TaskCreate and
  the ref is still deleted; deleting the ref, the command is printed.
  Exit 0 done, 1 a step failed, 2 bad invocation, 3 refused.
"""

import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

WORK_SNAPSHOT_REF_PREFIX = "refs/work-snapshots/"
ZERO_OBJECT_ID = "0" * 40

TRAILER_WORKTREE = "Work-snapshot-worktree"
TRAILER_BRANCH = "Work-snapshot-branch"
TRAILER_AGENT_SEAT = "Work-snapshot-agent-seat"
TRAILER_TRANSCRIPT = "Work-snapshot-transcript"
TRAILER_OPERATION = "Work-snapshot-operation"
UNKNOWN_AGENT_SEAT = "unknown"

# The launchers set GIT_AUTHOR_NAME to the agent-seat's name.
AGENT_SEAT_ENVIRONMENT_VARIABLE = "GIT_AUTHOR_NAME"
WORK_SNAPSHOT_IDENTITY_NAME = "uncommitted-work-snapshot-hook"
WORK_SNAPSHOT_IDENTITY_EMAIL = "uncommitted-work-snapshot-hook@nedschorus.invalid"

LEFTOVER_DELETED_DAYS_AFTER_FIRST_LISTING = 10
FIRST_PROMPT_ENTRIES_AT_MOST = 20
CHANGED_FILES_NAMED_AT_MOST = 10
FIRST_LISTED_FILE_SUFFIX = "-work-snapshots-first-listed.json"
OWNER_PROCESS_COMMAND_NAME = "claude"

MODULE_PATH = Path(__file__).resolve()

RESTORED_BRANCH_NAME_PREFIX = "restored-"
RESTORE_COMMIT_MESSAGE_TEMPLATE = "Restore work from {ref}"
# scripts/clean-worktrees.py finds the tasks restore opens by these two.
RESTORED_BRANCH_TASK_SUBJECT_PREFIX = "Restored branch "
RESTORE_COMMIT_LINE_PREFIX = "Restore commit: "
TASK_LIST_ENVIRONMENT_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"
TASK_FILE_NAME_PATTERN = re.compile(r"[1-9][0-9]*\.json")
TASK_HIGH_WATER_MARK_FILE_NAME = ".highwatermark"

EXIT_DONE = 0
EXIT_STEP_FAILED = 1
EXIT_BAD_INVOCATION = 2
EXIT_REFUSED = 3


class WorkSnapshotError(Exception):
    """A git command or a process lookup this module depends on failed."""


_git_machine_readable_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[2] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_machine_readable_output = importlib.util.module_from_spec(_git_machine_readable_output_spec)
_git_machine_readable_output_spec.loader.exec_module(git_machine_readable_output)


def run_git(directory, *arguments, environment=None, input_text=None):
    return subprocess.run(
        ["git", "-C", str(directory), *arguments],
        capture_output=True, text=True, check=False,
        env=environment, input=input_text,
    )


def git_output(directory, *arguments, environment=None, input_text=None):
    """stdout of a git command, stripped; raises WorkSnapshotError when git fails."""
    result = run_git(directory, *arguments, environment=environment, input_text=input_text)
    if result.returncode != 0:
        raise WorkSnapshotError(
            f"git {' '.join(arguments)} in {directory} exited {result.returncode}: "
            f"{result.stderr.strip()}")
    return result.stdout.strip()


def git_output_or_none_on_exit_1(directory, *arguments):
    """stdout of a git command, stripped, or None when git exits 1; raises
    WorkSnapshotError for any other failure."""
    result = run_git(directory, *arguments)
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise WorkSnapshotError(
            f"git {' '.join(arguments)} in {directory} exited {result.returncode}: "
            f"{result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------- owners


def linux_boot_id(proc_root="/proc"):
    return Path(proc_root, "sys/kernel/random/boot_id").read_text().strip().replace("-", "")


def linux_stat_fields_after_command(process_id, proc_root="/proc"):
    """Fields 3 onward of /proc/<pid>/stat; the command in field 2 may hold spaces."""
    text = Path(proc_root, str(process_id), "stat").read_text()
    return text.rsplit(")", 1)[1].split()


def linux_start_ticks(process_id, proc_root="/proc"):
    # Field 22 counts clock ticks from boot; unlike seconds derived from btime,
    # it does not move when the system clock is stepped.
    return linux_stat_fields_after_command(process_id, proc_root)[22 - 3]


def run_ps(arguments):
    return subprocess.run(["ps", *arguments], capture_output=True, text=True, check=False)


def process_exists_or_raise(process_id):
    """Whether any process has this id: signal 0 checks without sending anything.

    An error other than "no such process" or "not permitted" raises, unlike
    handoff-supervisor.py's process_exists_by_signal, which counts every error
    as a live process because a lock must not be taken from an unknown owner.
    """
    try:
        os.kill(int(process_id), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def macos_start_seconds(process_id):
    """The process's start as whole seconds since 1970, or None when it is gone.

    Whether the process is gone is decided by process_exists_or_raise, not by ps: macOS ps
    exits 1 for an id no process has, with a message for some ids ("process id
    too large"), and the same exit can mean ps failed. Raises WorkSnapshotError
    when ps fails for a process that exists, so a failed lookup is never taken
    for a dead owner.
    """
    if not process_exists_or_raise(process_id):
        return None
    arguments = ["-o", "lstart=", "-p", str(process_id)]
    result = run_ps(arguments)
    started = " ".join(result.stdout.split())
    if result.returncode == 0 and started:
        return str(int(time.mktime(time.strptime(started, "%a %b %d %H:%M:%S %Y"))))
    # The process can exit between the check above and ps.
    if result.returncode == 1 and not started and not process_exists_or_raise(process_id):
        return None
    raise WorkSnapshotError(
        f"ps {' '.join(arguments)} exited {result.returncode}: "
        f"{result.stderr.strip() or 'no detail'}")


def owner_key_of_process(process_id, proc_root="/proc", platform=sys.platform):
    if platform.startswith("linux"):
        return (f"{linux_boot_id(proc_root)}-{process_id}-"
                f"{linux_start_ticks(process_id, proc_root)}")
    if platform == "darwin":
        started = macos_start_seconds(process_id)
        if started is None:
            raise WorkSnapshotError(f"process {process_id} is gone")
        return f"{process_id}-{started}"
    raise WorkSnapshotError(f"work-snapshots do not support the platform {platform}")


def owner_process_is_alive(owner_key, proc_root="/proc", platform=sys.platform):
    parts = owner_key.split("-")
    if platform.startswith("linux"):
        if len(parts) != 3:
            raise WorkSnapshotError(f"owner key {owner_key} is not a Linux owner key")
        boot_id, process_id, start_ticks = parts
        if boot_id != linux_boot_id(proc_root):
            return False
        try:
            return linux_start_ticks(process_id, proc_root) == start_ticks
        except (FileNotFoundError, ProcessLookupError, IndexError):
            return False
    if platform == "darwin":
        if len(parts) != 2:
            raise WorkSnapshotError(f"owner key {owner_key} is not a macOS owner key")
        process_id, start_seconds = parts
        return macos_start_seconds(process_id) == start_seconds
    raise WorkSnapshotError(f"work-snapshots do not support the platform {platform}")


def process_command_name_and_parent(process_id, proc_root="/proc", platform=sys.platform):
    if platform.startswith("linux"):
        name = Path(proc_root, str(process_id), "comm").read_text().strip()
        parent = int(linux_stat_fields_after_command(process_id, proc_root)[4 - 3])
        return name, parent
    result = run_ps(["-o", "ppid=,comm=", "-p", str(process_id)])
    fields = result.stdout.strip().split(None, 1)
    if result.returncode != 0 or len(fields) != 2:
        raise WorkSnapshotError(f"ps could not read process {process_id}")
    return os.path.basename(fields[1].strip()), int(fields[0])


def claude_owner_process_id(start_process_id, proc_root="/proc", platform=sys.platform):
    """The nearest ancestor (or start_process_id itself) named claude, or None."""
    process_id = start_process_id
    while process_id > 1:
        name, parent = process_command_name_and_parent(process_id, proc_root, platform)
        if name == OWNER_PROCESS_COMMAND_NAME:
            return process_id
        process_id = parent
    return None


# ---------------------------------------------------------------- worktrees


def worktree_containing(path):
    """The resolved top of the git worktree holding path, or None outside any.

    Raises WorkSnapshotError when git fails for another reason, so a worktree
    that could not be found is reported rather than skipped.
    """
    directory = Path(path)
    while not directory.is_dir():
        if directory.parent == directory:
            return None
        directory = directory.parent
    try:
        output = git_machine_readable_output.run_git_unless_outside_a_repository(
            directory, ["rev-parse", "--show-toplevel"])
    except git_machine_readable_output.GitCommandFailed as failure:
        raise WorkSnapshotError(
            f"git rev-parse --show-toplevel in {directory} exited {failure.returncode}: "
            f"{failure.stderr.strip() or 'no output'}") from None
    if output is None:
        return None
    top = os.fsdecode(output).strip()
    if not top:
        raise WorkSnapshotError(
            f"git rev-parse --show-toplevel in {directory} exited 0: no output")
    return Path(top).resolve()


def common_git_directory(directory):
    return Path(git_output(directory, "rev-parse", "--path-format=absolute",
                           "--git-common-dir")).resolve()


def work_snapshot_ref(owner_key, worktree):
    path_hash = hashlib.sha1(str(Path(worktree).resolve()).encode()).hexdigest()
    return f"{WORK_SNAPSHOT_REF_PREFIX}{owner_key}/{path_hash}"


def operation_in_progress(worktree):
    """merge, rebase, cherry-pick, revert or am when git shows one under way, else None."""
    arguments = ["rev-parse", "--path-format=absolute"]
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        arguments += ["--git-path", name]
    lines = git_output(worktree, *arguments).split("\n")
    if len(lines) != 5:
        raise WorkSnapshotError(
            f"git {' '.join(arguments)} in {worktree} printed {len(lines)} lines where the 5 paths "
            "should give one line each; a path holding a newline prints as two lines, "
            "and fewer lines mean git printed less than asked")
    merge_head, cherry_pick_head, revert_head, rebase_merge, rebase_apply = (
        Path(line) for line in lines)
    if merge_head.exists():
        return "merge"
    if cherry_pick_head.exists():
        return "cherry-pick"
    if revert_head.exists():
        return "revert"
    if rebase_merge.is_dir():
        return "rebase"
    if rebase_apply.is_dir():
        return "am" if (rebase_apply / "applying").exists() else "rebase"
    return None


def has_uncommitted_changes(worktree):
    return bool(git_output(worktree, "--no-optional-locks", "status", "--porcelain",
                           "--untracked-files=all"))


def tree_of_worktree_now(worktree):
    """The tree `git add -A` would stage, built on a copy of the index."""
    index = Path(git_output(worktree, "rev-parse", "--path-format=absolute",
                            "--git-path", "index"))
    with tempfile.TemporaryDirectory(prefix="work-snapshot-index-") as scratch:
        scratch_index = Path(scratch, "index")
        if index.exists():
            # Keep the index's mtime: git trusts an entry's stat data only when the entry is
            # older than the index file, so a fresh mtime would hide a same-size edit made in
            # the second the index was written.
            shutil.copy2(index, scratch_index)
        environment = dict(os.environ, GIT_INDEX_FILE=str(scratch_index))
        git_output(worktree, "add", "-A", environment=environment)
        return git_output(worktree, "write-tree", environment=environment)


def build_work_snapshot_commit(worktree, agent_seat, transcript):
    tree = tree_of_worktree_now(worktree)
    head = head_commit_or_raise(worktree)
    # symbolic-ref -q exits 1 only for a detached HEAD.
    branch = git_output_or_none_on_exit_1(
        worktree, "symbolic-ref", "-q", "--short", "HEAD") or "detached"
    trailers = [
        f"{TRAILER_WORKTREE}: {worktree}",
        f"{TRAILER_BRANCH}: {branch}",
        f"{TRAILER_AGENT_SEAT}: {agent_seat or UNKNOWN_AGENT_SEAT}",
        f"{TRAILER_TRANSCRIPT}: {transcript or ''}",
    ]
    operation = operation_in_progress(worktree)
    if operation:
        trailers.append(f"{TRAILER_OPERATION}: {operation}")
    message = (f"Work-snapshot of uncommitted changes in {worktree}\n\n"
               + "\n".join(trailers) + "\n")
    environment = dict(
        os.environ,
        GIT_AUTHOR_NAME=agent_seat or UNKNOWN_AGENT_SEAT,
        GIT_AUTHOR_EMAIL=WORK_SNAPSHOT_IDENTITY_EMAIL,
        GIT_COMMITTER_NAME=WORK_SNAPSHOT_IDENTITY_NAME,
        GIT_COMMITTER_EMAIL=WORK_SNAPSHOT_IDENTITY_EMAIL,
    )
    arguments = ["commit-tree", tree, "-F", "-"]
    if head:
        arguments[2:2] = ["-p", head]
    return git_output(worktree, *arguments, environment=environment, input_text=message)


def current_ref_value(directory, ref):
    """The commit ref holds, or None when ref does not exist."""
    return git_output_or_none_on_exit_1(directory, "rev-parse", "--verify", "-q", ref)


def refresh_work_snapshot(worktree, owner_key, agent_seat, transcript):
    """Write, replace or delete this owner's work-snapshot of worktree.

    Returns "written", "deleted" or "clean". The ref is set with
    compare-and-swap; when an overlapping run changed it in between, the
    work-snapshot is built once more from the worktree's state then.
    """
    ref = work_snapshot_ref(owner_key, worktree)
    for attempt in (1, 2):
        old = current_ref_value(worktree, ref)
        if not has_uncommitted_changes(worktree):
            if old is None:
                return "clean"
            result = run_git(worktree, "update-ref", "-d", ref, old)
            outcome = "deleted"
        else:
            new = build_work_snapshot_commit(worktree, agent_seat, transcript)
            result = run_git(worktree, "update-ref", ref, new, old or ZERO_OBJECT_ID)
            outcome = "written"
        if result.returncode == 0:
            return outcome
        if attempt == 2:
            raise WorkSnapshotError(f"git update-ref {ref} failed twice: "
                                    f"{result.stderr.strip()}")
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- listing


def parse_trailer_lines(text):
    trailers = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            trailers[key.strip()] = value.strip()
    return trailers


def all_work_snapshots(repo):
    """Every work-snapshot in repo's clone, newest first, as dicts."""
    record_end = "\x00\x01"
    output = git_output(
        repo, "for-each-ref", "--sort=-authordate",
        "--format=%(refname)%00%(objectname)%00%(authordate:unix)%00"
        "%(trailers:only,unfold)%00%01",
        WORK_SNAPSHOT_REF_PREFIX)
    snapshots = []
    for record in output.split(record_end):
        record = record.strip("\n")
        if not record:
            continue
        ref, commit, author_time, trailer_text = record.split("\x00")[:4]
        relative = ref[len(WORK_SNAPSHOT_REF_PREFIX):]
        trailers = parse_trailer_lines(trailer_text)
        snapshots.append({
            "ref": ref,
            "commit": commit,
            "time": int(author_time),
            "owner_key": relative.split("/", 1)[0],
            "worktree": trailers.get(TRAILER_WORKTREE, ""),
            "branch": trailers.get(TRAILER_BRANCH, ""),
            "agent_seat": trailers.get(TRAILER_AGENT_SEAT, UNKNOWN_AGENT_SEAT),
            "transcript": trailers.get(TRAILER_TRANSCRIPT, ""),
            "operation": trailers.get(TRAILER_OPERATION, ""),
        })
    return snapshots


def leftover_work_snapshots(repo, agent_seat=None, is_alive=None, everything=None):
    """Work-snapshots whose owner process is gone, newest first."""
    is_alive = is_alive or owner_process_is_alive
    everything = all_work_snapshots(repo) if everything is None else everything
    return [snapshot for snapshot in everything
            if (agent_seat is None or snapshot["agent_seat"] == agent_seat)
            and not is_alive(snapshot["owner_key"])]


LOST = "lost"
IN_PLACE = "in place"


def leftover_state(repo, snapshot):
    """LOST or IN_PLACE: whether a leftover's worktree still holds its changes.

    IN_PLACE: the worktree exists and still has the work-snapshot's parent as
    HEAD and its tree, as after a session-handoff, a quota stop or a logout;
    it is kept, unlisted, so it is still there if the worktree is removed
    later. LOST: anything else, including a worktree that is gone, holds other
    changes, or had the changes committed or discarded; the work-snapshot may
    be the only copy, so it is listed. Raises WorkSnapshotError when the
    worktree or the work-snapshot cannot be read.
    """
    worktree = snapshot["worktree"]
    if not worktree or not worktree_resolves_to_itself(worktree):
        return LOST
    return IN_PLACE if snapshot_matches_worktree(repo, snapshot) else LOST


def worktree_resolves_to_itself(worktree):
    """Whether git, run in worktree, answers for that worktree and not an enclosing one.

    A directory without a .git entry is not the worktree: an interrupted
    removal can leave one, and git there would answer for the checkout around
    it. Raises WorkSnapshotError when the directory has a .git entry git
    cannot use, including one git skips to answer for an enclosing checkout.
    """
    directory = Path(worktree)
    if not directory.is_dir():
        return False
    if not (directory / ".git").exists():
        return False
    result = run_git(directory, "rev-parse", "--show-toplevel")
    if result.returncode != 0 or not result.stdout.strip():
        raise WorkSnapshotError(
            f"git rev-parse --show-toplevel in {directory}, which has a .git entry, "
            f"exited {result.returncode}: {result.stderr.strip() or 'no output'}")
    toplevel = Path(result.stdout.strip()).resolve()
    if toplevel != directory.resolve():
        raise WorkSnapshotError(
            f"{directory} has a .git entry git cannot use: git there answers for {toplevel}")
    return True


def tree_and_parents(repo, commit, cache):
    """(tree id, parent ids) of commit, read once per commit."""
    if commit not in cache:
        tree, _, parents = git_output(repo, "log", "-1", "--format=%T%x00%P",
                                      commit).partition("\0")
        cache[commit] = (tree, parents)
    return cache[commit]


def newer_duplicate(repo, snapshot, leftovers, cache):
    """A later leftover of the same agent-seat and worktree with the same tree and parents, or None.

    Such a pair is what each session-handoff leaves: the same unchanged files
    written again by the next owner. The later one holds every byte the
    earlier one holds, compared by git object id. Only leftovers count, never
    a live owner's work-snapshot, which its own hook may delete. Only the same
    agent-seat counts, because a leftover is listed only to its own
    agent-seat: a copy kept under another agent-seat, or under `unknown`,
    which no first prompt lists, would never be listed to this one.
    """
    if not snapshot["worktree"]:
        return None
    mine = tree_and_parents(repo, snapshot["commit"], cache)
    order = (snapshot["time"], snapshot["ref"])
    for other in leftovers:
        if (other["worktree"] == snapshot["worktree"]
                and other["agent_seat"] == snapshot["agent_seat"]
                and (other["time"], other["ref"]) > order
                and tree_and_parents(repo, other["commit"], cache) == mine):
            return other
    return None


def lost_work_snapshots(repo, agent_seat=None, is_alive=None, everything=None):
    """(leftover, problem) pairs to list, newest first.

    problem is None, or why the work-snapshot could not be checked; such a
    leftover is listed, since its changes may exist nowhere else. A leftover
    with a newer duplicate is left out: the duplicate is listed in its place.
    """
    everything = all_work_snapshots(repo) if everything is None else everything
    all_leftovers = leftover_work_snapshots(repo, None, is_alive, everything)
    cache = {}
    lost = []
    for snapshot in all_leftovers:
        if agent_seat is not None and snapshot["agent_seat"] != agent_seat:
            continue
        try:
            if newer_duplicate(repo, snapshot, all_leftovers, cache):
                continue
            if leftover_state(repo, snapshot) == LOST:
                lost.append((snapshot, None))
        except WorkSnapshotError as error:
            lost.append((snapshot, str(error)))
    return lost


def changed_files(repo, ref):
    """(status, path) pairs of the changes ref holds against its parent."""
    output = git_output(repo, "diff-tree", "-z", "-r", "--root", "--no-renames",
                        "--no-commit-id", "--name-status", ref)
    return [(entry.status, entry.path)
            for entry in git_machine_readable_output.name_status_entries(output)]


def changed_files_text(repo, ref):
    files = changed_files(repo, ref)
    named = ", ".join(f"{status} {path}" for status, path in files[:CHANGED_FILES_NAMED_AT_MOST])
    rest = len(files) - CHANGED_FILES_NAMED_AT_MOST
    return named + (f", and {rest} more" if rest > 0 else "")


def utc_text(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry_command_text(repo, snapshot):
    """The command that handles the work-snapshot: discard for one taken during an operation,
    otherwise restore keeping every changed file, each path quoted for the shell."""
    program = f"python3 {shlex.quote(str(MODULE_PATH))}"
    if snapshot["operation"]:
        return f"{program} discard {snapshot['ref']}"
    files = " ".join(shlex.quote(path) for _status, path in changed_files(repo, snapshot["ref"]))
    return f"{program} restore {snapshot['ref']} --keep {files}"


def entry_text(repo, snapshot, problem=None, with_command=True):
    worktree = snapshot["worktree"]
    transcript = snapshot["transcript"]
    exists = "exists" if worktree and Path(worktree).is_dir() else "is gone"
    transcript_state = ("exists" if transcript and Path(transcript).is_file()
                        else "is gone")
    parts = [
        f"{snapshot['ref']}: worktree {worktree} ({exists})",
        f"branch {snapshot['branch']}",
        f"written {utc_text(snapshot['time'])}",
        f"transcript {transcript or '(none recorded)'} ({transcript_state})",
    ]
    if snapshot["operation"]:
        parts.append(f"taken during a {snapshot['operation']}")
    if problem:
        parts.append(f"its worktree could not be compared with it: {problem}")
    parts.append(f"changes: {changed_files_text(repo, snapshot['ref'])}")
    if with_command:
        parts.append(f"handle it with: `{entry_command_text(repo, snapshot)}`")
    return "; ".join(parts)


def list_command_text(agent_seat):
    return f"python3 {MODULE_PATH} list --agent-seat {agent_seat}"


RESTORE_STEPS = """\
Each was listed because its worktree is gone or no longer holds its changes. Handle each of them, before your other work:
1. See what it holds: `git diff --stat <ref>^ <ref>`, then `git diff <ref>^ <ref>`.
2. Decide what to keep. Read the end of the transcript the entry names, to learn what the dead agent was doing; if the transcript is gone, decide from the diff alone, and ask the user when unsure. Drop any mutant: a deliberate small break in code that nc-mutation-testing makes, by a program or by an agent's own edit, to check that the tests notice. A crash during nc-mutation-testing leaves the mutant in the work-snapshot. Leave a file that holds only a mutant off `--keep`; keep a file that holds both wanted work and a mutant, and after `restore` remove the mutant from it in a commit of its own on the restored branch, before the branch is pushed.
3. Run the entry's command. To keep one file or more, run `restore`, after deleting from `--keep` the files you drop. To keep nothing, run `python3 {module} discard <ref>`. For a work-snapshot taken during an operation, run `discard`, as its entry says. When the command refuses or fails, do what it prints, and tell the user what failed.
4. Tell the user, in your next message to the user, each work-snapshot handled, using the summary line each command prints, and add why each dropped file was dropped. Whether to finish the dead agent's task is a separate decision, made after the restore; the task `restore` opens keeps the restored branch on your task list until that decision is carried out."""


def first_listed_path(handoff_directory, agent_seat):
    return Path(handoff_directory) / f"{agent_seat}{FIRST_LISTED_FILE_SUFFIX}"


def read_first_listed(path):
    if not Path(path).is_file():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def record_first_listing(path, refs, now, existing_refs):
    """Add each ref's first listing time; drop entries whose ref no longer exists."""
    records = {ref: when for ref, when in read_first_listed(path).items()
               if ref in existing_refs}
    for ref in refs:
        records.setdefault(ref, int(now))
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(records, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def first_prompt_text(repo, agent_seat, handoff_directory, now=None, is_alive=None):
    """The first prompt's paragraph on this agent-seat's leftover work-snapshots.

    Empty when there are none. A failure is stated, with the list command, so
    it cannot be mistaken for none.
    """
    is_alive = is_alive or owner_process_is_alive
    try:
        outside_any_clone = git_machine_readable_output.run_git_unless_outside_a_repository(
            repo, ["rev-parse", "--git-dir"]) is None
    except git_machine_readable_output.GitCommandFailed:
        # The listing below runs git again and states the failure.
        outside_any_clone = False
    if outside_any_clone:
        # Work-snapshots live in a clone; a working directory outside any has none.
        return ""
    try:
        everything = all_work_snapshots(repo)
        lost = lost_work_snapshots(repo, agent_seat, is_alive, everything)
        if not lost:
            return ""
        leftovers = [snapshot for snapshot, problem in lost]
        entries = [entry_text(repo, snapshot, problem)
                   for snapshot, problem in lost[:FIRST_PROMPT_ENTRIES_AT_MOST]]
    except Exception as error:
        return (f"Leftover work-snapshots could not be listed ({type(error).__name__}: "
                f"{error}). Uncommitted work from a dead agent of this agent-seat may be "
                f"waiting; list it with: {list_command_text(agent_seat)}")
    lines = [f"Leftover work-snapshots: {len(leftovers)} copy(ies) of uncommitted work "
             "left by an agent of this agent-seat whose `claude` process is gone, and no "
             "longer in its worktree:"]
    lines.extend(f"- {entry}" for entry in entries)
    rest = len(leftovers) - len(entries)
    if rest > 0:
        lines.append(f"- and {rest} more; list them all with: {list_command_text(agent_seat)}")
    lines.append(RESTORE_STEPS.format(module=shlex.quote(str(MODULE_PATH))))
    try:
        record_first_listing(first_listed_path(handoff_directory, agent_seat),
                             [snapshot["ref"] for snapshot in leftovers],
                             time.time() if now is None else now,
                             {snapshot["ref"] for snapshot in everything})
    except Exception as error:
        lines.append(f"(Their first listing could not be recorded ({type(error).__name__}: "
                     f"{error}), so scripts/clean-worktrees.py counts them as never listed and keeps them.)")
    return "\n".join(lines)


# ---------------------------------------------------------------- restore and discard


_owner_file_module = None


def owner_file_module():
    """scripts/worktree-owner-file-read-and-write.py, loaded on first use: it loads this module
    itself, so loading it at import would be circular."""
    global _owner_file_module
    if _owner_file_module is None:
        spec = importlib.util.spec_from_file_location(
            "worktree_owner_file_read_and_write",
            MODULE_PATH.parents[2] / "scripts" / "worktree-owner-file-read-and-write.py")
        _owner_file_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_owner_file_module)
    return _owner_file_module


def restored_branch_name(ref):
    """restored- and the ref's last two parts joined by a hyphen; no other work-snapshot shares it."""
    return RESTORED_BRANCH_NAME_PREFIX + "-".join(ref.split("/")[-2:])


def restored_branch_task_subject(branch):
    return f"{RESTORED_BRANCH_TASK_SUBJECT_PREFIX}{branch}: open its pull request or delete it"


def restored_branch_task_description(snapshot, kept, worktree, restore_commit):
    return "\n".join([
        f"`restore` restored the work-snapshot {snapshot['ref']}, left by the worktree "
        f"{snapshot['worktree'] or '(none recorded)'} with the transcript "
        f"{snapshot['transcript'] or '(none recorded)'}.",
        f"Kept files: {', '.join(kept)}.",
        f"Restored worktree: {worktree}",
        f"{RESTORE_COMMIT_LINE_PREFIX}{restore_commit}",
        "Carry the branch on to a pull request, or delete it. Leave this task open: "
        "scripts/clean-worktrees.py marks it completed once that commit is on main or no branch "
        "holds it any more.",
    ])


def task_list_new_pending_task_write(list_directory, subject, description):
    """Write a new pending task into the Claude Code task list; return its id. Raises OSError.

    The id is one more than the highest of the list's task ids and its .highwatermark, as
    Claude Code numbers a new task; the file is linked into place only where no file of that
    name exists, so a task Claude Code creates at the same moment is not overwritten.
    """
    list_directory = Path(list_directory)
    list_directory.mkdir(parents=True, exist_ok=True)
    highest = 0
    for path in list_directory.iterdir():
        if TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            highest = max(highest, int(path.stem))
    mark_path = list_directory / TASK_HIGH_WATER_MARK_FILE_NAME
    mark = mark_path.read_text(encoding="utf-8").strip() if mark_path.is_file() else ""
    if mark.isdigit():
        highest = max(highest, int(mark))
    task_id = highest + 1
    with tempfile.NamedTemporaryFile("w", dir=list_directory, prefix=".task-", suffix=".partial",
                                     delete=False, encoding="utf-8") as partial:
        partial_path = Path(partial.name)
    try:
        while True:
            partial_path.write_text(json.dumps({
                "id": str(task_id), "subject": subject, "description": description,
                "status": "pending", "blocks": [], "blockedBy": []}, indent=2), encoding="utf-8")
            try:
                os.link(partial_path, list_directory / f"{task_id}.json")
                break
            except FileExistsError:
                task_id += 1
    finally:
        partial_path.unlink(missing_ok=True)
    mark_partial = list_directory / (TASK_HIGH_WATER_MARK_FILE_NAME + ".partial")
    mark_partial.write_text(str(task_id), encoding="utf-8")
    os.replace(mark_partial, mark_path)
    return task_id


def work_snapshot_of_ref(repo, ref, out):
    """The work-snapshot ref names, or None after printing why there is none."""
    if not ref.startswith(WORK_SNAPSHOT_REF_PREFIX):
        out(f"REFUSED: {ref} is not a work-snapshot; a work-snapshot's ref starts with "
            f"{WORK_SNAPSHOT_REF_PREFIX}, as its list entry prints it.")
        return None
    for snapshot in all_work_snapshots(repo):
        if snapshot["ref"] == ref:
            return snapshot
    out(f"REFUSED: the work-snapshot {ref} does not exist, so nothing was changed.\n"
        f"If you restored or discarded it earlier, it is already handled.\n"
        f"Otherwise list the work-snapshots there are with: python3 {shlex.quote(str(MODULE_PATH))} list")
    return None


def git_failure_text(result):
    return f"exited {result.returncode}: {(result.stderr or result.stdout or '').strip() or 'no output'}"


def restore_refusal(repo, snapshot, keep, environment):
    """Why restore must not start, or None. Checked before anything changes."""
    ref = snapshot["ref"]
    program = f"python3 {shlex.quote(str(MODULE_PATH))}"
    if not keep:
        return (f"--keep names no file, which would restore every file.\n"
                f"To keep every file, name each one, as the list entry does.\n"
                f"To keep nothing, run: {program} discard {ref}")
    changed = [path for _status, path in changed_files(repo, ref)]
    missing = [path for path in keep if path not in changed]
    if missing:
        return (f"{', '.join(missing)} is not among the files the work-snapshot changed: "
                f"{', '.join(changed)}.\n"
                f"Give the paths relative to the clone's root, as the list entry prints them.")
    if snapshot["operation"]:
        return (f"the work-snapshot was taken during a {snapshot['operation']} in the worktree "
                f"{snapshot['worktree']}, and git's record of the {snapshot['operation']} is not "
                f"in it, so it cannot be resumed or restored.\n"
                f"Run: {program} discard {ref}\n"
                f"Then tell the user that the {snapshot['operation']} in {snapshot['worktree']} "
                f"was discarded; its commits are still on the branches.")
    branch = restored_branch_name(ref)
    worktree = common_git_directory(repo).parent / ".claude" / "worktrees" / branch
    if current_ref_value(repo, f"refs/heads/{branch}") is not None:
        newest = git_output(repo, "log", "-1", "--format=%s", f"refs/heads/{branch}")
        if newest == RESTORE_COMMIT_MESSAGE_TEMPLATE.format(ref=ref):
            return (f"the branch {branch} already holds this restore: its newest commit is "
                    f"\"{newest}\". Only the ref's deletion failed earlier.\n"
                    f"Run: git update-ref -d {ref}")
        return (f"the branch {branch} already exists, and its newest commit is not this "
                f"work-snapshot's restore.\n"
                f"Look at it with `git log {branch}`, and ask the user what to do with it.")
    if worktree.exists():
        return (f"the directory {worktree} already exists.\n"
                f"Look at what it holds, and ask the user what to do with it.")
    unset = [name for name in (TASK_LIST_ENVIRONMENT_VARIABLE, AGENT_SEAT_ENVIRONMENT_VARIABLE)
             if not environment.get(name)]
    if unset:
        return (f"{' and '.join(unset)} is unset; the launchers set both for every agent-seat, "
                f"and restore needs them to name the worktree's owner and the task list.\n"
                f"Run restore from an agent-session the launcher started, or ask the user.")
    return None


def restore_undo(repo, worktree, branch, out):
    """Remove the worktree and the branch restore made; name each that cannot be removed."""
    if worktree.exists():
        removal = run_git(repo, "worktree", "remove", "--force", "--force", str(worktree))
        if removal.returncode:
            out(f"The worktree {worktree} restore made could not be removed "
                f"({git_failure_text(removal)}); remove it with: "
                f"git worktree remove --force --force {shlex.quote(str(worktree))}")
    if current_ref_value(repo, f"refs/heads/{branch}") is not None:
        deletion = run_git(repo, "branch", "-D", branch)
        if deletion.returncode:
            out(f"The branch {branch} restore made could not be deleted "
                f"({git_failure_text(deletion)}); delete it with: git branch -D {branch}")


def restore_work_snapshot(repo, ref, keep, environment=None, out=print):
    """The restore command; returns its exit code."""
    environment = os.environ if environment is None else environment
    snapshot = work_snapshot_of_ref(repo, ref, out)
    if snapshot is None:
        return EXIT_REFUSED
    refusal = restore_refusal(repo, snapshot, keep, environment)
    if refusal:
        out(f"REFUSED: nothing was changed, because {refusal}")
        return EXIT_REFUSED
    branch = restored_branch_name(ref)
    worktree = common_git_directory(repo).parent / ".claude" / "worktrees" / branch
    agent_seat = environment[AGENT_SEAT_ENVIRONMENT_VARIABLE]

    def undo_after(step, detail):
        out(f"FAILED: {step} failed ({detail}).")
        restore_undo(repo, worktree, branch, out)
        out(f"The ref {ref} is kept, so nothing is lost. Tell the user what failed.")
        return EXIT_STEP_FAILED

    added = run_git(repo, "worktree", "add", "-b", branch, str(worktree), f"{ref}^")
    if added.returncode:
        return undo_after(f"git worktree add -b {branch} {worktree} {ref}^", git_failure_text(added))
    owners = owner_file_module()
    try:
        owners.worktree_owner_file_write(worktree, owners.OWNER_AGENT_SEAT, agent_seat)
    except Exception as error:
        return undo_after(f"writing the owner file of {worktree}", f"{type(error).__name__}: {error}")
    diff = subprocess.run(["git", "-C", str(worktree), "diff", "--binary", f"{ref}^", ref, "--",
                           *keep], capture_output=True, check=False)
    if diff.returncode:
        return undo_after(f"git diff --binary {ref}^ {ref}",
                          f"exited {diff.returncode}: {diff.stderr.decode(errors='replace').strip()}")
    applied = subprocess.run(["git", "-C", str(worktree), "apply", "--index"], input=diff.stdout,
                             capture_output=True, check=False)
    if applied.returncode:
        return undo_after("git apply --index",
                          f"exited {applied.returncode}: {applied.stderr.decode(errors='replace').strip()}")
    committed = run_git(worktree, "commit", "-q", "-m", RESTORE_COMMIT_MESSAGE_TEMPLATE.format(ref=ref))
    if committed.returncode:
        return undo_after("git commit", git_failure_text(committed))
    restore_commit = git_output(worktree, "rev-parse", "HEAD")

    exit_code = EXIT_DONE
    subject = restored_branch_task_subject(branch)
    description = restored_branch_task_description(snapshot, keep, worktree, restore_commit)
    task_list = Path.home() / ".claude" / "tasks" / environment[TASK_LIST_ENVIRONMENT_VARIABLE]
    try:
        task_id = task_list_new_pending_task_write(task_list, subject, description)
    except OSError as error:
        task_id = None
        exit_code = EXIT_STEP_FAILED
        out(f"FAILED: the task could not be opened in {task_list} ({type(error).__name__}: {error}). "
            f"The branch and the worktree hold the work, so the ref is still deleted.\n"
            f"Create the task with Claude Code's TaskCreate tool, with exactly this subject and "
            f"description, so that scripts/clean-worktrees.py closes it:\n"
            f"subject: {subject}\ndescription:\n{description}")
    deleted = run_git(repo, "update-ref", "-d", ref, snapshot["commit"])
    if deleted.returncode:
        exit_code = EXIT_STEP_FAILED
        out(f"FAILED: the ref could not be deleted ({git_failure_text(deleted)}); the branch "
            f"{'and the task are' if task_id else 'is'} kept.\nRun: git update-ref -d {ref}")
    out(f"branch: {branch}\nworktree: {worktree}\n"
        f"task: {task_id if task_id is not None else 'not opened, as the FAILED line above says'}")
    dropped = [path for _status, path in changed_files(repo, snapshot["commit"]) if path not in keep]
    out(f"summary: restored {ref}: kept {', '.join(keep)}; dropped "
        f"{', '.join(dropped) if dropped else 'nothing'}; on the branch {branch} in the worktree "
        f"{worktree}")
    return exit_code


def discard_work_snapshot(repo, ref, out=print):
    """The discard command; returns its exit code."""
    snapshot = work_snapshot_of_ref(repo, ref, out)
    if snapshot is None:
        return EXIT_REFUSED
    entry = entry_text(repo, snapshot, with_command=False)
    deleted = run_git(repo, "update-ref", "-d", ref, snapshot["commit"])
    if deleted.returncode:
        out(f"FAILED: the ref could not be deleted ({git_failure_text(deleted)}).\n"
            f"Run: git update-ref -d {ref}")
        return EXIT_STEP_FAILED
    out(f"summary: discarded {entry}")
    return EXIT_DONE


# ---------------------------------------------------------------- cleaner


def first_listing_times(handoff_directory):
    """ref -> earliest first-listing time across every agent-seat's record."""
    times = {}
    for path in sorted(Path(handoff_directory).glob(f"*{FIRST_LISTED_FILE_SUFFIX}")):
        for ref, when in read_first_listed(path).items():
            times[ref] = min(when, times.get(ref, when))
    return times


def clean_leftover_work_snapshots(repo, remove, only_due, handoff_directory, now=None,
                                  is_alive=None, out=print):
    """Report leftovers; with remove, delete duplicates and those listed and left.

    A leftover is due when a newer leftover of the same worktree duplicates
    it, or when it is still lost more than
    LEFTOVER_DELETED_DAYS_AFTER_FIRST_LISTING days after its first listing.
    Returns the number of failures. A live owner's work-snapshot is never
    touched or reported.
    """
    now = time.time() if now is None else now
    is_alive = is_alive or owner_process_is_alive
    try:
        everything = all_work_snapshots(repo)
        leftovers = leftover_work_snapshots(repo, is_alive=is_alive, everything=everything)
        listed = first_listing_times(handoff_directory)
    except Exception as error:
        out(f"work-snapshots: could not be listed: {type(error).__name__}: {error}")
        return 1
    failures = 0
    threshold = LEFTOVER_DELETED_DAYS_AFTER_FIRST_LISTING * 86400
    cache = {}
    for snapshot in leftovers:
        ref = snapshot["ref"]
        age_days = int((now - snapshot["time"]) // 86400)
        first_listed = listed.get(ref)
        try:
            files = changed_files_text(repo, ref)
            duplicate = newer_duplicate(repo, snapshot, leftovers, cache)
            state = None if duplicate else leftover_state(repo, snapshot)
        except WorkSnapshotError as error:
            out(f"work-snapshot {ref}: could not be checked, kept: {error}")
            failures += 1
            continue
        where = (f"agent-seat {snapshot['agent_seat']}, worktree {snapshot['worktree']}, "
                 f"files: {files}")
        due = duplicate is not None or (state == LOST and first_listed is not None
                                        and now - first_listed > threshold)
        if due and remove:
            result = run_git(repo, "update-ref", "-d", ref, snapshot["commit"])
            reason = (f"a duplicate of the newer leftover {duplicate['ref']}, same HEAD and "
                      "same content" if duplicate else
                      f"first listed {utc_text(first_listed)} and not restored")
            if result.returncode == 0:
                out(f"work-snapshot {ref}: deleted, {reason} ({where})")
            else:
                out(f"work-snapshot {ref}: deletion failed: {result.stderr.strip()} ({where})")
                failures += 1
            continue
        if only_due and not due:
            continue
        if duplicate:
            listing = f"a duplicate of the newer leftover {duplicate['ref']}"
        elif state == IN_PLACE:
            listing = "its changes are still in its worktree, so it is not listed"
        elif first_listed is not None:
            listing = f"first listed {utc_text(first_listed)}"
        else:
            listing = "never listed in a first prompt"
        verdict = ("due for deletion — delete with: scripts/clean-worktrees.py --remove"
                   if due else "kept")
        out(f"work-snapshot {ref}: {verdict} — owner process gone, written {age_days} "
            f"day(s) ago, {listing} ({where})")
    return failures


# ---------------------------------------------------------------- comparing with the worktree


def snapshot_matches_worktree(repo, snapshot):
    """Whether the worktree still has the work-snapshot's parent as HEAD and its tree.

    Raises WorkSnapshotError when HEAD or a tree cannot be read, so a failed
    comparison is reported, not taken for a mismatch.
    """
    worktree = Path(snapshot["worktree"])
    if not worktree.is_dir():
        return False
    tree, parents = tree_and_parents(repo, snapshot["commit"], {})
    if head_commit_or_raise(worktree) != (parents or None):
        return False
    return tree_of_worktree_now(worktree) == tree


def head_commit_or_raise(worktree):
    """HEAD's commit, or None when HEAD is unborn; raises WorkSnapshotError on any other failure.

    Unborn means HEAD names a branch that has no commit yet; `rev-parse -q`
    alone cannot tell that from a HEAD git cannot resolve.
    """
    # ^{commit} makes git check the object exists; plain HEAD echoes any id HEAD holds.
    result = run_git(worktree, "rev-parse", "--verify", "-q", "HEAD^{commit}")
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    branch = run_git(worktree, "symbolic-ref", "-q", "HEAD")
    if branch.returncode == 0 and branch.stdout.strip():
        exists = run_git(worktree, "show-ref", "--verify", "-q", branch.stdout.strip())
        # show-ref exits 1 only when the ref does not exist; a ref naming a
        # missing object exits 128.
        if exists.returncode == 1:
            return None
        if exists.returncode != 0:
            raise WorkSnapshotError(
                f"git show-ref --verify {branch.stdout.strip()} in {worktree} exited "
                f"{exists.returncode}: {exists.stderr.strip() or 'the branch could not be read'}")
    raise WorkSnapshotError(
        f"git rev-parse --verify -q HEAD^{{commit}} in {worktree} exited {result.returncode}: "
        f"{result.stderr.strip() or 'HEAD could not be resolved'}")


# ---------------------------------------------------------------- command line


def command_exit_code(run):
    """Run a restore or discard; a git failure outside its own steps is printed, exit 1."""
    try:
        return run()
    except WorkSnapshotError as error:
        print(f"FAILED: {error}. Nothing after that step was done; tell the user what failed.")
        return EXIT_STEP_FAILED


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    repo = Path.cwd()
    if "--repo" in arguments:
        position = arguments.index("--repo")
        if position + 1 >= len(arguments):
            print("uncommitted-work-snapshots: --repo needs a path", file=sys.stderr)
            return 2
        repo = Path(arguments[position + 1])
        del arguments[position:position + 2]
    if arguments[:1] == ["restore"]:
        rest = arguments[1:]
        if len(rest) < 2 or rest[1] != "--keep" or "--keep" in rest[2:]:
            print(__doc__, file=sys.stderr)
            return EXIT_BAD_INVOCATION
        return command_exit_code(lambda: restore_work_snapshot(repo, rest[0], rest[2:]))
    if arguments[:1] == ["discard"]:
        if len(arguments) != 2:
            print(__doc__, file=sys.stderr)
            return EXIT_BAD_INVOCATION
        return command_exit_code(lambda: discard_work_snapshot(repo, arguments[1]))
    if arguments[:1] == ["list"]:
        agent_seat = None
        rest = arguments[1:]
        if rest[:1] == ["--agent-seat"] and len(rest) == 2:
            agent_seat = rest[1]
        elif rest:
            print(__doc__, file=sys.stderr)
            return 2
        try:
            leftovers = lost_work_snapshots(repo, agent_seat)
            for snapshot, problem in leftovers:
                print(f"agent-seat {snapshot['agent_seat']}: "
                      f"{entry_text(repo, snapshot, problem)}")
        except Exception as error:
            print(f"uncommitted-work-snapshots: could not list: {type(error).__name__}: "
                  f"{error}", file=sys.stderr)
            return 2
        if not leftovers:
            print("no leftover work-snapshots")
        unchecked = sum(1 for _snapshot, problem in leftovers if problem)
        if unchecked:
            print(f"uncommitted-work-snapshots: {unchecked} work-snapshot(s) could not be "
                  "compared with their worktree; they are listed above with the reason",
                  file=sys.stderr)
            return 1
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
