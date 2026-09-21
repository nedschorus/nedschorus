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

Both of those hold of the edit verb's step 3 as much as of create's step 4:
it asks GitHub about its branch, and its worktree leaves no branch behind.
It did neither until the review of PR [Build the GHI write tool's edit
verb](https://github.com/nedschorus/nedschorus/pull/596), where the cost was
measured — an edit's branch name is derived from the file's content, so one
branch left behind wedged every later run on that content, not one run.

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
                which the cold-start prompt's item 2 asks for. Asked only
                where step 3 has new content to land, which a rerun
                finishing an earlier run's last steps has not.
  3. Land       the author's file, when it differs from main's copy, on a
                pull request, the way create's step 4 lands a new one —
                including the move: a file the author took out of
                docs/issues/ and into its system's directory is removed
                from where main still holds it, in the same commit, or the
                merge leaves the document at two paths and step 5 links it
                twice. That removal is a deletion of main's copy, so it is
                refused on the same conflict the landing is, and it is made
                only where main holds the file under the same name.
  4. Title      when the edit CHANGED the file's first heading, and the
                issue has one paired file.
  5. Link       the body to the paired files on main, as create's step 5
                writes it in the first place.

THE ISSUE IS READ BEFORE ANYTHING IS LANDED, not after. The number comes
from the file's name, so a name carrying a number no issue has is the
caller's input being wrong — the 64 below — and the run that learned it at
step 5 had already pushed a branch and opened a pull request naming an
issue that does not exist. One read serves that test and both of the steps
that may change the issue (reviewed 2026-09-21 on PR [Build the GHI write
tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596)).

WHICH RUNS ARE ADJUDICATED is settled before step 2 is reached, by the same
branch test the pull-request resume uses. Nothing new to land is nothing to
adjudicate, and TWO states mean that: main's copy is already this file, and
this edit's content is already pushed on its branch. Testing only the first
refused the one run that could finish an interrupted one — the question is
the same draft with the same exclusion, so the too-similar verdict that
stopped the first run stopped every rerun, and the pushed branch stayed
stranded with no pull request on it. Measured 2026-09-21, reviewing the
same pull request; see `edit_landing_state`.

THE TITLE FOLLOWS A CHANGE, NOT A MISMATCH. The design's trigger is "when
the edit changes the file's first heading", and reading that as "make the
title match the heading" would be a different tool. Measured 2026-09-21 over
the paired corpus on main — the 26 files `paired_paths` returns, for the 21
issues that have one: 25 of them have a heading that differs from their
issue's title, so the matching rule renames most issues the first time
anybody edits one. An issue with several paired files is left alone even
when the heading did change — issue 3 has four files with four headings, and
nothing in the pairing says which one names it — and the tool says so
rather than guessing.

The change is measured against the document as main holds it before the
edit, which on a moved file is main's copy at the path it moved from.
Measured against the author's path instead, a moved file's heading never
looks changed — main has nothing there to compare with on the first run,
and by the rerun after the merge main's copy is the changed file itself —
so a moved file's title would follow a heading change never.

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

A MOVE PUTS TWO PATHS UNDER THAT CHECK. The author's path is where the file
lands; the moved-from path is where main's copy is deleted. Main holds
nothing at the author's path on a move, so that comparison passes on two
Nones and says nothing at all about the deletion. Checking only it turned
the duplicate that a missing removal used to leave into a discard of
another seat's work: measured against a real repository on 2026-09-21,
reviewing PR [Build the GHI write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596),
a run whose author moved a file while another seat changed it at the old
path exited 0, opened a pull request, and left the other seat's line
nowhere in the branch it pushed. Both paths are compared now, and either
one's conflict refuses the run before anything is pushed.

A MOVE THAT ALSO RENAMED IS REPORTED, NOT GUESSED AT. The moved-from path
is found by the file's name, which a move keeps and a rename does not.
There is no second rule to fall back on: a file the author renamed and a
new second document for the same issue are the same state on main — no
copy at this path, other files of the issue present — and this verb is how
both arrive. A tool that deleted on suspicion would delete a file nobody
moved, which is the discard the check above exists to stop. So the run says
what main still holds and lands the file; the author lands the removal.

THE ORDER MATTERS FOR RESUMING. Main's copy is compared to the author's
BEFORE the conflict check runs, because once the pull request merges the
author's own landed change is a difference between the merge base and main,
and a conflict check made first would refuse an author their own edit on the
rerun that finishes step 4. The branch test comes before it too, and for the
same reason: a branch under this name is one this tool pushed, after that
check had passed, and a refusal on the rerun cannot un-push it — it can only
leave it stranded with no pull request. What each guard protects is the
push, so the run that pushes nothing passes both.

A PROSE BODY IS LEFT ALONE, NOT RELINKED AND NOT REFUSED. The design says
that until an issue is migrated it keeps its prose body and is read as it
stands, and measurement says that is every issue this verb can reach:
2026-09-21, all 21 issues with a paired file on main still carry the prose
body they were filed with, migrating them being its own build-slice. So step
5 writes only over a body this tool wrote — its link list, or create's
placeholder — reports what it found otherwise, and finishes. Refusing
instead would shut the verb out of the whole existing corpus, and refusing
AFTER the file had landed would refuse an author work that had already
happened.

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
      create wants it unpaired or unpaired when edit wants it paired, a
      path this tool does not write, or a name carrying a number no issue
      has
  65  refused by adjudication as too similar to an open issue
  66  refused: the file, or the path a move takes it from, changed on main
      since the caller's checkout started from it, so landing would discard
      that change (edit)

The 66 refusals are the deny paths here that do not end with the
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
# What gh's stderr carries when the number names no issue, lowercased for
# the comparison. Measured 2026-09-21; see `read_issue`.
GH_NO_SUCH_ISSUE_STDERR_FRAGMENT = "could not resolve to an issue"
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
    """Every file paired with this issue that is on main: the files named
    `<number>-*` DIRECTLY in docs/issues/, and the files named `<number>-*`
    DIRECTLY in a system's own directory under nc-systems/. Those are the
    two places § Where the tool may write allows a paired file to sit —
    before a system's code starts and after — and the move between them is
    the reason the design gives for rewriting the body. The body is built
    from this, so a file still sitting on an unmerged branch is not linked:
    a link that does not resolve is worse than a body that is not finished.

    DIRECTLY IN, NOT ANYWHERE BENEATH, and that is the user's ruling rather
    than this function's choice. The walk
    ghi-info-design-write-path-becomes-link-only, 2026-09-19 (minutes at
    nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-info-design-write-path-becomes-link-only-minutes.md),
    ruled that step 5 "writes a computed list: one link per file matching
    `docs/issues/<number>-*`, globbed at every write, never curated". That
    glob is a literal prefix and does not descend, and the ruling's own
    worked example counts on it: it gives issue 3 four files. Re-confirmed
    by the user 2026-09-21.

    Measured 2026-09-21 against origin/main, which is what a rule matching
    the name at any depth would have linked instead: issue 3 six files
    rather than four, the two extra being queue notes under
    docs/issues/queue/; issue 18 two rather than one; issue 45 three rather
    than one; and issue 43, which has no paired file at all, one — an
    archived draft under docs/issues/archived/. Neither the queue nor the
    archive is part of an issue's file set. `create`'s step 5 calls this
    function too, so a wider rule would have rewritten those issues' bodies
    on the next create run, not only on an edit."""
    listed = runner(
        ["git", "ls-tree", "-r", "--name-only", "origin/main",
         f"{PAIRED_DIRECTORY}/", f"{SYSTEM_DIRECTORY}/"],
        cwd=str(repository_root), check=False)
    prefix = f"{number}-"
    paired_directory_parts = tuple(Path(PAIRED_DIRECTORY).parts)
    selected = []
    for line in (listed.stdout or "").splitlines():
        parts = Path(line).parts
        if not parts or not parts[-1].startswith(prefix):
            continue
        # The depth is read off the path rather than left to git: `-r` is
        # what reaches a system's own directory at all, and it also keeps
        # a DIRECTORY named `<number>-something` out of the answer, git
        # listing only blobs when it recurses.
        directly_in_the_paired_directory = (
            parts[:-1] == paired_directory_parts)
        directly_in_a_system_directory = (
            len(parts) == 3 and parts[0] == SYSTEM_DIRECTORY)
        if directly_in_the_paired_directory or directly_in_a_system_directory:
            selected.append(line)
    return selected


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


def conflict_refusal(opening: str, fold: str, relative: str, revision: str,
                     repository_root: Path, runner) -> Refused:
    """The 66 refusal, with the change it would have discarded shown under
    it. Both conflicts are built here so their instruction lines cannot
    drift apart: the opening names which path conflicted and what this run
    would have done to it, and the three lines under it are what clears
    either one.

    No reconsider line, on either: see the module docstring's last
    paragraph."""
    difference = runner(
        ["git", "diff", revision, "origin/main", "--", relative],
        cwd=str(repository_root), check=False)
    return Refused(
        f"{opening}\n\n"
        "Bring your checkout up to date with main: fetch, then merge or "
        "rebase onto origin/main.\n"
        f"{fold}\n"
        "Run this command again.\n\n"
        "The change you would have discarded:\n"
        f"{(difference.stdout or '').strip()}", 66)


def refuse_on_conflict(relative: str, on_main, moved_from, moved_from_on_main,
                       repository_root: Path, runner, report):
    """The 2026-09-08 conflict ruling applied to the file rather than the
    body (module docstring, THE CONFLICT THIS REFUSES ON). The base record
    is taken from git instead of asked for as a flag: the version the
    author's checkout started from is what they read.

    Main's copies are passed in rather than read again, so every comparison
    a run makes is against one reading of main.

    TWO PATHS CAN CONFLICT ON A MOVE, NOT ONE. A move lands the file at the
    author's path and removes main's copy at the path it moved from, so the
    other seat's change can be sitting at either. Main holds nothing at the
    author's path on a move, which makes the first comparison pass on two
    Nones, and the removal is then the whole of what the run does to that
    other seat's work: it deletes it, exit 0, saying only that it moved the
    content. Reproduced against a real repository on 2026-09-21, reviewing
    PR [Build the GHI write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596):
    the branch that run pushed did not hold the other seat's line at all. So
    the check covers the path the `git rm` names, or it does not cover the
    move."""
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
    if blob_at(revision, relative, repository_root, runner) != on_main:
        raise conflict_refusal(
            f"Refused: {relative} changed on main since your checkout "
            "started from it, and landing your copy would discard that "
            "change.",
            "Fold your edit into main's copy of the file.",
            relative, revision, repository_root, runner)
    if moved_from is None:
        return
    if blob_at(revision, moved_from, repository_root,
               runner) != moved_from_on_main:
        raise conflict_refusal(
            f"Refused: landing your move removes {moved_from} from main, "
            "and main's copy there changed since your checkout started "
            "from it, so removing it would discard that change.",
            "Fold that change into the file you moved.",
            moved_from, revision, repository_root, runner)


def create_pull_request_for_edit_branch(repo: str, branch: str, number: int,
                                        title: str, cwd: Path, runner,
                                        report):
    """Open the pull request that carries this edit to main. Called from the
    worktree on the ordinary path, and from the author's checkout when a
    rerun finds the branch pushed with no pull request on it.

    Its own wording rather than `create_pull_request_for_branch`'s: that one
    says a file is reaching main for the first time, and this one says an
    edit is following a file already there."""
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
        cwd=str(cwd))
    report((created.stdout or "").strip())


