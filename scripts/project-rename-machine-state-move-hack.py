#!/usr/bin/env python3
"""Move one machine's state outside the repository from the nedschorus names to the nedsnodes names, and back.

The user runs it in the stopped window of the project rename, once on each machine: --apply on ned-box first, then on the Mac (the Mac step), because the Mac reaches the log-store through ned-box's home share and its --apply refuses until ned-box has renamed the log-store; --rollback in the reverse order, the Mac first, then ned-box.

Usage:
  scripts/project-rename-machine-state-move-hack.py (--check | --apply | --rollback)
      [--machine mac|ned-box] [--home DIR] [--claude-dir DIR] [--claude-json FILE]
      [--config-dir DIR] [--projects-dir DIR] [--log-store-parent DIR]
      [--systemd-user-dir DIR] [--launch-agents-dir DIR] [--authorized-keys FILE] [--journal FILE]

--check reports, without changing anything, whether --apply would refuse and why, how many changes each step has left to make, whether a journal file exists and how many of its entries --rollback already reversed, whether `git status` works in every worktree of the reference-checkout, and each worktree git lists whose directory is missing, as after a move whose repair did not run.

--apply first refuses, changing nothing, unless all of these hold: no scheduled job of this project is installed (a crontab line naming the reference-checkout, the worktrees directory or the log-store, a `com.nedschorus.*` or `com.nedsnodes.*` LaunchAgent plist other than com.nedschorus.mount-ned-box-home-share, whose mount the Mac step (this program's --apply on the Mac) needs and whose plist this program leaves as it is, a systemd user unit naming one of those paths, other than the units step 8 moves); `~/.claude/.transcript-mirror.lock` is not held; no process named `claude` runs on this machine; none of the `nc-*` systemd user units step 8 renames is active; no path a step would create already exists; the reference-checkout is on main with no uncommitted change to a tracked file (untracked files are allowed and move with it); every worktree git lists for the reference-checkout has its directory, since `git worktree repair` cannot repair one that is missing; no journal exists yet; on the Mac, the log-store is already at its new name under the /Volumes/nedhome mount. It also refuses when it cannot find out: the crontab or the process list cannot be read, ~/.claude.json is not JSON, or the reference-checkout is missing or `git worktree list` fails in it. Then it journals the path flags it was given, each with its value, and, in this order, journals each change before making it:
  1. renames ~/Projects/nedschorus to ~/Projects/nedsnodes and ~/Projects/nedschorus-worktrees to ~/Projects/nedsnodes-worktrees;
  2. on ned-box only, renames the log-store ~/nedschorus-logs to ~/nedsnodes-logs;
  2a. on the Mac as on ned-box, runs `git worktree repair` in this machine's reference-checkout with the new path of every worktree it listed before step 1, runs `git status` in every worktree, stopping when one fails, and sets core.hooksPath to the new path when it named the old checkout path;
  3. in this machine's tree of the log-store's guarded-file versions-and-approvals store, renames the directories of the old checkout, worktrees-directory and log-store paths to the new ones, and inside them every `nc-systems` to `nn-systems`, `nc-queue` to `nn-queue`, `docs/nedschorus-wiki` to `docs/nedsnodes-wiki` and each `nedschorus-*` directory directly in `docs/nedschorus-wiki` to `nedsnodes-*`;
  4. renames each ~/.claude/projects/<key> that Claude Code made for the reference-checkout or a worktree that still exists, replacing only the part of the key made from the moved directory, and its copy under <log-store>/agent-session-files-by-machine/<machine>/projects/ the same way;
  5. renames each ~/.claude/tasks/nedschorus-<seat>-tasks to nedsnodes-<seat>-tasks, and its copy under <log-store>/agent-session-files-by-machine/<machine>/tasks/;
  6. renames ~/.config/nedschorus to ~/.config/nedsnodes;
  7. copies ~/.claude.json to a backup beside it, then rewrites every key and string value in it that holds the old checkout, worktrees-directory or log-store path, to the new path, and `nedschorus/nedschorus` to `nedsnodes/nedsnodes`; and copies ~/.ssh/authorized_keys to a backup beside it, then rewrites the old checkout, worktrees-directory and log-store paths inside each `command="..."` option and nowhere else on the line, keeping the file's permissions;
  8. on ned-box only, renames each systemd user unit entry named `nc-*`, in the unit directory and its *.wants directories, to `nn-*`; a symlink is re-made pointing at the new checkout path with each `nc-` directory and file name in it changed to `nn-`; then runs `systemctl --user daemon-reload`; it starts nothing;
  9. leaves symlinks at the old reference-checkout path, the old ~/.config/nedschorus path and, on ned-box, the old log-store path, each pointing at its new sibling by a relative name.
--rollback reverses the journal's changes in reverse order: it removes the step-9 symlinks, re-makes the step-8 links under their old names, restores core.hooksPath to its old value, renames every directory back, and restores ~/.claude.json and ~/.ssh/authorized_keys from their backups and deletes the backups. A backup is restored only when its SHA-256 matches the one --apply journaled once the copy was complete; a file whose backup never got that record was never rewritten, so it is left as it is, and any partial backup is left in place and named; when a backup recorded complete is missing, --rollback stops, unless the file already holds the backed-up content. It then runs `git worktree repair` with the old paths and `systemctl --user daemon-reload` when --apply ran them, and renames the journal to <journal>.rolled-back-<time>. Every path flag is made absolute when it is read, so every path the journal holds is absolute and --rollback needs only --journal; every message that says to run --rollback prints the exact command, with the journal's path and this program's path where the program is at that moment, which is under the renamed checkout once step 1 has moved the checkout it was started from, both quoted for the shell. A change the journal records but that was never made, because --apply stopped first, is skipped.

HARM IT CAN CAUSE. --apply leaves symlinks at the old reference-checkout, ~/.config/nedschorus and (ned-box) log-store paths, so old code keeps working against the new directories until the symlinks are removed by hand. It rewrites ~/.ssh/authorized_keys, after copying it to ~/.ssh/authorized_keys.before-project-rename-<time>; a mistake there would refuse the forced command ned-box's key runs on the Mac, and the backup or --rollback restores it. It rewrites ~/.claude.json, after copying it to ~/.claude.json.before-project-rename-<time>; a Claude Code process that starts or exits during the rewrite can overwrite the rewrite, which is why --apply refuses while any process named `claude` runs. Every directory is moved by a rename on one filesystem, so no directory's contents are copied; the only copies made are the two backups, and the only files deleted are the step-8 links, which are re-made under their new names, and, by --rollback, the step-9 symlinks it removes and the backups it has restored from. Programs holding the old paths (a supervisor, a cron job installed later from the old path) fail until restarted from the new ones.

WHAT IT DOES NOT DO OR HANDLE. It does not install, remove or edit cron lines, LaunchAgents or systemd units other than the step-8 renames, start or stop any service or agent-seat, touch GitHub, or edit any file's text other than ~/.claude.json and ~/.ssh/authorized_keys. It does not rewrite the text of a step-8 unit file. Claude Code shortens a project key longer than 200 characters with a hash, so such a key matches no worktree and stays under its old name. Keys of worktrees that no longer exist, and of sessions started in a subdirectory of the checkout, stay as history. The guarded-file store's entries for files in ~/agents/<seat> are not renamed. The -tasks lists of other names, handoff files, and the cwd fields in transcripts are not touched.

HOW IT CAN FAIL. A refusal prints each condition that failed and what to do, and exits 1 with nothing changed. A failure during --apply prints the step and the error, and exits 1 with the journal holding every change made so far: run the --rollback command it prints, or fix the cause and finish by hand. --rollback stops with exit 1 at a journal entry whose paths are in neither the before nor the after state, saying which; --rollback journals each change it reverses, so a second --rollback, after the path is fixed by hand, continues where the first stopped. A `git status` that fails after the repair, in step 2a, stops --apply the same way, after step 1, and on ned-box step 2, have moved the directories, so --rollback is then needed; a worktree whose `git status` already fails before the move does this too, and --check lists such worktrees. --rollback also stops, keeping the journal, when `git config`, `git worktree repair` or `systemctl --user daemon-reload` fails.

Each path root is a flag, and the commands it runs to read processes, the crontab and systemd are taken from the environment variables PROJECT_RENAME_MOVE_PROCESS_LIST_COMMAND, PROJECT_RENAME_MOVE_CRONTAB_LIST_COMMAND and PROJECT_RENAME_MOVE_SYSTEMCTL_COMMAND when set, so a test can run it on a temporary tree."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Messages this program prints for an agent follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
PROGRAM = "project-rename-machine-state-move-hack"

OLD_NAME = "nedschorus"
NEW_NAME = "nedsnodes"
OLD_REPOSITORY = "nedschorus/nedschorus"
NEW_REPOSITORY = "nedsnodes/nedsnodes"
OLD_TERM_PREFIX = "nc-"
NEW_TERM_PREFIX = "nn-"

MACHINE_MAC = "mac"
MACHINE_NED_BOX = "ned-box"
MAC_LOG_STORE_PARENT = Path("/Volumes/nedhome")

# The Mac reaches the log-store through this job's mount, which --apply needs.
MOUNT_JOB_LABEL = f"com.{OLD_NAME}.mount-ned-box-home-share"
# Installed by its own installer on each machine, not by the scheduled-jobs installer.
RESTART_LIVE_SEATS_JOB = "restart-live-seats-at-login"
MIRROR_DIRECTORY = "agent-session-files-by-machine"
GUARDED_FILE_STORE_DIRECTORY = "guarded-file-versions-and-approvals"
TRANSCRIPT_MIRROR_LOCK_NAME = ".transcript-mirror.lock"
JOURNAL_NAME = "project-rename-machine-state-move-journal.jsonl"
BACKUP_SUFFIX = ".before-project-rename-"
WIKI_PARTS = ("docs", f"{OLD_NAME}-wiki")
TASK_LIST_PATTERN = re.compile(rf"^{OLD_NAME}-.+-tasks$")

PROCESS_LIST_VARIABLE = "PROJECT_RENAME_MOVE_PROCESS_LIST_COMMAND"
CRONTAB_LIST_VARIABLE = "PROJECT_RENAME_MOVE_CRONTAB_LIST_COMMAND"
SYSTEMCTL_VARIABLE = "PROJECT_RENAME_MOVE_SYSTEMCTL_COMMAND"
DEFAULT_PROCESS_LIST_COMMAND = "ps -A -o comm="
DEFAULT_CRONTAB_LIST_COMMAND = "crontab -l"
DEFAULT_SYSTEMCTL_COMMAND = "systemctl --user"

EXIT_OK = 0
EXIT_REFUSED_OR_FAILED = 1
CHECK_EXAMPLES_SHOWN = 5
REPAIR_STEP = "2a"
STEPS = [1, 2, REPAIR_STEP, 3, 4, 5, 6, 7, 8, 9]
ARGUMENTS = "arguments"
PATH_FLAGS = ("--machine", "--home", "--claude-dir", "--claude-json", "--config-dir", "--projects-dir",
              "--log-store-parent", "--systemd-user-dir", "--launch-agents-dir", "--authorized-keys", "--journal")


class StepFailed(Exception):
    pass


def command_from_environment(variable, default):
    return shlex.split(os.environ.get(variable) or default)


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def derived_project_key(path):
    """The name Claude Code gives ~/.claude/projects/<key> for a working directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


