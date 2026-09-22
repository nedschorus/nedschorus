#!/usr/bin/env python3
"""Tests for file-name-collision-warning-hook.py.

Run: python3 scripts/file-name-collision-warning-hook-test.py
Prints one line per case and exits non-zero if any case fails.

Every case but the last runs against a throwaway repository under a
temporary directory. The last case is different in kind: it asserts the
property on THIS repository -- that no two tracked files share a name -- and
is the half of the ruling a hook cannot cover, because a file created by
git mv, by a shell copy, or by a program that writes its own files never
passes through the Edit or Write tools.

THE FIRST CASE IS THE POSITIVE ONE, deliberately. A check that has never
been shown able to say "something here" is worth nothing when it says
"nothing here"; that failure has been found repeatedly across this fleet, so
the instrument proves it can warn before any case asserts silence.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("file-name-collision-warning-hook.py")
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(arguments, cwd: Path):
    return subprocess.run(["git", *arguments], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


def commit_file(repository: Path, name: str, content: str = "x\n"):
    (repository / name).parent.mkdir(parents=True, exist_ok=True)
    (repository / name).write_text(content, encoding="utf-8")
    git(["add", "--", name], repository)
    git(["commit", "-q", "-m", f"add {name}"], repository)


def write_file(repository: Path, name: str, content: str = "new\n") -> Path:
    """A file on disk that git does not know about: what an agent's Write
    leaves behind before anyone commits."""
    target = repository / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def hook_payload(cwd, file_path, tool_name="Write") -> dict:
    """The shape a PostToolUse hook is handed: the session's own cwd, the
    tool's name, and tool_input.file_path -- absolute for both Edit and
    Write."""
    return {
        "session_id": "file-name-collision-warning-test-session",
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path), "success": True},
    }


def run_hook(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], input=text,
                          capture_output=True, text=True, check=False,
                          env=dict(os.environ))


def agent_text(result) -> str:
    """What the AGENT was told. Plain stdout on a PostToolUse hook reaches
    the debug log and nobody else; only hookSpecificOutput.additionalContext
    arrives."""
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


def silent(result) -> bool:
    return result.returncode == 0 and result.stdout.strip() == ""


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory).resolve()
    repository = tmp / "checkout"
    repository.mkdir()
    git(["init", "-q", "-b", "main"], repository)
    git(["config", "user.email", "test@example.invalid"], repository)
    git(["config", "user.name", "file-name-collision test"], repository)

    commit_file(repository, "scripts/cold-read-grid.py")
    commit_file(repository, "scripts/only-one-of-these.py")
    commit_file(repository, ".claude/skills/walk-me-through/SKILL.md")
    commit_file(repository, "docs/README.md")
    commit_file(repository, "nc-queue/.gitkeep")
    commit_file(repository, ".gitignore", "docs/walk/\ncold-read-records/\n")

    # --- the instrument can say "something here" ------------------------
    colliding = write_file(repository, "nc-systems/cold-read/cold-read-grid.py")
    warned = run_hook(hook_payload(repository, colliding))
    warning = agent_text(warned)
    check("a new file whose name is already a tracked file's warns",
          warning != "", f"stdout was {warned.stdout!r}")
    check("the warning names BOTH paths, so no search is needed",
          "nc-systems/cold-read/cold-read-grid.py" in warning
          and "scripts/cold-read-grid.py" in warning, warning)
    check("the warning arrives on additionalContext under PostToolUse",
          (json.loads(warned.stdout or "{}").get("hookSpecificOutput", {})
           .get("hookEventName")) == "PostToolUse", warned.stdout)
    check("the hook exits 0 even when it warns (a warning never fails a turn)",
          warned.returncode == 0, str(warned.returncode))

    # --- the two instructions, each with its condition -------------------
    check("line 2 tells a mover to delete the old path, naming it",
          "If you are moving the file, delete scripts/cold-read-grid.py "
          "in this change." in warning, warning)
    check("line 3 points at CLAUDE.md's naming rule instead of restating it",
          "rename the one you just wrote by CLAUDE.md's naming rule" in warning
          and "3 or 4 parts" not in warning and "three or four" not in warning,
          warning)

    # --- silence, each for its own reason --------------------------------
    fresh = write_file(repository, "scripts/nothing-shares-this-name.py")
    check("a name that matches no tracked file is silent",
          silent(run_hook(hook_payload(repository, fresh))))

    existing = repository / "scripts" / "only-one-of-these.py"
    check("editing the only file with that name is silent",
          silent(run_hook(hook_payload(repository, existing, "Edit"))))

    for exempt in ("nc-systems/handoff/SKILL.md", "scripts/README.md",
                   "docs/.gitkeep"):
        written = write_file(repository, exempt)
        check(f"the exempt name {Path(exempt).name} is silent",
              silent(run_hook(hook_payload(repository, written))))

    ignored = write_file(repository,
                         "docs/walk/cold-read-grid.py")
    check("a write inside a gitignored directory is silent",
          silent(run_hook(hook_payload(repository, ignored))))

    outside = tmp / "scratchpad" / "cold-read-grid.py"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("scratch\n", encoding="utf-8")
    check("a write outside the checkout is silent",
          silent(run_hook(hook_payload(repository, outside))))

    not_a_repository = tmp / "loose"
    not_a_repository.mkdir()
    loose_file = not_a_repository / "cold-read-grid.py"
    loose_file.write_text("loose\n", encoding="utf-8")
    check("a session seated outside any checkout is silent",
          silent(run_hook(hook_payload(not_a_repository, loose_file))))

    # --- the Mac's filesystem ignores case, ned-box does not -------------
    cased = write_file(repository, "nc-systems/Cold-Read-Grid.PY")
    check("a name differing only in letter case warns",
          agent_text(run_hook(hook_payload(repository, cased))) != "",
          "case-insensitive comparison did not fire")

    # --- malformed payloads cost nothing and say nothing ------------------
    check("a payload that is not JSON exits 0 and prints nothing",
          silent(run_hook("not json at all")))
    no_tool_input = hook_payload(repository, colliding)
    del no_tool_input["tool_input"]
    check("a payload with no tool_input exits 0 and prints nothing",
          silent(run_hook(no_tool_input)))
    no_cwd = hook_payload(repository, colliding)
    del no_cwd["cwd"]
    check("a payload with no cwd exits 0 and prints nothing",
          silent(run_hook(no_cwd)))
    empty_path = hook_payload(repository, colliding)
    empty_path["tool_input"] = {"file_path": ""}
    check("a payload with an empty file_path exits 0 and prints nothing",
          silent(run_hook(empty_path)))

# --- the half a hook cannot cover: this repository, as it stands ---------
listing = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPOSITORY_ROOT),
                         capture_output=True, text=True, check=False)
names = {}
for tracked in listing.stdout.split("\0"):
    if tracked:
        names.setdefault(Path(tracked).name.lower(), []).append(tracked)
exempt_names = {"skill.md", "readme.md", ".gitkeep"}
collisions = {name: paths for name, paths in names.items()
              if len(paths) > 1 and name not in exempt_names}
check("no two tracked files in this repository share a name",
      not collisions,
      "; ".join(f"{name}: {', '.join(paths)}"
                for name, paths in sorted(collisions.items())))

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
