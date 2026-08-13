#!/usr/bin/env python3
"""The single program through which every change reaches main in nedschorus.

Specification: docs/cross-project/git-gatekeeper-design.md (canonical).
Build bindings: docs/issues/queue/3-gatekeeper-build-bindings.md (B1-B6).
Build order and the design points left to the builder:
docs/issues/3-git-gatekeeper-build-slice-plan.md. Issue: nedschorus#3.

Slices 1 to 5 of five are built (slice 5's CLAUDE.md workflow lines land
separately, walked with the user). For each request the program does exactly
one of two things — checks the work in, or refuses and teaches the fix. On
success four things are true: the change is on main, the checks ran against
exactly the content pushed, the commit's trailers carry the whole
machine-readable record, and the caller has the commit id.

Built: a synchronous check-in end to end (slice 1); the entry checkpoint — the
recorded gate every legacy import crosses (slice 2; the import record is read
straight from history with `git log origin/main --grep "Gatekeeper-import:"` —
an `imports` table subcommand was built here and deleted by user ruling
2026-08-10, the trailer being the record and the git command the view); and
concurrent check-ins, where a request that loses the race is integrated over
the newer commits by the program rather than by the calling agent (slice 3).

Check-ins run in parallel with no queue and no lock, because GitHub already
provides the one property the design rests on: a push either wins cleanly or
is rejected whole. The winner never learns there was a race. The loser fetches
the new main and re-applies its declared changes onto it, which is clean
whenever the two requests touched different paths — the usual case. When they
touched the same path, re-applying would mean choosing whose version survives,
so the request is refused as `conflict` instead: the program never guesses at
an author's intent.

Slice 4 (built 2026-08-12): --no-wait detaches a worker into its own
session (process group), whose outcome lands in history on success or as
the retained B4d refusal record on refusal; status answers checked-in /
in-progress / abandoned / the retained record (once, then swept) / unknown;
cancel kills the worker's whole process group, waits, then lets history
arbitrate — four outcomes. Every invocation opportunistically sweeps stale
workspaces (30-day refusal records, day-old screening scratch and
dead-worker leftovers). Slice 5 (built 2026-08-12): the branch-protection
audit — `audit` reads main's live protection via gh and answers B3c's three
outcomes, protection-ok / protection-wrong (facts naming every differing
setting) / audit-failed (gh missing, unauthenticated, API error — a loud
finding, never a silent skip); it rides each session recycle via the
fast-handoff writer. Exit code 2 stays reserved for a defect in this
program; the parser layer refuses malformed command lines as JSON, exit 1.

The entry checkpoint's guarantee is that the record cannot lag the system: an
import is declared as a triple, validated against the legacy repository at
instant screening, and written into the trailer of the very commit that
carries it. A second import in one request is inexpressible by construction —
it is a second check-in.

Resubmitting is always safe. The digest identifies the WORK — base, paths and
their bytes — and not the metadata around it, so identical work resubmitted
under a different message deduplicates, and work that already went through
answers already-checked-in with its commit id. An agent that crashed never
reconstructs what happened; it submits again.

The base — the main commit the work started from — is computed by the
program (`git merge-base HEAD origin/main`, after a fetch, in the caller's
checkout), never declared: user ruling 2026-08-10, replacing a --base field
and its two hand-off refusals. Same exact id, no relay step to garble.

Reply contract (B1): exactly one JSON object on stdout, always carrying a
human-readable `summary`. Exit 0 for success and informational answers, 1 for
a catalog refusal (the gatekeeper working correctly), 2 for a program defect.

Records: git history and the invoking session's transcript, and nothing else.
The workspace exists only while a request is in flight and is swept on both
endings, so a refusal leaves the repository and the disk untouched.

Usage:
  git-gatekeeper.py check-in --files <path>... --message <text>
                    --issue none|<n> --agent <runtime/model>
                    (--import none | --import-commit <40-hex>
                     --import-source <path> --import-dest <path>)
                    [--wait] [--repo <dir>] [--remote <url-or-path>]
                    [--legacy-repo <dir>]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
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

# The integration loop is bounded rather than open: refusing beats spinning.
MAX_INTEGRATION_ROUNDS = 5

EXIT_SUCCESS = 0
EXIT_REFUSED = 1
EXIT_DEFECT = 2


class Refusal(Exception):
    """A named catalog refusal: the error, the facts, and the exact next act.

    Never a bare error code. B5: the next action is verb-first and specific —
    "resubmit without that path", never "fix the problem" — and
    one term is used per concept across the whole catalog, because agents
    pattern-match this text. A path is always a "path", never a "file".
    """

    def __init__(self, error: str, facts: str, next_action: str):
        super().__init__(f"{error}: {facts}")
        self.error = error
        self.facts = facts
        self.next_action = next_action


class AlreadyCheckedIn(Exception):
    """This exact work reached main while the request was in flight.

    Not a refusal: the caller wanted the work on main and it is on main. The
    race was lost in the only way that costs nothing.
    """

    def __init__(self, commit: str):
        super().__init__(commit)
        self.commit = commit


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
        "malformed-field",
        f"the {position} path {path!r} contains {detail}",
        "Rename the path so it contains only printable ASCII without whitespace, "
        "then resubmit. Paths of this shape are refused rather than quoted because "
        "the trailer format is unquoted; quoting grows in when a real import needs it.",
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
        seen.add(path)
    return sorted(seen)


def screen_import(arguments, declared_paths: list[str]) -> dict | None:
    """The entry checkpoint's declaration: `none`, or all three parts.

    Every import crosses this gate and is recorded in the commit that carries
    it, so the record can never lag the system. A second import in one request
    is inexpressible by construction — it is a second check-in.
    """
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
    """The canonical one-line form, used by both the digest and the trailer."""
    if import_declaration is None:
        return "none"
    return (f"{import_declaration['commit']} {import_declaration['source']}"
            f" {UNSAFE_PATH_MARKER} {import_declaration['dest']}")


def read_legacy_content(legacy_repository: str, import_declaration: dict) -> bytes:
    """One transaction: the bytes as they stood at the declared legacy commit."""
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
    """Validate every field that can be judged without touching a repository."""
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
        # The base joins the request after screening: it is computed from the
        # caller's checkout (which screening never touches), never declared.
        "issue": arguments.issue,
        "agent": arguments.agent.strip(),
        "import": import_declaration,
        # B4c, the resolve-once rule: every environment-derived field is
        # resolved here, at screening, and written into the request record.
        # Nothing downstream re-derives it from its own environment.
        "origin": os.environ.get("CLAUDE_CODE_SESSION_ID") or "none",
    }


# --- Reading the caller's worktree and computing the base ------------------


def compute_base(repository: Path) -> str:
    """The exact main commit the work started from — computed, never declared.

    `git merge-base HEAD origin/main`, after a fetch, in the caller's checkout
    (user ruling 2026-08-10, replacing a caller-supplied --base field): every
    caller gets the exact right value deterministically, with no relay step to
    garble. The result is on main by construction. Accepted residual, recorded
    in the specification: a caller who refreshed from main mid-task presents a
    too-new fork point — a blind spot the wrapper-derived design shared.
    """
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


def read_worktree_content(
    repository: Path, paths: list[str], import_declaration: dict | None = None
) -> dict[str, bytes | None]:
    """The new content of each declared path; None where the path is absent.

    This is the program's only read of the caller's working copy for content.
    An import destination is the one exception: its bytes come from the legacy
    repository at the declared commit, so the caller need not — and should not
    — stage a hand-made copy of it.
    """
    import_destination = import_declaration["dest"] if import_declaration else None
    content: dict[str, bytes | None] = {}
    for path in paths:
        if path == import_destination:
            continue
        candidate = repository / path
        if candidate.is_symlink():
            raise Refusal(
                "malformed-field", f"the path {path!r} is a symlink",
                "Resubmit naming regular files only: the gate reads regular-file "
                "bytes and does not follow links (ruled 2026-08-12).",
            )
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
    # No aggregate nothing-differs branch exists: it was unreachable — the
    # first unchanged path refuses `unchanged-path` before any aggregate check
    # could run — and was deleted as dead code (user ruling 2026-08-10).
    return changes


def compute_digest(base: str, worktree: dict[str, bytes | None], import_declaration: str) -> str:
    """SHA-256 over the WORK: base, sorted paths, each path's new bytes.

    Deliberately excluded: message, issue, mode, origin, agent, time. The
    digest identifies the work, so identical work resubmitted under different
    metadata still deduplicates — which is what makes resubmission safe.
    """
    digest = hashlib.sha256()

    def frame(tag: bytes, content: bytes) -> None:
        # Length-prefixed under a NUL-framed tag (2026-08-12): tag-only
        # framing was collidable — one file whose bytes contained the tag
        # sequence serialized identically to two files (Codex finding G25).
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
    """Paths the caller's worktree also modifies — an advisory, never a refusal.

    Unrelated work in progress in the same worktree is legitimate, so this
    never blocks; the likeliest cause of a surprise here is a forgotten
    declaration, which is worth saying out loud.
    """
    # Untracked files included (ruled 2026-08-12): a forgotten NEW file is
    # the advisory's likeliest target; .gitignore still hides scratch.
    status = run_git(["status", "--porcelain"], cwd=repository, check=False)
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
        f"Gatekeeper-import: {import_record(request['import'])}",
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


def find_existing_check_in(clone: Path, digest: str, ref: str | None = None) -> str | None:
    """The digest screen: work that already went through is never redone."""
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
    """Start from main at `target` and apply exactly what was declared.

    `target` is the declared base on the first attempt, and the newer main tip
    on each integration round. Either way the candidate is built FROM the
    declaration, so an undeclared edit can never reach it.
    """
    run_git(["checkout", "--quiet", "-B", CANDIDATE_BRANCH, target or request["base"]], cwd=clone)

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


def attempt_push(clone: Path) -> tuple[bool, str]:
    """One atomic push attempt. Returns (won, stderr).

    Everything rests on the one property GitHub provides: a push either wins
    cleanly or is rejected whole — never partial, never interleaved. That is
    the arbiter, which is why no queue and no lock exist here.
    """
    pushed = subprocess.run(
        ["git", "push", "--quiet", "origin", f"{CANDIDATE_BRANCH}:{MAIN_BRANCH}"],
        cwd=str(clone), capture_output=True, text=True, check=False,
    )
    return pushed.returncode == 0, pushed.stderr.strip()


def classify_push_failure(stderr: str) -> str:
    """Lost the race, or something else entirely."""
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
    """Push, and integrate over anyone who got there first. Returns (commit, N).

    The winner of a race completes unaware of it. The loser is handled here,
    not by the calling agent: fetch the new main and re-apply the declared
    changes onto it. Clean re-application is the usual case, because two
    requests usually touch different paths. A real conflict — the new main
    changed a path this request also changes — is refused rather than guessed
    at, because re-applying would mean choosing whose version survives, and
    the program never chooses that.
    """
    base = request["base"]
    target = base

    for _ in range(MAX_INTEGRATION_ROUNDS):
        commit = build_candidate(clone, request, worktree, digest, target)
        # Version 1 re-runs every check against the rebuilt candidate; there
        # are none beyond construction yet, so this is where a test suite
        # attaches when one exists.
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

        # Someone may have checked in this very work while we were building.
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




# --- The worker lifecycle (slice 4) -----------------------------------------
# The caller's process is the worker in --wait mode; --no-wait detaches one.
# Everything here rests on the same invariant as crash recovery: the atomic
# push is the only durable effect, so every state question is answered from
# history plus what the workspace holds.

STALE_SCREENING_SECONDS = 24 * 60 * 60
STALE_WORKSPACE_SECONDS = 24 * 60 * 60
REFUSAL_RECORD_RETENTION_SECONDS = 30 * 24 * 60 * 60


def process_start_time(pid: int) -> str:
    """The /proc start-time of a pid (clock ticks since boot); '' unreadable.

    3.13: a recycled pid can masquerade as a live worker; the start-time
    unmasks it. Linux-specific by design — this box is the gate's home.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return stat.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return ""


