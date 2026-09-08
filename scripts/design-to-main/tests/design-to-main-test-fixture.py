#!/usr/bin/env python3
"""Shared fixture for the design-to-main machine's tests: loads the machine
through importlib (hyphenated file names), builds a throwaway repository
with a bare `origin` carrying `main`, and drives the machine through a
scripted launcher.

Not a test file; the three *-test.py files beside it load it.
"""

import importlib.util
import pathlib
import shutil
import subprocess
import tempfile

MACHINE_DIR = pathlib.Path(__file__).resolve().parent.parent


def load_machine_module():
    spec = importlib.util.spec_from_file_location(
        "design_to_main_state_machine", MACHINE_DIR / "design-to-main-state-machine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


machine_module = load_machine_module()
tables = machine_module.tables
run_state_module = machine_module.run_state_module
git_record_module = machine_module.git_record_module

COMPONENT = "widget-counter"
COMPONENT_DIRECTORY = "scripts/widget-counter"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args),
                          check=True, capture_output=True, text=True).stdout


class ThrowawayRepository:
    """A working checkout of `main` with a bare origin, in a temp dir."""

    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="design-to-main-test-"))
        self.origin = self.root / "origin.git"
        self.checkout = self.root / "checkout"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.checkout)],
                       check=True, capture_output=True)
        git(self.checkout, "config", "user.name", "design-to-main-test")
        git(self.checkout, "config", "user.email", "design-to-main-test@example.invalid")
        git(self.checkout, "checkout", "-q", "-b", "main")
        (self.checkout / "README.md").write_text("main\n")
        git(self.checkout, "add", "-A")
        git(self.checkout, "commit", "-q", "-m", "main: first commit")
        git(self.checkout, "push", "-q", "-u", "origin", "main")
        self.origin_refs_at_start = self.origin_refs()

    def origin_refs(self):
        return git(self.checkout, "ls-remote", str(self.origin))

    def remove(self):
        shutil.rmtree(self.root, ignore_errors=True)


def make_machine(script, repository=None):
    """A machine over a throwaway repository, driven by `script`."""
    repository = repository or ThrowawayRepository()
    record = git_record_module.TopicBranchGitRecord(
        repository.checkout, COMPONENT, COMPONENT_DIRECTORY)
    launcher = machine_module.ScriptedStateExitLauncher(script)
    machine = machine_module.DesignToMainStateMachineFlow(
        record, launcher, today=lambda: "2026-09-08")
    run = machine.start(COMPONENT)
    return machine, run, record, repository


def drive(machine, run, max_steps=200):
    """Run until the script is exhausted or the run ends; returns the run."""
    steps = 0
    while run.current_state != tables.ENDED and machine.launcher.script:
        try:
            machine.step(run)
        except machine_module.ScriptedStateExitLauncherExhausted:
            # A reviewing state runs its sub-states in one step; the run
            # stands at the sub-state the script did not reach.
            break
        steps += 1
        if steps > max_steps:
            raise RuntimeError("did not finish within %d steps" % max_steps)
    return run


# Scripts that reach known points of a run.

def prefix_to_design_approved():
    return [
        (tables.INITIATE_DESIGN_TO_MAIN, tables.V_INVOKED, {}),
        (tables.DESIGN_WRITING, tables.V_EMITTED, {}),
        (tables.CONTRACT_ACCEPTANCE_BY_PROGRAM, tables.V_ADVANCE, {}),
        (tables.DESIGN_ACCEPTANCE_BY_AGENT, tables.V_ADVANCE, {}),
        (tables.DESIGN_ACCEPTANCE_BY_USER, tables.V_ADVANCE, {}),
    ]


def implementation_write(coverage_type="script"):
    return (tables.IMPLEMENTATION_WRITING, tables.V_EMITTED, {"coverage_type": coverage_type})


def test_write(coverage_type="script"):
    return (tables.TEST_WRITING, tables.V_EMITTED, {"coverage_type": coverage_type})


def prefix_to_tests_begun():
    """Design approved, first implementation-write accepted; the test-work-
    stream is at test-design-writing."""
    return prefix_to_design_approved() + [
        implementation_write(),
        (tables.IMPLEMENTATION_ACCEPTANCE_BY_AGENT, tables.V_ADVANCE, {}),
    ]


def prefix_to_test_writing():
    return prefix_to_tests_begun() + [
        (tables.TEST_DESIGN_WRITING, tables.V_EMITTED, {}),
        (tables.TEST_DESIGN_ACCEPTANCE_BY_AGENT, tables.V_ADVANCE, {}),
        (tables.TEST_DESIGN_ACCEPTANCE_BY_USER, tables.V_ADVANCE, {}),
    ]


def whole_run_to_passed():
    return prefix_to_test_writing() + [
        test_write(),
        (tables.TEST_ACCEPTANCE_BY_AGENT, tables.V_ADVANCE, {}),
        (tables.TEST_SUITE_EXECUTING, tables.V_PASS, {}),
        (tables.SUBMIT_TO_PR_GATE, tables.V_ACCEPTED, {}),
    ]
