#!/usr/bin/env python3
"""Tests for .claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py.

Each case runs the hook as Claude Code runs it, a separate process fed a PostToolUse or
PostToolUseFailure payload, in a throwaway repository, with a stand-in home and a stand-in
store, so no real guarded file and no real log-store directory is touched.

Run: python3 .claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook-test.py
Prints one line per case and exits 1 if any case fails.
"""

import importlib.util
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[2] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK = Path(os.environ.get(
    "GUARDED_FILE_HOOK_PATH",
    Path(__file__).resolve().parent / "guarded-file-unapproved-change-afterward-backup-and-ask-hook.py"))
OBVIOUS_FIX = "Obvious fix under CLAUDE.md's standing approval: a typo in CLAUDE.md"

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


class World:
    """A throwaway home, store and repository; session names stand in for sessions."""

    def __init__(self, scratch: Path, machine="ned-box"):
        self.scratch = scratch
        self.extra_environment = {}
        self.home = scratch / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "CLAUDE.md").write_text("global v1\n")
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"model": "a", "hooks": {}}, indent=2))
        self.agents = scratch / "agents"
        self.agents.mkdir()
        self.store = scratch / "store" / machine
        self.store.mkdir(parents=True)
        self.machine = machine
        self.repo = scratch / "agents" / "seat"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "CLAUDE.md").write_text("project v1\n")
        (self.repo / "notes.txt").write_text("not guarded\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "start")

    def environment(self, owner="owner-a"):
        environment = dict(os.environ)
        environment.update({
            "HOME": str(self.home),
            "GUARDED_FILE_VERSIONS_STORE_DIRECTORY": str(self.store),
            "GUARDED_FILE_VERSIONS_MACHINE": self.machine,
            "GUARDED_FILE_VERSIONS_OUTSIDE_STATE_DIRECTORY": str(self.scratch / "cache"),
            "GUARDED_FILE_VERSIONS_AGENTS_DIRECTORY": str(self.agents),
            "GUARDED_FILE_VERSIONS_OWNER_KEY": owner,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null",
        })
        environment.update(self.extra_environment)
        return environment

    def git(self, *arguments, check_ok=True, cwd=None, input_text=None):
        result = subprocess.run(["git", "-C", str(cwd or self.repo), *arguments],
                                capture_output=True, text=True, env=self.environment(),
                                input=input_text)
        if check_ok and result.returncode:
            raise RuntimeError(f"git {arguments}: {result.stderr}")
        return result

    def call(self, change, tool="Bash", file_path=None, event="PostToolUse", **keywords):
        """One tool call as Claude Code makes it: the PreToolUse run, the change the call
        makes, then the run after the call, both with one tool_use_id."""
        self.calls = getattr(self, "calls", 0) + 1
        tool_use_id = f"toolu_test_{self.calls}"
        before = self.run(tool=tool, event="PreToolUse", file_path=file_path,
                          tool_use_id=tool_use_id, **keywords)
        if before:
            raise RuntimeError(f"the PreToolUse run spoke: {before}")
        change()
        return self.run(tool=tool, event=event, file_path=file_path, tool_use_id=tool_use_id,
                        **keywords)

    def text_key(self, text):
        return self.git("hash-object", "--stdin", input_text=text).stdout.strip()

    def run(self, session="session-a", owner="owner-a", tool="Bash", event="PostToolUse",
            file_path=None, cwd=None, tool_use_id=None):
        payload = {"session_id": session, "hook_event_name": event, "tool_name": tool,
                   "cwd": str(cwd or self.repo),
                   "tool_input": {"file_path": str(file_path)} if file_path else {"command": "x"}}
        if tool_use_id:
            payload["tool_use_id"] = tool_use_id
        started = time.monotonic()
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                capture_output=True, text=True, env=self.environment(owner),
                                cwd=str(cwd or self.repo), timeout=120)
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.last_seconds = time.monotonic() - started
        # The hook's own CPU time and that of the git processes it waited for.
        self.last_cpu_seconds = (cpu_after.ru_utime - cpu_before.ru_utime
                                 + cpu_after.ru_stime - cpu_before.ru_stime)
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(f"hook exited {result.returncode}: {result.stderr}")
        if not result.stdout.strip():
            return ""
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def command(self, mode, *pairs, owner="owner-a"):
        return subprocess.run([sys.executable, str(HOOK), mode, *map(str, pairs)],
                              capture_output=True, text=True, env=self.environment(owner),
                              cwd=str(self.repo), timeout=120)

    def key(self, path):
        return self.git("hash-object", str(path)).stdout.strip()

    def versions(self, path):
        directory = self.store / str(Path(path)).lstrip("/")
        return sorted(child.name for child in directory.iterdir()) if directory.is_dir() else []

    def store_file(self, path, name):
        target = self.store / str(Path(path)).lstrip("/") / name
        return target.read_text() if target.exists() else ""

    def git_holds(self, key):
        return self.git("cat-file", "-e", key, check_ok=False).returncode == 0

    def seen_in_log(self, path, key):
        return any(line.startswith("seen\t") and f"\t{key}\t" in line
                   for line in self.store_file(path, "log").splitlines())

    def failing_git(self, arguments):
        """Make every git whose command line holds arguments fail as a broken repository does,
        for the hook's runs and commands until failing_git(None)."""
        if arguments is None:
            self.extra_environment.pop("PATH", None)
            return
        directory = self.scratch / "failing-git"
        directory.mkdir(exist_ok=True)
        wrapper = directory / "git"
        wrapper.write_text(
            "#!/bin/sh\n"
            f"case \" $* \" in *\"{arguments}\"*) echo 'fatal: injected failure' >&2; exit 128;; esac\n"
            f"exec {shutil.which('git')} \"$@\"\n")
        wrapper.chmod(0o755)
        self.extra_environment["PATH"] = f"{directory}:{os.environ['PATH']}"

    def marker(self, text, before=None):
        marker = self.repo / ".walk-approved"
        marker.write_text(text)
        if before is not None:
            os.utime(marker, ns=(before, before))
        return marker


def fresh(scratch_root, name, machine="ned-box"):
    directory = Path(scratch_root) / name
    directory.mkdir()
    world = World(directory, machine)
    world.run()  # the first run stocks the machine and the checkout
    return world


STORE_CITATION = ("nedlern@ned-box:/home/nedlern/nedschorus-logs/"
                  "guarded-file-versions-and-approvals/ned-box")
V1 = "project v1\n"
V2 = "project v2 by shell\n"


