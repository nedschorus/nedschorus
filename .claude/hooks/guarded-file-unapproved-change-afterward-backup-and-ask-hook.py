#!/usr/bin/env python3
"""After every tool call, notice a guarded file changed without the user's approval, keep
every version, and tell the agent to ask him.

Registered under PostToolUse and PostToolUseFailure for every tool. A guarded file is a file
instruction-file-guard.py protects, plus ~/.claude/CLAUDE.md and ~/.claude/settings.json. At
each run the hook compares each checked file's stat data with what it stored at its previous
run, hashes only a file whose stat data differs, logs each new version in this machine's
directory of the log-store kind guarded-file-versions-and-approvals/, copies it there unless
the file's checkout is on a branch whose HEAD commit holds it, and, when the version is not in its path's
approved set, tells the agent to show the user the change and run this program with --approve
or --restore. The change stays in place while he is asked. A version with no copy is read
back from git; a file outside every checkout, such as ~/.claude/CLAUDE.md, is always copied.

    python3 <this file> --approve <path> <hash> [<path> <hash> ...]
    python3 <this file> --restore <path> <hash> [<path> <hash> ...]

Design and tests: docs/issues/1268-catch-a-guarded-file-changed-without-the-user.md.

Exit status: the hook always exits 0, since the tool call has already happened. --approve and
--restore exit 0 when done, 1 when they refuse, when the store cannot be reached, when a
file operation or git fails, or when --restore changes some files and fails on others, and 64 on a bad
command line.
"""

import difflib
import hashlib
import importlib.util
import json
import os
import pickle
import select
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

HOOK_PATH = Path(__file__).resolve()
CLONE_ROOT = HOOK_PATH.parents[2]
HOOK_NAME = HOOK_PATH.stem

LOG_STORE_KIND = "guarded-file-versions-and-approvals"
NED_BOX_STORE = Path("/home/nedlern/nedschorus-logs") / LOG_STORE_KIND / "ned-box"
MAC_MOUNT_POINT = Path("/Volumes/nedhome")
MAC_STORE = MAC_MOUNT_POINT / "nedschorus-logs" / LOG_STORE_KIND / "mac"
LOG_STORE_HOSTNAME = "ned-box"
MAC_MOUNT_FILESYSTEM_TYPE = "smbfs"

# Set by the tests, which stand in for the store, the machine and the Mac's mount.
STORE_DIRECTORY_VARIABLE = "GUARDED_FILE_VERSIONS_STORE_DIRECTORY"
MACHINE_VARIABLE = "GUARDED_FILE_VERSIONS_MACHINE"
MOUNT_TABLE_VARIABLE = "GUARDED_FILE_VERSIONS_MOUNT_TABLE"
MOUNT_POINT_VARIABLE = "GUARDED_FILE_VERSIONS_MOUNT_POINT"
OUTSIDE_STATE_VARIABLE = "GUARDED_FILE_VERSIONS_OUTSIDE_STATE_DIRECTORY"
AGENTS_DIRECTORY_VARIABLE = "GUARDED_FILE_VERSIONS_AGENTS_DIRECTORY"
DEADLINE_VARIABLE = "GUARDED_FILE_VERSIONS_DEADLINE_SECONDS"
OWNER_VARIABLE = "GUARDED_FILE_VERSIONS_OWNER_KEY"

# The hook's timeout in .claude/settings.json is 30 s. On the Mac every store operation runs in
# a child with about half of that, so a hung SMB mount is still reported in additionalContext
# before Claude Code kills the hook.
MAC_STORE_DEADLINE_SECONDS = 15

STATE_FILE_NAME = HOOK_NAME + "-state.json"
APPROVED_FILE_NAME = "approved"
LOG_FILE_NAME = "log"
DELETED = "deleted"
COPY_MODE = 0o600
APPROVAL_MARKER_NAME = ".walk-approved"
# The obvious-fix marker's opening words, as instruction-file-guard.py's refusal gives them.
OBVIOUS_FIX_MARKER_PREFIX = "Obvious fix under CLAUDE.md's standing approval:"
DIFF_MAX_LINES = 40
DIFF_MAX_CHARACTERS = 4000

# Only these keys of ~/.claude/settings.json change what hooks and tools may do; a /model or
# /config change to another key is copied and not asked about.
SETTINGS_KEYS_ASKED_ABOUT = ("hooks", "disableAllHooks", "permissions", "env")

# The tools the instruction-file guard checks before they write, so a successful call to one was
# let through by the guard. Keep this equal to the guard's PreToolUse matcher in settings.json.
FILE_WRITING_TOOLS = ("Edit", "Write", "NotebookEdit")
# A reflog subject starting with this is a commit the agent made; any other subject is git's
# own work: a switch, reset, merge, pull, rebase, cherry-pick or revert.
COMMIT_SUBJECT_PREFIX = "commit"

HOW_GIT = "git"
HOW_EDIT = "edit"
HOW_USER = "user"
HOW_OBVIOUS_FIX = "obvious-fix"
HOW_PRE_APPROVED = "pre-approved"
HOW_STOCK = "stock"
HOW_RENAME = "rename"

# An approval that is not the user's either always adds its version, or adds it only when no
# run has seen that version: a version the log records as seen and not approved enters the set
# only by the user's yes.
APPROVE_ALWAYS = "always"
UNLESS_SEEN = "unless-seen"

EXIT_DONE = 0
EXIT_REFUSED = 1
EXIT_BAD_INVOCATION = 64

ASK_HEADER = (
    "A guarded file changed, and the user has not approved the new version. The change stays in "
    "place while you ask him; this hook has kept a copy of the version.")
ASK_FILE = "{path}, version {key}. Its change against the newest approved version:\n{diff}"
ASK_INSTRUCTIONS = (
    "If you are a subagent, report the change to the agent that dispatched you instead of "
    "asking the user, and do none of the steps below.\n"
    "Show the user each change above and ask him whether he approves it.\n"
    "If he approves, write his words into {marker} at the top of your session's checkout, then "
    "run once: python3 {program} --approve {pairs}\n"
    "If you wrote an obvious-fix marker before you made the change, run that --approve command "
    "without asking him, then tell him what you fixed.\n"
    "If you wrote a `#pre_approved_change` marker before you made the change, run that "
    "--approve command without asking him.\n"
    "If he declines, run: python3 {program} --restore {pairs}\n"
    "If he declines a version that is in a commit, also run, for each such file: "
    "git commit --only -m \"Put back the approved <file name>\" -- <path>")
