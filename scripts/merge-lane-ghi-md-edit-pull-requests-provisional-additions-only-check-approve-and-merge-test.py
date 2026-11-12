#!/usr/bin/env python3
"""Tests for merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py.

The program is loaded by path and its main() is called in this process, with
a fake `gh` first on PATH, HOME pointing at a scratch home that holds the
merge account's token file, and scratch outputs and review worktrees
directories. The fake `gh` logs every call with the GH_TOKEN it saw and
answers from a routes file the case writes. The program's CHECKOUT is a
clone of a scratch origin repository, so the review tools worktree is made
and moved by real git, and its MERGE_PROGRAM is a fake that logs its
arguments and exits with the code the case writes.

Run: python3 scripts/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge-test.py
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name(
    "merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py")
_spec = importlib.util.spec_from_file_location("ghi_md_edit_auto_merge", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

TOKEN = "ghi-md-edit-auto-merge-test-token-not-a-credential"
HEAD = "b" * 40
NEW_HEAD = "c" * 40
SUBMITTED = "2026-11-07T22:00:00Z"
HEADING = "## Provisional additions (not yet vetted by the user)"
MERGE_BASE = "a" * 40
FILE = [{"filename": "docs/issues/9-x.md", "status": "modified"}]
BASE_TEXT = "".join(f"line {number}\n" for number in range(1, 11))
PASSING_FILE_TEXT = BASE_TEXT + "\n" + HEADING + "\n- an addition\n"
# A file whose section sits between two vetted sections, and the same file with one line added.
SECTION_BASE_TEXT = ("## Problem\nvetted\n\n" + HEADING + "\n\n- old\n\n## Next action\n"
                     "vetted next\n")
SECTION_HEAD_TEXT = SECTION_BASE_TEXT.replace("- old\n", "- old\n- new\n")

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"]
argv = sys.argv[1:]
with open(os.path.join(directory, "gh-calls.log"), "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.path.join(directory, "gh-routes.json")))
if argv[:2] == ["pr", "view"]:
    key = f"view {argv[2]} {argv[argv.index('--json') + 1]}"
elif argv[0] == "api" and "/contents/" in argv[-1]:
    key = "contents " + argv[-1].split("?ref=")[1]
elif argv[0] == "api" and "/compare/" in argv[-1]:
    key = "compare " + argv[-1].split("/compare/")[1]
elif argv[0] == "api":
    key = "api " + argv[3].split("/")[4]
else:
    key = " ".join(argv[:2])
route = routes[key]
if route.get("killed"):
    os.kill(os.getpid(), 9)
sys.stdout.buffer.write(bytes.fromhex(route["out_hex"]) if "out_hex" in route
                        else route.get("out", "").encode())
sys.stderr.write(route.get("err", ""))
sys.exit(route.get("exit", 0))
'''

FAKE_MERGE = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"]
with open(os.path.join(directory, "merge-calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
print("merge line one\nmerge line two\nmerge program last line", flush=True)
code = int(open(os.path.join(directory, "merge.exit")).read())
if code < 0:
    os.kill(os.getpid(), -code)
sys.exit(code)
'''

failures = []


def check(name, condition, detail=""):
    if not condition:
        failures.append(name)
        print(f"FAIL: {name}\n{detail}")
    else:
        print(f"ok: {name}")


def git(*arguments, cwd=None):
    subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True)


def listed(*entries):
    return json.dumps([{"number": number, "title": title, "headRefOid": head, "isDraft": draft,
                        "baseRefName": "main"} for number, title, head, draft in entries])


def routes_for(number=9, head=HEAD, files=FILE, base_text=BASE_TEXT, head_after_read=None,
               review=None, review_exit=0, entries=None, file_text=PASSING_FILE_TEXT,
               contents_exit=0, head_bytes_hex=None):
    entries = entries if entries is not None else [
        (number, f"GHI-MD edit for issue {number}: a title", head, False)]
    return {
        "pr list": {"out": listed(*entries)},
        f"compare main...{head}": {"out": json.dumps({"files": files,
                                                       "merge_base_commit": {"sha": MERGE_BASE}})},
        f"contents {MERGE_BASE}": {"out": base_text},
        f"contents {head}": ({"out_hex": head_bytes_hex} if head_bytes_hex
                             else {"out": file_text} if contents_exit == 0
                             else {"exit": contents_exit, "err": "HTTP 404"}),
        f"view {number} headRefOid": {"out": json.dumps({"headRefOid": head_after_read or head})},
        f"api {number}": ({"out": json.dumps(review if review is not None
                                             else {"submitted_at": SUBMITTED})}
                          if review_exit == 0 else {"exit": review_exit, "err": "refused"}),
    }


class Scratch:
    def __init__(self, root, name):
        self.directory = root / name
        self.directory.mkdir()
        self.home = self.directory / "home"
        (self.home / ".config" / "nedschorus").mkdir(parents=True)
        (self.home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(TOKEN + "\n")
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.merge_program = self.directory / "fake-merge.py"
        self.merge_program.write_text(FAKE_MERGE)
        (self.directory / "merge.exit").write_text("0")
        self.outputs = self.directory / "outputs"
        self.review_worktrees = self.directory / "review-worktrees"
        self.state = self.outputs / "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages"
        self.origin = self.directory / "origin"
        git("init", "-q", "-b", "main", str(self.origin))
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m",
            "one", cwd=self.origin)
        self.checkout = self.directory / "checkout"
        git("clone", "-q", str(self.origin), str(self.checkout))
        self.worktree = self.review_worktrees / "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-review-tools-worktree-at-main"

    def routes(self, routes):
        (self.directory / "gh-routes.json").write_text(json.dumps(routes))

    def run(self, extra=(), checkout=None, path_only_fake_bin=False):
        saved = dict(os.environ), program.CHECKOUT, program.MERGE_PROGRAM
        os.environ["HOME"] = str(self.home)
        os.environ["PATH"] = (str(self.bin) if path_only_fake_bin
                              else f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        os.environ["GHI_MD_AUTO_MERGE_TEST_DIRECTORY"] = str(self.directory)
        program.CHECKOUT = checkout or self.checkout
        program.MERGE_PROGRAM = self.merge_program
        printed = io.StringIO()
        try:
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                code = program.main(["--merge-lane-worktrees-and-outputs-directory",
                                     str(self.outputs), "--merge-lane-review-worktrees-directory",
                                     str(self.review_worktrees), *extra])
        finally:
            os.environ.clear()
            os.environ.update(saved[0])
            program.CHECKOUT, program.MERGE_PROGRAM = saved[1], saved[2]
        return code, printed.getvalue()

    def gh_calls(self):
        log = self.directory / "gh-calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def merge_calls(self):
        log = self.directory / "merge-calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def messages(self):
        directory = self.state / "needs-a-look"
        return sorted(path.name for path in directory.iterdir()) if directory.is_dir() else []

    def message(self, name):
        return (self.state / "needs-a-look" / name).read_text()

    def record(self):
        path = self.state / "reported-nc-head-commits.json"
        return json.loads(path.read_text()) if path.exists() else None


def approvals(scratch):
    return [call["argv"] for call in scratch.gh_calls()
            if call["argv"][0] == "api" and "/contents/" not in call["argv"][-1]
            and "/compare/" not in call["argv"][-1]]


def main():
    root = Path(tempfile.mkdtemp(prefix="ghi-md-edit-auto-merge-test-"))
    try:
        # --- a passing pull request is approved at its nc-head-commit and merged
        scratch = Scratch(root, "passes")
        scratch.routes(routes_for())
        code, output = scratch.run()
        approval = approvals(scratch)
        merges = scratch.merge_calls()
        check("a pull request that only adds provisional-additions is approved, pinned to its "
              "nc-head-commit, and merged with the approval's time, exit 0",
              code == 0 and len(approval) == 1 and f"commit_id={HEAD}" in approval[0]
              and "event=APPROVE" in approval[0]
              and any(argument.startswith("body=") and "adding a \"Provisional additions"
                      in argument for argument in approval[0])
              and merges and merges[0][:3] == ["9", HEAD, SUBMITTED]
              and "merged: merge program last line" in output and scratch.messages() == [],
              f"exit {code}\n{output}\n{approval}\n{merges}")
        check("the file is read at the nc-head-commit",
              any(call["argv"][-1] == f"repos/nedschorus/nedschorus/contents/docs/issues/9-x.md"
                  f"?ref={HEAD}" for call in scratch.gh_calls()), scratch.gh_calls())
        check("every gh call carries the merge account's token",
              all(call["gh_token"] == TOKEN for call in scratch.gh_calls()), scratch.gh_calls())
        check("the merge runs merge-gate.sh from the program's own review tools worktree, made at "
              "origin/main",
              merges and merges[0][merges[0].index("--review-tools-worktree-at-main") + 1]
              == str(scratch.worktree.resolve())
              and (scratch.worktree / ".git").exists(), merges)

        # --- adding lines to an existing section is approved with the other wording
        scratch = Scratch(root, "existing-section")
        scratch.routes(routes_for(base_text=SECTION_BASE_TEXT, file_text=SECTION_HEAD_TEXT))
        code, output = scratch.run()
        check("lines added at the end of an existing section, above the blank line that ends it, "
              "are approved with that section's wording",
              code == 0 and len(approvals(scratch)) == 1
              and any("adding lines to its existing" in argument
                      for argument in approvals(scratch)[0]), f"exit {code}\n{output}")
        scratch = Scratch(root, "existing-section-top")
        scratch.routes(routes_for(base_text=SECTION_BASE_TEXT, file_text=SECTION_BASE_TEXT.replace(
            "- old\n", "- new\n- old\n")))
        code, output = scratch.run()
        check("a line added at the top of an existing section is approved",
              code == 0 and len(approvals(scratch)) == 1, f"exit {code}\n{output}")

        # --- a new section between two vetted sections, after a blank line, is approved
        scratch = Scratch(root, "new-section-between-sections")
        middle_base = "## Problem\nvetted\n\n## Next action\nvetted next\n"
        scratch.routes(routes_for(base_text=middle_base, file_text=middle_base.replace(
            "\n## Next action", "\n" + HEADING + "\n\n- new\n\n## Next action")))
        code, output = scratch.run()
        check("a new section put between two vetted sections is approved with the new-section "
              "wording", code == 0 and len(approvals(scratch)) == 1
              and any("adding a \"Provisional additions" in argument
                      for argument in approvals(scratch)[0]),
              f"exit {code}\n{output}")

        # --- every line break other than "\n" is refused, in either text, as a problem
        parser = program.markdown_parser()
        for character in "\r\x0b\x0c\x1c\x1d\x1e\x85  ":
            for base_text, head_text, where, line in (
                    (SECTION_BASE_TEXT, SECTION_HEAD_TEXT.replace("- new", "- n" + character + "ew"),
                     "nc-head-commit", 7),
                    (SECTION_BASE_TEXT.replace("- old", "- o" + character + "ld"),
                     SECTION_HEAD_TEXT.replace("- old", "- o" + character + "ld"), "merge base", 6)):
                problem = program.provisional_additions_only_problem(parser, base_text, head_text)
                check(f"U+{ord(character):04X} at the {where} is refused, naming its line",
                      problem == (f"the file at the {where} holds U+{ord(character):04X} on line "
                                  f"{line}, which Markdown or git reads as a line break where the "
                                  f"other does not"), problem)

        # --- the check's answers, exactly, where a section sits at the file's edges
        long_line = "y" * 200
        for name, base_text, head_text, expected in (
                ("a section that starts the file takes lines added at its end",
                 HEADING + "\n- a\n", HEADING + "\n- a\n- b\n", None),
                ("a new section after one blank line is a passing addition",
                 "x\n", "x\n\n" + HEADING + "\n- a\n", None),
                ("a changed line outside the section is named with the section's lines, cut to "
                 "120 characters",
                 "## Problem\n" + long_line + "\n\n" + HEADING + "\n- a\n",
                 "## Problem\n" + long_line + "z\n\n" + HEADING + "\n- a\n- b\n",
                 f"it changes text outside the section \"{HEADING}\" (lines 3 to 6 of the file at "
                 f"the nc-head-commit): the first line that differs is {long_line[:120]!r} at the "
                 f"merge base and {long_line[:120]!r} at the nc-head-commit"),
                ("an added heading is named by its place among the other headings",
                 "## One\n## Two\n" + HEADING + "\n- a\n",
                 "## One\n## Two\n" + HEADING + "\n- a\n## Three\n",
                 f"it adds, removes or changes a heading other than \"{HEADING}\": heading 3 is "
                 f"'none' at the merge base and ('h2', 0, '## Three') at the nc-head-commit"),
                ("a link reference definition already outside the section does not stop lines "
                 "being added to it",
                 "## Problem\nSee [x].\n\n[x]: https://example.com\n\n" + HEADING + "\n- a\n",
                 "## Problem\nSee [x].\n\n[x]: https://example.com\n\n" + HEADING + "\n- a\n- b\n",
                 None),
                ("an added link reference definition is named with the one it adds",
                 "See [x].\n\n" + HEADING + "\n- a\n",
                 "See [x].\n\n" + HEADING + "\n- a\n\n[x]: https://example.com\n",
                 f"it adds, removes or changes a Markdown link reference definition, such as "
                 f"\"[x]: https://example.com\", which renders as nothing and can change where "
                 f"other links in the file point: definition 1 is 'none' at the merge base and "
                 f"('X', 'https://example.com', '') at the nc-head-commit"),
                ("a moved section is named with the line its heading moved from and to",
                 "## A\na\n\n" + HEADING + "\n- x\n\n## B\nb\n",
                 "## A\na\n\n## B\nb\n\n" + HEADING + "\n- x\n",
                 f"it moves the section \"{HEADING}\", whose heading is on line 4 of the file at "
                 f"the merge base and on line 7 at the nc-head-commit, instead of only adding lines "
                 f"to it"),
                ("a removed heading is named the other way round",
                 "## One\n## Two\n" + HEADING + "\n- a\n",
                 "## One\n" + HEADING + "\n- a\n- b\n",
                 f"it adds, removes or changes a heading other than \"{HEADING}\": heading 2 is "
                 f"('h2', 0, '## Two') at the merge base and 'none' at the nc-head-commit")):
            problem = program.provisional_additions_only_problem(parser, base_text, head_text)
            check(name, problem == expected, problem)

        # --- a Markdown parser that cannot be loaded stops the invocation
        scratch = Scratch(root, "parser-missing")
        scratch.routes(routes_for())
        saved_module = program.MARKDOWN_PARSER_MODULE
        program.MARKDOWN_PARSER_MODULE = scratch.directory / "no-such-parser-module.py"
        try:
            code, output = scratch.run()
        finally:
            program.MARKDOWN_PARSER_MODULE = saved_module
        check("a Markdown parser that cannot be loaded stops the invocation before any approval, "
              "exit 2, and tells merge-lane-2",
              code == 2 and approvals(scratch) == [] and "could not be loaded" in output
              and "could not be loaded" in scratch.message("invocation-stopped.txt"),
              f"exit {code}\n{output}")

        # --- each failed condition is reported to merge-lane-2 once per nc-head-commit
        later_heading_base = "line 1\n" + HEADING + "\nline 3\n## Deferred-decisions\nline 5\n"
        for name, routes, why in (
                ("two-files", routes_for(files=FILE + [{"filename": "docs/issues/1-y.md",
                                                        "status": "modified"}]),
                 "changes 2 files"),
                ("outside-docs-issues", routes_for(files=[{"filename": "scripts/x.py",
                                                           "status": "modified"}]),
                 "not exactly one under docs/issues/"),
                ("removes-a-line", routes_for(file_text=PASSING_FILE_TEXT.replace("line 3\n", "")),
                 "the first line that differs is 'line 3' at the merge base and 'line 4'"),
                ("other-heading", routes_for(file_text=PASSING_FILE_TEXT + "## Another heading\n"),
                 "heading 1 is 'none' at the merge base and ('h2', 0, '## Another heading')"),
                ("new-file", routes_for(files=[dict(FILE[0], status="added")]),
                 "does not change docs/issues/9-x.md in place: GitHub calls the change \"added\""),
                ("renamed-file", routes_for(files=[dict(FILE[0], status="renamed")]),
                 "GitHub calls the change \"renamed\""),
                ("deleted-file", routes_for(files=[dict(FILE[0], status="removed")]),
                 "GitHub calls the change \"removed\""),
                ("subheading-added-inside-the-section", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- new\n", "- new\n\n### Details\n")),
                 "('h3', 0, '### Details') at the nc-head-commit"),
                ("adds-nothing", routes_for(file_text=BASE_TEXT), "does not change the file's text"),
                ("heading-missing", routes_for(file_text=PASSING_FILE_TEXT.replace(HEADING, "x")),
                 "at the nc-head-commit has the heading \"" + HEADING + "\" 0 times, not once"),
                ("addition-above-the-section", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_BASE_TEXT.replace("vetted\n", "vetted\n- an addition\n", 1)),
                 "the first line that differs is '' at the merge base and '- an addition'"),
                ("addition-under-a-later-heading", routes_for(
                    base_text=later_heading_base, file_text=later_heading_base + "- an addition\n"),
                 "'- an addition' at the nc-head-commit"),
                ("existing-section-line-changed", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- old\n", "- changed\n")),
                 "removes or changes a line of the section"),
                ("existing-section-line-removed", routes_for(
                    base_text=SECTION_HEAD_TEXT, file_text=SECTION_HEAD_TEXT.replace(
                        "- old\n", "")),
                 "removes or changes a line of the section"),
                ("heading-twice", routes_for(file_text=PASSING_FILE_TEXT + HEADING + "\n"),
                 "2 times, not once"),
                ("heading-twice-at-the-merge-base", routes_for(
                    base_text=SECTION_BASE_TEXT + HEADING + "\n",
                    file_text=SECTION_HEAD_TEXT + HEADING + "\n"),
                 "at the merge base has the heading \"" + HEADING + "\" 2 times"),
                ("heading-with-trailing-spaces", routes_for(
                    base_text=SECTION_BASE_TEXT.replace(HEADING, HEADING + "  "),
                    file_text=SECTION_HEAD_TEXT.replace(HEADING, HEADING + "  ")),
                 "0 times, not once"),
                # Markdown reads a lone carriage return as a line break, so this adds a heading.
                ("carriage-returns-in-an-added-line", routes_for(
                    file_text=PASSING_FILE_TEXT + "- new item\r## Next action\rSneaky text.\n"),
                 "at the nc-head-commit holds U+000D on line 14"),
                # A carriage return already in the merge base's section hides "## Next action" from
                # a splitter that splits on "\n" alone, so the line added beneath it would pass.
                ("carriage-return-at-the-merge-base", routes_for(
                    base_text=HEADING + "\n- old\r## Next action\n",
                    file_text=HEADING + "\n- old\r## Next action\nSneaky.\n"),
                 "at the merge base holds U+000D on line 2"),
                # Python's splitlines() splits on a form feed; git does not.
                ("form-feed-lines-before-the-section", routes_for(
                    base_text="## Problem\ntext\n" + HEADING + "\n- item\n## Next action\nmore\n",
                    file_text=("## Problem\ntext\n\x0c\n\x0c\n" + HEADING
                               + "\n- item\n## Next action\nSneaky.\nmore\n")),
                 "at the nc-head-commit holds U+000C on line 3"),
                ("indented-heading-added", routes_for(
                    base_text=HEADING + "\nprovisional\n",
                    file_text=HEADING + "\nprovisional\n   ## Next action\nSneaky.\n"),
                 "('h2', 0, '   ## Next action') at the nc-head-commit"),
                ("setext-heading-added", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_BASE_TEXT.replace("- old\n", "- old\n\nNext action\n---\n")),
                 "('h2', 0, 'Next action\\n---') at the nc-head-commit"),
                ("setext-underline-under-an-existing-line", routes_for(
                    base_text=HEADING + "\nvetted? no, provisional paragraph\n",
                    file_text=HEADING + "\nvetted? no, provisional paragraph\n===\n"),
                 "('h1', 0, 'vetted? no, provisional paragraph\\n===') at the nc-head-commit"),
                ("heading-in-a-block-quote-added", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- new\n", "- new\n> ## Next action\n")),
                 "('h2', 1, '> ## Next action') at the nc-head-commit"),
                ("open-fence-swallows-a-later-heading", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- new\n", "- new\n```\n")),
                 "('h2', 0, '## Next action') at the merge base and 'none' at the nc-head-commit"),
                # The section moves below a vetted section, so the vetted text it sat above now
                # reads as if it came before the provisional-additions.
                ("section-moved-below-a-vetted-section", routes_for(
                    base_text="## A\na\n\n" + HEADING + "\n- x\n\n## B\nb\n",
                    file_text="## A\na\n\n## B\nb\n\n" + HEADING + "\n- x\n"),
                 "it moves the section"),
                ("section-moved-with-a-line-added", routes_for(
                    base_text="## A\na\n\n" + HEADING + "\n- x\n\n## B\nb\n",
                    file_text="## A\na\n\n## B\nb\n\n" + HEADING + "\n- x\n- y\n"),
                 "it moves the section"),
                ("link-reference-definition-added", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- new\n", "- new\n\n[x]: https://example.com\n")),
                 "Markdown link reference definition"),
                # A later definition of a label already defined changes no link, but renders as
                # nothing, so a reader of the rendered issue never sees the line.
                ("link-reference-definition-repeating-a-label", routes_for(
                    base_text="See [x].\n\n[x]: https://a.example\n\n" + HEADING + "\n- a\n",
                    file_text=("See [x].\n\n[x]: https://a.example\n\n" + HEADING
                               + "\n- a\n\n[x]: https://b.example\n")),
                 "Markdown link reference definition"),
                ("link-reference-definition-in-a-list-item", routes_for(
                    base_text=SECTION_BASE_TEXT,
                    file_text=SECTION_HEAD_TEXT.replace("- new\n", "- [x]: https://example.com\n")),
                 "Markdown link reference definition"),
                ("not-utf-8", routes_for(head_bytes_hex=(PASSING_FILE_TEXT.encode() + b"\xff\n").hex()),
                 "docs/issues/9-x.md is not UTF-8")):
            scratch = Scratch(root, name)
            scratch.routes(routes)
            code, output = scratch.run()
            message_name = f"pr9-{HEAD[:12]}.txt"
            check(f"{name}: merge-lane-2 gets one message naming why, nothing is approved or "
                  f"merged, exit 0",
                  code == 0 and scratch.messages() == [message_name]
                  and why in scratch.message(message_name)
                  and "https://github.com/nedschorus/nedschorus/pull/9" in scratch.message(
                      message_name)
                  and approvals(scratch) == [] and scratch.merge_calls() == []
                  and scratch.record() == {"9": HEAD}, f"exit {code}\n{output}")
        handled = scratch.state / "needs-a-look" / "handled"
        check("the message tells merge-lane-2 to move it into needs-a-look/handled/ once read",
              f"Move this file into {handled.resolve()} as soon as you have read it"
              in scratch.message(message_name), scratch.message(message_name))
        calls_before = len(scratch.gh_calls())
        handled.mkdir()
        (scratch.state / "needs-a-look" / message_name).rename(handled / message_name)
        code, output = scratch.run()
        check("a pull request reported at its nc-head-commit, its message moved into handled/, "
              "is not read or reported again",
              code == 0 and scratch.messages() == ["handled"]
              and len(scratch.gh_calls()) == calls_before + 1
              and output == "", f"exit {code}\n{output}")
        scratch.routes(routes_for(head=NEW_HEAD, file_text=PASSING_FILE_TEXT + "## Another heading\n"))
        code, output = scratch.run()
        check("a reported pull request with a new nc-head-commit is reported again",
              code == 0 and scratch.messages() == ["handled", f"pr9-{NEW_HEAD[:12]}.txt"]
              and scratch.record() == {"9": NEW_HEAD}, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"out": "[]"}})
        code, output = scratch.run()
        check("a pull request no longer open is dropped from the record",
              code == 0 and scratch.record() == {}, f"exit {code}\n{output}")

        # --- held, draft and other titles are left alone
        scratch = Scratch(root, "held")
        scratch.state.mkdir(parents=True)
        (scratch.state / "held-pull-requests.txt").write_text("# held by merge-lane-2\n\n9\n")
        scratch.routes(routes_for(entries=[(9, "GHI-MD edit for issue 9: t", HEAD, False),
                                           (10, "GHI-MD edit for issue 10: t", HEAD, True),
                                           (11, "GHI-MD for issue 11: t", HEAD, False)]))
        code, output = scratch.run()
        check("a held pull request, a draft and another title are neither read, merged nor "
              "reported",
              code == 0 and [call["argv"][:2] for call in scratch.gh_calls()] == [["pr", "list"]]
              and scratch.messages() == [] and "9 is on the held list" in output,
              f"exit {code}\n{output}")
        (scratch.state / "held-pull-requests.txt").write_text("9\npull request 12\n")
        code, output = scratch.run()
        check("a malformed held list stops the invocation before any gh call, exit 2, and tells "
              "merge-lane-2",
              code == 2 and "line 2 of the held list" in output and len(scratch.gh_calls()) == 1
              and "line 2 of the held list" in scratch.message("invocation-stopped.txt")
              and f"Move this file into {(scratch.state / 'needs-a-look').resolve() / 'handled'} "
              "as soon as "
              in scratch.message("invocation-stopped.txt")
              and "line 2 of the held list" in scratch.message("invocation-stopped.txt")
              .splitlines()[0],
              f"exit {code}\n{output}")
        (scratch.state / "held-pull-requests.txt").unlink()
        (scratch.state / "held-pull-requests.txt").mkdir()
        code, output = scratch.run()
        check("an unreadable held list stops the invocation, exit 2",
              code == 2 and "could not read the held list" in output, f"exit {code}\n{output}")

        # --- a pull request whose nc-head-commit moves while it is read waits
        scratch = Scratch(root, "moved")
        scratch.routes(routes_for(head_after_read=NEW_HEAD))
        code, output = scratch.run()
        check("a pull request whose nc-head-commit moved while it was read is left for the next "
              "invocation, unapproved and unreported",
              code == 0 and approvals(scratch) == [] and scratch.messages() == []
              and "moved while it was read" in output, f"exit {code}\n{output}")

        # --- approval and merge failures are reported, exit 1
        scratch = Scratch(root, "approval-refused")
        scratch.routes(routes_for(review_exit=1))
        code, output = scratch.run()
        check("a refused approval is reported to merge-lane-2 with gh's error, nothing is merged, "
              "exit 1",
              code == 1 and scratch.merge_calls() == []
              and "its approval failed" in scratch.message(f"pr9-{HEAD[:12]}.txt")
              and "refused" in scratch.message(f"pr9-{HEAD[:12]}.txt"), f"exit {code}\n{output}")
        scratch = Scratch(root, "approval-without-time")
        scratch.routes(routes_for(review={"state": "APPROVED"}))
        code, output = scratch.run()
        check("an approval answer without submitted_at is reported, nothing is merged, exit 1",
              code == 1 and scratch.merge_calls() == []
              and "its approval failed" in scratch.message(f"pr9-{HEAD[:12]}.txt"),
              f"exit {code}\n{output}")
        for merge_exit, outcome in ((1, "not merged"), (2, "not merged"),
                                    (3, "merged, but a step after the merge was not done"),
                                    (4, "not merged"), (-9, "not merged")):
            scratch = Scratch(root, f"merge-exit-{merge_exit}")
            (scratch.directory / "merge.exit").write_text(str(merge_exit))
            scratch.routes(routes_for())
            code, output = scratch.run()
            message = scratch.message(f"pr9-{HEAD[:12]}.txt")
            check(f"a merge program exit {merge_exit} is reported with its last lines, exit 1",
                  code == 1 and f"exited {merge_exit}: {outcome}" in message
                  and "merge line one\nmerge line two\nmerge program last line" in message
                  and scratch.record() == {"9": HEAD}, f"exit {code}\n{output}\n{message}")

        scratch = Scratch(root, "approval-refused-then-next-merged")
        refused, passing = routes_for(review_exit=1), routes_for(number=10, head=NEW_HEAD)
        scratch.routes({**refused, **passing, "pr list": {"out": listed(
            (9, "GHI-MD edit for issue 9: t", HEAD, False),
            (10, "GHI-MD edit for issue 10: t", NEW_HEAD, False))}})
        code, output = scratch.run()
        check("a refused approval on one pull request is reported and the next pull request is "
              "still merged, exit 1",
              code == 1 and scratch.messages() == [f"pr9-{HEAD[:12]}.txt"]
              and [merge[:2] for merge in scratch.merge_calls()] == [["10", NEW_HEAD]],
              f"exit {code}\n{output}")

        scratch = Scratch(root, "unexpected-exception")
        scratch.routes(routes_for())
        saved_section = program.provisional_section

        def section_raising(*arguments):
            raise KeyError("map")
        program.provisional_section = section_raising
        try:
            code, output = scratch.run()
        finally:
            program.provisional_section = saved_section
        check("an unexpected exception stops the invocation before any approval, exit 2, prints "
              "the traceback and tells merge-lane-2 the exception's type",
              code == 2 and approvals(scratch) == [] and scratch.merge_calls() == []
              and scratch.record() is None and "Traceback" in output
              and scratch.messages() == ["invocation-stopped.txt"]
              and "KeyError: 'map'" in scratch.message("invocation-stopped.txt"),
              f"exit {code}\n{output}\n{scratch.messages()}")

        scratch = Scratch(root, "contents-fails")
        scratch.routes(routes_for(contents_exit=1))
        code, output = scratch.run()
        check("a file that cannot be read at the nc-head-commit stops the invocation before any "
              "approval, exit 2",
              code == 2 and approvals(scratch) == [] and "HTTP 404" in output,
              f"exit {code}\n{output}")

        # --- the review tools worktree is moved to origin/main
        scratch = Scratch(root, "worktree-moved")
        scratch.routes(routes_for())
        git("-C", str(scratch.checkout), "worktree", "add", "-q", "--detach",
            str(scratch.worktree), "HEAD")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m",
            "two", cwd=scratch.origin)
        code, output = scratch.run()
        worktree_head = subprocess.run(["git", "-C", str(scratch.worktree), "rev-parse", "HEAD"],
                                       capture_output=True, text=True).stdout.strip()
        origin_head = subprocess.run(["git", "-C", str(scratch.origin), "rev-parse", "HEAD"],
                                     capture_output=True, text=True).stdout.strip()
        check("an existing review tools worktree is fetched and moved to origin/main before the "
              "merge", code == 0 and worktree_head == origin_head, f"exit {code}\n{output}")
        scratch = Scratch(root, "worktree-fails")
        scratch.routes(routes_for())
        code, output = scratch.run(checkout=scratch.directory / "not-a-checkout")
        check("a review tools worktree that cannot be made stops the invocation before any "
              "approval, exit 2",
              code == 2 and approvals(scratch) == [] and "git -C" in output
              and scratch.messages() == ["invocation-stopped.txt"], f"exit {code}\n{output}")
        scratch = Scratch(root, "worktree-checkout-fails")
        scratch.routes(routes_for())
        scratch.worktree.mkdir(parents=True)
        code, output = scratch.run()
        check("a review tools worktree path that is not a git checkout stops the invocation, exit 2",
              code == 2 and approvals(scratch) == [] and "fetch" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "git-killed")
        scratch.routes(routes_for())
        (scratch.bin / "git").write_text("#!/bin/sh\nkill -9 $$\n")
        (scratch.bin / "git").chmod(0o755)
        code, output = scratch.run()
        check("a git killed by a signal stops the invocation before any approval, exit 2",
              code == 2 and approvals(scratch) == [] and "exited -9" in output,
              f"exit {code}\n{output}")

        # --- failures that stop the invocation
        scratch = Scratch(root, "list-fails")
        scratch.routes({"pr list": {"exit": 1, "err": "HTTP 502"}})
        code, output = scratch.run()
        check("a failed gh pr list stops the invocation with gh's error, exit 2, and tells "
              "merge-lane-2",
              code == 2 and "gh pr list --repo exited 1: HTTP 502" in output
              and "HTTP 502" in scratch.message("invocation-stopped.txt"), f"exit {code}\n{output}")
        scratch.routes({"pr list": {"exit": 1}})
        code, output = scratch.run()
        check("a failed gh that prints no error is named so, exit 2",
              code == 2 and "no error printed" in output, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"killed": True}})
        code, output = scratch.run()
        check("a gh killed by a signal stops the invocation, exit 2",
              code == 2 and "gh pr list --repo exited -9" in output, f"exit {code}\n{output}")
        scratch.routes({"pr list": {"out": "x" * 300}})
        code, output = scratch.run()
        check("gh output that is not JSON stops the invocation, quoting its first 200 "
              "characters, exit 2",
              code == 2 and f"gh pr list --repo printed no JSON: '{'x' * 200}'" in output,
              f"exit {code}\n{output}")
        (scratch.bin / "gh").unlink()
        code, output = scratch.run(path_only_fake_bin=True)
        check("a gh that cannot run stops the invocation, exit 2",
              code == 2 and "gh pr list --repo could not run" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "git-missing")
        scratch.routes(routes_for())
        (scratch.bin / "python3").symlink_to(sys.executable)
        code, output = scratch.run(path_only_fake_bin=True)
        check("a git that cannot run stops the invocation before any approval, exit 2",
              code == 2 and approvals(scratch) == [] and "git -C" in output
              and "could not run" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "no-token")
        (scratch.home / ".config" / "nedschorus" / "ned-review-merge.token").unlink()
        scratch.routes(routes_for())
        code, output = scratch.run()
        check("a missing token stops the invocation before any gh call, exit 2",
              code == 2 and scratch.gh_calls() == [] and "token" in output,
              f"exit {code}\n{output}")

        scratch = Scratch(root, "bad-record")
        scratch.state.mkdir(parents=True)
        (scratch.state / "reported-nc-head-commits.json").write_text('{"nine": "x"}')
        scratch.routes(routes_for())
        code, output = scratch.run()
        check("a record that is not pull request numbers to nc-head-commits stops the "
              "invocation, exit 2",
              code == 2 and "is not a JSON object" in output and scratch.gh_calls() == [],
              f"exit {code}\n{output}")
        (scratch.state / "reported-nc-head-commits.json").write_text("{")
        code, output = scratch.run()
        check("a record that is not JSON stops the invocation, exit 2",
              code == 2 and "could not read the record" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "message-unwritable")
        scratch.state.mkdir(parents=True)
        (scratch.state / "needs-a-look").write_text("a file, not a directory")
        scratch.routes(routes_for(files=[{"filename": "scripts/x.py", "status": "modified"}]))
        code, output = scratch.run()
        check("a message that cannot be written stops the invocation, records nothing, exit 2, "
              "and says the stop message could not be written either",
              code == 2 and "could not write the needs-a-look notice for merge-lane-2" in output
              and scratch.record() is None
              and "invocation-stopped.txt" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "record-unwritable")
        scratch.state.mkdir(parents=True)
        (scratch.state / "reported-nc-head-commits.json.being-written").mkdir()
        scratch.routes(routes_for(files=[{"filename": "scripts/x.py", "status": "modified"}]))
        code, output = scratch.run()
        check("a record that cannot be written stops the invocation, exit 2",
              code == 2 and "could not write the record" in output, f"exit {code}\n{output}")

        scratch = Scratch(root, "lock-held")
        scratch.state.mkdir(parents=True)
        scratch.routes(routes_for())
        with open(scratch.state / ".lock", "a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, output = scratch.run()
        check("an invocation that finds the lock held does nothing, exit 0",
              code == 0 and "another invocation holds" in output and scratch.gh_calls() == [],
              f"exit {code}\n{output}")

        scratch = Scratch(root, "lock-unopenable")
        scratch.outputs.mkdir()
        scratch.state.write_text("a file, not a directory")
        code, output = scratch.run()
        check("a lock that cannot be opened stops the invocation, exit 2",
              code == 2 and "could not open the lock" in output, f"exit {code}\n{output}")
        scratch = Scratch(root, "lock-is-a-directory")
        (scratch.state / ".lock").mkdir(parents=True)
        code, output = scratch.run()
        check("a lock that cannot be opened is reported to merge-lane-2 in "
              "invocation-stopped.txt, exit 2",
              code == 2 and scratch.gh_calls() == []
              and "could not open the lock" in scratch.message("invocation-stopped.txt"),
              f"exit {code}\n{output}\n{scratch.messages()}")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
