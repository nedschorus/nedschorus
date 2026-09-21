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

What that leaves to the author: a recorder answers whatever the case tells
it to, including a state no real run could be in, and a case built on one
passes without exercising anything. It happened here — see the happy path
below. So each state a case encodes was produced once against a real
repository, with a bare remote and `gh` stubbed, before being written down:
filed, merged, head branch deleted, source moved, pushed without a pull
request, and a destination holding a file that is not this one.

Produced the same way on 2026-09-21, for the cases added that day: a main
carrying this source already landed under an issue number, the same content
landed under a different number, a queue file sitting beside them under
`docs/issues/` and belonging to no issue, and the exit codes git really
gives — 0 with empty output for a directory or a path that is not on the
revision, 128 for a revision that does not exist, for a path outside the
checkout and for a fetch from a remote that is not there, and 128 from `git
rev-parse --show-toplevel` outside every checkout.
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
    reply with no verdict line, which is itself a pass condition.

    `check` is honoured, as `run` honours it: a non-zero answer to a call the
    tool made with check on raises the refusal `run` would raise. Until
    2026-09-21 it was ignored, and a case answering a call with a failure
    could only ever exercise the path where that failure was swallowed —
    which is the path the cases below exist to say is gone."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, arguments, timeout=None, cwd=None, check=True):
        self.calls.append(list(arguments))
        for prefix, answer in self.answers.items():
            if prefix in " ".join(arguments):
                if isinstance(answer, Exception):
                    raise answer
                if check and answer.returncode != 0:
                    raise tool.Refused(
                        f"{' '.join(arguments[:3])} failed: "
                        f"{(answer.stderr or answer.stdout).strip()}", 1)
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


def parsed_issue_value(frontmatter_line):
    """The `issue:` value read the way a YAML parser reads a double-quoted
    scalar. A value that is not quoted is not a scalar at all — it opens a
    flow sequence and raises, which is the defect the quoting fixed — so
    that is handed back as text and fails the case rather than killing the
    suite."""
    try:
        return json.loads(frontmatter_line.split(": ", 1)[1])
    except ValueError as failure:
        return f"unparsable: {failure}"


