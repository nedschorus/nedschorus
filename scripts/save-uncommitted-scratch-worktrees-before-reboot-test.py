#!/usr/bin/env python3
"""Tests for scripts/save-uncommitted-scratch-worktrees-before-reboot.py.

A scratch clone gets worktrees under a scratch "tmp" root: dirty ones, a
clean one, one whose path names no agent-seat, and a dirty one outside the
root. LOCAL mode saves into a scratch store; REMOTE mode goes through stub
ssh and scp on PATH that act on scratch directories. Nothing here touches
ned-box, the log-store or a real clone.

Run: python3 scripts/save-uncommitted-scratch-worktrees-before-reboot-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SAVER = SCRIPTS_DIR / "save-uncommitted-scratch-worktrees-before-reboot.py"

# Stub ssh runs the remote command locally; stub scp copies to the local path
# after "host:". SAVER_TEST_SCP_EXIT makes scp fail; SAVER_TEST_SCP_CORRUPT
# makes it alter what it copies.
STUB_SSH = """#!/usr/bin/env python3
import subprocess, sys
arguments = sys.argv[1:]
while arguments and arguments[0] == "-o":
    arguments = arguments[2:]
sys.exit(subprocess.run(["sh", "-c", " ".join(arguments[1:])]).returncode)
"""
STUB_SCP = """#!/usr/bin/env python3
import os, shutil, sys
if os.environ.get("SAVER_TEST_SCP_EXIT"):
    sys.stderr.write("scp: stub refused\\n")
    sys.exit(int(os.environ["SAVER_TEST_SCP_EXIT"]))
arguments = [a for a in sys.argv[1:] if a != "-q"]
cleaned = []
while arguments:
    if arguments[0] == "-o":
        arguments = arguments[2:]
        continue
    cleaned.append(arguments.pop(0))
target = cleaned[-1].split(":", 1)[1]
for source in cleaned[:-1]:
    destination = os.path.join(target, os.path.basename(source))
    shutil.copyfile(source, destination)
    if os.environ.get("SAVER_TEST_SCP_CORRUPT"):
        with open(destination, "ab") as handle:
            handle.write(b"x")
