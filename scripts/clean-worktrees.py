#!/usr/bin/env python3
"""Report or remove finished session worktrees under .claude/worktrees/.

Session worktrees pile up invisibly: every Claude session gets one, sessions
end, and nothing reaps them. A worktree is DONE — removable losing nothing —
only when three mechanical checks all pass:

  1. clean    - no uncommitted, untracked, or ignored files (`git status
                --porcelain --ignored` is empty). Ignored files count as dirt
                on purpose: uncommitted state like walk minutes or an
                identity file must never be reaped with its worktree. The one
                exception is regenerable junk every worktree accumulates —
                .DS_Store and __pycache__ — which counts as nothing (git
                worktree remove tolerates it, verified). The second
                exception is a cold-read-record under cold-read-records/ or a
                walk file directly in docs/walk/, both gitignored, when the
                log-store on ned-box holds a byte-identical copy (sha256) at
                the path the shippers use: cold-read-records/<record>/... and
                walk/<file>. One file missing from the store or different
                there keeps the worktree. So does a store that cannot be
                read, which is also printed as a FAILED line and makes the
                exit 1. On ned-box the store is read locally; elsewhere over
                one ssh call per worktree, and not again in the same run
                once ned-box has failed to answer.
  2. landed   - no commits beyond origin/main (`git log origin/main..HEAD`
                is empty), so everything the worktree's branch carries is
                already on main. origin/main is read as fetched; a stale ref
                only errs toward keeping.
  3. vacant   - no live process has its working directory inside the
                worktree (lsof). Vacancy must be proven, never assumed: if
                lsof is missing, cannot be run, exits nonzero, or reports no
                working directories at all, the worktree is kept and the
                reason says the check could not be trusted — it does not
                claim a process that was never seen.
  4. quiet    - for a worktree the Agent tool made for a subagent
                (`agent-<id>`), neither the subagent's transcript nor the
                worktree itself was written in the last
                AGENT_WORKTREE_QUIET_SECONDS. The vacancy check cannot see
                such a subagent: it runs inside its parent `claude` process,
                whose working directory stays the seat home, and only the
                short-lived shell of each Bash call sits in the worktree. The
                subagent's transcript, written on every message, is the one
                trace of it that lives outside a process.

Anything that fails a check is KEPT, with the failing reason. Worktrees
outside <repo>/.claude/worktrees/ — agent seat homes, manual checkouts — are
always kept: their lifecycles belong to their owners, not to this script.

Removing a worktree does not remove the branch it was on, and nothing has
ever swept a branch whose worktree is already gone — list_worktrees()
enumerates worktrees, not refs. So the report also carries one line naming
every local branch that no worktree has checked out and that carries nothing
origin/main lacks: the refs removable losing nothing. Orphaned refs that DO
carry commits origin/main lacks are deliberately NOT named — 41 of the 51
local branches left after 2026-08-31's hand sweep were in that state. Their
disposal is a judgment rather than a sweep, and printing them at every boot
teaches a reader to skip the line. The line prints in every mode; --remove
deletes the refs it names.

Separately from the worktrees themselves, the report ends with one line
naming dead registrations — the ones `git worktree prune` would remove,
typically because the worktree's directory is gone, which is what a
temp-area clearing leaves behind — each with git's own reason, and the
prune command. The line prints in every mode and is report only: the prune
stays a deliberate human act (ruled 2026-08-18; R25 in
docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md).

Modes:
  (default)    report every worktree, one line each
  --only-done  print only what needs someone's attention — done worktrees,
               the orphaned-branch-ref line, and the dead-registration line
               when there are any; nothing otherwise (the launchers run this
               at boot, so a reapable worktree, an orphaned branch ref or a
               dead registration is named at the moment someone is looking)
  --remove     re-check and remove the done worktrees; each removal also
               deletes the worktree's fully-merged branch (git branch -d,
               which refuses anything unmerged). Never --force. Orphaned
               branch refs are deleted the same way, and a refusal there is
               a failure rather than a silence.

SCHEDULED. --remove runs once a day on both machines, from the reference
clone, so worktrees that sessions and subagents leave behind do not pile up
between handoffs. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py: on
the Mac a launchd job at 06:30, so a run missed while the Mac sleeps starts at
the next wake; on ned-box the cron line

    30 6 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/clean-worktrees.py --remove >> /home/nedlern/.claude/daily-clean-worktrees.log 2>&1

It does not fetch; a stale origin/main only keeps more. A worktree still
locked by the claude process that made it fails to remove and is tried again
the next day.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal or a ref deletion failed or the log-store could
not be read, 2 bad invocation.
"""

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent

