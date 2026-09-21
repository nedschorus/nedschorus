#!/usr/bin/env python3
"""Tests for scripts/ghi-issue-write.py, the GHI write tool's create verb.

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
"""

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

    # --- The happy path: one issue, one branch, one body -----------------

    source = written(scratch)
    recorder = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(
            "docs/issues/570-a-statusline-that-drops-its-branch-name.md\n"),
        "gh pr create": Completed("https://github.com/x/y/pull/9\n"),
    })
    number, finished = tool.create(source, REPO, scratch, recorder, quiet)
    check("the issue is filed once and its number is read from gh's output",
          number == 570 and recorder.count("gh issue create") == 1,
          f"number {number}, {recorder.count('gh issue create')} create call(s)")
    check("the run finishes when the file is on main", finished)
    check("the title comes from the file, not the caller",
          any("A statusline that drops its branch name" in " ".join(call)
              for call in recorder.calls if call[:3] == ["gh", "issue", "create"]))
    check("the body written at the end is the link, not the placeholder",
          any(call[:3] == ["gh", "issue", "edit"]
              and "blob/main/docs/issues/570-" in " ".join(call)
              and tool.PAIRING_KEY_PREFIX not in " ".join(call)
              for call in recorder.calls),
          str(recorder.commands()))
    check("main is fetched before the commit is made",
          recorder.commands().index("git fetch origin")
          < recorder.commands().index("git worktree add"),
          str(recorder.commands()))
    check("the worktree is removed even though the run succeeded",
          recorder.ran("git worktree remove"), str(recorder.commands()))

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
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    tool.create(source, REPO, scratch, untracked, quiet)
    check("a source that is not on main is not removed",
          not untracked.ran("git rm"), str(untracked.commands()))

    # --- Resuming: the property the design promises -----------------------

    key = tool.pairing_key(FILE_TEXT)
    resumed = Recorder({
        "gh issue list": Completed(
            '[{"number": 570, "title": "t", "body": "placeholder ' + key + '"}]'),
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
        "gh issue list": Completed(
            '[{"number": 570, "title": "t", "body": "x ' + key + '"}]'),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-a\n"),
        "git ls-tree": Completed(""),
    })
    tool.create(source, REPO, scratch, open_branch, quiet)
    check("a branch already on the remote is not pushed a second time",
          not open_branch.ran("git worktree add")
          and not open_branch.ran("gh pr create"),
          str(open_branch.commands()))
    check("and while its file is not on main the body keeps its placeholder",
          not open_branch.ran("gh issue edit"), str(open_branch.commands()))

    unlanded = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/571\n"),
        "git ls-remote": Completed(""),
        "git ls-tree": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    _, done = tool.create(source, REPO, scratch, unlanded, quiet)
    check("a body is never linked to a file that is not on main",
          done is False and not unlanded.ran("gh issue edit"),
          str(unlanded.commands()))

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


def main():
    import tempfile
    with tempfile.TemporaryDirectory(prefix="ghi-issue-write-test-") as name:
        run_cases(Path(name))
    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