REMINDER = (
    "Reminder: {path} still holds version {key}, which the user has not approved.\n"
    "If you are a subagent, report the change to the agent that dispatched you instead of "
    "asking the user.\n"
    "Otherwise show him the change and ask him, as this hook's earlier message said.\n"
    "If he approves, write his words into {marker} at the top of your session's checkout, then "
    "run: python3 {program} --approve {path} {key}\n"
    "If he declines, run: python3 {program} --restore {path} {key}")
STORE_FAILED = (
    "The guarded-file backup did not run, so a change to a guarded file is neither copied nor "
    "checked against the versions the user approved: {reason}.\n"
    "Tell the user what failed, with this remedy: {remedy}\n"
    "Once the store can be reached, the next tool call checks the files again.")
REMEDY_NED_BOX = "check that {store} exists and that nedlern can write to it."
REMEDY_MAC = ("check that ned-box is up and that the Mac has mounted ned-box's home share at "
              "/Volumes/nedhome with {store} in it.")
REFUSED = "{program_name} {mode}: refused, nothing was changed: {reason}"
COMMAND_FAILED = ("{program_name} {mode} failed: {reason}. Tell the user, with this message; run "
                  "the command again once the cause is fixed.")
RESTORE_INCOMPLETE = ("{program_name} --restore: not every file was put back; the lines above "
                      "say what was done to each. Tell the user which files failed and why.")


class StoreUnreachable(Exception):
    """The store could not be checked, opened, read or written."""


class RestoreIncomplete(Exception):
    """--restore changed some files and failed on others; args[0] is a line per pair."""


class Refused(Exception):
    """--approve or --restore must not go on."""


class BranchUnreadable(RuntimeError):
    """git could not say whether HEAD is on a branch."""


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_loaded = {}


def loaded(name, path):
    if name not in _loaded:
        _loaded[name] = load_module(name, path)
    return _loaded[name]


def guard():
    """instruction-file-guard.py, whose functions decide what is guarded, so the two hooks
    cannot disagree."""
    return loaded("instruction_file_guard", HOOK_PATH.parent / "instruction-file-guard.py")


