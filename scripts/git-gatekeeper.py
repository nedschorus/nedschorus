#!/usr/bin/env python3
"""The single program through which every change reaches main in nedschorus.

Specification: docs/cross-project/git-gatekeeper-design.md (canonical).
Build bindings: docs/issues/queue/3-gatekeeper-build-bindings.md (B1-B6).
Build order and the design points left to the builder:
docs/issues/3-git-gatekeeper-build-slice-plan.md. Issue: nedschorus#3.

This is SLICE 1 of five: a synchronous check-in, end to end. For each request
the program does exactly one of two things — checks the work in, or refuses
and teaches the fix. On success four things are true: the change is on main,
the checks ran against exactly the content pushed, the commit's trailers carry
the whole machine-readable record, and the caller has the commit id.

What slice 1 deliberately does not do, and which slice takes it: --import and
the imports query (2); automatic integration when main moved, and the conflict
and main-moving-too-fast endings (3); --no-wait, the detached worker, status
and cancel (4); the trailer-absence and branch-protection audits (5). Reaching
one of those is a named refusal, `unbuilt-option`, never an unnamed ending and
never a crash — exit code 2 is reserved for a defect in this program, so an
argument parser rejection must not be how a caller learns a slice boundary.

Resubmitting is always safe. The digest identifies the WORK — base, paths and
their bytes — and not the metadata around it, so identical work resubmitted
under a different message deduplicates, and work that already went through
answers already-checked-in with its commit id. An agent that crashed never
reconstructs what happened; it submits again.

Reply contract (B1): exactly one JSON object on stdout, always carrying a
human-readable `summary`. Exit 0 for success and informational answers, 1 for
a catalog refusal (the gatekeeper working correctly), 2 for a program defect.

Records: git history and the invoking session's transcript, and nothing else.
The workspace exists only while a request is in flight and is swept on both
endings, so a refusal leaves the repository and the disk untouched.

Usage:
  git-gatekeeper.py check-in --files <path>... --message <text>
                    --base <40-hex> --import none --issue none|<n>
                    --agent <runtime/model> [--wait]
                    [--repo <dir>] [--remote <url-or-path>]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT_NAME = "nedschorus-gatekeeper"
CANDIDATE_BRANCH = "git-gatekeeper-candidate"
MAIN_BRANCH = "main"

FULL_COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")
ISSUE_NUMBER = re.compile(r"^[1-9][0-9]*$")

# B2: start tight. Relaxing later is forward-compatible; tightening later
# strands history. Verified 2026-07-30 that both repositories have zero paths
# matching any of these classes, so the rule costs nothing today.
UNSAFE_PATH_MARKER = "->"

EXIT_SUCCESS = 0
EXIT_REFUSED = 1
EXIT_DEFECT = 2


class Refusal(Exception):
    """A named catalog refusal: the error, the facts, and the exact next act.

    Never a bare error code. B5: the next action is verb-first and specific —
    "resubmit with --base <current-main-id>", never "fix the problem" — and
    one term is used per concept across the whole catalog, because agents
    pattern-match this text. A path is always a "path", never a "file".
    """

    def __init__(self, error: str, facts: str, next_action: str):
        super().__init__(f"{error}: {facts}")
        self.error = error
        self.facts = facts
        self.next_action = next_action


def workspace_root() -> Path:
    """B4a: outside every repository, discoverable from the digest alone."""
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / WORKSPACE_ROOT_NAME


def emit(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload))
    return exit_code


def run_git(arguments: list[str], cwd: Path | None = None, check: bool = True):
    """Run git and return the completed process; stdout and stderr as text."""
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


# --- Instant screening -----------------------------------------------------
# Form validation is synchronous and in memory: nothing touches disk until a
# request has passed it, so a malformed request cannot leave a trace.


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
        "unsafe-path",
        f"the {position} path {path!r} contains {detail}",
        "Rename the path so it contains only printable ASCII without whitespace, "
        "then resubmit. Paths of this shape are refused rather than quoted because "
        "the trailer format is unquoted; quoting grows in when a real import needs it.",
    )


def screen_paths(raw_paths: list[str]) -> list[str]:
    if not raw_paths:
        raise Refusal(
            "empty-change", "the --files list is empty",
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
        seen.add(path)
    return sorted(seen)


def screen_form(arguments) -> dict:
    """Validate every field that can be judged without touching a repository."""
    if not arguments.message or not arguments.message.strip():
        raise Refusal(
            "missing-message", "--message is empty",
            "Resubmit with --message stating what the change does and why. "
            "Intent lives with the author; it cannot be auto-filled.",
        )

    if not FULL_COMMIT_ID.match(arguments.base or ""):
        raise Refusal(
            "malformed-field",
            f"--base {arguments.base!r} is not a full 40-character commit id",
            "Resubmit with the full 40-character id of the main commit this work "
            "started from. Abbreviations can turn ambiguous as history grows, and "
            "branch names move.",
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

    if getattr(arguments, "no_wait", False):
        raise Refusal(
            "unbuilt-option", "--no-wait is not built in this version",
            "Resubmit with --wait. The detached worker, status and cancel arrive "
            "together in slice 4 of the git-gatekeeper build (nedschorus#3).",
        )

    if arguments.import_declaration != "none":
        raise Refusal(
            "unbuilt-option",
            f"--import {arguments.import_declaration!r} is not built in this version",
            "Resubmit with --import none. The entry checkpoint — the recorded gate "
            "every legacy import crosses — arrives in slice 2 of the git-gatekeeper "
            "build (nedschorus#3).",
        )

    return {
        "paths": screen_paths(arguments.files),
        "message": arguments.message.strip(),
        "base": arguments.base,
        "issue": arguments.issue,
        "agent": arguments.agent.strip(),
        "import": "none",
        # B4c, the resolve-once rule: every environment-derived field is
        # resolved here, at screening, and written into the request record.
        # Nothing downstream re-derives it from its own environment.
        "origin": os.environ.get("CLAUDE_CODE_SESSION_ID") or "none",
    }


# --- Reading the caller's worktree and the declared base -------------------


def read_worktree_content(repository: Path, paths: list[str]) -> dict[str, bytes | None]:
    """The new content of each declared path; None where the path is absent.

    This is the program's only read of the caller's working copy for content.
    """
    content: dict[str, bytes | None] = {}
    for path in paths:
        candidate = repository / path
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
    """The content of each declared path at the declared base, None if absent."""
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
    """Infer added / modified / deleted per path, refusing dishonest claims."""
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
    if not changes:
        raise Refusal(
            "empty-change", "no declared path differs from the declared base",
            "Resubmit once the working copy actually differs from the base.",
        )
    return changes


def compute_digest(base: str, worktree: dict[str, bytes | None], import_declaration: str) -> str:
    """SHA-256 over the WORK: base, sorted paths, each path's new bytes.

    Deliberately excluded: message, issue, mode, origin, agent, time. The
    digest identifies the work, so identical work resubmitted under different
    metadata still deduplicates — which is what makes resubmission safe.
    """
    digest = hashlib.sha256()
    digest.update(base.encode("utf-8"))
    for path in sorted(worktree):
        digest.update(b"\x00path\x00")
        digest.update(path.encode("utf-8"))
        content = worktree[path]
        if content is None:
            digest.update(b"\x00deleted\x00")
        else:
            digest.update(b"\x00content\x00")
            digest.update(content)
    digest.update(b"\x00import\x00")
    digest.update(import_declaration.encode("utf-8"))
    return digest.hexdigest()


def undeclared_changes(repository: Path, declared: list[str]) -> list[str]:
    """Paths the caller's worktree also modifies — an advisory, never a refusal.

    Unrelated work in progress in the same worktree is legitimate, so this
    never blocks; the likeliest cause of a surprise here is a forgotten
    declaration, which is worth saying out loud.
    """
    status = run_git(["status", "--porcelain", "--untracked-files=no"], cwd=repository, check=False)
    if status.returncode != 0:
        return []
    others = []
    for line in status.stdout.splitlines():
        path = line[3:].strip()
        if path and path not in declared:
            others.append(path)
    return sorted(others)


# --- The trailer -----------------------------------------------------------


def trailer_block(request: dict, digest: str) -> str:
    """Three facts, a writer, and a pointer; nothing else.

    The issue value is written in #<n> form deliberately: any commit reaching
    the default branch with #<n> in its message appears in that issue's GitHub
    timeline, so an issue collects all its check-ins with zero machinery.
    """
    issue = "none" if request["issue"] == "none" else f"#{request['issue']}"
    return "\n".join([
        f"Gatekeeper-origin: {request['origin']}",
        f"Gatekeeper-agent: {request['agent']}",
        f"Gatekeeper-digest: {digest}",
        f"Gatekeeper-import: {request['import']}",
        f"Gatekeeper-issue: {issue}",
    ])


# --- The procedure ---------------------------------------------------------


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
    """D1: the remote defaults to the invoking repository's origin.

    Taking it as an argument is what lets a test hand the program a throwaway
    bare repository (B3a) without any test-only path inside the program.
    """
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
    """Clone main into the program's own workspace — never the agent's worktree.

    Unchanged files come from main, so a stale working copy cannot smuggle old
    content into the candidate: the candidate is built FROM the declaration.
    """
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
    run_git(["config", "user.name", "nedschorus-git-gatekeeper"], cwd=clone)
    run_git(["config", "user.email", "gatekeeper@nedschorus.invalid"], cwd=clone)
    return clone


def validate_base(clone: Path, base: str) -> None:
    known = run_git(["cat-file", "-e", f"{base}^{{commit}}"], cwd=clone, check=False)
    if known.returncode != 0:
        raise Refusal(
            "unknown-base", f"no commit {base} exists in this repository",
            "Resubmit with --base set to a commit id that exists on main; read the "
            "current tip with: git rev-parse origin/main",
        )
    ancestor = run_git(
        ["merge-base", "--is-ancestor", base, f"origin/{MAIN_BRANCH}"], cwd=clone, check=False
    )
    if ancestor.returncode != 0:
        raise Refusal(
            "base-not-on-main", f"commit {base} is not on main's history",
            "Resubmit with --base set to a commit that is on main; read the current "
            "tip with: git rev-parse origin/main",
        )


def find_existing_check_in(clone: Path, digest: str) -> str | None:
    """The digest screen: work that already went through is never redone."""
    found = run_git(
        ["log", f"origin/{MAIN_BRANCH}", "--format=%H", "--grep", f"Gatekeeper-digest: {digest}"],
        cwd=clone, check=False,
    )
    if found.returncode != 0:
        return None
    lines = [line.strip() for line in found.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


def build_candidate(
    clone: Path, request: dict, worktree: dict[str, bytes | None], digest: str
) -> str:
    """Start from main at the declared base and apply exactly what was declared."""
    run_git(["checkout", "--quiet", "-B", CANDIDATE_BRANCH, request["base"]], cwd=clone)

    for path in request["paths"]:
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


def push_candidate(clone: Path, base: str) -> None:
    """One push. A rejected push means main moved; slice 3 integrates instead."""
    pushed = subprocess.run(
        ["git", "push", "--quiet", "origin", f"{CANDIDATE_BRANCH}:{MAIN_BRANCH}"],
        cwd=str(clone), capture_output=True, text=True, check=False,
    )
    if pushed.returncode == 0:
        return

    stderr = pushed.stderr.strip()
    if "non-fast-forward" in stderr or "fetch first" in stderr or "rejected" in stderr:
        tip = run_git(["rev-parse", f"origin/{MAIN_BRANCH}"], cwd=clone, check=False)
        newer = run_git(
            ["log", "--format=%h %s", f"{base}..origin/{MAIN_BRANCH}"], cwd=clone, check=False
        )
        intervening = newer.stdout.strip() or "unavailable"
        raise Refusal(
            "main-moved",
            f"main moved since the declared base {base}; it is now "
            f"{tip.stdout.strip() or 'unknown'}. Intervening commits:\n{intervening}",
            "Update your working copy from main, re-apply the change on top of it, "
            "and resubmit with --base set to the new tip. The adjusted work digests "
            "fresh and processes as a new request.",
        )
    if "authentication" in stderr.lower() or "permission" in stderr.lower() or "denied" in stderr.lower():
        raise Refusal(
            "push-auth-failed", f"the push was refused: {stderr or 'no stderr'}",
            "Resubmit once the pushing credential is available; this failure is safe "
            "to retry and changed nothing.",
        )
    raise Refusal(
        "network-down", f"the push failed: {stderr or 'no stderr'}",
        "Resubmit; this failure is safe to retry and changed nothing.",
    )


def check_in(arguments) -> int:
    request = screen_form(arguments)
    repository = resolve_repository(arguments.repo)
    remote = resolve_remote(repository, arguments.remote)
    worktree = read_worktree_content(repository, request["paths"])

    workspace: Path | None = None
    try:
        clone_parent = workspace_root() / "screening"
        shutil.rmtree(clone_parent, ignore_errors=True)
        clone_parent.mkdir(parents=True, exist_ok=True)
        clone = prepare_clone(clone_parent, remote)

        validate_base(clone, request["base"])
        base_content = read_base_content(clone, request["base"], request["paths"])
        request["changes"] = classify_changes(worktree, base_content)

        digest = compute_digest(request["base"], worktree, request["import"])
        already = find_existing_check_in(clone, digest)
        if already:
            return emit({
                "outcome": "already-checked-in", "digest": digest, "commit": already,
                "summary": f"already-checked-in {already}",
            }, EXIT_SUCCESS)

        # The request record: written once, read by everything downstream.
        workspace = workspace_root() / digest
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "request.json").write_text(
            json.dumps({**request, "digest": digest, "remote": remote}, indent=2),
            encoding="utf-8",
        )
        (workspace / "worker.pid").write_text(str(os.getpid()), encoding="utf-8")
        shutil.move(str(clone), str(workspace / "candidate"))
        clone = workspace / "candidate"

        commit = build_candidate(clone, request, worktree, digest)
        push_candidate(clone, request["base"])

        advisory = undeclared_changes(repository, request["paths"])
        payload = {
            "outcome": "checked-in", "commit": commit, "digest": digest,
            "summary": f"checked-in {commit}",
        }
        if advisory:
            payload["advisory"] = (
                f"the working copy also differs at {', '.join(advisory)}; confirm intentional"
            )
        return emit(payload, EXIT_SUCCESS)
    finally:
        shutil.rmtree(workspace_root() / "screening", ignore_errors=True)
        if workspace is not None:
            shutil.rmtree(workspace, ignore_errors=True)


def unbuilt_command(name: str, slice_number: int) -> int:
    raise Refusal(
        "unbuilt-option", f"the {name} command is not built in this version",
        f"Nothing to do: {name} arrives in slice {slice_number} of the git-gatekeeper "
        "build (nedschorus#3). Until then, resubmit the work itself with check-in — "
        "resubmitting is always safe.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-gatekeeper.py", description="The single check-in gate for nedschorus.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-in", help="check work in to main")
    check.add_argument("--files", nargs="+", required=True, metavar="PATH")
    check.add_argument("--message", required=True)
    check.add_argument("--base", required=True, metavar="COMMIT")
    check.add_argument("--import", dest="import_declaration", required=True, metavar="none")
    check.add_argument("--issue", required=True, metavar="none|N")
    check.add_argument("--agent", required=True, metavar="RUNTIME/MODEL")
    check.add_argument("--repo", default=None, help="the repository holding the work")
    check.add_argument("--remote", default=None, help="where main lives; defaults to origin")
    mode = check.add_mutually_exclusive_group()
    mode.add_argument("--wait", dest="no_wait", action="store_false", default=False)
    mode.add_argument("--no-wait", dest="no_wait", action="store_true")

    for name in ("status", "cancel"):
        later = commands.add_parser(name, help=f"{name} a request (slice 4)")
        later.add_argument("digest", nargs="?", default=None)
    commands.add_parser("imports", help="print the legacy import table (slice 2)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "check-in":
            return check_in(arguments)
        if arguments.command in ("status", "cancel"):
            return unbuilt_command(arguments.command, 4)
        return unbuilt_command("imports", 2)
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
