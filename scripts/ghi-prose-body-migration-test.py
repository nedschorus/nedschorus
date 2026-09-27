#!/usr/bin/env python3
"""Tests for scripts/ghi-prose-body-migration.py.

Run: python3 scripts/ghi-prose-body-migration-test.py
Prints one line per case and exits non-zero if any case fails.

NOTHING HERE TOUCHES GITHUB OR A REAL REPOSITORY. Every subprocess the
program makes goes through one runner, and each case passes a fake that
answers from a small in-memory world: the open issues, main's tree, and the
files main holds. So a case asserts what the program WOULD run — above all,
that `relink-moved-bodies` never issues a `gh issue edit` a case did not earn.

Each hazard case was run against a copy of the program with that hazard's
guard removed, and failed there, before it was kept. The shapes the world
answers with were read from nedschorus/nedschorus and origin/main on
2026-09-24: `gh issue list --json number,title,body` gives bodies with no
trailing newline, `git show <rev>:<path>` exits 128 at a path the revision
lacks, and `git ls-tree -r --name-only` lists blobs one per line.
"""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ghi_prose_body_migration",
    Path(__file__).resolve().with_name("ghi-prose-body-migration.py"))
migration = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(migration)
tool = migration.tool

REPO = "nedschorus/nedschorus"
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Completed:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class World:
    """GitHub's open issues and main's tree, answering the program's calls.

    `issues` is what `gh issue list` returns; `current` overrides what a
    later `gh issue view` of one issue returns, for the case where a body
    changes between the listing and the write. `main` maps each path on
    main to its content."""

    def __init__(self, issues, main=None, current=None):
        self.issues = issues
        self.main = dict(main or {})
        self.current = dict(current or {})
        self.calls = []

    def __call__(self, arguments, timeout=None, cwd=None, check=True):
        self.calls.append(list(arguments))
        answer = self.answer(arguments)
        if check and answer.returncode != 0:
            raise tool.Refused(f"{' '.join(arguments[:3])} failed: "
                               f"{answer.stderr.strip()}", 1)
        return answer

    def answer(self, arguments):
        words = list(arguments)
        if words[:3] == ["gh", "issue", "list"]:
            return Completed(json.dumps(self.issues))
        if words[:3] == ["gh", "issue", "view"]:
            number = int(words[3])
            issue = next(i for i in self.issues if i["number"] == number)
            body = self.current.get(number, issue["body"])
            return Completed(json.dumps({
                "title": issue["title"], "body": body,
                "url": f"https://github.com/{REPO}/issues/{number}"}))
        if words[:3] == ["gh", "issue", "edit"]:
            return Completed()
        if words[:2] == ["git", "fetch"]:
            return Completed()
        if words[:2] == ["git", "ls-tree"]:
            prefixes = [w for w in words[5:]]
            listed = [path for path in sorted(self.main)
                      if not prefixes
                      or any(path.startswith(p) for p in prefixes)]
            return Completed("".join(f"{path}\n" for path in listed))
        if words[:2] == ["git", "show"]:
            path = words[2].split(":", 1)[1]
            if path in self.main:
                return Completed(self.main[path])
            return Completed("", 128, f"fatal: path '{path}' does not exist")
        raise AssertionError(f"unexpected call: {words}")

    def edits(self):
        return [call for call in self.calls
                if call[:3] == ["gh", "issue", "edit"]]


def issue(number, title, body):
    return {"number": number, "title": title, "body": body}


def run_write(world, root, dry_run=False):
    lines = []
    code = migration.write_files(REPO, root, world, lines.append, dry_run)
    return code, lines


def run_relink(world, root, dry_run=False):
    lines = []
    code = migration.relink_moved_bodies(REPO, root, world, lines.append,
                                         dry_run)
    return code, lines


def fresh_root(parent: Path, name: str) -> Path:
    root = parent / name
    (root / "docs" / "issues").mkdir(parents=True)
    return root


def written_files(root: Path):
    return sorted(str(p.relative_to(root))
                  for p in (root / "docs" / "issues").glob("*.md"))


def land(world, root):
    """What merging the write-files pull request does: every file written
    into the checkout is on main."""
    for path in (root / "docs" / "issues").glob("*.md"):
        world.main[str(path.relative_to(root))] = path.read_text(
            encoding="utf-8")


