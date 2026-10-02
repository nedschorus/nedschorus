#!/usr/bin/env python3
"""Check declared changes into main, or return a refusal with a fix."""

# Keep union annotations unevaluated so this module imports under Python 3.9.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WORKSPACE_ROOT_NAME = "nedschorus-gatekeeper"
CANDIDATE_BRANCH = "main-gatekeeper-candidate"
MAIN_BRANCH = "main"

FULL_COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")
ISSUE_NUMBER = re.compile(r"^[1-9][0-9]*$")

# Tightening accepted path rules later would strand existing history.
UNSAFE_PATH_MARKER = "->"

# The deployed gate updates itself from main; its own source must receive independent review by pull request.
GATEKEEPER_SOURCE_PATH = "nc-systems/main-gatekeeper/main-gatekeeper.py"

MAX_INTEGRATION_ROUNDS = 5

EXIT_SUCCESS = 0
EXIT_REFUSED = 1
EXIT_DEFECT = 2

# An unreadable worker PID is not evidence that a workspace is safe to destroy.
LIVE_STATES = ("alive", "unknown")


class Refusal(Exception):
    """A catalog refusal carrying facts and a specific next action."""

    def __init__(self, error: str, facts: str, next_action: str):
        super().__init__(f"{error}: {facts}")
        self.error = error
        self.facts = facts
        self.next_action = next_action


class AlreadyCheckedIn(Exception):
    """The requested work reached main while the request was in flight."""

    def __init__(self, commit: str):
        super().__init__(commit)
        self.commit = commit


def workspace_root() -> Path:
    """Return the host-local workspace root outside the repositories."""
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / WORKSPACE_ROOT_NAME


def workspace_for(digest: str) -> Path | None:
    """Return the workspace matching a digest, or None."""
    # Enumerate names instead of joining caller input, which could escape the root.
    try:
        entries = list(workspace_root().iterdir())
    except OSError:
        return None
    return next((entry for entry in entries
                 if entry.name == digest and entry.is_dir()), None)


def emit(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload))
    return exit_code


def run_git(arguments: list[str], cwd: Path | None = None, check: bool = True):
    """Return the git process result with stdout and stderr as text."""
    completed = subprocess.run(
        ["git", *arguments], cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, check=False,
    )
    if check and completed.returncode != 0:
        raise Refusal(
            "workspace-io-error",
            f"git {' '.join(arguments)} failed: {completed.stderr.strip() or 'no stderr'}",
            "Resubmit the same request; this class of failure is safe to retry.",
        )
    return completed


# Screen in memory so malformed requests leave no disk state.


def screen_unsafe_path(path: str, position: str) -> None:
    if any(character.isspace() for character in path):
        detail = "whitespace"
    elif UNSAFE_PATH_MARKER in path:
        detail = f"the sequence {UNSAFE_PATH_MARKER!r}, which is the import trailer's separator"
    elif not path.isascii():
        detail = "a non-ASCII byte"
    elif not path.isprintable():
        detail = "a non-printable byte"
    else:
        return
    raise Refusal(
        "malformed-field",
        f"the {position} path {path!r} contains {detail}",
        "Rename the path so it contains only printable ASCII without whitespace, "
        "then resubmit. Paths of this shape are refused rather than quoted because "
        "the trailer format is unquoted; quoting grows in when a real import needs it.",
    )


def screen_gatekeeper_source_path(path: str) -> None:
    # Case-fold to prevent a case variant from overwriting the gate on case-insensitive checkouts.
    if Path(path).as_posix().casefold() != GATEKEEPER_SOURCE_PATH.casefold():
        return
    raise Refusal(
        "gatekeeper-source-refused",
        f"the declared path {GATEKEEPER_SOURCE_PATH!r} is this program's own source, "
        "which the gatekeeper does not check in",
        "Take this change through the pull-request lane instead: commit it on a "
        "branch, push the branch, and open a pull request for review before merge. "
        "Resubmitting this check-in unchanged refuses again; the refusal is by "
        "design, not a defect. If the request also carries unrelated paths, "
        "resubmit those as their own check-in.",
    )


def screen_paths(raw_paths: list[str]) -> list[str]:
    if not raw_paths:
        raise Refusal(
            "malformed-field", "the --files list is empty",
            "Resubmit with --files naming at least one repository-relative path.",
        )

    seen: set[str] = set()
    for path in raw_paths:
        screen_unsafe_path(path, "declared")
        if path.startswith("/"):
            raise Refusal(
                "malformed-field", f"the path {path!r} is absolute",
                "Resubmit with the path written relative to the repository root.",
            )
        parts = Path(path).parts
        if ".." in parts:
            raise Refusal(
                "malformed-field", f"the path {path!r} contains '..'",
                "Resubmit with the path written relative to the repository root, "
                "without parent-directory segments.",
            )
        if parts and parts[0] == ".git":
            raise Refusal(
                "malformed-field", f"the path {path!r} is inside .git/",
                "Resubmit without it; git's own directory is never check-in content.",
            )
        if path in seen:
            raise Refusal(
                "malformed-field", f"the path {path!r} is declared twice",
                "Resubmit with each path named exactly once.",
            )
        screen_gatekeeper_source_path(path)
        seen.add(path)
    return sorted(seen)