def snapshots():
    return loaded("uncommitted_work_snapshots",
                  CLONE_ROOT / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")


# ---------------------------------------------------------------- hashes and checked lines

def blob_hash(data: bytes) -> str:
    """The id git gives these bytes as a blob, as `git hash-object` prints it for a file outside
    every checkout."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def settings_approval_key(data: bytes) -> str:
    """The hash ~/.claude/settings.json is approved by: that of its four keys that change what
    hooks and tools may do, so a /model choice is not asked about."""
    try:
        settings = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return blob_hash(data)
    if not isinstance(settings, dict):
        return blob_hash(data)
    # A missing key is hashed as null. Sorted keys and no spaces make the hash independent of
    # how Claude Code orders and indents the file.
    canonical = json.dumps({key: settings.get(key) for key in SETTINGS_KEYS_ASKED_ABOUT},
                           sort_keys=True, separators=(",", ":"))
    return blob_hash(canonical.encode("utf-8"))


def line_checksum(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def checked_line(body: str) -> bytes:
    return f"{body}\t{line_checksum(body)}\n".encode("utf-8")


def valid_line_bodies(data: bytes):
    """The bodies of the complete lines whose checksum matches; a line a cut-off write left
    incomplete is skipped, never read as an approval."""
    bodies = []
    for raw in data.split(b"\n")[:-1]:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        body, separator, checksum = text.rpartition("\t")
        if separator and checksum == line_checksum(body):
            bodies.append(body)
    return bodies


# ---------------------------------------------------------------- the store

def this_machine():
    override = os.environ.get(MACHINE_VARIABLE)
    if override:
        return override
    return "ned-box" if socket.gethostname().split(".")[0] == LOG_STORE_HOSTNAME else "mac"


def store_directory(machine):
    override = os.environ.get(STORE_DIRECTORY_VARIABLE)
    if override:
        return Path(override)
    return NED_BOX_STORE if machine == "ned-box" else MAC_STORE


def mac_mount_problem(mount_table: str, mount_point: Path):
    """None when mount_point is an SMB mount of ned-box's home share, else what is wrong.

    macOS's `mount` prints each mount as `//user@host/share on /Volumes/x (smbfs, ...)`."""
    for line in mount_table.splitlines():
        source, separator, rest = line.partition(" on ")
        if not separator:
            continue
        point, _, options = rest.rpartition(" (")
        if point != str(mount_point):
            continue
        filesystem = options.split(",", 1)[0].strip(" )")
        if filesystem != MAC_MOUNT_FILESYSTEM_TYPE:
            return f"{mount_point} is a {filesystem} mount, not an SMB mount of ned-box"
        host = source.lstrip("/").split("/", 1)[0].rpartition("@")[2].split(".", 1)[0].lower()
        if host != LOG_STORE_HOSTNAME:
            return f"{mount_point} is mounted from {source}, not from ned-box"
        return None
    return f"{mount_point} is not mounted"


def write_all(fd, data: bytes):
    written = os.write(fd, data)
    if written != len(data):
        raise OSError(f"a short write: {written} of {len(data)} bytes")


class Store:
    """One machine's directory of the store, opened once. Every later read and write is relative
    to the open directory, so a mount that disappears part way fails the operation instead of
    landing on the Mac's own disk; directories are created only below it."""

    def __init__(self, machine):
        self.machine = machine
        self.directory = store_directory(machine)
        if machine == "mac":
            mount_point = Path(os.environ.get(MOUNT_POINT_VARIABLE) or MAC_MOUNT_POINT)
            table_file = os.environ.get(MOUNT_TABLE_VARIABLE)
            try:
                table = (Path(table_file).read_text(encoding="utf-8") if table_file else
                         subprocess.run(["mount"], capture_output=True, text=True, timeout=10,
                                        check=False).stdout)
            except (OSError, subprocess.SubprocessError) as error:
                raise StoreUnreachable(f"the mount table could not be read: {error}")
            problem = mac_mount_problem(table, mount_point)
            if problem:
                raise StoreUnreachable(problem)
        try:
            self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        except OSError as error:
            raise StoreUnreachable(f"{self.directory} could not be opened: {error.strerror}")

    def path_directory(self, path: str, create: bool):
        """An open descriptor of the directory of path's versions, or None when there is none.
        The directory mirrors the path as this machine sees it, without its leading slash."""
        fd = os.dup(self.fd)
        for part in [part for part in path.split("/") if part]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    os.close(fd)
                    return None
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd

    def read(self, path: str, name: str) -> bytes:
        fd = self.path_directory(path, create=False)
        if fd is None:
            return b""
        try:
            file_fd = os.open(name, os.O_RDONLY, dir_fd=fd)
        except FileNotFoundError:
            return b""
        finally:
            os.close(fd)
        try:
            chunks = []
            while True:
                chunk = os.read(file_fd, 1 << 20)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(file_fd)

    def approved(self, path: str):
        return set(valid_line_bodies(self.read(path, APPROVED_FILE_NAME)))

    def approved_in_order(self, path: str):
        return valid_line_bodies(self.read(path, APPROVED_FILE_NAME))

    def log(self, path: str):
        return [body.split("\t") for body in valid_line_bodies(self.read(path, LOG_FILE_NAME))]

    def append(self, path: str, name: str, body: str):
        """Append one checked line in one O_APPEND write; nothing is ever rewritten."""
        fd = self.path_directory(path, create=True)
        try:
            file_fd = os.open(name, os.O_RDWR | os.O_APPEND | os.O_CREAT, COPY_MODE, dir_fd=fd)
        finally:
            os.close(fd)
        try:
            size = os.fstat(file_fd).st_size
            if size and os.pread(file_fd, 1, size - 1) != b"\n":
                # A writer cut off part way left no newline; start this line on its own.
                write_all(file_fd, b"\n")
            write_all(file_fd, checked_line(body))
        finally:
            os.close(file_fd)

    def approve(self, path: str, key: str):
        self.append(path, APPROVED_FILE_NAME, key)

    def copy(self, path: str, copy_hash: str, data: bytes):
        """Keep one copy of a version, named by its hash. A copy that matches its name is never
        replaced, even by an identical one; one that does not match counts as missing."""
        fd = self.path_directory(path, create=True)
        try:
            for attempt in range(2):
                try:
                    file_fd = os.open(copy_hash, os.O_WRONLY | os.O_CREAT | os.O_EXCL, COPY_MODE,
                                      dir_fd=fd)
                except FileExistsError:
                    if blob_hash(self.read(path, copy_hash)) == copy_hash or attempt:
                        return
                    os.unlink(copy_hash, dir_fd=fd)
                    continue
                try:
                    write_all(file_fd, data)
                finally:
                    os.close(file_fd)
                return
        finally:
            os.close(fd)

    def copied_version(self, path: str, copy_hash: str):
        data = self.read(path, copy_hash)
        return data if blob_hash(data) == copy_hash else None

    def kept_version(self, path: str, copy_hash: str):
        """The version's bytes from its copy, else from the git repository of path's checkout;
        None when neither holds it."""
        data = self.copied_version(path, copy_hash)
        if data is None:
            data = version_from_git(path, copy_hash)
        return data


# ---------------------------------------------------------------- versions git holds

# Git holds a version when a commit that a durable ref reaches holds its blob: a branch, a tag
# or a remote-tracking branch. A worktree's detached HEAD is not durable, since removing the
# worktree drops it and gc then drops its commits, and neither are refs/work-snapshots/* and
# refs/stash, deleted within hours, or a blob only staged or only in the object store; a version
# held only there keeps its copy.
DURABLE_REF_OPTIONS = ("--branches", "--tags", "--remotes")


def blobs_durable_refs_hold(checkout):
    """Every blob id a commit reachable from a durable ref of the checkout's repository holds:
    the whole history, so it is for the daily prune, not for the hook's run on every tool call."""
    output = git_text(checkout, "rev-list", "--objects", *DURABLE_REF_OPTIONS, timeout=600)
    # Commits and trees are listed too; only a blob's id can name a copy.
    return {line.split(" ", 1)[0] for line in output.splitlines()}


def versions_head_holds(checkout, versions):
    """The (path, blob id) pairs among versions whose path, in the checkout's HEAD commit, is
    that blob, when HEAD is on a branch; none when HEAD is detached, since a detached HEAD is
    not a durable ref. A branch's HEAD is the one durable ref the hook can ask cheaply on every
    tool call; a version only another durable ref holds is copied, and the daily prune deletes
    the copy. Raises BranchUnreadable, a RuntimeError carrying git's stderr, when git
    symbolic-ref fails with any exit other than 1."""
    relative = {}
    for path, blob_id in versions:
        if blob_id == DELETED:
            continue
        relative[os.path.relpath(Path(path).parent.resolve() / Path(path).name, checkout)] = (
            path, blob_id)
    if not relative:
        return set()
    if subprocess.run(["git", "-C", str(checkout), "rev-parse", "-q", "--verify", "HEAD^{commit}"],
                      capture_output=True, timeout=60, check=False).returncode == 1:
        # A repository with no commit yet holds nothing.
        return set()
    # git symbolic-ref -q exits 1, with nothing on stderr, when HEAD is detached; any other
    # nonzero exit is git failing.
    on_branch = subprocess.run(["git", "-C", str(checkout), "symbolic-ref", "-q", "HEAD"],
                               capture_output=True, timeout=60, check=False)
    if on_branch.returncode == 1:
        return set()
    if on_branch.returncode != 0:
        raise BranchUnreadable(f"git symbolic-ref -q HEAD in {checkout} exited "
                               f"{on_branch.returncode}: "
                               f"{on_branch.stderr.decode(errors='replace').strip()}")
    output = git_text(checkout, "--literal-pathspecs", "ls-tree", "-r", "-z", "--full-tree",
                      "HEAD", "--", *sorted(relative))
    held = set()
    for entry in output.split("\0"):
        header, _, name = entry.partition("\t")
        fields = header.split()
        if len(fields) == 3 and fields[1] == "blob" and name in relative \
                and relative[name][1] == fields[2]:
            held.add(relative[name])
    return held


def version_from_git(path: str, blob_id: str):
    """The blob's bytes from the repository of path's checkout, or None when path is in no
    checkout or the repository does not hold the blob. A git that fails otherwise raises."""
    checkout = guard().enclosing_repository_root(Path(path).parent)
    if checkout is None:
        return None
    exists = subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", blob_id],
                            capture_output=True, timeout=60, check=False)
    # git cat-file -e exits 1, silently, for an object the repository does not hold.
    if exists.returncode == 1 and not exists.stderr:
        return None
    if exists.returncode != 0:
        raise RuntimeError(f"git cat-file -e {blob_id} in {checkout} exited {exists.returncode}: "
                           f"{exists.stderr.decode(errors='replace').strip()}")
    data = subprocess.run(["git", "-C", str(checkout), "cat-file", "blob", blob_id],
                          capture_output=True, timeout=60, check=False)
    if data.returncode != 0 or blob_hash(data.stdout) != blob_id:
        raise RuntimeError(f"git cat-file blob {blob_id} in {checkout} exited {data.returncode}: "
                           f"{data.stderr.decode(errors='replace').strip()}")
    return data.stdout


# ---------------------------------------------------------------- the log

def log_line(store, path, kind, *fields):
    store.append(path, LOG_FILE_NAME, "\t".join([kind, str(time.time_ns()), *fields]))