def put_back_cases(scratch):
    # -- this tool call's unapproved change is put back, and can be reapplied once approved
    world = fresh(scratch, "put-back")
    claude = world.repo / "CLAUDE.md"
    approved_key, key = world.key(claude), world.text_key(V2)
    message = world.call(lambda: claude.write_text(V2))
    check("a shell edit this tool call made to a file whose earlier version was approved is put "
          "back", claude.read_text() == V1, claude.read_text())
    check("the put-back message names the approved version and where the unapproved one is kept",
          f"{claude}: put back the approved version {approved_key}" in message
          and f"{STORE_CITATION}{claude}/{key}" in message, message)
    check("the unapproved version is kept in the store and is not approved",
          key in world.versions(claude) and key not in world.store_file(claude, "approved"),
          world.versions(claude))
    check("the store's log records the put-back",
          any(line.startswith("restored\t") and key in line
              for line in world.store_file(claude, "log").splitlines()),
          world.store_file(claude, "log"))
    check("the put-back message tells a subagent to stop and report before any other step",
          0 <= message.find("If you are a subagent, stop: make no further edit")
          < message.find("If the change is still wanted"), message)
    check("the put-back message gives the command that reapplies the kept version",
          f"python3 {HOOK} --approve-and-reapply-kept-version {claude} {key}" in message, message)
    check("the run after the call removes the record the PreToolUse run made",
          not list((world.repo / ".git").glob("*-files-unchanged-before-tool-call-*")),
          list((world.repo / ".git").glob("*-files-unchanged-before-tool-call-*")))
    check("a file put back is settled: the next run says nothing", world.run() == "", "")
    result = world.command("--approve-and-reapply-kept-version", claude, key)
    check("--approve-and-reapply-kept-version refuses without the user's words in the marker file",
          result.returncode == 1 and "ask him" in result.stderr and claude.read_text() == V1,
          result.stderr)
    marker = world.marker('The user said "y" to the CLAUDE.md change')
    result = world.command("--approve-and-reapply-kept-version", claude, key)
    check("--approve-and-reapply-kept-version with the user's words puts the kept version back, approves it, "
          "spends the marker file and says so",
          result.returncode == 0 and claude.read_text() == V2
          and key in world.store_file(claude, "approved") and not marker.exists()
          and f"Approved {claude} at version {key} and put that kept version back."
          in result.stdout, (result.stdout, result.stderr))
    check("after --approve-and-reapply-kept-version the next run says nothing", world.run() == "", "")
    check("a change in no commit gets no git commit command", "git commit --only" not in message,
          message)

    world = fresh(scratch, "two-files-put-back")
    claude, local = world.repo / "CLAUDE.md", world.repo / "CLAUDE.local.md"
    world.call(lambda: local.write_text("seat v1\n"), tool="Write", file_path=local)

    def change_both():
        claude.write_text(V2)
        local.write_text("seat v2 by shell\n")

    message = world.call(change_both)
    check("two files one tool call changed are both put back, in one message",
          claude.read_text() == V1 and local.read_text() == "seat v1\n"
          and message.count("This tool call changed a guarded file") == 1
          and f"--approve-and-reapply-kept-version {local} {world.text_key('seat v2 by shell' + chr(10))} "
          f"{claude} {world.text_key(V2)}" in message, message)

    world = fresh(scratch, "reapply-deletion-and-change-together")
    claude, local = world.repo / "CLAUDE.md", world.repo / "CLAUDE.local.md"
    world.call(lambda: local.write_text("seat v1\n"), tool="Write", file_path=local)

    def delete_one_change_other():
        claude.unlink()
        local.write_text("seat v2 by shell\n")

    world.call(delete_one_change_other)
    world.marker('The user said "y" to both changes')
    result = world.command("--approve-and-reapply-kept-version", claude, "deleted", local,
                           world.text_key("seat v2 by shell\n"))
    check("--approve-and-reapply-kept-version of a deletion and a change in one command reapplies both",
          result.returncode == 0 and not claude.exists()
          and local.read_text() == "seat v2 by shell\n", (result.stdout, result.stderr))

    world = fresh(scratch, "before-call-run-records-nothing-it-cannot")
    outside = Path(scratch) / "before-call-run-records-nothing-it-cannot" / "outside"
    outside.mkdir()
    check("the PreToolUse run with no tool_use_id says nothing and records nothing",
          world.run(event="PreToolUse") == ""
          and not list((world.repo / ".git").glob("*-files-unchanged-before-tool-call-*")), "")
    check("the PreToolUse run outside every checkout says nothing",
          world.run(event="PreToolUse", cwd=outside, tool_use_id="toolu_outside") == "", "")

    world = fresh(scratch, "mac-put-back", machine="mac")
    claude = world.repo / "CLAUDE.md"
    mount_point = Path(scratch) / "mac-put-back" / "store"
    table = Path(scratch) / "mac-put-back" / "mount-table"
    table.write_text(f"//nedlern@ned-box/nedlern on {mount_point} (smbfs)\n")
    world.extra_environment = {"GUARDED_FILE_VERSIONS_MOUNT_POINT": str(mount_point),
                               "GUARDED_FILE_VERSIONS_MOUNT_TABLE": str(table)}
    world.run()
    message = world.call(lambda: claude.write_text(V2))
    check("on the Mac a change this tool call made is put back, and the kept copy is cited in "
          "the Mac's directory of the store",
          claude.read_text() == V1 and "guarded-file-versions-and-approvals/mac/" in message,
          message)

    world = fresh(scratch, "reapply-refusals")
    claude = world.repo / "CLAUDE.md"
    key = world.text_key(V2)
    world.call(lambda: claude.write_text(V2))
    message = world.call(lambda: claude.write_text("project v3 by Edit\n"), tool="Edit",
                         file_path=claude)
    check("an Edit of a version that was put back is approved", message == "", message)
    world.marker('The user said "y"')
    result = world.command("--approve-and-reapply-kept-version", claude, key)
    check("--approve-and-reapply-kept-version refuses when the file changed after the put-back",
          result.returncode == 1 and "would overwrite a later change" in result.stderr
          and claude.read_text() == "project v3 by Edit\n", result.stderr)
    result = world.command("--approve-and-reapply-kept-version", claude, world.key(claude))
    check("--approve-and-reapply-kept-version refuses a version the hook never put back",
          result.returncode == 1 and "never put back" in result.stderr, result.stderr)

    world = fresh(scratch, "deletion-put-back")
    claude = world.repo / "CLAUDE.md"
    message = world.call(claude.unlink)
    check("a shell deletion this tool call made is put back",
          claude.read_text() == V1 and "deletion" in message, message)
    world.marker('The user said "y" to deleting CLAUDE.md')
    result = world.command("--approve-and-reapply-kept-version", claude, "deleted")
    check("--approve-and-reapply-kept-version of a deletion deletes the file again",
          result.returncode == 0 and not claude.exists(), (result.stdout, result.stderr))

    world = fresh(scratch, "failure-event-put-back")
    claude = world.repo / "CLAUDE.md"
    world.call(lambda: claude.write_text(V2), event="PostToolUseFailure")
    check("a failing tool call's change is put back too", claude.read_text() == V1,
          claude.read_text())

    # -- every case where putting back is not safe keeps the ask, and says why
    world = fresh(scratch, "changed-before-the-call")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2, changed outside any tool call\n")
    message = world.call(lambda: None)
    check("a change made before the tool call is not put back, and the message says why",
          claude.read_text() == "project v2, changed outside any tool call\n"
          and "cannot show that this tool call made the change" in message
          and "has not approved" in message, message)
    earlier = world.key(claude)
    message = world.call(lambda: claude.write_text("project v3 by shell\n"))
    check("a tool call's change to a version that was itself unapproved is not put back",
          claude.read_text() == "project v3 by shell\n"
          and f"the version this hook saw before, {earlier}, was not approved either" in message,
          message)

    world = fresh(scratch, "no-record-before-the-call")
    claude = world.repo / "CLAUDE.md"
    claude.write_text(V2)
    message = world.run(tool_use_id="toolu_with_no_record")
    check("with no record from before the call, nothing is put back",
          claude.read_text() == V2 and "cannot show that this tool call" in message, message)

    world = fresh(scratch, "put-back-fails")
    claude = world.repo / "CLAUDE.md"

    def change_and_lock():
        claude.write_text(V2)
        world.repo.chmod(0o500)

    try:
        message = world.call(change_and_lock)
    finally:
        world.repo.chmod(0o755)
    check("when putting back fails, the change stays, the message says what failed, and the "
          "agent is asked as before",
          claude.read_text() == V2 and "putting back the approved version failed" in message
          and "Permission denied" in message
          and f"--restore {claude} {world.key(claude)}" in message, message)

    world = fresh(scratch, "approved-copy-missing")
    claude = world.repo / "CLAUDE.md"
    # An approved version no commit holds, so the store's copy is its only copy.
    world.call(lambda: claude.write_text("project v1, an approved Edit\n"), tool="Edit",
               file_path=claude)
    approved_key = world.key(claude)
    (world.store / str(claude).lstrip("/") / approved_key).unlink()
    message = world.call(lambda: claude.write_text(V2))
    check("with the approved version in neither the store nor git, nothing is put back",
          claude.read_text() == V2
          and f"the approved version {approved_key} is in neither the store's copies" in message,
          message)

    world = fresh(scratch, "approved-version-only-in-git")
    claude = world.repo / "CLAUDE.md"
    approved_key = world.key(claude)
    message = world.call(lambda: claude.write_text(V2))
    check("an approved version the branch's HEAD commit holds, with no copy in the store, is put "
          "back from git", approved_key not in world.versions(claude)
          and claude.read_text() == V1 and "put back the approved version" in message,
          (world.versions(claude), message))

    world = fresh(scratch, "outside-the-checkout")
    home_claude = world.home / ".claude" / "CLAUDE.md"
    message = world.call(lambda: home_claude.write_text("global v2 by shell\n"))
    check("a guarded file outside the agent-session's checkout is not put back",
          home_claude.read_text() == "global v2 by shell\n"
          and "outside your agent-session's own checkout" in message, message)

    world = fresh(scratch, "settings-local-not-put-back")
    local = world.repo / ".claude" / "settings.local.json"
    local.parent.mkdir()
    message = world.call(lambda: local.write_text('{"a": 1}\n'), tool="Write", file_path=local)
    check("a Write of a new guarded file is approved", message == "", message)
    grant = '{"permissions": {"allow": ["Bash(ls)"]}}\n'
    message = world.call(lambda: local.write_text(grant))
    check("a change to .claude/settings.local.json, which Claude Code writes itself, is not put "
          "back", local.read_text() == grant and "Claude Code writes this file itself" in message,
          message)

    world = fresh(scratch, "git-work-not-put-back")
    claude = world.repo / "CLAUDE.md"
    # The branch switched to is on another commit, so its reflog entry differs from the last.
    world.git("checkout", "-q", "-b", "elsewhere")
    (world.repo / "notes.txt").write_text("elsewhere\n")
    world.git("commit", "-qam", "elsewhere moves")
    world.git("checkout", "-q", "main")
    world.run()

    def change_and_switch():
        claude.write_text(V2)
        world.git("checkout", "-q", "elsewhere")

    message = world.call(change_and_switch)
    check("a change in a tool call that also switched branches is not put back",
          claude.read_text() == V2 and "git's own work" in message, message)

    world = fresh(scratch, "unpushed-commit-put-back")
    claude = world.repo / "CLAUDE.md"

    def change_and_commit():
        claude.write_text(V2)
        world.git("commit", "-qam", "a shell edit")

    message = world.call(change_and_commit)
    check("a change committed but not pushed in the same tool call is put back, and the message "
          "gives the commit that puts back the approved version",
          claude.read_text() == V1 and f'git commit --only -m "Put back the approved CLAUDE.md" '
          f"-- {claude}" in message
          and "is kept at the commit HEAD points to in your checkout's git repository" in message,
          message)
    world.marker('The user said "y" to the committed change')
    result = world.command("--approve-and-reapply-kept-version", claude, world.text_key(V2))
    check("--approve-and-reapply-kept-version reads a kept version that only the commit holds from git",
          result.returncode == 0 and claude.read_text() == V2, (result.stdout, result.stderr))

    world = fresh(scratch, "pushed-commit-not-put-back")
    claude = world.repo / "CLAUDE.md"
    remote = Path(scratch) / "pushed-commit-not-put-back" / "remote.git"
    world.git("init", "-q", "--bare", str(remote))
    world.git("remote", "add", "origin", str(remote))
    world.git("push", "-q", "origin", "main")
    world.run()

    def change_commit_and_push():
        claude.write_text(V2)
        world.git("commit", "-qam", "a shell edit")
        world.git("push", "-q", "origin", "main")

    message = world.call(change_commit_and_push)
    check("a change already pushed in the same tool call is not put back",
          claude.read_text() == V2 and "already pushed" in message, message)

    # -- an Edit made on an unapproved version does not approve the unapproved text
    world = fresh(scratch, "edit-after-unapproved-shell-edit")
    claude = world.repo / "CLAUDE.md"
    claude.write_text(V2)
    world.run()
    message = world.call(lambda: claude.write_text(V2 + "an approved Edit's line\n"),
                         tool="Edit", file_path=claude)
    check("an Edit of a file that holds an unapproved version is not approved, and the message "
          "says why", world.key(claude) not in world.store_file(claude, "approved")
          and "covers only that call's change" in message, message)

    # -- a mv of a settled guarded file is a rename, not put back
    world = fresh(scratch, "rename-in-a-call")
    skills = world.repo / ".claude" / "skills"
    skills.mkdir(parents=True)
    world.call(lambda: (skills / "a.md").write_text("skill a\n"), tool="Write",
               file_path=skills / "a.md")
    message = world.call(lambda: os.rename(skills / "a.md", skills / "b.md"))
    check("a mv of a settled guarded file in a tool call is neither put back nor asked about",
          message == "" and (skills / "b.md").exists() and not (skills / "a.md").exists(),
          message)


