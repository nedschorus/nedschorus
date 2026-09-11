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
    `Write:` (for writes: the number the writer's counter reached, or
    `forced` for a write forced by an upstream change or ordered by the
    arbitrator, which that counter does not count), and every counter as
    `Counter-<name>:`, on the model of the gatekeeper's trailer."""
    lines = [
        "State: %s" % state,
        "Exit: %s" % verdict,
        "Package-commit: %s" % package_commit,
    ]
    if write_number is not None:
        lines.append("Write: %s" % write_number)
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
    """Something asked to discard or commit for a run that row 1 has not
    yet routed — its topic branch not cut — while the checkout is still
    the invoking conversation's, on whatever branch it stood on (`main`,
    or the topic branch a finished run for the same component left it
    on), with whatever uncommitted work the invoker had. Until row 1 cuts
    the branch the machine owns nothing in the checkout, so it refuses:
    the refusal is the report to the invoking conversation, the run does
    not start, and the checkout is as it was. A sibling of
    TopicBranchCutRefused rather than a widening of it: that one carries
    git's refusal of the name at the cut; this one carries what the machine
    refused to do before any cut — a state-exit from
    initiate-design-to-main other than `invoked`, or (the structural
    backstop, in TopicBranchGitRecord) a discard or a commit for a run
    whose `topic-branch-cut` flag is not set, or with the checkout off
    the run's topic branch."""


