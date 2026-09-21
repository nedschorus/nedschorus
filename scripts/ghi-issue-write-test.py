#!/usr/bin/env python3
"""Tests for scripts/ghi-issue-write.py, the GHI write tool's create and
edit verbs.

Run: python3 scripts/ghi-issue-write-test.py
Prints one line per case and exits non-zero if any case fails.

NOTHING HERE TOUCHES GITHUB. The tool makes every subprocess call through one
function, and each case passes in a fake that records the calls and returns
canned output. So a case asserts what the tool WOULD run, in order, which is
what the design's promises are about: that a rerun never files a second
issue, that a body is not linked to a file which is not on main, that a
refusal writes nothing.

The git parts of step 4 are exercised against the recorder too rather than a
throwaway repository. The reason is that step 4's promise is not "git works"
— it is "this sequence of commands, in this order, and not twice". A real
repository would test git and hide the ordering.

What that leaves to the author: a recorder answers whatever the case tells
it to, including a state no real run could be in, and a case built on one
passes without exercising anything. It happened here — see the happy path
below. So each state a case encodes was produced once against a real
repository, with a bare remote and `gh` stubbed, before being written down:
filed, merged, head branch deleted, source moved, pushed without a pull
request, and a destination holding a file that is not this one.
"""

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
TOOL = __import__("importlib").import_module("importlib.util")
spec = TOOL.spec_from_file_location(
    "ghi_issue_write", Path(__file__).resolve().with_name("ghi-issue-write.py"))
tool = TOOL.module_from_spec(spec)
spec.loader.exec_module(tool)

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


