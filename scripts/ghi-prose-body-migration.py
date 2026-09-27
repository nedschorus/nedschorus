#!/usr/bin/env python3
"""Move every open issue's prose body into a filed GHI-MD, then make the
body the links to that issue's files. The migration build-slice that
docs/issues/46-ghi-info-agent-design.md § The GHI write path names and
leaves unbuilt: "The existing corpus is migrated in its own build-slice,
after this tool exists".

WHY NOW. The user ruled on 2026-09-15 that a GHI's body is the links to its
GHI-MD and nothing else. On 2026-09-24 the redirect hook
(.claude/hooks/ghi-issue-write-redirect.py) began refusing hand-typed
comments and body edits and telling an agent whose issue has no GHI-MD to
stop and tell the user. Measured that day on nedschorus/nedschorus: of 75
open issues, 1 had a link-only body, 16 a prose body beside a filed GHI-MD,
and 58 a prose body and no GHI-MD at all — so for 58 issues an agent had no
way left to record anything. The user, shown those numbers during the walk
decisions-this-seat-owes-the-user-2026-09-22 (item 5): "Move them all now."

TWO VERBS, ONE PULL REQUEST BETWEEN THEM. A body of links points at
`blob/main`, and main takes no direct push, so the move cannot be one step.

  write-files
      Read every open issue. For each whose body is prose, write that body
      verbatim, under a first heading that is the issue's exact title, to a
      file in docs/issues/ in this checkout. The author commits the files
      and lands them through one pull request, merged by merge-lane like
      any other.
  relink-moved-bodies
      Run after that pull request merges. For each open issue whose body is
      prose, find the file on main that holds exactly that body; where one
      does, rewrite the body as one link per filed GHI-MD of the issue —
      `ghi-issue-write.py`'s own link list.

THE EQUALITY GATE IS THE WHOLE OF relink-moved-bodies' SAFETY. A body is
rewritten only when a file on main holds it word for word (after the one
normalization the write tool compares bodies with), and it is read again
just before the write. A body somebody edited after write-files ran matches
no file and is left alone and reported: rerun write-files, which writes
nothing for an issue whose body is already on main and a file for one whose
body is not, land that, and run relink-moved-bodies again. Nothing is ever
overwritten on a guess.

NAMES. An issue with no filed GHI-MD gets `docs/issues/<number>-<slug>.md`,
the name `create` gives a filed file. An issue that already has one gets a
second file, `<number>-<slug>-former-issue-body.md`: its existing GHI-MD is
never edited, so nothing has to judge whether that file already says what
the body said. A second file also cannot rename the issue: the edit verb
changes a title only for an issue with one filed GHI-MD
(`sync_title_on_heading_change`). A name any tracked file already has, at
any depth, is refused for that issue and the rest proceed.

THE HEADING. The write tool reads a file's title as its first line starting
with `#` at any level, after frontmatter (`first_heading`). 34 of the 75
bodies opened with their own `##` heading on 2026-09-24, so the title is
written as the file's first heading above the body, and every file is
checked with `first_heading` itself before it is written. The `issue:`
frontmatter line is `with_issue_frontmatter`'s, as a filed file carries.

EMPTY BODIES. `is_derived_body` calls an empty body derived, which is right
for relinking and wrong here: an empty-bodied issue with no GHI-MD is as
stuck as a prose one. So an empty body with no filed GHI-MD gets a file
holding its heading alone. None existed on 2026-09-24.

WHAT THIS IMPORTS rather than restates: the write tool's `slug`,
`links_body`, `is_derived_body`, `normalized`, `first_heading`,
`with_issue_frontmatter`, `ghi_md_paths_for_issue`, `blob_at`, `read_issue`
and `run`. The body this writes and the body `edit` would write are one
function's output, so the two cannot disagree.

Exit codes:
  0   every open issue was moved, relinked, or needed nothing
  1   an operating failure — gh, git or the network
  3   the run finished, and at least one issue was refused or skipped by the
      equality gate; the lines above say which and what to do
  64  the command line is wrong
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TOOL_PATH = Path(__file__).resolve().with_name("ghi-issue-write.py")
_TOOL_SPEC = importlib.util.spec_from_file_location("ghi_issue_write",
                                                    _TOOL_PATH)
tool = importlib.util.module_from_spec(_TOOL_SPEC)
_TOOL_SPEC.loader.exec_module(tool)

# gh returns at most this many; a listing this long may be cut short, and a
# migration that silently missed the rest would report success over them.
OPEN_ISSUE_LISTING_LIMIT = 1000
FORMER_BODY_FILE_SUFFIX = "-former-issue-body"
EXIT_SOME_ISSUES_LEFT = 3


def open_issues(repo: str, runner):
    """Every open issue's number, title and body, read from the API."""
    completed = runner(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--limit", str(OPEN_ISSUE_LISTING_LIMIT),
         "--json", "number,title,body"])
    issues = json.loads(completed.stdout or "[]")
    if len(issues) >= OPEN_ISSUE_LISTING_LIMIT:
        raise tool.Refused(
            f"gh listed {len(issues)} open issues, its limit, so the list "
            "may be cut short.\n"
            "Raise OPEN_ISSUE_LISTING_LIMIT in this program and run it "
            "again.", 1)
    return sorted(issues, key=lambda issue: issue["number"])


