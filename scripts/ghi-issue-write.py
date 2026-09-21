#!/usr/bin/env python3
"""File a GitHub issue from its GHI-MD, then make the issue's body the links
to that issue's files. The `create` verb of the GHI write tool.

WHAT THIS IS. The user ruled on 2026-09-15 that a GHI's body is the link to
its paired markdown file and nothing else: one copy of every fact, GitHub
holding the state and the file holding the content. Nothing could build that
rule by hand, because a body of links needs its files on main first and main
takes no direct push. This is the program that does it. Designed in
docs/issues/46-ghi-info-agent-design.md § The GHI write path; that design is
the authority and this docstring does not restate it.

WHAT IS AND IS NOT IN THIS SLICE. Only `create`. The `edit` verb, the
comment verb and the PreToolUse hook that redirects raw `gh issue
create`/`edit` into this tool are each their own slice, unbuilt. So today an
author calls this program by name, and nothing stops a raw `gh issue create`
alongside it, which is the accepted cooperative posture the design states.

THE SEQUENCE, and what makes each step safe to run twice:

  1. Validate   the file exists, opens with a heading, and is not already at
                a paired path.
  2. Adjudicate ask ghi-info whether an open issue already covers this.
                Fail-open: unreachable means the write proceeds.
  3. File       gh issue create, title from the file's first heading, body a
                placeholder carrying this file's pairing key.
  4. Name+land  copy the file to docs/issues/<number>-<slug>.md in a
                throwaway worktree cut from a just-fetched origin/main,
                commit, push, open a pull request.
  5. Link       rewrite the body as one link per file of docs/issues/<n>-*.

RESUMING, and why there is no state file. Steps 3 to 5 are three separate
remote operations and any of them can fail, leaving an issue with a
placeholder body and no file, or a file on a branch nobody merged. A rerun
on the same path must continue rather than file a second issue. The pairing
key makes that possible with nothing stored on disk: it is a hash of the
file's content, written into the placeholder body at step 3, and a rerun
finds its own issue by scanning open issues for it. The user chose this over
a state file and over matching on the title (2026-09-20); a title can
collide, because adjudication fails open, and a rerun matching a title could
adopt another issue.

The scan reads bodies directly rather than using GitHub's search index,
which is not immediate: a rerun seconds after a failure must still find the
issue, and `gh issue list --json body` answers from the API rather than the
index.

Step 4 is idempotent through its branch name, which is derived from the
issue number and slug rather than generated: if that branch is already on
the remote, its pull request is open and waiting for merge-lane, and the
rerun says so instead of opening a second one.

WHERE THE GIT WORK HAPPENS. In a throwaway worktree cut from a just-fetched
origin/main, removed afterwards. The user ruled this on 2026-09-20, in place
of the design's original ghi-info checkout on ned-box reached over ssh. The
2026-09-15 ruling it replaces wanted one thing — that a write never runs
against stale disk — and a worktree made from a fresh fetch cannot be stale
or dirty by construction. It also means filing an issue does not need the
box reachable. What is given up: writes no longer funnel through one
machine, so two seats filing at once each push their own branch; they are
separate branches and separate pull requests, so nothing collides.

Usage:
  ghi-issue-write.py create <path-to-ghi-md> [--repo OWNER/NAME]
                     [--dry-run]

The author gives the file its cold read before calling this (user-ruled
2026-09-20). This program does not check that one happened: the design puts
that on the front-loading layer, as it does routing.

Exit codes:
  0   the issue is filed, its file is on a pull request, its body is links
      (or the run resumed and said what is still outstanding)
  1   an operating failure — gh, git or the network
  64  the caller's input is wrong: no such file, no heading, already paired
  65  refused by adjudication as too similar to an open issue
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REPO = "nedschorus/nedschorus"
PAIRED_DIRECTORY = "docs/issues"
PAIRING_KEY_PREFIX = "ghipair"
RECONSIDERED_MARKER_NAME = ".ghi-issue-write-reconsidered"
SLUG_WORD_LIMIT = 8
GH_TIMEOUT_SECONDS = 120
ADJUDICATION_TIMEOUT_SECONDS = 420

RECONSIDER_LINE = (
    "If you believe this refusal is wrong, reconsider once against its stated "
    "reason. Still convinced, write your reasoning into "
    f"{RECONSIDERED_MARKER_NAME} at the repository root and resubmit — the "
    "marker passes exactly one write and is consumed by it.")


class Refused(Exception):
    """A refusal the caller can act on. Carries its own exit code."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def run(arguments, timeout=GH_TIMEOUT_SECONDS, cwd=None, check=True):
    """Every subprocess this program makes goes through here, so a test can
    replace one function rather than patching subprocess itself."""
    completed = subprocess.run(
        arguments, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        check=False)
    if check and completed.returncode != 0:
        raise Refused(
            f"{' '.join(arguments[:3])} failed: "
            f"{(completed.stderr or completed.stdout).strip()}", 1)
    return completed


