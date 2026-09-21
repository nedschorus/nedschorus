#!/usr/bin/env python3
"""File a GitHub issue from its GHI-MD, then make the issue's body the links
to that issue's files; and land an edit to one of those files, after which
the issue follows it. The `create` and `edit` verbs of the GHI write tool.

WHAT THIS IS. The user ruled on 2026-09-15 that a GHI's body is the link to
its paired markdown file and nothing else: one copy of every fact, GitHub
holding the state and the file holding the content. Nothing could build that
rule by hand, because a body of links needs its files on main first and main
takes no direct push. This is the program that does it. Designed in
docs/issues/46-ghi-info-agent-design.md § The GHI write path; that design is
the authority and this docstring does not restate it.

WHAT IS AND IS NOT IN THIS SLICE. `create` and `edit`. The comment verb
and the PreToolUse hook that redirects raw `gh issue create`/`edit` into
this tool are each their own slice, unbuilt. So today an author calls this
program by name, and nothing stops a raw `gh issue create` alongside it,
which is the accepted cooperative posture the design states.

THE SEQUENCE, and what makes each step safe to run twice:

  1. Validate   the file exists, opens with a heading, and is not already
                paired with an issue whose filing finished.
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

WHAT A RERUN TESTS, and why it is not the branch. Step 4 asks first
whether main's copy of the destination is already the file this run would
land, and stops there when it is. It asks about the branch only after that.
The order is the whole of it: a merged pull request's head branch is deleted
here seconds after the merge, so a branch test finds nothing exactly when
the work is most finished, and the run walks into `git worktree add` and
`git commit` with nothing to commit (reviewed 2026-09-21, on PR [Build the
GHI write tool's create verb](https://github.com/nedschorus/nedschorus/pull/569),
where both deaths were reproduced against a real repository). A branch says
whether this run's work is in flight; main says whether it is done, and done
is what a rerun needs to know.

The branch test that remains answers a different question — is a pull
request open on it — and it asks GitHub rather than assuming: a run whose
push succeeded and whose `gh pr create` then failed leaves a branch with no
pull request, and every rerun after that would otherwise report one waiting
forever. Finding none, the rerun opens it.

The worktree is cut with --detach and the push names the branch as a
refspec, so nothing is created in the filing checkout that could outlive the
run: a branch made with `git worktree add -b` survives `git worktree
remove --force`, and the next run's add then fails on the name.

AFTER THE MERGE, WHAT TO RERUN ON. Step 4 is a move when the source is
already tracked on main, so the merge takes the source path off main and the
author's pull takes it off disk; a rerun on that path has nothing to read.
So a paired file — one whose name carries an issue number — is accepted as
the resume entry point when that issue's body is still a placeholder, and
the run finishes at step 5. When the body is no longer a placeholder the
filing is done, and the refusal at step 1 stands: changing a paired file is
the edit verb's work.

WHERE THE GIT WORK HAPPENS. In a throwaway worktree cut from a just-fetched
origin/main, removed afterwards. The user ruled this on 2026-09-20, in place
of the design's original ghi-info checkout on ned-box reached over ssh. The
2026-09-15 ruling it replaces wanted one thing — that a write never runs
against stale disk — and a worktree made from a fresh fetch cannot be stale
or dirty by construction. It also means filing an issue does not need the
box reachable. What is given up: writes no longer funnel through one
machine, so two seats filing at once each push their own branch; they are
separate branches and separate pull requests, so nothing collides.

EDITING AN ISSUE IS EDITING ITS GHI-MD. `edit <path>` takes a file
already paired with an issue — a paired file carries its issue's number in
its name wherever it sits — and does four things:

  1. Validate   the file exists, opens with a heading, is named for an
                issue, and sits where this tool may write: docs/issues/
                before its system's code starts, the system's own directory
                after.
  2. Adjudicate as create does, with this issue left out of the comparison,
                which the cold-start prompt's item 2 asks for. Skipped when
                main's copy is already this file, since a rerun that only
                finishes step 4 has nothing new to adjudicate.
  3. Land       the author's file, when it differs from main's copy, on a
                pull request, the way create's step 4 lands a new one.
  4. Title      when the edit CHANGED the file's first heading, and the
                issue has one paired file.
  5. Link       the body to the paired files on main, as create's step 5
                writes it in the first place.

THE TITLE FOLLOWS A CHANGE, NOT A MISMATCH. The design's trigger is "when
the edit changes the file's first heading", and reading that as "make the
title match the heading" would be a different tool. Measured 2026-09-20 over
the paired corpus on main: 35 files have a heading that differs from their
issue's title, so the matching rule renames most issues the first time
anybody edits one. An issue with several paired files is left alone even
when the heading did change — issue 3 has six files with six headings, and
nothing in the pairing says which one names it — and the tool says so
rather than guessing.

THE CONFLICT THIS REFUSES ON IS THE FILE'S, NOT THE BODY'S. The user ruled
on 2026-09-08 that a GHI edit checks for conflicts and refuses rather than
merges; scripts/ghi-issue-body-edit.py is that ruling built, for the world
where an author typed the body. Under link-only the body is computed from
main's file set, so two seats computing it reach the same answer and there
is no body change to lose. The content is in the file, so the file is where
the check belongs: main's copy is compared against the copy at `git
merge-base HEAD origin/main`, the version the author's checkout started
from, which is the base record they read — taken from git rather than asked
for as a flag, since git already holds it. They differ, and another seat
changed the file since: the tool prints that diff and writes nothing. No
retry, no lock, no merge, as the ruling says.

THE ORDER MATTERS FOR RESUMING. Main's copy is compared to the author's
BEFORE the conflict check runs, because once the pull request merges the
author's own landed change is a difference between the merge base and main,
and a conflict check made first would refuse an author their own edit on the
rerun that finishes step 4.

A PROSE BODY IS LEFT ALONE, NOT RELINKED AND NOT REFUSED. The design says
that until an issue is migrated it keeps its prose body and is read as it
stands, and measurement says that is every issue this verb can reach:
2026-09-20, all 26 paired issues on main still carry the prose body they
were filed with, migrating them being its own build-slice. So step 5 writes
only over a body this tool wrote — its link list, or create's placeholder —
reports what it found otherwise, and finishes. Refusing instead would shut
the verb out of the whole existing corpus, and refusing AFTER the file had
landed would refuse an author work that had already happened.

Usage:
  ghi-issue-write.py create <path-to-ghi-md> [--repo OWNER/NAME] [--dry-run]
  ghi-issue-write.py edit <path-to-paired-ghi-md> [--repo OWNER/NAME]
                     [--dry-run]

A rerun after the merge is given the file that still exists: the source
where filing left it alone, its landed copy under docs/issues/ where filing
moved it. The run that stops at step 4 names that path in its last line.

The author gives the file its cold read before calling this (user-ruled
2026-09-20). This program does not check that one happened: the design puts
that on the front-loading layer, as it does routing.

Exit codes:
  0   the work is done — or the run resumed and said what is still
      outstanding
  1   an operating failure — gh, git or the network
  64  the caller's input is wrong: no such file, no heading, paired when
      create wants it unpaired or unpaired when edit wants it paired, or a
      path this tool does not write
  65  refused by adjudication as too similar to an open issue
  66  refused: the file changed on main since the caller's checkout started
      from it, so landing would discard that change (edit)

The 66 refusal is the one deny path here that does not end with the
reconsider line, deliberately. A conflict is not a judgment to think
again about: another seat's change is sitting on main, and the way past it
is to fold that change in, which the refusal says and shows. The marker
could not pass it in any case — adjudication consumes the marker before
this check is reached — and a line promising otherwise would be false. The
2026-09-08 ruling this implements gives a conflict no reconsider path
either.
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
SYSTEM_DIRECTORY = "nc-systems"
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
            "file and it will continue from where it stopped. If that file is "
            f"gone, rerun it on this issue's file under {PAIRED_DIRECTORY}/.")


ISSUE_FRONTMATTER_KEY = "issue"


def issue_frontmatter_line(repo: str, number: int, title: str) -> str:
    """The issue this file is paired with, written the way CLAUDE.md says to
    cite one: its type word — the key — then its title, as a link. Never a
    bare number."""
    return (f"{ISSUE_FRONTMATTER_KEY}: [{title}]"
            f"(https://github.com/{repo}/issues/{number})")


def with_issue_frontmatter(text: str, repo: str, number: int,
                           title: str) -> str:
    """Set the file's `issue:` frontmatter line, adding a frontmatter block
    if it has none.

    The author writes the file before its issue exists, so the file cannot
    name its issue at the moment it is written and nothing later fills it in;
    measured 2026-09-20, every dated frontmatter field in the corpus was
    older than its file's last change, because a field a person must remember
    to update is a field that drifts. So this one is derived and rewritten on
    every run rather than authored once, which is the same reason the body is
    a computed list of links.

    Only this key is touched. `status:`, `form:` and the rest say things git
    and GitHub cannot, and they stay exactly as their author wrote them."""
    line = issue_frontmatter_line(repo, number, title)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "---\n" + line + "\n---\n\n" + text
    closing = None
    for position in range(1, len(lines)):
        if lines[position].strip() == "---":
            closing = position
            break
    if closing is None:
        # An unterminated block: prepend rather than guess where it ends.
        return "---\n" + line + "\n---\n\n" + text
    for position in range(1, closing):
        if lines[position].startswith(f"{ISSUE_FRONTMATTER_KEY}:"):
            lines[position] = line
            break
    else:
        lines.insert(1, line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


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

def paired_issue_number(path: Path):
    """The issue number a paired file carries in its name, or None for a file
    that is not paired. A paired file carries the number wherever it sits, so
    this does not look at the directory."""
    match = re.match(r"^(\d+)-", path.name)
    return int(match.group(1)) if match else None


def issue_body_carries_pairing_key(repo: str, number: int, runner) -> bool:
    """Whether this issue's body is still the placeholder a create wrote,
    which is what tells a rerun on a paired file that the filing stopped
    partway rather than finished. Read from the API for the same reason the
    resume scan is: a rerun seconds after a failure must see the write."""
    viewed = runner(["gh", "issue", "view", str(number), "--repo", repo,
                     "--json", "body"])
    body = (json.loads(viewed.stdout or "{}") or {}).get("body") or ""
    return PAIRING_KEY_PREFIX in body


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
    if paired_issue_number(path) is not None:
        raise Refused(
            f"{path} is already named for an issue, so that issue exists. A "
            "paired file carries its issue's number wherever it sits, so this "
            "check does not depend on the directory. To change a paired file, "
            "use the edit verb.", 64)
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
               runner, report, exclude_issue=None):
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
    excluded = ""
    if exclude_issue is not None:
        excluded = (f"This draft is an edit of issue #{exclude_issue}: leave "
                    "that issue out of the comparison.\n\n")
    question = (
        "Does an open issue already cover this ground? Reply with exactly "
        "one line: `verdict: too-similar #n`, `verdict: related #n,#m`, or "
        "`verdict: unrelated`.\n\n" + excluded +
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
        # The design's § Prompts gives this refusal verbatim, including the
        # paragraph that appears only for an edit; the slots are filled from
        # the verdict line and the issue being edited.
        cited = re.search(r"#(\d+)", verdict)
        covering = f"#{cited.group(1)}" if cited else "that issue"
        paragraphs = [
            f"Refused: {covering} already covers this ground. Read "
            f"{covering}, then merge this content into it by editing it — "
            "not as a new issue or a parallel edit."]
        if exclude_issue is not None:
            paragraphs.append(
                f"#{exclude_issue}, the issue you were editing, keeps its "
                f"current body; if {covering} now carries its ground, mark "
                f"it Superseded-by: {covering} and close it with a reason.")
        paragraphs.append(RECONSIDER_LINE)
        raise Refused("\n\n".join(paragraphs), 65)
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


def blob_at(revision: str, relative: str, repository_root: Path, runner):
    """The file's content at a revision, or None where it is not there."""
    completed = runner(["git", "show", f"{revision}:{relative}"],
                       cwd=str(repository_root), check=False)
    return completed.stdout if completed.returncode == 0 else None


