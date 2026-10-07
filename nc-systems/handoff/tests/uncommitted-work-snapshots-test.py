#!/usr/bin/env python3
"""Tests for work-snapshots: the hook, the shared module, the cleaner's step,
and the handoff-supervisor's first-prompt list.

Design: nc-systems/handoff/uncommitted-work-snapshots-across-crashes-design.md;
each section below is one bullet of its "How it will be tested".

Every case works in a scratch clone with the programs copied into it, so the
hook's own clone, and every ref written, is the scratch clone's. Git reads a
scratch global config and no system config.

The hook finds its owner by walking up to a process named claude. The suite
stands one in with a shell script named `claude`: on Linux the kernel names a
script's process after the script. On macOS `ps` names it after the shell, so
the cases that run the hook under that stand-in print SKIP there. No case
sends a signal: the stand-in ends when its stdin closes.

Run: python3 nc-systems/handoff/tests/uncommitted-work-snapshots-test.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent

_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
_fixture.remove_git_redirecting_environment_variables_from_this_process()

MODULE_RELATIVE = Path("nc-systems/handoff/uncommitted-work-snapshots.py")
HOOK_RELATIVE = Path("scripts/uncommitted-work-snapshot-hook.py")
CLEANER_RELATIVE = Path("scripts/clean-worktrees.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshots = load(REPOSITORY_ROOT / MODULE_RELATIVE, "uncommitted_work_snapshots")

failures = []
SKIPPED = []
CLAUDE_STAND_IN_WORKS = sys.platform.startswith("linux")


def check(condition, name, detail=""):
    if condition:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name}" + (f": {detail}" if detail else ""))
        failures.append(name)


def skip(name, reason):
    print(f"SKIP {name}: {reason}")
    SKIPPED.append(name)


def git(directory, *arguments, check_exit=True, input_text=None, environment=None):
    result = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                            text=True, input=input_text, env=environment)
    if check_exit and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} in {directory}: {result.stderr}")
    return result.stdout.strip()


SCRATCH = Path(tempfile.mkdtemp(prefix="uncommitted-work-snapshots-test-"))
HOME = SCRATCH / "home"
HOME.mkdir()
GLOBAL_EXCLUDES = SCRATCH / "global-excludes"
GLOBAL_EXCLUDES.write_text("*.globally-ignored\n")
GLOBAL_CONFIG = SCRATCH / "gitconfig"
GLOBAL_CONFIG.write_text(
    "[user]\n\tname = work-snapshot test\n\temail = test@nedschorus.invalid\n"
    f"[core]\n\texcludesFile = {GLOBAL_EXCLUDES}\n"
    "[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n")
os.environ.update(HOME=str(HOME), GIT_CONFIG_GLOBAL=str(GLOBAL_CONFIG), GIT_CONFIG_NOSYSTEM="1")
os.environ.pop("GIT_AUTHOR_NAME", None)

CLAUDE_STAND_IN = SCRATCH / "bin" / "claude"
CLAUDE_STAND_IN.parent.mkdir()
CLAUDE_STAND_IN.write_text(
    "#!/bin/sh\n"
    "while read hook_input; do\n"
    "  \"$@\" < \"$hook_input\"\n"
    "  echo \"hook-done $?\"\n"
    "done\n")
CLAUDE_STAND_IN.chmod(0o755)

clone_count = [0]


def new_clone():
    """A scratch clone holding the programs, with origin/main, and its main checkout."""
    clone_count[0] += 1
    base = SCRATCH / f"clone-{clone_count[0]}"
    origin = base / "origin.git"
    git(SCRATCH, "init", "-q", "--bare", str(origin))
    main = base / "main"
    git(SCRATCH, "clone", "-q", str(origin), str(main))
    for relative in (MODULE_RELATIVE, HOOK_RELATIVE, CLEANER_RELATIVE):
        (main / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative, main / relative)
    (main / "tracked.txt").write_text("one\n")
    (main / "doomed.txt").write_text("to be deleted\n")
    (main / ".gitignore").write_text("*.ignored\n.claude/worktrees/\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "base")
    git(main, "push", "-q", "origin", "main")
    return main


def add_worktree(main, path, branch):
    git(main, "worktree", "add", "-q", "-b", branch, str(path), "origin/main")
    return Path(path).resolve()


class ClaudeStandIn:
    """A process named claude that runs the clone's hook once per run_hook call."""

    started = 0

    def __init__(self, main, environment=None):
        self.main = main
        ClaudeStandIn.started += 1
        self.inputs = SCRATCH / f"hook-inputs-{ClaudeStandIn.started}"
        self.inputs.mkdir()
        self.count = 0
        self.last_exit = None
        self.process = subprocess.Popen(
            [str(CLAUDE_STAND_IN), sys.executable, str(main / HOOK_RELATIVE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            env=dict(os.environ, **(environment or {})))
        self.owner_key = snapshots.owner_key_of_process(self.process.pid)

    def run_hook(self, payload):
        self.count += 1
        path = self.inputs / f"{self.count}.json"
        path.write_text(json.dumps(payload))
        self.process.stdin.write(f"{path}\n")
        self.process.stdin.flush()
        output = []
        while True:
            line = self.process.stdout.readline()
            if line.startswith("hook-done"):
                self.last_exit = int(line.split()[1])
                break
            if not line:
                break
            output.append(line)
        text = "".join(output).strip()
        return json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else None

    def end(self):
        self.process.stdin.close()
        self.process.wait(timeout=30)
        self.process.stdout.close()


def refs_of(main, owner_key=None):
    prefix = snapshots.WORK_SNAPSHOT_REF_PREFIX + (f"{owner_key}/" if owner_key else "")
    return git(main, "for-each-ref", "--format=%(refname)", prefix).split()


def files_in_snapshot(main, ref):
    return sorted(git(main, "ls-tree", "-r", "--name-only", ref).split())


def bash(cwd):
    return {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": "true"},
            "transcript_path": str(SCRATCH / "transcript.jsonl")}


def edit(path):
    return {"tool_name": "Edit", "cwd": str(path.parent),
            "tool_input": {"file_path": str(path)},
            "transcript_path": str(SCRATCH / "transcript.jsonl")}


# ---------------------------------------------------------------- the hook


def test_what_a_work_snapshot_holds():
    name = "a work-snapshot holds modified, deleted and new files, not ignored ones"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("two\n")
    (worktree / "doomed.txt").unlink()
    (worktree / "new.txt").write_text("new\n")
    (worktree / "a.ignored").write_text("x\n")
    (worktree / "b.globally-ignored").write_text("x\n")
    exclude = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path",
                       "info/exclude"))
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("c.locally-excluded\n")
    (worktree / "c.locally-excluded").write_text("x\n")
    index = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index"))
    index_before = index.read_bytes()
    head_before = git(worktree, "rev-parse", "HEAD")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-one"})
    message = claude.run_hook(edit(worktree / "tracked.txt"))
    check(message is None, "the hook says nothing when the work-snapshot is written", message)
    refs = refs_of(main, claude.owner_key)
    check(len(refs) == 1, "one work-snapshot ref for the worktree", refs)
    if refs:
        held = files_in_snapshot(main, refs[0])
        check("new.txt" in held and "doomed.txt" not in held
              and git(main, "show", f"{refs[0]}:tracked.txt") == "two",
              name, held)
        check(not any(path.endswith(("ignored", "excluded")) for path in held),
              "ignored, locally excluded and globally excluded files are not held", held)
        trailers = snapshots.all_work_snapshots(main)[0]
        check(trailers["agent_seat"] == "seat-one" and trailers["branch"] == "fork-branch"
              and trailers["worktree"] == str(worktree)
              and trailers["transcript"] == str(SCRATCH / "transcript.jsonl"),
              "the trailers name the agent-seat, branch, worktree and transcript", trailers)
        check(git(main, "rev-parse", f"{refs[0]}^") == head_before,
              "the work-snapshot's parent is the worktree's HEAD")
    check(index.read_bytes() == index_before, "the worktree's index is unchanged")
    check(git(worktree, "rev-parse", "HEAD") == head_before
          and git(worktree, "symbolic-ref", "--short", "HEAD") == "fork-branch",
          "the worktree's HEAD and branch are unchanged")
    claude.end()