def write_worker_identity(workspace: Path) -> None:
    pid = os.getpid()
    (workspace / "worker.pid").write_text(
        f"{pid} {process_start_time(pid)}", encoding="utf-8"
    )


def worker_state(workspace: Path) -> str:
    """'alive', 'dead', or 'none' — the whole state machine's oracle."""
    if not workspace.is_dir():
        return "none"
    try:
        tokens = (workspace / "worker.pid").read_text(encoding="utf-8").split()
        pid = int(tokens[0])
    except (OSError, ValueError, IndexError):
        return "dead"
    recorded_start = tokens[1] if len(tokens) > 1 else "0"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        pass  # alive under another user; still alive
    live_start = process_start_time(pid)
    # "0" is the spawner's placeholder before the worker stamps itself.
    if recorded_start not in ("", "0") and live_start and recorded_start != live_start:
        return "dead"
    return "alive"


def sweep_stale_workspaces() -> None:
    """Opportunistic housekeeping at every invocation (ruled 2026-08-10):
    refusal records older than 30 days, screening scratch and dead-worker
    workspaces older than a day. Never blocks, never reports — a caller
    whose record aged out resubmits, the same recovery as every lost reason.
    """
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
            if age > STALE_WORKSPACE_SECONDS and worker_state(entry) == "dead":
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue


def retain_refusal_record(workspace: Path, digest: str, refusal: Refusal) -> None:
    """B4d: a refused --no-wait request keeps its workspace holding just the
    JSON refusal record; status returns it once, then sweeps."""
    for entry in ("candidate", "declared"):
        shutil.rmtree(workspace / entry, ignore_errors=True)
    (workspace / "worker.pid").unlink(missing_ok=True)
    (workspace / "request.json").unlink(missing_ok=True)
    (workspace / "refusal.json").write_text(json.dumps({
        "outcome": "refused", "error": refusal.error, "facts": refusal.facts,
        "next_action": refusal.next_action, "digest": digest,
        "summary": f"refused: {refusal.error} — {refusal.facts}",
    }), encoding="utf-8")


def require_digest(arguments, command: str) -> str:
    digest = getattr(arguments, "digest", None)
    if not digest:
        raise Refusal(
            "malformed-field", f"{command} needs the request digest",
            f"Resubmit as: git-gatekeeper.py {command} <digest> — the digest is "
            "in the reply of the submission being asked about.",
        )
    return digest


def fetch_and_find(repository: Path, digest: str) -> str | None:
    run_git(["fetch", "--quiet", "origin", MAIN_BRANCH], cwd=repository, check=False)
    return find_existing_check_in(repository, digest)


