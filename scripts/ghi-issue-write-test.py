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

The edit verb's move states were produced the same way on 2026-09-21: a
file moved into its system's directory while another seat landed a change
at the path it moved from, a move that also renamed the file, and a move
whose first heading changed. The first of those was run through the tool
itself, which pushed a branch whose tree did not hold the other seat's line
at all — the deletion the conflict check now refuses.

The third round's states are the same rule again, 2026-09-21, and each was
run through the tool itself against a repository with a bare remote and gh
stubbed. A branch pushed with no pull request on it, made by failing `gh pr
create` after the push: the frozen head, rerun on it with a too-similar
verdict standing, exited 65 having made no gh call at all, and with another
seat's change landed on main under it, exited 66 — either way the branch
stayed stranded, and the fixed tool opened its pull request without asking
ghi-info anything. A file whose name carries a number no issue has: the
frozen head pushed the branch and opened the pull request before learning
that, then exited 1; the fixed tool exits 64 having run nothing but the
read, and still exits 1 when gh fails for any other reason. gh's own words
for such a number were read from the real repository. And the listing the
filed-path cases assert against is origin/main's own tree, read at that
commit and cut to the entries that decide the question.

The fourth round's, 2026-09-22, are the same rule again, and each was run
through the FIXED tool against a repository with a bare remote and `gh`
stubbed before it was written down. What the frozen head did in each is
the review's own reproduction, cited here rather than repeated.

A queue note named for an issue — `ghi_md_paths_for_issue` refuses to link one
and
`writable_relative_path` used to accept it, so the frozen head landed the
note and renamed the issue after THAT file's heading. The two are one
function now, and a case over main's own tree asserts they cannot answer
differently; the fixed tool refuses the note with 64, and `create`'s
refusal no longer sends an agent holding one to a verb that refuses it
too.

A second edit of one file, made while the first is still open — the frozen
head pushed a second branch, both merged clean, and main held the later
file with the earlier correction gone. The fixed tool refuses with 66 and
pushes nothing; handed an open edit of ANOTHER of the issue's files, it
lands, the open pull request's own file list being what is compared.

A file whose `issue:` line was built from its own heading rather than from
the issue's title — the fixed tool's run landed a line citing the issue by
the title GitHub holds, with the heading left where the author wrote it,
and the Reader cases read that line back out of the staged file. The issue
and number counts a case quotes were read from nedschorus/nedschorus the
same week.

Produced the same way on 2026-09-21, for the cases added that day: a main
carrying this source already landed under an issue number, the same content
landed under a different number, a queue file sitting beside them under
`docs/issues/` and belonging to no issue, and the exit codes git really
gives — 0 with empty output for a directory or a path that is not on the
revision, 128 for a revision that does not exist, for a path outside the
checkout and for a fetch from a remote that is not there, and 128 from `git
rev-parse --show-toplevel` outside every checkout.

Produced the same way on 2026-09-22, for the cases added that day: numbered
files sitting below `docs/issues/` rather than directly in it — 11 of them
on main that day, under `queue/` and `archived/` — `git show` exiting 0 at a
path a listing of the same commit just named and 128 at a path that commit
does not have, and `git rev-parse --verify origin/main` answering with one
hash and exiting 0.
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