def test_same_size_edit_in_the_index_second():
    name = ("a same-size edit made in the second the index was written is held when the "
            "work-snapshot is built a second later")
    main = new_clone()
    for attempt in range(20):
        worktree = add_worktree(main, main / ".claude" / "worktrees" / f"racy-{attempt}",
                                f"racy-{attempt}")
        (worktree / "tracked.txt").write_text("two\n")
        index = Path(git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "index"))
        if int(os.stat(worktree / "tracked.txt").st_mtime) == int(os.stat(index).st_mtime):
            break
    else:
        return skip(name, "no edit landed in the index's second in 20 tries")
    # A copy of the index made in a later second, with a fresh mtime, would make git trust the
    # entry's stat data, which this same-size, same-second edit leaves unchanged.
    time.sleep(1.05)
    snapshots.refresh_work_snapshot(worktree, "3-3", "seat", "")
    ref = snapshots.work_snapshot_ref("3-3", worktree)
    check(git(main, "show", f"{ref}:tracked.txt") == "two", name)


def test_ref_names():
    name = "two worktrees with the same directory name get different refs; a space is legal"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    first = add_worktree(main, main / ".claude" / "worktrees" / "a" / "same", "a-branch")
    second = add_worktree(main, main / ".claude" / "worktrees" / "b" / "same", "b-branch")
    spaced = add_worktree(main, main / ".claude" / "worktrees" / "with space", "spaced")
    for worktree in (first, second, spaced):
        (worktree / "tracked.txt").write_text("changed\n")
    claude = ClaudeStandIn(main)
    for worktree in (first, second, spaced):
        message = claude.run_hook(edit(worktree / "tracked.txt"))
        check(message is None, f"the hook wrote a work-snapshot for {worktree.name!r}", message)
    refs = refs_of(main, claude.owner_key)
    check(len(set(refs)) == 3, name, refs)
    claude.end()