def run_worker(arguments) -> int:
    """The detached half of --no-wait. Detached means nobody is listening:
    outcomes land in history (success) or the B4d record (refusal), where
    status finds them. Never prints; the reply channel is the workspace."""
    workspace = workspace_root() / arguments.digest
    record_path = workspace / "request.json"
    if not record_path.is_file():
        return EXIT_DEFECT
    request = json.loads(record_path.read_text(encoding="utf-8"))
    digest = request["digest"]

    # Stamp identity, yielding briefly to the spawner's placeholder write so
    # the exact start-time always wins the file.
    deadline = time.time() + 2
    while not (workspace / "worker.pid").is_file() and time.time() < deadline:
        time.sleep(0.05)
    write_worker_identity(workspace)

    pause = float(os.environ.get("GATEKEEPER_TEST_WORKER_PAUSE", "0") or 0)
    if pause:  # test seam: holds the WORKING state open for cancel/liveness cases
        time.sleep(pause)

    worktree: dict[str, bytes | None] = {}
    for path, change in request["changes"].items():
        worktree[path] = (
            None if change == "deleted"
            else (workspace / "declared" / path).read_bytes()
        )
    clone = workspace / "candidate"
    try:
        try:
            integrate_and_push(clone, request, worktree, digest)
        except AlreadyCheckedIn:
            pass
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
    workspace = workspace_root() / digest
    record_path = workspace / "refusal.json"
    if record_path.is_file():
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {"outcome": "refused", "error": "workspace-io-error",
                       "facts": "the retained refusal record was unreadable",
                       "next_action": "Resubmit the work; resubmitting is always safe.",
                       "digest": digest,
                       "summary": "refused: workspace-io-error — record unreadable"}
        shutil.rmtree(workspace, ignore_errors=True)  # returned once, then swept (B4d)
        return emit(payload, EXIT_REFUSED)
    state = worker_state(workspace)
    if state == "alive":
        return emit({"outcome": "in-progress", "digest": digest,
                     "summary": "in-progress — a live worker holds this request; "
                                "ask again shortly"}, EXIT_SUCCESS)
    if state == "dead":
        return emit({"outcome": "abandoned", "digest": digest,
                     "summary": "abandoned — workspace present, worker dead; "
                                "resubmit safely, the sweep is automatic"}, EXIT_SUCCESS)
    return emit({"outcome": "unknown", "digest": digest,
                 "summary": "unknown — no trace of this digest; submit it, "
                            "submitting is always safe"}, EXIT_SUCCESS)


