#!/usr/bin/env python3
"""Record topic-branch state exits and recovery changes locally; pushing is the caller's responsibility."""

import importlib.util
import pathlib
import subprocess

_tables_spec = importlib.util.spec_from_file_location(
    "design_to_main_state_tables",
    pathlib.Path(__file__).with_name("design-to-main-state-tables.py"))
tables = importlib.util.module_from_spec(_tables_spec)
_tables_spec.loader.exec_module(tables)


def compose_state_exit_trailer(state, verdict, package_commit, counters, write_number=None):
    """Compose state-exit trailers, optionally including a counted or forced write."""
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
    """Return recognized state-exit trailer fields as a dict."""
    trailer = {}
    for line in message.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in ("State", "Exit", "Package-commit", "Write") or key.startswith("Counter-"):
                trailer[key] = value
    return trailer


class TopicBranchCutRefused(Exception):
    """Git refused the branch name or the required start point is absent."""


class RefusedBeforeTopicBranchCut(Exception):
    """Refuse checkout changes until this run has cut and checked out its topic branch."""


class TopicBranchGitRecord:
    """The component's topic branch in one repository checkout."""

    def __init__(self, repository_dir, component, component_directory,
                 design_path, topic_branch_start_point="origin/main"):
        self.repository_dir = pathlib.Path(repository_dir)
        self.component = component
        # The design is refined in its issue document before code exists; the contract stays beside it.
        self.design_path = str(design_path)
        # Use the same start point for branch creation and instance counting so recovery counts the same span.
        self.topic_branch_start_point = topic_branch_start_point
        self.component_directory = pathlib.Path(component_directory)
        self.record_directory = self.component_directory / tables.RECORD_DIRECTORY_NAME


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
        """Return the first commit after commit, or None at HEAD."""
        # The record stores the opening commit's parent because a commit cannot contain its own hash.
        commits = self.commits_on_branch(since=commit)
        return commits[-1] if commits else None


    def require_topic_branch_start_point(self):
        # Validate before assembling the initial package: instance counting needs the start point before branch creation.
        start_point = self.topic_branch_start_point
        if self.git("rev-parse", "--verify", "--quiet",
                    "%s^{commit}" % start_point, check=False).returncode != 0:
            raise TopicBranchCutRefused(
                "the checkout at %s has no %s to cut the topic branch %r from; "
                "the run does not start and the checkout is as it was" % (
                    self.repository_dir, start_point, self.component))

    def cut_topic_branch(self):
        """Create the component branch, raising TopicBranchCutRefused on refusal."""
        start_point = self.topic_branch_start_point
        cut = self.git("checkout", "-b", self.component, start_point, check=False)
        if cut.returncode != 0:
            raise TopicBranchCutRefused(
                "git refused to cut the topic branch %r from %s: %s" % (
                    self.component, start_point, cut.stderr.strip()))
        # Create the directory after the cut so refusal leaves no files behind.
        self.absolute(self.record_directory).mkdir(parents=True, exist_ok=True)
        return self.head_commit()

    def topic_branch_is_checked_out(self):
        # The branch name alone does not prove this run cut the branch; a finished run can leave the same name checked out.
        return self.current_branch() == self.component

    def require_topic_branch_cut_for_run(self, run, action):
        # Before the cut, the checkout belongs to the invoker; after the cut, reject a checkout switched to another branch.
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


    @property
    def run_state_path(self):
        return self.record_directory / tables.RUN_STATE_FILE_NAME

    @property
    def user_rulings_path(self):
        return self.record_directory / tables.USER_RULINGS_FILE_NAME


    def evidence_directory_for_instance(self, state_or_sub_state, instance_number):
        """Return the repository-relative evidence directory for a one-based instance number."""
        return (self.record_directory / tables.EVIDENCE_DIRECTORY_NAME
                / ("%s-%d" % (state_or_sub_state, instance_number)))

    def notes_path_for_instance(self, state_or_sub_state, instance_number):
        return self.evidence_directory_for_instance(state_or_sub_state, instance_number) / tables.NOTES_FILE_NAME

    def state_exit_path_for_instance(self, state_or_sub_state, instance_number):
        return (self.evidence_directory_for_instance(state_or_sub_state, instance_number)
                / tables.STATE_EXIT_FILE_NAME)

    def instances_of_state_so_far(self, state_or_sub_state):
        """Count committed instances across the run, including stale and refused exits."""
        # Exclude ancestry before the cut: merged runs must not contribute to this run's numbering.
        states = self.git("log", "--format=%(trailers:key=State,valueonly)",
                          "%s..HEAD" % self.topic_branch_start_point).stdout.split("\n")
        return sum(1 for line in states if line.strip() == state_or_sub_state)

    def evidence_directory_for_the_next_instance(self, state_or_sub_state):
        return self.evidence_directory_for_instance(
            state_or_sub_state, self.instances_of_state_so_far(state_or_sub_state) + 1)


    def investigation_report_path_for_instance(self, instance_number):
        """Return the repository-relative report path for a one-based investigation number."""
        return (self.record_directory / tables.INVESTIGATION_REPORTS_DIRECTORY_NAME
                / (tables.INVESTIGATION_REPORT_FILE_NAME_FORMAT % instance_number))

    def investigation_report_path_for_the_next_instance(self):
        return self.investigation_report_path_for_instance(
            self.instances_of_state_so_far(tables.INVESTIGATE_WORKFLOW) + 1)

    def investigation_report_path_of_the_latest_instance(self):
        return self.investigation_report_path_for_instance(
            self.instances_of_state_so_far(tables.INVESTIGATE_WORKFLOW))

    def absolute(self, relative):
        return self.repository_dir / relative

    def append_user_ruling(self, run, text, date):
        # Guard before writing so a refused invocation leaves no ruling behind.
        self.require_topic_branch_cut_for_run(run, "write a user ruling")
        path = self.absolute(self.user_rulings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as rulings:
            rulings.write("- %s (user-ruled %s)\n" % (text, date))

    def run_state_text_at_last_commit(self):
        """Return the run-state.json text at HEAD, or None when absent."""
        shown = self.git("show", "HEAD:%s" % self.run_state_path, check=False)
        if shown.returncode != 0:
            return None
        return shown.stdout


    def commit_state_exit(self, run, subject, trailer, named_files=()):
        """Commit the record and named files, allowing empty state exits."""
        # Do not stage the whole worktree: other files may contain a paused agent's unfinished work.
        self.require_topic_branch_cut_for_run(run, "commit a state-exit")
        # Path-scoped add -A also stages deletions; validate never-existing paths before calling Git.
        self.git("add", "-A", "--", str(self.record_directory), *named_files)
        message = subject + "\n\n" + trailer
        self.git("commit", "--allow-empty", "-q", "-m", message)
        return self.head_commit()

    def named_files_that_are_not_there(self, named_files):
        """Return paths absent from both the worktree and HEAD, excluding tracked deletions."""
        missing = []
        for path in named_files:
            if self.absolute(path).exists():
                continue
            tracked = self.git("cat-file", "-e", "HEAD:%s" % path, check=False)
            if tracked.returncode != 0:
                missing.append(path)
        return missing


    def discard_every_change_the_commit_did_not_carry(self, run):
        self.require_topic_branch_cut_for_run(run, "discard what the commit did not carry")
        self.put_the_whole_checkout_back_to_head()


    def discard_all_uncommitted_work_for_recovery(self, run):
        # Recovery must read the run from the last commit before discarding uncommitted work.
        self.require_topic_branch_cut_for_run(run, "discard a dead process's uncommitted work")
        self.put_the_whole_checkout_back_to_head()

    def put_the_whole_checkout_back_to_head(self):
        # Reset the index first: checkout restores from the index, so staged work would otherwise survive recovery.
        self.git("reset", "-q", check=False)
        self.git("checkout", "--", ".", check=False)
        self.git("clean", "-fdq", check=False)


    def paths_changed_since(self, commit):
        """Return committed and uncommitted changes since commit, excluding the record directory."""
        changed = set(self.git("diff", "--name-only", commit).stdout.split())
        changed |= set(self.git("ls-files", "--others", "--exclude-standard").stdout.split())
        record = str(self.record_directory)
        return sorted(p for p in changed if not p.startswith(record + "/"))

    @property
    def test_design_path(self):
        return self.component_directory / ("%s-test-design.md" % self.component)

    def test_design_text(self):
        """Return the working-tree test-design text, or None when absent."""
        path = self.absolute(self.test_design_path)
        if not path.exists():
            return None
        return path.read_text()

    def document_of_path(self, path):
        """Classify a path as design, design-contract, test-design, tests, or implementation."""
        component_dir = str(self.component_directory)
        if path in (self.design_path,
                    "%s/%s-design.md" % (component_dir, self.component)):
            return "design"
        if path in (tables.contract_path_beside_design(self.design_path),
                    "%s/%s-contract.md" % (component_dir, self.component)):
            return "design-contract"
        if path == str(self.test_design_path):
            return "test-design"
        if path.startswith(component_dir + "/tests/"):
            return "tests"
        if path.startswith(component_dir + "/"):
            return "implementation"
        return None

    def earliest_state_downstream_of_changes(self, since_commit):
        """Return the resume destination implied by changed paths, or None."""
        documents = {self.document_of_path(p) for p in self.paths_changed_since(since_commit)}
        for document, state in tables.RESUME_DESTINATION_BY_EDITED_DOCUMENT:
            if document in documents:
                return state
        return None