"""

failures = []


def check(case_name, condition, detail=""):
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail}")


def git(*arguments, cwd):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)


def make_clone(root):
    clone = root / "clone"
    clone.mkdir()
    git("init", "-q", "-b", "main", cwd=clone)
    git("config", "user.name", "saver test", cwd=clone)
    git("config", "user.email", "saver-test@example.invalid", cwd=clone)
    (clone / "tracked.txt").write_text("one\n")
    (clone / ".gitignore").write_text("ignored.log\n")
    git("add", ".", cwd=clone)
    git("commit", "-q", "-m", "first", cwd=clone)
    return clone


def add_worktree(clone, path, branch):
    path.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "-b", branch, str(path), cwd=clone)
    return path


def run_saver(clone, destination, roots, extra_env=None):
    environment = dict(os.environ)
    environment.update(extra_env or {})
    command = [sys.executable, str(SAVER), "--clone", str(clone), "--destination", destination]
    for root in roots:
        command += ["--scratch-root", str(root)]
    return subprocess.run(command, capture_output=True, text=True, check=False, env=environment)


def saves_under(seat_root):
    return sorted(p for p in seat_root.glob("pre-reboot-*") if p.is_dir()) if seat_root.exists() else []


with tempfile.TemporaryDirectory(prefix="pre-reboot-saver-test-") as scratch_name:
    scratch = pathlib.Path(scratch_name).resolve()
    tmp_root = scratch / "tmp"
    clone = make_clone(scratch)

    dirty = add_worktree(clone, tmp_root / "claude-501" / "-Users-el-agents-merge-lane-2" / "u1"
                         / "scratchpad" / "wt-dirty", "dirty-branch")
    (dirty / "tracked.txt").write_text("one\ntwo\n")
    (dirty / "new-untracked.md").write_text("not yet added\n")
    (dirty / "sub").mkdir()
    (dirty / "sub" / "deeper.txt").write_text("deep\n")
    (dirty / "ignored.log").write_text("ignored\n")
    (dirty / "staged.txt").write_text("staged\n")
    git("add", "staged.txt", cwd=dirty)

    clean = add_worktree(clone, tmp_root / "claude-1000" / "-home-nedlern-agents-beta" / "u2"
                         / "scratchpad" / "wt-clean", "clean-branch")
    noseat = add_worktree(clone, tmp_root / "elsewhere" / "wt-noseat", "noseat-branch")
    (noseat / "tracked.txt").write_text("changed\n")
    outside = add_worktree(clone, scratch / "outside" / "wt-out", "outside-branch")
    (outside / "tracked.txt").write_text("outside change\n")

    # --- LOCAL mode -------------------------------------------------------
    store = scratch / "store"
    result = run_saver(clone, str(store), [tmp_root])
    output = result.stdout
    check("local: exit 0 when every dirty worktree was saved", result.returncode == 0,
          output + result.stderr)
    check("local: the dirty worktree is SAVED", f"SAVED    {dirty}" in output, output)
    check("local: the clean worktree is reported CLEAN and not saved",
          f"CLEAN    {clean}" in output and not (store / "beta").exists(), output)
    check("local: the dirty worktree outside the scratch root, and the clone itself, are not looked at",
          str(outside) not in output and "2 worktree(s) outside" in output, output)
    check("local: the summary counts two saved, one clean, none failed",
          "SUMMARY: 2 saved, 1 clean, 0 failed" in output, output)

    seat_saves = saves_under(store / "merge-lane-2")
    check("local: the save is under seats/<seat>/pre-reboot-<date>/ for the seat in the path",
          len(seat_saves) == 1, str(list(store.rglob("*"))))
    saved_dirs = [p for p in seat_saves[0].iterdir()] if seat_saves else []
    saved_dir = saved_dirs[0] if saved_dirs else scratch / "missing"
    manifest = json.loads((saved_dir / "manifest.json").read_text()) if (saved_dir / "manifest.json").exists() else {}
    check("local: the manifest names the worktree, branch, head and seat",
          manifest.get("worktree") == str(dirty) and manifest.get("branch") == "refs/heads/dirty-branch"
          and len(manifest.get("head") or "") == 40 and manifest.get("seat") == "merge-lane-2", str(manifest))
    check("local: the manifest lists sizes and sha256 of the diff and the tar",
          [entry["name"] for entry in manifest.get("saved", [])] == ["changes.diff", "untracked.tar"]
          and all(len(entry["sha256"]) == 64 for entry in manifest.get("saved", [])), str(manifest))
    diff_text = (saved_dir / "changes.diff").read_text() if (saved_dir / "changes.diff").exists() else ""
    check("local: the diff holds the tracked edit and the staged new file",
          "+two" in diff_text and "staged.txt" in diff_text, diff_text)
    members = []
    if (saved_dir / "untracked.tar").exists():
        with tarfile.open(saved_dir / "untracked.tar") as archive:
            members = sorted(archive.getnames())
    check("local: the tar holds the untracked files and not the ignored one",
          members == ["new-untracked.md", "sub/deeper.txt"], str(members))
    check("local: the worktree with no agent-seat in its path is saved as unknown-seat and said so",
          len(saves_under(store / "unknown-seat")) == 1 and "(no agent-seat in its path)" in output, output)

    restore = scratch / "restore"
    git("worktree", "add", "-q", "--detach", str(restore), manifest.get("head", "HEAD"), cwd=clone)
    applied = subprocess.run(["git", "apply", str(saved_dir / "changes.diff")], cwd=restore,
                             capture_output=True, text=True)
    check("local: the saved diff applies at the manifest's head and brings back the edit",
          applied.returncode == 0 and (restore / "tracked.txt").read_text() == "one\ntwo\n",
          applied.stderr)
    git("worktree", "remove", "--force", str(restore), cwd=clone)

    check("local: the worktrees are left as they were",
          (dirty / "tracked.txt").read_text() == "one\ntwo\n" and (dirty / "new-untracked.md").exists())

    result = run_saver(clone, str(store), [tmp_root])
    second = saves_under(store / "merge-lane-2")
    check("local: a second run on the same day saves into pre-reboot-<date>-2 and keeps the first",
          result.returncode == 0 and len(second) == 2 and second[1].name.endswith("-2")
          and (seat_saves[0] / saved_dir.name / "manifest.json").exists(), result.stdout)

    # --- REMOTE mode, stub ssh and scp -----------------------------------
    stubs = scratch / "stub-bin"
    stubs.mkdir()
    for name, text in (("ssh", STUB_SSH), ("scp", STUB_SCP)):
        (stubs / name).write_text(text)
        (stubs / name).chmod(0o755)
    remote_env = {"PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    remote_store = scratch / "remote-store"
    result = run_saver(clone, f"fakehost:{remote_store}", [tmp_root], remote_env)
    check("remote: exit 0 and the save reached the far side, verified",
          result.returncode == 0 and len(saves_under(remote_store / "merge-lane-2")) == 1
          and f"-> fakehost:{remote_store}/merge-lane-2/pre-reboot-" in result.stdout
          and "copy verified" in result.stdout, result.stdout + result.stderr)

    result = run_saver(clone, f"fakehost:{scratch / 'remote-corrupt'}", [tmp_root],
                       dict(remote_env, SAVER_TEST_SCP_CORRUPT="1"))
    check("remote: a copy whose checksum does not match is FAILED and exits 1",
          result.returncode == 1 and "does not match its checksum" in result.stdout
          and "SUMMARY: 0 saved, 1 clean, 2 failed" in result.stdout, result.stdout)

    result = run_saver(clone, f"fakehost:{scratch / 'remote-refused'}", [tmp_root],
                       dict(remote_env, SAVER_TEST_SCP_EXIT="1"))
    check("remote: a copy that fails is FAILED naming the copy and exits 1",
          result.returncode == 1 and "could not copy to fakehost:" in result.stdout
          and "stub refused" in result.stdout, result.stdout)

    # --- a gone worktree, a broken one, a nested repository, no diff -----
    # Worktrees are handled in path order, so the gone and broken ones come
    # before the dirty one: a loop that stopped at either would not save it.
    clone_two = scratch / "clone-two-parent"
    clone_two.mkdir()
    clone_two = make_clone(clone_two)
    tmp_two = scratch / "tmp-two"
    gone = add_worktree(clone_two, tmp_two / "aaa-gone", "gone-branch")
    subprocess.run(["rm", "-rf", str(gone)], check=True)
    broken = add_worktree(clone_two, tmp_two / "aab-broken", "broken-branch")
    (broken / ".git").write_text(f"gitdir: {scratch / 'no-such-gitdir'}\n")
    # Under "zzz-", so it sorts after both failure fixtures ("-" sorts before "a").
    untracked_only = add_worktree(clone_two, tmp_two / "zzz-scratch" / "-home-nedlern-agents-gamma"
                                  / "wt-untracked",
                                  "untracked-branch")
    nested = untracked_only / "nested"
    nested.mkdir()
    git("init", "-q", cwd=nested)
    (nested / "inner.txt").write_text("nested work\n")
    (untracked_only / "loose.txt").write_text("loose\n")
    store_two = scratch / "store-two"
    result = run_saver(clone_two, str(store_two), [tmp_two])
    output = result.stdout
    check("a registered worktree whose directory is gone is reported GONE and the run goes on",
          f"GONE     {gone}" in output and f"SAVED    {untracked_only}" in output, output)
    check("a worktree where git fails is FAILED naming git, and the run goes on to the next",
          f"FAILED   {broken}: git status --porcelain" in output
          and f"SAVED    {untracked_only}" in output and "Traceback" not in result.stderr,
          output + result.stderr)
    check("a worktree where git fails makes the run exit 1",
          result.returncode == 1 and "SUMMARY: 1 saved, 0 clean, 1 failed" in output, output)
    gamma_saves = saves_under(store_two / "gamma")
    gamma_dir = next(gamma_saves[0].iterdir()) if gamma_saves else scratch / "missing"
    gamma_manifest = (json.loads((gamma_dir / "manifest.json").read_text())
                      if (gamma_dir / "manifest.json").exists() else {})
    check("an untracked-only save writes no changes.diff and its manifest says so",
          not (gamma_dir / "changes.diff").exists() and gamma_manifest.get("diff_written") is False
          and [entry["name"] for entry in gamma_manifest.get("saved", [])] == ["untracked.tar"],
          str(gamma_manifest) + str(list(gamma_dir.iterdir()) if gamma_dir.exists() else ""))
    gamma_members = []
    if (gamma_dir / "untracked.tar").exists():
        with tarfile.open(gamma_dir / "untracked.tar") as archive:
            gamma_members = archive.getnames()
    check("an untracked nested repository is in the tar whole, its .git included",
          "nested/inner.txt" in gamma_members and "nested/.git/HEAD" in gamma_members
          and "loose.txt" in gamma_members, str(gamma_members))
    check("the manifest lists the nested repository",
          gamma_manifest.get("nested_repositories") == ["nested"], str(gamma_manifest))
    restore_two = scratch / "restore-two"
    git("worktree", "add", "-q", "--detach", str(restore_two), gamma_manifest.get("head", "HEAD"),
        cwd=clone_two)
    extracted = subprocess.run(["tar", "-xf", str(gamma_dir / "untracked.tar")], cwd=restore_two,
                               capture_output=True, text=True)
    check("the untracked-only save comes back with tar alone, nested repository included",
          extracted.returncode == 0 and (restore_two / "nested" / "inner.txt").is_file()
          and (restore_two / "nested" / "inner.txt").read_text() == "nested work\n"
          and (restore_two / "loose.txt").exists(), extracted.stderr)

    # --- which destination is local --------------------------------------
    saver_spec = importlib.util.spec_from_file_location("pre_reboot_saver", SAVER)
    saver = importlib.util.module_from_spec(saver_spec)
    saver_spec.loader.exec_module(saver)
    default = saver.DEFAULT_DESTINATION
    store_path = default.split(":", 1)[1]
    check("on ned-box the default destination is a local copy",
          saver.copy_host_and_store(default, "ned-box") == (None, store_path)
          and saver.copy_host_and_store(default, "ned-box.local") == (None, store_path))
    check("elsewhere the default destination goes over ssh to ned-box",
          saver.copy_host_and_store(default, "Edwards-MacBook-Air") == ("nedlern@ned-box", store_path)
          and saver.copy_host_and_store(default, "ned-box2") == ("nedlern@ned-box", store_path))
    check("on ned-box a destination given by hand is used as given",
          saver.copy_host_and_store("otherhost:/srv/store", "ned-box") == ("otherhost", "/srv/store")
          and saver.copy_host_and_store("/local/store", "ned-box") == (None, "/local/store"))

    # --- invocation and help ---------------------------------------------
    result = run_saver(scratch / "not-a-clone", str(store), [tmp_root])
    check("a clone that cannot be read exits 2 naming it",
          result.returncode == 2 and "could not list the worktrees" in result.stdout, result.stdout)
    help_text = subprocess.run([sys.executable, str(SAVER), "--help"], capture_output=True,
                               text=True).stdout
    check("--help carries the restart procedure",
          "THE RESTART PROCEDURE" in help_text and "pgrep -fl 'git push|codex exec'" in help_text
          and "scripts/restart-live-seats-at-login.py" in help_text
          and "-supervisor-state.json" in help_text, help_text[:300])
    check("the restart program --help names exists",
          (SCRIPTS_DIR / "restart-live-seats-at-login.py").exists())

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
