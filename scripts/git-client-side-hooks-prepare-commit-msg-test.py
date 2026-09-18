#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/prepare-commit-msg, the hook that
stamps the Claude-Session trailer.

Run: python3 scripts/git-client-side-hooks-prepare-commit-msg-test.py
Prints one line per case and exits non-zero if any case fails. Every case
commits with real git in throwaway repositories under a temporary directory,
with core.hooksPath pointed at this checkout's copy of the hook directory,
so each case exercises exactly what git runs on a seat's commit.

The session id is always a fake one injected here, never inherited: the
seat running these tests has its own CLAUDE_CODE_BRIDGE_SESSION_ID, and the
unset cases must not see it.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_DIRECTORY = Path(__file__).resolve().with_name("git-client-side-hooks")
HOOK_SCRIPT = HOOK_DIRECTORY / "prepare-commit-msg"
SESSION_VARIABLE = "CLAUDE_CODE_BRIDGE_SESSION_ID"
FAKE_SESSION = "session_0FakeTestSessionAAAAAAAA"
OTHER_FAKE_SESSION = "session_0FakeTestSessionBBBBBBBB"
CO_AUTHOR_LINE = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def url(session_id):
    return f"https://claude.ai/code/{session_id}"


def session_line(session_id):
    return f"Claude-Session: {url(session_id)}"