def moved_from_path_on_main(number: int, relative: str,
                            repository_root: Path, runner):
    """The path main still holds this file at, when the author moved it out
    of docs/issues/ and into its system's directory — the move § Where the
    tool may write allows. None when main holds no other copy.

    `source_path_on_main`, which answers this for `create`, cannot answer it
    here. There the source and the destination are different paths, so the
    source's own path is the answer; here they are one path, and the
    question is which OTHER path main pairs with this issue. A paired file
    carries its issue's number in its name wherever it sits, and the move
    changes the directory and not the name, so the name is the match."""
    name = Path(relative).name
    return next((path
                 for path in paired_paths(number, repository_root, runner)
                 if path != relative and Path(path).name == name), None)


def report_no_moved_from_match(number: int, relative: str, paths, report):
    """Said when main holds files for this issue but none at the author's
    path and none by that name. A move that also RENAMED looks exactly like
    this: `moved_from_path_on_main` matches on the file's name, so a rename
    — or a rename with no move at all, inside docs/issues/ — misses that
    match, nothing is staged for removal, and the document lands at two
    paths that step 5 then links twice.

    REPORTED RATHER THAN GUARDED, and the choice is forced rather than
    cautious. This verb is also how a genuinely new SECOND document reaches
    an issue that already has one, and from main's tree the two states are
    the same: no copy at this path, other files of the issue present. A
    refusal would block the legitimate one. Nothing on main says which of an
    issue's files a new path was renamed from, so a tool that picked one to
    delete would be guessing, which is what the conflict check exists to
    stop. Being wrong the reported way costs a document at two paths —
    visible in the body, fixable by a commit. Being wrong the guessing way
    costs another seat's file.

    The title is left alone for the same reason: with no predecessor named,
    nothing says the heading changed."""
    report(f"main holds no copy of {relative}, and no file of issue "
           f"{number} on main carries that name, so nothing is removed and "
           "this lands as a file main does not have.")
    report(f"issue {number}'s files on main: " + ", ".join(paths) +
           ". If you renamed this file as well as moving it, main keeps the "
           "old copy and the body will link the document twice; land the "
           "removal of the old path yourself.")