PROGRAM_STARTED_AT = Path(__file__).resolve()


def program_path(layout):
    """Where this program's file is now. Step 1 may have moved the checkout it was started from, and --rollback may
    have moved it back, so a path under a moved directory is looked for under that directory's other name."""
    if PROGRAM_STARTED_AT.exists():
        return PROGRAM_STARTED_AT
    for old, new in layout.moved_roots():
        for source, target in ((old, new), (new, old)):
            if is_under(PROGRAM_STARTED_AT, source):
                moved = Path(str(target) + str(PROGRAM_STARTED_AT)[len(str(source)):])
                if moved.exists():
                    return moved
    return PROGRAM_STARTED_AT


def rollback_command(layout):
    return f"python3 {shlex.quote(str(program_path(layout)))} --rollback --journal {shlex.quote(str(layout.journal))}"


def apply_command(layout, arguments):
    return f"python3 {shlex.quote(str(program_path(layout)))} --apply {shlex.join(arguments)}"


def is_real_directory(path):
    return path.is_dir() and not path.is_symlink()


def is_under(path, root):
    path, root = str(path), str(root)
    return path == root or path.startswith(root + os.sep)


class Layout:
    def __init__(self, arguments):
        self.machine = arguments.machine
        # Made absolute here, so the journal and every printed command name the same paths from any directory.
        for flag in PATH_FLAGS:
            attribute = flag[2:].replace("-", "_")
            if flag != "--machine" and getattr(arguments, attribute) is not None:
                setattr(arguments, attribute, str(Path(getattr(arguments, attribute)).absolute()))
        self.path_flags = [item for flag in PATH_FLAGS if getattr(arguments, flag[2:].replace("-", "_")) is not None
                           for item in (flag, str(getattr(arguments, flag[2:].replace("-", "_"))))]
        home = Path(arguments.home or Path.home())
        self.home = home
        self.claude_dir = Path(arguments.claude_dir or home / ".claude")
        self.claude_json = Path(arguments.claude_json or home / ".claude.json")
        self.config_dir = Path(arguments.config_dir or home / ".config")
        projects = Path(arguments.projects_dir or home / "Projects")
        default_log_store_parent = MAC_LOG_STORE_PARENT if self.machine == MACHINE_MAC else home
        self.log_store_parent = Path(arguments.log_store_parent or default_log_store_parent)
        self.systemd_user_dir = Path(arguments.systemd_user_dir or self.config_dir / "systemd" / "user")
        self.launch_agents_dir = Path(arguments.launch_agents_dir or home / "Library" / "LaunchAgents")
        self.journal = Path(arguments.journal or self.claude_dir / JOURNAL_NAME)
        self.authorized_keys = Path(arguments.authorized_keys or home / ".ssh" / "authorized_keys")
        self.old_checkout = projects / OLD_NAME
        self.new_checkout = projects / NEW_NAME
        self.old_worktrees_dir = projects / f"{OLD_NAME}-worktrees"
        self.new_worktrees_dir = projects / f"{NEW_NAME}-worktrees"
        self.old_log_store = self.log_store_parent / f"{OLD_NAME}-logs"
        self.new_log_store = self.log_store_parent / f"{NEW_NAME}-logs"
        self.old_config = self.config_dir / OLD_NAME
        self.new_config = self.config_dir / NEW_NAME

    def moved_roots(self):
        """(old, new) of each directory this machine's run moves; none lies inside another."""
        return [(self.old_checkout, self.new_checkout), (self.old_worktrees_dir, self.new_worktrees_dir),
                (self.old_log_store, self.new_log_store)]

    def all_root_paths(self):
        return [str(path) for pair in self.moved_roots() for path in pair]

    def new_path_for(self, path):
        for old, new in self.moved_roots():
            if is_under(path, old):
                return Path(str(new) + str(path)[len(str(old)):])
        return Path(path)

    def current_log_store(self):
        """Where the log-store is before this run: ned-box renames it, the Mac finds it renamed."""
        if self.machine == MACHINE_NED_BOX and is_real_directory(self.old_log_store):
            return self.old_log_store
        return self.new_log_store

    def current_checkout(self):
        return self.old_checkout if is_real_directory(self.old_checkout) else self.new_checkout

    def mirror_root(self, log_store):
        return log_store / MIRROR_DIRECTORY / self.machine

    def installer_command(self):
        checkout = self.current_checkout()
        for systems in (f"{NEW_TERM_PREFIX}systems", f"{OLD_TERM_PREFIX}systems"):
            candidate = checkout / systems / "general-tools" / "install-scheduled-jobs-on-this-machine.py"
            if candidate.exists():
                return f"python3 {candidate}"
        return f"python3 {checkout}/{OLD_TERM_PREFIX}systems/general-tools/install-scheduled-jobs-on-this-machine.py"