def test_bash_commit_deletes_and_other_worktrees_follow():
    name = "a Bash call that commits everything deletes the ref"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    fork = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    other = add_worktree(main, main / ".claude" / "worktrees" / "other", "other-branch")
    claude = ClaudeStandIn(main)
    (fork / "new.txt").write_text("work\n")
    claude.run_hook(bash(fork))
    fork_ref = snapshots.work_snapshot_ref(claude.owner_key, fork)
    check(fork_ref in refs_of(main), "a Bash call whose cwd is a fork's worktree handles it")
    (other / "tracked.txt").write_text("first\n")
    claude.run_hook(edit(other / "tracked.txt"))
    other_ref = snapshots.work_snapshot_ref(claude.owner_key, other)
    (other / "tracked.txt").write_text("second\n")
    claude.run_hook(bash(fork))
    check(git(main, "show", f"{other_ref}:tracked.txt") == "second",
          "a Bash call elsewhere refreshes a worktree that already has this owner's "
          "work-snapshot")
    git(fork, "add", "-A")
    git(fork, "commit", "-q", "-m", "work")
    claude.run_hook(bash(fork))
    check(fork_ref not in refs_of(main), name, refs_of(main))
    claude.end()


def test_overlapping_runs_end_on_the_final_state():
    name = "overlapping runs leave the ref on a work-snapshot of the final state"
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("first\n")
    owner = "1-1"
    ref = snapshots.work_snapshot_ref(owner, worktree)
    real_build = snapshots.build_work_snapshot_commit
    interleaved = []

    def build_while_another_run_lands(*arguments):
        commit = real_build(*arguments)
        if not interleaved:
            interleaved.append(True)
            (worktree / "tracked.txt").write_text("final\n")
            other = real_build(*arguments)
            git(main, "update-ref", ref, other)
        return commit

    snapshots.build_work_snapshot_commit = build_while_another_run_lands
    try:
        snapshots.refresh_work_snapshot(worktree, owner, "seat", "")
    finally:
        snapshots.build_work_snapshot_commit = real_build
    check(git(main, "show", f"{ref}:tracked.txt") == "final", name)
    threads = [threading.Thread(target=snapshots.refresh_work_snapshot,
                                args=(worktree, owner, "seat", "")) for _ in range(2)]
    (worktree / "tracked.txt").write_text("last\n")
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    check(git(main, "show", f"{ref}:tracked.txt") == "last",
          "two concurrent runs end on the worktree's state")


def test_operation_trailer():
    name = "during a merge with conflicts the operation trailer is merge"
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("fork side\n")
    git(worktree, "commit", "-q", "-am", "fork side")
    git(main, "checkout", "-q", "-b", "other")
    (main / "tracked.txt").write_text("other side\n")
    git(main, "commit", "-q", "-am", "other side")
    git(worktree, "merge", "-q", "other", check_exit=False)
    snapshots.refresh_work_snapshot(worktree, "2-2", "seat", "")
    found = [s for s in snapshots.all_work_snapshots(main) if s["owner_key"] == "2-2"]
    check(found and found[0]["operation"] == "merge", name, found)


