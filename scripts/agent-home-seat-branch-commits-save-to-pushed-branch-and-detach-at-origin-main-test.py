#!/usr/bin/env python3
"""Tests for scripts/agent-home-seat-branch-commits-save-to-pushed-branch-and-detach-at-origin-main.py.

Run: python3 scripts/agent-home-seat-branch-commits-save-to-pushed-branch-and-detach-at-origin-main-test.py
Prints one line per case and exits non-zero if any case fails. Each case runs the program on a
throwaway bare origin, a clone of it and agent-homes made as worktrees of that clone under a
temporary agents root, with a temporary handoff directory; nothing outside the temporary
directory is read or changed.
"""

import contextlib
import datetime
import importlib.util
import io
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

PROGRAM = Path(__file__).resolve().with_name(
    "agent-home-seat-branch-commits-save-to-pushed-branch-and-detach-at-origin-main.py")
TODAY = datetime.date.today().isoformat()

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Fleet:
    """A bare origin, a clone of it, an agents root and a handoff directory."""

    def __init__(self, root: Path):
        self.root = root
        self.global_config = root / "gitconfig"
        self.global_config.write_text("[user]\n\tname = fixture\n\temail = fixture@example.invalid\n"
                                      "[init]\n\tdefaultBranch = main\n")
        self.origin = root / "origin.git"
        self.git(root, "init", "--quiet", "--bare", str(self.origin))
        self.clone = root / "clone"
        self.git(root, "clone", "--quiet", str(self.origin), str(self.clone))
        self.commit(self.clone, "base.txt", "First commit")
        self.git(self.clone, "push", "--quiet", "origin", "HEAD:refs/heads/main")
        self.git(self.clone, "fetch", "--quiet", "origin")
        self.agents_root = root / "agents"
        self.agents_root.mkdir()
        self.handoffs = root / "handoffs"
        self.handoffs.mkdir()

    def environment(self):
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = str(self.global_config)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        return env

    def git(self, directory: Path, *arguments, check_exit=True):
        completed = subprocess.run(["git", "-C", str(directory), *arguments],
                                   env=self.environment(), capture_output=True, text=True,
                                   timeout=60)
        if check_exit and completed.returncode != 0:
            raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
        return completed.stdout.strip()

    def commit(self, directory: Path, name: str, message: str):
        (directory / name).write_text(message + "\n")
        self.git(directory, "add", name)
        self.git(directory, "commit", "--quiet", "-m", message)

    def advance_main(self):
        self.git(self.clone, "switch", "--quiet", "main")
        self.git(self.clone, "pull", "--quiet", "--ff-only", "origin", "main")
        self.commit(self.clone, "main-moves.txt", "Main moves on")
        self.git(self.clone, "push", "--quiet", "origin", "main")

    def seat_home(self, name: str, own_commits: int, recorded: bool) -> Path:
        home = self.agents_root / name
        self.git(self.clone, "worktree", "add", "--quiet", "-b", name, str(home), "origin/main")
        for number in range(own_commits):
            self.commit(home, f"{name}-{number}.txt", f"{name} own commit {number}")
        if recorded:
            (self.handoffs / f"{name}-supervisor-state.json").write_text("{}\n")
        return home

    def run(self):
        return subprocess.run([sys.executable, str(PROGRAM), "--agents-root", str(self.agents_root),
                               "--handoff-directory", str(self.handoffs)],
                              env=self.environment(), capture_output=True, text=True, timeout=300)

    def origin_branches(self):
        return set(self.git(self.origin, "for-each-ref", "--format=%(refname:short)",
                            "refs/heads").split())

    def is_moved_and_marked(self, home: Path) -> bool:
        head = self.git(home, "rev-parse", "HEAD")
        main = self.git(home, "rev-parse", "origin/main")
        detached = self.git(home, "symbolic-ref", "-q", "HEAD", check_exit=False) == ""
        marker = Path(self.git(home, "rev-parse", "--absolute-git-dir")) / "agent-home-marker"
        return head == main and detached and marker.is_file()


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        fleet = Fleet(Path(temporary))
        alpha = fleet.seat_home("alpha", own_commits=2, recorded=True)
        alpha_tip = fleet.git(alpha, "rev-parse", "HEAD")
        beta = fleet.seat_home("beta", own_commits=0, recorded=False)
        (beta / "base.txt").write_text("changed, not committed\n")
        gamma = fleet.seat_home("gamma", own_commits=1, recorded=True)
        fleet.git(fleet.clone, "push", "--quiet", "origin",
                  f"main:refs/heads/gamma-seat-branch-commits-saved-{TODAY}")
        delta = fleet.seat_home("delta", own_commits=1, recorded=True)
        hooks = fleet.origin / "hooks"
        (hooks / "pre-receive").write_text(
            "#!/bin/sh\nwhile read old new ref; do\n"
            "  case \"$ref\" in *delta*) echo 'refusing delta' >&2; exit 1 ;; esac\n"
            "done\nexit 0\n")
        (hooks / "pre-receive").chmod(0o755)
        epsilon = fleet.seat_home("epsilon", own_commits=0, recorded=True)
        fleet.git(epsilon, "checkout", "--quiet", "--detach")
        fleet.commit(epsilon, "orphan.txt", "A commit on no branch")
        theta = fleet.seat_home("theta", own_commits=1, recorded=True)
        fleet.git(theta, "push", "--quiet", "origin", "HEAD:refs/heads/theta-closed-pull-request")
        fleet.git(fleet.clone, "fetch", "--quiet", "origin")
        fleet.git(fleet.origin, "update-ref", "-d", "refs/heads/theta-closed-pull-request")
        iota = fleet.seat_home("iota", own_commits=1, recorded=True)
        fleet.git(fleet.clone, "update-ref", "refs/remotes/backup/iota",
                  fleet.git(iota, "rev-parse", "HEAD"))
        kappa = fleet.seat_home("kappa", own_commits=0, recorded=True)
        fleet.git(kappa, "bisect", "start")
        topic = fleet.agents_root / "alpha-topic-worktree"
        fleet.git(fleet.clone, "worktree", "add", "--quiet", "-b", "some-topic", str(topic),
                  "origin/main")
        fleet.advance_main()

        first = fleet.run()
        report = first.stdout + first.stderr
        branches = fleet.origin_branches()
        check("a seat-branch's own commits are pushed under the saved-branch name",
              f"alpha-seat-branch-commits-saved-{TODAY}" in branches
              and fleet.git(fleet.origin, "rev-parse",
                            f"alpha-seat-branch-commits-saved-{TODAY}") == alpha_tip, report)
        check("a clean agent-home ends detached at the new origin/main and marked",
              fleet.is_moved_and_marked(alpha), report)
        check("the seat-branch itself is kept",
              fleet.git(alpha, "rev-parse", "refs/heads/alpha") == alpha_tip, report)
        check("an agent-home on its seat-branch is found without a handoff record, and with "
              "uncommitted changes is left with its reason",
              not fleet.is_moved_and_marked(beta)
              and fleet.git(beta, "symbolic-ref", "--short", "HEAD") == "beta"
              and f"{beta}: left as it was, because git status lists 1 uncommitted change(s)"
              in report, report)
        check("a saved-branch name already on origin gets the next free number",
              f"gamma-seat-branch-commits-saved-{TODAY}-2" in branches
              and fleet.is_moved_and_marked(gamma), report)
        check("a failed push leaves the agent-home on its seat-branch and says so",
              not fleet.is_moved_and_marked(delta)
              and fleet.git(delta, "symbolic-ref", "--short", "HEAD") == "delta"
              and f"{delta}: left as it was, because saving its seat-branch failed" in report
              and "refusing delta" in report, report)
        check("commits whose only remote branch was deleted on origin, its remote-tracking ref "
              "left behind, are pushed under the saved-branch name",
              f"theta-seat-branch-commits-saved-{TODAY}" in branches
              and fleet.is_moved_and_marked(theta), report)
        check("commits held only by another remote's remote-tracking ref are pushed to origin",
              f"iota-seat-branch-commits-saved-{TODAY}" in branches
              and fleet.is_moved_and_marked(iota), report)
        check("an agent-home with a git operation in progress is left with its reason",
              not fleet.is_moved_and_marked(kappa)
              and fleet.git(kappa, "symbolic-ref", "--short", "HEAD") == "kappa"
              and f"{kappa}: left as it was, because a bisect is in progress" in report, report)
        check("a detached HEAD holding commits on no branch is left",
              not fleet.is_moved_and_marked(epsilon)
              and "commit(s) no branch holds" in report, report)
        check("a worktree under the agents root that is not an agent-home is not touched",
              fleet.git(topic, "symbolic-ref", "--short", "HEAD") == "some-topic"
              and str(topic) not in report, report)
        check("the run exits 1 when any agent-home was left, and says what to do",
              first.returncode == 1 and "run this program again" in report,
              f"exit {first.returncode}: {report}")

        (beta / "base.txt").write_text("First commit\n")
        fleet.git(beta, "checkout", "--quiet", "--", "base.txt")
        (hooks / "pre-receive").unlink()
        fleet.git(epsilon, "branch", "epsilon-kept-work")
        fleet.git(kappa, "bisect", "reset")
        second = fleet.run()
        branches_after = fleet.origin_branches()
        check("a second run pushes no seat-branch twice",
              f"alpha-seat-branch-commits-saved-{TODAY}-2" not in branches_after
              and f"gamma-seat-branch-commits-saved-{TODAY}-3" not in branches_after
              and "all already on a branch on origin" in second.stdout, second.stdout)
        check("a second run, with nothing left in the way, moves every agent-home and exits 0",
              second.returncode == 0
              and all(fleet.is_moved_and_marked(home)
                      for home in (alpha, beta, gamma, delta, epsilon, theta, iota, kappa)),
              f"exit {second.returncode}: {second.stdout}{second.stderr}")

        empty_root = Path(temporary) / "no-agents"
        empty_root.mkdir()
        (empty_root / "plain-directory-not-a-checkout").mkdir()
        none =subprocess.run([sys.executable, str(PROGRAM), "--agents-root", str(empty_root),
                               "--handoff-directory", str(fleet.handoffs)],
                              env=fleet.environment(), capture_output=True, text=True, timeout=60)
        check("an agents root with no agent-home is nothing to do",
              none.returncode == 0 and "no agent-home" in none.stdout, none.stdout + none.stderr)

    spec = importlib.util.spec_from_file_location("agent_home_migration", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    real_load_recover_crashed_seats = module.load_recover_crashed_seats

    def listing_fails():
        raise OSError("the seat list could not be read")
    module.load_recover_crashed_seats = listing_fails
    listing_error = io.StringIO()
    with contextlib.redirect_stderr(listing_error):
        exit_status = module.main(["--agents-root", "/nonexistent"])
    module.load_recover_crashed_seats = real_load_recover_crashed_seats
    check("when the agent-homes cannot be listed, the run moves nothing, names the agents root "
          "and exits 2",
          exit_status == 2 and "the agent-homes under /nonexistent could not be listed"
          in listing_error.getvalue(), f"{exit_status}: {listing_error.getvalue()}")

    with tempfile.TemporaryDirectory() as temporary:
        fleet = Fleet(Path(temporary))
        os.environ["GIT_CONFIG_GLOBAL"] = str(fleet.global_config)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        zeta = fleet.seat_home("zeta", own_commits=0, recorded=True)
        today = datetime.date.today()
        real_run = module.subprocess.run

        def run_that_times_out(*arguments, **options):
            raise subprocess.TimeoutExpired(arguments[0], 1)
        module.subprocess.run = run_that_times_out
        try:
            moved, line = module.move_agent_home(zeta, today)
        finally:
            module.subprocess.run = real_run
        check("a git step that cannot run leaves the agent-home and says which step",
              not moved and "saving its seat-branch failed: git fetch --quiet --prune origin"
              in line and "could not start or timed out" in line, line)

        for failure_name, failure in (
                ("times out", lambda command: subprocess.TimeoutExpired(command, 1)),
                ("cannot start", lambda command: FileNotFoundError(2, "no git", "git"))):
            def run_whose_checkout_question_fails(*arguments, **options):
                if "--show-toplevel" in arguments[0]:
                    raise failure(arguments[0])
                return real_run(*arguments, **options)
            module.subprocess.run = run_whose_checkout_question_fails
            try:
                exit_status = module.main(["--agents-root", str(fleet.agents_root),
                                           "--handoff-directory", str(fleet.handoffs)])
            finally:
                module.subprocess.run = real_run
            check(f"when git, asked whether a directory is a checkout, {failure_name}, the run "
                  "moves nothing and exits 2",
                  exit_status == 2 and not fleet.is_moved_and_marked(zeta), str(exit_status))

        real_git = module.git

        def git_whose_checkout_fails(directory, *arguments, **options):
            if arguments[:1] == ("checkout",):
                raise module.GitStepFailed("git checkout failed in the test")
            return real_git(directory, *arguments, **options)
        module.git = git_whose_checkout_fails
        try:
            moved, line = module.move_agent_home(zeta, today)
        finally:
            module.git = real_git
        check("a failed detach leaves the agent-home on its seat-branch and says so",
              not moved and "not moved: git checkout failed in the test" in line
              and fleet.git(zeta, "symbolic-ref", "--short", "HEAD") == "zeta", line)

        eta = fleet.seat_home("eta", own_commits=0, recorded=False)
        real_output = module.output

        def output_naming_a_missing_git_directory(directory, *arguments, **options):
            if arguments == ("rev-parse", "--absolute-git-dir"):
                return str(Path(temporary) / "missing" / "git-directory")
            return real_output(directory, *arguments, **options)
        module.output = output_naming_a_missing_git_directory
        try:
            moved, line = module.move_agent_home(eta, today)
        finally:
            module.output = real_output
        check("a marker that cannot be written is reported, and the agent-home stays on its "
              "seat-branch",
              not moved and "not moved:" in line and "No such file" in line
              and fleet.git(eta, "symbolic-ref", "--short", "HEAD") == "eta", line)

        # An ignored directory at a path main newly tracks: without --no-overwrite-ignore,
        # git checkout replaces its file with main's, and the only copy is lost.
        iota = fleet.seat_home("iota", own_commits=0, recorded=False)
        fleet.git(fleet.clone, "switch", "--quiet", "main")
        fleet.git(fleet.clone, "pull", "--quiet", "--ff-only", "origin", "main")
        (fleet.clone / "ignored-here").mkdir()
        fleet.commit(fleet.clone, "ignored-here/notes.txt", "Main tracks a file iota ignores")
        fleet.git(fleet.clone, "push", "--quiet", "origin", "main")
        (iota / "ignored-here").mkdir()
        (iota / "ignored-here" / ".gitignore").write_text("*\n")
        (iota / "ignored-here" / "notes.txt").write_text("the only copy\n")
        moved, line = module.move_agent_home(iota, today)
        check("a detach over an ignored file at a path main tracks is refused, naming the file, "
              "and the agent-home stays on its seat-branch with the file intact",
              not moved and "not moved:" in line and "ignored-here/notes.txt" in line
              and fleet.git(iota, "symbolic-ref", "--short", "HEAD") == "iota"
              and (iota / "ignored-here" / "notes.txt").read_text() == "the only copy\n", line)
        shutil.rmtree(iota / "ignored-here")

        exit_status = module.main(["--agents-root", str(fleet.agents_root),
                                   "--handoff-directory", str(fleet.handoffs)])
        check("a rerun after a failed marker or detach finds each agent-home, even one with no "
              "handoff record, and moves and marks it",
              exit_status == 0 and fleet.is_moved_and_marked(eta)
              and fleet.is_moved_and_marked(zeta), str(exit_status))

    print(f"\n{len(failures)} failure(s)" if failures else "\nall cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