def cancel_request(arguments) -> int:
    """Outcomes, exactly four (spec § States, crashes, cancel, and errors)."""
    digest = require_digest(arguments, "cancel")
    repository = resolve_repository(getattr(arguments, "repo", None))
    commit = fetch_and_find(repository, digest)
    if commit:
        return emit({"outcome": "too-late", "digest": digest, "commit": commit,
                     "summary": f"too-late — already-checked-in {commit}; the remedy "
                                "for a bad checked-in change is a revert through the "
                                "same gate"}, EXIT_SUCCESS)
    workspace = workspace_root() / digest
    state = worker_state(workspace)
    if state == "none":
        return emit({"outcome": "unknown-request", "digest": digest,
                     "summary": "unknown-request — no trace of this digest"},
                    EXIT_SUCCESS)
    if state == "alive":
        # WALK-4 (ruled 2026-08-12): kill the whole process group and WAIT —
        # a pid-only kill leaves an already-spawned git push child racing the
        # history query below.
        try:
            pid = int((workspace / "worker.pid").read_text(encoding="utf-8").split()[0])
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ValueError, ProcessLookupError, PermissionError):
            pass
        deadline = time.time() + 10
        while time.time() < deadline and worker_state(workspace) == "alive":
            time.sleep(0.1)
        if worker_state(workspace) == "alive":
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (OSError, ProcessLookupError, PermissionError):
                pass
            while time.time() < deadline + 5 and worker_state(workspace) == "alive":
                time.sleep(0.1)
        commit = fetch_and_find(repository, digest)
        if commit:
            shutil.rmtree(workspace, ignore_errors=True)
            return emit({"outcome": "too-late", "digest": digest, "commit": commit,
                         "summary": f"too-late — already-checked-in {commit}; the "
                                    "push won the race"}, EXIT_SUCCESS)
    shutil.rmtree(workspace, ignore_errors=True)
    return emit({"outcome": "cancelled", "digest": digest,
                 "summary": "cancelled — the workspace is swept; nothing reached "
                            "main"}, EXIT_SUCCESS)


# --- The branch-protection audit (slice 5) ----------------------------------
# B3c: three named outcomes — protection-ok / protection-wrong / audit-failed
# — failing loudly as its own outcome, never a silent skip into green. Rides
# each session recycle (ruled 2026-08-12) via the fast-handoff writer.