# ---------------------------------------------------------------- planning

def rename_op(step, source, target, exists_now=None):
    """exists_now: where the target would be found before any change, when that differs from target."""
    return {"kind": "rename", "step": step, "from": str(source), "to": str(target),
            "exists_now": str(exists_now or target)}


def error_text(result):
    return result.stderr.strip() or f"it printed no error, exit code {result.returncode}"


def worktrees_listed(checkout):
    """The linked worktrees git lists for the checkout, main worktree left out: (those whose directory exists, those whose directory is missing)."""
    listing = run(["git", "-C", str(checkout), "worktree", "list", "--porcelain"])
    if listing.returncode != 0:
        raise StepFailed(f"`git -C {checkout} worktree list --porcelain` failed: {error_text(listing)}")
    paths = [line[len("worktree "):] for line in listing.stdout.splitlines() if line.startswith("worktree ")]
    present = [path for path in paths[1:] if os.path.isdir(path)]
    return present, [path for path in paths[1:] if path not in present]


def guarded_store_ops(layout, log_store):
    tree = log_store / GUARDED_FILE_STORE_DIRECTORY / layout.machine
    ops = []
    for old_root, new_root in layout.moved_roots():
        top = tree / str(old_root).lstrip(os.sep)
        if not top.is_dir() or top.is_symlink():
            continue
        new_top = tree / str(new_root).lstrip(os.sep)
        ops.append(rename_op(3, top, new_top))
        for directory, subdirectories, _ in os.walk(top, topdown=False, onerror=unreadable_store_directory):
            relative = Path(directory).relative_to(top)
            for name in subdirectories:
                target_name = inner_store_name(Path(directory), name)
                if target_name:
                    ops.append(rename_op(3, new_top / relative / name, new_top / relative / target_name,
                                         exists_now=top / relative / target_name))
    return ops


def unreadable_store_directory(error):
    raise StepFailed(f"cannot read {error.filename} in the guarded-file versions-and-approvals store, "
                     f"so its nested renames cannot be planned: {error.strerror}. "
                     f"Look at why with `ls -ld {error.filename}`: if it is a permission that this user may change, "
                     f"give it read and search permission, as `chmod u+rx {error.filename}` does; if it belongs to "
                     f"another user, or the error is an I/O error, fix that first. Then run this program again.")


def inner_store_name(parent, name):
    if name in (f"{OLD_TERM_PREFIX}systems", f"{OLD_TERM_PREFIX}queue"):
        return NEW_TERM_PREFIX + name[len(OLD_TERM_PREFIX):]
    if (parent.name, name) == WIKI_PARTS:
        return f"{NEW_NAME}-wiki"
    if parent.parts[-2:] == WIKI_PARTS and name.startswith(f"{OLD_NAME}-"):
        return NEW_NAME + name[len(OLD_NAME):]
    return None


