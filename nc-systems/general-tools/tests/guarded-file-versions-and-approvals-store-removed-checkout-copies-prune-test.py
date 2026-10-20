#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py.

Each case builds a scratch store and scratch checkouts in a temporary directory, never the real
store, and runs the program on them as ned-box.

Run: python3 nc-systems/general-tools/tests/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import hashlib
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = (Path(__file__).resolve().parents[1]
           / "guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py")
HOOK_PATH = (REPOSITORY_ROOT / ".claude" / "hooks"
             / "guarded-file-unapproved-change-afterward-backup-and-ask-hook.py")
_specification = importlib.util.spec_from_file_location("guarded_file_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(hook)

failures = []
HELD_SUMMARY = ("{verb} {count} copies whose version a commit on a branch, a tag or a "
                "remote-tracking branch holds")


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def blob(text):
    data = text.encode()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def add_version(store, path, text, approved, copy=True):
    """Put one copy of path into the scratch store, as the hook does, with its seen line and,
    when approved, its approved line. With copy=False, only the seen line of a deletion."""
    directory = store / path.lstrip("/")
    directory.mkdir(parents=True, exist_ok=True)
    key = blob(text) if copy else hook.DELETED
    if copy:
        (directory / key).write_text(text)
    with open(directory / hook.LOG_FILE_NAME, "ab") as log:
        log.write(hook.checked_line("\t".join(["seen", "1", "session", "owner", key, key, ""])))
    if approved:
        with open(directory / hook.APPROVED_FILE_NAME, "ab") as approved_file:
            approved_file.write(hook.checked_line(key))
    return directory / key


def run(store, *arguments, **variables):
    environment = dict(os.environ, GUARDED_FILE_VERSIONS_MACHINE="ned-box",
                       GUARDED_FILE_VERSIONS_STORE_DIRECTORY=str(store))
    environment.update(variables)
    return run_in_own_process_group([sys.executable, str(PROGRAM), *arguments], environment)


def run_in_own_process_group(command, environment):
    """Run command and kill its whole process group afterwards, so a child it forked and left
    blocked does not outlive the test. A timeout raises, after the kill."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env=environment, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=120)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def git(*arguments):
    subprocess.run(["git", *arguments], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                            GIT_CONFIG_GLOBAL="/dev/null"))


def path_failing_git(root, arguments):
    """A PATH on which every git whose command line holds arguments fails as a broken
    repository does."""
    directory = root / "failing-git"
    directory.mkdir()
    wrapper = directory / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"case \" $* \" in *\"{arguments}\"*) echo 'fatal: injected failure' >&2; exit 128;; esac\n"
        f"exec {shutil.which('git')} \"$@\"\n")
    wrapper.chmod(0o755)
    return f"{directory}:{os.environ['PATH']}"


def scratch(root):
    """A store and the checkouts its paths name: (store, agents directory, live repository)."""
    store = root / "store"
    store.mkdir()
    agents = root / "agents"
    (agents / "live").mkdir(parents=True)
    (agents / "live" / "CLAUDE.md").write_text("live\n")
    repository = root / "repository"
    repository.mkdir()
    git("init", "-q", str(repository))
    (repository / ".gitignore").write_text("worktrees/\n")
    (repository / "docs").mkdir()
    return store, agents, repository


def test_removed_checkouts_pruned_and_others_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, repository = scratch(root)
        removed = add_version(store, f"{agents}/removed/CLAUDE.md", "one\n", approved=True)
        live = add_version(store, f"{agents}/live/CLAUDE.md", "live\n", approved=True)
        unapproved_old = add_version(store, f"{agents}/declined/CLAUDE.md", "a\n", approved=True)
        unapproved = add_version(store, f"{agents}/declined/CLAUDE.md", "b\n", approved=False)
        nested = add_version(store, f"{repository}/worktrees/gone/CLAUDE.md", "n\n", approved=True)
        branch_deleted_directory = add_version(store, f"{repository}/docs/gone/a.md", "d\n",
                                               approved=True)
        branch_deleted_file = add_version(store, f"{repository}/docs/b.md", "f\n", approved=True)
        dry = run(store, "--dry-run")
        check("--dry-run exits 0", dry.returncode == 0, dry.stderr)
        check("--dry-run deletes nothing", removed.exists() and nested.exists(), dry.stdout)
        check("--dry-run names the removed checkout", f"removed checkout {agents}/removed: would delete" in dry.stdout,
              dry.stdout)
        check("--dry-run names no checkout that exists or keeps its copies",
              all(f"removed checkout {name}" not in dry.stdout for name in
                  (f"{agents}/live", f"{agents}/declined", f"{repository}:", f"{repository}/docs")),
              dry.stdout)
        result = run(store)
        check("a run exits 0", result.returncode == 0, result.stderr)
        check("a removed checkout's approved copy is deleted", not removed.exists())
        check("its log and approved set stay", (removed.parent / hook.LOG_FILE_NAME).exists())
        check("an existing checkout's copy is kept", live.exists())
        check("a removed checkout's version never approved is kept", unapproved.exists())
        check("so is the approved copy beside it", unapproved_old.exists())
        check("a gone checkout under a directory git ignores is pruned", not nested.exists())
        check("a directory deleted on a branch keeps its copies", branch_deleted_directory.exists())
        check("a file deleted in an existing directory keeps its copies",
              branch_deleted_file.exists())
        check("the run names each copy it deletes before deleting it",
              f"deleting {removed}\n" in result.stdout and f"deleting {nested}\n" in result.stdout
              and "deleting " + str(live) not in result.stdout, result.stdout)
        check("the summary counts two checkouts, one copy not approved and one approved copy kept",
              "whose every version was approved, in 2 removed checkouts" in result.stdout
              and "1 copies of versions not approved and 1 approved copies of the same files" in result.stdout,
              result.stdout)


def test_copies_of_paths_with_a_version_not_approved_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        before_declined_deletion = add_version(store, f"{agents}/removed/CLAUDE.md", "one\n",
                                               approved=True)
        add_version(store, f"{agents}/removed/CLAUDE.md", "", approved=False, copy=False)
        accounted = add_version(store, f"{agents}/removed/AGENTS.md", "two\n", approved=True)
        stray = accounted.parent / blob("never logged\n")
        stray.write_text("never logged\n")
        result = run(store)
        check("a run with nothing to delete exits 0", result.returncode == 0, result.stderr)
        check("the approved copy before a deletion never approved is kept",
              before_declined_deletion.exists())
        check("a copy neither approved nor logged is kept", stray.exists())
        check("and so is the approved copy beside it", accounted.exists())
        check("the summary counts the stray copy as not approved and the other two as approved",
              "1 copies of versions not approved and 2 approved copies of the same files" in result.stdout,
              result.stdout)


def test_outside_checkout_files_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, _, _ = scratch(root)
        home = root / "home"
        home.mkdir()
        instructions = add_version(store, f"{home}/.claude/CLAUDE.md", "one\n", approved=True)
        settings = add_version(store, f"{home}/.claude/settings.json", "{}\n", approved=True)
        result = run(store, HOME=str(home))
        check("a run with ~/.claude missing exits 0", result.returncode == 0, result.stderr)
        check("and keeps the copies of ~/.claude's files", instructions.exists() and settings.exists())


def test_checkout_that_cannot_be_searched_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        (agents / "locked" / "repo").mkdir(parents=True)
        (agents / "locked" / "repo" / "CLAUDE.md").write_text("one\n")
        locked = add_version(store, f"{agents}/locked/repo/CLAUDE.md", "one\n", approved=True)
        removed = add_version(store, f"{agents}/removed/CLAUDE.md", "two\n", approved=True)
        (agents / "locked").chmod(0)
        try:
            dry = run(store, "--dry-run")
            result = run(store)
        finally:
            (agents / "locked").chmod(0o700)
        check("--dry-run does not name a checkout it cannot search",
              f"{agents}/locked" not in dry.stdout, dry.stdout)
        check("a checkout it cannot search exits 1", result.returncode == 1, result.stdout)
        check("and keeps its copy", locked.exists())
        check("and says why", f"{agents}/locked/repo/CLAUDE.md's copies were kept" in result.stderr
              and "Permission denied" in result.stderr, result.stderr)
        check("the other checkout is still pruned", not removed.exists())


def load_program():
    specification = importlib.util.spec_from_file_location("prune", PROGRAM)
    prune = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(prune)
    return prune


def test_recreated_checkout_kept():
    prune = load_program()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, _, repository = scratch(root)
        copy = add_version(store, f"{repository}/worktrees/gone/CLAUDE.md", "one\n",
                           approved=True)

        def recreated_while_checked(checkout_root, relative):
            (checkout_root / relative).mkdir(parents=True)
            return True

        result = prune.prune(store, False, check_ignore=recreated_while_checked)
        check("a checkout re-created after it was found missing keeps its copies",
              copy.exists() and not result["checkouts"], result)


def test_recheck_that_cannot_be_told_keeps_copies():
    prune = load_program()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, _, repository = scratch(root)
        copy = add_version(store, f"{repository}/worktrees/gone/CLAUDE.md", "one\n",
                           approved=True)

        def made_unsearchable_while_checked(checkout_root, relative):
            checkout_root.chmod(0)
            return True

        try:
            result = prune.prune(store, False, check_ignore=made_unsearchable_while_checked)
        finally:
            repository.chmod(0o700)
        check("a recheck that cannot be told keeps the copies", copy.exists()
              and not result["checkouts"], result)
        check("and reports it", any("could not be told" in failure
                                    for failure in result["failures"]), result)


def test_volume_that_may_not_be_mounted_kept():
    prune = load_program()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        volumes = root / "Volumes"
        (volumes / "empty-mount-point").mkdir(parents=True)
        (volumes / "mounted" / "other").mkdir(parents=True)
        gone = add_version(store, f"{volumes}/gone/repo/CLAUDE.md", "a\n", approved=True)
        empty = add_version(store, f"{volumes}/empty-mount-point/repo/CLAUDE.md", "b\n",
                            approved=True)
        removed_on_mounted = add_version(store, f"{volumes}/mounted/repo/CLAUDE.md", "c\n",
                                         approved=True)
        removed = add_version(store, f"{agents}/removed/CLAUDE.md", "d\n", approved=True)
        result = prune.prune(store, False, mount_parents=(volumes,))
        check("copies under a missing volume directory are kept", gone.exists())
        check("copies under an empty volume directory are kept", empty.exists())
        check("and both are reported", sum("may not be mounted" in failure
                                          for failure in result["failures"]) == 2, result)
        check("a checkout removed from a volume with other content is pruned",
              not removed_on_mounted.exists())
        check("a checkout removed outside any volume is pruned", not removed.exists())


def test_run_stopped_between_two_unlinks_names_every_deleted_copy():
    # The wrapper makes the run wait forever, after creating a marker file, once the first unlink
    # of the run has finished: the stop lands between two unlinks of one path.
    wrapper = (
        "import importlib.util, pathlib, sys, time\n"
        "marker, program = sys.argv[1:3]\n"
        "spec = importlib.util.spec_from_file_location('prune', program)\n"
        "prune = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(prune)\n"
        "original, calls = pathlib.Path.unlink, []\n"
        "def unlink(self, *arguments, **keywords):\n"
        "    original(self, *arguments, **keywords)\n"
        "    calls.append(self)\n"
        "    if len(calls) == 1:\n"
        "        pathlib.Path(marker).write_text('waiting')\n"
        "        time.sleep(600)\n"
        "pathlib.Path.unlink = unlink\n"
        "sys.exit(prune.main([]))\n")
    for stop in (signal.SIGTERM, signal.SIGKILL):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store, agents, _ = scratch(root)
            copies = [add_version(store, f"{agents}/removed/CLAUDE.md", text, approved=True)
                      for text in ("one\n", "two\n", "three\n")]
            marker = root / "marker"
            output = root / "output"
            environment = dict(os.environ, GUARDED_FILE_VERSIONS_MACHINE="ned-box",
                               GUARDED_FILE_VERSIONS_STORE_DIRECTORY=str(store))
            with open(output, "w") as output_file:
                process = subprocess.Popen([sys.executable, "-c", wrapper, str(marker),
                                            str(PROGRAM)], stdout=output_file,
                                           stderr=subprocess.STDOUT, env=environment,
                                           start_new_session=True)
            try:
                deadline = time.monotonic() + 60
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                reached = marker.exists()
                os.killpg(process.pid, stop)
                process.wait(timeout=30)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            name = stop.name
            named = output.read_text().splitlines()
            deleted = [copy for copy in copies if not copy.exists()]
            check(f"{name}: the run was stopped between two unlinks of one path",
                  reached and len(deleted) == 1, (reached, deleted))
            check(f"{name}: every copy deleted before the stop is named on a deleting line",
                  all(f"deleting {copy}" in named for copy in deleted), (named, deleted))


def test_unreadable_store_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        result = run(root / "absent")
        check("a store that does not exist exits 1", result.returncode == 1, result.stdout)
        check("and says the store could not be opened", "could not be opened" in result.stderr,
              result.stderr)
        store, agents, _ = scratch(root)
        copy = add_version(store, f"{agents}/removed-a/CLAUDE.md", "one\n", approved=True)
        unreadable = copy.parent
        unreadable.chmod(0)
        other = add_version(store, f"{agents}/removed-b/CLAUDE.md", "two\n", approved=True)
        try:
            result = run(store)
        finally:
            unreadable.chmod(0o700)
        check("a store directory that cannot be read exits 1", result.returncode == 1,
              result.stdout)
        check("and names the directory", f"{unreadable} could not be read" in result.stderr,
              result.stderr)
        check("and keeps its copy", copy.exists())
        check("the other checkout is still pruned, and named", not other.exists()
              and f"deleting {other}\n" in result.stdout,
              result.stdout)
        other = add_version(store, f"{agents}/removed-b/CLAUDE.md", "two\n", approved=True)
        (copy.parent / hook.LOG_FILE_NAME).chmod(0)
        try:
            result = run(store)
        finally:
            (copy.parent / hook.LOG_FILE_NAME).chmod(0o600)
        check("a log that cannot be read exits 1", result.returncode == 1, result.stdout)
        check("and names the log", f"{copy.parent / hook.LOG_FILE_NAME} could not be read"
              in result.stderr, result.stderr)
        check("and keeps the copy", copy.exists())
        check("the other checkout is still pruned, and named", not other.exists()
              and f"deleting {other}\n" in result.stdout,
              result.stdout)


def test_failing_delete_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        stuck = add_version(store, f"{agents}/removed-a/CLAUDE.md", "one\n", approved=True)
        other = add_version(store, f"{agents}/removed-b/CLAUDE.md", "two\n", approved=True)
        repository = scratch_repository_with_commit(root)
        held_stuck = add_version(store, f"{repository}/CLAUDE.md", "one\n", approved=True)
        stuck.parent.chmod(0o500)
        held_stuck.parent.chmod(0o500)
        try:
            result = run(store)
        finally:
            stuck.parent.chmod(0o700)
            held_stuck.parent.chmod(0o700)
        check("a delete that fails exits 1", result.returncode == 1, result.stdout)
        check("and names the copy", f"{stuck} could not be deleted" in result.stderr,
              result.stderr)
        check("a delete of a copy a commit holds that fails is named and not counted",
              f"{held_stuck} could not be deleted" in result.stderr
              and HELD_SUMMARY.format(verb="deleted", count=0) in result.stdout,
              (result.stdout, result.stderr))
        check("the other checkout is still pruned", not other.exists())


def scratch_repository_with_commit(root):
    """A repository whose one commit holds CLAUDE.md reading "one"."""
    repository = root / "committed-repository"
    repository.mkdir()
    git("init", "-q", str(repository))
    (repository / "CLAUDE.md").write_text("one\n")
    git("-C", str(repository), "add", "CLAUDE.md")
    git("-C", str(repository), "commit", "-q", "-m", "one")
    return repository


def test_git_failure_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store = root / "store"
        store.mkdir()
        # Named to sort before agents/, so the walk reaches git's failure before the other copy.
        broken = root / "a-broken"
        broken.mkdir()
        git("init", "-q", str(broken))
        (broken / ".gitignore").write_text("worktree/\n")
        copy = add_version(store, f"{broken}/worktree/CLAUDE.md", "one\n", approved=True)
        other = add_version(store, f"{root}/agents/removed/CLAUDE.md", "two\n", approved=True)
        result = run(store, PATH=path_failing_git(root, "check-ignore"))
        check("git that cannot answer exits 1", result.returncode == 1, result.stdout)
        check("and says git failed", "check-ignore" in result.stderr
              and "injected failure" in result.stderr, result.stderr)
        check("and keeps that checkout's copy", copy.exists())
        check("and goes on to the end", "1 failures" in result.stdout, result.stdout)
        check("the other checkout is still pruned, and named", not other.exists()
              and f"deleting {other}\n" in result.stdout,
              result.stdout)


def test_copies_a_commit_holds_deleted():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, _, repository = scratch(root)
        (repository / "CLAUDE.md").write_text("committed\n")
        (repository / "docs" / "a.md").write_text("on a branch\n")
        git("-C", str(repository), "add", "CLAUDE.md")
        git("-C", str(repository), "commit", "-q", "-m", "one")
        git("-C", str(repository), "checkout", "-q", "-b", "side")
        git("-C", str(repository), "add", "docs/a.md")
        git("-C", str(repository), "commit", "-q", "-m", "side")
        git("-C", str(repository), "checkout", "-q", "-")
        committed = add_version(store, f"{repository}/CLAUDE.md", "committed\n", approved=True)
        not_approved = add_version(store, f"{repository}/CLAUDE.md", "unapproved\n",
                                   approved=False)
        (repository / "CLAUDE.md").write_text("unapproved\n")
        git("-C", str(repository), "commit", "-q", "-am", "two")
        (repository / "docs").mkdir(exist_ok=True)
        (repository / "docs" / "a.md").write_text("only staged\n")
        git("-C", str(repository), "add", "docs/a.md")
        uncommitted = add_version(store, f"{repository}/CLAUDE.md", "never committed\n",
                                  approved=False)
        on_branch = add_version(store, f"{repository}/docs/a.md", "on a branch\n", approved=True)
        staged = add_version(store, f"{repository}/docs/a.md", "only staged\n", approved=True)
        in_removed = add_version(store, f"{repository}/worktrees/gone/CLAUDE.md", "committed\n",
                                 approved=False)
        approved_in_removed = add_version(store, f"{repository}/worktrees/gone-too/CLAUDE.md",
                                          "committed\n", approved=True)
        dry = run(store, "--dry-run")
        check("--dry-run deletes no copy a commit holds",
              committed.exists() and on_branch.exists(), dry.stdout)
        check("--dry-run counts them",
              HELD_SUMMARY.format(verb="would delete", count=5) in dry.stdout, dry.stdout)
        result = run(store)
        check("a run that deletes copies a commit holds exits 0", result.returncode == 0,
              result.stderr)
        check("an approved copy a commit holds, in an existing checkout, is deleted",
              not committed.exists())
        check("a copy a commit holds whose version was never approved is deleted",
              not not_approved.exists())
        check("a copy only a branch other than the checked-out one holds is deleted",
              not on_branch.exists())
        check("a copy a commit holds, of a removed checkout's version never approved, is deleted",
              not in_removed.exists())
        check("and so is an approved one", not approved_in_removed.exists())
        check("a copy no commit holds is kept", uncommitted.exists())
        check("a copy git holds only as a staged blob is kept", staged.exists())
        check("the run names each copy it deletes", f"deleting {committed}\n" in result.stdout,
              result.stdout)
        check("the summary counts them",
              HELD_SUMMARY.format(verb="deleted", count=5) in result.stdout, result.stdout)
        check("a run with no failures says so, and does not point at stderr",
              result.stdout.rstrip().endswith("; no failures")
              and "failures, each named" not in result.stdout, result.stdout)


def test_copies_only_refs_that_are_not_durable_hold_kept():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, _, repository = scratch(root)
        (repository / "CLAUDE.md").write_text("on main\n")
        git("-C", str(repository), "add", "CLAUDE.md")
        git("-C", str(repository), "commit", "-q", "-m", "one")
        # A work snapshot: a commit only refs/work-snapshots/ reaches, as the snapshot hook makes.
        (repository / "CLAUDE.md").write_text("only in a work snapshot\n")
        git("-C", str(repository), "add", "CLAUDE.md")
        tree = subprocess.run(["git", "-C", str(repository), "write-tree"], check=True,
                              capture_output=True, text=True).stdout.strip()
        snapshot = subprocess.run(
            ["git", "-C", str(repository), "commit-tree", tree, "-m", "snapshot"], check=True,
            capture_output=True, text=True,
            env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                     GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")).stdout.strip()
        git("-C", str(repository), "update-ref", "refs/work-snapshots/agent", snapshot)
        (repository / "CLAUDE.md").write_text("only in a stash\n")
        git("-C", str(repository), "stash", "-q")
        # A detached worktree's HEAD, on no branch, is not durable: removing the worktree drops it.
        linked = root / "linked-worktree"
        git("-C", str(repository), "worktree", "add", "-q", "--detach", str(linked))
        (linked / "CLAUDE.md").write_text("only at a detached worktree HEAD\n")
        git("-C", str(linked), "commit", "-q", "-am", "detached")
        snapshot_only = add_version(store, f"{repository}/CLAUDE.md", "only in a work snapshot\n",
                                    approved=True)
        stash_only = add_version(store, f"{repository}/CLAUDE.md", "only in a stash\n",
                                 approved=True)
        detached = add_version(store, f"{linked}/CLAUDE.md", "only at a detached worktree HEAD\n",
                               approved=True)
        result = run(store)
        check("a run with versions only refs that are not durable hold exits 0",
              result.returncode == 0, result.stderr)
        check("a copy only a refs/work-snapshots/ ref holds is kept", snapshot_only.exists(),
              result.stdout)
        check("a copy only refs/stash holds is kept", stash_only.exists(), result.stdout)
        check("a copy only a detached worktree's HEAD holds is kept", detached.exists(),
              result.stdout)


def test_repository_that_cannot_be_named_fails():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, repository = scratch(root)
        (repository / "CLAUDE.md").write_text("one\n")
        git("-C", str(repository), "add", "CLAUDE.md")
        git("-C", str(repository), "commit", "-q", "-m", "one")
        copy = add_version(store, f"{repository}/CLAUDE.md", "one\n", approved=True)
        other = add_version(store, f"{agents}/removed/CLAUDE.md", "two\n", approved=True)
        result = run(store, PATH=path_failing_git(root, "--git-common-dir"))
        check("git that cannot name a path's repository exits 1", result.returncode == 1,
              result.stdout)
        check("and says so", f"{repository}/CLAUDE.md's copies were kept: git rev-parse" in
              result.stderr and "injected failure" in result.stderr, result.stderr)
        check("and keeps that path's copy", copy.exists())
        check("the other checkout is still pruned", not other.exists(), result.stdout)


def test_commits_that_cannot_be_listed_fail():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, repository = scratch(root)
        (repository / "CLAUDE.md").write_text("one\n")
        git("-C", str(repository), "add", "CLAUDE.md")
        git("-C", str(repository), "commit", "-q", "-m", "one")
        copy = add_version(store, f"{repository}/CLAUDE.md", "one\n", approved=True)
        other = add_version(store, f"{agents}/removed/CLAUDE.md", "two\n", approved=True)
        result = run(store, PATH=path_failing_git(root, "rev-list"))
        check("git that cannot list its commits' blobs exits 1", result.returncode == 1,
              result.stdout)
        check("and says so", f"{repository}/CLAUDE.md's copies were kept: git rev-list" in
              result.stderr and "injected failure" in result.stderr, result.stderr)
        check("and keeps that path's copy", copy.exists())
        check("the other checkout is still pruned", not other.exists(), result.stdout)


def test_mac_deadline_names_what_was_deleted():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        store, agents, _ = scratch(root)
        mount_point = root / "mount"
        table = root / "mount-table"
        table.write_text(f"//nedlern@ned-box/nedlern on {mount_point} (smbfs)\n")
        deleted = add_version(store, f"{agents}/removed/CLAUDE.md", "one\n", approved=True)
        # The walk lists a directory before the ones inside it; reading the FIFO below waits.
        hanging = store / str(agents).lstrip("/") / "removed" / "CLAUDE.md" / "inner"
        hanging.mkdir()
        (hanging / blob("two\n")).write_text("two\n")
        os.mkfifo(hanging / hook.LOG_FILE_NAME)
        started = time.monotonic()
        result = run(store, GUARDED_FILE_VERSIONS_MACHINE="mac",
                     GUARDED_FILE_VERSIONS_MOUNT_TABLE=str(table),
                     GUARDED_FILE_VERSIONS_MOUNT_POINT=str(mount_point),
                     GUARDED_FILE_VERSIONS_DEADLINE_SECONDS="2")
        check("a run stopped at the Mac's deadline exits 1", result.returncode == 1,
              result.stdout + result.stderr)
        check("and stops at the deadline", time.monotonic() - started < 60)
        check("and has deleted the copy it reached", not deleted.exists())
        check("and names that deletion", f"deleting {deleted}\n" in result.stdout, result.stdout)
        check("and says the run stopped, not that nothing was pruned",
              "stopped: the store did not answer within 2.0 seconds" in result.stderr
              and "not pruned" not in result.stderr, result.stderr)


if __name__ == "__main__":
    test_removed_checkouts_pruned_and_others_kept()
    test_copies_of_paths_with_a_version_not_approved_kept()
    test_outside_checkout_files_kept()
    test_checkout_that_cannot_be_searched_kept()
    test_recreated_checkout_kept()
    test_recheck_that_cannot_be_told_keeps_copies()
    test_volume_that_may_not_be_mounted_kept()
    test_run_stopped_between_two_unlinks_names_every_deleted_copy()
    test_unreadable_store_fails()
    test_failing_delete_fails()
    test_git_failure_fails()
    test_copies_a_commit_holds_deleted()
    test_commits_that_cannot_be_listed_fail()
    test_copies_only_refs_that_are_not_durable_hold_kept()
    test_repository_that_cannot_be_named_fails()
    test_mac_deadline_names_what_was_deleted()
    if failures:
        print(f"{len(failures)} case(s) failed")
        sys.exit(1)
    print("all cases passed")