def main():
    with tempfile.TemporaryDirectory() as scratch:
        put_back_cases(os.path.realpath(scratch))
        cases(os.path.realpath(scratch))
    print(f"\n{'FAILED' if failures else 'PASSED'}: {failures} failing case(s)")
    return 1 if failures else 0


def cases(scratch):
    # -- a shell command that edits CLAUDE.md is caught
    world = fresh(scratch, "shell-edit")
    claude = world.repo / "CLAUDE.md"
    check("the first run stocks the checkout and asks nothing",
          world.key(claude) in world.store_file(claude, "approved"),
          world.store_file(claude, "approved"))
    claude.write_text("project v2\n")
    key = world.key(claude)
    message = world.run()
    check("a shell edit of CLAUDE.md is reported, with the path and the version's hash",
          str(claude) in message and key in message and "has not approved" in message, message)
    check("the shell edit's version is copied into the store",
          key in world.versions(claude), world.versions(claude))
    check("the file is left as the shell edit wrote it", claude.read_text() == "project v2\n")
    check("the message shows the diff against the approved version",
          "-project v1" in message and "+project v2" in message, message)
    check("the message gives the --approve and --restore commands with the hook's full path",
          f"{HOOK} --approve {claude} {key}" in message
          and f"{HOOK} --restore {claude} {key}" in message, message)

    # -- reminders repeat in the asking session, once in another, and stop once settled
    reminder = world.run()
    check("the asking session is reminded after its next tool call",
          "Reminder" in reminder and str(claude) in reminder, reminder)
    check("the asking session is reminded again after the call after that",
          "Reminder" in world.run(), "")
    other = world.run(session="session-b", owner="owner-b")
    check("another session is reminded once", "Reminder" in other, other)
    check("another session is not reminded a second time",
          world.run(session="session-b", owner="owner-b") == "", "")
    marker = world.marker('The user said "y" to the CLAUDE.md change')
    result = world.command("--approve", claude, key)
    check("--approve with the user's words records his yes", result.returncode == 0,
          result.stderr)
    check("--approve spends the marker", not marker.exists())
    check("after --approve the asking session is reminded no more", world.run() == "", "")

    # -- --approve refusals
    world = fresh(scratch, "approve-refusals")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    key = world.key(claude)
    world.run()
    result = world.command("--approve", claude, key)
    check("--approve refuses without a marker, and says to ask the user",
          result.returncode == 1 and "ask him" in result.stderr, result.stderr)
    world.marker('The user said "y"')
    claude.write_text("project v3\n")
    result = world.command("--approve", claude, key)
    check("--approve refuses when the file no longer holds the hash given",
          result.returncode == 1 and "no longer holds" in result.stderr, result.stderr)
    check("a refused --approve leaves the marker", (world.repo / ".walk-approved").exists())

    # -- an obvious-fix marker approves only a change it came before
    world = fresh(scratch, "obvious-fix-before")
    claude = world.repo / "CLAUDE.md"
    world.marker(OBVIOUS_FIX, before=time.time_ns() - 10_000_000_000)
    claude.write_text("project v1, typo fixed\n")
    key = world.key(claude)
    world.run()
    result = world.command("--approve", claude, key)
    check("an obvious-fix marker written before a shell edit approves the edit's version",
          result.returncode == 0 and key in world.store_file(claude, "approved"), result.stderr)

    world = fresh(scratch, "obvious-fix-after")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v1, an accident\n")
    key = world.key(claude)
    world.run()
    world.marker(OBVIOUS_FIX, before=time.time_ns() + 10_000_000_000)
    result = world.command("--approve", claude, key)
    check("an obvious-fix marker written after the run that first saw the version is refused, "
          "and the agent is told to ask the user",
          result.returncode == 1 and "ask him" in result.stderr, result.stderr)
    check("the refused version stays unsettled", "Reminder" in world.run(), "")

    world = fresh(scratch, "obvious-fix-after-quotes-the-marker")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v1, a quoted accident\n")
    key = world.key(claude)
    world.run()
    world.marker("Obvious fix under CLAUDE.md's standing approval: a typo\n  in CLAUDE.md\n",
                 before=time.time_ns() + 10_000_000_000)
    result = world.command("--approve", claude, key)
    check("a late obvious-fix marker's refusal gives the line that opens the question to the "
          "user, quoting the marker's words with their lines joined by spaces",
          result.returncode == 1 and (
              f'"An obvious fix to the guarded file {claude}; the marker was written after the '
              'change, so it needs your yes: a typo in CLAUDE.md"') in result.stderr,
          result.stderr)

    world = fresh(scratch, "obvious-fix-after-marker-says-nothing")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v1, an unexplained accident\n")
    key = world.key(claude)
    world.run()
    world.marker("Obvious fix under CLAUDE.md's standing approval:",
                 before=time.time_ns() + 10_000_000_000)
    result = world.command("--approve", claude, key)
    check("a late obvious-fix marker with no words after its opening gives "
          "\"(the marker does not say what)\" in the line",
          result.returncode == 1
          and "so it needs your yes: (the marker does not say what)\"" in result.stderr,
          result.stderr)

    world = fresh(scratch, "obvious-fix-same-time")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v1, same time\n")
    key = world.key(claude)
    world.run()
    log = world.store_file(claude, "log")
    seen_time = int([line for line in log.splitlines() if key in line][0].split("\t")[1])
    world.marker(OBVIOUS_FIX, before=seen_time)
    result = world.command("--approve", claude, key)
    check("an obvious-fix marker with the same time as the first sight counts as after it",
          result.returncode == 1, result.stderr)

    world = fresh(scratch, "marker-spent-by-edit")
    claude = world.repo / "CLAUDE.md"
    other = world.repo / ".claude" / "skills" / "x" / "SKILL.md"
    other.parent.mkdir(parents=True)
    world.marker(OBVIOUS_FIX, before=time.time_ns() - 10_000_000_000)
    claude.write_text("project v1, fixed by shell\n")
    key = world.key(claude)
    world.run()
    # A guarded Edit between the shell change and --approve spends the marker at PreToolUse.
    (world.repo / ".walk-approved").unlink()
    other.write_text("skill\n")
    world.run(tool="Write", file_path=other)
    result = world.command("--approve", claude, key)
    check("when a guarded Edit spends the marker first, --approve refuses and says ask the user",
          result.returncode == 1 and "ask him" in result.stderr, result.stderr)

    # -- --restore
    world = fresh(scratch, "restore")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2, approved edit\n")
    world.run(tool="Edit", file_path=claude)
    approved_key = world.key(claude)
    check("a successful Edit's version is approved by the hook run after it",
          approved_key in world.store_file(claude, "approved"), world.store_file(claude, "approved"))
    claude.write_text("project v3, shell\n")
    declined = world.key(claude)
    world.run()
    claude.write_text("project v4, changed again\n")
    result = world.command("--restore", claude, declined)
    check("--restore refuses when the file changed after the user was shown it",
          result.returncode == 1 and "changed after" in result.stderr, result.stderr)
    claude.write_text("project v3, shell\n")
    result = world.command("--restore", claude, declined)
    check("an approved uncommitted Edit, a shell edit, then a decline puts back the Edit",
          result.returncode == 0 and claude.read_text() == "project v2, approved edit\n",
          (result.stderr, claude.read_text()))
    check("the next run sees the restored file as settled", world.run() == "", "")

    world = fresh(scratch, "restore-keeps-current")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    world.run()
    claude.write_text("project v3, never seen by a run\n")
    key = world.key(claude)
    result = world.command("--restore", claude, key)
    check("--restore keeps the current version before it restores",
          result.returncode == 0 and key in world.versions(claude), world.versions(claude))

    # -- a version git holds is logged, not copied, and read back from git
    world = fresh(scratch, "git-holds")
    claude = world.repo / "CLAUDE.md"
    committed = world.key(claude)
    check("a version a commit holds is not copied",
          committed not in world.versions(claude), world.versions(claude))
    check("and the log has its line with the version's git id",
          world.seen_in_log(claude, committed), world.store_file(claude, "log"))
    home_claude = world.home / ".claude" / "CLAUDE.md"
    check("a guarded file outside every checkout is copied",
          world.key(home_claude) in world.versions(home_claude), world.versions(home_claude))
    claude.write_text("project v2, committed\n")
    world.git("commit", "-qam", "v2")
    second = world.key(claude)
    message = world.run()
    check("a version committed before a run sees it is asked about, with the diff read from git",
          str(claude) in message and "-project v1" in message and "+project v2" in message,
          message)
    check("and it is not copied", second not in world.versions(claude), world.versions(claude))
    result = world.command("--restore", claude, second)
    check("--restore puts back an approved version that only git holds",
          result.returncode == 0 and claude.read_text() == "project v1\n",
          (result.stderr, claude.read_text()))
    check("and does not copy the declined version git holds",
          second not in world.versions(claude), world.versions(claude))
    world.git("commit", "-qam", "Put back the approved CLAUDE.md")
    world.run()
    claude.write_text("project v3, shell\n")
    world.run()
    check("a version git does not hold is copied", world.key(claude) in world.versions(claude),
          world.versions(claude))

    world = fresh(scratch, "held-only-outside-durable-refs")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2, staged\n")
    world.git("add", "CLAUDE.md")
    world.run()
    staged = world.key(claude)
    check("a version git holds only as a staged blob is copied",
          world.git_holds(staged) and staged in world.versions(claude), world.versions(claude))
    claude.write_text("project v3, in a work snapshot\n")
    world.git("stash", "-q")
    world.git("stash", "apply", "-q")
    world.run()
    stashed = world.key(claude)
    check("a version only refs/stash holds is copied",
          world.git_holds(stashed) and stashed in world.versions(claude), world.versions(claude))
    other = world.repo / "sub" / "CLAUDE.md"
    other.parent.mkdir(exist_ok=True)
    other.write_text("project v1\n")
    world.run()
    check("a version HEAD holds at another path is copied",
          world.key(other) in world.versions(other), world.versions(other))

    world = fresh(scratch, "held-only-by-a-detached-head")
    claude = world.repo / "CLAUDE.md"
    world.git("checkout", "-q", "--detach")
    claude.write_text("project v2, committed on a detached HEAD\n")
    world.git("commit", "-qam", "detached")
    world.run()
    check("a version only a detached HEAD holds is copied",
          world.key(claude) in world.versions(claude), world.versions(claude))

    world = fresh(scratch, "approved-version-held-nowhere")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2, approved edit\n")
    world.run(tool="Edit", file_path=claude)
    approved_key = world.key(claude)
    (world.store / str(claude).lstrip("/") / approved_key).unlink()
    claude.write_text("project v3, shell\n")
    declined = world.key(claude)
    world.run()
    result = world.command("--restore", claude, declined)
    check("--restore refuses when the approved version is in neither its copy nor git",
          result.returncode == 1 and "neither the guarded-file store's copies of that file nor the git repository" in result.stderr
          and claude.read_text() == "project v3, shell\n", (result.stderr, claude.read_text()))

    world = fresh(scratch, "git-holds-check-fails")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    world.failing_git("ls-tree")
    message = world.run()
    check("a run whose git cannot say which versions it holds reports the failure",
          "did not run" in message and "injected failure" in message, message)
    check("and copies nothing", world.key(claude) not in world.versions(claude),
          world.versions(claude))
    result = world.command("--restore", claude, world.key(claude))
    check("--restore whose git cannot say which versions it holds fails and changes nothing",
          result.returncode == 1 and "injected failure" in result.stderr
          and "Traceback" not in result.stderr
          and claude.read_text() == "project v2\n", (result.stderr, claude.read_text()))
    world.failing_git(None)
    message = world.run()
    check("the next run checks the file", str(claude) in message, message)

    world = fresh(scratch, "git-read-back-fails")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    world.failing_git("cat-file -e")
    message = world.run()
    check("a run whose git fails to say whether it holds the approved version reports it",
          "did not run" in message and "injected failure" in message, message)
    world.failing_git(None)
    world.run()
    key = world.key(claude)
    world.failing_git("cat-file blob")
    result = world.command("--restore", claude, key)
    check("--restore whose git fails to read the approved version fails and changes nothing",
          result.returncode == 1 and "injected failure" in result.stderr
          and "Traceback" not in result.stderr
          and claude.read_text() == "project v2\n", (result.stderr, claude.read_text()))
    world.failing_git(None)

    # -- edit, commit and rebase in one command
    world = fresh(scratch, "commit-rebase")
    claude = world.repo / "CLAUDE.md"
    world.git("checkout", "-q", "-b", "topic")
    world.git("checkout", "-q", "main")
    (world.repo / "notes.txt").write_text("main moved\n")
    world.git("commit", "-qam", "main moves")
    world.git("checkout", "-q", "topic")
    world.run()
    claude.write_text("project v2, committed and rebased\n")
    world.git("commit", "-qam", "edit CLAUDE.md")
    world.git("rebase", "-q", "main")
    message = world.run()
    check("an edit committed and rebased in one command is caught",
          str(claude) in message and "has not approved" in message, message)
    check("and is still unsettled at the next run", "Reminder" in world.run(), "")

    # -- git's own work is not asked about
    world = fresh(scratch, "git-own-work")
    claude = world.repo / "CLAUDE.md"
    world.git("checkout", "-q", "-b", "other")
    claude.write_text("project on other\n")
    world.git("commit", "-qam", "other's CLAUDE.md")
    world.git("checkout", "-q", "main")
    world.run()
    world.git("checkout", "-q", "other")
    check("a branch switch is not asked about", world.run() == "", "")
    world.git("checkout", "-q", "main")
    world.run()
    world.git("merge", "-q", "--no-edit", "other")
    check("a merge is not asked about", world.run() == "", "")
    world.git("revert", "--no-edit", "HEAD")
    check("a revert is not asked about", world.run() == "", "")
    world.git("checkout", "-q", "-b", "picked", "HEAD~1")
    world.run()
    world.git("checkout", "-q", "main")
    world.git("checkout", "-q", "-b", "pick-target", "HEAD~2")
    world.run()
    world.git("cherry-pick", "other")
    check("a cherry-pick is not asked about", world.run() == "", "")

    # -- a merge finished after a conflict a run saw
    world = fresh(scratch, "conflict")
    claude = world.repo / "CLAUDE.md"
    world.git("checkout", "-q", "-b", "side")
    claude.write_text("project side\n")
    world.git("commit", "-qam", "side")
    world.git("checkout", "-q", "main")
    claude.write_text("project main\n")
    world.run(tool="Edit", file_path=claude)
    world.git("commit", "-qam", "main")
    world.run()
    world.git("merge", "side", check_ok=False)
    during = world.run()
    check("nothing is asked while a merge is stopped on a conflict", during == "", during)
    conflicted = world.key(claude)
    check("the conflicted version is copied during the conflict",
          conflicted in world.versions(claude), world.versions(claude))
    claude.write_text("project merged\n")
    world.git("commit", "-qam", "merged")
    message = world.run()
    check("a resolution committed with no run seeing it is not asked about", message == "",
          message)

    world = fresh(scratch, "conflict-seen-resolution")
    claude = world.repo / "CLAUDE.md"
    world.git("checkout", "-q", "-b", "side")
    claude.write_text("project side\n")
    world.git("commit", "-qam", "side")
    world.git("checkout", "-q", "main")
    claude.write_text("project main\n")
    world.run(tool="Edit", file_path=claude)
    world.git("commit", "-qam", "main")
    world.run()
    world.git("merge", "side", check_ok=False)
    world.run()
    claude.write_text("project resolution a run saw\n")
    world.run()
    world.git("commit", "-qam", "merged")
    message = world.run()
    check("a resolution a run saw before the finishing commit is asked about",
          str(claude) in message, message)

    # -- stash
    world = fresh(scratch, "stash")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2, approved\n")
    world.run(tool="Edit", file_path=claude)
    world.git("stash", "-q")
    check("git stash of an approved edit is not asked about", world.run() == "", "")
    world.git("stash", "apply", "-q")
    check("git stash apply of an approved edit is not asked about", world.run() == "", "")

    # -- two checkouts keep two paths
    world = fresh(scratch, "two-checkouts")
    second = world.agents / "second"
    world.git("worktree", "add", "-q", str(second))
    (world.repo / "CLAUDE.local.md").write_text("seat one\n")
    (second / "CLAUDE.local.md").write_text("seat two\n")
    world.run()
    world.run(cwd=second)
    check("an edit of CLAUDE.local.md in two checkouts is kept under two paths",
          world.versions(world.repo / "CLAUDE.local.md")
          and world.versions(second / "CLAUDE.local.md")
          and world.versions(world.repo / "CLAUDE.local.md")
          != world.versions(second / "CLAUDE.local.md"),
          (world.versions(world.repo / "CLAUDE.local.md"),
           world.versions(second / "CLAUDE.local.md")))

    # -- renames
    world = fresh(scratch, "renames")
    skills = world.repo / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "a.md").write_text("skill a\n")
    world.run(tool="Write", file_path=skills / "a.md")
    os.rename(skills / "a.md", skills / "b.md")
    check("a mv of a settled guarded file is not asked about", world.run() == "", "")
    (skills / "b.md").write_text("skill b, unapproved\n")
    world.run()
    os.rename(skills / "b.md", skills / "c.md")
    message = world.run()
    check("a mv of an unsettled guarded file to a new guarded path is asked about",
          str(skills / "c.md") in message, message)

    # -- copies that do not match, incomplete lines
    world = fresh(scratch, "damaged-store")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    key = world.key(claude)
    directory = world.store / str(claude).lstrip("/")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / key).write_text("cut off")
    with open(directory / "approved", "ab") as approved:
        approved.write(key.encode())  # an incomplete last line, as a cut-off write leaves
    message = world.run()
    check("a copy whose content does not match its hash name is replaced",
          (directory / key).read_text() == "project v2\n", (directory / key).read_text())
    check("an incomplete last line of approved is never read as an approval",
          str(claude) in message, message)

    # -- a run that fails part way leaves the file looking changed
    world = fresh(scratch, "fails-part-way")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    directory = world.store / str(claude).lstrip("/")
    (directory / "approved").chmod(0o000)
    message = world.run()
    check("a run that cannot read the approved set reports the failure",
          "did not run" in message, message)
    (directory / "approved").chmod(0o600)
    message = world.run()
    check("the next run checks the file", str(claude) in message, message)

    # -- unapproved commit, switch away and back
    world = fresh(scratch, "switch-back")
    claude = world.repo / "CLAUDE.md"
    world.git("branch", "elsewhere")
    claude.write_text("project v2, unapproved\n")
    world.run()
    world.git("commit", "-qam", "commit the unapproved version")
    world.run()
    world.git("checkout", "-q", "elsewhere")
    world.run()
    world.git("checkout", "-q", "main")
    message = world.run()
    check("an unapproved commit, a switch away and back leaves the version unsettled",
          str(claude) in message, message)

    # -- two runs copying the same version at the same moment
    world = fresh(scratch, "two-runs")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    key = world.key(claude)
    state = next((world.repo / ".git").glob("*-state.json"))
    before = state.read_bytes()
    world.run(session="s1")
    # The second run read the same stored state as the first, as it would at the same moment.
    state.write_bytes(before)
    world.run(session="s2")
    log = world.store_file(claude, "log")
    check("two runs copying one version leave one copy and two log lines",
          world.versions(claude).count(key) == 1
          and len([line for line in log.splitlines() if line.startswith("seen") and key in line]) == 2,
          log)

    # -- settings.json
    world = fresh(scratch, "settings")
    settings = world.home / ".claude" / "settings.json"
    settings.write_text(json.dumps({"model": "b", "hooks": {}}, indent=4))
    check("a /model change to settings.json is not asked about", world.run() == "", "")
    check("and it is copied", len([name for name in world.versions(settings)
                                   if name not in ("approved", "log")]) == 2,
          world.versions(settings))
    settings.write_text(json.dumps({"model": "b", "hooks": {"Stop": []}}))
    message = world.run()
    check("a change to the hooks key of settings.json is asked about", str(settings) in message,
          message)

    world = fresh(scratch, "settings-obvious-fix")
    settings = world.home / ".claude" / "settings.json"
    world.marker(OBVIOUS_FIX, before=time.time_ns() - 10_000_000_000)
    settings.write_text(json.dumps({"model": "c", "hooks": {"Stop": []}}))
    message = world.run()
    key = message.split(f"{settings}, version ", 1)[1].split(".", 1)[0] if message else ""
    result = world.command("--approve", settings, key)
    check("an obvious-fix marker written before a settings.json change approves it by the hash "
          "of the four keys", result.returncode == 0, (message[:300], result.stderr))

    # -- stocking
    world = World(Path(scratch) / "stocking")
    brief = world.agents / "seat" / "CLAUDE.local.md"
    brief.write_text("seat brief\n")
    world.run()
    stocked = [world.home / ".claude" / "CLAUDE.md", world.home / ".claude" / "settings.json", brief]
    check("the first run on a machine stocks ~/.claude/CLAUDE.md, settings.json and each "
          "seat-brief", all(world.store_file(path, "approved") for path in stocked),
          [world.store_file(path, "approved") for path in stocked])

    # -- the store cannot be written
    world = fresh(scratch, "unwritable")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    directory = world.store / str(claude).lstrip("/")
    for target in (directory / "approved", directory / "log", directory):
        target.chmod(0o500 if target.is_dir() else 0o400)
    message = world.run()
    for target in (directory, directory / "approved", directory / "log"):
        target.chmod(0o700 if target.is_dir() else 0o600)
    check("when the store cannot be written, the agent is told", "did not run" in message,
          message)
    check("and nothing else changes", claude.read_text() == "project v2\n")

    # -- the Mac's store over a stand-in mount
    mac_cases(scratch)
    durable_ref_cases(scratch)

    # -- a failing tool call
    world = fresh(scratch, "failure-event")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("written by a failing command\n")
    message = world.run(event="PostToolUseFailure")
    check("a PostToolUseFailure run catches a failing command's write", str(claude) in message,
          message)

    # -- the asking session after a handoff
    world = fresh(scratch, "handoff")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    world.run(session="old", owner="ended-old")
    message = world.run(session="successor", owner="owner-new")
    check("when the asking session has ended, the next session to see the file is asked",
          "A guarded file changed" in message, message)
    check("a live asking session's file only reminds another session",
          "Reminder" in world.run(session="third", owner="owner-third"), "")

    # -- the takeover of a deletion's ask after the asking session ended
    world = fresh(scratch, "deleted-takeover")
    claude = world.repo / "CLAUDE.md"
    claude.unlink()
    world.run(session="old", owner="ended-old")
    message = world.run(session="successor", owner="owner-new")
    check("when the asking session has ended, the next session is asked about a deletion",
          "A guarded file changed" in message and "version deleted" in message
          and "did not run" not in message, message)

    # -- a shell deletion, and a declined version that is in a commit
    world = fresh(scratch, "deletion")
    claude = world.repo / "CLAUDE.md"
    claude.unlink()
    message = world.run()
    check("a shell deletion of a guarded file is asked about", str(claude) in message
          and "version deleted" in message, message)
    result = world.command("--restore", claude, "deleted")
    check("declining a deletion puts back the newest approved content",
          result.returncode == 0 and claude.read_text() == "project v1\n", result.stderr)
    check("the put-back file is settled", world.run() == "", "")
    claude.write_text("project v2, committed\n")
    declined = world.key(claude)
    world.git("commit", "-qam", "commit an unapproved version")
    world.run()
    result = world.command("--restore", claude, declined)
    check("declining a version that is in a commit gives the commit command",
          result.returncode == 0 and f'git commit --only -m "Put back the approved CLAUDE.md" '
          f"-- {claude}" in result.stdout, result.stdout)

    world = fresh(scratch, "new-file")
    skill = world.repo / ".claude" / "skills" / "new" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("new skill\n")
    key = world.key(skill)
    world.run()
    result = world.command("--restore", skill, key)
    check("declining a new file with no approved version copies it and deletes it",
          result.returncode == 0 and not skill.exists() and key in world.versions(skill),
          (result.stderr, world.versions(skill)))
    check("the declined new file is not asked about again once it is deleted",
          world.run() == "", world.store_file(skill, "log"))

    # -- declining deletions whose folders are gone
    world = fresh(scratch, "deleted-folders")
    skills = world.repo / ".claude" / "skills"
    first, second = skills / "x" / "SKILL.md", skills / "y" / "SKILL.md"
    for path in (first, second):
        path.parent.mkdir(parents=True)
        path.write_text(f"{path.parent.name} v1\n")
    world.run()
    world.marker('The user said "y" to both skills')
    world.command("--approve", first, world.key(first), second, world.key(second))
    for path in (first, second):
        path.unlink()
        path.parent.rmdir()
    world.run()
    result = world.command("--restore", first, "deleted")
    check("declining a deletion whose folder is gone too recreates the folder and puts the file "
          "back", result.returncode == 0 and first.read_text() == "x v1\n",
          (result.returncode, result.stdout, result.stderr))
    second.parent.mkdir()
    second.parent.chmod(0o500)
    first.unlink()
    world.run()
    try:
        result = world.command("--restore", first, "deleted", second, "deleted")
    finally:
        second.parent.chmod(0o700)
    check("when one of several files cannot be put back, --restore says what it did to each and "
          "exits 1",
          result.returncode == 1 and first.read_text() == "x v1\n"
          and f"Put back the approved version" in result.stdout
          and f"Failed on {second}" in result.stdout and "not every file" in result.stderr,
          (result.returncode, result.stdout, result.stderr))

    # -- a guarded file that cannot be read is reported, never kept as an empty version
    world = World(Path(scratch) / "unreadable-first-run")
    home_claude = world.home / ".claude" / "CLAUDE.md"
    home_claude.chmod(0o000)
    try:
        message = world.run()
    finally:
        home_claude.chmod(0o600)
    empty_blob = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    check("an unreadable guarded file on the first run is reported, and no empty version is "
          "approved", "did not run" in message
          and empty_blob not in world.store_file(home_claude, "approved"),
          (message, world.store_file(home_claude, "approved")))
    world = fresh(scratch, "unreadable-later")
    home_claude = world.home / ".claude" / "CLAUDE.md"
    home_claude.write_text("global v2\n")
    home_claude.chmod(0o000)
    try:
        message = world.run()
    finally:
        home_claude.chmod(0o600)
    check("an unreadable changed guarded file is reported and no empty version is kept",
          "did not run" in message and empty_blob not in world.versions(home_claude),
          (message, world.versions(home_claude)))
    check("once it can be read, the next run asks about it",
          str(home_claude) in world.run(), "")
    key = world.key(home_claude)
    world.marker('The user said "y"')
    home_claude.chmod(0o000)
    try:
        result = world.command("--approve", home_claude, key)
    finally:
        home_claude.chmod(0o600)
    check("--approve of a file it cannot read says it failed, without a traceback, and exits 1",
          result.returncode == 1 and "--approve failed" in result.stderr
          and "Traceback" not in result.stderr, result.stderr)

    # -- a guarded file absent when first listed is checked once it comes back
    world = fresh(scratch, "absent-at-listing")
    later = world.repo / ".claude" / "skills" / "later" / "SKILL.md"
    later.parent.mkdir(parents=True)
    later.write_text("later v1\n")
    world.git("add", ".")
    world.git("commit", "-qm", "add a skill")
    later.unlink()
    world.run()
    later.write_text("later v2, never approved\n")
    message = world.run()
    check("a tracked guarded file absent when first listed is asked about once it comes back "
          "changed", str(later) in message, message)

    # -- a tool the instruction-file guard does not check is no approval
    world = fresh(scratch, "multiedit")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2 by MultiEdit\n")
    message = world.run(tool="MultiEdit", file_path=claude)
    check("a MultiEdit of a guarded file, which the guard does not check, is asked about",
          str(claude) in message and "has not approved" in message, message)

    # -- the subagent line comes first in the ask, and is in the reminder
    world = fresh(scratch, "subagent-line")
    claude = world.repo / "CLAUDE.md"
    claude.write_text("project v2\n")
    message = world.run()
    reminder = world.run()
    check("the ask tells a subagent what to do before any step that asks the user",
          0 <= message.find("If you are a subagent") < message.find("Show the user each change"),
          message)
    check("the reminder tells a subagent to report instead, and names the approval marker",
          "If you are a subagent" in reminder and ".walk-approved" in reminder, reminder)

    # -- two files changed by one tool call get one message
    world = fresh(scratch, "two-files")
    claude = world.repo / "CLAUDE.md"
    local = world.repo / "CLAUDE.local.md"
    claude.write_text("project v2\n")
    local.write_text("seat\n")
    message = world.run()
    check("the files one tool call changed are named in one message",
          message.count("A guarded file changed") == 1 and str(claude) in message
          and str(local) in message
          and f"{claude} {world.key(claude)}" in message.split("--approve", 1)[1].split("\n")[0]
          and f"{local} {world.key(local)}" in message.split("--approve", 1)[1].split("\n")[0],
          message)

    # -- a git-ignored Claude Code runtime file under .claude/ is not guarded
    world = fresh(scratch, "ignored-runtime-file")
    exclude = world.repo / ".git" / "info" / "exclude"
    exclude.write_text("**/.claude/scheduled_tasks.lock\nCLAUDE.local.md\n")
    lock = world.repo / ".claude" / "scheduled_tasks.lock"
    lock.parent.mkdir()
    lock.write_text('{"pid": 1}\n')
    world.run()
    lock.write_text('{"pid": 2}\n')
    message = world.run()
    check("a changed git-ignored .claude/scheduled_tasks.lock is not asked about",
          message == "" and str(lock) not in message, message)
    check("a git-ignored .claude/scheduled_tasks.lock is not copied into the store",
          world.versions(lock) == [], world.versions(lock))
    check("a git-ignored .claude/scheduled_tasks.lock draws no reminder",
          world.run() == "" and world.run(session="session-b", owner="owner-b") == "", "")

    # -- a pending ask for a file that is no longer guarded is dropped, not reported as deleted
    world = fresh(scratch, "formerly-guarded-file")
    settings_file = world.repo / ".claude" / "settings.json"
    settings_file.parent.mkdir()
    settings_file.write_text('{"a": 1}\n')
    world.run()
    settings_file.write_text('{"a": 2}\n')
    check("a changed untracked .claude file is asked about", str(settings_file) in world.run(), "")
    (world.repo / ".git" / "info" / "exclude").write_text("**/.claude/settings.json\n")
    message = world.run()
    check("a file that git now ignores draws no further ask or reminder",
          message == "" and world.run() == "", message)
    state_file = next((world.repo / ".git").glob("*-state.json"))
    check("the state file no longer names a file that git now ignores",
          str(settings_file) not in state_file.read_text(), "")
    settings_file.unlink()
    message = world.run()
    check("deleting a file that git ignores, after it was dropped, draws no ask",
          message == "" and world.run() == "", message)

    # -- a git-ignored CLAUDE.local.md is still guarded
    (world.repo / ".git" / "info" / "exclude").write_text(
        "**/.claude/scheduled_tasks.lock\nCLAUDE.local.md\n")
    ignored_local = world.repo / "CLAUDE.local.md"
    ignored_local.write_text("seat v1\n")
    world.run()
    ignored_local.write_text("seat v2\n")
    message = world.run()
    ignored = subprocess.run(["git", "-C", str(world.repo), "check-ignore", "-q", "CLAUDE.local.md"],
                             env=world.environment()).returncode == 0
    check("a changed git-ignored CLAUDE.local.md is still asked about",
          ignored and str(ignored_local) in message and "has not approved" in message,
          (ignored, message))

    # -- a git-ignored .claude/settings.local.json is still guarded
    world = fresh(scratch, "ignored-settings-local")
    (world.repo / ".git" / "info" / "exclude").write_text("**/.claude/settings.local.json\n")
    settings_local = world.repo / ".claude" / "settings.local.json"
    settings_local.parent.mkdir(exist_ok=True)
    settings_local.write_text('{"a": 1}\n')
    world.run()
    settings_local.write_text('{"a": 2}\n')
    message = world.run()
    ignored = subprocess.run(["git", "-C", str(world.repo), "check-ignore", "-q",
                              ".claude/settings.local.json"], env=world.environment()).returncode == 0
    check("a changed git-ignored .claude/settings.local.json is still asked about",
          ignored and str(settings_local) in message and "has not approved" in message,
          (ignored, message))

    # -- a cold read's frozen copy of CLAUDE.local.md, in its git-ignored record, is not guarded
    world = fresh(scratch, "cold-read-record-copy")
    (world.repo / ".git" / "info" / "exclude").write_text("cold-read-records/\n")
    record_copy = world.repo / "cold-read-records" / "CLAUDE.local-2026-10-18" / "target" / "CLAUDE.local.md"
    record_copy.parent.mkdir(parents=True)
    record_copy.write_text("seat v1\n")
    world.run()
    record_copy.write_text("seat v2\n")
    message = world.run()
    check("a changed CLAUDE.local.md copy in a cold-read record is not asked about",
          message == "", message)
    check("a CLAUDE.local.md copy in a cold-read record is not copied into the store",
          world.versions(record_copy) == [], world.versions(record_copy))
    check("a CLAUDE.local.md copy in a cold-read record draws no reminder, in any session",
          world.run() == "" and world.run(session="session-b", owner="owner-b") == "", "")

    # -- Claude Code's scheduler lock is never guarded, even where no exclude line ignores it
    world = fresh(scratch, "unignored-runtime-lock")
    lock = world.repo / ".claude" / "scheduled_tasks.lock"
    lock.parent.mkdir(exist_ok=True)
    lock.write_text('{"pid": 1}\n')
    world.run()
    lock.write_text('{"pid": 2}\n')
    message = world.run()
    check("a changed .claude/scheduled_tasks.lock that git does not ignore is not asked about",
          message == "" and world.versions(lock) == [] and world.run() == "", message)

    # -- speed, on a copy of main
    if sys.platform != "linux":
        print("SKIP  with nothing changed, a run does no hashing, copying or store work: not on ned-box")
        return
    top = subprocess.run(["git", "-C", str(HOOK.parent), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0:
        print("SKIP  with nothing changed, a run does no hashing, copying or store work: the hook is "
              "in no checkout to copy")
        return
    world = World(Path(scratch) / "speed")
    copy_of_main = Path(scratch) / "speed" / "main"
    subprocess.run(["git", "clone", "-q", "--shared", top.stdout.strip(), str(copy_of_main)],
                   check=True, env=world.environment())
    world.run(cwd=copy_of_main)
    world.run(cwd=copy_of_main)
    # CPU and wall time vary with machine load and tracing, so they are printed for information
    # only. What the case guards is that a run with nothing changed does no expensive work.
    times = []
    cpu_times = []
    for _ in range(5):
        world.run(cwd=copy_of_main)
        times.append(world.last_seconds)
        cpu_times.append(world.last_cpu_seconds)
    print(f"INFO  with nothing changed, wall seconds per run: {[round(t, 3) for t in times]}")
    print(f"INFO  with nothing changed, CPU seconds per run: {[round(t, 3) for t in cpu_times]}")
    hook = load_hook_in_this_process()
    calls = {"hash a file": 0, "read a file": 0, "hash bytes": 0, "open the store": 0}

    def counting(name, function):
        def wrapper(*arguments, **keywords):
            calls[name] += 1
            return function(*arguments, **keywords)
        return wrapper

    hashes_in_checkout = hook.hashes_in_checkout

    def hashes_counting_files(checkout, paths):
        calls["hash a file"] += len(paths)  # a call with no paths hashes nothing
        return hashes_in_checkout(checkout, paths)

    hook.hashes_in_checkout = hashes_counting_files
    hook.read_file = counting("read a file", hook.read_file)
    hook.blob_hash = counting("hash bytes", hook.blob_hash)
    hook.Store = counting("open the store", hook.Store)
    store_before = store_listing(world.store)
    saved_environment, saved_directory = dict(os.environ), os.getcwd()
    try:
        os.environ.update(world.environment())
        os.chdir(copy_of_main)
        texts = hook.run_hook({"session_id": "session-a", "hook_event_name": "PostToolUse",
                               "tool_name": "Bash", "cwd": str(copy_of_main),
                               "tool_input": {"command": "x"}})
    finally:
        os.chdir(saved_directory)
        os.environ.clear()
        os.environ.update(saved_environment)
    check("with nothing changed, a run on a copy of main hashes no file, reads no file, copies "
          "nothing and does not open the store",
          texts == [] and not any(calls.values()) and store_listing(world.store) == store_before,
          (texts, calls))


def load_hook_in_this_process():
    specification = importlib.util.spec_from_file_location("guarded_file_hook_under_test", HOOK)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def store_listing(store):
    """Every path in the store with its size and modification time."""
    return sorted((str(path), path.stat().st_size, path.stat().st_mtime_ns)
                  for path in Path(store).rglob("*"))


def durable_ref_cases(scratch):
    hook = load_hook_in_this_process()
    environment = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                       GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                       GIT_CONFIG_GLOBAL="/dev/null")

    def git(directory, *arguments):
        subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                       capture_output=True, env=environment)

    empty = Path(scratch) / "durable-refs-no-commit"
    empty.mkdir()
    git(empty, "init", "-q")
    (empty / "CLAUDE.md").write_text("first\n")
    check("a repository with no commit yet holds no version, and its git is not taken as failing",
          hook.versions_head_holds(empty, [(str(empty / "CLAUDE.md"),
                                            hook.blob_hash(b"first\n"))]) == set())
    git(empty, "add", "CLAUDE.md")
    git(empty, "commit", "-q", "-m", "first")
    detached = Path(scratch) / "durable-refs-detached-worktree"
    git(empty, "worktree", "add", "-q", "--detach", str(detached))
    (detached / "CLAUDE.md").write_text("only at a detached worktree HEAD\n")
    git(detached, "commit", "-q", "-am", "detached")
    held = hook.blobs_durable_refs_hold(empty)
    check("a branch's blobs are held by the durable refs", hook.blob_hash(b"first\n") in held)
    check("a blob only a detached worktree's HEAD holds is not",
          hook.blob_hash(b"only at a detached worktree HEAD\n") not in held)