# Imported so this check reads the same store, and honours the same test
# override, as the programs that ship there.
_record_shipper_spec = importlib.util.spec_from_file_location(
    "cold_read_record_ship", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py")
record_shipper = importlib.util.module_from_spec(_record_shipper_spec)
_record_shipper_spec.loader.exec_module(record_shipper)

COLD_READ_RECORDS_DIRECTORY = "cold-read-records"
WALK_FILES_DIRECTORY = "docs/walk"
# The walk shipper's kind directory, beside cold-read-records/ in the store.
WALK_STORE_KIND_DIRECTORY = "walk"
STORE_CHECKSUM_TIMEOUT_SECONDS = 60
SSH_EXIT_CONNECTION_FAILED = 255
# xargs exits 123 when sha256sum failed on some path, which is how a file
# missing from the store shows up; any other nonzero exit is a failed read.
XARGS_EXIT_SOME_INVOCATION_FAILED = 123

# Once ned-box fails to answer, later worktrees in the same run are kept
# without another ssh attempt, so a run on a cut-off machine stays short.
store_unreachable_reason = None

# Only known regenerable ignored files are disposable; other ignored files may hold uncommitted state.
DISPOSABLE_JUNK_BASENAMES = (".DS_Store", "__pycache__")

# lsof scans all processes and can be slow under load; a timeout must keep worktrees.
VACANCY_CHECK_TIMEOUT_SECONDS = 120

# An isolated subagent's cwd may remain outside its worktree between tool calls.
# Require transcript and .git quiet time as well as the process vacancy check.
AGENT_WORKTREE_QUIET_SECONDS = 3600
AGENT_WORKTREE_NAME_PREFIX = "agent-"


def run_git(repo, *arguments):
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )


def main_checkout_of(repo):
    """Return the primary checkout from the common git directory."""
    common = run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        return None
    return Path(common.stdout.strip()).parent


def list_worktrees(repo, main_checkout):
    """Return (path, branch-or-None) pairs excluding the primary checkout."""
    listing = run_git(repo, "worktree", "list", "--porcelain")
    worktrees = []
    path, branch = None, None
    for line in listing.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            path = Path(line.split(" ", 1)[1])
        elif line.startswith("branch refs/heads/"):
            branch = line.split("refs/heads/", 1)[1]
        elif not line:
            if path is not None and path.resolve() != main_checkout.resolve():
                worktrees.append((path, branch))
            path, branch = None, None
    return worktrees


def dead_worktree_registrations(repo):
    """Return (path, git reason) for unlocked prunable registrations."""
    # A prunable directory can still exist and hold work; report git's reason without inferring absence.
    listing = run_git(repo, "worktree", "list", "--porcelain")
    dead = []
    path = None
    for line in listing.stdout.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif (line == "prunable" or line.startswith("prunable ")) and path:
            reason = line[len("prunable"):].strip() or "no reason given"
            dead.append((path, reason))
            path = None
    return dead


def branch_refs_with_no_worktree_fully_on_main(repo):
    listing = run_git(repo, "worktree", "list", "--porcelain")
    if listing.returncode != 0:
        return []
    attached = {
        line.split("refs/heads/", 1)[1]
        for line in listing.stdout.splitlines()
        if line.startswith("branch refs/heads/")
    }
    # Use lstrip=2: :short can return heads/<name> when a same-named tag shadows a branch.
    landed = run_git(repo, "for-each-ref", "--format=%(refname:lstrip=2)",
                     "--merged", "origin/main", "refs/heads/")
    if landed.returncode != 0:
        return []
    return [branch for branch in landed.stdout.splitlines()
            if branch not in attached]


def delete_orphaned_branch_ref(branch, repo):
    """Delete a ref and return whether git accepted the deletion."""
    # Keep -d: git's merged-branch check is independent of our containment test.
    deletion = run_git(repo, "branch", "-d", branch)
    if deletion.returncode != 0:
        print(f"branch {branch}: deletion FAILED — {deletion.stderr.strip()[:120]}")
        return False
    print(f"branch {branch}: deleted (no worktree, nothing beyond origin/main)")
    return True