def log_seen(store, path, session, owner, key, copy_hash, how=""):
    """One line per version seen: time, session, the session's process, hash, copy, and how
    the version entered the approved set, if it did."""
    log_line(store, path, "seen", session, owner, key, copy_hash, how)


def seen_lines(log, key):
    return [fields for fields in log if fields[0] == "seen" and len(fields) >= 7
            and fields[4] == key]


def first_seen_time(log, key):
    lines = seen_lines(log, key)
    return int(lines[0][1]) if lines else None


def asking_session(log, key):
    """(session, owner) asked about key: the last one named after a handoff, else the session
    whose run first saw the version."""
    asking = None
    for fields in log:
        if fields[0] == "seen" and len(fields) >= 7 and fields[4] == key and asking is None:
            asking = (fields[2], fields[3])
        elif fields[0] == "asking" and len(fields) >= 5 and fields[4] == key:
            asking = (fields[2], fields[3])
    return asking


def was_reminded(log, key, session):
    return any(fields[0] == "reminded" and len(fields) >= 4 and fields[2] == session
               and fields[3] == key for fields in log)


def copy_of(log, key):
    """The copy the log names for a key; for settings.json the key and the copy differ."""
    for fields in reversed(seen_lines(log, key)):
        return fields[5]
    return key


def newest_approved(store, path, log, excluded):
    """(key, copy hash) of the version approved last, other than the excluded key, or None."""
    for key in reversed(store.approved_in_order(path)):
        if key != excluded:
            return key, (DELETED if key == DELETED else copy_of(log, key))
    return None


# ---------------------------------------------------------------- local state

def outside_state_path():
    override = os.environ.get(OUTSIDE_STATE_VARIABLE)
    directory = Path(override) if override else Path.home() / ".cache" / HOOK_NAME
    return directory / STATE_FILE_NAME


def read_state(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def write_state(path: Path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)


def stat_data(path: str):
    try:
        result = os.stat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(result.st_mode):
        return None
    return [result.st_ctime_ns, result.st_mtime_ns, result.st_size, result.st_ino]


# ---------------------------------------------------------------- what is checked

def home_directory():
    return Path(os.environ.get("HOME") or Path.home())


def outside_files():
    claude = home_directory() / ".claude"
    return [str(claude / "CLAUDE.md"), str(claude / "settings.json")]


def is_settings_file(path: str):
    return path == str(home_directory() / ".claude" / "settings.json")


def git_text(checkout, *arguments, input_text=None, timeout=60):
    result = subprocess.run(["git", "-C", str(checkout), *arguments], capture_output=True,
                            input=None if input_text is None else input_text.encode(),
                            timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} in {checkout} exited {result.returncode}: "
                           f"{result.stderr.decode(errors='replace').strip()}")
    return result.stdout.decode("utf-8", errors="surrogateescape")


def could_be_guarded(relative: str):
    """A cheap test that keeps every path the guard can protect; the guard's own functions
    then decide."""
    if "__pycache__/" in relative:
        # Python's byte-code caches under .claude/hooks/ change on every run of a hook and
        # instruct no one.
        return False
    name = relative.rsplit("/", 1)[-1]
    if name == "scheduled_tasks.lock" and ".claude/" in "/" + relative:
        # Claude Code's own scheduler lock is rewritten by Claude Code, whether git ignores it or not.
        return False
    return (name in ("CLAUDE.md", "CLAUDE.local.md") or ".claude/" in "/" + relative
            or name.endswith(".md"))


def is_guarded(path: str):
    module = guard()
    return (module.is_protected(path) or module.is_reusable_prompt(path)
            or module.is_reviewed_document(path))