def pairing_key(file_text: str) -> str:
    """This file's identity, and the only thing tying a half-finished run to
    the issue it already created. Content rather than path, because step 4
    moves the file."""
    digest = hashlib.sha256(file_text.encode("utf-8")).hexdigest()[:16]
    return f"{PAIRING_KEY_PREFIX}{digest}"


def first_heading(file_text: str) -> str:
    """The file's first ATX heading, which becomes the issue's title. The
    user ruled 2026-09-16 that the title is generated rather than typed, so
    the two cannot disagree.

    A leading YAML frontmatter block is skipped before looking. Measured on
    2026-09-20: of the 25 files in docs/issues/, 14 carry frontmatter before
    their heading and 11 open with one, so a parser that required the file to
    open with a heading would have refused the majority of the corpus it
    exists to serve."""
    lines = file_text.splitlines()
    index = 0
    if lines and lines[0].strip() == "---":
        for position in range(1, len(lines)):
            if lines[position].strip() == "---":
                index = position + 1
                break
    for line in lines[index:]:
        if line.strip().startswith("#"):
            return line.strip().lstrip("#").strip()
    return ""


def slug(title: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", title.lower()).split()
    return "-".join(words[:SLUG_WORD_LIMIT]) or "issue"


def placeholder_body(key: str) -> str:
    return (f"Filing in progress, pairing key {key}. This body becomes the "
            "links to this issue's files once they land on main. If it still "
            "reads this way, rerun `scripts/ghi-issue-write.py create` on the "
            "file and it will continue from where it stopped.")


def links_body(repo: str, paths) -> str:
    """The body under link-only: one link per paired file, in filename order,
    and nothing else. Derived at every write, so nobody curates it and it
    cannot fall behind the files."""
    lines = []
    for path in sorted(paths):
        name = Path(path).name
        lines.append(f"- [{name}](https://github.com/{repo}/blob/main/{path})")
    return "\n".join(lines)


# --- The steps ----------------------------------------------------------

def validate(path: Path):
    """Step 1. Refuses rather than guesses: a file with no heading has no
    title to generate, and a file already at a paired path belongs to an
    issue that exists."""
    if not path.is_file():
        raise Refused(f"no such file: {path}", 64)
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise Refused(f"{path} is empty", 64)
    title = first_heading(text)
    if not title:
        raise Refused(
            f"{path} has no heading, so there is no title to generate from "
            "it. The issue's title is the file's first heading, after any "
            "frontmatter (user-ruled 2026-09-16).", 64)
    if re.match(r"^\d+-", path.name):
        raise Refused(
            f"{path} is already named for an issue, so that issue exists. A "
            "paired file carries its issue's number wherever it sits, so this "
            "check does not depend on the directory. To change a paired file, "
            "use the edit verb, which is not built yet.", 64)
    return text, title


def find_existing_pairing(repo: str, key: str, runner):
    """The resume path. Reads bodies from the API rather than the search
    index, which is not immediate — a rerun seconds after a failure must
    still find its issue."""
    completed = runner(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--limit", "300", "--json", "number,body,title"])
    for issue in json.loads(completed.stdout or "[]"):
        if key in (issue.get("body") or ""):
            return issue
    return None


def adjudicate(repo: str, title: str, text: str, repository_root: Path,
               runner, report):
    """Step 2. Fail-open by design: ghi-info unreachable means the write
    proceeds, because an infrastructure failure must never look like a
    refusal. A too-similar verdict is a soft block — the caller reconsiders
    once and passes by leaving its reasoning in the marker file."""
    marker = repository_root / RECONSIDERED_MARKER_NAME
    if marker.is_file():
        marker.unlink()
        report("adjudication skipped: the reconsidered marker was present "
               "and is consumed by this write")
        return
    ask = repository_root / "scripts" / "ghi-info-ask.py"
    if not ask.is_file():
        report("adjudication skipped: ghi-info-ask.py is not in this "
               "checkout")
        return
    question = (
        "Does an open issue already cover this ground? Reply with exactly "
        "one line: `verdict: too-similar #n`, `verdict: related #n,#m`, or "
        "`verdict: unrelated`.\n\n"
        f"Draft title: {title}\n\nDraft GHI-MD, verbatim:\n\n{text}")
    try:
        completed = runner([sys.executable, str(ask), question],
                           timeout=ADJUDICATION_TIMEOUT_SECONDS, check=False)
    except Exception as failure:                      # noqa: BLE001
        report(f"adjudication skipped: ghi-info did not answer ({failure})")
        return
    if completed.returncode != 0:
        report("adjudication skipped: ghi-info did not answer")
        return
    verdict = ""
    for line in (completed.stdout or "").splitlines():
        if line.strip().lower().startswith("verdict:"):
            verdict = line.strip()
    if not verdict:
        report("adjudication skipped: ghi-info's reply had no verdict line")
        return
    if "too-similar" in verdict.lower():
        raise Refused(
            f"Refused: {verdict}. Read that issue, then merge this content "
            f"into it by editing it, not as a new issue.\n\n{RECONSIDER_LINE}",
            65)
    report(f"ghi-info: {verdict}")


def file_issue(repo: str, title: str, key: str, runner, report) -> int:
    """Step 3. The placeholder body carries the pairing key, which is the
    only thing a rerun has to find this issue by."""
    completed = runner(
        ["gh", "issue", "create", "--repo", repo, "--title", title,
         "--body", placeholder_body(key)])
    report((completed.stdout or "").strip())
    match = re.search(r"/issues/(\d+)", completed.stdout or "")
    if not match:
        raise Refused(
            "gh issue create returned no issue URL, so this run cannot tell "
            "which issue it made. Rerun on the same file: the pairing key "
            "will find it if it exists.", 1)
    return int(match.group(1))


def land_file(repo: str, number: int, title: str, source: Path,
              repository_root: Path, runner, report) -> str:
    """Step 4, in a throwaway worktree cut from a just-fetched origin/main,
    so the commit is never made against stale or dirty disk.

    Idempotent through the branch name rather than through a record: the name
    is derived from the issue, so a branch already on the remote means the
    pull request is open and waiting, and a rerun says so."""
    branch = f"ghi-{number}-{slug(title)}"
    destination = f"{PAIRED_DIRECTORY}/{number}-{slug(title)}.md"

    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    on_remote = runner(
        ["git", "ls-remote", "--heads", "origin", branch],
        cwd=str(repository_root))
    if (on_remote.stdout or "").strip():
        report(f"step 4 already done: branch {branch} is on the remote and "
               "its pull request is waiting for merge-lane")
        return destination

    worktree_parent = Path(tempfile.mkdtemp(prefix="ghi-issue-write-"))
    worktree = worktree_parent / "worktree"
    try:
        runner(["git", "worktree", "add", "--quiet", "-b", branch,
                str(worktree), "origin/main"], cwd=str(repository_root))
        target = worktree / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        runner(["git", "add", destination], cwd=str(worktree))
        message = (f"GHI-MD for issue {number}: {title}\n\n"
                   f"Filed by scripts/ghi-issue-write.py from {source.name}. "
                   "The issue's body becomes the links to this file and its "
                   "siblings once this lands.\n")
        runner(["git", "commit", "--quiet", "-m", message], cwd=str(worktree))
        runner(["git", "push", "--quiet", "-u", "origin", branch],
               cwd=str(worktree))
        body = (f"The GHI-MD for issue #{number}, filed by "
                "`scripts/ghi-issue-write.py`.\n\nUnder link-only that "
                "issue's body is the links to its files, so this file has to "
                "be on main before the body can point at it. Prose under "
                "`docs/`, silent to reviewers by CLAUDE.md's review-scope "
                "rule.\n")
        created = runner(
            ["gh", "pr", "create", "--repo", repo, "--base", "main",
             "--head", branch, "--title", f"GHI-MD for issue {number}: {title}",
             "--body", body], cwd=str(worktree))
        report((created.stdout or "").strip())
    finally:
        runner(["git", "worktree", "remove", "--force", str(worktree)],
               cwd=str(repository_root), check=False)
        shutil.rmtree(worktree_parent, ignore_errors=True)
    return destination


def paired_paths(number: int, repository_root: Path, runner):
    """Every file paired with this issue that is on main. The body is built
    from this, so a file still sitting on an unmerged branch is not linked —
    a link that does not resolve is worse than a body that is not finished."""
    listed = runner(
        ["git", "ls-tree", "-r", "--name-only", "origin/main",
         f"{PAIRED_DIRECTORY}/"], cwd=str(repository_root), check=False)
    prefix = f"{PAIRED_DIRECTORY}/{number}-"
    return [line for line in (listed.stdout or "").splitlines()
            if line.startswith(prefix)]


def link_body(repo: str, number: int, repository_root: Path, runner, report):
    """Step 5. Nothing happens until the file is on main: until then the body
    keeps its placeholder, which tells the next reader to rerun."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root),
           check=False)
    paths = paired_paths(number, repository_root, runner)
    if not paths:
        report(f"step 5 not done: no file for issue {number} is on main yet. "
               "The pull request from step 4 is waiting for merge-lane. Rerun "
               "this command once it merges and the body becomes its links.")
        return False
    runner(["gh", "issue", "edit", str(number), "--repo", repo,
            "--body", links_body(repo, paths)])
    report(f"body is now {len(paths)} link(s): " + ", ".join(paths))
    return True


def create(path: Path, repo: str, repository_root: Path, runner, report):
    """The whole sequence, and the one function the tests drive."""
    text, title = validate(path)
    key = pairing_key(text)

    existing = find_existing_pairing(repo, key, runner)
    if existing:
        number = existing["number"]
        report(f"resuming issue {number}: its body still carries this file's "
               "pairing key, so an earlier run stopped partway")
    else:
        adjudicate(repo, title, text, repository_root, runner, report)
        number = file_issue(repo, title, key, runner, report)

    land_file(repo, number, title, path, repository_root, runner, report)
    finished = link_body(repo, number, repository_root, runner, report)
    return number, finished


def repository_root_of(path: Path) -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(path),
        capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise Refused(f"{path} is not inside a git checkout", 64)
    return Path(completed.stdout.strip())


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="File a GitHub issue from its GHI-MD and make the "
                    "issue's body the links to that issue's files.")
    sub = parser.add_subparsers(dest="verb", required=True)
    creator = sub.add_parser("create", help="file a new issue from a GHI-MD")
    creator.add_argument("path")
    creator.add_argument("--repo", default=DEFAULT_REPO)
    creator.add_argument(
        "--dry-run", action="store_true",
        help="validate the file and print what would be filed, touching "
             "neither GitHub nor git")
    arguments = parser.parse_args(argv)

    path = Path(arguments.path).resolve()

    def report(line):
        if line:
            print(line)

    try:
        if arguments.dry_run:
            text, title = validate(path)
            report(f"would file: {title}")
            report(f"pairing key: {pairing_key(text)}")
            report(f"would land at: {PAIRED_DIRECTORY}/<number>-"
                   f"{slug(title)}.md")
            return 0
        root = repository_root_of(path.parent)
        number, finished = create(path, arguments.repo, root, run, report)
        if not finished:
            report(f"issue {number} is filed and its file is on a pull "
                   "request; rerun this command after that merges.")
        return 0
    except Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return refusal.code
    except subprocess.TimeoutExpired as expiry:
        print(f"timed out: {expiry}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