def screen_import(arguments, declared_paths: list[str]) -> dict | None:
    parts = {
        "commit": arguments.import_commit,
        "source": arguments.import_source,
        "dest": arguments.import_dest,
    }
    supplied = {name: value for name, value in parts.items() if value}

    if arguments.import_declaration == "none":
        if supplied:
            raise Refusal(
                "import-invalid",
                f"--import none was given alongside {', '.join('--import-' + n for n in sorted(supplied))}",
                "Resubmit with either --import none, or all three of --import-commit, "
                "--import-source and --import-dest — never both forms.",
            )
        return None

    if arguments.import_declaration is not None:
        raise Refusal(
            "malformed-field",
            f"--import {arguments.import_declaration!r} is not a recognised value",
            "Resubmit with --import none, or drop --import and give all three of "
            "--import-commit, --import-source and --import-dest.",
        )

    if not supplied:
        raise Refusal(
            "import-invalid", "no import was declared",
            "Resubmit with --import none when this change imports nothing, or with all "
            "three of --import-commit, --import-source and --import-dest when it does. "
            "The declaration is never optional: an unrecorded import is the one thing "
            "the entry checkpoint exists to prevent.",
        )
    if len(supplied) < len(parts):
        missing = sorted(set(parts) - set(supplied))
        raise Refusal(
            "import-invalid",
            f"the import declaration is missing {', '.join('--import-' + n for n in missing)}",
            "Resubmit with all three of --import-commit, --import-source and "
            "--import-dest. A partial triple cannot be recorded, so it cannot be "
            "allowed through.",
        )

    if not FULL_COMMIT_ID.match(parts["commit"]):
        raise Refusal(
            "malformed-field",
            f"--import-commit {parts['commit']!r} is not a full 40-character commit id",
            "Resubmit with the full 40-character id of the legacy commit the content "
            "is taken from. Abbreviations can turn ambiguous as history grows.",
        )
    screen_unsafe_path(parts["source"], "import source")
    screen_unsafe_path(parts["dest"], "import destination")

    if parts["dest"] not in declared_paths:
        raise Refusal(
            "import-invalid",
            f"the import destination {parts['dest']!r} is not in --files",
            "Resubmit with the destination path also named in --files. The import "
            "writes that path, so the declaration must say so.",
        )
    return parts


def import_record(import_declaration: dict | None) -> str:
    """Return the canonical import record shared by the digest and trailer."""
    if import_declaration is None:
        return "none"
    return (f"{import_declaration['commit']} {import_declaration['source']}"
            f" {UNSAFE_PATH_MARKER} {import_declaration['dest']}")