# The three states step 3 can be in. Resolved before step 2 runs, because
# which of them a run is in is what says whether step 2 runs at all. Named
# for the state rather than for what the run then does in it: the state is
# what the next reader has to recognise.
EDIT_LANDING_ALREADY_ON_MAIN = "already-on-main"
EDIT_LANDING_ALREADY_PUSHED = "already-pushed"
EDIT_LANDING_NEW_CONTENT = "new-content"


def edit_landing_branch_name(number: int, staged: str) -> str:
    """The branch this edit lands on. Named for the content and not for the
    issue alone, so a rerun of the same edit names the same branch — which
    is what lets `edit_landing_state` recognise this tool's own earlier
    push — and an edit that changed since names another."""
    return f"ghi-{number}-edit-{pairing_key(staged)}"


def edit_landing_state(number: int, staged: str, on_main,
                       repository_root: Path, runner):
    """Whether step 3 has new content to land, and the branch it would land
    on. Asked BEFORE step 2, because the answer is what says whether step 2
    is asked at all.

    NOTHING NEW TO LAND IS NOTHING TO ADJUDICATE, and TWO states mean that,
    not one. Main's copy is already this file — the rerun after the merge.
    Or this exact content is already pushed on its branch — the rerun after
    a push whose `gh pr create` then failed, which the resume in `land_edit`
    exists to finish.

    Only the first was tested until this was measured on 2026-09-21,
    reviewing PR [Build the GHI write tool's edit
    verb](https://github.com/nedschorus/nedschorus/pull/596). In the second
    state main's copy is NOT this file — the edit has not merged — so the
    run asked ghi-info a question it had already asked, and the question is
    the same draft with the same exclusion, so the answer is the same: a
    too-similar verdict raised 65 before the resume was reached, every
    rerun, and the one run that could open the missing pull request was the
    one run refused. Adjudication also consumes the reconsidered marker, so
    the marker the caller spent to pass the first run was already gone.

    The conflict check in `land_edit` sits behind this same answer, for the
    same reason: see the module docstring, THE ORDER MATTERS FOR RESUMING."""
    if on_main == staged:
        return EDIT_LANDING_ALREADY_ON_MAIN, None
    branch = edit_landing_branch_name(number, staged)
    on_remote = runner(["git", "ls-remote", "--heads", "origin", branch],
                       cwd=str(repository_root))
    if (on_remote.stdout or "").strip():
        return EDIT_LANDING_ALREADY_PUSHED, branch
    return EDIT_LANDING_NEW_CONTENT, branch