class Recorder:
    """Stands in for every subprocess the tool makes.

    Answers are matched as a SUBSTRING of the whole command, not as a
    prefix. Prefix matching looked right and was not: the tool invokes the
    adjudication script through sys.executable, an absolute path, so a
    "python" key matched nothing and every adjudication case got the default
    empty answer instead. Two cases failed loudly and three — the fail-open
    ones — passed for the wrong reason, because an unmatched call returns a
    reply with no verdict line, which is itself a pass condition."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, arguments, timeout=None, cwd=None, check=True):
        self.calls.append(list(arguments))
        for prefix, answer in self.answers.items():
            if prefix in " ".join(arguments):
                if isinstance(answer, Exception):
                    raise answer
                return answer
        return Completed()

    def commands(self):
        """Each call reduced to its first three words, which is enough to say
        what happened and immune to argument churn."""
        return [" ".join(call[:3]) for call in self.calls]

    def ran(self, fragment):
        return any(fragment in " ".join(call) for call in self.calls)

    def count(self, fragment):
        return sum(1 for call in self.calls if fragment in " ".join(call))


FILE_TEXT = "---\nstatus: draft\n---\n\n# A statusline that drops its branch name\n\nBody.\n"
REPO = "nedschorus/nedschorus"
ASK = "ghi-info-ask.py"   # how a case names the adjudication call


def written(scratch: Path, name="statusline-drops-branch.md", text=FILE_TEXT):
    path = scratch / name
    path.write_text(text, encoding="utf-8")
    return path


def quiet(_line):
    pass


def run_cases(scratch: Path):
    # --- The pure parts, which decide the title, the slug and the key ----

    check("frontmatter is skipped and the first heading becomes the title",
          tool.first_heading(FILE_TEXT) == "A statusline that drops its branch name",
          repr(tool.first_heading(FILE_TEXT)))
    check("a file that opens with its heading works too",
          tool.first_heading("# Plain\n\nBody.\n") == "Plain")
    check("an unterminated frontmatter block does not swallow the heading",
          tool.first_heading("---\nstatus: draft\n\n# Still found\n") == "Still found",
          repr(tool.first_heading("---\nstatus: draft\n\n# Still found\n")))
    check("a file with no heading yields none, and is refused later",
          tool.first_heading("no heading here\n") == "")
    check("the slug is bounded and hyphenated",
          tool.slug("A statusline that drops its branch name")
          == "a-statusline-that-drops-its-branch-name")
    check("the pairing key follows the content, not the name",
          tool.pairing_key(FILE_TEXT) == tool.pairing_key(FILE_TEXT)
          and tool.pairing_key(FILE_TEXT) != tool.pairing_key(FILE_TEXT + "x"))
    check("the placeholder body carries the key, so a rerun can find it",
          tool.pairing_key(FILE_TEXT) in tool.placeholder_body(tool.pairing_key(FILE_TEXT)))
    check("the body is links and nothing else, in filename order",
          tool.links_body(REPO, ["docs/issues/9-b.md", "docs/issues/9-a.md"])
          == ("- [9-a.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/9-a.md)\n"
              "- [9-b.md](https://github.com/nedschorus/nedschorus/blob/main/docs/issues/9-b.md)"),
          repr(tool.links_body(REPO, ["docs/issues/9-b.md", "docs/issues/9-a.md"])))

    # --- What the caller is refused for, before anything is written ------

    for case_name, path_or_text, expected in [
            ("a missing file is refused", scratch / "absent.md", 64),
            ("a file with no heading is refused", "no heading here\n", 64),
            ("an empty file is refused", "   \n", 64)]:
        path = (path_or_text if isinstance(path_or_text, Path)
                else written(scratch, "refused.md", path_or_text))
        try:
            tool.validate(path)
            check(case_name, False, "it was accepted")
        except tool.Refused as refusal:
            check(case_name, refusal.code == expected, f"code {refusal.code}")

    already = written(scratch, "570-already-paired.md", "# Paired\n")
    try:
        tool.validate(already)
        check("a file already named for an issue is refused", False, "accepted")
    except tool.Refused as refusal:
        check("a file already named for an issue is refused",
              refusal.code == 64, f"code {refusal.code}")

    # --- The happy path, which takes two runs ---------------------------
    # One run cannot both find its file on main and have something to
    # commit, and until 2026-09-21 this case answered `git ls-tree` with the
    # file already on main AND let `git commit` succeed. Nothing after the
    # merge was exercised, and two deaths there went uncaught. So the happy
    # path is two runs: the first files and opens the pull request, the
    # second is the rerun after merge-lane merges and deletes the branch.

    source = written(scratch)
    KEY = tool.pairing_key(FILE_TEXT)
    TITLE = "A statusline that drops its branch name"
    STAGED = tool.with_issue_frontmatter(FILE_TEXT, REPO, 570, TITLE)
    LANDED = "docs/issues/570-a-statusline-that-drops-its-branch-name.md"
    PLACEHOLDER = ('[{"number": 570, "title": "t", "body": "in progress '
                   + KEY + '"}]')

    first = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("https://github.com/x/y/pull/9\n"),
    })
    number, finished = tool.create(source, REPO, scratch, first, quiet)
    check("the issue is filed once and its number is read from gh's output",
          number == 570 and first.count("gh issue create") == 1,
          f"number {number}, {first.count('gh issue create')} create call(s)")
    check("the first run stops short of the body, its file not being on main",
          finished is False and not first.ran("gh issue edit"),
          str(first.commands()))
    check("the title comes from the file, not the caller",
          any(TITLE in " ".join(call) for call in first.calls
              if call[:3] == ["gh", "issue", "create"]))
    check("main is fetched before the commit is made",
          first.commands().index("git fetch origin")
          < first.commands().index("git worktree add"),
          str(first.commands()))
    check("the worktree is detached, so the run makes no branch to leave",
          first.ran("git worktree add --quiet --detach")
          and not any("-b" in call for call in first.calls
                      if call[:3] == ["git", "worktree", "add"]),
          str(first.calls))
    check("and the push names the branch as a refspec instead",
          first.ran("git push --quiet origin "
                    "HEAD:refs/heads/ghi-570-a-statusline"),
          str(first.commands()))
    check("the worktree is removed even though the run succeeded",
          first.ran("git worktree remove"), str(first.commands()))

    second = Recorder({
        "gh issue list": Completed(PLACEHOLDER),
        "git show": Completed(STAGED),
        "git ls-tree": Completed(LANDED + "\n"),
    })
    number, finished = tool.create(source, REPO, scratch, second, quiet)
    check("the rerun after the merge writes the body the first run could not",
          number == 570 and finished is True
          and any(call[:3] == ["gh", "issue", "edit"]
                  and "blob/main/docs/issues/570-" in " ".join(call)
                  and tool.PAIRING_KEY_PREFIX not in " ".join(call)
                  for call in second.calls),
          str(second.commands()))
    check("and it files no second issue",
          second.count("gh issue create") == 0, str(second.commands()))
    check("the rerun asks main, not the branch, so a deleted head branch "
          "stops nothing",
          not second.ran("git ls-remote")
          and not second.ran("git worktree add")
          and not second.ran("git commit")
          and not second.ran("gh pr create"), str(second.commands()))

    stale = Recorder({
        "gh issue list": Completed(PLACEHOLDER),
        "git show": Completed("---\nissue: [x](https://example.invalid/1)\n"
                              "---\n\n# Someone else's file\n"),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(LANDED + "\n"),
        "gh pr create": Completed("pr\n"),
    })
    tool.create(source, REPO, scratch, stale, quiet)
    check("a different file at the destination is not mistaken for this one",
          stale.ran("git worktree add"), str(stale.commands()))

    # --- The issue line the tool writes into the file's frontmatter ------
    # The author writes the file before the issue exists, so the file cannot
    # name its issue when written. The tool derives the line instead, which
    # is why none of these cases asks an author to have got it right.

    line = tool.issue_frontmatter_line(REPO, 570, "A title")
    check("the issue line cites by title and link, never a bare number",
          line == "issue: [A title](https://github.com/nedschorus/nedschorus/issues/570)",
          repr(line))

    for case_name, source_text, expectation in [
            ("a file with frontmatter gains the line and keeps its own keys",
             "---\nstatus: draft\n---\n\n# T\n",
             lambda out: line in out and "status: draft" in out),
            ("a file with no frontmatter gains a block",
             "# T\n\nBody.\n",
             lambda out: out.startswith("---\n" + line) and "# T" in out),
            ("an existing issue line is replaced, not duplicated",
             "---\nissue: [old](https://example.invalid/1)\nstatus: d\n---\n\n# T\n",
             lambda out: out.count("issue:") == 1 and line in out
             and "example.invalid" not in out),
            ("an unterminated block is not mistaken for frontmatter",
             "---\nstatus: draft\n\n# T\n",
             lambda out: out.startswith("---\n" + line) and "# T" in out)]:
        produced = tool.with_issue_frontmatter(source_text, REPO, 570, "A title")
        check(case_name, expectation(produced), repr(produced[:120]))
        check(f"  and running it again changes nothing ({case_name[:28]})",
              tool.with_issue_frontmatter(produced, REPO, 570, "A title")
              == produced)

    class Reader(Recorder):
        """Reads the file the tool staged, at the moment it stages it: the
        throwaway worktree is gone by the time the run returns."""

        def __init__(self, answers, worktree_holder):
            super().__init__(answers)
            self.staged = None
            self.holder = worktree_holder

        def __call__(self, arguments, timeout=None, cwd=None, check=True):
            if arguments[:2] == ["git", "add"] and cwd:
                candidate = Path(cwd) / arguments[2]
                if candidate.is_file():
                    self.staged = candidate.read_text(encoding="utf-8")
            return super().__call__(arguments, timeout, cwd, check)

    source = written(scratch, "for-frontmatter.md")
    reader = Reader({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree -r --name-only origin/main docs/issues/": Completed(
            "docs/issues/570-a.md\n"),
        "gh pr create": Completed("pr\n"),
    }, None)
    tool.create(source, REPO, scratch, reader, quiet)
    check("the file that lands carries the issue line the tool derived",
          reader.staged is not None
          and tool.issue_frontmatter_line(REPO, 570,
                                          "A statusline that drops its branch name")
          in reader.staged,
          repr((reader.staged or "")[:140]))
    check("and the author's own text is untouched beneath it",
          reader.staged is not None and "status: draft" in reader.staged
          and "Body." in reader.staged, repr((reader.staged or "")[:140]))

    # --- Step 4 is a move, not a copy -------------------------------------

    tracked = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree -r --name-only origin/main docs/issues/": Completed(""),
        "git ls-tree": Completed("for-frontmatter.md\n"),
        "gh pr create": Completed("pr\n"),
    })
    tool.create(source, REPO, scratch, tracked, quiet)
    check("a source already on main is removed in the same commit",
          tracked.ran("git rm"), str(tracked.commands()))

    untracked = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    tool.create(source, REPO, scratch, untracked, quiet)
    check("a source that is not on main is not removed",
          not untracked.ran("git rm"), str(untracked.commands()))

    # --- Resuming: the property the design promises -----------------------

    resumed = Recorder({
        "gh issue list": Completed(PLACEHOLDER),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed("docs/issues/570-a.md\n"),
        "gh pr create": Completed("pr\n"),
    })
    tool.create(source, REPO, scratch, resumed, quiet)
    check("a rerun never files a second issue for one file",
          resumed.count("gh issue create") == 0, str(resumed.commands()))
    check("and it does not ask ghi-info again either",
          not resumed.ran(ASK), str(resumed.commands()))

    open_branch = Recorder({
        "gh issue list": Completed(PLACEHOLDER),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-a\n"),
        "gh pr list": Completed(
            '[{"number": 9, "title": "GHI-MD for issue 570", '
            '"url": "https://github.com/x/y/pull/9"}]'),
        "git ls-tree": Completed(""),
    })
    tool.create(source, REPO, scratch, open_branch, quiet)
    check("a branch whose pull request is open is not pushed a second time",
          not open_branch.ran("git worktree add")
          and not open_branch.ran("gh pr create"),
          str(open_branch.commands()))
    check("and while its file is not on main the body keeps its placeholder",
          not open_branch.ran("gh issue edit"), str(open_branch.commands()))

    # A push that succeeded and a `gh pr create` that then failed leaves
    # this state. Reported as a pull request waiting for merge-lane, it
    # would be reported that way forever, because nothing else opens one.
    pushed_only = Recorder({
        "gh issue list": Completed(PLACEHOLDER),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-a\n"),
        "gh pr list": Completed("[]"),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("https://github.com/x/y/pull/10\n"),
    })
    tool.create(source, REPO, scratch, pushed_only, quiet)
    check("a branch pushed without a pull request gets one on the rerun",
          pushed_only.ran("gh pr create"), str(pushed_only.commands()))
    check("and nothing is committed or pushed over it to get there",
          not pushed_only.ran("git worktree add")
          and not pushed_only.ran("git push"), str(pushed_only.commands()))

    unlanded = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/571\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    _, done = tool.create(source, REPO, scratch, unlanded, quiet)
    check("a body is never linked to a file that is not on main",
          done is False and not unlanded.ran("gh issue edit"),
          str(unlanded.commands()))

    # --- After the merge, when filing moved the source --------------------
    # Step 4 moves a source that was already tracked on main, so the merge
    # takes that path off main and the author's pull takes it off disk. The
    # file that exists then is the landed one, and it is the entry point.

    landed = written(scratch, "570-a-statusline-that-drops-its-branch-name.md",
                     STAGED)
    moved = Recorder({
        "gh issue view": Completed('{"body": "in progress ' + KEY + '"}'),
        "git ls-tree": Completed(LANDED + "\n"),
    })
    number, finished = tool.create(landed, REPO, scratch, moved, quiet)
    check("the landed file finishes the run its moved source cannot",
          number == 570 and finished is True and moved.ran("gh issue edit"),
          str(moved.commands()))
    check("and that entry files nothing and lands nothing",
          moved.count("gh issue create") == 0
          and not moved.ran("git worktree add")
          and not moved.ran("gh pr create"), str(moved.commands()))

    filed_already = Recorder({
        "gh issue view": Completed(
            '{"body": "- [570-a.md](https://github.com/x/y/blob/main/x.md)"}'),
    })
    try:
        tool.create(landed, REPO, scratch, filed_already, quiet)
        check("a paired file whose filing finished is still refused", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a paired file whose filing finished is still refused",
              refusal.code == 64 and not filed_already.ran("gh issue edit"),
              f"code {refusal.code}, {filed_already.commands()}")

    # The move takes the source's directory too when it held nothing else,
    # and git asked from a directory that is gone raises rather than
    # answering. Driven through main(), which is where the checkout is
    # looked for; it reaches neither git nor gh.
    complaint = io.StringIO()
    with contextlib.redirect_stderr(complaint):
        code = tool.main(["create", str(scratch / "gone" / "statusline.md"),
                          "--repo", REPO])
    check("a source whose directory the move took is refused, not a crash",
          code == 64 and "no such file" in complaint.getvalue(),
          f"code {code}, {complaint.getvalue()!r}")

    absent = Recorder({"gh issue view": Completed('{"body": "x ghipairff"}')})
    try:
        tool.create(scratch / "999-not-on-disk.md", REPO, scratch, absent,
                    quiet)
        check("a paired path with no file is refused for the file", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a paired path with no file is refused for the file",
              refusal.code == 64 and not absent.ran("gh issue view"),
              f"code {refusal.code}, {absent.commands()}")

    # --- Adjudication: refuses, fails open, and the reconsider marker -----

    ask = scratch / "scripts" / "ghi-info-ask.py"
    ask.parent.mkdir(exist_ok=True)
    ask.write_text("# stands in for the real one; never executed\n")

    refusing = Recorder({ASK: Completed("verdict: too-similar #13\n")})
    try:
        tool.adjudicate(REPO, "t", FILE_TEXT, scratch, refusing, quiet)
        check("a too-similar verdict refuses the write", False, "it proceeded")
    except tool.Refused as refusal:
        check("a too-similar verdict refuses the write",
              refusal.code == 65 and "#13" in str(refusal), str(refusal))
        check("and the refusal ends with the reconsider line",
              tool.RECONSIDER_LINE in str(refusal))

    for case_name, answers in [
            ("ghi-info answering nothing lets the write proceed",
             {ASK: Completed("", returncode=1)}),
            ("a reply with no verdict line lets the write proceed",
             {ASK: Completed("I could not tell.\n")}),
            ("ghi-info raising lets the write proceed",
             {ASK: RuntimeError("box unreachable")})]:
        try:
            tool.adjudicate(REPO, "t", FILE_TEXT, scratch, Recorder(answers),
                            quiet)
            check(case_name, True)
        except tool.Refused as refusal:
            check(case_name, False, f"refused: {refusal}")

    marker = scratch / tool.RECONSIDERED_MARKER_NAME
    marker.write_text("I checked #13 and it is a different matter.\n")
    passed = Recorder({ASK: Completed("verdict: too-similar #13\n")})
    tool.adjudicate(REPO, "t", FILE_TEXT, scratch, passed, quiet)
    check("the reconsidered marker passes one write",
          not passed.ran(ASK), str(passed.commands()))
    check("and is consumed by it, so it cannot pass a second",
          not marker.exists())

    # --- The refusal that must not leave a half-made issue ----------------

    nothing_written = Recorder({ASK: Completed("verdict: too-similar #13\n")})
    try:
        tool.create(written(scratch, "refused-create.md"), REPO, scratch,
                    nothing_written, quiet)
        check("a refused create writes nothing at all", False, "it proceeded")
    except tool.Refused:
        check("a refused create writes nothing at all",
              not nothing_written.ran("gh issue create")
              and not nothing_written.ran("git worktree add")
              and not nothing_written.ran("gh issue edit"),
              str(nothing_written.commands()))


# --- The edit verb ------------------------------------------------------
#
# Same fake-subprocess method as the create cases: each case asserts what
# the tool WOULD run. Edit adds two commands create never makes — `git
# merge-base` and `git show`, which are how the conflict check reads the
# version the author's checkout started from and the version main holds —
# so several cases are about which of those ran, and in which order.

EDIT_NAME = "570-a-statusline-that-drops-its-branch-name.md"
EDIT_RELATIVE = f"docs/issues/{EDIT_NAME}"
MOVED_RELATIVE = f"nc-systems/statusline/{EDIT_NAME}"
EDIT_TITLE = "A statusline that drops its branch name"
BASE_REVISION = "basesha1234"


def paired(scratch: Path, name=EDIT_NAME, text=FILE_TEXT,
           directory="docs/issues"):
    """A file where a paired file lives, which is where edit insists on
    finding one."""
    holder = scratch / directory
    holder.mkdir(parents=True, exist_ok=True)
    target = holder / name
    target.write_text(text, encoding="utf-8")
    return target


def staged_form(number=570, title=EDIT_TITLE, text=FILE_TEXT):
    """What the tool lands: the author's file with the issue line it
    derives. Every comparison the edit verb makes is against this, not
    against the author's text, or a file whose only difference was the line
    the tool itself writes would land over and over."""
    return tool.with_issue_frontmatter(text, REPO, number, title)


def issue_json(title, body):
    return Completed(json.dumps({"title": title, "body": body}))


def ran_with(recorder, *fragments):
    return any(all(fragment in " ".join(call) for fragment in fragments)
               for call in recorder.calls)


def run_edit_cases(scratch: Path):
    ask = scratch / "scripts" / "ghi-info-ask.py"
    ask.parent.mkdir(parents=True, exist_ok=True)
    ask.write_text("# stands in for the real one; never executed\n")

    staged = staged_form()
    one_link = tool.links_body(REPO, [EDIT_RELATIVE])

    # --- Where a paired file may be, and what makes it paired ------------

    check("a paired file under docs/issues/ is where it belongs",
          tool.writable_relative_path(EDIT_RELATIVE))
    check("so is one under its system's own directory",
          tool.writable_relative_path(
              "nc-systems/main-gatekeeper/570-contract.md"))
    check("a file loose in the system tree is not",
          not tool.writable_relative_path("nc-systems/570-contract.md"))
    check("and neither is one somewhere else entirely",
          not tool.writable_relative_path("docs/drafts/570-contract.md"))

    text, title, number, relative = tool.validate_edit(
        paired(scratch), scratch)
    check("the issue number comes from the file's name",
          number == 570 and relative == EDIT_RELATIVE and title == EDIT_TITLE,
          f"{number} {relative} {title!r}")

    check("a paired file in its system's directory validates too",
          tool.validate_edit(
              paired(scratch, name="570-contract.md",
                     directory="nc-systems/statusline"), scratch)[2] == 570)

    for case_name, target in [
            ("a file not named for an issue is refused",
             paired(scratch, name="notes.md")),
            ("a paired file outside the writable paths is refused",
             paired(scratch, directory="docs/drafts")),
            ("a paired file with no heading is refused",
             paired(scratch, name="571-no-heading.md", text="no heading\n")),
            ("a missing file is refused", scratch / "docs" / "absent.md")]:
        try:
            tool.validate_edit(target, scratch)
            check(case_name, False, "it was accepted")
        except tool.Refused as refusal:
            check(case_name, refusal.code == 64, f"code {refusal.code}")

    # --- Which bodies this tool may overwrite ----------------------------

    check("a link list is a body the tool wrote", tool.is_derived_body(one_link))
    check("so is the placeholder create leaves between its steps",
          tool.is_derived_body(tool.placeholder_body(tool.pairing_key(FILE_TEXT))))
    check("an empty body is not prose to protect", tool.is_derived_body(""))
    check("prose is not a body the tool wrote",
          not tool.is_derived_body("This issue is about the statusline.\n"))
    check("and neither is a link list with a sentence added to it",
          not tool.is_derived_body(one_link + "\nAlso see the design.\n"))
    check("a body is compared without the newline gh adds to it",
          tool.normalized("a\r\nb\n\n") == "a\nb")

    # --- The body reaches files that moved into their system's directory -

    listing = Recorder({"git ls-tree": Completed(
        "docs/issues/570-design.md\n"
        "nc-systems/statusline/570-contract.md\n"
        "docs/issues/5700-unrelated.md\n"
        "docs/issues/571-another.md\n")})
    check("the file set spans docs/issues/ and the system directories",
          tool.paired_paths(570, scratch, listing)
          == ["docs/issues/570-design.md",
              "nc-systems/statusline/570-contract.md"],
          str(tool.paired_paths(570, scratch, listing)))
    check("and git is asked for both of them, not just the one",
          ran_with(listing, "git ls-tree", "docs/issues/", "nc-systems/"),
          str(listing.calls))

    # --- The happy path: the file differs from main, so it lands ---------

    source = paired(scratch)
    landing = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("https://github.com/x/y/pull/11\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    edited_number, finished = tool.edit(source, REPO, scratch, landing, quiet)
    check("the edit lands the file on a pull request of its own",
          edited_number == 570 and landing.ran("git worktree add")
          and landing.ran("gh pr create"), str(landing.commands()))
    check("an edit never files an issue",
          not landing.ran("gh issue create"), str(landing.commands()))
    check("the branch is named for this edit's content, not for the issue "
          "alone",
          ran_with(landing, "gh pr create", f"ghi-570-edit-{tool.pairing_key(staged)}"),
          str(landing.commands()))
    check("the worktree is detached, so the run makes no branch to leave",
          landing.ran("git worktree add --quiet --detach")
          and not any("-b" in call for call in landing.calls
                      if call[:3] == ["git", "worktree", "add"]),
          str(landing.calls))
    check("and the push names the branch as a refspec instead",
          landing.ran("git push --quiet origin HEAD:refs/heads/"
                      f"ghi-570-edit-{tool.pairing_key(staged)}"),
          str(landing.commands()))
    check("an edit in place removes nothing from main",
          not landing.ran("git rm"), str(landing.commands()))
    check("main is fetched before anything is compared against it",
          landing.commands().index("git fetch origin")
          < landing.commands().index(f"git show origin/main:{EDIT_RELATIVE}"),
          str(landing.commands()))
    check("the run is unfinished while its pull request waits", not finished)
    check("a heading the edit did change renames the issue",
          ran_with(landing, "gh issue edit", "--title", EDIT_TITLE),
          str(landing.commands()))
    check("the worktree is removed even though the run succeeded",
          landing.ran("git worktree remove"), str(landing.commands()))
    check("the question to ghi-info says which issue to leave out",
          ran_with(landing, "ghi-info-ask.py", "edit of issue #570",
                   "leave that issue out"), "the ask carried no exclusion")

    class Reader(Recorder):
        """Reads the file the tool staged at the moment it stages it: the
        throwaway worktree is gone by the time the run returns."""

        def __init__(self, answers):
            super().__init__(answers)
            self.staged = None

        def __call__(self, arguments, timeout=None, cwd=None, check=True):
            if arguments[:2] == ["git", "add"] and cwd:
                candidate = Path(cwd) / arguments[2]
                if candidate.is_file():
                    self.staged = candidate.read_text(encoding="utf-8")
            return super().__call__(arguments, timeout, cwd, check)

    reader = Reader({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(source, REPO, scratch, reader, quiet)
    check("the file that lands is the author's, at its own path, carrying "
          "the issue line",
          reader.staged == staged, repr((reader.staged or "")[:140]))

    # --- A file the author moved into its system's directory -------------
    # The move § Where the tool may write allows: out of docs/issues/ once
    # the system's code starts. Main still holds the file where it was, and
    # a commit that only adds the new path leaves the document at two paths
    # the moment it merges — after which paired_paths returns both and step
    # 5 links the same document twice.

    moved_source = paired(scratch, directory="nc-systems/statusline")
    moved = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("", returncode=1),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{MOVED_RELATIVE}": Completed(
            "", returncode=1),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + "\ndocs/issues/570-test-design.md\n"),
    })
    tool.edit(moved_source, REPO, scratch, moved, quiet)
    check("a moved file is added at its new path",
          ran_with(moved, "git add", MOVED_RELATIVE), str(moved.commands()))
    check("and the copy main still holds is removed in the same commit, "
          "so the merge leaves one document and not two",
          ran_with(moved, "git rm", EDIT_RELATIVE)
          and moved.commands().index("git rm --quiet")
          < moved.commands().index("git commit --quiet"),
          str(moved.commands()))
    check("while the issue's other paired file, which this edit did not "
          "move, is left where it is",
          not ran_with(moved, "git rm", "570-test-design.md"),
          str(moved.calls))

    # A same-named copy in the other directory, while this run's own file
    # is where main has it, is not a move: it is an edit in place, and that
    # copy is not this edit's to delete.

    in_place = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + f"\n{MOVED_RELATIVE}\n"),
    })
    tool.edit(source, REPO, scratch, in_place, quiet)
    check("an edit in place removes no copy of itself from elsewhere on "
          "main, however that copy got there",
          not in_place.ran("git rm"), str(in_place.commands()))

    # --- The conflict the 2026-09-08 ruling is about ---------------------

    conflicted = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Theirs\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git diff": Completed("@@\n-# Older\n+# Theirs\n"),
        "git ls-remote": Completed(""),
    })
    try:
        tool.edit(source, REPO, scratch, conflicted, quiet)
        check("a file that moved on main refuses the edit", False,
              "it proceeded")
    except tool.Refused as refusal:
        check("a file that moved on main refuses the edit",
              refusal.code == 66, f"code {refusal.code}")
        check("and the refusal shows the change it would have discarded",
              "+# Theirs" in str(refusal), str(refusal)[:200])
        check("and tells the caller to bring the checkout up to date, "
              "which is what actually clears it",
              "merge or rebase onto origin/main" in str(refusal),
              str(refusal)[:300])
        check("and does not promise the marker can pass it, which it "
              "cannot — adjudication consumes the marker first",
              tool.RECONSIDER_LINE not in str(refusal), str(refusal)[:300])
    check("a refused edit writes nothing at all",
          not conflicted.ran("git worktree add")
          and not conflicted.ran("gh pr create")
          and not conflicted.ran("gh issue edit"),
          str(conflicted.commands()))

    # --- Resuming after the pull request merged --------------------------
    # The author's own landed change is a difference between the merge base
    # and main, so a conflict check made first would refuse them their own
    # edit. Main's copy is compared to theirs before any of that.

    resumed = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(staged),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "gh issue view": issue_json("Stale title", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    done, wrongly_refused = False, None
    try:
        _, done = tool.edit(source, REPO, scratch, resumed, quiet)
    except tool.Refused as refusal:
        wrongly_refused = refusal
    check("a rerun after the merge is not refused as a conflict with itself",
          wrongly_refused is None and done
          and not resumed.ran("git merge-base"),
          f"refused: {str(wrongly_refused)[:120]}" if wrongly_refused
          else str(resumed.commands()))
    check("and it opens no second pull request",
          not resumed.ran("git worktree add")
          and not resumed.ran("gh pr create"), str(resumed.commands()))
    check("a heading the edit did not change leaves the title alone, "
          "however far the title is from it",
          not ran_with(resumed, "gh issue edit", "--title"),
          str(resumed.commands()))
    check("and the rerun does not spend a model call asking ghi-info again",
          not resumed.ran(ASK), str(resumed.commands()))

    # --- The pull request is already open --------------------------------

    waiting = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-edit-x\n"),
        "gh pr list": Completed(
            '[{"number": 11, "title": "GHI-MD edit for issue 570", '
            '"url": "https://github.com/x/y/pull/11"}]'),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    _, still_waiting = tool.edit(source, REPO, scratch, waiting, quiet)
    check("a branch already on the remote is not pushed a second time",
          not waiting.ran("git worktree add")
          and not waiting.ran("gh pr create"), str(waiting.commands()))
    check("and the pull request it reports is one GitHub says is open, not "
          "one inferred from the branch being there",
          waiting.ran("gh pr list"), str(waiting.commands()))
    check("and the run says it is not finished", not still_waiting)

    # A push that succeeded and a `gh pr create` that then failed leaves
    # this state. Reported as a pull request waiting for merge-lane, it
    # would be reported that way forever, because nothing else opens one.

    pushed_only = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-edit-x\n"),
        "gh pr list": Completed("[]"),
        "gh pr create": Completed("https://github.com/x/y/pull/12\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(source, REPO, scratch, pushed_only, quiet)
    check("a branch pushed without a pull request gets one on the rerun",
          pushed_only.ran("gh pr create"), str(pushed_only.commands()))
    check("and nothing is committed or pushed over it to get there",
          not pushed_only.ran("git worktree add")
          and not pushed_only.ran("git push"), str(pushed_only.commands()))
    check("and the pull request it opens is the edit's own, not a filing's",
          ran_with(pushed_only, "gh pr create",
                   f"GHI-MD edit for issue 570: {EDIT_TITLE}",
                   "An edit to the GHI-MD for issue #570"),
          str(pushed_only.calls))

    # --- The body is rewritten only when the file set changed ------------

    unchanged = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(staged),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(source, REPO, scratch, unchanged, quiet)
    check("a body that already lists the files is left alone",
          not ran_with(unchanged, "gh issue edit", "--body"),
          str(unchanged.commands()))
    check("and so is a title that already matches",
          not ran_with(unchanged, "gh issue edit", "--title"),
          str(unchanged.commands()))

    added = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(staged),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + "\nnc-systems/statusline/570-contract.md\n"),
    })
    tool.edit(source, REPO, scratch, added, quiet)
    check("a file added to the issue is relinked into the body",
          ran_with(added, "gh issue edit", "--body", "570-contract.md",
                   EDIT_NAME), str(added.commands()))

    several = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("An issue with several documents",
                                    one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + "\ndocs/issues/570-test-design.md\n"),
    })
    tool.edit(source, REPO, scratch, several, quiet)
    check("an issue with several paired files is not renamed after one of "
          "them, even when that one's heading changed",
          not ran_with(several, "gh issue edit", "--title"),
          str(several.commands()))

    # --- A body nobody has migrated yet ----------------------------------

    prose = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(staged),
        "gh issue view": issue_json(
            EDIT_TITLE, "The statusline drops its branch name after a "
                        "rebase. Reproduced twice."),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    prose_refusal, prose_finished = None, False
    try:
        _, prose_finished = tool.edit(source, REPO, scratch, prose, quiet)
    except tool.Refused as refusal:
        prose_refusal = refusal
    check("an unmigrated prose body is left as it stands, not overwritten",
          not ran_with(prose, "gh issue edit", "--body"),
          str(prose.commands()))
    check("and not refused either, since every paired issue on main is in "
          "that state and a refusal would shut the verb out of all of them",
          prose_refusal is None and prose_finished,
          f"refused: {str(prose_refusal)[:120]}" if prose_refusal
          else "the run did not report itself finished")

    # --- The file is not on main at all ----------------------------------

    absent = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("", returncode=1),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    _, not_yet = tool.edit(source, REPO, scratch, absent, quiet)
    check("a file that is not on main lands, and the issue waits for it",
          absent.ran("gh pr create") and not not_yet
          and not absent.ran("gh issue edit"), str(absent.commands()))

    # --- Adjudication, in the shape the design gives for an edit ---------

    refusing = Recorder({ASK: Completed("verdict: too-similar #13\n")})
    try:
        tool.adjudicate(REPO, "t", FILE_TEXT, scratch, refusing, quiet,
                        exclude_issue=570)
        check("a too-similar verdict refuses an edit too", False,
              "it proceeded")
    except tool.Refused as refusal:
        check("a too-similar verdict refuses an edit too",
              refusal.code == 65 and "#13 already covers this ground"
              in str(refusal), str(refusal)[:160])
        check("and an edit's refusal says what becomes of the issue being "
              "edited",
              "#570, the issue you were editing" in str(refusal)
              and "Superseded-by: #13" in str(refusal), str(refusal))

    creating = Recorder({ASK: Completed("verdict: too-similar #13\n")})
    try:
        tool.adjudicate(REPO, "t", FILE_TEXT, scratch, creating, quiet)
        check("a create's refusal carries no such paragraph", False,
              "it proceeded")
    except tool.Refused as refusal:
        check("a create's refusal carries no such paragraph",
              "Superseded-by" not in str(refusal), str(refusal))


def main():
    import tempfile
    with tempfile.TemporaryDirectory(prefix="ghi-issue-write-test-") as name:
        run_cases(Path(name))
    # A checkout of its own: the reconsidered marker lives at the root of
    # one and is consumed by the write it passes, so two groups sharing a
    # directory would share that.
    with tempfile.TemporaryDirectory(prefix="ghi-issue-edit-test-") as name:
        run_edit_cases(Path(name))
    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
