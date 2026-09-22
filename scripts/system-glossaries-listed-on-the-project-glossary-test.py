#!/usr/bin/env python3
"""Every system glossary git tracks is listed on the project glossary, and
every glossary path the project glossary names is one git tracks.

The project glossary, docs/nedschorus-wiki/nedschorus-glossary.md, carries a
paragraph above its entries naming each system glossary, so a reader of that
one page sees the whole vocabulary of the project and knows where the rest of
it lives. The user ruled the paragraph on 2026-09-22, at item 3 of the walk
skills-glossary-2026-09-21-2, preferring it to two mechanisms the walk had
reached for first: a clause in six reviewer prompts and skills telling a
reviewer to read the system glossaries, and a rule that every document using
a system-term cite its glossary by path. His words: "I have a simpler
proposal. Include links in the project glossary all the system glossaries. At
least for now, our glossaries are small, and there is some advantage to
seeing all of them."

THIS TEST EXISTS BECAUSE HE ASKED FOR IT, in the same breath: "I think we
need to add something to ensure that future system glossaries get added to
the project glossary." A list nothing checks is right on the day it is
written and wrong the first time a system is added, and this project has one
instance of exactly that: the clause "and any system glossary that page
names" was approved on 2026-09-21 and was still unbuilt a day later, in all
six files, because nothing failed while it was missing.

WHAT COUNTS AS A SYSTEM GLOSSARY: a file git tracks in this checkout whose
name ends `-glossary.md`, other than the project glossary itself, which
matches the same pattern and cannot be asked to list itself. The list comes
from `git ls-files -- '*-glossary.md'`, as scripts/run-all-test-suites.py
lists the suites it runs. A system whose glossary is named otherwise is
invisible here, which is the known limit of a name-based rule and the reason
the check runs both ways: a listed path git does not track fails too, so a
rename cannot leave the page pointing at nothing. A new glossary git does
not track yet is not checked -- add or commit it first, as
run-all-test-suites.py says of a new suite.

WHY GIT'S LIST AND NOT THE DIRECTORY TREE (user-ruled 2026-09-22, on the
finding both reviewers of PR "The skills glossary, and the project
glossary's list of system glossaries",
https://github.com/nedschorus/nedschorus/pull/633, raised and reproduced
independently). The first version of this test walked the checkout with
rglob, so a checkout holding an agent worktree at `.claude/worktrees/<name>/`
-- the project's documented home for them, see
docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md --
failed, reporting that worktree's copies of all three glossaries as unlisted
and instructing the agent to add those worktree paths to the page; once the
worktree was removed those same paths failed the other direction. The check
asks whether THIS checkout's committed page lists THIS checkout's committed
glossaries. Both halves are per-worktree and per-commit, so the tool that
answers it is too. Walking the filesystem answers "what files are on this
disk", a different question nobody asked. A nested worktree's copies are not
in the parent's index, so git never lists them, and nothing here excludes a
directory by name: the skip list the first version carried is gone and does
not come back.

THE PARAGRAPH, NOT THE PAGE (user-ruled 2026-09-22, on the second finding).
A glossary counts as listed only when the paragraph names it, not when any
part of the page does: the skills glossary's path also appears in the
approval-walk entry, so a page that dropped it from the paragraph used to
pass. The user's reason for tightening it: "Let's not assume agents have
perfect recall. So let's be cautious." The paragraph is the one carrying the
wording SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR holds. When no paragraph carries
that wording, or several do, this test fails saying the paragraph could not
be located, and the listing case fails with it: a check that cannot find
what it checks must never pass with nothing checked. The wording is the
paragraph's own promise sentence, because the sentence that opens its list,
"The system glossaries are", is carried by the system-term entry as well --
measured on the page 2026-09-22, when that wording was the anchor and this
test reported two paragraphs rather than checking the wrong one.

PATHS WRITTEN AS LINKS (user-ruled 2026-09-22, on the third finding, whose
ruling was worded "Include links"). A path written as a Markdown link counts
as naming it, and splitting the page on whitespace does not see one: it made
the token `glossary](../../.claude/skills/skills-glossary.md`, which the
second check then reported as a path that does not exist. So a link's target
is read out of it and the rest of the link left to the whitespace split.
Every path the page names is then read two ways, from the repository root
and relative to the page naming it, and it resolves when either reading is a
glossary git tracks; a leading `/` is read from the repository root, as
scripts/md-drift-lint.py reads one. That lint's resolve() is not reused
here: it resolves a path by whether the file exists on disk, the instrument
the first finding rejected, and it would resolve a nested worktree's copy.

WHAT THE CASES RUN AGAINST. The promise's cases are one function of a
checkout, so the same code judges the real checkout and the scratch
checkouts built below -- real repositories with real commits, because
`git ls-files` is what is under test and a mocked file list would prove
nothing.

Run: python3 scripts/system-glossaries-listed-on-the-project-glossary-test.py
"""