def land_edit(repo: str, number: int, title: str, relative: str, staged: str,
              on_main, moved_from, moved_from_on_main, state, branch,
              repository_root: Path, runner, report) -> bool:
    """Step 3. Returns True when a pull request is waiting on this edit.

    `state` and `branch` are `edit_landing_state`'s answer, resolved by the
    caller before step 2 rather than taken here: which state this run is in
    is what says whether step 2 is asked at all. The conflict check and the
    push below are what the one state with new content to land does, and
    the other two return above them — see the module docstring, THE ORDER
    MATTERS FOR RESUMING, for why neither guard belongs in front of a run
    that pushes nothing.

    `moved_from` is the path main still holds this document at when the
    author moved it, and `moved_from_on_main` is main's copy there. Both are
    resolved by the caller, which needs the same copy for the title: one
    reading of main serves every comparison the run makes."""
    if state == EDIT_LANDING_ALREADY_ON_MAIN:
        report(f"step 3 already done: main's copy of {relative} is this file")
        return False

    if state == EDIT_LANDING_ALREADY_PUSHED:
        # The branch says the push happened, not that the pull request did:
        # GitHub is asked, as create's step 4 asks it, or a run whose
        # `gh pr create` failed reports a pull request waiting forever.
        waiting = existing_pull_request_for_branch(repo, branch, runner)
        if waiting:
            report(f"step 3 already done: pull request "
                   f"[{waiting.get('title')}]({waiting.get('url')}) is "
                   "waiting for merge-lane")
        else:
            report(f"branch {branch} is on the remote with no pull request "
                   "open on it, so an earlier run stopped between its push "
                   "and its pull request")
            create_pull_request_for_edit_branch(repo, branch, number, title,
                                                repository_root, runner,
                                                report)
        return True

    refuse_on_conflict(relative, on_main, moved_from, moved_from_on_main,
                       repository_root, runner, report)

    worktree_parent = Path(tempfile.mkdtemp(prefix="ghi-issue-write-"))
    worktree = worktree_parent / "worktree"
    try:
        # --detach, and the push names the branch as a refspec, so this run
        # creates nothing in the author's checkout: a branch made with -b
        # outlives `git worktree remove --force`, and this branch's name is
        # derived from the file's content, so every later run on that same
        # content walks into the name again.
        runner(["git", "worktree", "add", "--quiet", "--detach",
                str(worktree), "origin/main"], cwd=str(repository_root))
        target = worktree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(staged, encoding="utf-8")
        runner(["git", "add", relative], cwd=str(worktree))
        # A move, not a copy, as create's step 4 is. The author moved this
        # file into its system's directory and main still holds it where it
        # was: leaving that behind would put the same document at two paths
        # the moment this merges, and paired_paths would then link it twice.
        # Refused above when main's copy there has moved on, because this
        # line is a deletion of it.
        if moved_from:
            runner(["git", "rm", "--quiet", moved_from], cwd=str(worktree))
            report(f"removing {moved_from}: its content moves to {relative}")
        message = (f"GHI-MD edit for issue {number}: {title}\n\n"
                   f"Edited by scripts/ghi-issue-write.py from {relative}. "
                   "The issue's title and body are derived from main's copy "
                   "of this file, so they follow when this lands. The "
                   "file's `issue:` frontmatter line is written by the "
                   "tool, not by its author.\n")
        runner(["git", "commit", "--quiet", "-m", message], cwd=str(worktree))
        runner(["git", "push", "--quiet", "origin",
                f"HEAD:refs/heads/{branch}"], cwd=str(worktree))
        create_pull_request_for_edit_branch(repo, branch, number, title,
                                            worktree, runner, report)
    finally:
        runner(["git", "worktree", "remove", "--force", str(worktree)],
               cwd=str(repository_root), check=False)
        shutil.rmtree(worktree_parent, ignore_errors=True)
    return True