def test_hook_failure_is_reported():
    name = "a hook that cannot write reports it through additionalContext and exits 0"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "tracked.txt").write_text("changed\n")
    claude = ClaudeStandIn(main)
    ref = snapshots.work_snapshot_ref(claude.owner_key, worktree)
    lock = Path(git(main, "rev-parse", "--path-format=absolute", "--git-common-dir")) / (
        ref + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("")
    message = claude.run_hook(edit(worktree / "tracked.txt"))
    check(message is not None and str(worktree) in message and "no work-snapshot" in message,
          name, message)
    check(claude.last_exit == 0, "the hook exits 0 when it reports a failure",
          claude.last_exit)
    check(claude.process.poll() is None, "the stand-in claude carried on after the failure")
    claude.end()
    hook = load(main / HOOK_RELATIVE, "hook_without_claude")
    hook.snapshots = hook.load_snapshots_module()
    hook.snapshots.claude_owner_process_id = lambda start: None
    messages = hook.run(edit(worktree / "tracked.txt"), os.getpid())
    check(len(messages) == 1 and "no process named claude" in messages[0]
          and str(worktree) in messages[0],
          "with no claude among its parents the hook tells the agent, naming the worktree",
          messages)
    (worktree / "tracked.txt").write_text("one\n")
    check(hook.run(edit(worktree / "tracked.txt"), os.getpid()) == [],
          "with no claude parent and nothing uncommitted the hook says nothing")


def test_other_repository_is_untouched():
    name = "an edit or a Bash call in another repository writes no work-snapshot there"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    other = SCRATCH / f"unrelated-repository-{clone_count[0]}"
    git(SCRATCH, "init", "-q", str(other))
    (other / "file.txt").write_text("one\n")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "base")
    (other / "file.txt").write_text("two\n")
    claude = ClaudeStandIn(main)
    message = claude.run_hook(edit(other / "file.txt"))
    claude.run_hook(bash(other))
    claude.end()
    other_refs = git(other, "for-each-ref", "--format=%(refname)",
                     snapshots.WORK_SNAPSHOT_REF_PREFIX).split()
    check(other_refs == [] and refs_of(main) == [] and message is None, name,
          (other_refs, refs_of(main), message))


def test_worktree_discovery_failure_is_reported():
    name = "a worktree that git fails to find, for a reason other than no repository, is reported"
    main = new_clone()
    bare = SCRATCH / f"bare-{clone_count[0]}.git"
    git(SCRATCH, "init", "-q", "--bare", str(bare))
    try:
        snapshots.worktree_containing(bare)
        raised = False
    except snapshots.WorkSnapshotError:
        raised = True
    check(raised, "worktree_containing raises when git fails inside a repository")
    outside = SCRATCH / "outside-every-repository"
    outside.mkdir(exist_ok=True)
    check(snapshots.worktree_containing(outside) is None,
          "worktree_containing gives None outside any repository")
    hook = load(main / HOOK_RELATIVE, "hook_discovery_failure")
    hook.snapshots = hook.load_snapshots_module()
    worktrees, messages = hook.candidate_worktrees(edit(bare / "config"), None)
    check(worktrees == [] and len(messages) == 1 and str(bare) in messages[0]
          and "could not be found" in messages[0], name, (worktrees, messages))


def test_module_load_failure_is_reported():
    name = "a module that cannot be loaded is reported through additionalContext, exit 0"
    main = new_clone()
    (main / MODULE_RELATIVE).write_text("this is not python (\n")
    result = subprocess.run([sys.executable, str(main / HOOK_RELATIVE)],
                            input=json.dumps(edit(main / "tracked.txt")),
                            capture_output=True, text=True)
    try:
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError):
        context = ""
    check(result.returncode == 0 and "could not be loaded" in context
          and "no work-snapshot" in context, name,
          (result.returncode, result.stdout, result.stderr))


