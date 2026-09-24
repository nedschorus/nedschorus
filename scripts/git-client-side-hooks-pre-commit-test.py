#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/pre-commit and pre-merge-commit,
the hooks that refuse an agent's commit made under the user's own address or
under the unconfigured-agent tripwire.

Run: python3 scripts/git-client-side-hooks-pre-commit-test.py
Prints one line per case and exits non-zero if any case fails. Every case
commits with real git in throwaway repositories under a temporary directory,
with core.hooksPath pointed at this checkout's copy of the hook directory,
so each case exercises exactly what git runs on a seat's commit.

Nothing is inherited that could decide a case. The seat running these tests
is itself a Claude session, with its own CLAUDE_CODE_SESSION_ID and
CLAUDE_CODE_BRIDGE_SESSION_ID, and once launched by a launcher that carries
the identity exports it has GIT_AUTHOR_* and GIT_COMMITTER_* too. All of
them are removed from every case's environment and put back only when the
case asks for them; global and system git config are shut out.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_DIRECTORY = Path(__file__).resolve().with_name("git-client-side-hooks")
SESSION_VARIABLES = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID")
IDENTITY_VARIABLES = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                      "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")
FAKE_SESSION = {"CLAUDE_CODE_SESSION_ID": "00000000-fake-4000-8000-00000000000b"}
SEAT_IDENTITY = {"GIT_AUTHOR_NAME": "seat-g",
                 "GIT_AUTHOR_EMAIL": "seat-g@nedschorus.invalid",
                 "GIT_COMMITTER_NAME": "seat-g",
                 "GIT_COMMITTER_EMAIL": "seat-g@nedschorus.invalid"}
TRIPWIRE_NAME = "unconfigured-agent"
TRIPWIRE_EMAIL = "unconfigured-agent@nedschorus.invalid"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class ThrowawayRepository:
    """One repository on main with one commit, wired to the hooks under test,
    its own config holding `config_name <config_email>` the way a clone's
    shared .git/config holds one identity for every worktree."""

    def __init__(self, parent: Path, name: str,
                 config_name="shared-config", config_email="shared-config@example.invalid"):
        self.root = parent / name
        self.root.mkdir()
        self.empty_global_config = parent / f"{name}-empty-gitconfig"
        self.empty_global_config.write_text("")
        self.git({}, "init", "--quiet", "--initial-branch=main")
        self.git({}, "config", "user.name", config_name)
        self.git({}, "config", "user.email", config_email)
        self.git({}, "config", "core.hooksPath", str(HOOK_DIRECTORY))
        (self.root / "base.txt").write_text("base\n")
        self.git({}, "add", "base.txt")
        self.git({}, "commit", "--quiet", "-m", "Base commit")

    def environment(self, extra):
        env = {key: value for key, value in os.environ.items()
               if key not in SESSION_VARIABLES and key not in IDENTITY_VARIABLES}
        env["GIT_CONFIG_GLOBAL"] = str(self.empty_global_config)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env.update(extra)
        return env

    def git(self, extra, *arguments):
        completed = subprocess.run(
            ["git", *arguments], cwd=str(self.root), env=self.environment(extra),
            capture_output=True, text=True, timeout=30)
        if completed.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
        return completed

    def attempt(self, extra, *arguments):
        """Run git and return the completed process, for cases where git
        must refuse."""
        return subprocess.run(
            ["git", *arguments], cwd=str(self.root), env=self.environment(extra),
            capture_output=True, text=True, timeout=30)

    def attempt_commit(self, extra, filename="a.txt", *commit_options):
        with open(self.root / filename, "a") as handle:
            handle.write("line\n")
        self.git({}, "add", filename)
        return self.attempt(extra, "commit", "--quiet", "-m", "A change",
                            *commit_options)

    def head(self):
        return self.git({}, "rev-parse", "HEAD").stdout.strip()

    def head_author_and_committer(self):
        return self.git({}, "log", "-1", "--format=%an <%ae>|%cn <%ce>").stdout.strip()


REFUSAL_FIRST_INSTRUCTION = "Commit under this seat's own name, not as "


