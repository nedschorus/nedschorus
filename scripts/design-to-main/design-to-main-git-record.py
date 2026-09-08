#!/usr/bin/env python3
"""Git is the record (section 9): the topic branch, the state-exit commit
and its trailer, `run-state.json` and the user-rulings file on the branch,
and the diff an investigation resumes on.

This module never pushes. Section 9 says every state-exit is committed AND
pushed; pushing is not in this slice and no `git push` appears here. The
whole-run test asserts that origin's refs are unchanged after a run.
"""

import importlib.util
import pathlib
import subprocess

_tables_spec = importlib.util.spec_from_file_location(
    "design_to_main_state_tables",
    pathlib.Path(__file__).with_name("design-to-main-state-tables.py"))
tables = importlib.util.module_from_spec(_tables_spec)
_tables_spec.loader.exec_module(tables)


def compose_state_exit_trailer(state, verdict, package_commit, counters, write_number=None):
    """The commit trailer of section 9: `State:`, `Exit:`, `Package-commit:`,
    `Write:` (the write number, for writes), and every counter as
    `Counter-<name>:`, on the model of the gatekeeper's trailer."""
    lines = [
        "State: %s" % state,
        "Exit: %s" % verdict,
        "Package-commit: %s" % package_commit,
    ]
    if write_number is not None:
        lines.append("Write: %d" % write_number)
    for name in tables.COUNTER_NAMES:
        lines.append("Counter-%s: %d" % (name, counters[name]))
    return "\n".join(lines) + "\n"


def parse_state_exit_trailer(message):
    """The trailer back out of a commit message, as a dict."""
    trailer = {}
    for line in message.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in ("State", "Exit", "Package-commit", "Write") or key.startswith("Counter-"):
                trailer[key] = value
    return trailer


class TopicBranchCutRefused(Exception):
    """Git refused to cut the topic branch (section 6.6: the name is
    refused, the machine says so in the invoking conversation and the run
    does not start). Carries git's own words; the checkout is as it was."""


class RefusedBeforeTopicBranchCut(Exception):
    """Something asked to discard or commit before the run's topic branch
    was cut, while the checkout still stands on the invoking conversation's
    branch — `main`, with whatever uncommitted work the invoker had. Until
    row 1 cuts the branch the machine owns nothing in the checkout, so it
    refuses: the refusal is the report to the invoking conversation, the
    run does not start, and the checkout is as it was. A sibling of
    TopicBranchCutRefused rather than a widening of it: that one carries
    git's refusal of the name at the cut; this one carries what the machine
    refused to do before any cut — a state-exit from
    initiate-design-to-main other than `invoked`, or (the structural
    backstop, in TopicBranchGitRecord) a discard or a commit off the topic
    branch."""