class FakePs:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_macos_ps_failure_is_not_a_dead_owner():
    real_run_ps = snapshots.run_ps
    try:
        snapshots.run_ps = lambda arguments: FakePs(1)
        check(snapshots.macos_start_seconds(100) is None,
              "ps exiting 1 with no output means the process is gone")
        check(not snapshots.owner_process_is_alive("100-5", platform="darwin"),
              "a gone macOS owner counts as dead")
        for fake, why in ((FakePs(-9), "killed by a signal"),
                          (FakePs(1, stderr="ps: illegal option"), "an error message"),
                          (FakePs(2), "another exit code")):
            snapshots.run_ps = lambda arguments, fake=fake: fake
            try:
                alive = snapshots.owner_process_is_alive("100-5", platform="darwin")
                outcome = f"returned {alive}"
            except snapshots.WorkSnapshotError:
                outcome = "raised"
            check(outcome == "raised",
                  f"a ps failure ({why}) raises instead of counting the owner dead", outcome)
    finally:
        snapshots.run_ps = real_run_ps
    if shutil.which("ps") is None:
        return skip("ps on this machine reads a live and a gone process", "no ps here")
    check(snapshots.macos_start_seconds(os.getpid()) is not None,
          "ps on this machine gives a live process's start")
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    check(snapshots.macos_start_seconds(gone.pid) is None,
          "ps on this machine gives None for a process that is gone")


# ---------------------------------------------------------------- owners


def fake_proc(root, boot_id, processes, btime="1000"):
    """processes: pid -> (name, parent, start ticks)."""
    (root / "sys" / "kernel" / "random").mkdir(parents=True, exist_ok=True)
    (root / "sys" / "kernel" / "random" / "boot_id").write_text(boot_id + "\n")
    (root / "stat").write_text(f"cpu 1 2 3\nbtime {btime}\n")
    for pid, (name, parent, ticks) in processes.items():
        directory = root / str(pid)
        directory.mkdir(exist_ok=True)
        (directory / "comm").write_text(name + "\n")
        fields = ["S", str(parent)] + ["0"] * 17 + [str(ticks)] + ["0"] * 10
        (directory / "stat").write_text(f"{pid} ({name} with (spaces)) " + " ".join(fields))


def test_owner_liveness():
    root = SCRATCH / "fake-proc"
    boot = "1234abcd-0000-0000-0000-000000000000"
    fake_proc(root, boot, {300: ("python3", 200, 50), 200: ("sh", 100, 40),
                           100: ("claude", 1, 30)})
    linux = "linux"
    check(snapshots.claude_owner_process_id(300, str(root), linux) == 100,
          "the owner is the nearest ancestor named claude")
    key = snapshots.owner_key_of_process(100, str(root), linux)
    check(key == "1234abcd000000000000000000000000-100-30",
          "a Linux owner key is boot id, process id and start ticks", key)
    check(snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner process still running is alive")
    fake_proc(root, boot, {}, btime="999999")
    check(snapshots.owner_process_is_alive(key, str(root), linux),
          "a live owner still counts as alive after the system clock is stepped")
    fake_proc(root, boot, {100: ("claude", 1, 31)})
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "a reused process id with a different start counts as dead")
    fake_proc(root, "ffff" + boot[4:], {100: ("claude", 1, 30)})
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner from an earlier boot counts as dead")
    shutil.rmtree(root / "100")
    check(not snapshots.owner_process_is_alive(key, str(root), linux),
          "an owner process that is gone counts as dead")
    root2 = SCRATCH / "fake-proc-no-claude"
    fake_proc(root2, boot, {300: ("python3", 200, 50), 200: ("bash", 1, 40)})
    check(snapshots.claude_owner_process_id(300, str(root2), linux) is None,
          "no claude among the ancestors gives no owner")


def test_live_and_dead_owners_listed():
    name = "a dead owner's work-snapshots are listed, a live owner's are not"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    kept = add_worktree(main, main / ".claude" / "worktrees" / "kept", "kept-branch")
    removed = add_worktree(main, main / ".claude" / "worktrees" / "removed", "removed-branch")
    for worktree in (kept, removed):
        (worktree / "new.txt").write_text("work\n")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-two"})
    for worktree in (kept, removed):
        claude.run_hook(bash(worktree))
    handoffs = SCRATCH / "handoffs-listing"
    handoffs.mkdir()
    check(snapshots.first_prompt_text(main, "seat-two", handoffs) == "",
          "a live owner's work-snapshots are not listed")
    claude.end()
    git(main, "worktree", "remove", "--force", str(removed))
    text = snapshots.first_prompt_text(main, "seat-two", handoffs)
    check(str(kept) in text and str(removed) in text and "(is gone)" in text, name, text)
    check(snapshots.first_prompt_text(main, "another-seat", handoffs) == "",
          "another agent-seat's leftovers are not listed")


# ---------------------------------------------------------------- listing