def read_issue(repo: str, number: int, relative: str, runner):
    """The issue's title and body as GitHub holds them, read once and used
    by both of the steps that may change them — and, because the caller
    reads it before anything is fetched, adjudicated, pushed or opened, the
    test that the number the file's name carries names an issue at all.

    A NUMBER NO ISSUE HAS IS A 64, NOT A 1. The number comes from the file's
    NAME, so a name carrying one no issue has is the caller's input being
    wrong, which is the class the exit table calls 64 — the same class as a
    path this tool does not write. It was a 1 until 2026-09-21, this read
    having gone through `run`, which calls every failed subprocess an
    operating failure.

    gh says which of the two happened. Measured 2026-09-21 against
    nedschorus/nedschorus — `gh issue view 999999 --repo nedschorus/nedschorus
    --json title,body`, exit 1, nothing on stdout, this on stderr:

      GraphQL: Could not resolve to an issue or pull request with the number
      of 999999. (repository.issue)

    Anything else it fails on — logged out, no network, the repository
    unreadable — is an operating failure still, and stays a 1."""
    current = runner(["gh", "issue", "view", str(number), "--repo", repo,
                      "--json", "title,body"], check=False)
    if current.returncode != 0:
        said = (current.stderr or current.stdout or "").strip()
        if GH_NO_SUCH_ISSUE_STDERR_FRAGMENT in said.lower():
            raise Refused(
                f"Refused: {repo} has no issue {number}, and {relative} is "
                "named for it.\n\n"
                "Rename the file for the issue it is paired with, if it has "
                "one.\n"
                "If it has no issue yet, file one with the create verb, from "
                "a copy whose name carries no number — create refuses a file "
                "already named for an issue.\n\n"
                f"gh said: {said}", 64)
        raise Refused(f"gh issue view failed: {said}", 1)
    return json.loads(current.stdout or "{}")