# The contract the audit checks (spec § The credential and enforcement, LIVE
# since 2026-07-21). The C3 amendment moves the pusher to the dedicated
# account — update this set in the same commit that applies it.
EXPECTED_MAIN_PUSHER_ACCOUNTS = {"NedLern"}


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
        raise Refusal(
            "audit-failed",
            f"reading protection for {repo_slug} failed: "
            f"{completed.stderr.strip() or completed.stdout.strip() or 'no detail'}",
            "Authenticate gh with an account that can read branch protection, or "
            "fix the network, then re-run. An unreadable wall is a finding, never "
            "a silent skip into green.",
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise Refusal(
            "audit-failed", "the protection reply was not JSON",
            "Re-run the audit; if this repeats, gh or the API changed shape.",
        ) from None


def compare_protection(protection: dict) -> list[str]:
    """Every way the live settings differ from the design, in plain words."""
    problems: list[str] = []
    restrictions = protection.get("restrictions")
    if not restrictions:
        problems.append(
            "no push restriction exists; the design restricts main pushes to "
            f"exactly {sorted(EXPECTED_MAIN_PUSHER_ACCOUNTS)}"
        )
    else:
        users = sorted(u.get("login", "") for u in restrictions.get("users") or [])
        if set(users) != EXPECTED_MAIN_PUSHER_ACCOUNTS:
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
        if arguments.protection_file:  # test seam, C7 class: replaces only the fetch
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
        # Per-process scratch, never a shared fixed path: check-ins run in
        # parallel by design, and a shared screening directory would have one
        # request delete another's clone out from under it. The digest is not
        # known yet — it needs the base content — so the per-digest workspace
        # cannot be used until screening is done.
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

        # 4.1 (ruled 2026-08-10): concurrent identical submissions share one
        # digest workspace — a live twin is answered, never swept from under.
        existing = workspace_root() / digest
        if worker_state(existing) == "alive":
            return emit({
                "outcome": "in-progress", "digest": digest,
                "summary": "in-progress — a live worker already holds this exact "
                           f"work; collect the outcome with: status {digest}",
            }, EXIT_SUCCESS)
        shutil.rmtree(existing, ignore_errors=True)

        # The request record: written once, read by everything downstream.
        workspace = existing
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "request.json").write_text(
            json.dumps({**request, "digest": digest, "remote": remote}, indent=2),
            encoding="utf-8",
        )
        write_worker_identity(workspace)
        # The declaration snapshot: the worker (and any resubmit-side rebuild)
        # reads declared bytes from here, never from the caller's live
        # worktree, whose state at worker time is nobody's promise (B4c).
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
            (workspace / "worker.pid").write_text(
                f"{spawned.pid} 0", encoding="utf-8"  # worker stamps exact identity
            )
            workspace = None  # ownership passed to the worker; do not sweep
            return emit({
                "outcome": "accepted", "digest": digest,
                "next_action": f"Collect the outcome with: git-gatekeeper.py "
                               f"status {digest}",
                "summary": f"accepted {digest}",
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
    """Command-line-form errors join the JSON contract (user-ruled 2026-08-11).

    argparse's default is usage text on stderr and exit 2 — the defect code.
    A caller's typo is not a gatekeeper defect: it refuses like every other
    malformed field, teaching form intact, exit 1.
    """

    def error(self, message):
        raise Refusal(
            "malformed-field", f"the command line is malformed: {message}",
            "Resubmit with a corrected invocation; the request grammar is in the "
            "specification (docs/cross-project/git-gatekeeper-design.md) and in "
            "--help.",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = TeachingArgumentParser(
        prog="git-gatekeeper.py", description="The single check-in gate for nedschorus.",
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

    worker = commands.add_parser("worker", help="internal: the detached --no-wait worker")
    worker.add_argument("digest")

    audit = commands.add_parser(
        "audit", help="check main's live branch protection against the design (B3c)")
    audit.add_argument("--repo", default=None,
                       help="checkout whose origin names the repository")
    audit.add_argument("--repo-slug", default=None, metavar="OWNER/REPO")
    audit.add_argument("--protection-file", default=None, metavar="JSON",
                       help="test seam: read settings from a file instead of gh")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
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