def worktree_vacancy_keep_reason(worktree):
    """Return why vacancy is unproven, or None for a provably vacant worktree."""
    # Even a partial listing proves occupancy when it contains a matching cwd.
    if shutil.which("lsof") is None:
        return "lsof is not installed, so vacancy cannot be checked"
    try:
        cwd_listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, check=False,
            timeout=VACANCY_CHECK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "the vacancy check (lsof) could not be run"
    prefix = str(worktree.resolve())
    reported_paths = 0
    for line in cwd_listing.stdout.splitlines():
        if line.startswith("n"):
            reported_paths += 1
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                return "a live process is rooted inside it"
    # No match proves vacancy only when lsof returned a usable listing.
    if cwd_listing.returncode != 0:
        return (f"the vacancy check (lsof) failed with exit "
                f"{cwd_listing.returncode}, so vacancy cannot be trusted")
    if reported_paths == 0:
        return "the vacancy check (lsof) reported no working directories at all"
    return None


def claude_projects_directory():
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured) if configured else Path.home() / ".claude"
    return base / "projects"


def agent_worktree_quiet_keep_reason(worktree, now=None):
    """Return why a subagent worktree must be kept, or None after sufficient quiet."""
    # The .git timestamp covers new or pruned transcripts; unreadable times cannot prove quiet.
    if not worktree.name.startswith(AGENT_WORKTREE_NAME_PREFIX):
        return None
    agent_id = worktree.name[len(AGENT_WORKTREE_NAME_PREFIX):]
    now = time.time() if now is None else now
    written = []
    try:
        written.append((worktree / ".git").stat().st_mtime)
        for transcript in claude_projects_directory().glob(
                f"*/*/subagents/agent-{agent_id}.jsonl"):
            written.append(transcript.stat().st_mtime)
    except OSError as error:
        return f"its subagent's activity could not be read ({error.strerror})"
    quiet_seconds = now - max(written)
    if quiet_seconds < AGENT_WORKTREE_QUIET_SECONDS:
        return (f"its Agent-tool subagent or the worktree was written "
                f"{int(quiet_seconds // 60)} min ago, so the subagent may still be "
                f"working in it (quiet for {AGENT_WORKTREE_QUIET_SECONDS // 60} min "
                f"before removal)")
    return None


def shippable_store_path(relative, records_path, walk_path):
    """Return the store path for a worktree file the shippers ship, or None."""
    parts = PurePosixPath(relative).parts
    if len(parts) >= 3 and parts[0] == COLD_READ_RECORDS_DIRECTORY:
        return records_path.joinpath(*parts[1:])
    walk_parts = PurePosixPath(WALK_FILES_DIRECTORY).parts
    if len(parts) == len(walk_parts) + 1 and parts[:len(walk_parts)] == walk_parts:
        return walk_path / parts[-1]
    return None


def shippable_files_of_ignored_entry(worktree, entry):
    """Return the files under an ignored status entry, or None if any is not a plain file."""
    root = worktree / entry
    if root.is_symlink():
        return None
    if root.is_file():
        return [entry]
    if not root.is_dir():
        return None
    files = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [name for name in subdirectories
                             if name not in DISPOSABLE_JUNK_BASENAMES]
        for name in names:
            if name in DISPOSABLE_JUNK_BASENAMES:
                continue
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file():
                return None
            files.append(path.relative_to(worktree).as_posix())
    return files


def split_dirt_into_shippable_and_other(worktree, dirt, records_path, walk_path):
    """Return ({worktree-relative file: store path}, other dirt lines)."""
    shippable, other = {}, []
    for line in dirt:
        entry = line[3:].rstrip("/")
        is_candidate = line.startswith("!!") and (
            entry == COLD_READ_RECORDS_DIRECTORY
            or entry.startswith(COLD_READ_RECORDS_DIRECTORY + "/")
            or entry == WALK_FILES_DIRECTORY
            or entry.startswith(WALK_FILES_DIRECTORY + "/"))
        files = shippable_files_of_ignored_entry(worktree, entry) if is_candidate else None
        store_paths = None if files is None else {
            relative: shippable_store_path(relative, records_path, walk_path)
            for relative in files}
        if store_paths is None or None in store_paths.values():
            other.append(line)
        else:
            shippable.update(store_paths)
    return shippable, other