def run_cases(scratch: Path):

    def refusal_from_creating(source_path, recorder):
        """create(), with a refusal handed back as text rather than raised.

        A case that says the tool goes ON is only a case if a refusal fails
        it by name. Raised, it escapes run_cases instead and the suite dies
        with a traceback, which says a guard fired but not which case it
        broke."""
        try:
            tool.create(source_path, REPO, scratch, recorder, quiet)
            return ""
        except tool.Refused as refusal:
            return f"refused: {refusal}"

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
    # Between the filing and the commit, not merely somewhere before it.
    # The duplicate check fetches at the top of the run and adjudication
    # sits between the two, which can take minutes, so only a fetch after
    # the filing makes the worktree's "cut from a just-fetched main" true.
    ordered = first.commands()
    check("main is fetched between the filing and the commit, so the "
          "worktree is cut from a main that is current",
          "git fetch origin" in ordered[ordered.index("gh issue create"):
                                        ordered.index("git worktree add")],
          str(ordered))
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
          line == 'issue: "[A title](https://github.com/nedschorus/nedschorus/issues/570)"',
          repr(line))

    # The value is quoted because unquoted it is not YAML: it opens with `[`,
    # so a parser reads a flow sequence and raises at the `](`. A parser is
    # not imported to prove that — the suite runs under a stdlib with no YAML
    # in it — so the case pins the shape a double-quoted scalar has.
    value = line.split(": ", 1)[1]
    check("the value is a double-quoted scalar, not a bare flow sequence",
          value.startswith('"') and value.endswith('"')
          and not value.startswith("["), repr(value))
    check("and it parses back to the link it carries",
          parsed_issue_value(line)
          == "[A title](https://github.com/nedschorus/nedschorus/issues/570)",
          repr(value))

    awkward = tool.issue_frontmatter_line(
        REPO, 570, 'He said "no" \\ then left')
    check("a title holding a quote or a backslash is escaped inside them",
          parsed_issue_value(awkward)
          == '[He said "no" \\ then left]'
             '(https://github.com/nedschorus/nedschorus/issues/570)',
          repr(awkward))

    accented = tool.issue_frontmatter_line(REPO, 570, "Naïve café")
    check("and a non-ASCII title stays itself rather than being escaped",
          "Naïve café" in accented, repr(accented))

    # A file the tool filed before this change carries the unquoted shape.
    # It corrects itself the next time the tool writes to it, and only while
    # the rewriter finds the line by its key rather than by the shape of its
    # value. (Measured 2026-09-21: of the 50 paths under docs/issues/ on
    # main, 25 are paired and none carries an `issue:` line at all, the
    # create verb having filed nothing that has merged yet. So there is
    # nothing to correct today and everything to correct tomorrow.)
    old_shape = ("---\nissue: [A title](https://github.com/nedschorus/"
                 "nedschorus/issues/570)\nstatus: draft\n---\n\n# T\n")
    corrected = tool.with_issue_frontmatter(old_shape, REPO, 570, "A title")
    check("a line written in the old unquoted shape is corrected, not doubled",
          corrected.count("issue:") == 1 and line in corrected
          and "status: draft" in corrected, repr(corrected[:150]))

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

    # --- Resuming, where the pairing key cannot reach ---------------------
    # A finished filing leaves no key anywhere and a source the tool did not
    # move is still on disk, so the key alone lets a rerun file a second
    # issue. Main is asked instead, forward: what would this source become
    # if it were filed under the number each paired file carries.

    LISTING = (LANDED + "\n"
               + "docs/issues/571-a-statusline-that-drops-its-branch-name.md\n"
               + "docs/issues/queue/statusline-drops-branch.md\n")

    already_landed = Recorder({
        "gh issue list": Completed("[]"),
        "git ls-tree": Completed(LISTING),
        "git show": Completed(STAGED),
    })
    try:
        tool.create(source, REPO, scratch, already_landed, quiet)
        check("a source already on main under an issue is refused", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a source already on main under an issue is refused",
              refusal.code == 64, f"code {refusal.code}")
        check("and the refusal names the landed path and the edit verb",
              LANDED in str(refusal) and "edit verb" in str(refusal),
              str(refusal))
        check("and it files nothing, lands nothing and asks ghi-info nothing",
              not already_landed.ran("gh issue create")
              and not already_landed.ran("git worktree add")
              and not already_landed.ran(ASK),
              str(already_landed.commands()))
    check("and the check reads main freshly rather than trusting the disk",
          already_landed.ran("git fetch origin main"),
          str(already_landed.commands()))

    # The comparison is computed under the number the PATH carries. The same
    # content landed under a different issue is a different file, and must
    # not stop this one being filed.
    landed_elsewhere = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed(LISTING),
        "git show": Completed(
            tool.with_issue_frontmatter(FILE_TEXT, REPO, 999, TITLE)),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    refused_wrongly = refusal_from_creating(source, landed_elsewhere)
    check("the same content staged under another number is not this file",
          not refused_wrongly
          and landed_elsewhere.count("gh issue create") == 1,
          refused_wrongly or str(landed_elsewhere.commands()))

    # `docs/issues/` also holds the queue, whose files carry no number and
    # belong to no issue. Read as paired, one would be compared under a
    # number that does not exist.
    queue_only = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed("docs/issues/queue/statusline.md\n"),
        "git show": Completed(STAGED),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    refused_wrongly = refusal_from_creating(source, queue_only)
    check("a queue file beside the paired ones is not read as paired",
          not refused_wrongly and queue_only.count("gh issue create") == 1
          and not queue_only.ran("origin/main:docs/issues/queue/"),
          refused_wrongly or str(queue_only.commands()))

    # --- An edit made mid-filing, which moves the key off its own issue ---

    IN_FLIGHT = ('[{"number": 570, "title": "' + TITLE + '", '
                 '"body": "Filing in progress, pairing key ghipairOTHER."}]')
    # The whole sentence, not a fragment of it. It is what keeps an author
    # out of the one case neither check sees — an edited source rerun after
    # the merge — so the words are the guard and the case pins all of them.
    INSTRUCTION = ("Wait for the merge, then apply your edit to the landed "
                   "file with the edit verb, and do not rerun create on this "
                   "file.")
    edited = written(scratch, "edited-mid-filing.md",
                     FILE_TEXT.replace("Body.", "Body, edited."))

    in_flight = Recorder({
        "gh issue list": Completed(IN_FLIGHT),
        "gh pr list": Completed(
            '[{"number": 9, "title": "GHI-MD for issue 570: ' + TITLE + '", '
            '"url": "https://github.com/x/y/pull/9"}]'),
    })
    try:
        tool.create(edited, REPO, scratch, in_flight, quiet)
        check("an edit made while its own filing is in flight is refused",
              False, "it was accepted")
    except tool.Refused as refusal:
        check("an edit made while its own filing is in flight is refused",
              refusal.code == 64, f"code {refusal.code}")
        check("and the refusal names the issue and the pull request to wait "
              "for",
              "https://github.com/nedschorus/nedschorus/issues/570"
              in str(refusal)
              and "https://github.com/x/y/pull/9" in str(refusal),
              str(refusal))
        check("and it instructs, in the words that cover the case neither "
              "check sees",
              INSTRUCTION in str(refusal), str(refusal))
        check("and nothing is filed, landed or adjudicated",
              not in_flight.ran("gh issue create")
              and not in_flight.ran("git worktree add")
              and not in_flight.ran(ASK),
              str(in_flight.commands()))
    check("and the check costs no issue list of its own",
          in_flight.count("gh issue list") == 1,
          str(in_flight.commands()))

    # A run that died between step 3 and its push leaves the issue in flight
    # with no pull request on it. The refusal still has to instruct.
    no_pull_request = Recorder({
        "gh issue list": Completed(IN_FLIGHT),
        "gh pr list": Completed("[]"),
    })
    try:
        tool.create(edited, REPO, scratch, no_pull_request, quiet)
        check("an in-flight filing with no pull request yet still refuses",
              False, "it was accepted")
    except tool.Refused as refusal:
        check("an in-flight filing with no pull request yet still refuses",
              refusal.code == 64 and "No pull request" in str(refusal)
              and INSTRUCTION in str(refusal), str(refusal))

    # Both halves are required. A title alone cannot refuse: adjudication
    # fails open, so two open issues can carry one title, and the design
    # rejected title matching for exactly that reason.
    finished_same_title = Recorder({
        "gh issue list": Completed(
            '[{"number": 570, "title": "' + TITLE + '", '
            '"body": "- [570-a.md](https://github.com/x/y/blob/main/a.md)"}]'),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed(""),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    refused_wrongly = refusal_from_creating(edited, finished_same_title)
    check("an open issue of the same title whose filing finished does not "
          "refuse",
          not refused_wrongly
          and finished_same_title.count("gh issue create") == 1,
          refused_wrongly or str(finished_same_title.commands()))

    other_heading = Recorder({
        "gh issue list": Completed(
            '[{"number": 570, "title": "Some other heading", '
            '"body": "Filing in progress, pairing key ghipairOTHER."}]'),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed(""),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    refused_wrongly = refusal_from_creating(edited, other_heading)
    check("a filing in flight under another heading does not refuse",
          not refused_wrongly and other_heading.count("gh issue create") == 1,
          refused_wrongly or str(other_heading.commands()))

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

    # --- Step 5's git raises instead of reading a failure as an answer ----
    # A failed fetch and a main with nothing paired leave the same empty
    # list, and the report then tells the author no file is on main yet —
    # which, the fetch having failed, the run cannot know. The exit codes
    # here are git's own: 128 from a fetch whose remote is not there, 128
    # from ls-tree given a revision that does not exist, and 0 with empty
    # output from ls-tree given a directory that is simply not on the
    # revision, which is why a non-zero exit is safe to treat as a failure.

    failed_fetch = Recorder({
        "git fetch": Completed("", returncode=128,
                               stderr="fatal: could not read from remote"),
        "git ls-tree": Completed(LANDED + "\n"),
    })
    try:
        tool.link_body(REPO, 570, scratch, failed_fetch, quiet, LANDED)
        check("a failed fetch stops step 5 rather than reporting an empty "
              "main", False, "it went on")
    except tool.Refused as refusal:
        check("a failed fetch stops step 5 rather than reporting an empty "
              "main",
              refusal.code == 1 and not failed_fetch.ran("gh issue edit"),
              f"code {refusal.code}, {failed_fetch.commands()}")

    failed_list = Recorder({
        "git ls-tree": Completed("", returncode=128,
                                 stderr="fatal: Not a valid object name"),
    })
    try:
        tool.link_body(REPO, 570, scratch, failed_list, quiet, LANDED)
        check("a failed list stops step 5 the same way", False, "it went on")
    except tool.Refused as refusal:
        check("a failed list stops step 5 the same way",
              refusal.code == 1 and not failed_list.ran("gh issue edit"),
              f"code {refusal.code}, {failed_list.commands()}")

    nothing_paired = Recorder({"git ls-tree": Completed("")})
    check("but a main with nothing paired is still an answer, not a failure",
          tool.link_body(REPO, 570, scratch, nothing_paired, quiet,
                         LANDED) is False
          and not nothing_paired.ran("gh issue edit"),
          str(nothing_paired.commands()))

    # --- Where the checkout is looked for ---------------------------------
    # Through the shared `run`, so that function's docstring is true of this
    # call too, and with check off, so a path outside a checkout keeps this
    # program's own refusal and its 64 rather than `run`'s generic 1.

    rooted = Recorder({"git rev-parse": Completed("/x/y\n")})
    try:
        found = tool.repository_root_of(scratch, rooted)
        detail = str(rooted.commands())
    except tool.Refused as refusal:
        found, detail = None, f"refused: {refusal}"
    check("the checkout is found through the shared run, not around it",
          found == Path("/x/y")
          and rooted.ran("git rev-parse --show-toplevel"), detail)

    unrooted = Recorder({
        "git rev-parse": Completed(
            "", returncode=128,
            stderr="fatal: not a git repository (or any of the parent "
                   "directories): .git")})
    try:
        tool.repository_root_of(scratch, unrooted)
        check("a path outside every checkout keeps this program's refusal",
              False, "it was accepted")
    except tool.Refused as refusal:
        check("a path outside every checkout keeps this program's refusal",
              refusal.code == 64 and "not inside a git checkout"
              in str(refusal), f"code {refusal.code}, {refusal}")

    # --- A bad command line -----------------------------------------------
    # argparse exits 2 of its own accord, and this program documents no 2.
    # 64 is what every other wrong input to it gets. Usage text and message
    # stay argparse's; only the code moves. These reach neither git nor gh.

    for case_name, argv in [
            ("no verb at all is a bad invocation, not argparse's 2", []),
            ("an unknown flag is a bad invocation", ["--bogus"]),
            ("a verb missing its path is a bad invocation", ["create"]),
            ("an unknown verb is a bad invocation", ["frobnicate", "x.md"])]:
        complaint = io.StringIO()
        try:
            with contextlib.redirect_stderr(complaint):
                tool.main(argv)
            check(case_name, False, "argparse did not exit")
        except SystemExit as exit_code:
            check(case_name, exit_code.code == 64, f"code {exit_code.code}")
            check(f"  and argparse's own usage text survives ({argv})",
                  "usage:" in complaint.getvalue(),
                  repr(complaint.getvalue()[:120]))


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