def project_key_ops(layout, log_store, worktrees):
    projects = layout.claude_dir / "projects"
    mirror = layout.mirror_root(log_store) / "projects"
    ops = []
    live_paths = [layout.old_checkout] + [Path(path) for path in worktrees]
    for path in live_paths:
        root = next((pair for pair in layout.moved_roots() if is_under(path, pair[0])), None)
        if root is None:
            continue
        key = derived_project_key(path)
        old_prefix, new_prefix = derived_project_key(root[0]), derived_project_key(root[1])
        new_key = new_prefix + key[len(old_prefix):]
        if (projects / key).is_dir():
            ops.append(rename_op(4, projects / key, projects / new_key))
        if (mirror / key).is_dir():
            ops.append(rename_op(4, mirror / key, mirror / new_key))
    return ops


def task_list_ops(layout, log_store):
    ops = []
    for tasks in (layout.claude_dir / "tasks", layout.mirror_root(log_store) / "tasks"):
        if not tasks.is_dir():
            continue
        for entry in sorted(tasks.iterdir()):
            if entry.is_dir() and TASK_LIST_PATTERN.match(entry.name):
                ops.append(rename_op(5, entry, tasks / (NEW_NAME + entry.name[len(OLD_NAME):])))
    return ops


def rewrite_paths(layout, text):
    for old, new in layout.moved_roots():
        text = re.sub(re.escape(str(old)) + r"(?![A-Za-z0-9._-])", lambda _: str(new), text)
    return text


def rewrite_text(layout, text):
    return rewrite_paths(layout, text).replace(OLD_REPOSITORY, NEW_REPOSITORY)


FORCED_COMMAND = re.compile(r'(command=")((?:[^"\\]|\\.)*)(")')


def rewritten_authorized_keys(layout, text):
    return FORCED_COMMAND.sub(lambda match: match.group(1) + rewrite_paths(layout, match.group(2)) + match.group(3), text)


def rewritten_file(layout, file_format, text):
    if file_format == "json":
        return json.dumps(rewritten_json(layout, json.loads(text)), indent=2) + "\n"
    return rewritten_authorized_keys(layout, text)