class TopicBranchGitRecord:
    """The component's topic branch in one repository checkout."""

    def __init__(self, repository_dir, component, component_directory):
        self.repository_dir = pathlib.Path(repository_dir)
        self.component = component
        # Where the component's directory is follows the layout rule of
        # GitHub issue #224 (section 9); this slice takes it as a parameter.
        self.component_directory = pathlib.Path(component_directory)
        self.record_directory = self.component_directory / tables.RECORD_DIRECTORY_NAME

    # -- git plumbing -------------------------------------------------------

    def git(self, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(self.repository_dir)] + list(args),
            check=check, capture_output=True, text=True)

    def head_commit(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def current_branch(self):
        return self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def commit_message(self, commit):
        return self.git("log", "-1", "--format=%B", commit).stdout

    def commits_on_branch(self, since=None):
        span = "%s..HEAD" % since if since else "HEAD"
        return self.git("log", "--format=%H", span).stdout.split()

    # -- section 9: the topic branch ----------------------------------------

    def cut_topic_branch(self, start_point="origin/main"):
        """Cut the topic branch from `origin/main`, named for the component,
        naming the start point explicitly (the topic-branch rule,
        docs/issues/238-topic-branch-creation-script-design.md). A refusal
        — the branch already exists, as after a run that ended failed —
        is TopicBranchCutRefused, an ordinary outcome rather than a crash,
        as the topic-branch rule has it."""
        cut = self.git("checkout", "-b", self.component, start_point, check=False)
        if cut.returncode != 0:
            raise TopicBranchCutRefused(
                "git refused to cut the topic branch %r from %s: %s" % (
                    self.component, start_point, cut.stderr.strip()))
        return self.head_commit()

    def topic_branch_is_checked_out(self):
        """Whether the checkout stands on the run's topic branch, the branch
        named for the component (section 9). Read from git each time, not
        remembered from `cut_topic_branch`: a successor process recovering
        a run (section 9) builds a fresh record over a checkout the cut
        happened in long before."""
        return self.current_branch() == self.component

    def require_topic_branch_checked_out(self, action):
        """The structural guard: every method here that discards or commits
        calls this first, so nothing can reach the invoking conversation's
        checkout before row 1 has cut the topic branch — whatever path a
        future row takes to get here."""
        if not self.topic_branch_is_checked_out():
            raise RefusedBeforeTopicBranchCut(
                "refused to %s: the checkout stands on %r, not on the topic branch %r, "
                "which is not checked out; the run does not start and the checkout is as it was" % (
                    action, self.current_branch(), self.component))

    # -- section 9: the record files ----------------------------------------

    @property
    def run_state_path(self):
        return self.record_directory / tables.RUN_STATE_FILE_NAME

    @property
    def user_rulings_path(self):
        return self.record_directory / tables.USER_RULINGS_FILE_NAME

    def absolute(self, relative):
        return self.repository_dir / relative

    def append_user_ruling(self, text, date):
        """The user-rulings file is append-only; each ruling is marked
        user-ruled with its date."""
        path = self.absolute(self.user_rulings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as rulings:
            rulings.write("- %s (user-ruled %s)\n" % (text, date))

    # -- section 9: every state-exit is committed -----------------------------

    def commit_state_exit(self, subject, trailer):
        """Commit everything in the worktree as one state-exit, the trailer
        under the subject. Empty commits are allowed: a retry or a discarded
        state-exit changes nothing but the record."""
        self.require_topic_branch_checked_out("commit a state-exit")
        self.git("add", "-A")
        message = subject + "\n\n" + trailer
        self.git("commit", "--allow-empty", "-q", "-m", message)
        return self.head_commit()

    # -- section 6.6: the paused agent's uncommitted work is discarded --------

    def discard_uncommitted_work_outside_the_record(self):
        """Put every path outside the record directory back to HEAD:
        staged or not, modified, added or deleted, untracked. The record
        directory is kept — a ruling appended for this state-exit and a
        reviewer's notes under `evidence/` belong to the state-exit, not
        to the work that is discarded."""
        self.require_topic_branch_checked_out("discard the paused agent's uncommitted work")
        outside_the_record = [".", ":(exclude)%s" % self.record_directory]
        self.git("reset", "-q", "--", *outside_the_record)
        self.git("checkout", "--", *outside_the_record)
        self.git("clean", "-fdq", "--", *outside_the_record)

    # -- section 9, recovery: the dead process's uncommitted files ------------

    def discard_all_uncommitted_work_for_recovery(self):
        """Put the whole checkout back to HEAD, the record directory
        included: a process that died before committing a state-exit left
        files that belong to no commit (section 9)."""
        self.require_topic_branch_checked_out("discard a dead process's uncommitted work")
        self.git("checkout", "--", ".", check=False)
        self.git("clean", "-fdq", check=False)

    # -- section 6.6: what the user changed in an investigation --------------

    def paths_changed_since(self, commit):
        """Committed and uncommitted changes since `commit`, ignoring the
        record directory (the report and the user-rulings file)."""
        self.git("add", "-A")
        changed = self.git("diff", "--name-only", commit).stdout.split()
        record = str(self.record_directory)
        return [p for p in changed if not p.startswith(record + "/")]

    def document_of_path(self, path):
        """Which of section 9's documents a changed path belongs to:
        design, component-contract, test-design, tests, or implementation."""
        component_dir = str(self.component_directory)
        if path in (tables.design_path_while_no_code_exists(self.component),
                    "%s/%s-design.md" % (component_dir, self.component)):
            return "design"
        if path in (tables.contract_path_while_no_code_exists(self.component),
                    "%s/%s-contract.md" % (component_dir, self.component)):
            return "component-contract"
        if path == "%s/%s-test-design.md" % (component_dir, self.component):
            return "test-design"
        if path.startswith(component_dir + "/tests/"):
            return "tests"
        if path.startswith(component_dir + "/"):
            return "implementation"
        return None

    def earliest_state_downstream_of_changes(self, since_commit):
        """The resume destination the diff of the branch yields (section
        6.6), or None when nothing the machine routes on changed."""
        documents = {self.document_of_path(p) for p in self.paths_changed_since(since_commit)}
        for document, state in tables.RESUME_DESTINATION_BY_EDITED_DOCUMENT:
            if document in documents:
                return state
        return None