def run_cases(scratch: Path):
    # A body opening with its own heading: the title must still be the
    # heading the write tool reads, and the body must read back whole.
    root = fresh_root(scratch, "heading")
    body = "## What is wanted\n\nA statusline that keeps its branch."
    world = World([issue(12, "Statusline keeps the branch", body)])
    code, lines = run_write(world, root)
    files = written_files(root)
    check("a body opening with ## gets one file named for the issue",
          files == ["docs/issues/12-statusline-keeps-the-branch.md"],
          str(files))
    text = (root / files[0]).read_text(encoding="utf-8") if files else ""
    check("the write tool reads the issue's title as the file's heading",
          tool.first_heading(text) == "Statusline keeps the branch",
          repr(tool.first_heading(text)))
    check("the file holds the body verbatim",
          migration.body_held_by(text) == body, repr(text))
    check("the file carries the issue: frontmatter line a filed file has",
          text.startswith("---\nissue: ") and "/issues/12)" in text,
          text[:120])
    check("a clean run exits 0", code == 0, str(code))

    # A body line starting with '#' that is not a heading, and a bare issue
    # reference: both stay verbatim, and the title is still first.
    root = fresh_root(scratch, "bare-reference")
    body = "#46 is the design.\nSee #639 too."
    world = World([issue(7, "Name the design", body)])
    run_write(world, root)
    text = (root / written_files(root)[0]).read_text(encoding="utf-8")
    check("a body line opening with #46 does not become the title",
          tool.first_heading(text) == "Name the design",
          repr(tool.first_heading(text)))
    check("bare issue references stay verbatim",
          "#46 is the design.\nSee #639 too." in text, text)

    # CRLF: the file holds LF only, and relink-moved-bodies still matches
    # the CRLF body.
    root = fresh_root(scratch, "crlf")
    body = "line one\r\nline two\r\n"
    world = World([issue(8, "Carriage returns", body)])
    run_write(world, root)
    files = written_files(root)
    check("a CRLF body gets its file", len(files) == 1, str(files))
    text = (root / files[0]).read_text(encoding="utf-8") if files else "\r"
    check("a CRLF body is written with LF only", "\r" not in text, repr(text))
    land(world, root)
    code, lines = run_relink(world, root)
    check("relink-moved-bodies matches a CRLF body against its LF file",
          len(world.edits()) == 1 and code == 0, "\n".join(lines))

    # An empty body with no file: stuck like a prose one, so it gets a file
    # holding its heading, and relink-moved-bodies links it.
    root = fresh_root(scratch, "empty")
    world = World([issue(9, "Nothing written yet", "")])
    code, lines = run_write(world, root)
    files = written_files(root)
    check("an empty body with no file gets a heading-only file",
          files == ["docs/issues/9-nothing-written-yet.md"], str(files))
    check("the empty body is counted", "empty body 1" in lines[-1], lines[-1])
    land(world, root)
    run_relink(world, root)
    check("relink-moved-bodies links an empty body whose heading-only "
          "file is on main",
          len(world.edits()) == 1, str(world.calls))

    # The equality gate: a body edited after write-files ran is left alone.
    root = fresh_root(scratch, "gate")
    world = World([issue(10, "Moving target", "first words")])
    run_write(world, root)
    land(world, root)
    world.issues[0]["body"] = "first words, then more written later"
    code, lines = run_relink(world, root)
    check("relink-moved-bodies never rewrites a body no file on main holds",
          world.edits() == [], str(world.edits()))
    check("that issue is reported, and the run exits 3",
          code == 3 and any("differs" in line for line in lines),
          "\n".join(lines))

    # The re-read: the listing matched, but the body changed before the
    # write.
    root = fresh_root(scratch, "reread")
    world = World([issue(11, "Changed mid-run", "as listed")])
    run_write(world, root)
    land(world, root)
    world.current[11] = "as listed, and edited a second later"
    code, lines = run_relink(world, root)
    check("relink-moved-bodies reads the body again and leaves a changed "
          "one alone",
          world.edits() == [] and code == 3, "\n".join(lines))

    # Derived bodies: a link list and a filing placeholder are not moved and
    # not rewritten.
    root = fresh_root(scratch, "derived")
    links = ("- [13-a.md](https://github.com/"
             f"{REPO}/blob/main/docs/issues/13-a.md)")
    placeholder = tool.placeholder_body("ghipair0123456789abcdef")
    world = World([issue(13, "Already links", links),
                   issue(14, "Filing in flight", placeholder)],
                  main={"docs/issues/13-a.md": "# A\n"})
    code, lines = run_write(world, root)
    check("write-files writes nothing for a link list or a placeholder",
          written_files(root) == [], str(written_files(root)))
    code, lines = run_relink(world, root)
    check("relink-moved-bodies leaves a link list and a placeholder alone",
          world.edits() == [] and code == 0, "\n".join(lines))

    # An issue that already has a filed GHI-MD: a second file, the first
    # untouched, and relink-moved-bodies links both.
    root = fresh_root(scratch, "second-file")
    existing = "docs/issues/15-design-of-the-thing.md"
    world = World([issue(15, "The thing", "Summary of the thing.")],
                  main={existing: "---\nstatus: draft\n---\n\n## Design\n"})
    run_write(world, root)
    files = written_files(root)
    check("an issue with a GHI-MD gets a second, distinctly named file",
          files == ["docs/issues/15-the-thing-former-issue-body.md"],
          str(files))
    land(world, root)
    run_relink(world, root)
    edits = world.edits()
    second = "docs/issues/15-the-thing-former-issue-body.md"
    expected = tool.links_body(REPO, [existing, second])
    check("relink-moved-bodies links both of that issue's files",
          len(edits) == 1 and edits[0][-1] == expected,
          str(edits))
    check("the existing GHI-MD is not written",
          world.main[existing] == "---\nstatus: draft\n---\n\n## Design\n",
          world.main[existing])

    # A name another tracked file already has, at any depth: refused for
    # that issue, the rest proceed.
    root = fresh_root(scratch, "collision")
    world = World([issue(16, "Queue note", "body a"),
                   issue(17, "Fine", "body b")],
                  main={"docs/issues/queue/16-queue-note.md": "# q\n"})
    code, lines = run_write(world, root)
    check("a name a tracked file has is refused and nothing is written",
          written_files(root) == ["docs/issues/17-fine.md"],
          str(written_files(root)))
    check("the refusal is reported and the run exits 3",
          code == 3 and any("already a file name" in line for line in lines),
          "\n".join(lines))

    # A title the write tool would read back differently: first_heading
    # strips the heading line, so surrounding space is lost. A title opening
    # with '#' is not such a title — "# #1 priority" reads back whole.
    root = fresh_root(scratch, "hash-title")
    world = World([issue(18, "#1 priority", "body")])
    run_write(world, root)
    check("a title opening with # is written and reads back whole",
          written_files(root) == ["docs/issues/18-1-priority.md"],
          str(written_files(root)))
    root = fresh_root(scratch, "space-title")
    world = World([issue(18, "Trailing space ", "body")])
    code, lines = run_write(world, root)
    check("a title first_heading would alter is refused",
          written_files(root) == [] and code == 3, "\n".join(lines))

    # Reruns: a body already on main, and a file already written here.
    root = fresh_root(scratch, "rerun")
    world = World([issue(19, "Twice", "same words")])
    run_write(world, root)
    code, lines = run_write(world, root)
    check("a rerun before the merge counts the file as already written",
          code == 0 and "already written 1" in lines[-1], lines[-1])
    land(world, root)
    for path in (root / "docs" / "issues").glob("*.md"):
        path.unlink()
    code, lines = run_write(world, root)
    check("a rerun after the merge writes nothing for a body on main",
          written_files(root) == [] and "already on main 1" in lines[-1],
          lines[-1])

    # Dry runs write and edit nothing.
    root = fresh_root(scratch, "dry")
    world = World([issue(20, "Dry", "words")])
    run_write(world, root, dry_run=True)
    check("write-files --dry-run writes no file", written_files(root) == [],
          str(written_files(root)))
    world.main["docs/issues/20-dry.md"] = migration.moved_file_text(
        REPO, 20, "Dry", "words")
    code, lines = run_relink(world, root, dry_run=True)
    check("relink-moved-bodies --dry-run edits no issue and says what it "
          "would link",
          world.edits() == [] and any("would link" in line for line in lines),
          "\n".join(lines))

    # A listing at gh's limit may be cut short.
    world = World([issue(n, f"t{n}", "b")
                   for n in range(1, migration.OPEN_ISSUE_LISTING_LIMIT + 1)])
    try:
        migration.open_issues(REPO, world)
        check("a listing at the limit is refused", False, "it proceeded")
    except tool.Refused:
        check("a listing at the limit is refused", True)

    # --as-if-main: git reads of origin/main go to the revision, the fetch
    # is skipped, and gh calls pass through untouched.
    world = World([], main={"docs/issues/1-a.md": "# A\n"})
    substituted = migration.runner_reading_revision_as_main("abc123", world)
    substituted(["git", "show", "origin/main:docs/issues/1-a.md"])
    substituted(["git", "ls-tree", "-r", "--name-only", "origin/main",
                 "docs/issues/"])
    substituted(["git", "fetch", "origin", "main"])
    substituted(["gh", "issue", "list", "--repo", REPO])
    check("--as-if-main reads the revision in place of origin/main",
          world.calls[0] == ["git", "show", "abc123:docs/issues/1-a.md"]
          and world.calls[1][4] == "abc123", str(world.calls))
    check("--as-if-main makes no fetch and passes gh through",
          [c[:2] for c in world.calls[2:]] == [["gh", "issue"]],
          str(world.calls))

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            code = migration.main(["relink-moved-bodies", "--as-if-main",
                                   "abc123"])
        except SystemExit as exit_:
            code = exit_.code
    check("--as-if-main without --dry-run is a command-line error, 64",
          code == 64, f"{code} {stderr.getvalue()}")


def main():
    with tempfile.TemporaryDirectory(
            prefix="ghi-prose-body-migration-test-") as name:
        run_cases(Path(name))
    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
