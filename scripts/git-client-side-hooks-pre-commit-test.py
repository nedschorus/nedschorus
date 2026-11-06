#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/pre-commit and pre-merge-commit,
the hooks that refuse an agent's commit made under the user's own address or
under the unconfigured-agent tripwire, and that keep the tripwire in the
clone's own config: writing it back when another identity replaced it, and
refusing a commit in a clone that holds no identity.

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

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

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
    shared .git/config holds one identity for every worktree: the tripwire
    unless a case says otherwise, and no identity at all when a case passes
    None for both."""

    def __init__(self, parent: Path, name: str,
                 config_name=TRIPWIRE_NAME, config_email=TRIPWIRE_EMAIL):
        self.root = parent / name
        self.root.mkdir()
        self.empty_global_config = parent / f"{name}-empty-gitconfig"
        self.empty_global_config.write_text("")
        self.git({}, "init", "--quiet", "--initial-branch=main")
        (self.root / "base.txt").write_text("base\n")
        self.git({}, "add", "base.txt")
        self.git({}, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--quiet", "-m", "Base commit")
        if config_name is not None:
            self.git({}, "config", "user.name", config_name)
        if config_email is not None:
            self.git({}, "config", "user.email", config_email)
        self.git({}, "config", "core.hooksPath", str(HOOK_DIRECTORY))

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

    def local_identity(self):
        """The clone's own user.name and user.email, None for an unset key."""
        values = []
        for key in ("user.name", "user.email"):
            completed = self.attempt({}, "config", "--local", "--get", key)
            values.append(completed.stdout.strip() if completed.returncode == 0 else None)
        return tuple(values)


REFUSAL_FIRST_INSTRUCTION = "Commit under this seat's own name, not as "

# The whole refusal, line for line, with the refused identity as {identity}.
# The first line says what was refused and why; every other line is an
# instruction, or an instruction under a stated condition.
EXPECTED_REFUSAL_LINES = [
    "pre-commit: this commit is refused, because its author or committer is"
    " {identity}: an agent's commit must not carry the user's own address,"
    " which a pushed commit publishes, or the unconfigured-agent address, which"
    " marks an agent-session started without its launcher.",
    "Commit under this seat's own name, not as {identity}.",
    "If this session is a seat, relaunch it with launch-claude-mac or"
    " launch-claude-ubuntu, then commit again.",
    "If you cannot relaunch, set the identity in the same command as the"
    " commit: GIT_AUTHOR_NAME=<seat> GIT_AUTHOR_EMAIL=<seat>@nedschorus.invalid"
    " GIT_COMMITTER_NAME=<seat> GIT_COMMITTER_EMAIL=<seat>@nedschorus.invalid"
    " git commit ...",
    "If you are amending a commit made under the user's address by mistake,"
    " add --reset-author to that same command.",
    "If you are amending a commit the user wrote, leave it and make a new"
    " commit on top instead.",
    "Do not change user.name or user.email in git config: every worktree of"
    " the clone shares that config, and a launched agent-seat's commits keep"
    " its own name either way, but an agent-session started without its"
    " launcher could then commit under the new identity.",
    "If the user is committing by hand, commit from a terminal outside the"
    " Claude session, adding -c user.name=<name> -c user.email=<address> after"
    " git if the clone's identity is unconfigured-agent.",
]


def refused(completed):
    return (completed.returncode != 0
            and REFUSAL_FIRST_INSTRUCTION in completed.stderr)


WRITTEN_BACK_OPENING = "pre-commit: this commit is refused, because the clone's own git config, "
WRITTEN_BACK_CLOSING = "; this hook has written unconfigured-agent back."
NO_IDENTITY_MARK = "holds no user.name or user.email"