def read_legacy_content(legacy_repository: str, import_declaration: dict) -> bytes:
    """Return the bytes at the declared legacy commit."""
    inside = subprocess.run(
        ["git", "-C", legacy_repository, "rev-parse", "--git-dir"],
        capture_output=True, text=True, check=False,
    )
    if inside.returncode != 0:
        raise Refusal(
            "import-invalid",
            f"{legacy_repository!r} is not a readable git repository: "
            f"{inside.stderr.strip() or 'no stderr'}",
            "Resubmit with --legacy-repo naming a readable checkout of the legacy "
            "repository. Nothing was changed.",
        )

    known = subprocess.run(
        ["git", "-C", legacy_repository, "cat-file", "-e",
         f"{import_declaration['commit']}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    if known.returncode != 0:
        raise Refusal(
            "import-invalid",
            f"no commit {import_declaration['commit']} exists in the legacy repository",
            "Resubmit with --import-commit set to a commit id that exists in the legacy "
            "repository.",
        )

    shown = subprocess.run(
        ["git", "-C", legacy_repository, "show",
         f"{import_declaration['commit']}:{import_declaration['source']}"],
        capture_output=True, check=False,
    )
    if shown.returncode != 0:
        raise Refusal(
            "import-invalid",
            f"the path {import_declaration['source']!r} does not exist in the legacy "
            f"repository at commit {import_declaration['commit']}",
            "Resubmit with --import-source set to the path as it stood at that commit; "
            "read it with: git -C <legacy> ls-tree --name-only <commit>",
        )
    return shown.stdout


def screen_form(arguments) -> dict:
    """Validate fields that require no repository access."""
    if not arguments.message or not arguments.message.strip():
        raise Refusal(
            "malformed-field", "--message is empty",
            "Resubmit with --message stating what the change does and why. "
            "Intent lives with the author; it cannot be auto-filled.",
        )

    if arguments.issue != "none" and not ISSUE_NUMBER.match(arguments.issue or ""):
        raise Refusal(
            "malformed-field",
            f"--issue {arguments.issue!r} is neither 'none' nor a positive integer",
            "Resubmit with --issue none, or with the issue number this work belongs to.",
        )

    if not arguments.agent or not arguments.agent.strip():
        raise Refusal(
            "malformed-field", "--agent is empty",
            "Resubmit with --agent <runtime/model> naming the runtime and model that "
            "produced this change, for example 'claude-code/opus-5'. The environment "
            "carries the runtime but not the model, so the caller declares it.",
        )

    paths = screen_paths(arguments.files)
    import_declaration = screen_import(arguments, paths)

    return {
        "paths": paths,
        "message": arguments.message.strip(),
        # Screening cannot read the caller’s checkout, so the computed base is added afterwards.
        "issue": arguments.issue,
        "agent": arguments.agent.strip(),
        "import": import_declaration,
        # Resolve environment-derived fields once; detached workers must use the same values.
        "origin": os.environ.get("CLAUDE_CODE_SESSION_ID") or "none",
    }




def compute_base(repository: Path) -> str:
    """Return the merge base of the caller’s HEAD and origin/main."""
    # Refreshing from main mid-task can make this fork point too new.
    run_git(["fetch", "--quiet", "origin", MAIN_BRANCH], cwd=repository, check=False)
    merged = subprocess.run(
        ["git", "merge-base", "HEAD", f"origin/{MAIN_BRANCH}"],
        cwd=str(repository), capture_output=True, text=True, check=False,
    )
    base = merged.stdout.strip()
    if merged.returncode != 0 or not FULL_COMMIT_ID.match(base):
        raise Refusal(
            "malformed-field",
            f"the base could not be computed in {str(repository)!r}: "
            f"git merge-base HEAD origin/main said: {merged.stderr.strip() or 'nothing'}",
            "Ensure the repository has an 'origin' remote whose main branch shares "
            "history with HEAD, then resubmit. The base is computed, never declared.",
        )
    return base


def refuse_symlinked_component(root: Path, path: str, side: str) -> None:
    # Check every component on both read and write paths to prevent following links outside the repository.
    # Links within the repository are also forbidden; containment alone is insufficient.
    current = root
    for part in Path(path).parts:
        current = current / part
        if not current.is_symlink():
            continue
        if side == "worktree":
            raise Refusal(
                "malformed-field",
                f"the declared path {path!r} passes through a symlink at "
                f"{current.relative_to(root).as_posix()!r}",
                "Resubmit naming regular files only, with no symlinked directory "
                "on the way: the gate reads regular-file bytes and does not "
                "follow links (ruled 2026-08-11, widened 2026-08-12).",
            )
        raise Refusal(
            "base-tree-symlink",
            f"main carries a symlink at "
            f"{current.relative_to(root).as_posix()!r}, on the way to the declared "
            f"path {path!r}",
            "Nothing to resubmit: the link is on main, not in your checkout, and "
            "writing through it would place your bytes outside the repository. "
            "Ask whoever maintains that path on main to replace the link with a "
            "regular file, then check the work in.",
        )


def read_worktree_content(
    repository: Path, paths: list[str], import_declaration: dict | None = None
) -> dict[str, bytes | None]:
    """Return declared content, using None for absent paths and legacy bytes for imports."""
    import_destination = import_declaration["dest"] if import_declaration else None
    content: dict[str, bytes | None] = {}
    for path in paths:
        if path == import_destination:
            continue
        candidate = repository / path
        refuse_symlinked_component(repository, path, side="worktree")
        if candidate.is_file():
            content[path] = candidate.read_bytes()
        elif candidate.exists():
            raise Refusal(
                "malformed-field", f"the path {path!r} is not a regular file",
                "Resubmit naming regular files only; declare a directory's contents "
                "path by path.",
            )
        else:
            content[path] = None
    return content


def read_base_content(clone: Path, base: str, paths: list[str]) -> dict[str, bytes | None]:
    """Return each declared path’s base content, or None if absent."""
    content: dict[str, bytes | None] = {}
    for path in paths:
        shown = subprocess.run(
            ["git", "show", f"{base}:{path}"], cwd=str(clone),
            capture_output=True, check=False,
        )
        content[path] = shown.stdout if shown.returncode == 0 else None
    return content


def classify_changes(
    worktree: dict[str, bytes | None], base: dict[str, bytes | None]
) -> dict[str, str]:
    """Classify paths as added, modified or deleted, refusing unchanged paths."""
    changes: dict[str, str] = {}
    for path in sorted(worktree):
        new, old = worktree[path], base[path]
        if new is None and old is None:
            raise Refusal(
                "unknown-path",
                f"the path {path!r} exists neither at the declared base nor in the "
                "working copy",
                "Check the spelling and resubmit with the path as it is written in "
                "the repository.",
            )
        if new == old:
            raise Refusal(
                "unchanged-path",
                f"the path {path!r} is identical to its content at the declared base",
                "Resubmit without that path. Declarations state what changed, so an "
                "unchanged path in the list is a mistake somewhere.",
            )
        changes[path] = "deleted" if new is None else ("added" if old is None else "modified")
    return changes


def compute_digest(base: str, worktree: dict[str, bytes | None], import_declaration: str) -> str:
    """Return a digest of the base, sorted paths and new bytes."""
    # Exclude metadata so identical work deduplicates even under a different message.
    digest = hashlib.sha256()

    def frame(tag: bytes, content: bytes) -> None:
        # Length prefixes prevent file content containing framing tags from colliding with another file sequence.
        digest.update(b"\x00" + tag + b"\x00")
        digest.update(str(len(content)).encode("ascii") + b":")
        digest.update(content)

    frame(b"base", base.encode("utf-8"))
    for path in sorted(worktree):
        frame(b"path", path.encode("utf-8"))
        content = worktree[path]
        if content is None:
            frame(b"deleted", b"")
        else:
            frame(b"content", content)
    frame(b"import", import_declaration.encode("utf-8"))
    return digest.hexdigest()


def undeclared_changes(repository: Path, declared: list[str]) -> list[str]:
    """Return undeclared worktree changes as an advisory."""
    # Unrelated work in the same worktree is legitimate and must not block check-in.
    # Include untracked files so forgotten new files are reported.
    # -z preserves arbitrary names; -uall lists files instead of collapsing new directories.
    status = run_git(["status", "--porcelain", "-z", "--untracked-files=all"],
                     cwd=repository, check=False)
    if status.returncode != 0:
        return []
    others = []
    for entry in status.stdout.split("\0"):
        path = entry[3:]
        if path and path not in declared:
            others.append(path)
    return sorted(others)




def trailer_block(request: dict, digest: str) -> str:
    # GitHub adds commits mentioning #<issue> to that issue’s timeline.
    issue = "none" if request["issue"] == "none" else f"#{request['issue']}"
    return "\n".join([
        f"Gatekeeper-origin: {request['origin']}",
        f"Gatekeeper-agent: {request['agent']}",
        f"Gatekeeper-digest: {digest}",
        f"Gatekeeper-import: {import_record(request['import'])}",
        f"Gatekeeper-issue: {issue}",
    ])




def resolve_repository(argument: str | None) -> Path:
    start = Path(argument).resolve() if argument else Path.cwd()
    toplevel = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    if toplevel.returncode != 0:
        raise Refusal(
            "malformed-field", f"{str(start)!r} is not inside a git repository",
            "Run the gatekeeper from inside the repository holding the work, or pass "
            "--repo <dir> naming it.",
        )
    return Path(toplevel.stdout.strip())


def resolve_remote(repository: Path, argument: str | None) -> str:
    if argument:
        return argument
    remote = run_git(["remote", "get-url", "origin"], cwd=repository, check=False)
    if remote.returncode != 0 or not remote.stdout.strip():
        raise Refusal(
            "malformed-field", "the repository has no 'origin' remote",
            "Resubmit with --remote <url> naming where main lives.",
        )
    return remote.stdout.strip()


def prepare_clone(workspace: Path, remote: str) -> Path:
    # Build from main so stale, undeclared worktree content cannot enter the candidate.
    clone = workspace / "candidate"
    cloned = subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", remote, str(clone)],
        capture_output=True, text=True, check=False,
    )
    if cloned.returncode != 0:
        raise Refusal(
            "network-down",
            f"could not read main from {remote!r}: {cloned.stderr.strip() or 'no stderr'}",
            "Resubmit once the remote is reachable; this failure is safe to retry.",
        )
    run_git(["config", "user.name", "nedschorus-main-gatekeeper"], cwd=clone)
    run_git(["config", "user.email", "gatekeeper@nedschorus.invalid"], cwd=clone)
    return clone


def find_existing_check_in(clone: Path, digest: str, ref: str | None = None) -> str | None:
    found = run_git(
        ["log", ref or f"origin/{MAIN_BRANCH}", "--format=%H",
         "--grep", f"Gatekeeper-digest: {digest}"],
        cwd=clone, check=False,
    )
    if found.returncode != 0:
        return None
    lines = [line.strip() for line in found.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


def build_candidate(
    clone: Path, request: dict, worktree: dict[str, bytes | None], digest: str,
    target: str | None = None,
) -> str:
    run_git(["checkout", "--quiet", "-B", CANDIDATE_BRANCH, target or request["base"]], cwd=clone)

    for path in request["paths"]:
        # Checkout recreates main’s symlinks; writes must not follow them outside the repository.
        refuse_symlinked_component(clone, path, side="base")
        target = clone / path
        content = worktree[path]
        if content is None:
            run_git(["rm", "--quiet", "--", path], cwd=clone)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            run_git(["add", "--", path], cwd=clone)

    message = f"{request['message']}\n\n{trailer_block(request, digest)}\n"
    committed = subprocess.run(
        ["git", "commit", "--quiet", "--file", "-"], cwd=str(clone),
        input=message, capture_output=True, text=True, check=False,
    )
    if committed.returncode != 0:
        raise Refusal(
            "workspace-io-error",
            f"the candidate commit failed: {committed.stderr.strip() or 'no stderr'}",
            "Resubmit the same request; this class of failure is safe to retry.",
        )
    return run_git(["rev-parse", "HEAD"], cwd=clone).stdout.strip()


def attempt_push(clone: Path) -> tuple[bool, str]:
    """Return (won, stderr) from one push attempt."""
    # GitHub accepts or rejects the entire push, so concurrent check-ins need no lock.
    pushed = subprocess.run(
        ["git", "push", "--quiet", "origin", f"{CANDIDATE_BRANCH}:{MAIN_BRANCH}"],
        cwd=str(clone), capture_output=True, text=True, check=False,
    )
    return pushed.returncode == 0, pushed.stderr.strip()


def classify_push_failure(stderr: str) -> str:
    lowered = stderr.lower()
    if "non-fast-forward" in lowered or "fetch first" in lowered or "rejected" in lowered:
        return "lost-the-race"
    if "authentication" in lowered or "permission" in lowered or "denied" in lowered:
        return "push-auth-failed"
    return "network-down"


def fetch_main_tip(clone: Path) -> str:
    run_git(["fetch", "--quiet", "origin", MAIN_BRANCH], cwd=clone)
    return run_git(["rev-parse", "FETCH_HEAD"], cwd=clone).stdout.strip()


def paths_changed_between(clone: Path, older: str, newer: str) -> set[str]:
    listed = run_git(["diff", "--name-only", f"{older}..{newer}"], cwd=clone, check=False)
    return {line.strip() for line in listed.stdout.splitlines() if line.strip()}


def describe_commits(clone: Path, older: str, newer: str) -> str:
    described = run_git(["log", "--format=%h %s", f"{older}..{newer}"], cwd=clone, check=False)
    return described.stdout.strip() or "unavailable"


def integrate_and_push(
    clone: Path, request: dict, worktree: dict[str, bytes | None], digest: str
) -> tuple[str, int]:
    """Return (commit, attempt count) after pushing over concurrent changes."""
    # Refuse overlapping paths rather than choosing which author’s content survives.
    base = request["base"]
    target = base

    for _ in range(MAX_INTEGRATION_ROUNDS):
        commit = build_candidate(clone, request, worktree, digest, target)
        won, stderr = attempt_push(clone)
        if won:
            integrated_over = run_git(
                ["rev-list", "--count", f"{base}..{target}"], cwd=clone, check=False
            ).stdout.strip()
            return commit, int(integrated_over or 0)

        failure = classify_push_failure(stderr)
        if failure == "push-auth-failed":
            raise Refusal(
                "push-auth-failed", f"the push was refused: {stderr or 'no stderr'}",
                "Resubmit once the pushing credential is available; this failure is "
                "safe to retry and changed nothing.",
            )
        if failure == "network-down":
            raise Refusal(
                "network-down", f"the push failed: {stderr or 'no stderr'}",
                "Resubmit; this failure is safe to retry and changed nothing.",
            )

        target = fetch_main_tip(clone)

        # Identical work may have reached main while this candidate was being built.
        already = find_existing_check_in(clone, digest, target)
        if already:
            raise AlreadyCheckedIn(already)

        collision = sorted(set(request["paths"]) & paths_changed_between(clone, base, target))
        if collision:
            raise Refusal(
                "conflict",
                f"main changed the same path(s) this request changes: "
                f"{', '.join(collision)}. Intervening commits:\n"
                f"{describe_commits(clone, base, target)}",
                "Update your working copy from main, re-apply the change on top of "
                f"the current tip {target}, resolve the overlap by hand, and resubmit. "
                "The recomputed base then reflects that tip, and the adjusted work "
                "digests fresh and processes as a new request.",
            )

    raise Refusal(
        "main-moving-too-fast",
        f"main moved {MAX_INTEGRATION_ROUNDS} times while this request was being "
        f"integrated, so the attempt was stopped rather than left spinning",
        "Resubmit once main is quieter; nothing was changed. If this repeats, the "
        "check-in rate has outgrown re-validation and the merge queue named in the "
        "specification is the next rung.",
    )





STALE_SCREENING_SECONDS = 24 * 60 * 60
STALE_WORKSPACE_SECONDS = 24 * 60 * 60
REFUSAL_RECORD_RETENTION_SECONDS = 30 * 24 * 60 * 60


def process_start_time(pid: int) -> str:
    """Return a process start token, or an empty string if unreadable."""
    # The start token distinguishes a worker from a recycled PID.
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return stat.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        pass
    # macOS has no /proc; use ps for the process start token.
    started = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True, text=True, check=False,
    )
    # worker.pid splits on whitespace, so the ps timestamp must be a single token.
    return "_".join(started.stdout.split())


def write_atomically(target: Path, content: str) -> None:
    # Rename keeps readers from seeing an empty or partially written state file.
    temporary = target.with_name(f".{target.name}.writing")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, target)