# origin/main resolved to one commit, which is what every read of main in
# a create is made at. Recorders answer the resolution with this, so a case
# can assert that a listing and the reads that follow it name the same
# commit, and a case that wants a failed resolution overrides the key.
MAIN_COMMIT = "5f0fd4c5ebc6a44d8d9acbf9cccf83a6b78de43d"
MAIN_COMMIT_CALL = "git rev-parse --verify origin/main"
GHI_MD_LISTING_CALL = f"git ls-tree -r --name-only {MAIN_COMMIT} docs/issues/"


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

    `check` IS HONOURED, as `run` honours it: a canned answer that failed
    raises where the tool asked for the call to be checked, and is returned
    where the tool passed `check=False`. It was ignored until 2026-09-22,
    so every case answering a checked call with a failure exercised the
    fail-open path instead of the refusal — and a guard could be switched
    to `check=False` without any case noticing, which is what let the
    earlier-edit guard's `gh pr list` fail open uncaught. The message
    matches `run`'s so a case may assert on either.

    Resolving origin/main is answered for every case, because every create
    does it before reading main and a case that has nothing filed there
    still makes the call. A case that wants that resolution to fail passes
    its own answer under the same key."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = {MAIN_COMMIT_CALL: Completed(MAIN_COMMIT + "\n"),
                        **(answers or {})}

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

    already = written(scratch, "570-already-filed.md", "# Filed\n")
    try:
        tool.validate(already)
        check("a file already named for an issue is refused", False, "accepted")
    except tool.Refused as refusal:
        check("a file already named for an issue is refused",
              refusal.code == 64, f"code {refusal.code}")
        # This refusal used to say "use the edit verb" and nothing else,
        # and create sends every `<number>-*` file here. Main holds ten
        # queue notes named for issues and an archived draft named for
        # one, and the edit verb writes none of those paths: an agent
        # holding one was sent from a refusal to a refusal. Each line now
        # carries the condition it applies under.
        check("and it says where the edit verb writes, so the agent "
              "holding a queue note is not sent to a verb that refuses it "
              "too",
              "docs/issues/" in str(refusal)
              and "nc-systems/<system>/" in str(refusal)
              and "edit verb" in str(refusal), str(refusal))
        check("and it says what to do with a file that is a new issue "
              "rather than one of that issue's files",
              "a copy whose name carries no number" in str(refusal),
              str(refusal))

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
    # main, 25 are filed and none carries an `issue:` line at all, the
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
        # A file main has under a filed name, and not this source. Read
        # as a failure — which is what this answered until 2026-09-22 — the
        # listed path below cannot be read at all, and the run stops.
        "git show": Completed("---\nissue: [x](https://example.invalid/1)\n"
                              "---\n\n# Someone else's file\n"),
        "git ls-remote": Completed(""),
        GHI_MD_LISTING_CALL: Completed("docs/issues/570-a.md\n"),
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
        GHI_MD_LISTING_CALL: Completed(""),
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

    # A failed look at main is not "not on main". Read that way, which is
    # what this did until 2026-09-22, step 4 copies a source it should move
    # and the document lands at two paths. git's own exit code for
    # ls-tree given a revision that does not exist is 128.
    failed_tracking = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/570\n"),
        "git show": Completed("", returncode=1),
        "git ls-remote": Completed(""),
        "origin/main for-frontmatter.md": Completed(
            "", returncode=128,
            stderr="fatal: Not a valid object name origin/main"),
        "gh pr create": Completed("pr\n"),
    })
    try:
        tool.create(source, REPO, scratch, failed_tracking, quiet)
        check("a failed look at main stops step 4 rather than copying the "
              "source", False, str(failed_tracking.commands()))
    except tool.Refused as refusal:
        check("a failed look at main stops step 4 rather than copying the "
              "source",
              refusal.code == 1 and not failed_tracking.ran("git commit")
              and not failed_tracking.ran("git push")
              and failed_tracking.ran("git worktree remove"),
              f"code {refusal.code}, {failed_tracking.commands()}")

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
    # if it were filed under the number each filed GHI-MD carries.

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
    # The ref moves. This clone's worktrees share one set of remote-tracking
    # refs, so another seat's fetch can carry origin/main from under a run
    # between the listing and the reads, and a path listed from one commit
    # is then read from another. Resolved once, both name the same tree.
    check("and the listing and its reads are pinned to the one commit",
          already_landed.ran(GHI_MD_LISTING_CALL)
          and already_landed.ran(f"git show {MAIN_COMMIT}:{LANDED}"),
          str(already_landed.commands()))
    ordered = already_landed.commands()
    check("and the commit is resolved after the fetch, not before it",
          ordered.index("git fetch origin")
          < ordered.index("git rev-parse --verify"),
          str(ordered))

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
    # belong to no issue. Read as filed, one would be compared under a
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
    check("a queue file beside the filed ones is not read as filed",
          not refused_wrongly and queue_only.count("gh issue create") == 1
          and not queue_only.ran(":docs/issues/queue/"),
          refused_wrongly or str(queue_only.commands()))

    # `-r` descends, so a numbered file in a subdirectory is listed too, and
    # it is named for its issue without being filed under it: step 4 lands
    # every file it files as a direct child of docs/issues/. Read as filed,
    # each one cost a `git show` every create — 11 of them on main as it
    # stood on 2026-09-22 — and this source would be refused under a number
    # no file on main holds it under.
    nested_number = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed(
            "docs/issues/queue/570-a-statusline-drops-its-branch.md\n"
            "docs/issues/archived/570-an-older-copy.md\n"),
        "git show": Completed(STAGED),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    refused_wrongly = refusal_from_creating(source, nested_number)
    check("a numbered file below docs/issues/ is not read as filed",
          not refused_wrongly
          and nested_number.count("gh issue create") == 1
          and not nested_number.ran(":docs/issues/queue/")
          and not nested_number.ran(":docs/issues/archived/"),
          refused_wrongly or str(nested_number.commands()))

    # A path a successful listing of this same commit just named cannot be
    # absent from it, so a `git show` that exits non-zero there is git
    # failing. Read as an absence — which is what None was until
    # 2026-09-22 — it differs from what this source would become, the loop
    # goes on, and the run files the second issue this check exists to stop.
    unreadable = Recorder({
        "gh issue list": Completed("[]"),
        "gh issue create": Completed(
            "https://github.com/nedschorus/nedschorus/issues/572\n"),
        "git ls-tree": Completed(LISTING),
        "git show": Completed("", returncode=128,
                              stderr="fatal: path does not exist"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
    })
    try:
        tool.create(source, REPO, scratch, unreadable, quiet)
        check("a listed path that cannot be read stops the run", False,
              "it went on and filed "
              f"{unreadable.count('gh issue create')} issue(s)")
    except tool.Refused as refusal:
        check("a listed path that cannot be read stops the run",
              refusal.code == 1, f"code {refusal.code}")
        check("and it files no second issue on the way past the failure",
              not unreadable.ran("gh issue create"),
              str(unreadable.commands()))

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

    # `gh pr list` exits non-zero on an expired token, a rate limit and an
    # unreachable network. Read as "none open", the refusal names a state
    # nobody looked up and sends the author to wait for a pull request that
    # may already be open.
    lookup_failed = Recorder({
        "gh issue list": Completed(IN_FLIGHT),
        "gh pr list": Completed("", returncode=1,
                                stderr="gh: could not authenticate"),
    })
    try:
        tool.create(edited, REPO, scratch, lookup_failed, quiet)
        check("a filing in flight refuses even when the lookup fails", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a filing in flight refuses even when the lookup fails",
              refusal.code == 64 and INSTRUCTION in str(refusal),
              str(refusal))
        check("and it says the lookup failed rather than that none is open",
              "Looking up the pull request carrying its file failed"
              in str(refusal) and "No pull request" not in str(refusal),
              str(refusal))

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
        check("a filed GHI-MD whose filing finished is still refused", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a filed GHI-MD whose filing finished is still refused",
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
        check("a filed path with no file is refused for the file", False,
              "it was accepted")
    except tool.Refused as refusal:
        check("a filed path with no file is refused for the file",
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
    # A failed fetch and a main with nothing filed leave the same empty
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

    nothing_filed = Recorder({"git ls-tree": Completed("")})
    check("but a main with nothing filed is still an answer, not a failure",
          tool.link_body(REPO, 570, scratch, nothing_filed, quiet,
                         LANDED) is False
          and not nothing_filed.ran("gh issue edit"),
          str(nothing_filed.commands()))

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

# The same file moved AND renamed, which is what makes main's copy of it
# unfindable: the moved-from path is matched by the file's name.
RENAMED_NAME = "570-statusline-contract.md"
RENAMED_RELATIVE = f"nc-systems/statusline/{RENAMED_NAME}"

# The same file moved with its first heading changed, and main's copy at
# the old path as another seat left it.
MOVED_HEADING_TITLE = "A statusline that keeps its branch name"
MOVED_HEADING_TEXT = FILE_TEXT.replace(EDIT_TITLE, MOVED_HEADING_TITLE)
OTHER_SEAT_TEXT = FILE_TEXT + "\nAnother seat measured this on 2026-09-21.\n"

# The issue's title as GitHub holds it, which is not the file's heading —
# the state 25 of the 26 filed GHI-MDs on main are in, measured 2026-09-21.
# The file's `issue:` line cites the issue, so it has to carry this.
ISSUE_TITLE_ON_GITHUB = "Statusline: branch name lost after a rebase"

# A second edit of the same file, landed while the first is still open.
# The branch is named for the content, so the revision gets a branch of
# its own; the name below stands for the first one's.
EARLIER_EDIT_BRANCH = "ghi-570-edit-ghipair0123456789ab"
EARLIER_EDIT_TITLE = f"GHI-MD edit for issue 570: {EDIT_TITLE}"
EARLIER_EDIT_URL = "https://github.com/nedschorus/nedschorus/pull/21"


def earlier_edit_pull_request(*paths):
    """What `gh pr list --head <that branch> --json ...,files` answers with
    when an earlier edit of those paths is open on it."""
    return Completed(json.dumps([{
        "number": 21, "title": EARLIER_EDIT_TITLE, "url": EARLIER_EDIT_URL,
        "files": [{"path": path} for path in paths]}]))


def filed_ghi_md(scratch: Path, name=EDIT_NAME, text=FILE_TEXT,
                 directory="docs/issues"):
    """A file where a filed GHI-MD lives, which is where edit insists on
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

    # --- Where a filed GHI-MD may be, and what makes it filed ------------

    check("a filed GHI-MD under docs/issues/ is where it belongs",
          tool.writable_relative_path(EDIT_RELATIVE))
    check("so is one under its system's own directory",
          tool.writable_relative_path(
              "nc-systems/main-gatekeeper/570-contract.md"))
    check("a file loose in the system tree is not",
          not tool.writable_relative_path("nc-systems/570-contract.md"))
    check("and neither is one somewhere else entirely",
          not tool.writable_relative_path("docs/drafts/570-contract.md"))

    # DIRECTLY IN, the same rule ghi_md_paths_for_issue applies, because they
    # are now
    # the same function. This one took any depth under docs/issues/ and any
    # depth from three down under nc-systems/ until 2026-09-21, so the verb
    # would land a file the issue's body cannot link — and take its title
    # from that file's heading.

    check("a queue note named for an issue is not one of the issue's "
          "files, so it is not a path this verb writes either",
          not tool.writable_relative_path(
              "docs/issues/queue/18-write-test-plan-agent-native-riders.md"))
    check("nor is an archived draft named for one",
          not tool.writable_relative_path(
              "docs/issues/archived/43-step-2-claude-md-inputs.md"))
    check("nor is a file buried below a system's own directory",
          not tool.writable_relative_path(
              "nc-systems/statusline/tests/570-contract-test.md"))

    text, title, number, relative = tool.validate_edit(
        filed_ghi_md(scratch), scratch)
    check("the issue number comes from the file's name",
          number == 570 and relative == EDIT_RELATIVE and title == EDIT_TITLE,
          f"{number} {relative} {title!r}")

    check("a filed GHI-MD in its system's directory validates too",
          tool.validate_edit(
              filed_ghi_md(scratch, name="570-contract.md",
                           directory="nc-systems/statusline"),
              scratch)[2] == 570)

    for case_name, target in [
            ("a file not named for an issue is refused",
             filed_ghi_md(scratch, name="notes.md")),
            ("a filed GHI-MD outside the writable paths is refused",
             filed_ghi_md(scratch, directory="docs/drafts")),
            ("a filed GHI-MD with no heading is refused",
             filed_ghi_md(scratch, name="571-no-heading.md",
                          text="no heading\n")),
            ("a missing file is refused", scratch / "docs" / "absent.md")]:
        try:
            tool.validate_edit(target, scratch)
            check(case_name, False, "it was accepted")
        except tool.Refused as refusal:
            check(case_name, refusal.code == 64, f"code {refusal.code}")

    # The file most often at an unwritable path is a queue note, and this
    # refusal used to end "Move this file to one of those two places" —
    # which, followed on a queue note, makes it one of the issue's files:
    # step 5 links it, and main keeps the copy under queue/,
    # ghi_md_paths_for_issue
    # skipping that directory, so nothing removes it. One document, two
    # paths. `create`'s refusal sends the agent holding that same note HERE
    # to edit the issue's own file, so the two now say the same thing.

    try:
        tool.validate_edit(
            filed_ghi_md(scratch, name="570-note.md",
                         directory="docs/issues/queue"), scratch)
        check("a queue note is refused", False, "it was accepted")
    except tool.Refused as note_refusal:
        check("a queue note is not told to move itself into the issue's "
              "own directory, which would give the issue a second copy of "
              "one document",
              "Move this file" not in str(note_refusal), str(note_refusal))
        check("it is told to run the verb on the issue's own file, as "
              "create's refusal tells its holder",
              "run this command on the issue's own file" in str(note_refusal),
              str(note_refusal))
        check("and the move line is kept for the file that does want it, "
              "under the condition that says which file that is",
              "The issue's own file somewhere else: move it"
              in str(note_refusal), str(note_refusal))

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
          tool.ghi_md_paths_for_issue(570, scratch, listing)
          == ["docs/issues/570-design.md",
              "nc-systems/statusline/570-contract.md"],
          str(tool.ghi_md_paths_for_issue(570, scratch, listing)))
    check("and git is asked for both of them, recursively, since a "
          "system's own directory is a level below the tree named",
          ran_with(listing, "git ls-tree", "-r", "docs/issues/",
                   "nc-systems/"),
          str(listing.calls))

    # --- What counts as one of the issue's files, and what does not ------
    # The user ruled on 2026-09-19, in the walk
    # ghi-info-design-write-path-becomes-link-only, that step 5 writes one
    # link per file matching `docs/issues/<number>-*`, globbed at every
    # write. That glob is a literal prefix and does not descend, and the
    # ruling's worked example counts on it: it gives issue 3 four files.
    # Re-confirmed by the user 2026-09-21.
    #
    # The listing below is origin/main's own tree, read on 2026-09-21 and
    # cut to the entries that decide the question — the filed names
    # directly under docs/issues/, the same issues' numbers under its
    # queue/ and archived/ subdirectories, and a system's own directory.
    # `create`'s step 5 calls this same function, so a rule that descended
    # would have rewritten these issues' bodies on the next create run.

    MAIN_TREE = (
        "docs/issues/18-write-test-plan-riders-and-test-evidence-rules.md\n"
        "docs/issues/3-credential-work-measured-state-and-rulings.md\n"
        "docs/issues/3-dismiss-stale-reviews-experiment-design.md\n"
        "docs/issues/3-main-gatekeeper-build-slice-plan.md\n"
        "docs/issues/3-slice-6-review-evidence-not-built.md\n"
        "docs/issues/45-remote-named-agent-launch-and-reattach.md\n"
        "docs/issues/archived/43-step-2-claude-md-inputs.md\n"
        "docs/issues/queue/18-write-test-plan-agent-native-riders.md\n"
        "docs/issues/queue/3-gatekeeper-build-bindings.md\n"
        "docs/issues/queue/3-gatekeeper-checks-never-run-at-check-in.md\n"
        "docs/issues/queue/45-session-seat-and-isolation-riders.md\n"
        "docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md\n"
        "nc-systems/main-gatekeeper/main-gatekeeper-design.md\n")

    main_tree = Recorder({"git ls-tree": Completed(MAIN_TREE)})
    check("issue 3's files are the four directly under docs/issues/, which "
          "is the count the ruling's own worked example gives",
          tool.ghi_md_paths_for_issue(3, scratch, main_tree) == [
              "docs/issues/3-credential-work-measured-state-and-rulings.md",
              "docs/issues/3-dismiss-stale-reviews-experiment-design.md",
              "docs/issues/3-main-gatekeeper-build-slice-plan.md",
              "docs/issues/3-slice-6-review-evidence-not-built.md"],
          str(tool.ghi_md_paths_for_issue(3, scratch, main_tree)))
    check("the queue is not part of an issue's file set: issue 18 has one "
          "file on main, not two",
          tool.ghi_md_paths_for_issue(18, scratch, main_tree)
          == ["docs/issues/18-write-test-plan-riders-and-test-evidence"
              "-rules.md"],
          str(tool.ghi_md_paths_for_issue(18, scratch, main_tree)))
    check("and issue 45 one, not three",
          tool.ghi_md_paths_for_issue(45, scratch, main_tree)
          == ["docs/issues/45-remote-named-agent-launch-and-reattach.md"],
          str(tool.ghi_md_paths_for_issue(45, scratch, main_tree)))
    check("nor is the archive: issue 43 has no filed GHI-MD on main at all, "
          "so there is nothing for its body to link",
          tool.ghi_md_paths_for_issue(43, scratch, main_tree) == [],
          str(tool.ghi_md_paths_for_issue(43, scratch, main_tree)))

    # And it is ONE rule, not two that agree today. `ghi_md_paths_for_issue`
    # says
    # which files an issue's body links; `writable_relative_path` says
    # which files this verb may land. They were separate and they
    # disagreed, which is how a queue note got landed and its heading made
    # an issue's title. Over main's own tree, they answer together.

    numbered_on_main = [line for line in MAIN_TREE.splitlines()
                        if Path(line).name.split("-")[0].isdigit()]
    disagreed = [
        line for line in numbered_on_main
        if tool.writable_relative_path(line)
        != (line in tool.ghi_md_paths_for_issue(
            int(Path(line).name.split("-")[0]), scratch,
            Recorder({"git ls-tree": Completed(MAIN_TREE)})))]
    check("every <number>-* path on main that the body links is a path "
          "this verb writes, and every one it drops is a path this verb "
          "refuses",
          not disagreed, str(disagreed))

    deeper = Recorder({"git ls-tree": Completed(
        "nc-systems/statusline/570-contract.md\n"
        "nc-systems/statusline/tests/570-contract-test.md\n"
        "nc-systems/570-loose.md\n")})
    check("a system's own directory is one level down, so a filed name "
          "buried deeper under it is not the issue's file, and neither is "
          "one loose in the system tree",
          tool.ghi_md_paths_for_issue(570, scratch, deeper)
          == ["nc-systems/statusline/570-contract.md"],
          str(tool.ghi_md_paths_for_issue(570, scratch, deeper)))

    # --- The happy path: the file differs from main, so it lands ---------

    source = filed_ghi_md(scratch)
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
    check("the issue is read before the run touches git at all, so a "
          "number no issue has is found before a branch is pushed for it",
          landing.commands().index("gh issue view") == 0
          and landing.commands().index("gh issue view")
          < landing.commands().index("git worktree add"),
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

    # --- What that issue line cites --------------------------------------
    # The issue, by title, as CLAUDE.md says to cite one. It was built from
    # the file's first HEADING, which is the title only in `create`, where
    # the issue is filed under the heading. Here the two part company on 25
    # of the 26 filed GHI-MDs on main, and each of an issue's files would
    # have cited it under that file's own heading — four different wrong
    # names for issue 3. The case above passes either way: its heading
    # changed and its issue has one file, so the title follows the heading
    # and the two answers coincide. These three separate them.

    citing = Reader({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(ISSUE_TITLE_ON_GITHUB, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(source, REPO, scratch, citing, quiet)
    check("an edit that leaves the heading alone cites the issue by the "
          "title GitHub holds, which is not that heading",
          citing.staged == staged_form(title=ISSUE_TITLE_ON_GITHUB),
          repr((citing.staged or "")[:160]))
    check("and the issue is read before the file is staged, that title "
          "being what the line carries",
          citing.commands().index("gh issue view")
          < citing.commands().index("git worktree add"),
          str(citing.commands()))

    renaming = Reader({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(ISSUE_TITLE_ON_GITHUB, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(filed_ghi_md(scratch, text=MOVED_HEADING_TEXT), REPO, scratch,
              renaming, quiet)
    check("while an edit that renames the issue cites the name the issue "
          "ends this run with, not the one it started with — the line "
          "would be stale the moment it landed",
          renaming.staged == staged_form(title=MOVED_HEADING_TITLE,
                                         text=MOVED_HEADING_TEXT),
          repr((renaming.staged or "")[:160]))
    check("and that run does rename the issue",
          ran_with(renaming, "gh issue edit", "--title", MOVED_HEADING_TITLE),
          str(renaming.commands()))

    several_citing = Reader({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(ISSUE_TITLE_ON_GITHUB, one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + "\ndocs/issues/570-test-design.md\n"),
    })
    tool.edit(filed_ghi_md(scratch, text=MOVED_HEADING_TEXT), REPO, scratch,
              several_citing, quiet)
    check("and an issue with several files, whose title follows no one "
          "file's heading, is cited by its own title even where this "
          "file's heading changed",
          several_citing.staged == staged_form(title=ISSUE_TITLE_ON_GITHUB,
                                               text=MOVED_HEADING_TEXT),
          repr((several_citing.staged or "")[:160]))

    # Put the author's file back the way the cases below expect it: the two
    # above wrote a changed heading over it.
    source = filed_ghi_md(scratch)

    # --- A file the author moved into its system's directory -------------
    # The move § Where the tool may write allows: out of docs/issues/ once
    # the system's code starts. Main still holds the file where it was, and
    # a commit that only adds the new path leaves the document at two paths
    # the moment it merges — after which ghi_md_paths_for_issue returns both
    # and step
    # 5 links the same document twice.

    # 128 is what git answers for a path that is not in the tree asked of,
    # measured; the older cases above say 1, which blob_at reads the same
    # way — it asks only whether the call succeeded.
    moved_source = filed_ghi_md(scratch, directory="nc-systems/statusline")
    moved = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("",
                                                            returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{MOVED_RELATIVE}": Completed(
            "", returncode=128),
        # Main's copy at the path the file moved from, and the copy the
        # author's checkout started from: the same, so nobody else changed
        # it and the removal is this author's to make. Answered rather than
        # left to the recorder's default, which is an empty file that
        # succeeded — a state main is never in for a file it holds.
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
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
    check("while the issue's other filed GHI-MD, which this edit did not "
          "move, is left where it is",
          not ran_with(moved, "git rm", "570-test-design.md"),
          str(moved.calls))
    check("and the path the removal names is read on main and at the "
          "author's base before any of it, the removal being a deletion",
          moved.ran(f"git show origin/main:{EDIT_RELATIVE}")
          and moved.ran(f"git show {BASE_REVISION}:{EDIT_RELATIVE}")
          and moved.commands().index(f"git show {BASE_REVISION}:"
                                     f"{EDIT_RELATIVE}")
          < moved.commands().index("git worktree add"),
          str(moved.commands()))

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

    # --- A move that also RENAMED the file -------------------------------
    # The moved-from path is found by the file's name, so a rename misses
    # that match. It is reported rather than guarded: a renamed file and a
    # new second document for the issue are the same state on main, and
    # this verb is how both arrive, so a refusal would block the legitimate
    # one and a deletion on suspicion would delete a file nobody moved.

    renamed_source = filed_ghi_md(scratch, name=RENAMED_NAME,
                                  directory="nc-systems/statusline")
    renamed = Recorder({
        f"git show origin/main:{RENAMED_RELATIVE}": Completed(
            "", returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{RENAMED_RELATIVE}": Completed(
            "", returncode=128),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    said = []
    tool.edit(renamed_source, REPO, scratch, renamed, said.append)
    check("a move that also renamed the file removes nothing, nothing on "
          "main saying which file it was renamed from",
          not renamed.ran("git rm"), str(renamed.commands()))
    check("and the run says so, naming what main still holds, instead of "
          "landing the second copy in silence",
          any(EDIT_RELATIVE in line for line in said)
          and any("renamed this file" in line for line in said), str(said))
    check("and it still lands the author's file rather than refusing it",
          ran_with(renamed, "git add", RENAMED_RELATIVE)
          and renamed.ran("gh pr create"), str(renamed.commands()))

    # --- A rename with no move at all ------------------------------------
    # The same code path, and the one the message used to describe somebody
    # else's case to: it said "if you renamed this file as well as moving
    # it", so the author who only renamed one, inside docs/issues/, read a
    # line about a move they had not made. Widened on the user's approval,
    # 2026-09-22, item 8 of the walk
    # ghi-write-session-open-rulings-and-concerns.

    renamed_in_place = filed_ghi_md(scratch, name=RENAMED_NAME)
    renamed_in_place_relative = f"docs/issues/{RENAMED_NAME}"
    in_place = Recorder({
        f"git show origin/main:{renamed_in_place_relative}": Completed(
            "", returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{renamed_in_place_relative}": Completed(
            "", returncode=128),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    said_in_place = []
    tool.edit(renamed_in_place, REPO, scratch, in_place, said_in_place.append)
    check("a rename with no move is reported the same way, main's copy at "
          "the old name being no more findable than after a move",
          any(EDIT_RELATIVE in line for line in said_in_place)
          and not in_place.ran("git rm"), str(said_in_place))
    check("and the message reaches the author who only renamed the file, "
          "naming the move as the case it may or may not be",
          any("renamed this file, whether or not you also moved it" in line
              for line in said_in_place), str(said_in_place))

    # --- A heading changed on a file the author also moved ---------------
    # Main holds nothing at the author's path on a move, so a comparison
    # against that path finds no heading to have changed — not on this run,
    # and not on the rerun after the merge either, by which time main's copy
    # is the changed file. The comparison is against main's copy at the path
    # the file moved from.

    moved_heading_source = filed_ghi_md(
        scratch, directory="nc-systems/statusline", text=MOVED_HEADING_TEXT)
    moved_heading = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("",
                                                            returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{MOVED_RELATIVE}": Completed(
            "", returncode=128),
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(moved_heading_source, REPO, scratch, moved_heading, quiet)
    check("a heading changed on a file the author moved still reaches the "
          "issue's title",
          ran_with(moved_heading, "gh issue edit", "--title",
                   MOVED_HEADING_TITLE), str(moved_heading.commands()))
    check("and the move itself lands as a move, removing main's copy",
          ran_with(moved_heading, "git rm", EDIT_RELATIVE),
          str(moved_heading.commands()))

    moved_same_heading = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("",
                                                            returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{MOVED_RELATIVE}": Completed(
            "", returncode=128),
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("A title nobody derived", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    tool.edit(filed_ghi_md(scratch, directory="nc-systems/statusline"), REPO,
              scratch, moved_same_heading, quiet)
    check("while a move that left the heading alone renames nothing, "
          "however far the issue's title is from that heading",
          not ran_with(moved_same_heading, "gh issue edit", "--title"),
          str(moved_same_heading.commands()))

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

    # A move puts a second path under the same ruling: the author's path is
    # where the file lands, the moved-from path is where main's copy is
    # deleted. Main holds nothing at the author's path on a move, so that
    # comparison passes on two Nones and says nothing about the deletion.
    # Produced against a real repository, which is where this was measured:
    # the author moved the file while another seat landed a change at the
    # old path, and the run exited 0 having pushed a branch whose tree did
    # not hold the other seat's line at all.

    moved_conflict = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("",
                                                            returncode=128),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{MOVED_RELATIVE}": Completed(
            "", returncode=128),
        f"git show origin/main:{EDIT_RELATIVE}": Completed(OTHER_SEAT_TEXT),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git diff": Completed(
            "@@ -5,3 +5,5 @@\n Body.\n+\n"
            "+Another seat measured this on 2026-09-21.\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    try:
        tool.edit(filed_ghi_md(scratch, directory="nc-systems/statusline"),
                  REPO, scratch, moved_conflict, quiet)
        check("a move whose old path another seat changed is refused", False,
              "it proceeded")
    except tool.Refused as refusal:
        check("a move whose old path another seat changed is refused",
              refusal.code == 66, f"code {refusal.code}")
        check("and the refusal names the path whose copy it would have "
              "deleted, which is not the path the caller named",
              EDIT_RELATIVE in str(refusal)
              and "removes" in str(refusal), str(refusal)[:200])
        check("and shows the change that deletion would have discarded",
              "+Another seat measured this on 2026-09-21." in str(refusal),
              str(refusal)[:300])
        check("and tells the caller to bring the checkout up to date and "
              "fold the change into the file they moved",
              "merge or rebase onto origin/main" in str(refusal)
              and "Fold that change into the file you moved" in str(refusal),
              str(refusal)[:400])
        check("and does not promise the marker can pass it either",
              tool.RECONSIDER_LINE not in str(refusal), str(refusal)[:400])
    check("and the deletion it refuses is never staged: no worktree, no "
          "removal, no push, no pull request",
          not moved_conflict.ran("git worktree add")
          and not moved_conflict.ran("git rm")
          and not moved_conflict.ran("git push")
          and not moved_conflict.ran("gh pr create")
          and not moved_conflict.ran("gh issue edit"),
          str(moved_conflict.commands()))

    # --- The author's own second edit, before the first one merges -------
    # The conflict check above compares main with the merge base, and an
    # edit that has not merged is on neither. So a revision made before
    # merge-lane's next session got a branch of its own, cut from a main
    # without the first, and merging both was CLEAN in either order — each
    # branch changed the line once against its own base — leaving main
    # holding the second file with the first's correction gone, and no
    # conflict shown to git or to merge-lane. Reproduced at the frozen head
    # on 2026-09-21: run 1 made a line read one way, run 2 put it back and
    # added a line, both exited 0.

    second_edit = Recorder({
        "ghi-570-edit-*": Completed(
            f"abc123\trefs/heads/{EARLIER_EDIT_BRANCH}\n"),
        f"--head {EARLIER_EDIT_BRANCH}": earlier_edit_pull_request(
            EDIT_RELATIVE),
        "git ls-remote": Completed(""),
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    try:
        tool.edit(source, REPO, scratch, second_edit, quiet)
        check("a second edit of a file whose first edit is still open is "
              "refused", False, "it proceeded")
    except tool.Refused as refusal:
        check("a second edit of a file whose first edit is still open is "
              "refused", refusal.code == 66, f"code {refusal.code}")
        check("and the refusal names the pull request to wait for, by "
              "title and link rather than by number",
              EARLIER_EDIT_TITLE in str(refusal)
              and EARLIER_EDIT_URL in str(refusal), str(refusal)[:400])
        check("and tells the caller to let that merge and fold this edit "
              "in, not to rebase onto a main that does not hold it",
              "to merge" in str(refusal)
              and "Fold this edit into it" in str(refusal)
              and "merge or rebase onto origin/main" not in str(refusal),
              str(refusal)[:400])
        check("and does not promise the marker can pass it either",
              tool.RECONSIDER_LINE not in str(refusal), str(refusal)[:400])
    check("and the second branch is never pushed, so merge-lane is never "
          "handed two branches that each drop the other",
          not second_edit.ran("git worktree add")
          and not second_edit.ran("git push")
          and not second_edit.ran("gh pr create")
          and not second_edit.ran("gh issue edit"),
          str(second_edit.commands()))

    # Every edit of every file of one issue shares the branch prefix, so
    # the prefix alone would refuse an author editing the second of an
    # issue's files while the first waits — issue 3 has four on main. Those
    # are different documents and different lines, and merging both drops
    # nothing, so the open pull request's own file list is what decides.

    other_file = Recorder({
        "ghi-570-edit-*": Completed(
            f"abc123\trefs/heads/{EARLIER_EDIT_BRANCH}\n"),
        f"--head {EARLIER_EDIT_BRANCH}": earlier_edit_pull_request(
            "docs/issues/570-test-design.md"),
        "git ls-remote": Completed(""),
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(
            EDIT_RELATIVE + "\ndocs/issues/570-test-design.md\n"),
    })
    other_file_refusal = None
    try:
        tool.edit(source, REPO, scratch, other_file, quiet)
    except tool.Refused as refusal:
        other_file_refusal = refusal
    check("while an open edit of ANOTHER of the issue's files does not "
          "refuse this one, the two changing nothing in common",
          other_file_refusal is None and other_file.ran("gh pr create"),
          f"refused {getattr(other_file_refusal, 'code', None)}: "
          f"{str(other_file_refusal)[:200]}" if other_file_refusal
          else str(other_file.commands()))

    # A branch left by a push whose `gh pr create` failed will never merge
    # on its own, and the resume above is what finishes it. Refusing on the
    # branch rather than on the pull request would wedge every later run on
    # that file behind a branch nothing can merge.

    stranded_earlier = Recorder({
        "ghi-570-edit-*": Completed(
            f"abc123\trefs/heads/{EARLIER_EDIT_BRANCH}\n"),
        f"--head {EARLIER_EDIT_BRANCH}": Completed("[]"),
        "git ls-remote": Completed(""),
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    stranded_refusal_on_earlier = None
    try:
        tool.edit(source, REPO, scratch, stranded_earlier, quiet)
    except tool.Refused as refusal:
        stranded_refusal_on_earlier = refusal
    check("and an earlier branch with no pull request open on it refuses "
          "nothing: GitHub is asked, not the remote's branch list",
          stranded_refusal_on_earlier is None
          and stranded_earlier.ran("gh pr create"),
          f"refused {getattr(stranded_refusal_on_earlier, 'code', None)}: "
          f"{str(stranded_refusal_on_earlier)[:200]}"
          if stranded_refusal_on_earlier
          else str(stranded_earlier.commands()))

    # A move puts the moved-from path under this check too: that is where
    # the run deletes main's copy, so an open edit of it is work this run
    # would remove.

    moved_second_edit = Recorder({
        "ghi-570-edit-*": Completed(
            f"abc123\trefs/heads/{EARLIER_EDIT_BRANCH}\n"),
        f"--head {EARLIER_EDIT_BRANCH}": earlier_edit_pull_request(
            EDIT_RELATIVE),
        "git ls-remote": Completed(""),
        f"git show origin/main:{MOVED_RELATIVE}": Completed(
            "", returncode=128),
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    try:
        tool.edit(filed_ghi_md(scratch, directory="nc-systems/statusline"),
                  REPO, scratch, moved_second_edit, quiet)
        check("a move whose old path an open edit still holds is refused "
              "too, that path being where this run deletes main's copy",
              False, "it proceeded")
    except tool.Refused as refusal:
        check("a move whose old path an open edit still holds is refused "
              "too, that path being where this run deletes main's copy",
              refusal.code == 66 and EDIT_RELATIVE in str(refusal),
              f"code {refusal.code}: {str(refusal)[:200]}")
    check("and nothing of that move is staged, removed or pushed",
          not moved_second_edit.ran("git worktree add")
          and not moved_second_edit.ran("git rm")
          and not moved_second_edit.ran("git push")
          and not moved_second_edit.ran("gh pr create"),
          str(moved_second_edit.commands()))

    # --- The guard cannot be asked, so it does not let the run past -------
    # Both of its lookups had a case only for the answers they give when
    # they work. A lookup that FAILS is the same loss of work again, reached
    # by another road: read as "no earlier edit", it lets a second branch be
    # pushed over the first. The `gh pr list` was left open until 2026-09-22
    # and merge-lane-2 reproduced the whole sequence through it with gh
    # answering HTTP 401 — a second branch pushed, `gh pr create` failing
    # after it, and the rerun once gh recovered opening a second pull request
    # beside the first, through the resume path this guard does not sit on.
    # ned-box's own gh exits with a GraphQL deprecation error on a plain
    # `gh pr view`, so the failing state is a state seats are in.
    #
    # The glob key comes first in each recorder below: the branch list and
    # the landing-state lookup are both `git ls-remote`, and the answers are
    # matched in order, so a bare "git ls-remote" key placed first would
    # answer the guard's call as well.

    for case_name, answers, stopped_at in [
            ("the branch list the earlier-edit guard reads is checked, so a "
             "failed `git ls-remote` stops the run rather than reading as "
             "no earlier edit",
             {"ghi-570-edit-*": Completed("", returncode=1,
                                          stderr="fatal: unable to access"),
              "git ls-remote": Completed("")},
             "git ls-remote"),
            ("and so is the pull request lookup, so a failed `gh pr list` "
             "stops it rather than reading as no open pull request",
             {"ghi-570-edit-*": Completed(
                 f"abc123\trefs/heads/{EARLIER_EDIT_BRANCH}\n"),
              f"--head {EARLIER_EDIT_BRANCH}": Completed(
                  "", returncode=1, stderr="HTTP 401: Bad credentials"),
              "git ls-remote": Completed("")},
             "gh pr list")]:
        unaskable = Recorder(dict(answers, **{
            f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
            "git merge-base": Completed(BASE_REVISION + "\n"),
            f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(
                "# Older\n"),
            "gh pr create": Completed("pr\n"),
            "gh issue view": issue_json("Older", one_link),
            "git ls-tree": Completed(EDIT_RELATIVE + "\n")}))
        unaskable_refusal = None
        try:
            tool.edit(source, REPO, scratch, unaskable, quiet)
        except tool.Refused as refusal:
            unaskable_refusal = refusal
        check(case_name,
              unaskable_refusal is not None
              and unaskable_refusal.code == 1
              and stopped_at in str(unaskable_refusal),
              f"refused {getattr(unaskable_refusal, 'code', None)}: "
              f"{str(unaskable_refusal)[:200]}" if unaskable_refusal
              else f"it proceeded: {unaskable.commands()}")
        check(f"and nothing is pushed when {stopped_at} cannot be asked",
              not unaskable.ran("git worktree add")
              and not unaskable.ran("git push")
              and not unaskable.ran("gh pr create"),
              str(unaskable.commands()))

    # --- Resuming after the pull request merged --------------------------
    # The author's own landed change is a difference between the merge base
    # and main, so a conflict check made first would refuse them their own
    # edit. Main's copy is compared to theirs before any of that.

    # Main's copy is what the earlier run landed, `issue:` line included,
    # and that line cites the issue by the title GitHub holds — which on
    # this file is nowhere near its heading, and stays where it is because
    # the heading did not change. A fixture where main's copy cited the
    # HEADING instead would be a state this tool cannot produce, and the
    # rerun would read it as content of its own to land.
    resumed = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed(
            staged_form(title="Stale title")),
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
        ASK: Completed("verdict: too-similar #13\n"),
    })
    still_waiting, waiting_refusal = False, None
    try:
        _, still_waiting = tool.edit(source, REPO, scratch, waiting, quiet)
    except tool.Refused as refusal:
        waiting_refusal = refusal
    check("a branch already on the remote is not pushed a second time",
          waiting_refusal is None and not waiting.ran("git worktree add")
          and not waiting.ran("gh pr create"),
          f"refused {getattr(waiting_refusal, 'code', None)}: "
          f"{str(waiting_refusal)[:160]}" if waiting_refusal
          else str(waiting.commands()))
    check("nor does a rerun whose pull request is already open ask ghi-info "
          "again, or get refused for an edit it already landed",
          waiting_refusal is None and not waiting.ran(ASK),
          f"refused: {str(waiting_refusal)[:160]}" if waiting_refusal
          else str(waiting.commands()))
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
        # Standing over that state, the verdict that refused the first run.
        # The question is the same draft with the same exclusion, so this is
        # the answer every rerun gets.
        ASK: Completed("verdict: too-similar #13\n"),
    })
    stranded_refusal = None
    try:
        tool.edit(source, REPO, scratch, pushed_only, quiet)
    except tool.Refused as refusal:
        stranded_refusal = refusal
    check("a branch pushed without a pull request gets one on the rerun",
          stranded_refusal is None and pushed_only.ran("gh pr create"),
          f"refused {getattr(stranded_refusal, 'code', None)}: "
          f"{str(stranded_refusal)[:160]}" if stranded_refusal
          else str(pushed_only.commands()))
    check("and it asks ghi-info nothing, this content being pushed already: "
          "a rerun that only opens the missing pull request has nothing new "
          "to adjudicate",
          not pushed_only.ran(ASK), str(pushed_only.commands()))
    check("and nothing is committed or pushed over it to get there",
          not pushed_only.ran("git worktree add")
          and not pushed_only.ran("git push"), str(pushed_only.commands()))
    check("and the pull request it opens is the edit's own, not a filing's",
          ran_with(pushed_only, "gh pr create",
                   f"GHI-MD edit for issue 570: {EDIT_TITLE}",
                   "An edit to the GHI-MD for issue #570"),
          str(pushed_only.calls))

    # The same state with main moved under it: another seat landed a change
    # at this path after the branch was pushed. Refusing here cannot un-push
    # the branch — it only leaves it stranded, exactly as the verdict above
    # would have. Produced against a real repository on 2026-09-21: the
    # frozen head exited 66 on this state with the branch already on the
    # remote and no pull request on it.

    pushed_while_main_moved = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Theirs\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git diff": Completed("@@\n-# Older\n+# Theirs\n"),
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-edit-x\n"),
        "gh pr list": Completed("[]"),
        "gh pr create": Completed("https://github.com/x/y/pull/12\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
    })
    moved_refusal = None
    try:
        tool.edit(source, REPO, scratch, pushed_while_main_moved, quiet)
    except tool.Refused as refusal:
        moved_refusal = refusal
    check("a rerun that only opens the missing pull request is not refused "
          "for a change on main either, a refusal being unable to un-push "
          "the branch it would strand",
          moved_refusal is None
          and pushed_while_main_moved.ran("gh pr create"),
          f"refused {getattr(moved_refusal, 'code', None)}: "
          f"{str(moved_refusal)[:160]}" if moved_refusal
          else str(pushed_while_main_moved.commands()))
    check("and the conflict check is not even reached on that rerun, the "
          "push it guards having happened already",
          not pushed_while_main_moved.ran("git merge-base"),
          str(pushed_while_main_moved.commands()))

    # --- Which runs are adjudicated, and which have nothing to ask -------
    # Adjudication costs a model call and can refuse the run, so the run
    # that asks must be a run with something new to land. Two states have
    # nothing new: main's copy is already this file, and this content is
    # already pushed on its branch. Only the first was tested, so the second
    # asked again — and the same draft with the same exclusion gets the same
    # verdict, which raised 65 before the resume was reached. The one run
    # that could open the missing pull request was the one run refused.

    at_rest = Recorder()
    check("an edit whose content main already holds has nothing to land, "
          "and the branch is not even asked about",
          tool.edit_landing_state(570, staged, staged, scratch, at_rest)
          == (tool.EDIT_LANDING_ALREADY_ON_MAIN, None)
          and not at_rest.ran("git ls-remote"), str(at_rest.commands()))
    pushed_state = Recorder({
        "git ls-remote": Completed("abc123\trefs/heads/ghi-570-edit-x\n")})
    check("an edit already pushed on its branch has nothing NEW to land",
          tool.edit_landing_state(570, staged, "# Older\n", scratch,
                                  pushed_state)
          == (tool.EDIT_LANDING_ALREADY_PUSHED,
              tool.edit_landing_branch_name(570, staged)),
          str(tool.edit_landing_state(570, staged, "# Older\n", scratch,
                                      pushed_state)))
    fresh_state = Recorder({"git ls-remote": Completed("")})
    check("and an edit that is neither on main nor pushed has new content "
          "to land",
          tool.edit_landing_state(570, staged, "# Older\n", scratch,
                                  fresh_state)
          == (tool.EDIT_LANDING_NEW_CONTENT,
              tool.edit_landing_branch_name(570, staged)),
          str(tool.edit_landing_state(570, staged, "# Older\n", scratch,
                                      fresh_state)))

    # The opposite defect, and the worse one: a run that DOES have new
    # content to land must still be adjudicated, and a too-similar verdict
    # must still stop it before anything reaches the remote.

    new_to_land = Recorder({
        f"git show origin/main:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed("# Older\n"),
        "git ls-remote": Completed(""),
        "gh pr create": Completed("pr\n"),
        "gh issue view": issue_json("Older", one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
        ASK: Completed("verdict: too-similar #13\n"),
    })
    try:
        tool.edit(source, REPO, scratch, new_to_land, quiet)
        check("an edit with new content to land is adjudicated still",
              False, "it proceeded unasked")
    except tool.Refused as refusal:
        check("an edit with new content to land is adjudicated still",
              refusal.code == 65 and new_to_land.ran(ASK),
              f"code {refusal.code}, asked ghi-info: "
              f"{new_to_land.ran(ASK)}")
    check("and the verdict stops it before anything is pushed or opened",
          not new_to_land.ran("git worktree add")
          and not new_to_land.ran("git push")
          and not new_to_land.ran("gh pr create")
          and not new_to_land.ran("gh issue edit"),
          str(new_to_land.commands()))

    # A moved file is new content to land too — main holds nothing at the
    # author's path, so `on_main` is None and never equals the staged text.

    moved_to_land = Recorder({
        f"git show origin/main:{MOVED_RELATIVE}": Completed("",
                                                            returncode=128),
        f"git show origin/main:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git merge-base": Completed(BASE_REVISION + "\n"),
        f"git show {BASE_REVISION}:{EDIT_RELATIVE}": Completed(FILE_TEXT),
        "git ls-remote": Completed(""),
        "gh issue view": issue_json(EDIT_TITLE, one_link),
        "git ls-tree": Completed(EDIT_RELATIVE + "\n"),
        ASK: Completed("verdict: too-similar #13\n"),
    })
    try:
        tool.edit(filed_ghi_md(scratch, directory="nc-systems/statusline"),
                  REPO, scratch, moved_to_land, quiet)
        check("and so is a move, which main has nothing at the author's "
              "path to compare with",
              False, "it proceeded unasked")
    except tool.Refused as refusal:
        check("and so is a move, which main has nothing at the author's "
              "path to compare with",
              refusal.code == 65 and moved_to_land.ran(ASK),
              f"code {refusal.code}, asked ghi-info: "
              f"{moved_to_land.ran(ASK)}")
    check("and nothing of that move is staged, removed or pushed",
          not moved_to_land.ran("git worktree add")
          and not moved_to_land.ran("git rm")
          and not moved_to_land.ran("git push")
          and not moved_to_land.ran("gh pr create"),
          str(moved_to_land.commands()))

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
    check("an issue with several filed GHI-MDs is not renamed after one of "
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
    check("and not refused either, since every filed issue on main is in "
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

    # --- A name carrying a number no issue has ---------------------------
    # The issue was read after the push and the pull request, so a file
    # whose name carried a number that is not an issue got a branch pushed
    # and a pull request opened for an issue that does not exist, and then
    # failed with 1 — an operating failure — for what the exit table calls
    # wrong caller input. Both halves were produced against a real
    # repository on 2026-09-21: the frozen head exited 1 with the branch on
    # the remote and the pull request open. gh's answer to such a number was
    # read from the repository itself the same day — `gh issue view 999999
    # --repo nedschorus/nedschorus --json title,body`, exit 1, nothing on
    # stdout, this line on stderr with 999999 where this case's own number
    # stands.

    GH_SAID_NO_SUCH_ISSUE = (
        "GraphQL: Could not resolve to an issue or pull request with the "
        "number of 570. (repository.issue)")

    no_such_issue = Recorder({
        "gh issue view": Completed("", returncode=1,
                                   stderr=GH_SAID_NO_SUCH_ISSUE)})
    try:
        tool.edit(source, REPO, scratch, no_such_issue, quiet)
        check("a file named for an issue that does not exist is refused",
              False, "it proceeded")
    except tool.Refused as refusal:
        check("a file named for an issue that does not exist is refused",
              refusal.code == 64, f"code {refusal.code}")
        check("and the refusal names the file, the repository with no such "
              "issue, and the verb that files one",
              EDIT_RELATIVE in str(refusal) and REPO in str(refusal)
              and "create verb" in str(refusal), str(refusal)[:300])
    check("and the number is tested before anything is fetched, "
          "adjudicated, pushed or opened",
          not no_such_issue.ran("git fetch")
          and not no_such_issue.ran(ASK)
          and not no_such_issue.ran("git worktree add")
          and not no_such_issue.ran("git push")
          and not no_such_issue.ran("gh pr create")
          and not no_such_issue.ran("gh issue edit"),
          str(no_such_issue.commands()))

    gh_unreachable = Recorder({
        "gh issue view": Completed(
            "", returncode=1,
            stderr="error connecting to api.github.com: no such host")})
    try:
        tool.edit(source, REPO, scratch, gh_unreachable, quiet)
        check("while gh failing for any other reason is an operating "
              "failure still, not a caller who named a wrong number",
              False, "it proceeded")
    except tool.Refused as refusal:
        check("while gh failing for any other reason is an operating "
              "failure still, not a caller who named a wrong number",
              refusal.code == 1, f"code {refusal.code}")

    # --- A name carrying a number a PULL REQUEST has ---------------------
    # `gh issue view` given a pull request's number exits 0 and answers
    # with the pull request, so the refusal above never fires and the run
    # edits that pull request's title. Issues and pull requests share one
    # number line here — 125 issues among 632 numbers on 2026-09-22 — so a
    # mistyped number is likelier to name a pull request than nothing. The
    # url says which came back.

    numbered_for_a_pull_request = Recorder({
        "gh issue view": Completed(json.dumps({
            "title": "Build the GHI write tool's edit verb",
            "body": "",
            "url": "https://github.com/nedschorus/nedschorus/pull/570"}))})
    try:
        tool.edit(source, REPO, scratch, numbered_for_a_pull_request, quiet)
        check("a file named for a number a pull request has is refused",
              False, "it proceeded")
    except tool.Refused as refusal:
        check("a file named for a number a pull request has is refused",
              refusal.code == 64, f"code {refusal.code}")
        check("and the refusal says which it was, and shows the url gh "
              "answered with",
              "pull request" in str(refusal)
              and "/pull/570" in str(refusal), str(refusal)[:300])
    check("and the url is asked for, or nothing could tell the two apart",
          ran_with(numbered_for_a_pull_request, "gh issue view",
                   "title,body,url"),
          str(numbered_for_a_pull_request.calls))
    check("and nothing is fetched, adjudicated, pushed or opened for it",
          not numbered_for_a_pull_request.ran("git fetch")
          and not numbered_for_a_pull_request.ran(ASK)
          and not numbered_for_a_pull_request.ran("git worktree add")
          and not numbered_for_a_pull_request.ran("gh pr create")
          and not numbered_for_a_pull_request.ran("gh issue edit"),
          str(numbered_for_a_pull_request.commands()))

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