def existing_pull_request_for_branch(repo: str, branch: str, runner):
    """The open pull request whose head is this branch, or None. Asked of
    GitHub rather than inferred from the branch being on the remote, which
    is true of a push whose `gh pr create` then failed."""
    listed = runner(["gh", "pr", "list", "--repo", repo, "--head", branch,
                     "--state", "open", "--json", "number,title,url"],
                    check=False)
    if listed.returncode != 0:
        return None
    entries = json.loads(listed.stdout or "[]") or []
    return entries[0] if entries else None


def create_pull_request_for_branch(repo: str, branch: str, number: int,
                                   title: str, cwd: Path, runner, report):
    """Open the pull request that carries this issue's file to main. Called
    from the worktree on the ordinary path, and from the filing checkout when
    a rerun finds the branch pushed with no pull request on it."""
    body = (f"The GHI-MD for issue #{number}, filed by "
            "`scripts/ghi-issue-write.py`.\n\nUnder link-only that "
            "issue's body is the links to its files, so this file has to "
            "be on main before the body can point at it. Prose under "
            "`docs/`, silent to reviewers by CLAUDE.md's review-scope "
            "rule.\n")
    created = runner(
        ["gh", "pr", "create", "--repo", repo, "--base", "main",
         "--head", branch, "--title", f"GHI-MD for issue {number}: {title}",
         "--body", body], cwd=str(cwd))
    report((created.stdout or "").strip())