def write_worker_identity(workspace: Path) -> None:
    pid = os.getpid()
    write_atomically(workspace / "worker.pid", f"{pid} {process_start_time(pid)}")


def signal_worker(pid: int, signal_number: int) -> None:
    # Kill children only when the worker leads the group; a waiting worker may share the caller’s group.
    # PID 1 is init; zero and negative PIDs target groups.
    # killpg(1) can become kill(-1), broadcasting to every process this user may signal.
    if pid < 2:
        return
    try:
        leads_own_group = os.getpgid(pid) == pid
    except (OSError, ProcessLookupError, PermissionError):
        leads_own_group = False  # Cannot establish group ownership; signal only the worker.
    try:
        if leads_own_group:
            os.killpg(pid, signal_number)
        else:
            os.kill(pid, signal_number)
    except (OSError, ProcessLookupError, PermissionError):
        pass


def worker_stopped(workspace: Path, seconds: float) -> bool:
    """Wait up to seconds for the worker to stop and return whether it did."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if worker_state(workspace) not in LIVE_STATES:
            return True
        time.sleep(0.1)
    return worker_state(workspace) not in LIVE_STATES


def worker_state(workspace: Path) -> str:
    """Return alive, dead, unknown or none."""
    # Unreadable state is not proof of death; treating it as dead could destroy live work.
    if not workspace.is_dir():
        return "none"
    try:
        tokens = (workspace / "worker.pid").read_text(encoding="utf-8").split()
        pid = int(tokens[0])
    except (OSError, ValueError, IndexError):
        return "unknown"
    recorded_start = tokens[1] if len(tokens) > 1 else "0"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        pass  # Permission denial still proves the process exists.
    live_start = process_start_time(pid)
    # An unavailable start time is not evidence of PID reuse; skip comparison for either sentinel.
    if recorded_start not in ("", "0") and live_start and recorded_start != live_start:
        return "dead"
    return "alive"


def sweep_stale_workspaces() -> None:
    try:
        entries = list(workspace_root().iterdir())
    except OSError:
        return
    now = time.time()
    for entry in entries:
        try:
            age = now - entry.stat().st_mtime
            if entry.name.startswith("screening-"):
                if age > STALE_SCREENING_SECONDS:
                    shutil.rmtree(entry, ignore_errors=True)
                continue
            if not entry.is_dir():
                continue
            if (entry / "refusal.json").is_file():
                if age > REFUSAL_RECORD_RETENTION_SECONDS:
                    shutil.rmtree(entry, ignore_errors=True)
                continue
            # Age-gate unknown workers so the gap before the initial PID write is not swept.
            if age > STALE_WORKSPACE_SECONDS and worker_state(entry) in ("dead", "unknown"):
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


def retain_refusal_record(workspace: Path, digest: str, refusal: Refusal) -> None:
    """Keep the refusal for status to return once before sweeping the workspace."""
    for entry in ("candidate", "declared"):
        shutil.rmtree(workspace / entry, ignore_errors=True)
    # Publish the refusal atomically before removing worker state, so status never loses the reason.
    write_atomically(workspace / "refusal.json", json.dumps({
        "outcome": "refused", "error": refusal.error, "facts": refusal.facts,
        "next_action": refusal.next_action, "digest": digest,
        "summary": f"refused: {refusal.error} — {refusal.facts}",
    }))
    (workspace / "worker.pid").unlink(missing_ok=True)
    (workspace / "request.json").unlink(missing_ok=True)


def require_digest(arguments, command: str) -> str:
    digest = getattr(arguments, "digest", None)
    if not digest:
        raise Refusal(
            "malformed-field", f"{command} needs the request digest",
            f"Resubmit as: main-gatekeeper.py {command} <digest> — the digest is "
            "in the reply of the submission being asked about.",
        )
    return digest


def fetch_and_find(repository: Path, digest: str) -> str | None:
    """Return the commit for this digest, or None."""
    # A failed fetch must propagate: stale history cannot establish whether the work reached main.
    fetched = run_git(["fetch", "--quiet", "origin", MAIN_BRANCH],
                      cwd=repository, check=False)
    if fetched.returncode != 0:
        raise Refusal(
            "network-down",
            f"main could not be fetched, so whether this work reached it is "
            f"unknown: {fetched.stderr.strip() or 'no stderr'}",
            "Ask again once the remote is reachable; resubmitting is always safe, "
            "and a request that did reach main answers already-checked-in.",
        )
    return find_existing_check_in(repository, digest)


# Tests synchronize on phase files instead of timing assumptions; inert unless explicitly enabled.
WORKER_PHASES = ("before-git", "before-push", "after-push")
WORKER_PHASE_RELEASE_TIMEOUT = 120


def worker_phase(workspace: Path, phase: str) -> None:
    """Announce a phase and pause there when requested by a test."""
    paused_at = os.environ.get("GATEKEEPER_TEST_WORKER_PAUSE_AT")
    if not paused_at:
        return
    (workspace / f".reached-{phase}").write_text("", encoding="utf-8")
    if paused_at != phase:
        return
    if os.environ.get("GATEKEEPER_TEST_WORKER_IGNORES_TERM"):
        # Simulate an unsignalable worker or surviving push child so cancellation must verify its outcome.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    release = workspace / f".release-{phase}"
    deadline = time.monotonic() + WORKER_PHASE_RELEASE_TIMEOUT
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.02)


def run_worker(arguments) -> int:
    """Run the detached worker, reporting through history or the refusal record."""
    workspace = workspace_for(arguments.digest)
    if workspace is None:
        return EXIT_DEFECT
    # Only the detached worker writes its PID, avoiding a race with the spawner.
    write_worker_identity(workspace)
    record_path = workspace / "request.json"
    if not record_path.is_file():
        return EXIT_DEFECT
    request = json.loads(record_path.read_text(encoding="utf-8"))
    digest = request["digest"]

    worker_phase(workspace, "before-git")

    worktree: dict[str, bytes | None] = {}
    for path, change in request["changes"].items():
        worktree[path] = (
            None if change == "deleted"
            else (workspace / "declared" / path).read_bytes()
        )
    clone = workspace / "candidate"
    try:
        worker_phase(workspace, "before-push")
        try:
            integrate_and_push(clone, request, worktree, digest)
        except AlreadyCheckedIn:
            pass
        worker_phase(workspace, "after-push")
        shutil.rmtree(workspace, ignore_errors=True)
        return EXIT_SUCCESS
    except Refusal as refusal:
        retain_refusal_record(workspace, digest, refusal)
        return EXIT_REFUSED
    except Exception as defect:  # noqa: BLE001 - the record is the defect channel here
        retain_refusal_record(workspace, digest, Refusal(
            "program-defect", f"{type(defect).__name__}: {defect}",
            "Report this against nedschorus#3; it is a bug in the gatekeeper, "
            "not a problem with the request.",
        ))
        return EXIT_DEFECT


def status_query(arguments) -> int:
    digest = require_digest(arguments, "status")
    repository = resolve_repository(getattr(arguments, "repo", None))
    commit = fetch_and_find(repository, digest)
    if commit:
        return emit({"outcome": "checked-in", "digest": digest, "commit": commit,
                     "summary": f"checked-in {commit}"}, EXIT_SUCCESS)
    workspace = workspace_for(digest)
    if workspace is None:
        return emit({"outcome": "unknown", "digest": digest,
                     "summary": "unknown — no trace of this digest on this host; "
                                "if it was submitted from another machine, ask "
                                "there; otherwise submit it, submitting is "
                                "always safe"}, EXIT_SUCCESS)
    record_path = workspace / "refusal.json"
    if record_path.is_file():
        # Atomic rename gives only one concurrent status call ownership of the refusal record.
        claimed = workspace / "refusal.claimed.json"
        try:
            os.replace(record_path, claimed)
        except OSError:
            claimed = record_path  # Read in place if claiming failed.
        try:
            payload = json.loads(claimed.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Leave an unreadable refusal for retry; sweeping would destroy the only copy of the reason.
            return emit({"outcome": "refused", "error": "workspace-io-error",
                         "facts": "the retained refusal record could not be read; "
                                  "it is left in place",
                         "next_action": f"Ask again with: main-gatekeeper.py status "
                                        f"{digest} — if it stays unreadable, resubmit "
                                        "the work; resubmitting is always safe.",
                         "digest": digest,
                         "summary": "refused: workspace-io-error — record unreadable, "
                                    "retained"}, EXIT_REFUSED)
        shutil.rmtree(workspace, ignore_errors=True)
        return emit(payload, EXIT_REFUSED)
    state = worker_state(workspace)
    if state in LIVE_STATES:
        return emit({"outcome": "in-progress", "digest": digest,
                     "summary": "in-progress — a live worker holds this request; "
                                "ask again shortly"}, EXIT_SUCCESS)
    return emit({"outcome": "abandoned", "digest": digest,
                 "summary": "abandoned — workspace present, worker dead; "
                            "resubmit safely, the sweep is automatic"}, EXIT_SUCCESS)


def cancel_request(arguments) -> int:
    digest = require_digest(arguments, "cancel")
    repository = resolve_repository(getattr(arguments, "repo", None))
    commit = fetch_and_find(repository, digest)
    if commit:
        leftover = workspace_for(digest)
        if leftover is not None:
            shutil.rmtree(leftover, ignore_errors=True)
        return emit({"outcome": "too-late", "digest": digest, "commit": commit,
                     "summary": f"too-late — already-checked-in {commit}; the remedy "
                                "for a bad checked-in change is a revert through the "
                                "same gate"}, EXIT_SUCCESS)
    workspace = workspace_for(digest)
    if workspace is None:
        return emit({"outcome": "unknown-request", "digest": digest,
                     "summary": "unknown-request — no trace of this digest on "
                                "this host; a request submitted from another "
                                "machine is cancelled there"},
                    EXIT_SUCCESS)
    pid = None
    if worker_state(workspace) in LIVE_STATES:
        # Wait for the worker and push children before consulting history, or a push can race the answer.
        try:
            pid = int((workspace / "worker.pid").read_text(encoding="utf-8").split()[0])
        except (OSError, ValueError, IndexError):
            pid = None
        if pid is not None:
            signal_worker(pid, signal.SIGTERM)
            if not worker_stopped(workspace, seconds=10):
                signal_worker(pid, signal.SIGKILL)
                worker_stopped(workspace, seconds=5)

    # Recheck history even for a dead worker: it may have pushed before exiting.
    commit = fetch_and_find(repository, digest)
    if commit:
        shutil.rmtree(workspace, ignore_errors=True)
        return emit({"outcome": "too-late", "digest": digest, "commit": commit,
                     "summary": f"too-late — already-checked-in {commit}; the "
                                "push won the race"}, EXIT_SUCCESS)
    if worker_state(workspace) in LIVE_STATES:
        return emit({"outcome": "cancel-failed", "digest": digest,
                     "facts": f"worker {pid} is still alive after SIGTERM and "
                              "SIGKILL",
                     "next_action": f"Check status {digest} shortly; the worker "
                                    "may still push. If it persists, the "
                                    "workspace owner must kill it.",
                     "summary": "cancel-failed — the worker outlived SIGKILL, so "
                                "the workspace is left in place and the request "
                                "may still reach main"}, EXIT_REFUSED)
    shutil.rmtree(workspace, ignore_errors=True)
    return emit({"outcome": "cancelled", "digest": digest,
                 "summary": "cancelled — the workspace is swept; nothing reached "
                            "main"}, EXIT_SUCCESS)



# Keep expected accounts aligned with protection policy; stale expectations recommend undoing valid changes.
# GitHub identities are case-insensitive, but comparisons must match whole logins.
EXPECTED_MAIN_PUSHER_ACCOUNTS = {"NedLern", "ned-review-merge"}


def derive_repo_slug(repository: Path) -> str:
    remote = run_git(["remote", "get-url", "origin"], cwd=repository, check=False)
    url = remote.stdout.strip()
    match = re.search(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url)
    if remote.returncode != 0 or not match:
        raise Refusal(
            "audit-failed", f"the origin remote {url!r} is not a GitHub repository",
            "Run the audit from a checkout whose origin is on github.com, or pass "
            "--repo-slug owner/repo.",
        )
    return match.group(1)


def fetch_branch_protection(repo_slug: str) -> dict:
    try:
        completed = subprocess.run(
            ["gh", "api", f"repos/{repo_slug}/branches/{MAIN_BRANCH}/protection"],
            capture_output=True, text=True, check=False, timeout=30,
        )
    except FileNotFoundError:
        raise Refusal(
            "audit-failed", "gh is not installed on this box",
            "Install and authenticate the GitHub CLI, then re-run the audit.",
        ) from None
    except subprocess.TimeoutExpired:
        raise Refusal(
            "audit-failed", "the GitHub API did not answer within 30 seconds",
            "Re-run the audit; this failure is safe to retry.",
        ) from None
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no detail"
        # GitHub uses 404 for both missing protection and credentials forbidden to read it.
        unreadable = "404" in detail or "Not Found" in detail
        raise Refusal(
            "audit-failed",
            f"reading protection for {repo_slug} failed: {detail}"
            + (" — note that GitHub returns 404 both when protection is absent and "
               "when the credential may not read it, so this does NOT show protection "
               "is missing" if unreadable else ""),
            ("Re-run under a credential that can read branch protection: the setting "
             "requires admin on the repository, which agent tokens deliberately lack, "
             "so this outcome is expected until the credential work lands (a dedicated "
             "account, § The credential and enforcement). Until then the audit reports "
             "that it could not verify, which is the honest answer — an unreadable wall "
             "is a finding, never a silent skip into green."
             if unreadable else
             "Authenticate gh with an account that can read branch protection, or fix "
             "the network, then re-run. An unreadable wall is a finding, never a silent "
             "skip into green."),
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise Refusal(
            "audit-failed", "the protection reply was not JSON",
            "Re-run the audit; if this repeats, gh or the API changed shape.",
        ) from None


def compare_protection(protection: dict) -> list[str]:
    """Return descriptions of differences between live and expected protection."""
    problems: list[str] = []
    restrictions = protection.get("restrictions")
    if not restrictions:
        problems.append(
            "no push restriction exists; the design restricts main pushes to "
            f"exactly {sorted(EXPECTED_MAIN_PUSHER_ACCOUNTS)}"
        )
    else:
        users = sorted(u.get("login", "") for u in restrictions.get("users") or [])
        if ({u.casefold() for u in users}
                != {a.casefold() for a in EXPECTED_MAIN_PUSHER_ACCOUNTS}):
            problems.append(
                f"the push restriction names {users or ['nobody']} instead of "
                f"{sorted(EXPECTED_MAIN_PUSHER_ACCOUNTS)}"
            )
        for group in ("teams", "apps"):
            granted = [entry.get("slug") or entry.get("name", "")
                       for entry in restrictions.get(group) or []]
            if granted:
                problems.append(f"the push restriction grants {group} {granted}; "
                                "the design grants none")
    if not (protection.get("enforce_admins") or {}).get("enabled"):
        problems.append("enforce-admins is off; the design requires it on")
    if (protection.get("allow_force_pushes") or {}).get("enabled"):
        problems.append("force-push is allowed; the design blocks it")
    if (protection.get("allow_deletions") or {}).get("enabled"):
        problems.append("branch deletion is allowed; the design blocks it")
    return problems


def audit_branch_protection(arguments) -> int:
    try:
        if arguments.protection_file:
            try:
                protection = json.loads(
                    Path(arguments.protection_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise Refusal(
                    "audit-failed",
                    f"the protection settings could not be read: {error}",
                    "Re-run once the settings source is readable.",
                ) from None
        else:
            slug = arguments.repo_slug or derive_repo_slug(
                resolve_repository(arguments.repo))
            protection = fetch_branch_protection(slug)
    except Refusal as failure:
        return emit({
            "outcome": "audit-failed", "facts": failure.facts,
            "next_action": failure.next_action,
            "summary": f"audit-failed — {failure.facts}",
        }, EXIT_REFUSED)
    problems = compare_protection(protection)
    if problems:
        return emit({
            "outcome": "protection-wrong", "facts": "; ".join(problems),
            "next_action": "Restore the settings named in facts to the design's "
                           "values (an org-owner act — the user's alone), then "
                           "re-run the audit.",
            "summary": f"protection-wrong — {'; '.join(problems)}",
        }, EXIT_REFUSED)
    return emit({
        "outcome": "protection-ok",
        "summary": "protection-ok — main's live protection matches the design",
    }, EXIT_SUCCESS)


def check_in(arguments) -> int:
    request = screen_form(arguments)
    repository = resolve_repository(arguments.repo)
    remote = resolve_remote(repository, arguments.remote)
    request["base"] = compute_base(repository)
    worktree = read_worktree_content(repository, request["paths"], request["import"])
    if request["import"] is not None:
        worktree[request["import"]["dest"]] = read_legacy_content(
            arguments.legacy_repo, request["import"]
        )

    workspace: Path | None = None
    clone_parent: Path | None = None
    try:
        # Concurrent screening needs separate scratch directories; the digest is not known until content is read.
        workspace_root().mkdir(parents=True, exist_ok=True)
        clone_parent = Path(tempfile.mkdtemp(prefix="screening-", dir=workspace_root()))
        clone = prepare_clone(clone_parent, remote)

        base_content = read_base_content(clone, request["base"], request["paths"])
        request["changes"] = classify_changes(worktree, base_content)

        digest = compute_digest(request["base"], worktree, import_record(request["import"]))
        already = find_existing_check_in(clone, digest)
        if already:
            return emit({
                "outcome": "already-checked-in", "digest": digest, "commit": already,
                "summary": f"already-checked-in {already}",
            }, EXIT_SUCCESS)

        # Identical submissions share a workspace; never sweep a live twin.
        existing = workspace_root() / digest
        if worker_state(existing) in LIVE_STATES:
            return emit({
                "outcome": "in-progress", "digest": digest,
                "summary": "in-progress — a live worker already holds this exact "
                           f"work; collect the outcome with: status {digest}",
            }, EXIT_SUCCESS)
        shutil.rmtree(existing, ignore_errors=True)

        # Exclusive mkdir claims the workspace atomically, including the gap before a PID file exists.
        workspace = existing
        try:
            workspace.mkdir(parents=True)
        except FileExistsError:
            return emit({
                "outcome": "in-progress", "digest": digest,
                "summary": "in-progress — another submission claimed this exact "
                           f"work first; collect the outcome with: status {digest}",
            }, EXIT_SUCCESS)
        # Only the worker writes its PID; a spawner placeholder could overwrite the PID-reuse token.
        # Until the detached worker stamps itself, unknown state is treated as live.
        if not getattr(arguments, "no_wait", False):
            write_worker_identity(workspace)
        submitting_host = socket.gethostname()
        (workspace / "request.json").write_text(
            json.dumps({**request, "digest": digest, "remote": remote,
                        "host": submitting_host}, indent=2),
            encoding="utf-8",
        )
        # Snapshot declared bytes now; the caller’s worktree may change before the worker reads it.
        for declared_path, declared_content in worktree.items():
            if declared_content is None:
                continue
            snapshot = workspace / "declared" / declared_path
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(declared_content)
        shutil.move(str(clone), str(workspace / "candidate"))
        clone = workspace / "candidate"

        if getattr(arguments, "no_wait", False):
            spawned = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "worker", digest],
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            workspace = None  # Ownership passed to the worker; do not sweep.
            # Workspaces and workers are host-local, so the digest must identify its host.
            return emit({
                "outcome": "accepted", "digest": digest,
                "next_action": f"Collect the outcome with: main-gatekeeper.py "
                               f"status {digest} — run it on {submitting_host}, "
                               f"the host this request was submitted from; its "
                               f"workspace, worker and refusal record live "
                               f"there and nowhere else.",
                "summary": f"accepted {digest} on {submitting_host}",
            }, EXIT_SUCCESS)

        try:
            commit, integrated_over = integrate_and_push(clone, request, worktree, digest)
        except AlreadyCheckedIn as raced:
            return emit({
                "outcome": "already-checked-in", "digest": digest, "commit": raced.commit,
                "summary": f"already-checked-in {raced.commit}",
            }, EXIT_SUCCESS)

        advisory = undeclared_changes(repository, request["paths"])
        payload = {
            "outcome": "checked-in", "commit": commit, "digest": digest,
            "summary": f"checked-in {commit}",
        }
        if integrated_over:
            payload["integrated_over"] = integrated_over
            payload["summary"] += f" (integrated over {integrated_over} newer commit(s))"
        if advisory:
            payload["advisory"] = (
                f"the working copy also differs at {', '.join(advisory)}; confirm intentional"
            )
        return emit(payload, EXIT_SUCCESS)
    finally:
        if clone_parent is not None:
            shutil.rmtree(clone_parent, ignore_errors=True)
        if workspace is not None:
            shutil.rmtree(workspace, ignore_errors=True)


class TeachingArgumentParser(argparse.ArgumentParser):
    """Return command-line errors through the JSON refusal contract."""
    # argparse’s default exit 2 is reserved here for program defects.

    def error(self, message):
        raise Refusal(
            "malformed-field", f"the command line is malformed: {message}",
            "Resubmit with a corrected invocation; the request grammar is in the "
            "specification (nc-systems/main-gatekeeper/main-gatekeeper-design.md). "
            "(--help is deliberately not cited here: it prints usage text, "
            "not the JSON every other invocation returns.)",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = TeachingArgumentParser(
        prog="main-gatekeeper.py", description="The single check-in gate for nedschorus.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-in", help="check work in to main")
    check.add_argument("--files", nargs="+", required=True, metavar="PATH")
    check.add_argument("--message", required=True)
    check.add_argument("--import", dest="import_declaration", default=None, metavar="none",
                       help="'none', or omit and give the three --import-* parts")
    check.add_argument("--import-commit", default=None, metavar="COMMIT")
    check.add_argument("--import-source", default=None, metavar="PATH")
    check.add_argument("--import-dest", default=None, metavar="PATH")
    check.add_argument("--legacy-repo", default=str(Path.home() / "Projects" / "nedlern"),
                       help="the legacy repository an import reads from")
    check.add_argument("--issue", required=True, metavar="none|N")
    check.add_argument("--agent", required=True, metavar="RUNTIME/MODEL")
    check.add_argument("--repo", default=None, help="the repository holding the work")
    check.add_argument("--remote", default=None, help="where main lives; defaults to origin")
    mode = check.add_mutually_exclusive_group()
    mode.add_argument("--wait", dest="no_wait", action="store_false", default=False)
    mode.add_argument("--no-wait", dest="no_wait", action="store_true")

    for name in ("status", "cancel"):
        later = commands.add_parser(name, help=f"{name} a request by digest")
        later.add_argument("digest", nargs="?", default=None)
        later.add_argument("--repo", default=None,
                           help="the repository whose history answers")

    audit = commands.add_parser(
        "audit", help="check main's live branch protection against the design (B3c)")
    audit.add_argument("--repo", default=None,
                       help="checkout whose origin names the repository")
    audit.add_argument("--repo-slug", default=None, metavar="OWNER/REPO")
    audit.add_argument("--protection-file", default=None, metavar="JSON",
                       help="test seam: read settings from a file instead of gh")

    return parser


# Use a separate internal parser: argparse does not honor SUPPRESS for subparsers.
def build_internal_worker_parser() -> argparse.ArgumentParser:
    worker = TeachingArgumentParser(prog="main-gatekeeper.py worker")
    worker.add_argument("digest")
    return worker


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    try:
        if argv[:1] == ["worker"]:
            arguments = build_internal_worker_parser().parse_args(argv[1:])
            arguments.command = "worker"
        else:
            arguments = parser.parse_args(argv)
        sweep_stale_workspaces()
        if arguments.command == "check-in":
            return check_in(arguments)
        if arguments.command == "status":
            return status_query(arguments)
        if arguments.command == "cancel":
            return cancel_request(arguments)
        if arguments.command == "audit":
            return audit_branch_protection(arguments)
        return run_worker(arguments)
    except Refusal as refusal:
        return emit({
            "outcome": "refused", "error": refusal.error, "facts": refusal.facts,
            "next_action": refusal.next_action,
            "summary": f"refused: {refusal.error} — {refusal.facts}",
        }, EXIT_REFUSED)
    except Exception as defect:  # noqa: BLE001 - exit 2 is the defect channel
        return emit({
            "outcome": "refused", "error": "program-defect",
            "facts": f"{type(defect).__name__}: {defect}",
            "next_action": "Report this against nedschorus#3; it is a bug in the "
                           "gatekeeper, not a problem with the request.",
            "summary": f"program defect: {type(defect).__name__}: {defect}",
        }, EXIT_DEFECT)


if __name__ == "__main__":
    sys.exit(main())