def test_list_caps_and_failure():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "many", "many-branch")
    for number in range(12):
        (worktree / f"file-{number:02d}.txt").write_text("x\n")
    for number in range(21):
        snapshots.refresh_work_snapshot(worktree, f"{number + 10}-1", "seat-three", "")
    handoffs = SCRATCH / "handoffs-caps"
    handoffs.mkdir()
    text = snapshots.first_prompt_text(main, "seat-three", handoffs, now=1000,
                                       is_alive=lambda key: False)
    entries = [line for line in text.splitlines() if line.startswith("- refs/")]
    check(len(entries) == 20, "the list caps at 20 entries", len(entries))
    check("and 1 more; list them all with:" in text and "list --agent-seat seat-three" in text,
          "the rest are counted, with the command that lists them all")
    check(entries and entries[0].endswith("and 2 more"), "each entry names ten files and "
          "counts the rest", entries[:1])
    recorded = json.loads((handoffs / "seat-three-work-snapshots-first-listed.json").read_text())
    check(len(recorded) == 21 and set(recorded.values()) == {1000},
          "every listed work-snapshot's first listing is recorded", recorded)
    snapshots.first_prompt_text(main, "seat-three", handoffs, now=5000,
                                is_alive=lambda key: False)
    recorded = json.loads((handoffs / "seat-three-work-snapshots-first-listed.json").read_text())
    check(set(recorded.values()) == {1000}, "a later listing keeps the first listing's time")
    not_a_repository = SCRATCH / "not-a-repository"
    not_a_repository.mkdir()
    check(snapshots.first_prompt_text(not_a_repository, "seat-three", handoffs) == "",
          "a working directory outside any clone has no work-snapshots to list")

    def liveness_that_fails(key):
        raise snapshots.WorkSnapshotError("ps could not read process 10")

    failed = snapshots.first_prompt_text(main, "seat-three", handoffs,
                                         is_alive=liveness_that_fails)
    check("could not be listed" in failed and "list --agent-seat seat-three" in failed,
          "a failure to build the list is stated, with the list command", failed)
    blocked = SCRATCH / "handoffs-blocked"
    blocked.write_text("a file where the handoff directory should be")
    text = snapshots.first_prompt_text(main, "seat-three", blocked, is_alive=lambda key: False)
    check("could not be recorded" in text and "never listed" in text,
          "a failure to record the first listing is said in the prompt", text[-300:])


def test_supervisor_appends_the_list():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "new.txt").write_text("work\n")
    snapshots.refresh_work_snapshot(worktree, "1-1", "seat-four", "")
    fixture = load(SYSTEM_DIRECTORY / "tests" / "handoff-supervisor-test-fixture.py",
                   "handoff_supervisor_test_fixture")
    supervisor = fixture.supervisor
    supervisor.uncommitted_work_snapshots.owner_process_is_alive = (
        lambda key, *rest, **keywords: False)
    handoffs = SCRATCH / "handoffs-supervisor"
    handoffs.mkdir()
    text = supervisor.uncommitted_work_snapshot_text("seat-four", main, handoffs)
    check(text.startswith("Leftover work-snapshots: 1") and "Handle each of them" in text,
          "the handoff-supervisor builds the leftover list with the restore steps", text[:200])
    launched = []
    supervisor.launch_agent_session = (
        lambda command, session_id, working_directory, prompt, **keywords:
        launched.append(prompt) or (_ for _ in ()).throw(StopIteration()))
    supervisor.sync_working_branch_with_main = lambda working_directory: "branch sync: test"
    settings = supervisor.SupervisorSettings(
        agent="seat-four", working_directory=main, handoff_directory=handoffs,
        agent_command="claude", first_prompt="Founding prompt.",
        first_prompt_wins_over_crashed_transcript=True, agent_update_timeout_seconds=0)
    try:
        supervisor.supervise_sessions(settings)
    except StopIteration:
        pass
    check(launched and launched[0].startswith("Founding prompt.\n\nLeftover work-snapshots: 1"),
          "every launch's prompt carries the leftover list after the prompt",
          launched[:1] and launched[0][:120])


# ---------------------------------------------------------------- restore