def land_file(repo: str, number: int, title: str, source: Path,
              repository_root: Path, runner, report) -> str:
    """Step 4, in a throwaway worktree cut from a just-fetched origin/main,
    so the commit is never made against stale or dirty disk.

    Safe to run twice through main's copy of the destination, compared with
    what this run would land before any branch is looked at: see the module
    docstring, WHAT A RERUN TESTS."""
    branch = f"ghi-{number}-{slug(title)}"
    destination = f"{PAIRED_DIRECTORY}/{number}-{slug(title)}.md"
    staged = with_issue_frontmatter(source.read_text(encoding="utf-8"), repo,
                                    number, title)

    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    if blob_at("origin/main", destination, repository_root, runner) == staged:
        report(f"step 4 already done: main's copy of {destination} is this "
               "file")
        return destination

    on_remote = runner(
        ["git", "ls-remote", "--heads", "origin", branch],
        cwd=str(repository_root))
    if (on_remote.stdout or "").strip():
        waiting = existing_pull_request_for_branch(repo, branch, runner)
        if waiting:
            report(f"step 4 already done: pull request "
                   f"[{waiting.get('title')}]({waiting.get('url')}) is "
                   "waiting for merge-lane")
        else:
            report(f"branch {branch} is on the remote with no pull request "
                   "open on it, so an earlier run stopped between its push "
                   "and its pull request")
            create_pull_request_for_branch(repo, branch, number, title,
                                           repository_root, runner, report)
        return destination

    worktree_parent = Path(tempfile.mkdtemp(prefix="ghi-issue-write-"))
    worktree = worktree_parent / "worktree"
    try:
        # --detach, and the push names the branch as a refspec, so this run
        # creates nothing in the filing checkout: a branch made with -b
        # outlives `git worktree remove --force` and the next run's add
        # fails on the name.
        runner(["git", "worktree", "add", "--quiet", "--detach",
                str(worktree), "origin/main"], cwd=str(repository_root))
        target = worktree / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(staged, encoding="utf-8")
        runner(["git", "add", destination], cwd=str(worktree))
        # A move, not a copy. When the source is already tracked on main —
        # a queue file, typically — leaving it behind would put the same
        # document at two paths the moment this merges, which is the
        # duplication link-only exists to prevent.
        tracked = source_path_on_main(source, repository_root, runner)
        if tracked and tracked != destination:
            runner(["git", "rm", "--quiet", tracked], cwd=str(worktree))
            report(f"removing {tracked}: its content moves to {destination}")
        message = (f"GHI-MD for issue {number}: {title}\n\n"
                   f"Filed by scripts/ghi-issue-write.py from {source.name}. "
                   "The issue's body becomes the links to this file and its "
                   "siblings once this lands. The file's `issue:` "
                   "frontmatter line is written by the tool, not by its "
                   "author, who had no issue number when they wrote it.\n")
        runner(["git", "commit", "--quiet", "-m", message], cwd=str(worktree))
        runner(["git", "push", "--quiet", "origin",
                f"HEAD:refs/heads/{branch}"], cwd=str(worktree))
        create_pull_request_for_branch(repo, branch, number, title, worktree,
                                       runner, report)
    finally:
        runner(["git", "worktree", "remove", "--force", str(worktree)],
               cwd=str(repository_root), check=False)
        shutil.rmtree(worktree_parent, ignore_errors=True)
    return destination