def mac_cases(scratch):
    world = fresh(scratch, "mac", machine="mac")
    claude = world.repo / "CLAUDE.md"
    mount_point = Path(scratch) / "mac" / "store"
    table = Path(scratch) / "mac" / "mount-table"
    world.extra_environment = {"GUARDED_FILE_VERSIONS_MOUNT_POINT": str(mount_point),
                               "GUARDED_FILE_VERSIONS_MOUNT_TABLE": str(table),
                               "GUARDED_FILE_VERSIONS_DEADLINE_SECONDS": "3"}
    table.write_text(f"//nedlern@ned-box._smb._tcp.local/nedlern on {mount_point} "
                     "(smbfs, nodev, nosuid, mounted by nedlern)\n")
    world.run()
    claude.write_text("project v2 on the Mac\n")
    key = world.key(claude)
    message = world.run()
    check("on the Mac a changed file is copied into the stand-in store",
          key in world.versions(claude) and str(claude) in message, message)
    copy = world.store / str(claude).lstrip("/") / key
    check("the copy has mode 0600", (copy.stat().st_mode & 0o777) == 0o600,
          oct(copy.stat().st_mode))

    table.write_text("")
    claude.write_text("project v3 while unmounted\n")
    message = world.run()
    check("with the stand-in not mounted, the agent is told the backup failed, with the remedy",
          "did not run" in message and "/Volumes/nedhome" in message, message)
    check("with the stand-in not mounted, nothing is copied",
          world.key(claude) not in world.versions(claude))
    result = world.command("--approve", claude, world.key(claude))
    check("--approve refuses while the store cannot be reached", result.returncode == 1,
          result.stderr)
    result = world.command("--restore", claude, world.key(claude))
    check("--restore refuses while the store cannot be reached", result.returncode == 1,
          result.stderr)
    table.write_text(f"//nedlern@ned-box/nedlern on {mount_point} (smbfs)\n")
    message = world.run()
    check("the next run after the store is back copies and checks the version",
          world.key(claude) in world.versions(claude) and str(claude) in message, message)

    saved = world.store
    world.store = Path(scratch) / "mac" / "missing"
    world.extra_environment["GUARDED_FILE_VERSIONS_STORE_DIRECTORY"] = str(world.store)
    claude.write_text("project v4 with mac/ missing\n")
    message = world.run()
    check("with the store's mac/ directory missing, the backup failure is reported",
          "did not run" in message, message)
    check("and nothing is created", not world.store.exists())
    world.store = saved
    del world.extra_environment["GUARDED_FILE_VERSIONS_STORE_DIRECTORY"]

    directory = world.store / str(claude).lstrip("/")
    (directory / "approved").unlink()
    os.mkfifo(directory / "approved")
    claude.write_text("project v5 while the store hangs\n")
    started = time.monotonic()
    message = world.run()
    check("with a store whose reads block, the failure is reported before the hook's timeout",
          "did not run" in message and time.monotonic() - started < 10,
          (message, time.monotonic() - started))


if __name__ == "__main__":
    sys.exit(main())