import posixpath
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
THIS_SUITE_RELATIVE_PATH = "scripts/" + Path(__file__).name
PROJECT_GLOSSARY_RELATIVE_PATH = "docs/nedschorus-wiki/nedschorus-glossary.md"
PROJECT_GLOSSARY_DIRECTORY = posixpath.dirname(PROJECT_GLOSSARY_RELATIVE_PATH)
GLOSSARY_SUFFIX = "-glossary.md"
GLOSSARY_PATHSPEC = "*" + GLOSSARY_SUFFIX
SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR = "A new system glossary is listed here when it is created"
# The shape scripts/md-drift-lint.py reads a Markdown link by, word for word.
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")

PARAGRAPH_LOCATED_CASE = (
    "the project glossary's paragraph listing the system glossaries is located")
EVERY_GLOSSARY_LISTED_CASE = "every system glossary is listed in that paragraph"
EVERY_NAMED_PATH_TRACKED_CASE = (
    "every glossary path the project glossary names is one git tracks")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(checkout, *arguments):
    return subprocess.run(["git", "-C", str(checkout), *arguments],
                          capture_output=True, text=True, check=False)


class CouldNotListGlossaries(Exception):
    """git could not list the checkout's tracked files."""


def glossary_paths_git_tracks(repo_root):
    """Every `*-glossary.md` file git tracks, as repository-relative paths,
    sorted. Run from the checkout's top directory, because `git ls-files`
    from a subdirectory lists only that subdirectory."""
    listed = git(repo_root, "ls-files", "-z", "--", GLOSSARY_PATHSPEC)
    if listed.returncode != 0:
        raise CouldNotListGlossaries(
            f"git ls-files failed in {repo_root}: {listed.stderr.strip()} — "
            f"fix what git reports, then run this suite again")
    return sorted(path for path in listed.stdout.split("\0") if path)


def system_glossary_paragraph(page_text):
    """The page's one paragraph listing the system glossaries, and the fault
    when it cannot be located: (paragraph, "") or (None, fault)."""
    carrying = [paragraph for paragraph in page_text.split("\n\n")
                if SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in paragraph]
    if len(carrying) == 1:
        return carrying[0], ""
    if not carrying:
        return None, (
            f'the paragraph could not be located: no paragraph of '
            f'{PROJECT_GLOSSARY_RELATIVE_PATH} carries "'
            f'{SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR}" — put that wording back in the '
            f'paragraph above the entries, or set '
            f'SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR in {THIS_SUITE_RELATIVE_PATH} to '
            f'wording that paragraph carries')
    return None, (
        f'the paragraph could not be located: {len(carrying)} paragraphs of '
        f'{PROJECT_GLOSSARY_RELATIVE_PATH} carry "'
        f'{SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR}" — leave that wording in the one '
        f'paragraph above the entries, or set SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR '
        f'in {THIS_SUITE_RELATIVE_PATH} to wording only that paragraph carries')


def repository_relative_readings(written_path):
    """The repository-relative paths a path written on the project glossary
    could mean: read from the repository root, and read relative to the page
    that names it. A reading that climbs out of the checkout is dropped."""
    from_root = written_path.lstrip("/") or written_path
    readings = []
    for base in ("", PROJECT_GLOSSARY_DIRECTORY):
        reading = posixpath.normpath(posixpath.join(base, from_root))
        if reading == ".." or reading.startswith("../"):
            continue
        readings.append(reading)
    return readings