def checkout_files(checkout: Path, decisions: dict):
    """Every guarded file in the checkout: tracked files, untracked files that git does not
    ignore, and ignored CLAUDE.local.md and .claude/settings.local.json files. Other ignored files are never listed, since
    Claude Code's own runtime files under .claude/, such as scheduled_tasks.lock, are ignored
    and rewritten by Claude Code itself.

    decisions caches the guard's answer for each listed path between runs, since deciding takes
    most of a run's time; it is dropped when instruction-file-guard.py changes."""
    listed = git_text(checkout, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    # An ignored file can be an instruction only as CLAUDE.local.md or .claude/settings.local.json
    # (usually ignored); listing all ignored files under .claude/ would catch Claude Code's runtime
    # files, and large ignored trees are never read.
    ignored = git_text(checkout, "ls-files", "-z", "--others", "--ignored", "--exclude-standard",
                       "--", ":(glob)**/CLAUDE.local.md",
                       ":(glob)**/.claude/settings.local.json")
    guard_version = str(stat_data(str(HOOK_PATH.parent / "instruction-file-guard.py")))
    if decisions.get("") != guard_version:
        decisions.clear()
        decisions[""] = guard_version
    paths = []
    for relative in set((listed + ignored).split("\0")):
        if not relative or not could_be_guarded(relative):
            continue
        absolute = str(checkout / relative)
        if not os.path.isfile(absolute):
            # Not decided while absent, so the file is classified when it comes back.
            continue
        if relative not in decisions:
            decisions[relative] = is_guarded(absolute)
        if decisions[relative]:
            paths.append(absolute)
    return sorted(paths)


def hashes_in_checkout(checkout: Path, paths):
    """The blob id git gives each file, its path's filters applied, as git hash-object --path."""
    if not paths:
        return {}
    output = git_text(checkout, "hash-object", "--stdin-paths",
                      input_text="".join(path + "\n" for path in paths))
    return dict(zip(paths, output.split()))


def reflog_entries(git_directory: Path):
    """[[new commit, time, subject]] of HEAD's reflog, oldest first."""
    try:
        data = (git_directory / "logs" / "HEAD").read_bytes()
    except FileNotFoundError:
        return []
    entries = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        head, _, subject = line.partition("\t")
        fields = head.split()
        if len(fields) >= 4:
            entries.append([fields[1], fields[-2], subject])
    return entries


def entries_after(entries, position):
    """The reflog entries newer than the stored position, found by the entry's commit and
    time, not by the reflog's length, which expiry can keep constant."""
    if not position:
        return []
    for index in range(len(entries) - 1, -1, -1):
        if entries[index][:2] == position[:2]:
            return entries[index + 1:]
    return [entry for entry in entries if int(entry[1]) > int(position[1])]


def git_operation_in_progress(checkout: Path):
    location_guard = loaded("session_location_write_guard",
                            HOOK_PATH.parent / "session-location-write-guard.py")
    return location_guard.git_operation_in_progress(checkout)


def guarded_blobs_at(checkout: Path, commit: str):
    """{absolute path: blob id} of the guarded files in a commit's tree."""
    blobs = {}
    for entry in git_text(checkout, "ls-tree", "-r", "-z", "--full-tree", commit).split("\0"):
        meta, _, relative = entry.partition("\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob" or not could_be_guarded(relative):
            continue
        absolute = str(checkout / relative)
        if is_guarded(absolute):
            blobs[absolute] = parts[2]
    return blobs


def introduced_by(checkout: Path, commits):
    """{(absolute path, blob)} the given commits introduced."""
    introduced = set()
    for commit in commits:
        fields = git_text(checkout, "diff-tree", "-r", "-z", "--root", "--no-renames",
                          "--no-commit-id", commit).split("\0")
        for meta, relative in zip(fields[0::2], fields[1::2]):
            parts = meta.split()
            if len(parts) >= 4:
                introduced.add((str(checkout / relative), parts[3]))
    return introduced


# ---------------------------------------------------------------- sessions

def this_owner_key():
    """The calling claude process's key. A session whose claude process is gone has ended, a
    handoff included; the work-snapshot module already tells a live process from an ended one."""
    override = os.environ.get(OWNER_VARIABLE)
    if override is not None:
        return override
    try:
        module = snapshots()
        process = module.claude_owner_process_id(os.getppid())
        return module.owner_key_of_process(process) if process is not None else "unknown"
    except Exception:
        return "unknown"


def owner_alive(owner_key):
    if owner_key in ("", "unknown"):
        return False
    if os.environ.get(OWNER_VARIABLE) is not None:
        # The tests name owners; one starting with "ended-" stands for an ended session.
        return not owner_key.startswith("ended-")
    try:
        return snapshots().owner_process_is_alive(owner_key)
    except Exception:
        return True


# ---------------------------------------------------------------- one run of the hook

def diff_text(before: bytes, after: bytes, path: str):
    before_lines = before.decode("utf-8", errors="replace").splitlines(keepends=True)
    after_lines = after.decode("utf-8", errors="replace").splitlines(keepends=True)
    lines = list(difflib.unified_diff(before_lines, after_lines, "approved", "now", n=2))
    shown = "".join(lines[:DIFF_MAX_LINES])[:DIFF_MAX_CHARACTERS]
    if len(lines) > DIFF_MAX_LINES or len(shown) < len("".join(lines)):
        shown += f"\n[... the diff is cut here; compare {path} with the approved copy]"
    return shown or "(no line differs)"


class Check:
    """What one run found about one checked file, to be settled in the store."""

    def __init__(self, path, data, key, copy_hash, how="", in_git=False):
        self.path, self.data, self.key, self.copy_hash, self.how = path, data, key, copy_hash, how
        self.in_git = in_git


def store_phase(store, session, owner, checks, unsettled_unchanged, approvals, quiet):
    """Everything that touches the store. Returns (asks, reminders, settled paths).

    approvals: [(path, key, how, rule)] git's own work and renames, recorded before the checks.
    checks: the files whose content changed, each copied unless its checkout's branch HEAD
    holds it.
    unsettled_unchanged: [(path, key)] files left unsettled by an earlier run. quiet: a rebase,
    merge, cherry-pick or revert is stopped, so every version is copied and nothing is asked."""
    for path, key, how, rule in approvals:
        approved = store.approved(path)
        if key in approved:
            continue
        if rule != APPROVE_ALWAYS:
            if seen_lines(store.log(path), key):
                continue
        store.approve(path, key)
        log_line(store, path, "approved", session, owner, key, how)
    asks, reminders, settled = [], [], {}
    for check in checks:
        if check.key != DELETED and not check.in_git:
            store.copy(check.path, check.copy_hash, check.data)
        log = store.log(check.path)
        approved = store.approved(check.path)
        new_approval = ""
        if check.key not in approved and check.how:
            store.approve(check.path, check.key)
            approved.add(check.key)
            new_approval = check.how
        log_seen(store, check.path, session, owner, check.key, check.copy_hash, new_approval)
        if check.key in approved:
            settled[check.path] = True
            continue
        settled[check.path] = False
        if quiet:
            continue
        asking = asking_session(log, check.key)
        if asking is None or asking[0] == session or not owner_alive(asking[1]):
            if asking is not None and asking[0] != session:
                log_line(store, check.path, "asking", session, owner, check.key)
            asks.append(ask_entry(store, check, log))
        elif not was_reminded(log, check.key, session):
            log_line(store, check.path, "reminded", session, check.key)
            reminders.append((check.path, check.key))
    for path, key in unsettled_unchanged:
        approved = store.approved(path)
        if key in approved:
            settled[path] = True
            continue
        settled[path] = False
        if quiet:
            continue
        log = store.log(path)
        asking = asking_session(log, key)
        if asking is not None and asking[0] != session and not owner_alive(asking[1]):
            data = b"" if key == DELETED else read_file(path)
            log_line(store, path, "asking", session, owner, key)
            asks.append(ask_entry(store, Check(path, data, key, copy_of(log, key)), log))
        elif asking is None or asking[0] == session:
            reminders.append((path, key))
        elif not was_reminded(log, key, session):
            log_line(store, path, "reminded", session, key)
            reminders.append((path, key))
    return asks, reminders, settled


def read_file(path):
    """The file's bytes. A read that fails raises, so the run reports the failure instead of
    keeping an empty version as if it were the file."""
    return Path(path).read_bytes()


def ask_entry(store, check, log):
    newest = newest_approved(store, check.path, log, check.key)
    if newest is None or newest[1] == DELETED:
        before = b""
    else:
        before = store.kept_version(check.path, newest[1]) or b""
    after = b"" if check.key == DELETED else check.data
    return check.path, check.key, diff_text(before, after, check.path)


def run_with_deadline(function, deadline_seconds):
    """Run function in a child process and return its result, or raise StoreUnreachable at the
    deadline, after killing the child: a mount that is still listed while ned-box has gone can
    make a read wait for SMB to reconnect."""
    read_end, write_end = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_end)
        try:
            result = ("ok", function())
        except StoreUnreachable as error:
            result = ("unreachable", str(error))
        except Exception as error:
            result = ("unreachable", f"{type(error).__name__}: {error}")
        try:
            write_all(write_end, pickle.dumps(result))
        finally:
            os._exit(0)
    os.close(write_end)
    chunks = []
    end = time.monotonic() + deadline_seconds
    try:
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                os.kill(child, signal.SIGKILL)
                raise StoreUnreachable(
                    f"the store did not answer within {deadline_seconds} seconds")
            ready, _, _ = select.select([read_end], [], [], remaining)
            if ready:
                chunk = os.read(read_end, 1 << 16)
                if not chunk:
                    break
                chunks.append(chunk)
    finally:
        os.close(read_end)
        os.waitpid(child, 0)
    status, value = pickle.loads(b"".join(chunks)) if chunks else ("unreachable", "no answer")
    if status != "ok":
        raise StoreUnreachable(value)
    return value


def deadline_seconds():
    return float(os.environ.get(DEADLINE_VARIABLE) or MAC_STORE_DEADLINE_SECONDS)


def with_store(machine, work):
    """work(store) where the machine's store is; on the Mac in a child with a deadline."""
    if machine == "mac":
        return run_with_deadline(lambda: work(Store(machine)), deadline_seconds())
    return work(Store(machine))


def scan(files, state_files, hash_function):
    """(changed {path: (stat, data, key, copy hash)}, unchanged unsettled [(path, key)])."""
    changed, unsettled = {}, []
    needs_hash = []
    for path in files:
        now = stat_data(path)
        before = state_files.get(path)
        if now is None:
            if before is not None and before[4] != DELETED:
                changed[path] = (None, b"", DELETED, DELETED)
            continue
        if before is not None and before[:4] == now:
            if not before[6]:
                unsettled.append((path, before[4]))
            continue
        needs_hash.append((path, now))
    hashes = hash_function([path for path, _ in needs_hash])
    for path, now in needs_hash:
        data = read_file(path)
        copy_hash = hashes.get(path) or blob_hash(data)
        key = settings_approval_key(data) if is_settings_file(path) else copy_hash
        before = state_files.get(path)
        if before is not None and before[4] == key and before[5] == copy_hash:
            # Only the stat data changed, as after a touch.
            state_files[path] = now + before[4:]
            if not before[6]:
                unsettled.append((path, key))
            continue
        changed[path] = (now, data, key, copy_hash)
    for path, before in list(state_files.items()):
        if path in files or path in changed:
            continue
        if os.path.isfile(path):
            # No longer listed as guarded though present, such as a file git now ignores:
            # forget it, so it is neither reported deleted nor reminded about.
            del state_files[path]
            continue
        if before[4] != DELETED:
            changed[path] = (None, b"", DELETED, DELETED)
        elif not before[6]:
            unsettled.append((path, DELETED))
    return changed, unsettled


def run_hook(payload):
    """Messages for the agent, possibly none."""
    session = str(payload.get("session_id") or "unknown-session")
    tool = payload.get("tool_name") or ""
    event = payload.get("hook_event_name") or "PostToolUse"
    tool_input = payload.get("tool_input") or {}
    written = tool_input.get("file_path") or tool_input.get("notebook_path")
    written = os.path.abspath(written) if written else None
    edit_succeeded = event == "PostToolUse" and tool in FILE_WRITING_TOOLS
    machine = this_machine()
    cwd = Path(payload.get("cwd") or os.getcwd())
    groups = []

    outside_path = outside_state_path()
    outside_state = read_state(outside_path)
    outside_stocking = outside_state is None
    outside_state = outside_state or {"files": {}}
    groups.append(("outside", outside_path, outside_state, outside_files(), None, outside_stocking))

    checkout = guard().enclosing_repository_root(cwd) if cwd.is_dir() else None
    if checkout is not None:
        git_directory = Path(git_text(checkout, "rev-parse", "--absolute-git-dir").strip())
        checkout_path = git_directory / STATE_FILE_NAME
        checkout_state = read_state(checkout_path)
        checkout_stocking = checkout_state is None
        checkout_state = checkout_state or {"files": {}, "reflog": None, "stopped": False}
        decisions = checkout_state.setdefault("guarded", {})
        decisions_before = dict(decisions)
        groups.append(("checkout", checkout_path, checkout_state, checkout_files(checkout, decisions),
                       (checkout, git_directory), checkout_stocking))

    owner_cache = []

    def owner():
        if not owner_cache:
            owner_cache.append(this_owner_key())
        return owner_cache[0]

    plans = []
    for kind, state_path, state, files, repository, stocking in groups:
        hash_function = ((lambda paths, checkout=repository[0]: hashes_in_checkout(checkout, paths))
                         if repository else (lambda paths: {}))
        listed_before = set(state["files"])
        changed, unsettled = scan(files, state["files"], hash_function)
        approvals, quiet, new_position, held = [], False, None, set()
        if repository is not None:
            checkout, git_directory = repository
            held = versions_head_holds(checkout, [(path, value[3])
                                                  for path, value in changed.items()])
            entries = reflog_entries(git_directory)
            new_position = entries[-1][:2] if entries else None
            window = [] if stocking else entries_after(entries, state.get("reflog"))
            # Loading the in-progress check costs more than a whole quiet run, so it is asked
            # only when there is something it could change.
            if changed or unsettled or window or state.get("stopped"):
                quiet = git_operation_in_progress(checkout)
            if quiet:
                new_position = state.get("reflog")
            elif window:
                approvals = git_own_work(checkout, window, state, changed)
        plans.append([kind, state_path, state, files, changed, unsettled, approvals, quiet,
                      new_position, stocking, set(state["files"]) != listed_before, held])

    stocking_machine = outside_stocking
    nothing_to_do = all(not plan[4] and not plan[5] and not plan[6] and not plan[9]
                        for plan in plans)
    if nothing_to_do:
        for plan in plans:
            moved = plan[8] is not None and plan[2].get("reflog") != plan[8]
            if moved or plan[10] or (plan[0] == "checkout"
                                     and plan[2].get("guarded") != decisions_before):
                if moved:
                    plan[2]["reflog"] = plan[8]
                write_state(plan[1], plan[2])
        return []

    def work(store):
        results = []
        if stocking_machine:
            for path in seat_briefs():
                if not store.approved(path):
                    data = read_file(path)
                    key = blob_hash(data)
                    store.copy(path, key, data)
                    store.approve(path, key)
                    log_seen(store, path, session, owner(), key, key, HOW_STOCK)
        for plan in plans:
            (kind, state_path, state, files, changed, unsettled, approvals, quiet, _, stocking, _,
             held) = plan
            checks = []
            for path, (now, data, key, copy_hash) in changed.items():
                how = ""
                if stocking:
                    log = store.log(path)
                    if not (key not in store.approved(path) and seen_lines(log, key)):
                        how = HOW_STOCK
                elif edit_succeeded and written == path:
                    how = HOW_EDIT
                checks.append(Check(path, data, key, copy_hash, how, (path, copy_hash) in held))
            approvals = approvals + renames(store, changed, state["files"])
            results.append(store_phase(store, session, owner(), checks, unsettled, approvals,
                                       quiet))
        return results

    try:
        results = with_store(machine, work)
    except (StoreUnreachable, OSError, RuntimeError) as error:
        remedy = (REMEDY_MAC if machine == "mac" else REMEDY_NED_BOX).format(
            store=store_directory(machine))
        return [STORE_FAILED.format(reason=str(error).rstrip("."), remedy=remedy)]

    asks, reminders = [], []
    for plan, (plan_asks, plan_reminders, settled) in zip(plans, results):
        state, changed = plan[2], plan[4]
        for path, (now, _, key, copy_hash) in changed.items():
            if now is None:
                state["files"][path] = [0, 0, 0, 0, DELETED, DELETED, settled.get(path, False)]
            else:
                state["files"][path] = now + [key, copy_hash, settled.get(path, False)]
        for path, is_settled in settled.items():
            if path in state["files"]:
                state["files"][path][6] = is_settled
        for path in [path for path, value in state["files"].items()
                     if value[4] == DELETED and value[6]]:
            del state["files"][path]
        if plan[8] is not None:
            state["reflog"] = plan[8]
        if "stopped" in state:
            state["stopped"] = plan[7]
        write_state(plan[1], state)
        asks += plan_asks
        reminders += plan_reminders
    return messages(asks, reminders)


def seat_briefs():
    """The seat-briefs, found as the transcript mirror finds them."""
    agents = Path(os.environ.get(AGENTS_DIRECTORY_VARIABLE) or home_directory() / "agents")
    if not agents.is_dir():
        return []
    mirror = loaded("transcript_mirror_to_log_store",
                    CLONE_ROOT / "scripts" / "transcript-mirror-to-log-store.py")
    return [str(agents / relative) for relative in mirror.seat_briefs_in(agents)]


def renames(store, changed, state_files):
    """A path that disappeared and a path that appeared in one run with the same content: when
    the content was approved under the old path, both are settled."""
    approvals = []
    gone = {path: state_files[path][4] for path, value in changed.items()
            if value[2] == DELETED and path in state_files}
    for path, (now, _, key, _) in changed.items():
        if now is None or path in state_files:
            continue
        for old_path, old_key in gone.items():
            if old_key == key and key in store.approved(old_path):
                approvals.append((path, key, HOW_RENAME, APPROVE_ALWAYS))
                approvals.append((old_path, DELETED, HOW_RENAME, APPROVE_ALWAYS))
                break
    return approvals


def git_own_work(checkout, window, state, changed):
    """The approvals git's own work since the previous run makes, for the files whose content
    changed: the versions HEAD holds now, less the versions the agent's own commits in the same
    window introduced. After a stopped operation the commit that finishes it is git's own work
    too."""
    finishing = state.get("stopped", False)
    commit_entries = [entry[2].startswith(COMMIT_SUBJECT_PREFIX) for entry in window]
    if all(commit_entries) and not finishing:
        return []
    own_commits = [] if finishing else [entry[0] for entry, is_commit
                                        in zip(window, commit_entries) if is_commit]
    excluded = introduced_by(checkout, own_commits)
    head_blobs = guarded_blobs_at(checkout, "HEAD")
    approvals = []
    for path, value in changed.items():
        blob = head_blobs.get(path, DELETED)
        if (value[2] == blob or (value[0] is None and blob == DELETED)) \
                and (path, blob) not in excluded:
            approvals.append((path, blob, HOW_GIT, UNLESS_SEEN))
    return approvals


def messages(asks, reminders):
    out = []
    if asks:
        program = str(HOOK_PATH)
        pairs = " ".join(f"{path} {key}" for path, key, _ in asks)
        files = "\n\n".join(ASK_FILE.format(path=path, key=key, diff=diff)
                            for path, key, diff in asks)
        out.append("\n\n".join([ASK_HEADER, files, ASK_INSTRUCTIONS.format(
            marker=APPROVAL_MARKER_NAME, program=program, pairs=pairs)]))
    for path, key in reminders:
        out.append(REMINDER.format(path=path, key=key, marker=APPROVAL_MARKER_NAME,
                                   program=HOOK_PATH))
    return out


# ---------------------------------------------------------------- --approve and --restore

def current_version(path: str):
    """(key, copy hash, data) of the file as it is now; (DELETED, DELETED, b"") when absent."""
    if stat_data(path) is None:
        return DELETED, DELETED, b""
    data = read_file(path)
    checkout = guard().enclosing_repository_root(Path(path).parent)
    copy_hash = (hashes_in_checkout(checkout, [path]).get(path) if checkout is not None
                 else None) or blob_hash(data)
    key = settings_approval_key(data) if is_settings_file(path) else copy_hash
    return key, copy_hash, data


def pairs_from(arguments):
    if not arguments or len(arguments) % 2:
        return None
    return [(os.path.abspath(path), key) for path, key in zip(arguments[0::2], arguments[1::2])]


def approve(pairs, cwd: Path):
    """Record each (path, hash) as approved, by the user's words, an obvious-fix marker or a
    pre-approved-change marker, spending the approval marker once."""
    checkout = guard().enclosing_repository_root(cwd)
    if checkout is None:
        raise Refused(f"{cwd} is in no checkout, so there is no {APPROVAL_MARKER_NAME} to read; "
                      "run this command from your session's checkout")
    marker = checkout / APPROVAL_MARKER_NAME
    words = loaded("guard_approval_marker",
                   HOOK_PATH.parent / "guard_approval_marker.py").read_marker_approval(marker)
    if words is None:
        raise Refused(f"there is no approval in {marker}. Show the user each change and ask him; "
                      f"if he approves, write his words into {marker} and run this command again")
    first_line = guard().PRE_APPROVED_CHANGE_MARKER_FIRST_LINE
    pre_approved = words.splitlines()[0].rstrip() == first_line
    if pre_approved and guard().pre_approved_change_marker_gives_no_reason(words):
        raise Refused(f"{marker} has `{first_line}` as its first line but no second line naming "
                      "the exception on the approval page the change falls under, or `on neither "
                      "list`, so it approves nothing. Put that on its second line and run this "
                      "command again")
    obvious_fix = words.startswith(OBVIOUS_FIX_MARKER_PREFIX)
    if pre_approved:
        # One log field: a tab in the agent's words would split it.
        exception = " ".join(words.splitlines()[1].split())
        how, extra_fields = HOW_PRE_APPROVED, [exception]
        late_marker_kind = f"`{first_line}` marker"

        def late_marker_line(path):
            return (f"A change to the guarded file {path} that needs no approval as "
                    f"`{exception}`; the marker was written after the change, so it needs your yes")
    elif obvious_fix:
        fix = " ".join(line.strip() for line in words[len(OBVIOUS_FIX_MARKER_PREFIX):].splitlines()
                       if line.strip()) or "(the marker does not say what)"
        how, extra_fields = HOW_OBVIOUS_FIX, []
        late_marker_kind = "obvious-fix marker"

        def late_marker_line(path):
            return (f"An obvious fix to the guarded file {path}; the marker was written after the "
                    f"change, so it needs your yes: {fix}")
    else:
        how, extra_fields = HOW_USER, []
    marker_time = os.stat(marker).st_mtime_ns
    for path, key in pairs:
        now = current_version(path)[0]
        if now != key:
            raise Refused(f"{path} no longer holds version {key} but {now}, so the user was not "
                          "shown this version. Show him the change the hook's latest message "
                          "gives, and ask him again")

    def work(store, end):
        logs = {path: store.log(path) for path, _ in pairs}
        if how != HOW_USER:
            for path, key in pairs:
                seen = first_seen_time(logs[path], key)
                # Equal times count as the marker coming after, so the change goes to the user.
                if seen is None or marker_time >= seen:
                    raise Refused(
                        f"the {late_marker_kind} in {marker} was written after this hook first "
                        f"saw {path} at version {key}, so it cannot approve that version. Show "
                        "the user the change and ask him, starting with this line: "
                        f"\"{late_marker_line(path)}\". If he approves, write his words "
                        f"into {marker} and run this command again")
        if time.monotonic() > end:
            raise StoreUnreachable("the deadline passed before the approval was recorded")
        for path, key in pairs:
            if key not in store.approved(path):
                store.approve(path, key)
            log_line(store, path, "approved", "command-line", "", key, how, *extra_fields)
        return True

    run_command_work(work)
    loaded("guard_approval_marker", HOOK_PATH.parent / "guard_approval_marker.py") \
        .consume_approval_marker(marker)
    return [f"Approved {path} at version {key}." for path, key in pairs]


def restore(pairs):
    """Put back the newest approved version of each declined (path, hash)."""
    current, held = {}, set()
    for path, key in pairs:
        now = current_version(path)
        if now[0] != key:
            raise Refused(f"{path} no longer holds the declined version {key} but {now[0]}, so it "
                          "changed after the user was shown it. Show him the change the hook's "
                          "latest message gives, and ask him again")
        current[path] = now
        checkout = guard().enclosing_repository_root(Path(path).parent)
        try:
            if checkout is not None and versions_head_holds(checkout, [(path, now[1])]):
                held.add(path)
        except BranchUnreadable:
            # --restore keeps its exit code by reading this as a detached HEAD; copying a
            # version a commit may hold loses nothing.
            pass

    def work(store, end):
        plan = []
        for path, key in pairs:
            _, copy_hash, data = current[path]
            if key != DELETED and path not in held:
                store.copy(path, copy_hash, data)
            log = store.log(path)
            newest = newest_approved(store, path, log, key)
            content = None
            if newest is not None and newest[0] != DELETED:
                content = store.kept_version(path, newest[1])
                if content is None:
                    raise StoreUnreachable(f"the approved version {newest[1]} of {path} is in "
                                           "neither the guarded-file store's copies of that "
                                           "file nor the git repository of its checkout")
            plan.append((path, key, newest, content))
        if time.monotonic() > end:
            raise StoreUnreachable("the deadline passed before any version was put back")
        lines, failed = [], []
        for path, key, newest, content in plan:
            try:
                if content is None:
                    if os.path.lexists(path):
                        os.unlink(path)
                    restored = DELETED
                    # Absence is the version the user chose, so the next run does not ask again.
                    if DELETED not in store.approved(path):
                        store.approve(path, DELETED)
                    message = f"Deleted {path}: it has no approved version."
                else:
                    put_back(path, content)
                    restored = newest[0]
                    message = f"Put back the approved version {restored} of {path}."
                log_line(store, path, "restored", "command-line", "", key, restored)
            except OSError as error:
                failed.append(path)
                lines.append(f"Failed on {path}, which may be only part way restored: {error}")
                continue
            lines.append(message)
        return lines, failed

    lines, failed = run_command_work(work)
    for path, key in pairs:
        checkout = guard().enclosing_repository_root(Path(path).parent)
        if checkout is None or key == DELETED or path in failed:
            continue
        relative = os.path.relpath(path, checkout)
        tree = subprocess.run(["git", "-C", str(checkout), "ls-tree", "HEAD", "--", relative],
                              capture_output=True, text=True, check=False).stdout.split()
        if len(tree) >= 3 and tree[2] == current[path][1]:
            lines.append(f"The declined version is in a commit; run: git commit --only -m "
                         f"\"Put back the approved {Path(path).name}\" -- {path}")
    if failed:
        raise RestoreIncomplete(lines)
    return lines


def put_back(path, content: bytes):
    # A declined deletion may have taken the file's folder with it.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.{os.getpid()}.restore"
    mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o644
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        write_all(descriptor, content)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def run_command_work(work):
    machine = this_machine()
    if machine == "mac":
        seconds = deadline_seconds()
        return run_with_deadline(lambda: work(Store(machine), time.monotonic() + seconds - 1),
                                 seconds)
    return work(Store(machine), float("inf"))


# ---------------------------------------------------------------- main

def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if arguments and arguments[0] in ("--approve", "--restore"):
        mode = arguments[0]
        pairs = pairs_from(arguments[1:])
        if pairs is None:
            print(f"usage: python3 {HOOK_PATH} {mode} <path> <hash> [<path> <hash> ...]",
                  file=sys.stderr)
            return EXIT_BAD_INVOCATION
        try:
            lines = approve(pairs, Path.cwd()) if mode == "--approve" else restore(pairs)
        except RestoreIncomplete as error:
            print("\n".join(error.args[0]))
            print(RESTORE_INCOMPLETE.format(program_name=HOOK_PATH.name), file=sys.stderr)
            return EXIT_REFUSED
        except (Refused, StoreUnreachable) as error:
            print(REFUSED.format(program_name=HOOK_PATH.name, mode=mode, reason=error),
                  file=sys.stderr)
            return EXIT_REFUSED
        except (OSError, RuntimeError) as error:
            print(COMMAND_FAILED.format(program_name=HOOK_PATH.name, mode=mode, reason=error),
                  file=sys.stderr)
            return EXIT_REFUSED
        print("\n".join(lines))
        return EXIT_DONE
    if arguments:
        print(f"usage: python3 {HOOK_PATH} [--approve | --restore <path> <hash> ...]",
              file=sys.stderr)
        return EXIT_BAD_INVOCATION
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as error:
        payload, texts = {}, [STORE_FAILED.format(reason=f"the hook's input was not JSON: {error}",
                                                  remedy="tell the user this hook got bad input.")]
    else:
        try:
            texts = run_hook(payload)
        except Exception as error:
            texts = [STORE_FAILED.format(reason=f"{type(error).__name__}: {error}",
                                         remedy="tell the user the hook failed, with this message.")]
    if texts:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": payload.get("hook_event_name") or "PostToolUse",
            "additionalContext": "\n\n".join(texts)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