def moved_file_text(repo: str, number: int, title: str, body: str) -> str:
    """The file write-files writes for one issue: frontmatter, the title as
    the first heading, a blank line, then the body verbatim."""
    text = f"# {title}\n" + (f"\n{body}\n" if body else "")
    return tool.with_issue_frontmatter(text, repo, number, title)


def body_held_by(file_text):
    """The body a file holds when it has moved_file_text's shape, or None.
    The exact inverse of moved_file_text: frontmatter skipped, the first
    heading and the one blank line after it dropped, the rest normalized.
    A file of any other shape — an author's GHI-MD opening with a `##`
    heading, say — holds no body, and so never passes the gate."""
    if file_text is None:
        return None
    lines = tool.normalized(file_text).split("\n")
    index = 0
    if lines and lines[0].strip() == "---":
        for position in range(1, len(lines)):
            if lines[position].strip() == "---":
                index = position + 1
                break
        else:
            return None
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith("# "):
        return None
    rest = lines[index + 1:]
    if rest and rest[0] == "":
        rest = rest[1:]
    return tool.normalized("\n".join(rest))


def files_on_main_holding(body: str, paths, repository_root: Path, runner):
    return [path for path in paths
            if body_held_by(tool.blob_at("origin/main", path,
                                         repository_root, runner)) == body]


def tracked_file_names(repository_root: Path, runner):
    listed = runner(["git", "ls-tree", "-r", "--name-only", "origin/main"],
                    cwd=str(repository_root))
    return {Path(line).name for line in (listed.stdout or "").splitlines()
            if line}