def glossary_paths_named_in(text):
    """Every `*-glossary.md` path the text names, as (as written, the
    repository-relative paths it could mean) pairs."""
    written = []
    for link in MARKDOWN_LINK.finditer(text):
        target = link.group(1)
        if "://" in target or target.startswith(("mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if target.endswith(GLOSSARY_SUFFIX):
            written.append(target)
    # The link's target goes and its label stays, so a path backticked inside
    # a label is still seen and the `glossary](../..` token is never made.
    outside_links = MARKDOWN_LINK.sub(
        lambda link: link.group(0).rsplit("](", 1)[0] + " ", text)
    for word in outside_links.replace("`", " ").split():
        # Only the trailing punctuation goes: a leading dot is part of the
        # path, as `.claude/skills/skills-glossary.md` is.
        candidate = word.lstrip("([").rstrip(".,;:)]")
        if candidate.endswith(GLOSSARY_SUFFIX):
            written.append(candidate)
    return [(path, repository_relative_readings(path)) for path in written]


def unlisted(paragraph, system_glossaries):
    """The system glossaries the paragraph does not name."""
    named = {reading for _, readings in glossary_paths_named_in(paragraph)
             for reading in readings}
    return [path for path in system_glossaries if path not in named]


def named_but_not_tracked(page_text, tracked_glossaries):
    """The glossary paths the page names that git does not track: a rename
    or a deletion that left the page pointing at nothing."""
    absent = []
    for written, readings in glossary_paths_named_in(page_text):
        if "/" not in written:
            # A bare file name, not a path: the prose is naming a file it
            # located elsewhere, and there is nothing to resolve.
            continue
        if not set(readings) & set(tracked_glossaries):
            absent.append(written)
    return sorted(set(absent))


def project_glossary_promise_cases(repo_root):
    """Every case the project glossary's promise makes of a checkout, as
    (case name, passed, detail) triples."""
    try:
        tracked = glossary_paths_git_tracks(repo_root)
    except CouldNotListGlossaries as refusal:
        return [("git lists the checkout's tracked glossaries", False, str(refusal))]

    page_path = repo_root / PROJECT_GLOSSARY_RELATIVE_PATH
    if not page_path.is_file():
        return [("the checkout holds the project glossary", False,
                 f"no file at {PROJECT_GLOSSARY_RELATIVE_PATH} in {repo_root} — "
                 f"run this suite in a checkout that holds the project glossary")]
    page = page_path.read_text(encoding="utf-8")

    # The project glossary matches the same pattern as the glossaries it
    # lists, and cannot be asked to list itself.
    system_glossaries = [path for path in tracked
                         if path != PROJECT_GLOSSARY_RELATIVE_PATH]
    cases = [("the checkout has at least one system glossary to check",
              bool(system_glossaries),
              f"git lists no {GLOSSARY_PATHSPEC} file in {repo_root} besides "
              f"{PROJECT_GLOSSARY_RELATIVE_PATH} — commit the system glossaries, "
              f"or change {THIS_SUITE_RELATIVE_PATH} if the naming changed")]

    paragraph, paragraph_fault = system_glossary_paragraph(page)
    cases.append((PARAGRAPH_LOCATED_CASE, paragraph is not None, paragraph_fault))
    if paragraph is None:
        cases.append((EVERY_GLOSSARY_LISTED_CASE, False,
                      f'nothing was checked: the paragraph could not be located — '
                      f'clear the "{PARAGRAPH_LOCATED_CASE}" case first'))
    else:
        not_listed = unlisted(paragraph, system_glossaries)
        cases.append((EVERY_GLOSSARY_LISTED_CASE, not not_listed,
                      f"not listed: {not_listed} — add each to the paragraph above "
                      f"the entries in {PROJECT_GLOSSARY_RELATIVE_PATH}"))

    absent = named_but_not_tracked(page, tracked)
    cases.append((EVERY_NAMED_PATH_TRACKED_CASE, not absent,
                  f"named but not tracked: {absent} — correct each in "
                  f"{PROJECT_GLOSSARY_RELATIVE_PATH} to a path git tracks, or "
                  f"commit the file it names"))
    return cases


def failing_case_details(cases):
    """What a run against a checkout faulted, as `case name: detail` lines."""
    return [f"{name}: {detail}" for name, passed, detail in cases if not passed]


def case_passed(cases, case_name):
    return any(passed for name, passed, _ in cases if name == case_name)


def write_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_scratch_checkout(root, page_text, tracked_glossaries=(),
                           untracked_glossaries=()):
    """A committed checkout holding the project glossary page and the system
    glossaries named, plus any glossary written but never added, so a case
    can tell git's list from what is on the disk."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@nedschorus.invalid")
    git(root, "config", "user.name", "system-glossaries-listed test")
    write_file(root / PROJECT_GLOSSARY_RELATIVE_PATH, page_text)
    for relative in tracked_glossaries:
        write_file(root / relative, f"# {relative}\n")
    git(root, "add", "-A")
    committed = git(root, "commit", "-qm",
                    "the project glossary and its system glossaries")
    if committed.returncode != 0:
        # Loudly, rather than leave a case judging an empty index.
        raise RuntimeError(f"the scratch checkout {root} could not be committed: "
                           f"{committed.stderr.strip()}")
    for relative in untracked_glossaries:
        write_file(root / relative, f"# {relative}\n")
    return root


def scratch_project_glossary_page(listing_sentence, entries=""):
    """A stand-in for the project glossary: a paragraph listing the system
    glossaries, above the entries."""
    return (f"# a scratch project glossary\n\n"
            f"A page standing in for {PROJECT_GLOSSARY_RELATIVE_PATH}.\n\n"
            f"A term used by one system alone is defined in that system's "
            f"glossary, not here. The system glossaries are {listing_sentence} "
            f"{SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR}.\n\n"
            f"- **a-term** — a term of the project.\n{entries}")


SCRATCH_SKILLS_GLOSSARY = ".claude/skills/skills-glossary.md"
SCRATCH_DESIGN_TO_MAIN_GLOSSARY = "docs/design-to-main/design-to-main-glossary.md"
SCRATCH_HANDOFF_GLOSSARY = "nc-systems/handoff/handoff-glossary.md"


if __name__ == "__main__":
    # --- the promise, against the checkout this file is in ------------------
    for case_name, passed, fault in project_glossary_promise_cases(REPO_ROOT):
        check(case_name, passed, fault)

    # --- the promise's own machinery, against scratch checkouts -------------
    with tempfile.TemporaryDirectory() as workspace:
        scratch = Path(workspace)

        # An agent worktree nested in the checkout, the way the Agent tool's
        # worktree isolation makes one: a second copy of every glossary, at
        # paths the parent's index never holds. Both reviewers of the pull
        # request the docstring cites reproduced the first version failing here.
        with_worktree = build_scratch_checkout(
            scratch / "checkout-with-a-nested-agent-worktree",
            scratch_project_glossary_page(
                f"`{SCRATCH_SKILLS_GLOSSARY}` and "
                f"`{SCRATCH_DESIGN_TO_MAIN_GLOSSARY}`."),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,
                                SCRATCH_DESIGN_TO_MAIN_GLOSSARY))
        nested = with_worktree / ".claude" / "worktrees" / "agent-probe"
        git(with_worktree, "worktree", "add", "-q", "-b", "agent-probe-branch",
            str(nested), "HEAD")
        nested_copies = [nested / relative
                         for relative in (PROJECT_GLOSSARY_RELATIVE_PATH,
                                          SCRATCH_SKILLS_GLOSSARY,
                                          SCRATCH_DESIGN_TO_MAIN_GLOSSARY)]
        check("the nested agent worktree holds its own copy of every glossary",
              all(copy.is_file() for copy in nested_copies),
              f"git worktree add left no copy under {nested}, so the case below "
              f"would prove nothing")
        faults = failing_case_details(project_glossary_promise_cases(with_worktree))
        check("a checkout holding an agent worktree passes",
              not faults, faults)

        # A tracked glossary the paragraph does not name.
        missing_one = build_scratch_checkout(
            scratch / "checkout-missing-one-from-the-paragraph",
            scratch_project_glossary_page(f"`{SCRATCH_SKILLS_GLOSSARY}`."),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,
                                SCRATCH_DESIGN_TO_MAIN_GLOSSARY))
        faults = failing_case_details(project_glossary_promise_cases(missing_one))
        check("a tracked glossary the paragraph does not name is faulted by name",
              any(SCRATCH_DESIGN_TO_MAIN_GLOSSARY in fault for fault in faults),
              faults)

        # The same glossary named in an entry and not in the paragraph: what
        # the first version's whole-page check let pass.
        only_in_an_entry = build_scratch_checkout(
            scratch / "checkout-naming-a-glossary-only-in-an-entry",
            scratch_project_glossary_page(
                f"`{SCRATCH_SKILLS_GLOSSARY}`.",
                entries=(f"- **a-spreading-term** — defined in "
                         f"`{SCRATCH_DESIGN_TO_MAIN_GLOSSARY}` and listed here "
                         f"because this page uses it.\n")),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,
                                SCRATCH_DESIGN_TO_MAIN_GLOSSARY))
        faults = failing_case_details(project_glossary_promise_cases(only_in_an_entry))
        check("a glossary named in an entry but not in the paragraph is faulted",
              any(SCRATCH_DESIGN_TO_MAIN_GLOSSARY in fault for fault in faults),
              faults)

        # A page whose paragraph carries none of the anchor's wording. The
        # listing case must fail with it rather than pass having checked
        # nothing.
        no_paragraph = build_scratch_checkout(
            scratch / "checkout-whose-paragraph-cannot-be-located",
            "# a scratch project glossary\n\n"
            "Each system keeps its own glossary, and this page once said "
            "which.\n\n"
            "- **a-term** — a term of the project.\n",
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,))
        cases = project_glossary_promise_cases(no_paragraph)
        faults = failing_case_details(cases)
        check("a page whose paragraph cannot be located is faulted, saying so",
              any("could not be located" in fault for fault in faults), faults)
        check("with the paragraph not located, the listing case does not pass",
              not case_passed(cases, EVERY_GLOSSARY_LISTED_CASE), cases)

        # A page carrying the anchor's wording twice: which paragraph holds
        # the list is then a guess, so the test refuses to guess. This is the
        # real page's shape under the anchor first tried here, the sentence
        # "The system glossaries are", which its system-term entry carries too.
        two_paragraphs = build_scratch_checkout(
            scratch / "checkout-carrying-the-anchor-twice",
            scratch_project_glossary_page(
                f"`{SCRATCH_SKILLS_GLOSSARY}`.",
                entries=(f"- **system-term** — a term one system alone uses. "
                         f"{SYSTEM_GLOSSARY_PARAGRAPH_ANCHOR}.\n")),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,))
        cases = project_glossary_promise_cases(two_paragraphs)
        check("a page carrying the paragraph's wording twice is faulted, saying so",
              any("could not be located" in fault
                  for fault in failing_case_details(cases)), cases)
        check("with the paragraph ambiguous, the listing case does not pass",
              not case_passed(cases, EVERY_GLOSSARY_LISTED_CASE), cases)

        # The three ways a correct page writes a path. The backticked one is
        # also the leading-dot regression: the first run of this test read
        # `.claude/skills/skills-glossary.md` as `claude/skills/...` and
        # reported the page's own listing as dangling.
        every_link_form = build_scratch_checkout(
            scratch / "checkout-naming-its-glossaries-three-ways",
            scratch_project_glossary_page(
                f"`{SCRATCH_SKILLS_GLOSSARY}`, "
                f"[the design-to-main glossary](../design-to-main/"
                f"design-to-main-glossary.md) and "
                f"[the handoff glossary]({SCRATCH_HANDOFF_GLOSSARY})."),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,
                                SCRATCH_DESIGN_TO_MAIN_GLOSSARY,
                                SCRATCH_HANDOFF_GLOSSARY))
        faults = failing_case_details(project_glossary_promise_cases(every_link_form))
        check("a backticked path, a page-relative link and a repository-relative "
              "link all resolve",
              not faults, faults)

        # A path the page names that git does not track, written to the disk
        # so that only git's list can tell it from a glossary.
        names_an_untracked_path = build_scratch_checkout(
            scratch / "checkout-naming-an-untracked-glossary",
            scratch_project_glossary_page(
                f"`{SCRATCH_SKILLS_GLOSSARY}` and `docs/gone/gone-glossary.md`."),
            tracked_glossaries=(SCRATCH_SKILLS_GLOSSARY,),
            untracked_glossaries=("docs/gone/gone-glossary.md",))
        check("the untracked glossary is on the disk",
              (names_an_untracked_path / "docs/gone/gone-glossary.md").is_file(),
              "the untracked file was not written, so the case below would "
              "prove nothing")
        faults = failing_case_details(
            project_glossary_promise_cases(names_an_untracked_path))
        check("a path the page names that git does not track is faulted by name",
              any("docs/gone/gone-glossary.md" in fault for fault in faults),
              faults)

    sys.exit(1 if failures else 0)
