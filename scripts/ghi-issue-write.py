#!/usr/bin/env python3
"""File a GitHub issue from its GHI-MD, then make the issue's body the links
to that issue's files; and land an edit to one of those files, after which
the issue follows it. The `create` and `edit` verbs of the GHI write tool.

WHAT THIS IS. The user ruled on 2026-09-15 that a GHI's body is the link to
its GHI-MD and nothing else: one copy of every fact, GitHub
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
                filed under an issue whose filing finished.
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

WHAT ELSE STOPS A SECOND ISSUE, the pairing key having limits. The key is a
hash of the source's content, so it finds a filing only while that filing's
issue still carries it and only while the source is unchanged. Two cases
fall outside it. Both were walked with the user item by item on 2026-09-21
and approved there, the in-flight refusal's wording included (walk-minutes
nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-write-create-verb-follow-ups-and-two-open-questions-minutes.md).

A FINISHED FILING LEAVES NO KEY ANYWHERE. Step 5 makes the body links, and a
source the tool did not move — any file not already tracked on main, which
is every freshly written document — is still on disk. A rerun on it finds no
pairing and would file a second issue. So before filing, every filed GHI-MD
on main is compared against what this source would become if it were filed
under that file's issue number. That is step 4's own idempotency test
generalised over the corpus, and it is computed forward: stripping the
`issue:` line back off main's copy would be a guess, because writing it may
have added a whole frontmatter block around it.

AN EDIT MID-FILING CHANGES THE KEY. An author who edits the source between
step 3 and a rerun makes a key no open issue carries, and would file a
second issue while the first one's pull request is still open. Content as
identity is the user's ruling of 2026-09-20 and is not up for revision, so
the second question is asked of the same read of the open issues: an issue
whose body still carries the pairing key prefix is a filing in flight, and
its title is the heading it was filed from. A source whose first heading
matches one of those is refused, and the refusal names the issue, names the
pull request to wait for, and sends the edit to the edit verb. Known
residual, accepted on 2026-09-21 rather than guarded: an author who changes
the heading itself mid-filing matches neither check, and that refusal's
wording is what keeps them out of it.

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
So a filed GHI-MD — one whose name carries an issue number — is accepted as
the resume entry point when that issue's body is still a placeholder, and
the run finishes at step 5. When the body is no longer a placeholder the
filing is done, and the refusal at step 1 stands: changing a filed GHI-MD is
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
already filed under an issue — a filed GHI-MD carries its issue's number in
its name wherever it sits — and does four things:

  1. Validate   the file exists, opens with a heading, is named for an
                issue, and sits where this tool may write: directly in
                docs/issues/ before its system's code starts, directly in
                the system's own directory after. The same two places
                step 5 builds the body from, and the same predicate —
                `writable_relative_path`, which `ghi_md_paths_for_issue` calls.
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
                issue has one filed GHI-MD.
  5. Link       the body to the filed GHI-MDs on main, as create's step 5
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
the filed corpus on main — the 26 files `ghi_md_paths_for_issue` returns, for
the 21
issues that have one: 25 of them have a heading that differs from their
issue's title, so the matching rule renames most issues the first time
anybody edits one. An issue with several filed GHI-MDs is left alone even
when the heading did change — issue 3 has four files with four headings, and
nothing in the pairing says which one names it — and the tool says so
rather than guessing.

The change is measured against the document as main holds it before the
edit, which on a moved file is main's copy at the path it moved from.
Measured against the author's path instead, a moved file's heading never
looks changed — main has nothing there to compare with on the first run,
and by the rerun after the merge main's copy is the changed file itself —
so a moved file's title would follow a heading change never.

WHICH IS WHY THE FILE'S `issue:` LINE CITES GITHUB'S TITLE, NOT THE
HEADING. That line cites the issue the way CLAUDE.md says to cite one, by
title and link. In `create` the heading IS the title, the issue being
filed under it. In `edit` it is not, on 25 of the 26 filed GHI-MDs on main,
and a run that cited the heading wrote each of an issue's files a
different wrong name for it. So the line carries the title this run leaves
the issue holding: the heading where step 4 sets it to that, and GitHub's
title everywhere else. It is derived after main and the issue have been
read, for that reason — see `issue_title_after_this_edit`.

THE CONFLICT THIS REFUSES ON IS THE FILE'S, NOT THE BODY'S. The user ruled
on 2026-09-08 that a GHI edit checks for conflicts and refuses rather than
merges; scripts/ghi-issue-body-edit.py is that ruling built, for the world
where an author typed the body. For a link-only-GHI the body is computed from
main's file set, so two seats computing it reach the same answer and there
is no body change to lose. The content is in the file, so the file is where
the check belongs: main's copy is compared against the copy at `git
merge-base HEAD origin/main`, the version the author's checkout started
from, which is the base record they read — taken from git rather than asked
for as a flag, since git already holds it. They differ, and another seat
changed the file since: the tool prints that diff and writes nothing. No
retry, no lock, no merge, as the ruling says.

THE AUTHOR'S OWN SECOND EDIT IS THAT CONFLICT TOO, AND THAT CHECK CANNOT
SEE IT. It compares main with the merge base, so an edit that has not
merged is invisible to it: the first run's pull request is open, main does
not hold it, nothing refuses. The landing branch is named for the content,
so the revised file gets a branch of its own, cut from a main without the
first. Merging both is CLEAN in either order — each branch changed the
line once against its own base — and what reaches main is the second
file's content with the first's correction gone, git and merge-lane each
shown no conflict at all. Reproduced 2026-09-21 reviewing PR [Build the
GHI write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596).
So the open pull request is what the second run is checked against:
`refuse_on_an_earlier_edit_still_open`.

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
2026-09-21, all 21 issues with a filed GHI-MD on main still carry the prose
body they were filed with, migrating them being its own build-slice. So step
5 writes only over a body this tool wrote — its link list, or create's
placeholder — reports what it found otherwise, and finishes. Refusing
instead would shut the verb out of the whole existing corpus, and refusing
AFTER the file had landed would refuse an author work that had already
happened.

Usage:
  ghi-issue-write.py create <path-to-ghi-md> [--repo OWNER/NAME] [--dry-run]
  ghi-issue-write.py edit <path-to-filed-ghi-md> [--repo OWNER/NAME]
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
  64  the caller's input is wrong: no such file, no heading, filed when
      create wants it unfiled or unfiled when edit wants it filed,
      already on main under an issue, a filing of the same heading already
      in flight, a path this tool does not write, a name carrying a number
      that names no issue — one no issue has, or one a pull request has, or
      a bad command line. argparse's own errors are given this code rather
      than its 2, which this list has no entry for and a caller could not
      place.
  65  refused by adjudication as too similar to an open issue
  66  refused because landing would discard work (edit): the file, or the
      path a move takes it from, changed on main since the caller's
      checkout started from it; or an earlier edit of the same file is
      still waiting on an open pull request

The 66 refusals are the deny paths here that do not end with the
reconsider line, deliberately. A conflict is not a judgment to think
again about: another seat's change is sitting on main, and the way past it
is to fold that change in, which the refusal says and shows. The marker
could not pass it in any case — adjudication consumes the marker before
this check is reached — and a line promising otherwise would be false. The
2026-09-08 ruling this implements gives a conflict no reconsider path
either. The earlier-edit refusal is the same kind: the change it would
discard is the author's own, sitting on a pull request nobody has merged,
and the way past it is to let that merge and fold it in.
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
GHI_MD_DIRECTORY = "docs/issues"
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
            f"gone, rerun it on this issue's file under {GHI_MD_DIRECTORY}/.")


ISSUE_FRONTMATTER_KEY = "issue"


def issue_frontmatter_line(repo: str, number: int, title: str) -> str:
    """The issue this file is filed under, written the way CLAUDE.md says to
    cite one: its ID-type — the key — then its name, as a link. Never a
    bare number.

    The value is emitted as a JSON string, which is also a valid
    double-quoted YAML scalar. Unquoted it is not valid YAML at all: the
    value opens with `[`, so a parser reads a flow sequence and raises at
    the `](` — on every document this tool files. json.dumps quotes and
    escapes together, which matters because the quoting alone does not: a
    title carrying a double quote or a backslash needs those escaped inside
    the quotes, and json.dumps is the escaping YAML's double-quoted style
    shares. ensure_ascii=False so a title's non-ASCII characters stay
    themselves rather than being turned into escapes.

    with_issue_frontmatter still finds a line written in the older unquoted
    shape, because it matches the key and not the value; a file carrying
    one corrects itself the next time this tool writes to it, and there is
    no migration sweep."""
    link = f"[{title}](https://github.com/{repo}/issues/{number})"
    return f"{ISSUE_FRONTMATTER_KEY}: {json.dumps(link, ensure_ascii=False)}"


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
    and GitHub cannot, and they stay exactly as their author wrote them.

    An existing line is found by its key alone, never by the shape of its
    value, so a line written before the value was quoted is still replaced
    rather than duplicated."""
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
    """The body of a link-only-GHI: one link per filed GHI-MD, in filename
    order,
    and nothing else. Derived at every write, so nobody curates it and it
    cannot fall behind the files."""
    lines = []
    for path in sorted(paths):
        name = Path(path).name
        lines.append(f"- [{name}](https://github.com/{repo}/blob/main/{path})")
    return "\n".join(lines)