class TopicBranchGitRecord:
    """The component's topic branch in one repository checkout."""

    def __init__(self, repository_dir, component, component_directory,
                 topic_branch_start_point="origin/main"):
        self.repository_dir = pathlib.Path(repository_dir)
        self.component = component
        # Where the topic branch is cut from (section 9: `origin/main`),
        # and so where the run's own commits begin: the cut and the count
        # of a state's instances (instances_of_state_so_far) both read it,
        # so a successor process recovering the run counts the same span
        # without a cut of its own.
        self.topic_branch_start_point = topic_branch_start_point
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

    def first_commit_after(self, commit):
        """The commit that follows `commit` on the branch, or None when
        HEAD is `commit`. run-state.json records the PARENT of the commit
        that opened an investigation (a commit's own SHA cannot be written
        into a file it contains), and the resume diff of section 6.6 runs
        against the opening commit itself: this is how it is found."""
        commits = self.commits_on_branch(since=commit)
        return commits[-1] if commits else None

    # -- section 9: the topic branch ----------------------------------------

    def cut_topic_branch(self):
        """Cut the topic branch from `origin/main`, named for the component,
        naming the start point explicitly (the topic-branch rule,
        docs/issues/238-topic-branch-creation-script-design.md). A refusal
        — the branch already exists, as after a run that ended failed —
        is TopicBranchCutRefused, an ordinary outcome rather than a crash,
        as the topic-branch rule has it."""
        start_point = self.topic_branch_start_point
        cut = self.git("checkout", "-b", self.component, start_point, check=False)
        if cut.returncode != 0:
            raise TopicBranchCutRefused(
                "git refused to cut the topic branch %r from %s: %s" % (
                    self.component, start_point, cut.stderr.strip()))
        # Section 9: the component's directory is created when the branch
        # is cut, holding only the record until code exists (user-ruled
        # 2026-09-08, the eighth walk, item 3). After the cut, so that a
        # refused cut leaves nothing behind.
        self.absolute(self.record_directory).mkdir(parents=True, exist_ok=True)
        return self.head_commit()

    def topic_branch_is_checked_out(self):
        """Whether the checkout stands on the run's topic branch, the branch
        named for the component (section 9). Read from git each time. This
        alone cannot stand for "row 1 has cut the branch": this slice's
        only branch switch is that cut, so a finished run leaves the
        checkout on its topic branch, and a fresh invocation for the same
        component from there finds the name already checked out. What
        row 1 did is the run's own record, `topic-branch-cut`
        (RunStateRecord), persisted in run-state.json on the branch, which
        is how a successor process recovering a run reads it."""
        return self.current_branch() == self.component

    def require_topic_branch_cut_for_run(self, run, action):
        """The structural guard: every method here that discards or commits
        takes the run and calls this first, so nothing can reach the
        invoking conversation's checkout before row 1 has cut the run's
        topic branch — whatever path a future row takes to get here, and
        whatever branch the checkout stands on. The run's flag decides;
        the branch name is a second condition, for a checkout switched off
        the topic branch after the cut."""
        if not run.topic_branch_cut:
            raise RefusedBeforeTopicBranchCut(
                "refused to %s: row 1 has not cut the topic branch %r for this run "
                "(the checkout stands on %r); the run does not start and the checkout is as it was" % (
                    action, self.component, self.current_branch()))
        if not self.topic_branch_is_checked_out():
            raise RefusedBeforeTopicBranchCut(
                "refused to %s: the checkout stands on %r, not on the run's topic branch %r; "
                "the checkout is as it was" % (
                    action, self.current_branch(), self.component))

    # -- section 9: the record files ----------------------------------------

    @property
    def run_state_path(self):
        return self.record_directory / tables.RUN_STATE_FILE_NAME

    @property
    def user_rulings_path(self):
        return self.record_directory / tables.USER_RULINGS_FILE_NAME

    # -- section 9: evidence/<state or sub-state>-<n>/ ------------------------

    def evidence_directory_for_instance(self, state_or_sub_state, instance_number):
        """The evidence directory of the nth instance of a state or
        sub-state, n counted from 1: `implementation-writing-1` is the
        first. Relative to the repository, like every path here."""
        return (self.record_directory / tables.EVIDENCE_DIRECTORY_NAME
                / ("%s-%d" % (state_or_sub_state, instance_number)))

    def notes_path_for_instance(self, state_or_sub_state, instance_number):
        return self.evidence_directory_for_instance(state_or_sub_state, instance_number) / tables.NOTES_FILE_NAME

    def state_exit_path_for_instance(self, state_or_sub_state, instance_number):
        return (self.evidence_directory_for_instance(state_or_sub_state, instance_number)
                / tables.STATE_EXIT_FILE_NAME)

    def instances_of_state_so_far(self, state_or_sub_state):
        """How many instances of a state or sub-state this run has
        committed: the `State:` trailers on the branch above its cut from
        the start point (section 9), `origin/main..HEAD` — never all of
        HEAD's ancestry, which holds every merged run's trailers too, so
        that one merged run of another component numbered the next run's
        first instance `-2` (GHI #313). Counted over the run, not per
        design version — the design counts "the nth instance of that
        state or sub-state" and says nothing of versions (reported with
        this slice). A stale or refused state-exit is committed too, so an
        instance that was re-run counts once per launch, as its
        directories should."""
        states = self.git("log", "--format=%(trailers:key=State,valueonly)",
                          "%s..HEAD" % self.topic_branch_start_point).stdout.split("\n")
        return sum(1 for line in states if line.strip() == state_or_sub_state)

    def evidence_directory_for_the_next_instance(self, state_or_sub_state):
        return self.evidence_directory_for_instance(
            state_or_sub_state, self.instances_of_state_so_far(state_or_sub_state) + 1)

    def absolute(self, relative):
        return self.repository_dir / relative

    def append_user_ruling(self, run, text, date):
        """The user-rulings file is append-only; each ruling is marked
        user-ruled with its date. Guarded like a commit: a ruling carried
        on an invocation that is then refused is not written, so the
        refusal leaves no file behind."""
        self.require_topic_branch_cut_for_run(run, "write a user ruling")
        path = self.absolute(self.user_rulings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as rulings:
            rulings.write("- %s (user-ruled %s)\n" % (text, date))

    def run_state_text_at_last_commit(self):
        """The text of run-state.json in the commit at HEAD, or None when
        HEAD carries none: recovery (section 9) re-runs the state from the
        last commit, and reads the run from there before it discards
        anything in the checkout."""
        shown = self.git("show", "HEAD:%s" % self.run_state_path, check=False)
        if shown.returncode != 0:
            return None
        return shown.stdout

    # -- section 9: every state-exit is committed -----------------------------

    def commit_state_exit(self, run, subject, trailer, named_files=()):
        """Commit one state-exit of `run`: the record directory and the
        files the state-exit names (the artifact, the notes), the trailer
        under the subject. Never the whole worktree (section 9): a paused
        agent's half-written files, or anything else in the checkout the
        state-exit does not name, is not committed as this state's work.
        Empty commits are allowed: a retry or a discarded state-exit
        changes nothing but the record."""
        self.require_topic_branch_cut_for_run(run, "commit a state-exit")
        # `add -A` restricted to these paths stages their deletions too.
        # A named file that is not there at all is the machine's error
        # to catch before this (named_files_that_are_not_there), never
        # git's to crash on.
        self.git("add", "-A", "--", str(self.record_directory), *named_files)
        message = subject + "\n\n" + trailer
        self.git("commit", "--allow-empty", "-q", "-m", message)
        return self.head_commit()

    def named_files_that_are_not_there(self, named_files):
        """The named files that are neither in the worktree nor tracked at
        HEAD: a state-exit naming one is a machine error (section 9),
        routed like any illegal state-exit. A named file that is tracked
        and gone from the worktree is a deletion the commit carries, not
        this."""
        missing = []
        for path in named_files:
            if self.absolute(path).exists():
                continue
            tracked = self.git("cat-file", "-e", "HEAD:%s" % path, check=False)
            if tracked.returncode != 0:
                missing.append(path)
        return missing

    # -- section 9: after the commit, every other change is discarded --------

    def discard_every_change_the_commit_did_not_carry(self, run):
        """After committing a state-exit, put the whole checkout back to
        HEAD (section 9, user-ruled 2026-09-09, the eighth walk, item 7):
        the commit carried the files the state-exit named and the record,
        so what remains is what no state-exit claimed — a writer's scratch
        file, a tracked file it touched, a paused agent's half-written
        work — and the next state's worktree holds only claimed work."""
        self.require_topic_branch_cut_for_run(run, "discard what the commit did not carry")
        self.put_the_whole_checkout_back_to_head()

    # -- section 9, recovery: the dead process's uncommitted files ------------

    def discard_all_uncommitted_work_for_recovery(self, run):
        """Put the whole checkout back to HEAD, the record directory
        included: a process that died before committing a state-exit left
        files that belong to no commit (section 9). `run` is the run being
        recovered, read from the last commit before this is called."""
        self.require_topic_branch_cut_for_run(run, "discard a dead process's uncommitted work")
        self.put_the_whole_checkout_back_to_head()

    def put_the_whole_checkout_back_to_head(self):
        """The index too, not only the working tree: commit_state_exit is
        `add` of the named files then `commit`, two subprocesses, so a
        process that dies between them leaves those files STAGED.
        `checkout -- .` restores from the index and `clean` removes only
        untracked files; without the `reset` first, what was staged
        survives both into the next state-exit's commit."""
        self.git("reset", "-q", check=False)
        self.git("checkout", "--", ".", check=False)
        self.git("clean", "-fdq", check=False)

    # -- section 6.6: what the user changed in an investigation --------------

    def paths_changed_since(self, commit):
        """Committed and uncommitted changes since `commit`, ignoring the
        record directory (the report and the user-rulings file). Read
        without staging anything: `diff <commit>` is the commit against
        the working tree for tracked paths, and `ls-files --others` the
        untracked ones."""
        changed = set(self.git("diff", "--name-only", commit).stdout.split())
        changed |= set(self.git("ls-files", "--others", "--exclude-standard").stdout.split())
        record = str(self.record_directory)
        return sorted(p for p in changed if not p.startswith(record + "/"))

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