def restore_steps_commit(main, ref, keep, into_new_worktree):
    """Follow the restore steps' commands; return (the commit's directory, its branch)."""
    module = main / MODULE_RELATIVE
    if not into_new_worktree:
        snapshot = next(s for s in snapshots.all_work_snapshots(main) if s["ref"] == ref)
        worktree = Path(snapshot["worktree"])
        matches = subprocess.run([sys.executable, str(module), "matches", ref, "--repo",
                                  str(main)], capture_output=True, text=True)
        if matches.stdout.strip() != "yes":
            raise RuntimeError(f"matches said {matches.stdout!r} {matches.stderr!r}")
        git(worktree, "add", "-A", "--", *keep)
        git(worktree, "commit", "-q", "-m", f"Restore work from {ref}")
        dropped_tracked = [path for path in
                           git(worktree, "diff", "--name-only", "HEAD").split() if path]
        if dropped_tracked:
            git(worktree, "restore", "--source=HEAD", "--staged", "--worktree", "--",
                *dropped_tracked)
        for path in git(worktree, "ls-files", "--others", "--exclude-standard").split():
            (worktree / path).unlink()
        return worktree
    name = "restored-" + "-".join(ref.split("/")[-2:])
    clone = Path(git(main, "rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    target = clone / ".claude" / "worktrees" / name
    git(main, "worktree", "add", "-q", "-b", name, str(target), f"{ref}^")
    diff = subprocess.run(["git", "-C", str(target), "diff", "--binary", f"{ref}^", ref, "--",
                           *keep], capture_output=True, check=True).stdout
    subprocess.run(["git", "-C", str(target), "apply", "--index"], input=diff, check=True)
    git(target, "commit", "-q", "-m", f"Restore work from {ref}")
    return target


def test_restore_a_subset():
    for into_new in (False, True):
        where = "into a new worktree from <ref>^" if into_new else "in the surviving worktree"
        main = new_clone()
        worktree = add_worktree(main, main / ".claude" / "worktrees" / f"fork-{into_new}",
                                f"fork-{into_new}")
        (worktree / "tracked.txt").write_text("kept change\n")
        (worktree / "doomed.txt").unlink()
        (worktree / "new.txt").write_text("kept new\n")
        (worktree / "mutant.txt").write_text("a mutant to drop\n")
        snapshots.refresh_work_snapshot(worktree, "7-7", "seat-five", "")
        ref = snapshots.work_snapshot_ref("7-7", worktree)
        if into_new:
            git(main, "worktree", "remove", "--force", str(worktree))
        target = restore_steps_commit(main, ref, ["tracked.txt", "doomed.txt", "new.txt"],
                                      into_new)
        changed = git(target, "diff-tree", "-r", "--no-commit-id", "--name-status",
                      "HEAD").splitlines()
        check(sorted(changed) == ["A\tnew.txt", "D\tdoomed.txt", "M\ttracked.txt"],
              f"restoring a chosen subset {where} commits exactly those changes", changed)
        check(git(target, "status", "--porcelain") == "",
              f"nothing dropped is left behind {where}")
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "drift", "drift")
    (worktree / "new.txt").write_text("work\n")
    snapshots.refresh_work_snapshot(worktree, "8-8", "seat", "")
    ref = snapshots.work_snapshot_ref("8-8", worktree)
    check(snapshots.worktree_still_matches(main, ref), "matches says yes for an unchanged worktree")
    (worktree / "new.txt").write_text("changed since\n")
    check(not snapshots.worktree_still_matches(main, ref),
          "matches says no once the worktree has changed")
    (worktree / "new.txt").write_text("work\n")
    git(worktree, "add", "-A")
    git(worktree, "commit", "-q", "-m", "the same changes, committed")
    check(not snapshots.worktree_still_matches(main, ref),
          "matches says no once the changes are committed, though the tree is the same")


# ---------------------------------------------------------------- cleaner


def test_cleaner():
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "fork", "fork-branch")
    (worktree / "new.txt").write_text("work\n")
    owners = {"old": "11-1", "recent": "12-1", "never": "13-1", "alive": "14-1"}
    for owner in owners.values():
        snapshots.refresh_work_snapshot(worktree, owner, "seat-six", "")
    refs = {label: snapshots.work_snapshot_ref(owner, worktree)
            for label, owner in owners.items()}
    now = 100 * 86400
    handoffs = SCRATCH / "handoffs-cleaner"
    handoffs.mkdir()
    (handoffs / "seat-six-work-snapshots-first-listed.json").write_text(json.dumps({
        refs["old"]: now - 11 * 86400, refs["recent"]: now - 5 * 86400,
        refs["alive"]: now - 30 * 86400}))
    alive = lambda key: key == owners["alive"]
    report = []
    failures_seen = snapshots.clean_leftover_work_snapshots(
        main, remove=False, only_due=False, handoff_directory=handoffs, now=now,
        is_alive=alive, out=report.append)
    check(failures_seen == 0 and set(refs_of(main)) == set(refs.values()),
          "run without --remove it deletes nothing", report)
    check(any(refs["old"] in line and "due for deletion" in line for line in report)
          and any(refs["never"] in line and "never listed" in line for line in report),
          "it reports leftovers with whether and when they were listed", report)
    check(not any(refs["alive"] in line for line in report),
          "a live owner's work-snapshot is not reported", report)
    report = []
    snapshots.clean_leftover_work_snapshots(
        main, remove=True, only_due=False, handoff_directory=handoffs, now=now,
        is_alive=alive, out=report.append)
    left = set(refs_of(main))
    check(refs["old"] not in left and any(refs["old"] in line and "deleted" in line
                                         and "new.txt" in line for line in report),
          "the cleaner deletes a dead owner's work-snapshot first listed more than 10 days "
          "ago, naming it and its files", report)
    check({refs["recent"], refs["never"], refs["alive"]} <= left,
          "it keeps one listed more recently, one never listed, and a live owner's one", left)
    report = []
    count = snapshots.clean_leftover_work_snapshots(
        SCRATCH / "not-a-repository", remove=True, only_due=False,
        handoff_directory=handoffs, now=now, is_alive=alive, out=report.append)
    check(count == 1 and "could not be listed" in report[0],
          "a failure to list work-snapshots is said and counted", report)