def refused_and_written_back(completed):
    return (completed.returncode != 0 and WRITTEN_BACK_OPENING in completed.stderr
            and WRITTEN_BACK_CLOSING in completed.stderr)


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
          refused_and_written_back(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))

    # --- The clone's own identity, replaced by an agent's `git config
    # user.name`: written back, the commit refused, and the next commit of a
    # launched seat goes through. ----------------------------------------
    repository = ThrowawayRepository(scratch, "replaced-identity",
                                     config_name="prime-intellect",
                                     config_email="prime-intellect@nedschorus.invalid")
    before = repository.head()
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("a replaced clone identity refuses even a launched seat's commit",
          refused_and_written_back(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))
    check("a replaced clone identity is written back to the tripwire",
          repository.local_identity() == (TRIPWIRE_NAME, TRIPWIRE_EMAIL),
          repository.local_identity())
    check("the written-back refusal names the identity it found",
          "held the identity prime-intellect <prime-intellect@nedschorus.invalid> instead of"
          in completed.stderr, completed.stderr)
    check("the written-back refusal says to tell the user, then commit again",
          "Tell the user that " in completed.stderr
          and "Then commit again." in completed.stderr, completed.stderr)
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("after the write-back, the launched seat's next commit goes through",
          completed.returncode == 0 and repository.head() != before,
          completed.stderr.strip())

    # --- Only one key replaced counts as replaced. ------------------------
    repository = ThrowawayRepository(scratch, "replaced-email-only",
                                     config_email="someone@nedschorus.invalid")
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("a clone identity with only its email replaced is written back and refused",
          refused_and_written_back(completed)
          and repository.local_identity() == (TRIPWIRE_NAME, TRIPWIRE_EMAIL),
          (completed.stderr.strip(), repository.local_identity()))

    # --- One key unset is a replaced identity, not a new clone: an agent's
    # `git config --unset user.email` is written back too. -----------------
    repository = ThrowawayRepository(scratch, "email-unset-only", config_email=None)
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("a clone identity with only its email unset is written back and refused",
          refused_and_written_back(completed)
          and repository.local_identity() == (TRIPWIRE_NAME, TRIPWIRE_EMAIL),
          (completed.stderr.strip(), repository.local_identity()))

    # --- A clone with no identity: refused, nothing written, and the two
    # commands for the user printed. ----------------------------------------
    repository = ThrowawayRepository(scratch, "no-identity",
                                     config_name=None, config_email=None)
    before = repository.head()
    completed = repository.attempt_commit({**FAKE_SESSION, **SEAT_IDENTITY})
    check("a clone holding no identity refuses the commit",
          completed.returncode != 0 and NO_IDENTITY_MARK in completed.stderr
          and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))
    check("a clone holding no identity is left with none written",
          repository.local_identity() == (None, None), repository.local_identity())
    check("the no-identity refusal prints the user's two commands",
          "config user.name unconfigured-agent" in completed.stderr
          and "config user.email unconfigured-agent@nedschorus.invalid" in completed.stderr,
          completed.stderr)

    # --- A launched seat's commit with its own -c values: --local ignores
    # them, so the clone's tripwire is untouched and the commit goes through.
    repository = ThrowawayRepository(scratch, "launched-dash-c")
    before = repository.head()
    with open(repository.root / "a.txt", "a") as handle:
        handle.write("line\n")
    repository.git({}, "add", "a.txt")
    completed = repository.attempt(
        {**FAKE_SESSION, **SEAT_IDENTITY}, "-c", "user.name=seat-g",
        "-c", "user.email=seat-g@nedschorus.invalid", "commit", "--quiet", "-m", "A change")
    check("a launched seat's `git -c user.name=... commit` is not affected by the clone check",
          completed.returncode == 0 and repository.head() != before
          and repository.local_identity() == (TRIPWIRE_NAME, TRIPWIRE_EMAIL),
          (completed.stderr.strip(), repository.local_identity()))

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

    # --- Amending a commit that went out under the user's address. --amend
    # keeps the amended commit's author, so the refusal's same-command
    # identity alone is refused again, and adding --reset-author, as the
    # refusal's amend line says, commits as the seat (mac-claude's finding
    # in merge-lane-2's review 5298511609 of PR "The commit guard's refusal
    # is instructions only"). --------------------------------------------
    repository = ThrowawayRepository(scratch, "amend-user-authored")
    repository.attempt_commit({}, "a.txt", "--author=Edward Lerner <junk@lerner1.com>")
    with open(repository.root / "a.txt", "a") as handle:
        handle.write("more\n")
    repository.git({}, "add", "a.txt")
    before = repository.head()
    completed = repository.attempt(
        {**FAKE_SESSION, **SEAT_IDENTITY}, "commit", "--quiet", "--amend", "--no-edit")
    check("amending a user-authored commit under the same-command identity alone is refused",
          refused(completed) and repository.head() == before,
          (completed.returncode, completed.stderr.strip()))
    completed = repository.attempt(
        {**FAKE_SESSION, **SEAT_IDENTITY}, "commit", "--quiet", "--amend",
        "--no-edit", "--reset-author")
    check("adding --reset-author, as the refusal says, amends it under the seat's name",
          completed.returncode == 0
          and repository.head_author_and_committer()
          == "seat-g <seat-g@nedschorus.invalid>|seat-g <seat-g@nedschorus.invalid>",
          (completed.stderr.strip(), repository.head_author_and_committer()))

    # --- Outside a session, under the tripwire, the user's hand commit with
    # the -c form the refusal's last line gives carries his name as both
    # author and committer; without it, it would go out as the tripwire. -
    repository = ThrowawayRepository(scratch, "hand-commit-under-tripwire",
                                     config_name=TRIPWIRE_NAME,
                                     config_email=TRIPWIRE_EMAIL)
    with open(repository.root / "a.txt", "a") as handle:
        handle.write("line\n")
    repository.git({}, "add", "a.txt")
    completed = repository.attempt(
        {}, "-c", "user.name=Edward Lerner", "-c", "user.email=junk@lerner1.com",
        "commit", "--quiet", "-m", "A change")
    check("under the tripwire, the user's -c hand commit carries his name as author and committer",
          completed.returncode == 0
          and repository.head_author_and_committer()
          == "Edward Lerner <junk@lerner1.com>|Edward Lerner <junk@lerner1.com>",
          (completed.stderr.strip(), repository.head_author_and_committer()))

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
          " the Claude session" in completed.stderr, completed.stderr)
    check("the refusal tells a user committing by hand under the tripwire to pass -c",
          "adding -c user.name=<name> -c user.email=<address> after git if the"
          " clone's identity is unconfigured-agent." in completed.stderr,
          completed.stderr)
    check("the refusal says to add --reset-author when amending a mistaken commit",
          "If you are amending a commit made under the user's address by mistake,"
          " add --reset-author to that same command." in completed.stderr,
          completed.stderr)
    check("the refusal says to commit on top when amending a commit the user wrote",
          "If you are amending a commit the user wrote, leave it and make a new"
          " commit on top instead." in completed.stderr, completed.stderr)
    # The first line says what was refused; every later line opens as an
    # instruction ("Commit", "Do not") or as the condition an instruction
    # applies under ("If").
    refusal_lines = [line for line in completed.stderr.splitlines() if line.strip()]
    check("the refusal opens by saying the commit is refused",
          bool(refusal_lines)
          and refusal_lines[0].startswith("pre-commit: this commit is refused, because "),
          refusal_lines)
    check("every later refusal line is an instruction",
          len(refusal_lines) > 1 and all(
              line.startswith(("Commit ", "If ", "Do not "))
              for line in refusal_lines[1:]),
          refusal_lines)
    # The line-start checks cannot see a wording change inside a line, so the
    # refusal is pinned line for line.
    check("the refusal is exactly its lines, nothing appended",
          refusal_lines == [line.format(identity="Edward Lerner <junk@lerner1.com>")
                            for line in EXPECTED_REFUSAL_LINES],
          refusal_lines)

    # --- git var failing: the hook says the identity went unchecked. -----
    # Run directly, not by git commit, because git puts its own exec-path
    # ahead of PATH, which would hide the stand-in git.
    stand_in_directory = scratch / "stand-in-git"
    stand_in_directory.mkdir()
    real_git = shutil.which("git")
    stand_in = stand_in_directory / "git"
    stand_in.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = var ] && [ "$2" = GIT_AUTHOR_IDENT ]; then\n'
        '    echo "fatal: injected git var failure" >&2\n'
        "    exit 128\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n')
    stand_in.chmod(0o755)
    for label, committer_email, expect_refused in (
            ("a seat committer", "seat-g@nedschorus.invalid", False),
            ("the user's address as committer", "ned@lerner1.com", True)):
        repository = ThrowawayRepository(scratch, "git-var-fails-" + committer_email)
        environment = repository.environment({
            **FAKE_SESSION, **SEAT_IDENTITY, "GIT_COMMITTER_EMAIL": committer_email,
            "PATH": f"{stand_in_directory}{os.pathsep}{os.environ.get('PATH', '')}"})
        completed = subprocess.run(
            ["sh", str(HOOK_DIRECTORY / "pre-commit")], cwd=str(repository.root),
            env=environment, capture_output=True, text=True, timeout=30)
        check(f"when git var fails for the author, with {label}, the hook says the author "
              f"was not checked, shows git's error, and still checks the committer",
              "pre-commit: git var GIT_AUTHOR_IDENT failed, so this commit's author was not "
              "checked" in completed.stderr
              and "fatal: injected git var failure" in completed.stderr
              and (refused(completed) if expect_refused else completed.returncode == 0),
              (completed.returncode, completed.stderr))


