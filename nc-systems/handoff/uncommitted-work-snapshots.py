#!/usr/bin/env python3
"""Work-snapshots: copies of a worktree's uncommitted changes that outlive a crash.

Design: nc-systems/handoff/uncommitted-work-snapshots-across-crashes-design.md.

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
the first prompt of every agent-session it starts, and
scripts/clean-worktrees.py deletes a listed leftover first listed more than
LEFTOVER_DELETED_DAYS_AFTER_FIRST_LISTING days ago and still lost, and a
leftover a newer leftover of the same worktree duplicates exactly.

Usage:
  uncommitted-work-snapshots.py list [--agent-seat NAME] [--repo PATH]
      every leftover work-snapshot holding lost work, or the agent-seat's;
      exit 0, 1 when a work-snapshot could not be compared with its worktree,
      2 when listing failed
"""

import hashlib
import json
import os
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


class WorkSnapshotError(Exception):
    """A git command or a process lookup this module depends on failed."""


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


def process_exists(process_id):
    """Whether any process has this id: signal 0 checks without sending anything."""
    try:
        os.kill(int(process_id), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def macos_start_seconds(process_id):
    """The process's start as whole seconds since 1970, or None when it is gone.

    Whether the process is gone is decided by process_exists, not by ps: macOS ps
    exits 1 for an id no process has, with a message for some ids ("process id
    too large"), and the same exit can mean ps failed. Raises WorkSnapshotError
    when ps fails for a process that exists, so a failed lookup is never taken
    for a dead owner.
    """
    if not process_exists(process_id):
        return None
    arguments = ["-o", "lstart=", "-p", str(process_id)]
    result = run_ps(arguments)
    started = " ".join(result.stdout.split())
    if result.returncode == 0 and started:
        return str(int(time.mktime(time.strptime(started, "%a %b %d %H:%M:%S %Y"))))
    # The process can exit between the check above and ps.
    if result.returncode == 1 and not started and not process_exists(process_id):
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
    result = run_git(directory, "rev-parse", "--show-toplevel")
    if result.returncode != 0 and "not a git repository" in result.stderr:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        raise WorkSnapshotError(
            f"git rev-parse --show-toplevel in {directory} exited {result.returncode}: "
            f"{result.stderr.strip() or 'no output'}")
    return Path(result.stdout.strip()).resolve()


def common_git_directory(directory):
    return Path(git_output(directory, "rev-parse", "--path-format=absolute",
                           "--git-common-dir")).resolve()


def work_snapshot_ref(owner_key, worktree):
    path_hash = hashlib.sha1(str(Path(worktree).resolve()).encode()).hexdigest()
    return f"{WORK_SNAPSHOT_REF_PREFIX}{owner_key}/{path_hash}"


def operation_in_progress(worktree):
    """merge, rebase, cherry-pick, revert or am when git shows one under way, else None."""
    def git_path(name):
        return Path(git_output(worktree, "rev-parse", "--path-format=absolute",
                               "--git-path", name))
    if git_path("MERGE_HEAD").exists():
        return "merge"
    if git_path("CHERRY_PICK_HEAD").exists():
        return "cherry-pick"
    if git_path("REVERT_HEAD").exists():
        return "revert"
    if git_path("rebase-merge").is_dir():
        return "rebase"
    rebase_apply = git_path("rebase-apply")
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


def head_commit(worktree):
    result = run_git(worktree, "rev-parse", "--verify", "-q", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def build_work_snapshot_commit(worktree, agent_seat, transcript):
    tree = tree_of_worktree_now(worktree)
    head = head_commit(worktree)
    branch_result = run_git(worktree, "symbolic-ref", "-q", "--short", "HEAD")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "detached"
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
    result = run_git(directory, "rev-parse", "--verify", "-q", ref)
    return result.stdout.strip() if result.returncode == 0 else None


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
    output = git_output(repo, "diff-tree", "-r", "--root", "--no-renames",
                        "--no-commit-id", "--name-status", ref)
    return [tuple(line.split("\t", 1)) for line in output.splitlines() if "\t" in line]


def changed_files_text(repo, ref):
    files = changed_files(repo, ref)
    named = ", ".join(f"{status} {path}" for status, path in files[:CHANGED_FILES_NAMED_AT_MOST])
    rest = len(files) - CHANGED_FILES_NAMED_AT_MOST
    return named + (f", and {rest} more" if rest > 0 else "")


def utc_text(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def entry_text(repo, snapshot, problem=None):
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
    return "; ".join(parts)


def list_command_text(agent_seat):
    return f"python3 {MODULE_PATH} list --agent-seat {agent_seat}"


RESTORE_STEPS = """\
Each was listed because its worktree is gone or no longer holds its changes. Handle each of them before your other work:
1. See what it holds: `git diff --stat <ref>^ <ref>`, then `git diff <ref>^ <ref>`.
2. Decide what to keep. If you keep nothing, skip step 3. Read the end of the transcript the entry names, to learn what the dead agent was doing; if the transcript is gone, decide from the diff alone, and ask the user when unsure. Drop any mutant: a deliberate small break in code that mutation testing makes, by a program or by an agent's own edit, to check that the tests notice. A crash during mutation testing leaves the mutant in the work-snapshot. If one file holds both wanted work and a mutant, keep the file and remove the mutant from it by editing it before you commit in step 3.
3. Restore what you keep, as a commit.
   - If the entry says the work-snapshot was taken during a merge, rebase, cherry-pick, revert or am: restore nothing from it. Delete it (step 4), tell the user in one line which worktree and which operation were discarded, and, if the dead agent's task still needs the operation, start the operation again from the branch, which still holds the committed work.
   - Otherwise make a new worktree from the work-snapshot's parent, so the changes apply without conflict. Do this even when the entry's worktree still exists: it no longer holds these changes, so leave it alone. With <name> standing for `restored-` and the ref's last two parts joined by a hyphen: `git worktree add -b <name> <clone>/.claude/worktrees/<name> <ref>^`, where <clone> is the directory containing the path `git rev-parse --path-format=absolute --git-common-dir` prints. In the new worktree run `git diff --binary <ref>^ <ref> -- <files to keep> | git apply --index`, then `git commit -m "Restore work from <ref>"`. Carry the restored branch on, or tell the user it is there.
   - If a command here fails, stop, leave the ref in place, and tell the user what failed.
4. Delete the ref: `git update-ref -d <ref>`, whether the work was kept or dropped.
5. Tell the user, in your next message to the user, each work-snapshot handled, what was kept and where, and what was dropped and why. Finishing the dead agent's task is a separate decision, made after the restore."""


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
    probe = run_git(repo, "rev-parse", "--git-dir")
    if probe.returncode != 0 and "not a git repository" in probe.stderr:
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
    lines.append(RESTORE_STEPS.format(module=MODULE_PATH))
    try:
        record_first_listing(first_listed_path(handoff_directory, agent_seat),
                             [snapshot["ref"] for snapshot in leftovers],
                             time.time() if now is None else now,
                             {snapshot["ref"] for snapshot in everything})
    except Exception as error:
        lines.append(f"(Their first listing could not be recorded ({type(error).__name__}: "
                     f"{error}), so scripts/clean-worktrees.py counts them as never listed and keeps them.)")
    return "\n".join(lines)


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


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    repo = Path.cwd()
    if "--repo" in arguments:
        position = arguments.index("--repo")
        if position + 1 >= len(arguments):
            print("uncommitted-work-snapshots: --repo needs a path", file=sys.stderr)
            return 2
        repo = Path(arguments[position + 1])
        del arguments[position:position + 2]
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