def source_path_on_main(source: Path, repository_root: Path, runner):
    """The source's path inside the repository, if origin/main tracks it.
    Returns None for a file that is new, or outside the checkout."""
    try:
        relative = source.resolve().relative_to(repository_root.resolve())
    except ValueError:
        return None
    listed = runner(["git", "ls-tree", "-r", "--name-only", "origin/main",
                     str(relative)], cwd=str(repository_root), check=False)
    return str(relative) if (listed.stdout or "").strip() else None


def paired_paths(number: int, repository_root: Path, runner):
    """Every file paired with this issue that is on main, wherever § Where
    the tool may write allows one to sit: under docs/issues/ before a
    system's code starts and under the system's own directory after, which
    is the move the design names as a reason the body is rewritten. The body
    is built from this, so a file still sitting on an unmerged branch is not
    linked — a link that does not resolve is worse than a body that is not
    finished."""
    listed = runner(
        ["git", "ls-tree", "-r", "--name-only", "origin/main",
         f"{PAIRED_DIRECTORY}/", f"{SYSTEM_DIRECTORY}/"],
        cwd=str(repository_root), check=False)
    prefix = f"{number}-"
    return [line for line in (listed.stdout or "").splitlines()
            if Path(line).name.startswith(prefix)]


def link_body(repo: str, number: int, repository_root: Path, runner, report,
              rerun_on: str):
    """Step 5. Nothing happens until the file is on main: until then the body
    keeps its placeholder, which tells the next reader to rerun.

    `rerun_on` is the path the rerun must be given, which is not always the
    path this run was given: filing moves a source that was already tracked
    on main, so after the merge that source is gone and its landed copy is
    the file that exists."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root),
           check=False)
    paths = paired_paths(number, repository_root, runner)
    if not paths:
        report(f"step 5 not done: no file for issue {number} is on main yet, "
               "so its body keeps the placeholder.")
        report("Once the pull request from step 4 merges, pull main and "
               f"rerun: scripts/ghi-issue-write.py create {rerun_on}")
        return False
    runner(["gh", "issue", "edit", str(number), "--repo", repo,
            "--body", links_body(repo, paths)])
    report(f"body is now {len(paths)} link(s): " + ", ".join(paths))
    return True


def create(path: Path, repo: str, repository_root: Path, runner, report):
    """The whole sequence, and the one function the tests drive."""
    paired = paired_issue_number(path)
    if (paired is not None and path.is_file()
            and issue_body_carries_pairing_key(repo, paired, runner)):
        # The file this run was given is named for an issue whose body is
        # still the placeholder a create wrote, so that filing stopped
        # before step 5. Step 4 is what puts a file at a paired name, so
        # step 5 is what is left, and this run touches nothing else.
        report(f"resuming issue {paired} on its landed file: the issue's "
               "body still carries a pairing key, so an earlier run stopped "
               "before step 5")
        return paired, link_body(repo, paired, repository_root, runner,
                                 report, str(path))

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

    destination = land_file(repo, number, title, path, repository_root,
                            runner, report)
    finished = link_body(repo, number, repository_root, runner, report,
                         destination)
    return number, finished


# --- The edit verb ------------------------------------------------------


def relative_to_root(path: Path, repository_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repository_root.resolve()))
    except ValueError:
        raise Refused(
            f"{path} is outside the checkout at {repository_root}, so it is "
            "not a file this tool can land.", 64)


def writable_relative_path(relative: str) -> bool:
    """§ Where the tool may write: `docs/issues/` before a system's code
    starts, the system's own directory after, nowhere else."""
    parts = Path(relative).parts
    if parts[:2] == tuple(Path(PAIRED_DIRECTORY).parts):
        return True
    return len(parts) >= 3 and parts[0] == SYSTEM_DIRECTORY