# --- The steps ----------------------------------------------------------

def issue_number_in_file_name(path: Path):
    """The issue number a filed GHI-MD carries in its name, or None for a file
    that is not filed. A filed GHI-MD carries the number wherever it sits, so
    this does not look at the directory."""
    match = re.match(r"^(\d+)-", path.name)
    return int(match.group(1)) if match else None


def issue_body_carries_pairing_key(repo: str, number: int, runner) -> bool:
    """Whether this issue's body is still the placeholder a create wrote,
    which is what tells a rerun on a filed GHI-MD that the filing stopped
    partway rather than finished. Read from the API for the same reason the
    resume scan is: a rerun seconds after a failure must see the write."""
    viewed = runner(["gh", "issue", "view", str(number), "--repo", repo,
                     "--json", "body"])
    body = (json.loads(viewed.stdout or "{}") or {}).get("body") or ""
    return PAIRING_KEY_PREFIX in body


def validate(path: Path):
    """Step 1. Refuses rather than guesses: a file with no heading has no
    title to generate, and a file already at a filed path belongs to an
    issue that exists.

    THE FILED-NAME REFUSAL SAYS WHERE THE EDIT VERB WRITES, not merely
    that the edit verb exists, because the two verbs met at a dead end
    otherwise. This check sends every `<number>-*` file to `edit`, and
    `edit` writes only a file sitting DIRECTLY in docs/issues/ or directly
    in a system's own directory. Main holds ten queue notes named for
    issues under docs/issues/queue/ and an archived draft under
    docs/issues/archived/ (measured 2026-09-21): an agent handed one of
    those was told by `create` to use `edit`, and by `edit` that the path
    is not one this tool writes. Named in the review of PR [Build the GHI
    write tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596).
    The three lines each name the condition they apply under, so the agent
    reads only the one it is in."""
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
    if issue_number_in_file_name(path) is not None:
        raise Refused(
            f"{path} is already named for an issue, so that issue exists. A "
            "filed GHI-MD carries its issue's number wherever it sits, so "
            "this check does not depend on the directory.\n"
            f"Directly in {GHI_MD_DIRECTORY}/, or directly in "
            f"{SYSTEM_DIRECTORY}/<system>/: change this file with the edit "
            "verb.\n"
            "Anywhere else, a queue note or an archived draft included: the "
            "edit verb writes no such path, so run it on the issue's own "
            "file in one of those two places instead.\n"
            "To file this material as a new issue of its own: run create "
            "again on a copy whose name carries no number.", 64)
    return text, title