def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def store_sha256_by_path(store_paths, copy_host):
    """Return ({store path: sha256} for the files present, None) or (None, why unread)."""
    global store_unreachable_reason
    if copy_host is None:
        found = {}
        for store_path in store_paths:
            try:
                found[store_path] = sha256_of_file(store_path)
            except FileNotFoundError:
                continue
            except OSError as error:
                return None, f"the log-store copy {store_path} could not be read ({error.strerror})"
        return found, None
    if store_unreachable_reason is not None:
        return None, store_unreachable_reason
    try:
        answer = subprocess.run(
            [*record_shipper.SSH_COMMAND, copy_host, "xargs -0 -r sha256sum --"],
            input="\0".join(store_paths), capture_output=True, text=True,
            check=False, timeout=STORE_CHECKSUM_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        store_unreachable_reason = f"{copy_host} could not be reached ({type(error).__name__})"
        return None, store_unreachable_reason
    if answer.returncode == SSH_EXIT_CONNECTION_FAILED:
        detail = (answer.stderr.strip().splitlines() or ["no detail"])[-1][:120]
        store_unreachable_reason = f"{copy_host} could not be reached ({detail})"
        return None, store_unreachable_reason
    if answer.returncode not in (0, XARGS_EXIT_SOME_INVOCATION_FAILED):
        detail = (answer.stderr.strip().splitlines() or ["no detail"])[-1][:120]
        return None, (f"the log-store's checksums could not be read "
                      f"(exit {answer.returncode}: {detail})")
    found = {}
    for line in answer.stdout.splitlines():
        # sha256sum prefixes a line with a backslash when it escapes the
        # name; such a file is left out, so it counts as missing and keeps.
        digest, separator, name = line.partition("  ")
        if separator and not digest.startswith("\\"):
            found[name] = digest
    return found, None


def shipped_files_keep_reason(worktree, shippable, copy_host):
    """Return (why the worktree must be kept, whether the store was unread), or (None, False)."""
    found, unread_reason = store_sha256_by_path(
        sorted(str(path) for path in shippable.values()), copy_host)
    if found is None:
        return (f"{len(shippable)} file(s) under {COLD_READ_RECORDS_DIRECTORY}/ or "
                f"{WALK_FILES_DIRECTORY}/ could not be compared with the log-store: "
                f"{unread_reason}"), True
    missing, differing = [], []
    for relative, store_path in sorted(shippable.items()):
        stored = found.get(str(store_path))
        if stored is None:
            missing.append(relative)
            continue
        try:
            local = sha256_of_file(worktree / relative)
        except OSError as error:
            return f"{relative} could not be read ({error.strerror})", False
        if local != stored:
            differing.append(relative)
    if not missing and not differing:
        return None, False
    parts = []
    if missing:
        parts.append(f"{len(missing)} file(s) not yet in the log-store, first {missing[0]}")
    if differing:
        parts.append(f"{len(differing)} file(s) that differ from the log-store's copy, "
                     f"first {differing[0]}")
    return "; ".join(parts), False


def classify(worktree, branch, main_checkout):
    """Return (done, reason, store_unread) for a worktree; store_unread is
    True when it was kept because the log-store could not be read."""
    managed_area = (main_checkout / ".claude" / "worktrees").resolve()
    if managed_area not in worktree.resolve().parents:
        return (False, "outside the managed area (.claude/worktrees/) — its owner "
                       "decides its lifecycle", False)

    status = run_git(worktree, "status", "--porcelain", "--ignored")
    if status.returncode != 0:
        return False, "git cannot read it (" + status.stderr.strip()[:80] + ")", False
    dirt = [
        line for line in status.stdout.splitlines()
        if not (line.startswith("!!") and
                line[2:].strip().rstrip("/").rsplit("/", 1)[-1]
                in DISPOSABLE_JUNK_BASENAMES)
    ]
    copy_host, records_path = record_shipper.destination_for_this_machine()
    walk_path = records_path.parent / WALK_STORE_KIND_DIRECTORY
    shippable, dirt = split_dirt_into_shippable_and_other(
        worktree, dirt, records_path, walk_path)
    if dirt:
        return False, f"{len(dirt)} uncommitted, untracked, or ignored file(s)", False

    unlanded = run_git(worktree, "log", "--oneline", "origin/main..HEAD")
    if unlanded.returncode != 0:
        return (False, "cannot compare against origin/main ("
                + unlanded.stderr.strip()[:80] + ")", False)
    if unlanded.stdout.strip():
        commits = len(unlanded.stdout.splitlines())
        return False, f"{commits} commit(s) not on origin/main", False

    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason, False

    keep_reason = agent_worktree_quiet_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason, False

    # Last, because it may cross the network and only matters for a
    # worktree every other check has already cleared.
    if shippable:
        keep_reason, store_unread = shipped_files_keep_reason(worktree, shippable, copy_host)
        if keep_reason is not None:
            return False, keep_reason, store_unread
        return (True, f"clean apart from {len(shippable)} file(s) already in the "
                      f"log-store, landed, and vacant", False)

    return True, "clean, landed, and vacant", False


def remove_worktree(worktree, branch, repo):
    """Remove a done worktree and its merged branch; return success."""
    removal = run_git(repo, "worktree", "remove", str(worktree))
    if removal.returncode != 0:
        print(f"{worktree.name}: removal FAILED — {removal.stderr.strip()[:120]}")
        return False
    line = f"{worktree.name}: removed"
    if branch:
        branch_deletion = run_git(repo, "branch", "-d", branch)
        if branch_deletion.returncode == 0:
            line += f", branch {branch} deleted"
        else:
            line += f", branch {branch} left in place (git branch -d refused)"
    print(line)
    return True


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else list(argv)
    repo = REPO_ROOT
    if "--repo" in arguments:
        flag_position = arguments.index("--repo")
        try:
            repo = Path(arguments[flag_position + 1])
        except IndexError:
            print("clean-worktrees: --repo needs a path", file=sys.stderr)
            return 2
        del arguments[flag_position:flag_position + 2]
    only_done = "--only-done" in arguments
    remove = "--remove" in arguments
    leftover = [a for a in arguments if a not in ("--only-done", "--remove")]
    if leftover or (only_done and remove):
        print(__doc__, file=sys.stderr)
        return 2

    main_checkout = main_checkout_of(repo)
    if main_checkout is None:
        print(f"clean-worktrees: {repo} is not a git repository", file=sys.stderr)
        return 2

    failures = 0
    kept_because_store_unread = []
    for worktree, branch in list_worktrees(repo, main_checkout):
        done, reason, store_unread = classify(worktree, branch, main_checkout)
        if store_unread:
            kept_because_store_unread.append((worktree.name, reason))
        if remove:
            if done and not remove_worktree(worktree, branch, repo):
                failures += 1
            elif not done:
                print(f"{worktree.name}: kept — {reason}")
        elif only_done:
            if done:
                print(f"{worktree.name}: done ({reason}) — remove with "
                      f"scripts/clean-worktrees.py --remove")
        else:
            state = "done" if done else "kept"
            print(f"{worktree.name}: {state} — {reason}")

    orphaned_refs = branch_refs_with_no_worktree_fully_on_main(repo)
    if orphaned_refs:
        if remove:
            for branch in orphaned_refs:
                if not delete_orphaned_branch_ref(branch, repo):
                    failures += 1
        else:
            print("branch ref(s) with no worktree, nothing beyond origin/main: "
                  + ", ".join(orphaned_refs)
                  + " — remove with: scripts/clean-worktrees.py --remove")

    if kept_because_store_unread:
        failures += 1
        names = ", ".join(name for name, _ in kept_because_store_unread)
        first_name, first_reason = kept_because_store_unread[0]
        print(f"log-store check FAILED, so worktree(s) {names} were kept; for "
              f"{first_name}: {first_reason}. Nothing was lost; the next run "
              f"checks again. If ned-box did not answer, check it with: "
              f"ssh nedlern@ned-box true")

    dead_registrations = dead_worktree_registrations(repo)
    if dead_registrations:
        print("dead registration(s) git would prune: "
              + ", ".join(f"{path} ({reason})" for path, reason in dead_registrations)
              + " — remove with: git worktree prune")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