def run_config_failure_cases(scratch: Path):
    """git config failing, read or write: the hook reports it and refuses.
    Run directly, not by git commit, for the reason the git var cases give."""
    stand_in_directory = scratch / "stand-in-git-config"
    stand_in_directory.mkdir()
    real_git = shutil.which("git")
    stand_in = stand_in_directory / "git"
    stand_in.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = config ] && [ "$2" = --local ] && [ "$3" = "$FAIL_CONFIG_ARGUMENT" ]; then\n'
        '    echo "fatal: injected git config failure" >&2\n'
        "    exit 128\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n')
    stand_in.chmod(0o755)
    for label, fail_argument, config_name, expected in (
            ("writing the tripwire back", "user.name", "prime-intellect",
             "and writing unconfigured-agent back failed"),
            ("reading user.name", "--get", TRIPWIRE_NAME,
             "because reading user.name from the clone's own git config")):
        repository = ThrowawayRepository(scratch, "config-fails-" + fail_argument.strip("-"),
                                         config_name=config_name)
        environment = repository.environment({
            **FAKE_SESSION, **SEAT_IDENTITY, "FAIL_CONFIG_ARGUMENT": fail_argument,
            "PATH": f"{stand_in_directory}{os.pathsep}{os.environ.get('PATH', '')}"})
        completed = subprocess.run(
            ["sh", str(HOOK_DIRECTORY / "pre-commit")], cwd=str(repository.root),
            env=environment, capture_output=True, text=True, timeout=30)
        check(f"when git config fails {label}, the hook says so, shows git's error, and refuses",
              completed.returncode != 0 and expected in completed.stderr
              and "fatal: injected git config failure" in completed.stderr,
              (completed.returncode, completed.stderr))


def main():
    scratch = Path(tempfile.mkdtemp(prefix="pre-commit-hook-test-"))
    try:
        run_cases(scratch)
        run_config_failure_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