def sync_title_on_heading_change(repo: str, number: int,
                                 document_before_this_edit, title: str,
                                 paths, issue, runner, report):
    """Step 4. The design's trigger is a CHANGE — "when the edit changes the
    file's first heading" — not a mismatch between the issue's title and the
    file's heading, and the difference is not academic. Measured 2026-09-21
    over the paired corpus on main, the 26 files `paired_paths` returns: 25
    of them have a heading that differs from their issue's title, so a tool
    that made the title match a heading would rename most issues the first
    time anybody edited one.

    An issue with more than one paired file is left alone even when the
    heading did change: issue 3 has four files with four headings, and
    nothing in the pairing says which of them names the issue. The design's
    sentence was written for the common shape it also states — most issues
    carry one file.

    WHAT THE CHANGE IS MEASURED AGAINST is the document as main holds it
    before this edit, which on a moved file is main's copy at the path it
    moved from. Passed in for that reason rather than read from the author's
    path here: main holds nothing at the author's path on a move, so a
    comparison against that finds no heading to have changed — not on the
    first run, and not on any rerun either, since once the move merges the
    heading on main is the changed one. A moved file's title would follow a
    heading change never."""
    if (document_before_this_edit is None
            or first_heading(document_before_this_edit) == title):
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
    # Read here, before a fetch, a model call, a push or a pull request: the
    # number is the file's NAME, so a name carrying a number no issue has is
    # the caller's input being wrong, and the run that found that out at
    # step 5 had already pushed a branch and opened a pull request for an
    # issue that does not exist. This one read serves steps 4 and 5 below.
    issue = read_issue(repo, number, relative, runner)

    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    on_main = blob_at("origin/main", relative, repository_root, runner)
    paths = paired_paths(number, repository_root, runner)
    # Where main still holds this document when the author moved it, and
    # main's copy there. Asked only when main has nothing at the author's
    # path — where it does, this is an edit in place and a same-named file
    # elsewhere is another document. Resolved here rather than inside a
    # step, because step 3 deletes that path and step 4 measures the
    # heading change against that copy: one reading of main, two users.
    moved_from = (moved_from_path_on_main(number, relative, repository_root,
                                          runner)
                  if on_main is None else None)
    moved_from_on_main = (
        blob_at("origin/main", moved_from, repository_root, runner)
        if moved_from else None)
    if on_main is None and moved_from is None and paths:
        report_no_moved_from_match(number, relative, paths, report)
    state, branch = edit_landing_state(number, staged, on_main,
                                       repository_root, runner)
    if state == EDIT_LANDING_NEW_CONTENT:
        # Nothing new to land is nothing new to adjudicate, so a rerun that
        # only finishes steps 4 and 5 costs no model call — the same reason
        # create skips the question when it resumes onto its own issue. Two
        # states mean that, and testing main's copy alone saw one of them:
        # see `edit_landing_state`.
        adjudicate(repo, title, text, repository_root, runner, report,
                   exclude_issue=number)
    pending = land_edit(repo, number, title, relative, staged, on_main,
                        moved_from, moved_from_on_main, state, branch,
                        repository_root, runner, report)

    # The document as main holds it before this edit, which is the author's
    # path where main has one and the path the file moved from where it
    # does not. Step 5 is not given this: it links what main holds AT the
    # author's path, and a moved file is not there until its merge.
    document_before_this_edit = (on_main if on_main is not None
                                 else moved_from_on_main)
    sync_title_on_heading_change(repo, number, document_before_this_edit,
                                 title, paths, issue, runner, report)
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