def rewritten_json(layout, value):
    if isinstance(value, dict):
        return {rewrite_text(layout, key): rewritten_json(layout, item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewritten_json(layout, item) for item in value]
    if isinstance(value, str):
        return rewrite_text(layout, value)
    return value


def claude_json_ops(layout, stamp):
    if not layout.claude_json.is_file():
        return []
    try:
        content = json.loads(layout.claude_json.read_text())
    except (OSError, ValueError) as error:
        raise StepFailed(f"{layout.claude_json} could not be read as JSON: {error}")
    if rewritten_json(layout, content) == content:
        return []
    return [rewrite_op(layout.claude_json, "json", stamp)]


def rewrite_op(path, file_format, stamp):
    backup = path.with_name(path.name + BACKUP_SUFFIX + stamp)
    return {"kind": "rewrite-file", "step": 7, "format": file_format, "path": str(path), "backup": str(backup)}


def authorized_keys_ops(layout, stamp):
    if not layout.authorized_keys.is_file():
        return []
    text = layout.authorized_keys.read_text()
    return [rewrite_op(layout.authorized_keys, "authorized-keys", stamp)] if rewritten_authorized_keys(layout, text) != text else []


def unit_entry_ops(layout):
    if layout.machine != MACHINE_NED_BOX or not layout.systemd_user_dir.is_dir():
        return []
    ops = []
    for directory in [layout.systemd_user_dir] + sorted(layout.systemd_user_dir.glob("*.wants")):
        for entry in sorted(directory.iterdir()):
            if not entry.name.startswith(OLD_TERM_PREFIX):
                continue
            new_entry = directory / (NEW_TERM_PREFIX + entry.name[len(OLD_TERM_PREFIX):])
            if entry.is_symlink():
                old_target = os.readlink(entry)
                ops.append({"kind": "relink", "step": 8, "from": str(entry), "from_target": old_target,
                            "to": str(new_entry), "to_target": str(unit_target_for(layout, old_target))})
            elif entry.is_file():
                ops.append(rename_op(8, entry, new_entry))
    if ops:
        ops.append({"kind": "daemon-reload", "step": 8})
    return ops


def unit_target_for(layout, target):
    target = Path(target)
    root = next((pair for pair in layout.moved_roots() if is_under(target, pair[0])), None)
    if root is None:
        return target.with_name(term_renamed(target.name))
    relative = Path(str(target)[len(str(root[0])):].lstrip(os.sep))
    return root[1].joinpath(*[term_renamed(part) for part in relative.parts])


def term_renamed(name):
    return NEW_TERM_PREFIX + name[len(OLD_TERM_PREFIX):] if name.startswith(OLD_TERM_PREFIX) else name


def plan(layout, stamp):
    """Every change, with paths as they will be when the change is made, in the order it is made."""
    checkout = layout.current_checkout()
    worktrees = worktrees_listed(checkout)[0] if checkout.is_dir() else []
    ops = []
    for old, new in ((layout.old_checkout, layout.new_checkout), (layout.old_worktrees_dir, layout.new_worktrees_dir)):
        if is_real_directory(old):
            ops.append(rename_op(1, old, new))
    if layout.machine == MACHINE_NED_BOX and is_real_directory(layout.old_log_store):
        ops.append(rename_op(2, layout.old_log_store, layout.new_log_store))
    if checkout == layout.old_checkout and checkout.is_dir():
        ops.append({"kind": "worktree-repair", "step": REPAIR_STEP, "checkout": str(layout.new_checkout),
                    "old_checkout": str(layout.old_checkout), "worktrees": [str(layout.new_path_for(path)) for path in worktrees],
                    "old_worktrees": worktrees})
        hooks_path = run(["git", "-C", str(checkout), "config", "--local", "--get", "core.hooksPath"]).stdout.strip()
        if hooks_path and is_under(hooks_path, layout.old_checkout):
            ops.append({"kind": "hooks-path", "step": REPAIR_STEP, "checkout": str(layout.new_checkout),
                        "old_value": hooks_path, "new_value": str(layout.new_path_for(hooks_path))})
    current_log_store = layout.current_log_store()
    log_store_ops = guarded_store_ops(layout, current_log_store) + project_key_ops(layout, current_log_store, worktrees) \
        + task_list_ops(layout, current_log_store)
    ops += [relocated(layout, op) for op in log_store_ops]
    if is_real_directory(layout.old_config):
        ops.append(rename_op(6, layout.old_config, layout.new_config))
    ops += claude_json_ops(layout, stamp)
    ops += authorized_keys_ops(layout, stamp)
    ops += unit_entry_ops(layout)
    renamed = {op["from"] for op in ops if op["kind"] == "rename" and op["step"] in (1, 2, 6)}
    for old, new in ((layout.old_checkout, layout.new_checkout), (layout.old_log_store, layout.new_log_store),
                     (layout.old_config, layout.new_config)):
        if str(old) in renamed:
            ops.append({"kind": "symlink", "step": 9, "path": str(old), "target": new.name})
    return ops


def relocated(layout, op):
    """The op with its paths moved under the renamed log-store, which steps 1 and 2 rename first."""
    op = dict(op)
    for field in ("from", "to"):
        op[field] = str(layout.new_path_for(op[field]))
    return op


def created_paths(op):
    """Paths, as they are before any change, that the op would create."""
    if op["kind"] == "rename":
        return [op["exists_now"]]
    if op["kind"] == "relink":
        return [op["to"]]
    if op["kind"] == "rewrite-file":
        return [op["backup"]]
    return []


# ---------------------------------------------------------------- refusals

def refusals(layout, ops):
    found = []
    if layout.journal.exists():
        found.append((f"a journal already exists at {layout.journal}",
                      f"If --apply ran before with this journal: run --check to see the state, or `{rollback_command(layout)}` to reverse what that --apply changed.\n"
                      f"If no --apply ran with it, such as a journal copied from elsewhere: move it aside, for example to "
                      f"{layout.journal}.set-aside, then run --apply again."))
    found += scheduled_job_refusals(layout)
    found += lock_refusals(layout)
    found += claude_process_refusals()
    found += active_unit_refusals(layout, ops)
    for op in ops:
        for path in created_paths(op):
            if os.path.lexists(path):
                found.append((f"{path} already exists, and step {op['step']} would create it",
                              "Move it aside or delete it by hand if it holds nothing needed, then run --apply again."))
    found += checkout_refusals(layout)
    if layout.machine == MACHINE_MAC and not layout.new_log_store.is_dir():
        found.append((f"the log-store is not at {layout.new_log_store}",
                      f"If {layout.log_store_parent} is not mounted: mount ned-box's home share there.\n"
                      "If ned-box's --apply has not run: run it on ned-box first, since ned-box renames the log-store."))
    return found


def scheduled_job_refusals(layout):
    found = []
    roots = layout.all_root_paths()
    crontab = run(command_from_environment(CRONTAB_LIST_VARIABLE, DEFAULT_CRONTAB_LIST_COMMAND))
    if crontab.returncode != 0 and "no crontab" not in crontab.stderr.lower():
        found.append((f"the crontab could not be read: {error_text(crontab)}",
                      "Find out why `crontab -l` fails for this user and fix that, then run --apply again; "
                      "the crontab must be read to know no job of this project runs."))
    lines = [line.strip() for line in crontab.stdout.splitlines()
             if not line.lstrip().startswith("#") and any(root in line for root in roots)]
    if lines:
        found.append((f"{len(lines)} crontab line(s) run from a moving path:\n" + "\n".join(lines),
                      f"Take each job off with `{layout.installer_command()} --remove --job <name>`, <name> being the "
                      "job whose cron line the installer's --print shows."))
    plists = sorted(plist for plist in layout.launch_agents_dir.glob("com.*.plist")
                    if plist.name.startswith((f"com.{OLD_NAME}.", f"com.{NEW_NAME}.")) and plist.stem != MOUNT_JOB_LABEL) \
        if layout.launch_agents_dir.is_dir() else []
    for plist in plists:
        label = plist.stem
        job = label.split(".", 2)[2]
        if label.startswith(f"com.{NEW_NAME}."):
            # The installers take off only the com.nedschorus.<job> labels they write.
            remedy = f"Run `launchctl bootout gui/$(id -u)/{label}`, then delete {plist}."
        elif job == RESTART_LIVE_SEATS_JOB:
            remedy = (f"Take it off with `python3 {layout.current_checkout()}/scripts/"
                      f"install-restart-live-seats-at-login-launch-agent.py --remove --label {label}`.")
        else:
            remedy = (f"If `{layout.installer_command()} --print` lists a job named {job}: take it off with "
                      f"`{layout.installer_command()} --remove --job {job}`.\n"
                      f"Otherwise: run `launchctl bootout gui/$(id -u)/{label}`, then delete {plist}.")
        found.append((f"the LaunchAgent {label} of this project is installed, at {plist}", remedy))
    found += systemd_unit_refusals(layout, roots)
    return found


def systemd_unit_refusals(layout, roots):
    found = []
    if not layout.systemd_user_dir.is_dir():
        return found
    for directory in [layout.systemd_user_dir] + sorted(layout.systemd_user_dir.glob("*.wants")):
        for entry in sorted(directory.iterdir()):
            if entry.name.startswith(OLD_TERM_PREFIX) and layout.machine == MACHINE_NED_BOX:
                continue
            if entry.is_symlink():
                names_root = any(is_under(os.readlink(entry), root) for root in roots)
            elif entry.is_file():
                names_root = any(root in entry.read_text(errors="replace") for root in roots)
            else:
                names_root = False
            if not names_root:
                continue
            if entry.name == f"{RESTART_LIVE_SEATS_JOB}.service":
                remedy = (f"Take it off with `python3 {layout.current_checkout()}/scripts/"
                          "install-restart-live-seats-at-login-systemd-unit.py --remove`.")
            else:
                remedy = (f"Run `systemctl --user disable --now {entry.name}`, delete {entry} if it is still there, "
                          "then run `systemctl --user daemon-reload`.")
            found.append((f"the systemd user unit {entry.name} names a moving path, in {entry}", remedy))
    return found


def lock_refusals(layout):
    lock_path = layout.claude_dir / TRANSCRIPT_MIRROR_LOCK_NAME
    if not lock_path.exists():
        return []
    with open(lock_path, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return [(f"{lock_path} is held: a transcript mirror run is copying",
                     f"Take the transcript mirror job off this machine with `{layout.installer_command()} --remove "
                     "--job transcript-mirror-to-log-store`, then run --check until it no longer reports this lock "
                     "held, which means the run has ended, then run --apply again.")]
        fcntl.flock(lock, fcntl.LOCK_UN)
    return []


def claude_process_refusals():
    listing = run(command_from_environment(PROCESS_LIST_VARIABLE, DEFAULT_PROCESS_LIST_COMMAND))
    if listing.returncode != 0:
        return [(f"the process list could not be read: {error_text(listing)}",
                 "Find out why `ps -A -o comm=` fails and fix that, then run --apply again; the process list must be "
                 "read to know no Claude Code runs, since Claude Code rewrites ~/.claude.json on exit.")]
    count = sum(1 for line in listing.stdout.splitlines() if os.path.basename(line.strip()) == "claude")
    if count:
        return [(f"{count} Claude Code process(es) named `claude` run on this machine",
                 "Hand off and stop every agent-seat and every other Claude Code session on this machine, then run "
                 "--apply from a plain terminal; Claude Code rewrites ~/.claude.json on exit and would undo step 7.")]
    return []


def active_unit_refusals(layout, ops):
    found = []
    for op in ops:
        if op["kind"] in ("relink", "rename") and op["step"] == 8 and Path(op["from"]).parent == layout.systemd_user_dir:
            unit = Path(op["from"]).name
            state = run(command_from_environment(SYSTEMCTL_VARIABLE, DEFAULT_SYSTEMCTL_COMMAND) + ["is-active", unit])
            if state.returncode == 0:
                found.append((f"systemd user unit {unit} is active",
                              f"Stop it with `systemctl --user stop {unit}` once today's nightly backup of the shared "
                              "database is in: ~/backups/nc-shared-database holds a file named "
                              "nc-shared-database-<today's UTC date>T<time>Z.sqlite3 with no .partial ending "
                              "(the backup's cron job runs at 02:15 UTC). Then run --apply again."))
    return found


def checkout_refusals(layout):
    checkout = layout.old_checkout
    if not checkout.is_dir():
        return [(f"no reference-checkout at {checkout}",
                 "If --apply already moved it: run --check. Otherwise pass --projects-dir with the directory that holds it.")]
    branch = run(["git", "-C", str(checkout), "symbolic-ref", "--short", "HEAD"])
    status = run(["git", "-C", str(checkout), "--no-optional-locks", "status", "--porcelain", "--untracked-files=no"])
    found = []
    if branch.returncode != 0:
        found.append((f"the reference-checkout {checkout} is not on main: its HEAD is detached ({error_text(branch)})",
                      f"Run `git -C {checkout} switch main`, then `git -C {checkout} pull --ff-only`, then run --apply again."))
    elif branch.stdout.strip() != "main":
        found.append((f"the reference-checkout {checkout} is not on main: it is on branch {branch.stdout.strip()}",
                      f"Run `git -C {checkout} switch main`, then `git -C {checkout} pull --ff-only`, then run --apply again."))
    for path in worktrees_listed(checkout)[1]:
        found.append((f"git lists the worktree {path} for {checkout}, but its directory is missing, "
                      "so `git worktree repair` cannot move it with the rest",
                      f"If the worktree was removed on purpose: run `git -C {checkout} worktree prune`, then run --apply again.\n"
                      f"If it should still be there: find where its directory went and move it back to {path}, "
                      "then run --apply again."))
    if status.returncode != 0 or status.stdout.strip():
        found.append((f"the reference-checkout {checkout} has uncommitted changes to tracked files: "
                      f"{(status.stdout or status.stderr).strip()}",
                      "Commit them on a topic branch or discard them, then run --apply again."))
    return found


# ---------------------------------------------------------------- journal and execution

def journal_append(journal, entry):
    with open(journal, "a") as handle:
        handle.write(json.dumps(entry) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def git_must(arguments, what):
    result = run(["git"] + arguments)
    if result.returncode != 0:
        raise StepFailed(f"{what}: `git {' '.join(arguments)}` failed: {error_text(result)}")
    return result.stdout


def systemctl_must(arguments):
    command = command_from_environment(SYSTEMCTL_VARIABLE, DEFAULT_SYSTEMCTL_COMMAND) + arguments
    result = run(command)
    if result.returncode != 0:
        raise StepFailed(f"`{' '.join(command)}` failed: {error_text(result)}")


def execute(layout, op):
    kind = op["kind"]
    if kind == "rename":
        os.rename(op["from"], op["to"])
    elif kind == "worktree-repair":
        if op["worktrees"]:
            git_must(["-C", op["checkout"], "worktree", "repair"] + op["worktrees"], "repairing the worktrees")
        failed = [path for path in [op["checkout"]] + op["worktrees"]
                  if run(["git", "-C", path, "--no-optional-locks", "status", "--porcelain"]).returncode != 0]
        if failed:
            raise StepFailed("`git status` fails after the repair in: " + ", ".join(failed))
    elif kind == "hooks-path":
        git_must(["-C", op["checkout"], "config", "--local", "core.hooksPath", op["new_value"]], "setting core.hooksPath")
    elif kind == "rewrite-file":
        shutil.copy2(op["path"], op["backup"])
        digest = sha256_of(op["path"])
        if sha256_of(op["backup"]) != digest:
            raise StepFailed(f"the backup {op['backup']} differs from {op['path']}, so --apply stopped here "
                             f"and {op['path']} was not rewritten")
        journal_append(layout.journal, {"kind": BACKUP_COMPLETE, "backup": op["backup"], "sha256": digest})
        write_atomically(Path(op["path"]), rewritten_file(layout, op["format"], Path(op["path"]).read_text()))
    elif kind == "relink":
        os.symlink(op["to_target"], op["to"])
        os.unlink(op["from"])
    elif kind == "daemon-reload":
        systemctl_must(["daemon-reload"])
    elif kind == "symlink":
        os.symlink(op["target"], op["path"])


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_atomically(path, text):
    temporary = path.with_name(path.name + ".project-rename-writing")
    temporary.write_text(text)
    shutil.copymode(path, temporary)
    os.replace(temporary, path)


def apply(layout):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        ops = plan(layout, stamp)
    except StepFailed as error:
        print(f"{PROGRAM}: REFUSED, nothing changed: {error}")
        return EXIT_REFUSED_OR_FAILED
    found = refusals(layout, ops)
    if found:
        print(f"{PROGRAM}: REFUSED, nothing changed. {len(found)} condition(s) do not hold:")
        for problem, remedy in found:
            print(f"\n- {problem}")
            for line in remedy.splitlines():
                print(f"  {line}")
        return EXIT_REFUSED_OR_FAILED
    journal_append(layout.journal, {"kind": ARGUMENTS, "arguments": layout.path_flags})
    for op in ops:
        try:
            journal_append(layout.journal, op)
            execute(layout, op)
        except (OSError, StepFailed, ValueError) as error:
            print(f"{PROGRAM}: FAILED at step {op['step']} ({op['kind']}): {error}")
            print(f"The journal {layout.journal} holds every change made before this one.")
            print(f"To reverse them, run: {rollback_command(layout)}")
            return EXIT_REFUSED_OR_FAILED
    print(f"{PROGRAM}: applied {len(ops)} change(s); the journal is {layout.journal}.")
    for op in ops:
        if op["kind"] == "relink" and not os.path.exists(op["to"]):
            print(f"WARNING: {op['to']} points at {op['to_target']}, which does not exist; "
                  "the unit cannot start until that file is there.")
    return EXIT_OK


UNDONE = "undone"
BACKUP_COMPLETE = "backup-complete"


def read_journal(journal):
    """The journaled changes, the indexes of those a --rollback already reversed, and each complete backup's SHA-256."""
    lines = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    changes = [line for line in lines if line["kind"] not in (UNDONE, BACKUP_COMPLETE, ARGUMENTS)]
    undone = {line["index"] for line in lines if line["kind"] == UNDONE}
    complete_backups = {line["backup"]: line["sha256"] for line in lines if line["kind"] == BACKUP_COMPLETE}
    return changes, undone, complete_backups


def undo(op, deferred, complete_backups):
    """Reverse one journal entry; an entry whose change was never made is left alone."""
    kind = op["kind"]
    if kind == "rename":
        if os.path.lexists(op["to"]) and not os.path.lexists(op["from"]):
            os.rename(op["to"], op["from"])
        elif not (os.path.lexists(op["from"]) and not os.path.lexists(op["to"])):
            if os.path.lexists(op["from"]):
                raise StepFailed(f"cannot reverse the rename {op['from']} -> {op['to']}: both exist, and --rollback "
                                 f"moves {op['to']} back to {op['from']}. Look at both: if {op['from']} holds work, move that work "
                                 f"into {op['to']} first. Then move {op['from']} aside by hand, for example to "
                                 f"{op['from']}.aside, so that only {op['to']} exists. Then run --rollback again.")
            raise StepFailed(f"cannot reverse the rename {op['from']} -> {op['to']}: neither exists. Find where the "
                             f"directory went and move it to {op['to']} by hand, then run --rollback again.")
    elif kind == "symlink":
        if os.path.islink(op["path"]) and os.readlink(op["path"]) == op["target"]:
            os.unlink(op["path"])
        elif os.path.lexists(op["path"]):
            raise StepFailed(f"cannot remove the symlink {op['path']}: it is not the one --apply made")
    elif kind == "relink":
        if os.path.islink(op["to"]) and os.readlink(op["to"]) == op["to_target"]:
            os.unlink(op["to"])
        if not os.path.lexists(op["from"]):
            os.symlink(op["from_target"], op["from"])
    elif kind == "rewrite-file":
        recorded = complete_backups.get(op["backup"])
        if recorded is None:
            if os.path.lexists(op["backup"]):
                print(f"Left as it is: {op['path']}, which --apply never rewrote. "
                      f"The partial backup {op['backup']} is left too; nothing reads it, so delete it by hand.")
        elif os.path.exists(op["backup"]):
            if sha256_of(op["backup"]) != recorded:
                raise StepFailed(f"the backup {op['backup']} no longer matches the SHA-256 --apply recorded, "
                                 f"so it is not restored over {op['path']}. Put back into {op['path']} the content "
                                 f"--apply backed up, whose SHA-256 is {recorded}, from a copy of your own (check it "
                                 f"with `sha256sum` on ned-box or `shasum -a 256` on the Mac), delete {op['backup']}, "
                                 f"then run --rollback again: it skips this file once "
                                 f"{op['path']} has that SHA-256.")
            shutil.copy2(op["backup"], op["path"])
            os.unlink(op["backup"])
        elif not (os.path.exists(op["path"]) and sha256_of(op["path"]) == recorded):
            raise StepFailed(f"the backup {op['backup']} that --apply recorded complete is missing, and {op['path']} "
                             f"does not hold the content it backed up, so {op['path']} cannot be restored.")
    elif kind == "hooks-path":
        if os.path.isdir(op["checkout"]):
            git_must(["-C", op["checkout"], "config", "--local", "core.hooksPath", op["old_value"]],
                     "restoring core.hooksPath")
    elif kind in ("worktree-repair", "daemon-reload"):
        deferred.append(op)


def no_journal_text(layout):
    """Why there is no journal: no --apply with these flags, or a finished --rollback renamed it."""
    rolled_back = sorted(layout.journal.parent.glob(f"{layout.journal.name}.rolled-back-*"))
    if len(rolled_back) == 1:
        return f"no journal at {layout.journal}: --rollback already finished and renamed it to {rolled_back[0]}"
    if rolled_back:
        return (f"no journal at {layout.journal}: --rollback already finished and renamed it to {rolled_back[-1]}, "
                f"the newest of {len(rolled_back)} rolled-back journals there, by the time in its name")
    return (f"no journal at {layout.journal}. If an --apply ran with another --journal, --claude-dir or --home, its "
            f"journal is elsewhere, named {JOURNAL_NAME} unless --journal named another; reverse it with "
            f"`python3 {shlex.quote(str(program_path(layout)))} --rollback --journal <that journal>`")


def recorded_arguments(journal):
    for line in journal.read_text().splitlines():
        if line.strip() and json.loads(line)["kind"] == ARGUMENTS:
            return json.loads(line)["arguments"]
    return None


def rollback(layout):
    if not layout.journal.exists():
        print(f"{PROGRAM}: nothing to roll back: {no_journal_text(layout)}.")
        return EXIT_REFUSED_OR_FAILED
    entries, undone, complete_backups = read_journal(layout.journal)
    deferred = []
    try:
        for index in reversed(range(len(entries))):
            if index in undone:
                continue
            before = len(deferred)
            undo(entries[index], deferred, complete_backups)
            if len(deferred) == before:
                journal_append(layout.journal, {"kind": UNDONE, "index": index})
            else:
                deferred[-1] = (index, deferred[-1])
        for index, op in deferred:
            if op["kind"] == "worktree-repair" and op["old_worktrees"]:
                git_must(["-C", op["old_checkout"], "worktree", "repair"] + op["old_worktrees"],
                         "repairing the worktrees at their old paths")
            elif op["kind"] == "daemon-reload":
                systemctl_must(["daemon-reload"])
            journal_append(layout.journal, {"kind": UNDONE, "index": index})
    except (OSError, StepFailed) as error:
        print(f"{PROGRAM}: FAILED during --rollback: {error}")
        print(f"The journal {layout.journal} is kept; entries already reversed are skipped when --rollback runs again.")
        print(f"Once the cause is fixed, run: {rollback_command(layout)}")
        return EXIT_REFUSED_OR_FAILED
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    done = layout.journal.with_name(f"{layout.journal.name}.rolled-back-{stamp}")
    os.rename(layout.journal, done)
    print(f"{PROGRAM}: rolled back {len(entries)} journal entr(ies); the journal is now {done}.")
    return EXIT_OK


# ---------------------------------------------------------------- check

def check(layout):
    stamp = "check"
    print(f"{PROGRAM} --check on {layout.machine}; nothing is changed.")
    try:
        ops = plan(layout, stamp)
    except StepFailed as error:
        print(f"Planning failed: {error}")
        return EXIT_REFUSED_OR_FAILED
    found = refusals(layout, ops)
    print(f"\n--apply would {'REFUSE' if found else 'proceed'}:")
    for problem, remedy in found:
        print(f"- {problem}")
        for line in remedy.splitlines():
            print(f"    {line}")
    print("\nChanges --apply would make, by step:")
    for step in STEPS:
        step_ops = [op for op in ops if op["step"] == step]
        print(f"  step {step}: {len(step_ops)}")
        for op in step_ops[:CHECK_EXAMPLES_SHOWN]:
            print(f"    {describe(op)}")
        if len(step_ops) > CHECK_EXAMPLES_SHOWN:
            print(f"    and {len(step_ops) - CHECK_EXAMPLES_SHOWN} more")
    if layout.journal.exists():
        entries, undone, _ = read_journal(layout.journal)
        print(f"\nJournal {layout.journal}: {len(entries)} entr(ies), {len(undone)} already reversed by --rollback.")
        recorded = recorded_arguments(layout.journal)
        if recorded is not None:
            print(f"The --apply that wrote it ran as: {apply_command(layout, recorded)}")
        print(f"To reverse it, run: {rollback_command(layout)}")
    else:
        print(f"\nJournal: {no_journal_text(layout)}.")
    checkout = layout.current_checkout()
    if checkout.is_dir():
        present, missing = worktrees_listed(checkout)
        paths = [str(checkout)] + present
        failed = [path for path in paths if run(["git", "-C", path, "--no-optional-locks", "status", "--porcelain"]).returncode != 0]
        print(f"\nWorktrees of {checkout}: git lists {len(paths) + len(missing)}; `git status` works in "
              f"{len(paths) - len(failed)}, fails in {len(failed)}, and {len(missing)} have no directory.")
        for path in failed:
            print(f"  FAILS: {path}")
        for path in missing:
            print(f"  MISSING: {path}")
    return EXIT_OK


def describe(op):
    if op["kind"] in ("rename", "relink"):
        return f"{op['kind']} {op['from']} -> {op['to']}"
    if op["kind"] == "symlink":
        return f"symlink {op['path']} -> {op['target']}"
    if op["kind"] == "rewrite-file":
        return f"rewrite {op['path']} after copying it to {op['backup']}"
    if op["kind"] == "worktree-repair":
        return f"git worktree repair in {op['checkout']} for {len(op['worktrees'])} worktree(s), then git status in each"
    if op["kind"] == "hooks-path":
        return f"set core.hooksPath in {op['checkout']} to {op['new_value']}"
    return op["kind"]


def detected_machine():
    return MACHINE_MAC if sys.platform == "darwin" else MACHINE_NED_BOX


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report each step's state; change nothing")
    mode.add_argument("--apply", action="store_true", help="make every change, journaling each first")
    mode.add_argument("--rollback", action="store_true", help="reverse the journal's changes")
    parser.add_argument("--machine", choices=(MACHINE_MAC, MACHINE_NED_BOX), default=detected_machine(),
                        help="default: mac on macOS, ned-box otherwise")
    parser.add_argument("--home", help="default: the home directory")
    parser.add_argument("--claude-dir", help="default: <home>/.claude")
    parser.add_argument("--claude-json", help="default: <home>/.claude.json")
    parser.add_argument("--config-dir", help="default: <home>/.config")
    parser.add_argument("--projects-dir", help="the directory holding the reference-checkout; default: <home>/Projects")
    parser.add_argument("--log-store-parent", help="the directory holding the log-store; default: /Volumes/nedhome on the Mac, <home> on ned-box")
    parser.add_argument("--systemd-user-dir", help="default: <config-dir>/systemd/user")
    parser.add_argument("--launch-agents-dir", help="default: <home>/Library/LaunchAgents")
    parser.add_argument("--authorized-keys", help="default: <home>/.ssh/authorized_keys")
    parser.add_argument("--journal", help=f"default: <claude-dir>/{JOURNAL_NAME}")
    arguments = parser.parse_args(argv)
    layout = Layout(arguments)
    if arguments.check:
        return check(layout)
    if arguments.apply:
        return apply(layout)
    return rollback(layout)


if __name__ == "__main__":
    sys.exit(main())