def refused(completed):
    return (completed.returncode != 0
            and REFUSAL_FIRST_INSTRUCTION in completed.stderr)


def run_cases(scratch: Path):
    # --- The hooks git will run are executable: git skips a hook file that
    # is not, silently, and the guard would then guard nothing. -----------
    for hook_name in ("pre-commit", "pre-merge-commit"):
        check(f"{hook_name} is executable",
              os.access(HOOK_DIRECTORY / hook_name, os.X_OK),
              str(HOOK_DIRECTORY / hook_name))

    # --- A seat's own identity commits. --------------------------------
    repository = ThrowawayRepository(scratch, "seat-identity")
    before = repository.head()
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("a session committing under its seat identity commits",
          completed.returncode == 0 and repository.head() != before,
          completed.stderr.strip())

    # --- Each of the user's own addresses is refused, as author. ------
    for address in ("junk@lerner1.com", "ned@lerner1.com", "nedlerner@yahoo.com"):
        repository = ThrowawayRepository(scratch, f"author-{address}")
        before = repository.head()
        completed = repository.attempt_commit(
            FAKE_SESSION, "a.txt", f"--author=Edward Lerner <{address}>")
        check(f"a session's commit authored by {address} is refused",
              refused(completed) and repository.head() == before,
              (completed.returncode, completed.stderr.strip()))

    # --- The committer is checked as well as the author: the author can
    # be right while the committer comes from a config that leaks. ------
    repository = ThrowawayRepository(scratch, "committer")
    before = repository.head()
    completed = repository.attempt_commit(
        {**FAKE_SESSION, "GIT_AUTHOR_NAME": "seat-g",
         "GIT_AUTHOR_EMAIL": "seat-g@nedschorus.invalid",
         "GIT_COMMITTER_EMAIL": "junk@lerner1.com"})
    check("a session's commit whose COMMITTER is the user's address is refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- The shared config's identity is what a session launched without
    # the launcher commits under; the 2026-09-22 leak was exactly this. --
    repository = ThrowawayRepository(scratch, "config-leak",
                                     config_name="identity-probe",
                                     config_email="junk@lerner1.com")
    before = repository.head()
    completed = repository.attempt_commit(FAKE_SESSION)
    check("a session committing under a shared config holding the user's address is refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- The tripwire: refused when a session falls through to it, and
    # outranked by the launcher's environment when the seat is launched. -
    repository = ThrowawayRepository(scratch, "tripwire",
                                     config_name=TRIPWIRE_NAME,
                                     config_email=TRIPWIRE_EMAIL)
    before = repository.head()
    completed = repository.attempt_commit(FAKE_SESSION)
    check("a session with no launcher identity is stopped at the tripwire",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("under the tripwire, a launched seat commits under its own name",
          completed.returncode == 0
          and repository.head_author_and_committer()
          == "seat-g <seat-g@nedschorus.invalid>|seat-g <seat-g@nedschorus.invalid>",
          (completed.stderr.strip(), repository.head_author_and_committer()))

    # --- A per-command -c override is config too, and is checked. This is
    # the exact form merge-lane used on 2026-09-22, which until this case
    # only a one-off probe verified (merge-lane-2's review of PR "Each seat
    # commits under its own name, and no agent commits as the user"). ----
    for address in ("junk@lerner1.com", "ned@lerner1.com"):
        repository = ThrowawayRepository(scratch, f"dash-c-{address}")
        before = repository.head()
        with open(repository.root / "a.txt", "a") as handle:
            handle.write("line\n")
        repository.git({}, "add", "a.txt")
        completed = repository.attempt(
            FAKE_SESSION, "-c", f"user.email={address}", "-c", "user.name=Edward Lerner",
            "commit", "--quiet", "-m", "A change")
        check(f"a session's `git -c user.email={address} commit` is refused",
              refused(completed) and repository.head() == before,
              (completed.returncode, completed.stderr.strip()))

    # --- The address match ignores case: git keeps an email as typed. -
    repository = ThrowawayRepository(scratch, "case")
    before = repository.head()
    completed = repository.attempt_commit(
        FAKE_SESSION, "a.txt", "--author=Edward Lerner <JUNK@Lerner1.COM>")
    check("the user's address in another case is still refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- Either session variable makes it a session's commit. ---------
    repository = ThrowawayRepository(scratch, "bridge-only")
    before = repository.head()
    completed = repository.attempt_commit(
        {"CLAUDE_CODE_BRIDGE_SESSION_ID": "session_0FakeTestSessionCCCCCCCC"},
        "a.txt", "--author=Edward Lerner <junk@lerner1.com>")
    check("a session known only by its bridge id is checked too",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- Outside any session the user's own commit is his. ------------
    repository = ThrowawayRepository(scratch, "no-session")
    before = repository.head()
    completed = repository.attempt_commit(
        {}, "a.txt", "--author=Edward Lerner <junk@lerner1.com>")
    check("a commit made outside any Claude session is not checked",
          completed.returncode == 0 and repository.head() != before,
          completed.stderr.strip())
    completed = repository.attempt_commit({"CLAUDE_CODE_SESSION_ID": ""},
                                          "a.txt",
                                          "--author=Edward Lerner <junk@lerner1.com>")
    check("an empty session variable counts as no session",
          completed.returncode == 0, completed.stderr.strip())

    # --- An amend is a commit, and is checked. -------------------------
    repository = ThrowawayRepository(scratch, "amend")
    repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    before = repository.head()
    completed = repository.attempt(
        FAKE_SESSION, "commit", "--quiet", "--amend", "--no-edit",
        "--author=Edward Lerner <junk@lerner1.com>")
    check("an amend authored by the user's address is refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- A merge commit runs pre-merge-commit, which runs the same check.
    repository = ThrowawayRepository(scratch, "merge")
    repository.git({}, "checkout", "--quiet", "-b", "side")
    repository.attempt_commit({}, "side.txt")
    repository.git({}, "checkout", "--quiet", "main")
    repository.attempt_commit({}, "main.txt")
    before = repository.head()
    completed = repository.attempt(
        {**FAKE_SESSION, "GIT_AUTHOR_EMAIL": "ned@lerner1.com"},
        "merge", "--quiet", "--no-ff", "-m", "Merge side", "side")
    check("a session's merge commit authored by the user's address is refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))
    repository.attempt({}, "merge", "--abort")
    completed = repository.attempt(
        {**FAKE_SESSION, **SEAT_IDENTITY},
        "merge", "--quiet", "--no-ff", "-m", "Merge side", "side")
    check("a session's merge commit under its seat identity merges",
          completed.returncode == 0 and repository.head() != before,
          completed.stderr.strip())

    # --- The refusal is instruction: it names the fix and the launchers. -
    repository = ThrowawayRepository(scratch, "message")
    completed = repository.attempt_commit(
        FAKE_SESSION, "a.txt", "--author=Edward Lerner <junk@lerner1.com>")
    check("the refusal names the identity it refused",
          "Edward Lerner <junk@lerner1.com>" in completed.stderr,
          completed.stderr)
    check("the refusal says to relaunch with a launcher",
          "launch-claude-mac" in completed.stderr
          and "launch-claude-ubuntu" in completed.stderr, completed.stderr)
    check("the refusal says not to change the shared config",
          "Do not change user.name or user.email" in completed.stderr,
          completed.stderr)
    check("the refusal says to set the identity in the same command as the commit",
          "in the same command as the commit" in completed.stderr
          and "GIT_COMMITTER_EMAIL=<seat>@nedschorus.invalid git commit"
          in completed.stderr, completed.stderr)
    check("the refusal tells a user committing by hand to use a terminal outside the session",
          "If the user is committing by hand, commit from a terminal outside"
          " the Claude session." in completed.stderr, completed.stderr)
    # Instruction only (CLAUDE.md): every line is an instruction, or an
    # instruction under a stated condition, never a status or a reason.
    refusal_lines = [line for line in completed.stderr.splitlines() if line.strip()]
    check("every refusal line is an instruction",
          bool(refusal_lines) and all(
              line.startswith(("Commit ", "If ", "Do not "))
              for line in refusal_lines),
          refusal_lines)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="pre-commit-hook-test-"))
    try:
        run_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
