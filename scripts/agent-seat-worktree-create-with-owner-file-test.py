#!/usr/bin/env python3
"""Tests for scripts/agent-seat-worktree-create-with-owner-file.py.

Run: python3 scripts/agent-seat-worktree-create-with-owner-file-test.py
Prints one line per case and exits non-zero if any case fails. Each case runs the program in
a throwaway clone, with an origin of its own and core.hooksPath set to this checkout's git
hooks, and with HOME pointed at a scratch directory holding one agent-seat's directory and
handoff record, so the program reads no real agent-seat. Failures that cannot be caused for
real, an owner file that cannot be written and a removal that fails, are injected by running
the program's main in this process with a function replaced.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS = Path(__file__).resolve().parent
PROGRAM = SCRIPTS / "agent-seat-worktree-create-with-owner-file.py"
HOOK_DIRECTORY = SCRIPTS / "git-client-side-hooks"
SEAT = "seat-a"

_spec = importlib.util.spec_from_file_location("agent_seat_worktree_create_with_owner_file", PROGRAM)
creator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(creator)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class ScratchMachine:
    """A HOME with one agent-seat, SEAT, and a clone at ~/Projects/nedschorus with an origin."""

    def __init__(self, root):
        self.home = root / "home"
        self.clone = self.home / "Projects" / "nedschorus"
        self.managed = self.clone / ".claude" / "worktrees"
        handoffs = self.home / ".claude" / "handoffs"
        handoffs.mkdir(parents=True)
        (handoffs / f"{SEAT}-handoff.md").write_text("handoff\n")
        (self.home / "agents" / SEAT).mkdir(parents=True)
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith(("GIT_", "CLAUDE_", "NEDSCHORUS_"))}
        (root / "empty-gitconfig").write_text("")
        self.environment.update(HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1",
                                GIT_CONFIG_GLOBAL=str(root / "empty-gitconfig"),
                                GIT_AUTHOR_NAME=SEAT)
        origin = root / "origin.git"
        self.git(root, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
        self.clone.mkdir(parents=True)
        self.git(self.clone, "init", "--quiet", "--initial-branch=main")
        self.commit("base")
        self.git(self.clone, "remote", "add", "origin", str(origin))
        self.git(self.clone, "push", "--quiet", "origin", "main")
        self.git(self.clone, "branch", "--quiet", "pushed-only")
        self.git(self.clone, "push", "--quiet", "origin", "pushed-only")
        self.git(self.clone, "branch", "--quiet", "-D", "pushed-only")
        self.git(self.clone, "fetch", "--quiet", "origin")
        self.git(self.clone, "config", "core.hooksPath", str(HOOK_DIRECTORY))

    def git(self, cwd, *arguments, check=True):
        return subprocess.run(["git", *arguments], cwd=cwd, env=self.environment,
                              capture_output=True, text=True, check=check)

    def commit(self, message):
        self.git(self.clone, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "--allow-empty", "-m", message)

    def run(self, *arguments, environment=None, cwd=None):
        return subprocess.run([sys.executable, str(PROGRAM), *arguments], cwd=cwd or self.clone,
                              env={**self.environment, **(environment or {})},
                              capture_output=True, text=True, check=False)

    def run_in_process(self, *arguments):
        """Run the program's main here, under the fixture's environment; (code, stdout, stderr)."""
        saved_environment, saved_directory = dict(os.environ), os.getcwd()
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            os.environ.clear()
            os.environ.update(self.environment)
            os.chdir(self.clone)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = creator.main(list(arguments))
        finally:
            os.environ.clear()
            os.environ.update(saved_environment)
            os.chdir(saved_directory)
        return code, stdout.getvalue(), stderr.getvalue()

    def owner_file(self, worktree):
        located = self.git(worktree, "rev-parse", "--absolute-git-dir")
        path = Path(located.stdout.strip()) / "worktree-owner.json"
        return json.loads(path.read_text()) if path.is_file() else None

    def head(self, worktree, *arguments):
        return self.git(worktree, "rev-parse", *arguments, "HEAD").stdout.strip()

    def registered_worktrees(self):
        listing = self.git(self.clone, "worktree", "list", "--porcelain").stdout
        return [Path(line.split(" ", 1)[1]).resolve() for line in listing.splitlines()
                if line.startswith("worktree ")]

    def branch_exists(self, branch):
        return self.git(self.clone, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}",
                        check=False).returncode == 0


@contextlib.contextmanager
def replaced(module, name, replacement):
    original = getattr(module, name)
    setattr(module, name, replacement)
    try:
        yield
    finally:
        setattr(module, name, original)


def main():
    root = Path(tempfile.mkdtemp(prefix="agent-seat-worktree-create-test-")).resolve()
    try:
        machine = ScratchMachine(root)
        main_commit = machine.head(machine.clone)

        made = machine.run("new-topic")
        path = (machine.managed / "new-topic").resolve()
        check("a new branch: exits 0 and prints the worktree's path alone on stdout",
              made.returncode == 0 and made.stdout == f"{path}\n", f"{made!r}")
        check("a new branch: the worktree is in the managed area, on the new branch, at origin/main",
              path in machine.registered_worktrees()
              and machine.head(path, "--abbrev-ref") == "new-topic"
              and machine.head(path) == main_commit, machine.registered_worktrees())
        check("a new branch: the owner file names the calling agent-seat",
              machine.owner_file(path) == {"owner_kind": "agent-seat", "agent_seat": SEAT},
              str(machine.owner_file(path)))

        machine.commit("second")
        second = machine.head(machine.clone)
        based = machine.run("based-topic", "--base", "main")
        based_path = machine.managed / "based-topic"
        check("--base: the new branch starts at the base given",
              based.returncode == 0 and machine.head(based_path) == second, f"{based!r}")

        machine.git(machine.clone, "branch", "--quiet", "existing-local", main_commit)
        existing = machine.run("existing-local")
        existing_path = machine.managed / "existing-local"
        check("an existing branch of this clone: the worktree checks it out, with an owner file",
              existing.returncode == 0
              and machine.head(existing_path, "--abbrev-ref") == "existing-local"
              and machine.owner_file(existing_path) is not None, f"{existing!r}")

        pushed = machine.run("pushed-only")
        pushed_path = machine.managed / "pushed-only"
        upstream = machine.git(pushed_path, "rev-parse", "--abbrev-ref", "@{upstream}", check=False)
        check("a branch only on origin: a local branch tracking origin's is checked out",
              pushed.returncode == 0 and upstream.stdout.strip() == "origin/pushed-only"
              and machine.head(pushed_path) == main_commit, f"{pushed!r} {upstream!r}")

        machine.git(machine.clone, "push", "--quiet", "origin", "main:refs/heads/pushed-later")
        machine.git(machine.clone, "update-ref", "-d", "refs/remotes/origin/pushed-later")
        later = machine.run("pushed-later")
        later_path = machine.managed / "pushed-later"
        later_upstream = machine.git(later_path, "rev-parse", "--abbrev-ref", "@{upstream}",
                                     check=False)
        check("a branch pushed to origin after this clone's last fetch: fetched, then tracked, "
              "not cut afresh from origin/main",
              later.returncode == 0 and later_upstream.stdout.strip() == "origin/pushed-later",
              f"{later!r} {later_upstream!r}")

        detached = machine.run("--detach", "review-head", main_commit)
        detached_path = machine.managed / "review-head"
        symbolic = machine.git(detached_path, "symbolic-ref", "-q", "HEAD", check=False)
        check("--detach: the worktree stands detached at the commit, with an owner file",
              detached.returncode == 0 and symbolic.returncode != 0
              and machine.head(detached_path) == main_commit
              and machine.owner_file(detached_path) is not None, f"{detached!r}")

        nested = machine.run("feature/nested")
        check("a branch name with / makes nested directories in the managed area",
              nested.returncode == 0 and (machine.managed / "feature" / "nested").is_dir(),
              f"{nested!r}")

        from_worktree = machine.run("from-a-worktree", cwd=path)
        check("run from a linked worktree, it still makes the worktree in the reference-checkout's "
              "managed area", from_worktree.returncode == 0
              and from_worktree.stdout.strip() == str((machine.managed / "from-a-worktree").resolve()),
              f"{from_worktree!r}")

        # --- refusals before anything is made -----------------------------------------------
        before = machine.registered_worktrees()
        not_a_seat = machine.run("no-seat-topic", environment={"GIT_AUTHOR_NAME": "nobody"})
        check("GIT_AUTHOR_NAME naming no agent-seat: refused with exit 2, nothing made",
              not_a_seat.returncode == 2 and "REFUSED" in not_a_seat.stderr
              and "'nobody'" in not_a_seat.stderr and not machine.branch_exists("no-seat-topic")
              and machine.registered_worktrees() == before, f"{not_a_seat!r}")

        machine.git(machine.clone, "branch", "--quiet", "existing-local-2", main_commit)
        base_on_existing = machine.run("existing-local-2", "--base", "main")
        check("--base with an existing branch: refused with exit 2, naming the branch",
              base_on_existing.returncode == 2
              and "branch existing-local-2 already exists (in this clone)" in base_on_existing.stderr
              and not (machine.managed / "existing-local-2").exists(),
              f"{base_on_existing!r}")
        machine.git(machine.clone, "push", "--quiet", "origin", "main:refs/heads/origin-only-2")
        machine.git(machine.clone, "fetch", "--quiet", "origin")
        base_on_origin = machine.run("origin-only-2", "--base", "main")
        check("--base with a branch only on origin: refused, saying it is on origin",
              base_on_origin.returncode == 2 and "(on origin)" in base_on_origin.stderr
              and not machine.branch_exists("origin-only-2"), f"{base_on_origin!r}")

        occupied = machine.managed / "occupied"
        occupied.mkdir(parents=True)
        path_exists = machine.run("occupied")
        check("a path that already exists: refused with exit 2, and no branch made",
              path_exists.returncode == 2 and f"{occupied} already exists" in path_exists.stderr
              and not machine.branch_exists("occupied"), f"{path_exists!r}")

        for arguments, wanted in ((("--detach", "only-a-name"), "--detach takes"),
                                  (("--detach", "../escape", main_commit), "no '..'"),
                                  (("--detach", "/absolute", main_commit), "no '..'"),
                                  (("two", "branches"), "one branch name"),
                                  (("topic", "--base"), "--base needs"),
                                  (("bad..name",), "not a valid branch name"),
                                  ((), "one branch name")):
            bad = machine.run(*arguments)
            check(f"bad invocation {arguments}: exit 2 and the usage",
                  bad.returncode == 2 and wanted in bad.stderr and "usage:" in bad.stderr,
                  f"{bad!r}")

        helped = machine.run("--help")
        check("--help prints the docstring on stdout and exits 0",
              helped.returncode == 0 and "Usage:" in helped.stdout, f"{helped!r}")

        # --- git fails ----------------------------------------------------------------------
        checked_out = machine.run("new-topic-again", "--base", "no-such-commit")
        check("git worktree add failing: exit 1 and git's own message",
              checked_out.returncode == 1 and checked_out.stderr.startswith(
                  "agent-seat-worktree-create-with-owner-file: FAILED: `git")
              and "no-such-commit" in checked_out.stderr and checked_out.stdout == "",
              f"{checked_out!r}")
        origin_url = machine.git(machine.clone, "remote", "get-url", "origin").stdout.strip()
        machine.git(machine.clone, "remote", "set-url", "origin", str(root / "no-such-origin.git"))
        unfetched = machine.run("needs-a-fetch")
        detached_offline = machine.run("--detach", "offline-detached", main_commit)
        machine.git(machine.clone, "remote", "set-url", "origin", origin_url)
        check("the fetch failing: exit 1 naming git fetch, and nothing made",
              unfetched.returncode == 1 and "`git fetch --quiet origin` exited" in unfetched.stderr
              and not machine.branch_exists("needs-a-fetch")
              and not (machine.managed / "needs-a-fetch").exists(), f"{unfetched!r}")
        check("--detach and a local branch need no fetch",
              detached_offline.returncode == 0, f"{detached_offline!r}")
        outside = machine.run("outside", cwd=root)
        check("run outside any clone: exit 1 naming the git command that failed",
              outside.returncode == 1 and "rev-parse" in outside.stderr, f"{outside!r}")

        # --- --owned-by-agent-session --------------------------------------------------------
        # The suite may itself run under claude, so the walk up the parent processes is replaced.
        snapshots = creator.owner_file.load_uncommitted_work_snapshots_module_once()
        with replaced(snapshots, "claude_owner_process_id", lambda start: os.getpid()):
            code, stdout, stderr = machine.run_in_process("session-owned", "--owned-by-agent-session")
        session_owned = machine.managed / "session-owned"
        check("--owned-by-agent-session: the owner file names the nearest claude parent's agent-session "
              "and the calling agent-seat",
              code == 0 and stdout == f"{session_owned}\n"
              and machine.owner_file(session_owned) == {
                  "owner_kind": "agent-session", "agent_seat": SEAT,
                  "owner_key": snapshots.owner_key_of_process(os.getpid())}, f"{code} {stderr}")
        with replaced(snapshots, "claude_owner_process_id", lambda start: None):
            code, stdout, stderr = machine.run_in_process("--detach", "no-claude", main_commit,
                                                          "--owned-by-agent-session")
        no_claude = machine.managed / "no-claude"
        check("--owned-by-agent-session with no claude among the parent processes: exit 1, the "
              "cause on stderr, the worktree removed",
              code == 1 and stdout == "" and "no process named claude" in stderr
              and not no_claude.exists() and no_claude.resolve() not in machine.registered_worktrees(),
              f"{code} {stderr}")

        # --- the owner file cannot be written ----------------------------------------------
        def refuse_write(*arguments, **keywords):
            raise creator.owner_file.WorktreeOwnerFileError("disk full (injected)")

        with replaced(creator.owner_file, "worktree_owner_file_write", refuse_write):
            code, stdout, stderr = machine.run_in_process("unwritable-topic")
        unwritable = machine.managed / "unwritable-topic"
        check("owner file write fails: exit 1, nothing on stdout, the cause on stderr",
              code == 1 and stdout == "" and "disk full (injected)" in stderr, f"{code} {stderr}")
        check("owner file write fails: the worktree it made is removed",
              not unwritable.exists()
              and unwritable.resolve() not in machine.registered_worktrees(),
              str(machine.registered_worktrees()))
        check("owner file write fails: the branch it made is kept and the message says so",
              machine.branch_exists("unwritable-topic")
              and "branch unwritable-topic it made is kept" in stderr, stderr)
        rerun = machine.run("unwritable-topic")
        check("owner file write fails: a rerun checks out the kept branch",
              rerun.returncode == 0 and machine.owner_file(unwritable) is not None, f"{rerun!r}")

        with replaced(creator.owner_file, "worktree_owner_file_write", refuse_write):
            code, _, stderr = machine.run_in_process("unwritable-based", "--base", "main")
        check("owner file write fails after --base: the message says to rerun without --base",
              code == 1 and "without --base" in stderr, stderr)
        with replaced(creator.owner_file, "worktree_owner_file_write", refuse_write):
            code, _, stderr = machine.run_in_process("existing-local-2")
        check("owner file write fails on a branch that existed: no branch-kept sentence",
              code == 1 and "it made is kept" not in stderr, stderr)

        real_git = creator.git

        def removal_fails(*arguments, check=True):
            if arguments[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(["git", *arguments], 128, "",
                                                   "fatal: removal refused (injected)")
            return real_git(*arguments, check=check)

        with replaced(creator.owner_file, "worktree_owner_file_write", refuse_write), \
                replaced(creator, "git", removal_fails):
            code, stdout, stderr = machine.run_in_process("unremovable-topic")
        unremovable = machine.managed / "unremovable-topic"
        check("owner file write and removal both fail: exit 1, the worktree named as left",
              code == 1 and stdout == "" and "removal refused (injected)" in stderr
              and f"git worktree remove --force {unremovable}" in stderr
              and unremovable.is_dir(), f"{code} {stderr}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