def normalized(text) -> str:
    """The comparable form of an issue body — LF, no trailing newlines — the
    same normalization `scripts/ghi-issue-body-edit.py` compares with, and
    for its reason: `gh` returns a body with a newline that is not part of
    it, so an un-normalized comparison finds a difference in every body and
    rewrites bodies that already say the right thing."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def is_derived_body(body: str) -> bool:
    """True for a body this tool wrote — its link list, or the placeholder
    `create` leaves between its steps — and False for prose somebody
    composed. See the module docstring: the false case is refused rather
    than overwritten."""
    text = normalized(body)
    if not text:
        return True
    if PAIRING_KEY_PREFIX in text:
        return True
    return all(re.match(r"^- \[[^\]]+\]\(https?://\S+\)$", line.strip())
               for line in text.splitlines() if line.strip())


def validate_edit(path: Path, repository_root: Path):
    """Step 1 of `edit`, which is `create`'s check inverted: this verb wants
    a file that is already paired, and refuses one that is not rather than
    filing it."""
    if not path.is_file():
        raise Refused(f"no such file: {path}", 64)
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise Refused(f"{path} is empty", 64)
    numbered = re.match(r"^(\d+)-", path.name)
    if not numbered:
        raise Refused(
            f"{path} is not named for an issue, so nothing pairs it with "
            "one. A paired file carries its issue's number wherever it "
            "sits. To file a new issue from this file, use the create "
            "verb.", 64)
    relative = relative_to_root(path, repository_root)
    if not writable_relative_path(relative):
        raise Refused(
            f"{relative} is not a path this tool writes. A paired file "
            f"lives under {PAIRED_DIRECTORY}/ before its system's code "
            f"starts and under {SYSTEM_DIRECTORY}/<system>/ after "
            "(docs/issues/46-ghi-info-agent-design.md § Where the tool may "
            "write).", 64)
    title = first_heading(text)
    if not title:
        raise Refused(
            f"{path} has no heading, so there is no title to derive from "
            "it. The issue's title is the file's first heading, after any "
            "frontmatter (user-ruled 2026-09-16).", 64)
    return text, title, int(numbered.group(1)), relative


def refuse_on_conflict(relative: str, on_main, repository_root: Path,
                       runner, report):
    """The 2026-09-08 conflict ruling applied to the file rather than the
    body (module docstring, THE CONFLICT THIS REFUSES ON). The base record
    is taken from git instead of asked for as a flag: the version the
    author's checkout started from is what they read.

    Main's copy is passed in rather than read again, so every comparison a
    run makes is against one reading of main."""
    located = runner(["git", "merge-base", "HEAD", "origin/main"],
                     cwd=str(repository_root), check=False)
    revision = (located.stdout or "").strip()
    if not revision:
        # Fails open and says so, as adjudication does: a checkout git
        # cannot find a merge base in is a broken checkout, not a caller
        # who did something wrong, and a refusal would read as the latter.
        report("conflict check skipped: this checkout has no merge base "
               "with origin/main")
        return
    started_from = blob_at(revision, relative, repository_root, runner)
    if started_from == on_main:
        return
    difference = runner(
        ["git", "diff", revision, "origin/main", "--", relative],
        cwd=str(repository_root), check=False)
    raise Refused(
        f"Refused: {relative} changed on main since your checkout started "
        "from it, and landing your copy would discard that change.\n\n"
        "Bring your checkout up to date with main: fetch, then merge or "
        "rebase onto origin/main.\n"
        "Fold your edit into main's copy of the file.\n"
        "Run this command again.\n\n"
        "The change you would have discarded:\n"
        f"{(difference.stdout or '').strip()}", 66)


def land_edit(repo: str, number: int, title: str, relative: str, staged: str,
              on_main, repository_root: Path, runner, report) -> bool:
    """Step 3. Returns True when a pull request is waiting on this edit.

    Main's copy is compared to the author's before the conflict check is
    made, which is what makes the rerun after a merge work: see the module
    docstring, THE ORDER MATTERS FOR RESUMING."""
    if on_main == staged:
        report(f"step 3 already done: main's copy of {relative} is this file")
        return False
    refuse_on_conflict(relative, on_main, repository_root, runner, report)

    branch = f"ghi-{number}-edit-{pairing_key(staged)}"
    on_remote = runner(["git", "ls-remote", "--heads", "origin", branch],
                       cwd=str(repository_root))
    if (on_remote.stdout or "").strip():
        report(f"step 3 already done: branch {branch} is on the remote and "
               "its pull request is waiting for merge-lane")
        return True

    worktree_parent = Path(tempfile.mkdtemp(prefix="ghi-issue-write-"))
    worktree = worktree_parent / "worktree"
    try:
        runner(["git", "worktree", "add", "--quiet", "-b", branch,
                str(worktree), "origin/main"], cwd=str(repository_root))
        target = worktree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(staged, encoding="utf-8")
        runner(["git", "add", relative], cwd=str(worktree))
        message = (f"GHI-MD edit for issue {number}: {title}\n\n"
                   f"Edited by scripts/ghi-issue-write.py from {relative}. "
                   "The issue's title and body are derived from main's copy "
                   "of this file, so they follow when this lands. The "
                   "file's `issue:` frontmatter line is written by the "
                   "tool, not by its author.\n")
        runner(["git", "commit", "--quiet", "-m", message], cwd=str(worktree))
        runner(["git", "push", "--quiet", "-u", "origin", branch],
               cwd=str(worktree))
        body = (f"An edit to the GHI-MD for issue #{number}, landed by "
                "`scripts/ghi-issue-write.py`.\n\nUnder link-only the "
                "issue's title and body are derived from main's copy of its "
                "files, so this has to land before either follows. Prose "
                "under `docs/`, silent to reviewers by CLAUDE.md's "
                "review-scope rule.\n")
        created = runner(
            ["gh", "pr", "create", "--repo", repo, "--base", "main",
             "--head", branch, "--title",
             f"GHI-MD edit for issue {number}: {title}", "--body", body],
            cwd=str(worktree))
        report((created.stdout or "").strip())
    finally:
        runner(["git", "worktree", "remove", "--force", str(worktree)],
               cwd=str(repository_root), check=False)
        shutil.rmtree(worktree_parent, ignore_errors=True)
    return True


def read_issue(repo: str, number: int, runner):
    """The issue's title and body as GitHub holds them, read once and used
    by both of the steps that may change them."""
    current = runner(["gh", "issue", "view", str(number), "--repo", repo,
                      "--json", "title,body"])
    return json.loads(current.stdout or "{}")


def sync_title_on_heading_change(repo: str, number: int, on_main, title: str,
                                 paths, issue, runner, report):
    """Step 4. The design's trigger is a CHANGE — "when the edit changes the
    file's first heading" — not a mismatch between the issue's title and the
    file's heading, and the difference is not academic. Measured 2026-09-20
    over the paired corpus on main: 35 files have a heading that differs
    from their issue's title, so a tool that made the title match a heading
    would rename most issues the first time anybody edited one.

    An issue with more than one paired file is left alone even when the
    heading did change: issue 3 has six files with six headings, and nothing
    in the pairing says which of them names the issue. The design's sentence
    was written for the common shape it also states — most issues carry one
    file."""
    if on_main is None or first_heading(on_main) == title:
        return
    if len(paths) > 1:
        report(f"the heading changed, but issue {number} has {len(paths)} "
               "paired files and nothing says which one names it, so the "
               "title is left alone")
        return
    if issue.get("title") == title:
        return
    runner(["gh", "issue", "edit", str(number), "--repo", repo,
            "--title", title])
    report(f"title is now: {title}")


def relink_body_from_main(repo: str, number: int, relative: str, on_main,
                          paths, issue, runner, report) -> bool:
    """Step 5, which is create's step 5 for a file that already exists: the
    body is one link per paired file on main, and is rewritten only when it
    does not already say that."""
    if on_main is None:
        report(f"step 5 not done: {relative} is not on main. Rerun this "
               "command once its pull request merges and the body follows.")
        return False
    body = links_body(repo, paths)
    if normalized(issue.get("body")) == normalized(body):
        report(f"body already lists {len(paths)} link(s), so it is left "
               "alone")
        return True
    if not is_derived_body(issue.get("body") or ""):
        # The design: until an issue is migrated it keeps its prose body and
        # is read as it stands.
        report(f"body is prose rather than links, so issue {number} has not "
               "been migrated yet; left as it stands")
        return True
    runner(["gh", "issue", "edit", str(number), "--repo", repo,
            "--body", body])
    report(f"body is now {len(paths)} link(s): " + ", ".join(paths))
    return True


def edit(path: Path, repo: str, repository_root: Path, runner, report):
    """The whole edit sequence, and the one function the tests drive."""
    text, title, number, relative = validate_edit(path, repository_root)
    staged = with_issue_frontmatter(text, repo, number, title)

    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    on_main = blob_at("origin/main", relative, repository_root, runner)
    if on_main != staged:
        # Nothing new to land is nothing new to adjudicate, so a rerun that
        # only finishes steps 4 and 5 costs no model call — the same reason
        # create skips the question when it resumes onto its own issue.
        adjudicate(repo, title, text, repository_root, runner, report,
                   exclude_issue=number)
    pending = land_edit(repo, number, title, relative, staged, on_main,
                        repository_root, runner, report)

    paths = paired_paths(number, repository_root, runner)
    issue = read_issue(repo, number, runner)
    sync_title_on_heading_change(repo, number, on_main, title, paths, issue,
                                 runner, report)
    finished = relink_body_from_main(repo, number, relative, on_main, paths,
                                     issue, runner, report)
    if pending:
        report("the body follows main's copy of the files, so it changes "
               "when that pull request merges; rerun this command then")
        return number, False
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
                    "issue's body the links to that issue's files; or land "
                    "an edit to one of those files, after which the issue "
                    "follows it.")
    sub = parser.add_subparsers(dest="verb", required=True)
    creator = sub.add_parser("create", help="file a new issue from a GHI-MD")
    creator.add_argument("path")
    creator.add_argument("--repo", default=DEFAULT_REPO)
    creator.add_argument(
        "--dry-run", action="store_true",
        help="validate the file and print what would be filed, touching "
             "neither GitHub nor git")
    editor = sub.add_parser(
        "edit", help="land an edit to a paired GHI-MD, after which the "
                     "issue's title and body follow it")
    editor.add_argument("path")
    editor.add_argument("--repo", default=DEFAULT_REPO)
    editor.add_argument(
        "--dry-run", action="store_true",
        help="validate the file and print which issue it would edit, "
             "touching neither GitHub nor git")
    arguments = parser.parse_args(argv)

    path = Path(arguments.path).resolve()

    def report(line):
        if line:
            print(line)

    try:
        if arguments.verb == "create" and arguments.dry_run:
            # The one path that needs no checkout: a file outside one can
            # still be validated, and create's own root lookup comes later.
            text, title = validate(path)
            report(f"would file: {title}")
            report(f"pairing key: {pairing_key(text)}")
            report(f"would land at: {PAIRED_DIRECTORY}/<number>-"
                   f"{slug(title)}.md")
            return 0
        if not path.is_file():
            # Asked before the checkout is looked for, because step 4 moves
            # a source that was already tracked on main and takes its
            # directory with it when it held nothing else: git run from a
            # directory that is gone raises instead of answering, and the
            # caller gets a traceback where a refusal is the honest reply.
            raise Refused(f"no such file: {path}", 64)
        root = repository_root_of(path.parent)
        if arguments.verb == "create":
            create(path, arguments.repo, root, run, report)
            return 0
        if arguments.dry_run:
            text, title, number, relative = validate_edit(path, root)
            report(f"would edit issue {number} from {relative}")
            report(f"the file's heading is: {title}")
            report("the issue's title changes only if this edit changed "
                   "that heading and the issue has one paired file")
            return 0
        edit(path, arguments.repo, root, run, report)
        return 0
    except Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return refusal.code
    except subprocess.TimeoutExpired as expiry:
        print(f"timed out: {expiry}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