class ThrowawayRepository:
    """One repository on main with one commit, wired to the hook under test.

    Global and system git config are shut out, so neither the machine's
    config nor its own core.hooksPath can change what a case sees.
    """

    def __init__(self, parent: Path, name: str):
        self.root = parent / name
        self.root.mkdir()
        self.empty_global_config = parent / f"{name}-empty-gitconfig"
        self.empty_global_config.write_text("")
        self.git(None, "init", "--quiet", "--initial-branch=main")
        self.git(None, "config", "user.name", "Hook Test")
        self.git(None, "config", "user.email", "hook-test@example.invalid")
        self.git(None, "config", "core.hooksPath", str(HOOK_DIRECTORY))
        self.write_and_commit(None, "base.txt", "base\n", "Base commit")

    def environment(self, session_id):
        env = dict(os.environ)
        env.pop(SESSION_VARIABLE, None)
        if session_id is not None:
            env[SESSION_VARIABLE] = session_id
        env["GIT_CONFIG_GLOBAL"] = str(self.empty_global_config)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        return env

    def git(self, session_id, *arguments, cwd=None):
        completed = subprocess.run(
            ["git", *arguments], cwd=str(cwd or self.root),
            env=self.environment(session_id),
            capture_output=True, text=True, timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
        return completed

    def write_and_commit(self, session_id, filename, content, message, cwd=None):
        work_tree = cwd or self.root
        (work_tree / filename).write_text(content)
        self.git(session_id, "add", filename, cwd=work_tree)
        completed = subprocess.run(
            ["git", "commit", "--quiet", "--file", "-"], cwd=str(work_tree),
            env=self.environment(session_id), input=message,
            capture_output=True, text=True, timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"commit failed: {completed.stderr.strip()}")

    def message(self, revision="HEAD", cwd=None):
        return self.git(None, "log", "-1", "--format=%B", revision,
                        cwd=cwd).stdout.rstrip("\n")

    def session_trailers(self, revision="HEAD", cwd=None):
        """The Claude-Session values git itself parses out of the trailer
        block, so a line sitting in the body rather than the block does not
        count."""
        output = self.git(
            None, "log", "-1",
            "--format=%(trailers:key=Claude-Session,valueonly)", revision,
            cwd=cwd).stdout
        return [line for line in output.splitlines() if line.strip()]


def attempt_commit(repository, session_id, message, *commit_options):
    """Stage a file and try to commit it with the message, returning the
    completed process rather than raising, for cases where git must refuse."""
    (repository.root / "a.txt").write_text("a\n")
    repository.git(None, "add", "a.txt")
    return subprocess.run(
        ["git", "commit", "--quiet", *commit_options, "--file", "-"],
        cwd=str(repository.root), env=repository.environment(session_id),
        input=message, capture_output=True, text=True, timeout=30,
    )


def run_cases(scratch: Path):
    # --- The variable decides -------------------------------------------

    repository = ThrowawayRepository(scratch, "set")
    repository.write_and_commit(FAKE_SESSION, "a.txt", "a\n", "Add a")
    check("a session with a link gets its trailer",
          repository.session_trailers() == [url(FAKE_SESSION)],
          repr(repository.message()))
    check("the trailer is the message's last line, after a blank line",
          repository.message() == f"Add a\n\n{session_line(FAKE_SESSION)}",
          repr(repository.message()))

    repository = ThrowawayRepository(scratch, "unset")
    repository.write_and_commit(None, "a.txt", "a\n", "Add a\n\nBody line.\n")
    check("a session with no link gets no trailer",
          repository.session_trailers() == [], repr(repository.message()))
    check("with no variable the message is left exactly as written",
          repository.message() == "Add a\n\nBody line.",
          repr(repository.message()))

    repository = ThrowawayRepository(scratch, "empty")
    repository.write_and_commit("", "a.txt", "a\n", "Add a")
    check("an empty variable counts as no link",
          repository.message() == "Add a", repr(repository.message()))

    # --- The agent already wrote attribution ----------------------------

    repository = ThrowawayRepository(scratch, "already-stamped")
    written = f"Add a\n\n{CO_AUTHOR_LINE}\n{session_line(FAKE_SESSION)}\n"
    repository.write_and_commit(FAKE_SESSION, "a.txt", "a\n", written)
    check("a message already carrying this session's line keeps exactly one",
          repository.session_trailers() == [url(FAKE_SESSION)],
          repr(repository.message()))
    check("and is otherwise unchanged",
          repository.message() == written.rstrip("\n"),
          repr(repository.message()))

    repository = ThrowawayRepository(scratch, "co-author-only")
    repository.write_and_commit(
        FAKE_SESSION, "a.txt", "a\n", f"Add a\n\n{CO_AUTHOR_LINE}\n")
    check("the line joins an existing trailer block, beneath Co-Authored-By",
          repository.message()
          == f"Add a\n\n{CO_AUTHOR_LINE}\n{session_line(FAKE_SESSION)}",
          repr(repository.message()))

    # interpret-trailers reads a "---" line as the start of a patch unless
    # told not to, and would put the line above it, mid-body. This
    # project's messages quote markdown rules and frontmatter fences.
    repository = ThrowawayRepository(scratch, "markdown-rule")
    repository.write_and_commit(
        FAKE_SESSION, "a.txt", "a\n", "Add a\n\nBefore\n---\nAfter\n")
    check("a --- line in the body does not pull the line above it",
          repository.message()
          == f"Add a\n\nBefore\n---\nAfter\n\n{session_line(FAKE_SESSION)}"
          and repository.session_trailers() == [url(FAKE_SESSION)],
          repr(repository.message()))

    # --- An empty message stays empty -----------------------------------

    # git refuses a commit whose message has no content of its own; the
    # trailer must not supply that content.
    repository = ThrowawayRepository(scratch, "empty-message")
    head_before = repository.git(None, "rev-parse", "HEAD").stdout.strip()
    completed = attempt_commit(repository, FAKE_SESSION, "")
    check("an empty message is still refused",
          completed.returncode != 0,
          f"exit 0, message {repository.message()!r}")
    check("and leaves HEAD where it was",
          repository.git(None, "rev-parse", "HEAD").stdout.strip() == head_before,
          repr(repository.message()))

    # The template git opens in an editor is all comment lines, and an edited
    # message is cleaned with strip, which drops them; --cleanup=strip stands
    # in for the editor here, since --file alone keeps comment lines as text.
    repository = ThrowawayRepository(scratch, "comment-only-message")
    head_before = repository.git(None, "rev-parse", "HEAD").stdout.strip()
    completed = attempt_commit(repository, FAKE_SESSION, "# comment only\n",
                               "--cleanup=strip")
    check("a message of only comment lines is still refused",
          completed.returncode != 0,
          f"exit 0, message {repository.message()!r}")
    check("and leaves HEAD where it was",
          repository.git(None, "rev-parse", "HEAD").stdout.strip() == head_before,
          repr(repository.message()))

    # --- Commits git makes itself ---------------------------------------

    repository = ThrowawayRepository(scratch, "merge")
    repository.git(None, "switch", "--quiet", "-c", "topic")
    repository.write_and_commit(None, "topic.txt", "t\n", "Topic work")
    repository.git(None, "switch", "--quiet", "main")
    repository.write_and_commit(None, "main.txt", "m\n", "Main work")
    repository.git(FAKE_SESSION, "merge", "--quiet", "--no-ff", "--no-edit", "topic")
    parents = repository.git(None, "log", "-1", "--format=%P").stdout.split()
    check("a merge commit is stamped",
          len(parents) == 2
          and repository.session_trailers() == [url(FAKE_SESSION)],
          f"parents={parents} message={repository.message()!r}")

    repository = ThrowawayRepository(scratch, "amend-same-session")
    repository.write_and_commit(FAKE_SESSION, "a.txt", "a\n", "Add a")
    repository.git(FAKE_SESSION, "commit", "--quiet", "--amend", "--no-edit")
    check("amending in the same session keeps exactly one line",
          repository.session_trailers() == [url(FAKE_SESSION)],
          repr(repository.message()))

    # Chosen, not accidental: a commit re-made by a second session records
    # both, the first session's line first, as Co-Authored-By lines do.
    repository = ThrowawayRepository(scratch, "amend-other-session")
    repository.write_and_commit(FAKE_SESSION, "a.txt", "a\n", "Add a")
    repository.git(OTHER_FAKE_SESSION, "commit", "--quiet", "--amend", "--no-edit")
    check("amending in another session adds its line beneath the first",
          repository.session_trailers()
          == [url(FAKE_SESSION), url(OTHER_FAKE_SESSION)],
          repr(repository.message()))

    repository = ThrowawayRepository(scratch, "cherry-pick")
    repository.git(None, "switch", "--quiet", "-c", "topic")
    repository.write_and_commit(FAKE_SESSION, "topic.txt", "t\n", "Topic work")
    picked = repository.git(None, "rev-parse", "HEAD").stdout.strip()
    repository.git(None, "switch", "--quiet", "main")
    repository.git(OTHER_FAKE_SESSION, "cherry-pick", picked)
    check("a cherry-pick by another session adds its line beneath the first",
          repository.session_trailers()
          == [url(FAKE_SESSION), url(OTHER_FAKE_SESSION)],
          repr(repository.message()))

    # --- Where seats commit ---------------------------------------------

    # A seat commits in a linked worktree, which reads its clone's config.
    repository = ThrowawayRepository(scratch, "worktree")
    seat_worktree = scratch / "worktree-seat"
    repository.git(None, "worktree", "add", "--quiet", "-b", "seat",
                   str(seat_worktree))
    repository.write_and_commit(FAKE_SESSION, "seat.txt", "s\n", "Seat work",
                                cwd=seat_worktree)
    check("a commit in a linked worktree of the clone is stamped",
          repository.session_trailers(cwd=seat_worktree)
          == [url(FAKE_SESSION)],
          repr(repository.message(cwd=seat_worktree)))

    # --- Never blocks a commit ------------------------------------------

    missing_message_file = scratch / "no-such-message-file"
    env = ThrowawayRepository(scratch, "fail-open").environment(FAKE_SESSION)
    completed = subprocess.run(
        [str(HOOK_SCRIPT), str(missing_message_file), "message"],
        cwd=str(scratch / "fail-open"), env=env,
        capture_output=True, text=True, timeout=30,
    )
    check("a failed stamp exits 0, so the commit goes ahead",
          completed.returncode == 0,
          f"exit {completed.returncode}, stderr {completed.stderr!r}")
    check("and says so on stderr",
          "could not add the Claude-Session trailer" in completed.stderr,
          repr(completed.stderr))

    check("the hook is executable, or git would silently skip it",
          os.access(HOOK_SCRIPT, os.X_OK), str(HOOK_SCRIPT))


def main():
    scratch = Path(tempfile.mkdtemp(prefix="prepare-commit-msg-test-"))
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