# ---------------------------------------------------------------- replay


def test_the_2026_10_05_loss_replayed():
    name = "the 2026-10-05 loss replayed: the restore brings both files back as a commit"
    if not CLAUDE_STAND_IN_WORKS:
        return skip(name, "the claude stand-in is named after its shell on this platform")
    main = new_clone()
    worktree = add_worktree(main, main / ".claude" / "worktrees" / "concurrency-step-1",
                            "concurrency-step-1")
    (worktree / "tracked.txt").write_text("edited by the fork\n")
    (worktree / "new-test.py").write_text("print('a new test')\n")
    claude = ClaudeStandIn(main, {"GIT_AUTHOR_NAME": "seat-seven"})
    claude.run_hook(edit(worktree / "tracked.txt"))
    claude.run_hook(edit(worktree / "new-test.py"))
    claude.end()
    cleaner = subprocess.run([sys.executable, str(main / CLEANER_RELATIVE), "--remove"],
                             capture_output=True, text=True, cwd=main)
    check(not worktree.exists(), "the cleaner removes the dead fork's worktree, as on "
          "2026-10-05", cleaner.stdout + cleaner.stderr)
    check("work-snapshot refs/work-snapshots/" in cleaner.stdout
          and "never listed in a first prompt" in cleaner.stdout,
          "the cleaner reports the work-snapshot it keeps", cleaner.stdout)
    handoffs = HOME / ".claude" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    text = snapshots.first_prompt_text(main, "seat-seven", handoffs)
    refs = [line.split(":")[0][2:] for line in text.splitlines() if line.startswith("- refs/")]
    check(len(refs) == 1 and "(is gone)" in text,
          "the next agent-session's first prompt lists the work-snapshot", text[:300])
    if refs:
        target = restore_steps_commit(main, refs[0], ["tracked.txt", "new-test.py"], True)
        check(git(target, "show", "HEAD:tracked.txt") == "edited by the fork"
              and git(target, "show", "HEAD:new-test.py") == "print('a new test')",
              name)
        git(main, "update-ref", "-d", refs[0])
        check(refs_of(main) == [], "step 4 deletes the ref")


def main():
    try:
        for case in (test_what_a_work_snapshot_holds, test_same_size_edit_in_the_index_second,
                     test_ref_names,
                     test_bash_commit_deletes_and_other_worktrees_follow,
                     test_overlapping_runs_end_on_the_final_state, test_operation_trailer,
                     test_hook_failure_is_reported, test_other_repository_is_untouched,
                     test_worktree_discovery_failure_is_reported,
                     test_module_load_failure_is_reported, test_owner_liveness,
                     test_macos_ps_failure_is_not_a_dead_owner,
                     test_live_and_dead_owners_listed, test_list_caps_and_failure,
                     test_supervisor_appends_the_list, test_restore_a_subset, test_cleaner,
                     test_the_2026_10_05_loss_replayed):
            try:
                case()
            except Exception as error:
                check(False, f"{case.__name__} raised", f"{type(error).__name__}: {error}")
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
