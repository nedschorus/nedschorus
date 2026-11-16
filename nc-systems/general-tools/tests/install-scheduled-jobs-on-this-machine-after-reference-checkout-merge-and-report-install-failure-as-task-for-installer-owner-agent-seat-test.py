#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py
and scripts/git-client-side-hooks/post-merge, which runs it.

No case runs the real installer or touches a crontab or launchd: a stand-in
installer records each call and exits as the case asks, and the task lists
are under a temporary directory. Each case runs in a temporary repository
that the case names as ned-box's or the Mac's reference-checkout, or as
neither. The last cases merge through the real post-merge hook.

Run: python3 nc-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import json
import os
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = GENERAL_TOOLS.parent.parent
PROGRAM_PATH = GENERAL_TOOLS / "install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py"
HOOKS_DIRECTORY = REPOSITORY_ROOT / "scripts" / "git-client-side-hooks"
_spec = importlib.util.spec_from_file_location(
    "install_scheduled_jobs_on_this_machine_after_reference_checkout_merge_and_report_install_failure_as_task_for_installer_owner_agent_seat", PROGRAM_PATH)
after_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(after_merge)

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


STAND_IN_INSTALLER = """import os, sys
with open(os.environ["STAND_IN_INSTALLER_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
code = int(os.environ.get("STAND_IN_INSTALLER_EXIT", "0"))
if code == 0:
    print("unchanged: transcript-mirror-to-log-store — the crontab holds the table's line.")
elif code == 2:
    print("install-scheduled-jobs-on-this-machine: not run — job `x` runs /nowhere/x.py, "
          "which is not a file on this machine.", file=sys.stderr)
else:
    print("FAILED: the crontab write did not hold", file=sys.stderr)
sys.exit(code)
"""

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    installer_log = scratch / "installer.log"
    stand_in = scratch / "stand-in-installer.py"
    stand_in.write_text(STAND_IN_INSTALLER, encoding="utf-8")
    task_lists = scratch / "tasks"
    list_directory = task_lists / "nedschorus-reboot-test-tasks"
    repository = scratch / "clone"
    elsewhere = scratch / "elsewhere"
    os.environ.update(GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@test.invalid",
                      GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@test.invalid",
                      GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
                      STAND_IN_INSTALLER_LOG=str(installer_log))
    seams = {
        after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_INSTALLER_ENVIRONMENT_VARIABLE: str(stand_in),
        after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE:
            str(task_lists),
    }

    def git(*arguments, hooks="/dev/null", environment=None):
        return subprocess.run(["git", "-c", f"core.hooksPath={hooks}", *arguments],
                              cwd=repository, capture_output=True, text=True, check=False,
                              env=environment)

    def tasks():
        if not list_directory.is_dir():
            return []
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(list_directory.glob("*.json"))]

    def reset():
        installer_log.unlink(missing_ok=True)
        if list_directory.is_dir():
            for path in list_directory.iterdir():
                path.unlink()

    def run(ned_box_reference=None, installer_exit=0, task_lists_directory=None,
            mac_reference=None):
        reset()
        os.environ["STAND_IN_INSTALLER_EXIT"] = str(installer_exit)
        environment = {
            **os.environ, **seams,
            after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE:
                str(ned_box_reference or elsewhere)}
        if task_lists_directory is not None:
            environment[after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE] = \
                str(task_lists_directory)
        saved_mac = after_merge.REFERENCE_CHECKOUT_OF_MACHINE[after_merge.MAC]
        if mac_reference is not None:
            after_merge.REFERENCE_CHECKOUT_OF_MACHINE[after_merge.MAC] = str(mac_reference)
        printed, errors = io.StringIO(), io.StringIO()
        before = os.getcwd()
        os.chdir(repository)
        try:
            with redirect_stdout(printed), redirect_stderr(errors):
                code = after_merge.main(environment)
        finally:
            os.chdir(before)
            after_merge.REFERENCE_CHECKOUT_OF_MACHINE[after_merge.MAC] = saved_mac
        calls = installer_log.read_text().splitlines() if installer_log.exists() else []
        return code, calls, printed.getvalue(), errors.getvalue()

    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    git("commit", "-q", "--allow-empty", "-m", "start")

    code, calls, printed, errors = run()
    check("in a checkout that is not a reference-checkout the installer is not run and nothing "
          "is printed",
          code == 0 and calls == [] and printed == errors == "" and tasks() == [],
          (code, calls, printed, errors))

    code, calls, printed, errors = run(ned_box_reference=repository)
    check("in ned-box's reference-checkout the installer runs with --install; its success "
          "prints nothing and opens no task",
          code == 0 and calls == ["--install"] and printed == errors == "" and tasks() == [],
          (code, calls, printed, errors))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1)
    written = tasks()
    check("a failed install on ned-box becomes one pending task for reboot-test, with the exit "
          "code and the installer's output, and nothing on stderr for the user's display",
          code == 0 and calls == ["--install"] and errors == "" and printed == ""
          and len(written) == 1 and written[0]["status"] == "pending"
          and written[0]["subject"] == after_merge.INSTALL_FAILED_TASK_SUBJECT
          and "exited 1" in written[0]["description"]
          and "FAILED: the crontab write did not hold" in written[0]["description"]
          and f"Run `python3 {repository}/nc-systems/general-tools/"
              "install-scheduled-jobs-on-this-machine.py --install` on ned-box"
              in written[0]["description"]
          and "Mark this task completed once --install exits 0" in written[0]["description"],
          (code, errors, written))

    os.environ["STAND_IN_INSTALLER_EXIT"] = "1"
    environment = {**os.environ, **seams,
                   after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE:
                       str(repository)}
    before = os.getcwd()
    os.chdir(repository)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors_again:
            again = after_merge.main(environment)
            still_open = len(tasks())
            first = list_directory / "1.json"
            task = json.loads(first.read_text(encoding="utf-8"))
            first.write_text(json.dumps({**task, "status": "completed"}), encoding="utf-8")
            after_completed = after_merge.main(environment)
    finally:
        os.chdir(before)
    check("a second failure while the task is open opens no second task; once it is completed, "
          "the next failure opens a new one",
          again == 0 and still_open == 1 and after_completed == 0 and len(tasks()) == 2
          and errors_again.getvalue() == "",
          (again, still_open, after_completed, tasks()))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=2)
    written = tasks()
    check("an installer that refuses to run (exit 2, no FAILED line) is a failure too, and "
          "becomes a task",
          code == 0 and len(written) == 1 and "exited 2" in written[0]["description"]
          and "not run — job `x`" in written[0]["description"], (code, errors, written))

    not_a_directory = scratch / "tasks-is-a-file"
    not_a_directory.write_text("", encoding="utf-8")
    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       task_lists_directory=not_a_directory)
    check("when the task cannot be written, a FAILED message with the installer's output goes "
          "to stderr, which checkout-freshness-catch-up.py shows the user, and the exit is 1",
          code == 1 and "FAILED — after a merge into ned-box's reference-checkout" in errors
          and "writing the task to" in errors and "NotADirectoryError" in errors
          and "Give this whole message to reboot-test, which finds the cause and fixes it; an agent sends it with SendMessage addressed to reboot-test." in errors
          and "FAILED: the crontab write did not hold" in errors, (code, errors))

    code, calls, printed, errors = run(mac_reference=repository)
    check("in the Mac's reference-checkout the installer runs with --install too",
          code == 0 and calls == ["--install"] and errors == "", (code, calls, errors))
    code, calls, printed, errors = run(mac_reference=repository, installer_exit=1)
    check("a failed install on the Mac writes no task, since reboot-test's task list is on "
          "ned-box, and prints the FAILED message",
          code == 1 and tasks() == [] and "FAILED — after a merge into the Mac's" in errors
          and "reboot-test's task list is on ned-box" in errors, (code, errors))

    outside = scratch / "not-a-repository"
    outside.mkdir()
    reset()
    before = os.getcwd()
    os.chdir(outside)
    try:
        code = after_merge.main({**os.environ, **seams})
    finally:
        os.chdir(before)
    check("outside any git checkout nothing is done", code == 0 and not installer_log.exists(),
          code)

    table = json.loads((GENERAL_TOOLS / "scheduled-jobs-on-each-machine.json").read_text())
    check("the reference-checkouts are the clones the scheduled-jobs table runs jobs from",
          sorted(after_merge.REFERENCE_CHECKOUT_OF_MACHINE.values())
          == sorted(machine["clone"] for machine in table["machines"].values()),
          after_merge.REFERENCE_CHECKOUT_OF_MACHINE)
    check("the installer the program runs by default is a file beside it",
          (GENERAL_TOOLS / Path(after_merge.INSTALLER_IN_CLONE).name).is_file()
          and (REPOSITORY_ROOT / after_merge.INSTALLER_IN_CLONE).is_file())

    git("checkout", "-q", "-b", "change")
    (repository / "README.md").write_text("words", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "change")
    git("checkout", "-q", "main")
    reset()
    hook_environment = {
        **os.environ, **seams, "STAND_IN_INSTALLER_EXIT": "1",
        after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE:
            str(repository)}
    merged = git("merge", "--ff-only", "change", hooks=str(HOOKS_DIRECTORY),
                 environment=hook_environment)
    check("through the real post-merge hook in ned-box's reference-checkout, a failed install "
          "leaves the merge in place, becomes a task, and puts no FAILED line on git's stderr",
          merged.returncode == 0 and "FAILED" not in merged.stderr
          and installer_log.read_text().splitlines() == ["--install"] and len(tasks()) == 1
          and git("rev-parse", "HEAD").stdout == git("rev-parse", "change").stdout,
          (merged.returncode, merged.stderr, tasks()))

    git("checkout", "-q", "-b", "change-again")
    (repository / "README.md").write_text("more words", encoding="utf-8")
    git("commit", "-q", "-am", "change again")
    git("checkout", "-q", "main")
    reset()
    merged = git("merge", "--ff-only", "change-again", hooks=str(HOOKS_DIRECTORY),
                 environment={**hook_environment,
                              after_merge.SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE:
                                  str(elsewhere)})
    check("through the real post-merge hook in a checkout that is not a reference-checkout, "
          "the installer is not run and git's stderr is empty",
          merged.returncode == 0 and merged.stderr == "" and not installer_log.exists(),
          (merged.returncode, merged.stderr))

raise SystemExit(1 if failures else 0)