def open_issues_with_bodies(repo: str, runner):
    """Every open issue, with the number, body and title of each. Read from
    the API rather than the search index, which is not immediate — a rerun
    seconds after a failure must still find its issue.

    One read, two questions: which open issue carries this file's pairing
    key, and which open issues are filings still in flight. Asking twice
    would be two API calls for an answer that cannot change between them."""
    completed = runner(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--limit", "300", "--json", "number,body,title"])
    return json.loads(completed.stdout or "[]")


def find_existing_pairing(issues, key: str):
    """The resume path: the open issue whose body carries this file's
    pairing key, or None when no run has filed this content yet."""
    for issue in issues:
        if key in (issue.get("body") or ""):
            return issue
    return None


def refuse_if_filing_is_in_flight(repo: str, issues, title: str, runner):
    """Refuse when an open issue is this same document part way through
    filing. An issue whose body still carries the pairing key prefix is a
    filing in flight, and its title is the heading it was filed from, so a
    source whose first heading matches one of those is that filing's
    document — edited since, which is why the key no longer finds it.

    Reads the list the resume scan already fetched, so the check costs no
    API call. The refusal costs one: the pull request its file is on, asked
    of GitHub by the branch step 4 pushes, so the author is told what to
    wait for rather than left to find it.

    That lookup has three answers, not two. `gh pr list` exits non-zero on
    an expired token, a rate limit or an unreachable network, and the line
    beneath the refusal used to say "No pull request carrying its file is
    open yet" on all three — sending the author to wait for a pull request
    nobody looked up. The refusal fires either way; only its second line
    changes."""
    for issue in issues:
        if PAIRING_KEY_PREFIX not in (issue.get("body") or ""):
            continue
        if (issue.get("title") or "") != title:
            continue
        number = issue.get("number")
        open_pull_requests = open_pull_requests_for_branch(
            repo, f"ghi-{number}-{slug(title)}", runner)
        if open_pull_requests is None:
            where = ("Looking up the pull request carrying its file failed, "
                     "so this run cannot name it.")
        elif open_pull_requests:
            waiting = open_pull_requests[0]
            where = (f"Its file is on pull request [{waiting.get('title')}]"
                     f"({waiting.get('url')}).")
        else:
            where = "No pull request carrying its file is open yet."
        raise Refused(
            f"This file's heading is already being filed as issue [{title}]"
            f"(https://github.com/{repo}/issues/{number}), whose body is "
            "still a placeholder.\n"
            f"{where}\n"
            "Wait for the merge, then apply your edit to the landed file "
            "with the edit verb, and do not rerun create on this file.",
            64)


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


def origin_main_commit_hash(repository_root: Path, runner) -> str:
    """The one commit `origin/main` names at this moment.

    Every read of main in the check below is made at this hash rather than
    at the ref. The ref moves: this clone's worktrees share one object store
    and one set of remote-tracking refs, so another seat's fetch can move
    origin/main between a listing and the reads that follow it, and a path
    listed from one commit is then read from another. Resolved once, the
    listing and its reads are of the same tree.

    --verify, so the answer is one hash or a failure. Through the shared
    `run` with check on, so a failure to resolve is a refusal rather than an
    empty string spliced into the revisions below."""
    resolved = runner(["git", "rev-parse", "--verify", "origin/main"],
                      cwd=str(repository_root))
    return (resolved.stdout or "").strip()


def ghi_md_paths_on_main(revision: str, repository_root: Path, runner):
    """Every filed GHI-MD at this revision — the files that carry an issue
    number in their name and sit directly under `docs/issues/`.

    Two things in that directory are not filed GHI-MDs. The queue's files
    belong to no issue and carry no number, so the number is one thing that
    selects. And `-r` descends, so a numbered file in a subdirectory is
    listed too — docs/issues/queue/18-… and docs/issues/archived/43-… are
    both on main — and those are named for their issue without being filed
    under it: step 4 lands every file it files as a direct child of
    `docs/issues/`, which is the only place a filed GHI-MD is. The parent is
    what selects those out, and the cost of not selecting them was one
    `git show` each, every create.

    Raises on a failed list for the reason ghi_md_paths_for_issue does, which
    is where
    that reasoning and the real-repository measurement behind it are
    written."""
    listed = runner(["git", "ls-tree", "-r", "--name-only", revision,
                     f"{GHI_MD_DIRECTORY}/"], cwd=str(repository_root))
    return [line for line in (listed.stdout or "").splitlines()
            if str(Path(line).parent) == GHI_MD_DIRECTORY
            and issue_number_in_file_name(Path(line)) is not None]


def refuse_if_already_landed_on_main(repo: str, text: str, title: str,
                                     repository_root: Path, runner):
    """Refuse when this source is already on main under some issue's number.

    The case the pairing key cannot see: once a filing finishes, the issue's
    body is links and the key is nowhere, so a rerun on a source that is
    still on disk — every source the tool did not move, which is every
    freshly written document — finds no pairing and files a second issue.

    Each filed GHI-MD on main is compared against what this source would
    become if it were filed under that file's issue number, which is
    land_file's own idempotency test generalised over the corpus. Computed
    forward, never by stripping the `issue:` line back off main's copy:
    with_issue_frontmatter may have added a whole frontmatter block around
    that line, and taking one back off again is a guess about what the
    author wrote.

    The fetch is this check's own. land_file fetches again later because
    adjudication runs between the two and can take minutes, and the
    docstring's promise is that the worktree is cut from a just-fetched
    main.

    A read that fails raises rather than going through blob_at, whose None
    means "not there". Here it cannot mean that: the path came from a
    successful listing of this same commit, so a `git show` that exits
    non-zero at it is a git failure. Read as an absence, None differs from
    what this source would become, the loop moves on, and the run files the
    second issue this check exists to prevent."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    revision = origin_main_commit_hash(repository_root, runner)
    for landed in ghi_md_paths_on_main(revision, repository_root, runner):
        number = issue_number_in_file_name(Path(landed))
        staged = with_issue_frontmatter(text, repo, number, title)
        read = runner(["git", "show", f"{revision}:{landed}"],
                      cwd=str(repository_root))
        if read.stdout == staged:
            raise Refused(
                f"This file is already on main as {landed}, filed as issue "
                f"[{title}](https://github.com/{repo}/issues/{number}).\n"
                f"Edit {landed} with the edit verb instead of rerunning "
                "create on this file.", 64)


def open_pull_requests_for_branch(repo: str, branch: str, runner):
    """The open pull requests whose head is this branch, or None where the
    lookup itself did not happen.

    None and the empty list are two different answers and a caller that
    needs to say which has to have both. An expired token, a rate limit and
    an unreachable network all exit non-zero, and read as "none open" they
    make a run state, as a fact, something nobody looked up."""
    listed = runner(["gh", "pr", "list", "--repo", repo, "--head", branch,
                     "--state", "open", "--json", "number,title,url"],
                    check=False)
    if listed.returncode != 0:
        return None
    return json.loads(listed.stdout or "[]") or []


def existing_pull_request_for_branch(repo: str, branch: str, runner):
    """The open pull request whose head is this branch, or None. Asked of
    GitHub rather than inferred from the branch being on the remote, which
    is true of a push whose `gh pr create` then failed. A caller that must
    tell a failed lookup from none open asks open_pull_requests_for_branch
    instead."""
    entries = open_pull_requests_for_branch(repo, branch, runner)
    return entries[0] if entries else None


def create_pull_request_for_branch(repo: str, branch: str, number: int,
                                   title: str, cwd: Path, runner, report):
    """Open the pull request that carries this issue's file to main. Called
    from the worktree on the ordinary path, and from the filing checkout when
    a rerun finds the branch pushed with no pull request on it."""
    body = (f"The GHI-MD for issue #{number}, filed by "
            "`scripts/ghi-issue-write.py`.\n\nAs a link-only-GHI, that "
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
    destination = f"{GHI_MD_DIRECTORY}/{number}-{slug(title)}.md"
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
        # duplication a link-only-GHI exists to prevent.
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
    Returns None for a file that is new, or outside the checkout.

    Raises on a failed list, as paired_paths does and for the reason written
    there: `git ls-tree` exits 0 with empty output for a path that is not on
    the revision, so a non-zero exit is a real failure and never means "not
    tracked". Until 2026-09-22 this call passed `check=False` and read a
    failure as "not tracked", so step 4 copied a source it should have moved
    and the same document landed at two paths once the pull request merged
    (user-ruled a fix 2026-09-22, "y sounds like this is a fix now", item 4
    of the walk ghi-write-session-open-rulings-and-concerns). Raising here
    is safe: nothing is committed or pushed yet, the worktree is removed by
    land_file's `finally`, and a rerun finds the issue by its pairing key."""
    try:
        relative = source.resolve().relative_to(repository_root.resolve())
    except ValueError:
        return None
    listed = runner(["git", "ls-tree", "-r", "--name-only", "origin/main",
                     str(relative)], cwd=str(repository_root))
    return str(relative) if (listed.stdout or "").strip() else None


def ghi_md_paths_for_issue(number: int, repository_root: Path, runner):
    """Every file filed under this issue that is on main: the files named
    `<number>-*` DIRECTLY in docs/issues/, and the files named `<number>-*`
    DIRECTLY in a system's own directory under nc-systems/. Those are the
    two places § Where the tool may write allows a filed GHI-MD to sit —
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
    than one; and issue 43, which has no filed GHI-MD at all, one — an
    archived draft under docs/issues/archived/. Neither the queue nor the
    archive is part of an issue's file set. `create`'s step 5 calls this
    function too, so a wider rule would have rewritten those issues' bodies
    on the next create run, not only on an edit.

    Raises on a failed list rather than answering with an empty one. The two
    are indistinguishable to every caller, and the caller then states that
    no file is on main yet as a fact it cannot know. Nothing is lost by
    raising: measured against a real repository on 2026-09-21, `git ls-tree`
    asked for a directory that is not on the revision exits 0 with empty
    output, and a path that is not there does too, so a non-zero exit is a
    real failure — a bad revision or a path outside the checkout, both
    128 — and never means "nothing there"."""
    listed = runner(
        ["git", "ls-tree", "-r", "--name-only", "origin/main",
         f"{GHI_MD_DIRECTORY}/", f"{SYSTEM_DIRECTORY}/"],
        cwd=str(repository_root))
    prefix = f"{number}-"
    selected = []
    for line in (listed.stdout or "").splitlines():
        if not Path(line).name.startswith(prefix):
            continue
        # The depth is read off the path rather than left to git: `-r` is
        # what reaches a system's own directory at all, and it also keeps
        # a DIRECTORY named `<number>-something` out of the answer, git
        # listing only blobs when it recurses. `writable_relative_path` is
        # what reads it, and is the whole of the depth rule, so the set
        # this returns and the set `edit` will land into cannot disagree.
        if writable_relative_path(line):
            selected.append(line)
    return selected


def link_body(repo: str, number: int, repository_root: Path, runner, report,
              rerun_on: str):
    """Step 5. Nothing happens until the file is on main: until then the body
    keeps its placeholder, which tells the next reader to rerun.

    `rerun_on` is the path the rerun must be given, which is not always the
    path this run was given: filing moves a source that was already tracked
    on main, so after the merge that source is gone and its landed copy is
    the file that exists.

    The fetch raises rather than being ignored. A fetch that failed leaves
    the list below empty exactly as a main with nothing filed does, and the
    report then tells the author no file for this issue is on main yet —
    which, the fetch having failed, this run cannot know."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    paths = ghi_md_paths_for_issue(number, repository_root, runner)
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
    filed_number = issue_number_in_file_name(path)
    if (filed_number is not None and path.is_file()
            and issue_body_carries_pairing_key(repo, filed_number, runner)):
        # The file this run was given is named for an issue whose body is
        # still the placeholder a create wrote, so that filing stopped
        # before step 5. Step 4 is what puts a file at a filed name, so
        # step 5 is what is left, and this run touches nothing else.
        report(f"resuming issue {filed_number} on its landed file: the "
               "issue's body still carries a pairing key, so an earlier run "
               "stopped before step 5")
        return filed_number, link_body(repo, filed_number, repository_root,
                                       runner, report, str(path))

    text, title = validate(path)
    key = pairing_key(text)

    issues = open_issues_with_bodies(repo, runner)
    existing = find_existing_pairing(issues, key)
    if existing:
        number = existing["number"]
        report(f"resuming issue {number}: its body still carries this file's "
               "pairing key, so an earlier run stopped partway")
    else:
        # Nothing open carries this content's key, so this is either a new
        # document or one of the two cases the key cannot see. Both are
        # asked before adjudication, which is fail-open and can take
        # minutes: a run that must be refused should not spend them.
        refuse_if_filing_is_in_flight(repo, issues, title, runner)
        refuse_if_already_landed_on_main(repo, text, title, repository_root,
                                         runner)
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
    """§ Where the tool may write: DIRECTLY in `docs/issues/` before a
    system's code starts, DIRECTLY in that system's own directory after,
    nowhere else.

    THE SAME TWO PLACES `ghi_md_paths_for_issue` RETURNS, and now the same
    predicate:
    that function calls this one, so the files an issue's body is built
    from and the files this verb will land are one set. They were two
    rules until the review of PR [Build the GHI write tool's edit
    verb](https://github.com/nedschorus/nedschorus/pull/596), where this
    one took any depth under docs/issues/ and any depth from three down
    under nc-systems/ while that one took neither, and the disagreement was
    reproduced against a repository with a bare remote and `gh` stubbed:
    `edit` on a queue note named for an issue landed the note, wrote it an
    `issue:` line, and renamed the issue after THAT file's heading — the
    heading of a file the issue's body does not link. A file this tool
    would not link is a file it must not land.

    DIRECTLY IN is the user's ruling of 2026-09-19, re-confirmed
    2026-09-21, not this function's choice: one link per file matching
    `docs/issues/<number>-*`, globbed at every write, never curated. A
    literal prefix does not descend, which puts docs/issues/queue/ and
    docs/issues/archived/ both outside it. `ghi_md_paths_for_issue` carries the
    measurement over main's own tree."""
    parts = Path(relative).parts
    if parts[:-1] == tuple(Path(GHI_MD_DIRECTORY).parts):
        return True
    return len(parts) == 3 and parts[0] == SYSTEM_DIRECTORY


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
    a file that is already filed, and refuses one that is not rather than
    filing it.

    THE UNWRITABLE-PATH REFUSAL DOES NOT SAY "MOVE IT", because the file
    most often at such a path is a queue note, and moving a queue note into
    the issue's own directory makes it one of the issue's files: step 5
    links it, and main keeps the copy under `queue/` — `ghi_md_paths_for_issue`
    skips
    that directory, so no moved-from path matches it and nothing removes it
    — leaving one document at two paths. Main holds ten queue notes named
    for issues and an archived draft named for one. `create`'s refusal, on
    the same file, sends its holder HERE to edit the issue's own file
    instead, so a "move it" line here sent an agent in a circle back out.
    Raised non-blocking on PR [Build the GHI write tool's edit
    verb](https://github.com/nedschorus/nedschorus/pull/596) and fixed
    2026-09-22. The move line is kept for the state that does want it — the
    issue's own file sitting somewhere this tool does not write — under the
    condition that says which state it is."""
    if not path.is_file():
        raise Refused(f"no such file: {path}", 64)
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise Refused(f"{path} is empty", 64)
    numbered = re.match(r"^(\d+)-", path.name)
    if not numbered:
        raise Refused(
            f"{path} is not named for an issue, so it is not filed under "
            "one. A filed GHI-MD carries its issue's number wherever it "
            "sits. To file a new issue from this file, use the create "
            "verb.", 64)
    relative = relative_to_root(path, repository_root)
    if not writable_relative_path(relative):
        raise Refused(
            f"{relative} is not a path this tool writes. A filed GHI-MD "
            f"lives directly in {GHI_MD_DIRECTORY}/ before its system's "
            f"code starts and directly in {SYSTEM_DIRECTORY}/<system>/ "
            "after, and in neither a queue nor an archive below them "
            "(docs/issues/46-ghi-info-agent-design.md § Where the tool may "
            "write).\n"
            "A queue note or an archived draft: run this command on the "
            "issue's own file in one of those two places instead.\n"
            "The issue's own file somewhere else: move it to one of those "
            "two places and run this command again.", 64)
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


def refuse_on_an_earlier_edit_still_open(repo: str, number: int,
                                         relative: str, moved_from,
                                         branch: str,
                                         repository_root: Path, runner):
    """The same 2026-09-08 conflict ruling applied to an edit of this file
    that this tool already landed on a pull request nobody has merged.

    `refuse_on_conflict` cannot see one. It compares main with the merge
    base, and the earlier edit is not on main — that is what "still open"
    means — so it finds nothing and the run proceeds. The landing branch is
    named for the content, so the revised file gets a branch of its own,
    cut from a main without the first, and merging both is clean in either
    order: each branch changed the line once against its own base. What
    reaches main is the later file with the earlier correction wiped out of
    it, and nobody is shown a conflict — not git, not merge-lane.
    Reproduced 2026-09-21 reviewing PR [Build the GHI write tool's edit
    verb](https://github.com/nedschorus/nedschorus/pull/596): run 1 made a
    line read one way, run 2 put it back and added a line, both exited 0,
    and main after both merges held run 1's wording with run 2's addition.
    The behaviour it defends against is an author revising a GHI-MD a
    second time before merge-lane's next session.

    THE FILE, NOT THE ISSUE, decides. Every edit of every file of one issue
    shares the `ghi-<number>-edit-` branch prefix, so the prefix alone
    would refuse an author editing the second of an issue's files while the
    first waits — issue 3 has four filed GHI-MDs on main. Those are
    different documents and different lines, and merging both drops
    nothing. So the open pull request's own file list is what is compared,
    against the paths this run writes: where the file lands, and on a move
    where main's copy is removed.

    THE OPEN PULL REQUEST, NOT THE BRANCH. A branch left by a push whose
    `gh pr create` failed will never merge on its own, and `land_edit`
    exists to finish it; refusing on it would wedge every later run on that
    file. GitHub is asked, as the resume path asks it.

    BOTH LOOKUPS ARE CHECKED rather than left to fail open: this guard's
    one job is not to discard an author's correction, and a failure to ask
    must not read as permission to land. The run stops with a 1, the exit
    table's operating failure, and the author reruns it once gh and the
    network answer again — nothing is pushed in the meantime, so there is
    nothing to undo.

    The `gh pr list` was the one left open, and the whole loss came back
    through it: reproduced 2026-09-22 reviewing PR [Build the GHI write
    tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596),
    against a bare remote with `gh` answering HTTP 401 and git working. A
    first edit landed and opened its pull request; a second edit of the
    same file, made while `gh` was failing, read the failed lookup as no
    open pull request, pushed a second branch, and failed at `gh pr
    create`; once gh answered again the rerun took the already-pushed
    resume path, which does not run this guard, and opened a second pull
    request beside the first — the two branches merging clean in either
    order and main keeping one edit's correction only. The failure is not
    hypothetical: gh 2.46 on ned-box exits with a GraphQL deprecation
    error on a plain `gh pr view`, reviewers were stopped by API 500 and
    529 errors on 2026-09-21, and a token past its expiry fails every gh
    call there is."""
    mine = [path for path in (relative, moved_from) if path]
    listed = runner(["git", "ls-remote", "--heads", "origin",
                     f"ghi-{number}-edit-*"], cwd=str(repository_root))
    for line in (listed.stdout or "").splitlines():
        earlier = line.split("refs/heads/")[-1].strip()
        if not earlier or earlier == branch:
            continue
        found = runner(["gh", "pr", "list", "--repo", repo, "--head",
                        earlier, "--state", "open", "--json",
                        "number,title,url,files"])
        for waiting in json.loads(found.stdout or "[]") or []:
            touched = {entry.get("path")
                       for entry in (waiting.get("files") or [])}
            shared = [path for path in mine if path in touched]
            if not shared:
                continue
            raise Refused(
                f"Refused: an earlier edit of {shared[0]} is waiting for "
                "merge-lane, and this one was written against a main that "
                "does not hold it, so landing both would discard one of "
                "them.\n\n"
                f"Wait for pull request [{waiting.get('title')}]"
                f"({waiting.get('url')}) to merge.\n"
                "Pull main, so your checkout holds that edit.\n"
                "Fold this edit into it.\n"
                "Run this command again.", 66)


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
            "`scripts/ghi-issue-write.py`.\n\nAs a link-only-GHI, the "
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
    question is which OTHER path main files under this issue. A filed GHI-MD
    carries its issue's number in its name wherever it sits, and the move
    changes the directory and not the name, so the name is the match."""
    name = Path(relative).name
    return next((path
                 for path in ghi_md_paths_for_issue(number, repository_root,
                                                    runner)
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
    nothing says the heading changed.

    THE MESSAGE NAMES THE RENAME WITHOUT THE MOVE TOO. It read "if you
    renamed this file as well as moving it" until 2026-09-22, while the
    docstring above says the same code handles a rename inside
    docs/issues/ with no move at all — so the reader whose case that was
    read a line describing somebody else's and passed it by. The user
    approved the wider wording on 2026-09-22, item 8 of the walk
    ghi-write-session-open-rulings-and-concerns. What the old copy costs
    the reader is above, not in the line: the line says what to do."""
    report(f"main holds no copy of {relative}, and no file of issue "
           f"{number} on main carries that name, so nothing is removed and "
           "this lands as a file main does not have.")
    report(f"issue {number}'s files on main: " + ", ".join(paths) +
           ". If you renamed this file, whether or not you also moved it, "
           "land the removal of the old path yourself.")


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
    is what says whether step 2 is asked at all. The two refusals and the
    push below are what the one state with new content to land does, and
    the other two states return above them — see the module docstring, THE
    ORDER MATTERS FOR RESUMING, for why no guard belongs in front of a run
    that pushes nothing. The earlier-edit refusal comes first of the two:
    where both would fire, the pull request it names is the thing to wait
    for, and main's copy is what the author will find once it merges.

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

    refuse_on_an_earlier_edit_still_open(repo, number, relative, moved_from,
                                         branch, repository_root, runner)
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
        # the moment this merges, and ghi_md_paths_for_issue would then link it
        # twice.
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
    unreadable — is an operating failure still, and stays a 1.

    A NUMBER A PULL REQUEST HAS IS A 64 TOO. `gh issue view` given a pull
    request's number exits 0 and answers with the pull request, so the
    failure above never fires and the run edits that pull request's title
    instead of an issue's. Issues and pull requests share one number line
    here: 125 issues among 632 numbers on 2026-09-22, so a mistyped number
    is likelier to name a pull request than to name nothing. Which one came
    back is in the url — `/issues/<number>` against `/pull/<number>` — so
    that is read, and only when it is there, a body of tests answering this
    call with title and body alone being none the wiser. Raised
    non-blocking on PR [Build the GHI write tool's edit
    verb](https://github.com/nedschorus/nedschorus/pull/596)."""
    current = runner(["gh", "issue", "view", str(number), "--repo", repo,
                      "--json", "title,body,url"], check=False)
    if current.returncode != 0:
        said = (current.stderr or current.stdout or "").strip()
        if GH_NO_SUCH_ISSUE_STDERR_FRAGMENT in said.lower():
            raise Refused(
                f"Refused: {repo} has no issue {number}, and {relative} is "
                "named for it.\n\n"
                "Rename the file for the issue it is filed under, if it has "
                "one.\n"
                "If it has no issue yet, file one with the create verb, from "
                "a copy whose name carries no number — create refuses a file "
                "already named for an issue.\n\n"
                f"gh said: {said}", 64)
        raise Refused(f"gh issue view failed: {said}", 1)
    issue = json.loads(current.stdout or "{}")
    url = issue.get("url") or ""
    if url and "/issues/" not in url:
        raise Refused(
            f"Refused: {number} is a pull request in {repo}, not an issue, "
            f"and {relative} is named for it.\n\n"
            "Rename the file for the issue it is filed under, if it has "
            "one.\n"
            "If it has no issue yet, file one with the create verb, from a "
            "copy whose name carries no number — create refuses a file "
            "already named for an issue.\n\n"
            f"gh answered with {url}", 64)
    return issue


def heading_changed_in_this_edit(document_before_this_edit,
                                 heading: str) -> bool:
    """Whether this edit changed the file's first heading, which is the
    design's trigger for the title following it — a CHANGE, not a mismatch.
    `sync_title_on_heading_change` holds what the comparison is made
    against and why, and `issue_title_after_this_edit` asks the same
    question, so the two cannot drift apart."""
    return (document_before_this_edit is not None
            and first_heading(document_before_this_edit) != heading)


def issue_title_after_this_edit(document_before_this_edit, heading: str,
                                paths, issue) -> str:
    """The title the issue carries once this run is done, which is what the
    file's `issue:` frontmatter line has to cite.

    THE ISSUE'S TITLE, NOT THE FILE'S HEADING. That line cites the issue
    the way CLAUDE.md says to cite one — by title, as a link — and it was
    built from `first_heading` until the review of PR [Build the GHI write
    tool's edit verb](https://github.com/nedschorus/nedschorus/pull/596).
    In `create` the two are one thing: the issue is filed under the
    heading. In `edit` they are not, and the docstring's own measurement
    says how far apart — 2026-09-21, of the 26 filed GHI-MDs on main, 25
    have a heading their issue's title does not match. An in-place edit of
    docs/issues/3-slice-6-review-evidence-not-built.md landed an `issue:`
    line naming issue 3 "Slice 6, the review-evidence check", which is that
    file's heading; the issue is titled "main-gatekeeper — the single
    check-in gate", and its four files would have carried four different
    wrong names for it. One of the corpus's headings contains a markdown
    link, which a heading-built line would have nested inside another.

    AFTER THIS RUN, not as GitHub holds it now, because step 4 may change
    it: where the heading did change and the issue has one filed GHI-MD, the
    title follows the heading, and a line citing the old title would be
    stale the moment this landed — and the next rerun would see a file
    differing from main's copy and land a second edit to put it right. The
    two conditions are `sync_title_on_heading_change`'s own, read here
    rather than restated."""
    if (heading_changed_in_this_edit(document_before_this_edit, heading)
            and len(paths) <= 1):
        return heading
    return issue.get("title") or heading


def sync_title_on_heading_change(repo: str, number: int,
                                 document_before_this_edit, title: str,
                                 paths, issue, runner, report):
    """Step 4. The design's trigger is a CHANGE — "when the edit changes the
    file's first heading" — not a mismatch between the issue's title and the
    file's heading, and the difference is not academic. Measured 2026-09-21
    over the filed corpus on main, the 26 files `ghi_md_paths_for_issue`
    returns: 25
    of them have a heading that differs from their issue's title, so a tool
    that made the title match a heading would rename most issues the first
    time anybody edited one.

    An issue with more than one filed GHI-MD is left alone even when the
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
    if not heading_changed_in_this_edit(document_before_this_edit, title):
        return
    if len(paths) > 1:
        report(f"the heading changed, but issue {number} has {len(paths)} "
               "filed GHI-MDs and nothing says which one names it, so the "
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
    body is one link per filed GHI-MD on main, and is rewritten only when it
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
    # Read here, before a fetch, a model call, a push or a pull request: the
    # number is the file's NAME, so a name carrying a number no issue has is
    # the caller's input being wrong, and the run that found that out at
    # step 5 had already pushed a branch and opened a pull request for an
    # issue that does not exist. This one read serves steps 4 and 5 below.
    issue = read_issue(repo, number, relative, runner)

    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    on_main = blob_at("origin/main", relative, repository_root, runner)
    paths = ghi_md_paths_for_issue(number, repository_root, runner)
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

    # The document as main holds it before this edit, which is the author's
    # path where main has one and the path the file moved from where it
    # does not. Step 5 is not given this: it links what main holds AT the
    # author's path, and a moved file is not there until its merge.
    document_before_this_edit = (on_main if on_main is not None
                                 else moved_from_on_main)
    # What lands: the author's file carrying the `issue:` line this tool
    # derives. Built here and not at the top of the run, because that line
    # cites the issue by TITLE, and the title is GitHub's — the one this
    # run leaves the issue holding, which main's copy and the file set are
    # what decide.
    staged = with_issue_frontmatter(
        text, repo, number,
        issue_title_after_this_edit(document_before_this_edit, title, paths,
                                    issue))
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

    sync_title_on_heading_change(repo, number, document_before_this_edit,
                                 title, paths, issue, runner, report)
    finished = relink_body_from_main(repo, number, relative, on_main, paths,
                                     issue, runner, report)
    if pending:
        report("the body follows main's copy of the files, so it changes "
               "when that pull request merges; rerun this command then")
        return number, False
    return number, finished


def repository_root_of(path: Path, runner=run) -> Path:
    """The checkout this path sits in, or a refusal naming it.

    Through the shared `run` like every other subprocess this program makes,
    so that function's docstring — "Every subprocess this program makes goes
    through here" — is true of this one too. check=False, so a path outside
    a checkout keeps this refusal and its 64 rather than becoming `run`'s
    generic exit 1."""
    completed = runner(["git", "rev-parse", "--show-toplevel"], timeout=30,
                       cwd=str(path), check=False)
    if completed.returncode != 0:
        raise Refused(f"{path} is not inside a git checkout", 64)
    return Path(completed.stdout.strip())


class BadInvocationArgumentParser(argparse.ArgumentParser):
    """argparse's own command-line errors join this program's 64.

    argparse exits 2 on a missing or unknown option, and this program has no
    2: the exit codes it documents are 0, 1, 64 and 65, so a caller reading
    that list cannot place a 2 at all. 64 already means the caller's input is
    wrong, which a mistyped flag is. Usage text and message are argparse's,
    unchanged; only the exit code moves. The form is
    scripts/ghi-issue-body-edit.py's parser of the same name."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def main(argv=None):
    parser = BadInvocationArgumentParser(
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
        "edit", help="land an edit to a filed GHI-MD, after which the "
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
            report(f"would land at: {GHI_MD_DIRECTORY}/<number>-"
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
                   "that heading and the issue has one filed GHI-MD")
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