def write_files(repo: str, repository_root: Path, runner, report,
                dry_run=False, save_fetched_bodies_to=None) -> int:
    """Phase A. Returns the exit code."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    issues = open_issues(repo, runner)
    if save_fetched_bodies_to:
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        Path(save_fetched_bodies_to).write_text(json.dumps(
            {"repository": repo, "fetched_at": fetched_at,
             "issues": issues}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        report(f"saved {len(issues)} open issues' bodies to "
               f"{save_fetched_bodies_to}")
    taken = tracked_file_names(repository_root, runner)
    counts = {"link-only": 0, "empty with a file": 0, "already on main": 0,
              "already written": 0, "new file": 0, "second file": 0,
              "empty body": 0, "refused": 0}
    for issue in issues:
        number, title = issue["number"], issue["title"]
        body = tool.normalized(issue.get("body"))
        if body and tool.is_derived_body(body):
            counts["link-only"] += 1
            continue
        paths = tool.ghi_md_paths_for_issue(number, repository_root, runner)
        if not body and paths:
            counts["empty with a file"] += 1
            continue
        if files_on_main_holding(body, paths, repository_root, runner):
            counts["already on main"] += 1
            report(f"issue {number}: its body is already on main; "
                   "relink-moved-bodies will link it")
            continue
        suffix = FORMER_BODY_FILE_SUFFIX if paths else ""
        name = f"{number}-{tool.slug(title)}{suffix}.md"
        relative = f"{tool.GHI_MD_DIRECTORY}/{name}"
        destination = repository_root / relative
        text = moved_file_text(repo, number, title, body)
        if (destination.is_file()
                and destination.read_text(encoding="utf-8") == text):
            counts["already written"] += 1
            continue
        if name in taken or destination.exists():
            counts["refused"] += 1
            report(f"issue {number}: refused, {name} is already a file name "
                   "in this repository.\n"
                   "Choose a name no tracked file has for this issue's body "
                   "and write it by hand.")
            continue
        if tool.first_heading(text) != title or body_held_by(text) != body:
            counts["refused"] += 1
            report(f"issue {number}: refused, the file would not read back "
                   "as this issue's title and body.\n"
                   "Move this issue's body by hand.")
            continue
        if not dry_run:
            destination.write_text(text, encoding="utf-8")
        taken.add(name)
        counts["second file" if paths else "new file"] += 1
        if not body:
            counts["empty body"] += 1
        report(f"issue {number}: {'would write' if dry_run else 'wrote'} "
               f"{relative}")
    report(f"{len(issues)} open issues: " + ", ".join(
        f"{key} {value}" for key, value in counts.items()))
    return EXIT_SOME_ISSUES_LEFT if counts["refused"] else 0


def runner_reading_revision_as_main(revision: str, runner):
    """A runner that answers every git read of origin/main from `revision`
    instead, so a dry run can show what relink-moved-bodies would do once a
    branch has merged. Refused for a real run by the caller."""
    def substituted(arguments, **keywords):
        if arguments and arguments[0] == "git":
            arguments = [argument.replace("origin/main", revision, 1)
                         if argument.startswith("origin/main") else argument
                         for argument in arguments]
            if arguments[1:2] == ["fetch"]:
                return tool.run(["true"])
        return runner(arguments, **keywords)
    return substituted


def relink_moved_bodies(repo: str, repository_root: Path, runner, report,
                        dry_run=False, table_to=None) -> int:
    """Phase B. Returns the exit code."""
    runner(["git", "fetch", "origin", "main"], cwd=str(repository_root))
    issues = open_issues(repo, runner)
    counts = {"link-only": 0, "filing in flight": 0, "relinked": 0,
              "no file on main": 0, "body differs": 0}
    table = []
    for issue in issues:
        number = issue["number"]
        body = tool.normalized(issue.get("body"))
        if tool.PAIRING_KEY_PREFIX in body:
            counts["filing in flight"] += 1
            continue
        if body and tool.is_derived_body(body):
            counts["link-only"] += 1
            continue
        paths = tool.ghi_md_paths_for_issue(number, repository_root, runner)
        if not paths:
            counts["no file on main"] += 1
            report(f"issue {number}: left alone, no file of it is on main.\n"
                   "Run write-files, land its pull request, then run "
                   "relink-moved-bodies again.")
            continue
        holders = files_on_main_holding(body, paths, repository_root, runner)
        if holders:
            # Read again just before the write: the listing above may be
            # minutes old by now, and a body edited since matches no file.
            current = tool.read_issue(repo, number, holders[0], runner)
        if not holders or tool.normalized(current.get("body")) != body:
            counts["body differs"] += 1
            report(f"issue {number}: left alone, its body differs from every "
                   "file of it on main.\n"
                   "Run write-files, land its pull request, then run "
                   "relink-moved-bodies again.")
            continue
        links = tool.links_body(repo, paths)
        table.append({"number": number, "title": issue["title"],
                      "body_held_by": holders[0], "links": paths})
        if not dry_run:
            runner(["gh", "issue", "edit", str(number), "--repo", repo,
                    "--body", links])
        counts["relinked"] += 1
        report(f"issue {number}: {'would link' if dry_run else 'linked'} "
               + ", ".join(paths))
    if table_to:
        Path(table_to).write_text(json.dumps(table, indent=1,
                                             ensure_ascii=False) + "\n",
                                  encoding="utf-8")
        report(f"wrote the {len(table)}-issue table to {table_to}")
    report(f"{len(issues)} open issues: " + ", ".join(
        f"{key} {value}" for key, value in counts.items()))
    left = counts["no file on main"] + counts["body differs"]
    return EXIT_SOME_ISSUES_LEFT if left else 0


def main(argv=None):
    parser = tool.BadInvocationArgumentParser(
        description="Move every open issue's prose body into a filed GHI-MD "
                    "(write-files), then, once those files are on main, make "
                    "each body the links to its files (relink-moved-bodies).")
    sub = parser.add_subparsers(dest="verb", required=True)
    writer = sub.add_parser("write-files",
                            help="write each prose body to docs/issues/")
    writer.add_argument("--repo", default=tool.DEFAULT_REPO)
    writer.add_argument("--dry-run", action="store_true",
                        help="print what would be written, writing nothing")
    writer.add_argument("--save-fetched-bodies", metavar="PATH",
                        help="also save every open issue's body, as read, "
                             "to this JSON file")
    linker = sub.add_parser("relink-moved-bodies",
                            help="rewrite each moved body as its links")
    linker.add_argument("--repo", default=tool.DEFAULT_REPO)
    linker.add_argument("--dry-run", action="store_true",
                        help="print what would be rewritten, rewriting "
                             "nothing")
    linker.add_argument("--as-if-main", metavar="REVISION",
                        help="with --dry-run only: read this revision as "
                             "main, to preview a branch before it merges")
    linker.add_argument("--table", metavar="PATH",
                        help="write the issue-to-files table to this JSON "
                             "file")
    arguments = parser.parse_args(argv)
    if arguments.verb == "relink-moved-bodies" and arguments.as_if_main \
            and not arguments.dry_run:
        parser.error("--as-if-main previews only; add --dry-run")

    def report(line):
        if line:
            print(line)

    try:
        root = tool.repository_root_of(Path(__file__).resolve().parent)
        if arguments.verb == "write-files":
            return write_files(arguments.repo, root, tool.run, report,
                               arguments.dry_run,
                               arguments.save_fetched_bodies)
        runner = tool.run
        if arguments.as_if_main:
            runner = runner_reading_revision_as_main(arguments.as_if_main,
                                                     tool.run)
        return relink_moved_bodies(arguments.repo, root, runner, report,
                      arguments.dry_run, arguments.table)
    except tool.Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return refusal.code
    except subprocess.TimeoutExpired as expiry:
        print(f"timed out: {expiry}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
