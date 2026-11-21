#!/usr/bin/env python3
"""Tests for nn-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py
and scripts/git-client-side-hooks/post-merge, which runs it.

No case runs the real installer or touches a crontab or launchd: a stand-in
installer records each call and exits as the case asks for each of --install
and --remove-not-in-table, and the task lists
are under a temporary directory. Each case runs in a temporary repository
that the case names as ned-box's or the Mac's reference-checkout, or as
neither. The last cases merge through the real post-merge hook.

Run: python3 nn-systems/general-tools/tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py
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
_spec = importlib.util.spec_from_file_location("scheduled_jobs_install_after_merge", PROGRAM_PATH)
after_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(after_merge)

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SUBJECT = after_merge.SCHEDULED_JOBS_INSTALLER_FAILURE_TASK_SUBJECT_FOR_OWNING_AGENT_SEAT_TASK_LIST
NED_BOX_OVERRIDE = after_merge.NED_BOX_REFERENCE_CHECKOUT_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE
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
if sys.argv[1:] == ["--remove-not-in-table"]:
    code = int(os.environ.get("STAND_IN_REMOVE_NOT_IN_TABLE_EXIT", "0"))
    if code == 1:
        print("KEPT: not in the table — the crontab line 0 3 * * * /usr/bin/python3 "
              "/clone/scripts/retired.py; /usr/bin/other also runs a job that is not a program "
              "of the clone, so this program left the line in place.")
    elif code:
        print("install-scheduled-jobs-on-this-machine: not run — the crontab could not be read.",
              file=sys.stderr)
    sys.exit(code)
code = int(os.environ.get("STAND_IN_INSTALLER_EXIT", "0"))
if code == 0:
    print("unchanged: transcript-mirror-to-log-store — the crontab holds the table's line.")
elif code == 2:
    print("install-scheduled-jobs-on-this-machine: not run — job `x` runs /nowhere/x.py, "
          "which is not a file on this machine.", file=sys.stderr)
else:
    print(os.environ.get("STAND_IN_INSTALLER_FAILED_LINE", "FAILED: the crontab write did not hold"),
          file=sys.stderr)
sys.exit(code)
"""

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    installer_log = scratch / "installer.log"
    stand_in = scratch / "stand-in-installer.py"
    stand_in.write_text(STAND_IN_INSTALLER, encoding="utf-8")
    task_lists = scratch / "tasks"
    list_directory = task_lists / "nedsnodes-reboot-test-tasks"
    repository = scratch / "clone"
    elsewhere = scratch / "elsewhere"
    os.environ.update(GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@test.invalid",
                      GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@test.invalid",
                      GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
                      STAND_IN_INSTALLER_LOG=str(installer_log))
    seams = {
        after_merge.SCHEDULED_JOBS_INSTALLER_PATH_TEST_OVERRIDE_ENVIRONMENT_VARIABLE: str(stand_in),
        after_merge.AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE: str(task_lists),
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

    def reset(keep_tasks=False):
        installer_log.unlink(missing_ok=True)
        if list_directory.is_dir() and not keep_tasks:
            for path in list_directory.iterdir():
                path.unlink()

    def run(ned_box_reference=None, installer_exit=0, task_lists_directory=None,
            mac_reference=None, failed_line=None, keep_tasks=False, remove_exit=0, argv=()):
        reset(keep_tasks)
        os.environ["STAND_IN_INSTALLER_EXIT"] = str(installer_exit)
        os.environ["STAND_IN_REMOVE_NOT_IN_TABLE_EXIT"] = str(remove_exit)
        environment = {**os.environ, **seams, NED_BOX_OVERRIDE: str(ned_box_reference or elsewhere)}
        # The installer inherits this process's environment, not the one main() reads.
        os.environ.pop("STAND_IN_INSTALLER_FAILED_LINE", None)
        if failed_line is not None:
            os.environ["STAND_IN_INSTALLER_FAILED_LINE"] = failed_line
        if task_lists_directory is not None:
            environment[after_merge.AGENT_SEAT_TASK_LISTS_DIRECTORY_TEST_OVERRIDE_ENVIRONMENT_VARIABLE] = \
                str(task_lists_directory)
        saved_mac = after_merge.REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME[after_merge.MAC]
        if mac_reference is not None:
            after_merge.REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME[after_merge.MAC] = str(mac_reference)
        printed, errors = io.StringIO(), io.StringIO()
        before = os.getcwd()
        os.chdir(repository)
        try:
            with redirect_stdout(printed), redirect_stderr(errors):
                code = after_merge.main(environment, argv=list(argv))
        finally:
            os.chdir(before)
            after_merge.REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME[after_merge.MAC] = saved_mac
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
    check("in ned-box's reference-checkout the installer runs with --install, then with "
          "--remove-not-in-table; their success prints nothing and opens no task",
          code == 0 and calls == ["--install", "--remove-not-in-table"] and printed == errors == "" and tasks() == [],
          (code, calls, printed, errors))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1)
    written = tasks()
    check("a failed install on ned-box is not followed by --remove-not-in-table, and becomes one "
          "pending task for reboot-test naming the --install step, with the exit code and the "
          "installer's output, and nothing on stderr for the user's display",
          code == 0 and calls == ["--install"] and errors == "" and printed == ""
          and len(written) == 1 and written[0]["status"] == "pending"
          and written[0]["subject"] == SUBJECT
          and "the --install step failed: it exited 1, so ned-box may not run every job"
              in written[0]["description"]
          and "FAILED: the crontab write did not hold" in written[0]["description"]
          and f"Then run `cd {repository} && python3 {after_merge.PROGRAM} --print-outcome` on "
              "ned-box: it runs both installer steps, `--install` and then "
              "`--remove-not-in-table`, again, marks this task completed when both exit 0 or "
              "rewrites this description with the new failure" in written[0]["description"]
          and "\nWhen the fix needs something only the user can do, tell the user"
              in written[0]["description"]
          and written[0]["description"].endswith(
              "The installer printed:\nFAILED: the crontab write did not hold")
          and "KEPT line" not in written[0]["description"],
          (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       failed_line="FAILED: a later failure", keep_tasks=True)
    written = tasks()
    check("a later failure while the task is open opens no second task, and replaces the open "
          "task's description with the later failure's output",
          code == 0 and errors == "" and len(written) == 1 and written[0]["status"] == "pending"
          and "FAILED: a later failure" in written[0]["description"]
          and "did not hold" not in written[0]["description"], (code, errors, written))

    for task_id in ("9", "10"):
        (list_directory / f"{task_id}.json").write_text(json.dumps(
            {"id": task_id, "subject": SUBJECT, "description": "an older failure",
             "status": "pending", "blocks": [], "blockedBy": []}), encoding="utf-8")
    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       failed_line="FAILED: with several open", keep_tasks=True)
    written = {task["id"]: task for task in tasks()}
    check("a failure while several tasks of the subject are open opens no new task and rewrites "
          "every open one, 9.json and 10.json alike, with the latest failure",
          code == 0 and errors == "" and sorted(written) == ["1", "10", "9"]
          and all("FAILED: with several open" in task["description"]
                  for task in written.values()), (code, errors, written))
    for task_id in ("9", "10"):
        (list_directory / f"{task_id}.json").unlink()

    list_directory.chmod(0o500)
    try:
        code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                           failed_line="FAILED: cannot reach the task",
                                           keep_tasks=True)
    finally:
        list_directory.chmod(0o700)
    written = tasks()
    check("when the open task cannot be rewritten, the FAILED message goes to stderr with exit "
          "1, and the task keeps its earlier description",
          code == 1 and "FAILED — after the latest merge into ned-box's reference-checkout" in errors
          and "writing the task into the task list directory" in errors
          and "PermissionError" in errors and "FAILED: cannot reach the task" in errors
          and len(written) == 1 and "FAILED: with several open" in written[0]["description"],
          (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, keep_tasks=True)
    written = tasks()
    check("when --install and --remove-not-in-table both succeed, the open task is marked "
          "completed, and nothing is printed",
          code == 0 and errors == printed == "" and calls == ["--install", "--remove-not-in-table"] and len(written) == 1
          and written[0]["status"] == "completed", (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, remove_exit=1)
    written = tasks()
    check("--remove-not-in-table failing after --install succeeds, with no task open, raises a "
          "pending task naming the --remove-not-in-table step, its KEPT line and what to do "
          "about the line",
          code == 0 and errors == printed == "" and calls == ["--install", "--remove-not-in-table"]
          and len(written) == 1 and written[0]["status"] == "pending"
          and written[0]["subject"] == SUBJECT
          and "which it runs only after `--install` exits 0, and the --remove-not-in-table step "
              "failed: it exited 1, so ned-box may still run a job" in written[0]["description"]
          and "KEPT: not in the table — the crontab line" in written[0]["description"]
          and "ask the user to edit that line by hand in ned-box's crontab"
              in written[0]["description"]
          and "the --install step failed" not in written[0]["description"],
          (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       keep_tasks=True)
    code, calls, printed, errors = run(ned_box_reference=repository, remove_exit=2,
                                       keep_tasks=True)
    written = tasks()
    check("--remove-not-in-table failing after --install succeeds leaves the open --install "
          "task open, not completed, with its description replaced by the "
          "--remove-not-in-table failure",
          code == 0 and errors == printed == "" and calls == ["--install", "--remove-not-in-table"]
          and len(written) == 1 and written[0]["status"] == "pending"
          and "the --remove-not-in-table step failed: it exited 2" in written[0]["description"]
          and "not run — the crontab could not be read" in written[0]["description"]
          and "the --install step failed" not in written[0]["description"],
          (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, keep_tasks=True)
    written = tasks()
    check("once both steps succeed again, the task the --remove-not-in-table failure kept open "
          "is marked completed",
          code == 0 and errors == printed == "" and len(written) == 1
          and written[0]["status"] == "completed", (code, errors, written))

    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       keep_tasks=True)
    written = tasks()
    check("once the task is completed, the next failure opens a new one",
          code == 0 and [task["status"] for task in written] == ["completed", "pending"],
          written)

    list_directory.chmod(0o500)
    try:
        code, calls, printed, errors = run(ned_box_reference=repository, keep_tasks=True)
    finally:
        list_directory.chmod(0o700)
    written = tasks()
    check("a successful install whose open task cannot be marked completed still exits 0 with "
          "nothing printed, and leaves the task open",
          code == 0 and errors == printed == "" and written[-1]["status"] == "pending",
          (code, errors, written))

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
          code == 1 and "FAILED — after the latest merge into ned-box's reference-checkout" in errors
          and "writing the task into the task list directory" in errors
          and "NotADirectoryError" in errors
          and "\nIf you are reboot-test, also put right, on ned-box, what stopped the task write, "
              f"such as the permissions of {not_a_directory}/nedsnodes-reboot-test-tasks" in errors
          and f"\nIf you are reboot-test, then run `cd {repository} && python3 "
              f"{after_merge.PROGRAM} --print-outcome` on ned-box: it runs both installer steps, "
              "`--install` and then `--remove-not-in-table`, again and prints how they ended.\n"
              in errors
          and errors.index("what stopped the task write") < errors.index("then run `cd")
              < errors.index("If you are a subagent")
          and "If you are any other agent, send this whole message to reboot-test with Claude Code's "
              "SendMessage tool, addressed to reboot-test" in errors
          and "If you are the user, paste this whole message into reboot-test's session." in errors
          and "FAILED: the crontab write did not hold" in errors, (code, errors))

    code, calls, printed, errors = run(ned_box_reference=repository, remove_exit=1,
                                       task_lists_directory=not_a_directory)
    check("when a --remove-not-in-table failure cannot be written as a task, the FAILED message "
          "on stderr names the --remove-not-in-table step and the KEPT line, and the exit is 1",
          code == 1 and calls == ["--install", "--remove-not-in-table"]
          and "FAILED — after the latest merge into ned-box's reference-checkout" in errors
          and "the --remove-not-in-table step failed: it exited 1" in errors
          and "NotADirectoryError" in errors
          and "If you are reboot-test and the installer printed a KEPT line, that crontab line "
              "runs a job the table does not give ned-box" in errors
          and errors.index("printed a KEPT line") < errors.index("then run `cd")
          and "KEPT: not in the table — the crontab line" in errors, (code, errors))

    code, calls, printed, errors = run(mac_reference=repository)
    check("in the Mac's reference-checkout the installer runs with --install and "
          "--remove-not-in-table too",
          code == 0 and calls == ["--install", "--remove-not-in-table"] and errors == "", (code, calls, errors))
    code, calls, printed, errors = run(mac_reference=repository, remove_exit=1)
    check("a failed --remove-not-in-table on the Mac writes no task and prints the FAILED "
          "message naming the --remove-not-in-table step",
          code == 1 and tasks() == [] and "FAILED — after the latest merge into the Mac's" in errors
          and "the --remove-not-in-table step failed: it exited 1, so the Mac may still run a job"
              in errors
          and "tell the user that the scheduled-jobs installer's --remove-not-in-table step "
              "failed on the Mac" in errors, (code, errors))
    code, calls, printed, errors = run(mac_reference=repository, installer_exit=1)
    check("a failed install on the Mac writes no task, since reboot-test's task list is on "
          "ned-box, and prints the FAILED message",
          code == 1 and tasks() == [] and "FAILED — after the latest merge into the Mac's" in errors
          and "the --install step failed" in errors
          and "reboot-test's task list is on ned-box" in errors
          and f"If you are reboot-test, then ask the user to run `cd {repository} && python3 "
              f"{after_merge.PROGRAM} --print-outcome` in a Terminal on the Mac, which ned-box "
              "cannot run commands on, and to paste what it prints into your session" in errors
          and "what stopped the task write" not in errors, (code, errors))

    outcome = after_merge.PRINT_OUTCOME_COMMAND_LINE_FLAG
    code, calls, printed, errors = run(ned_box_reference=repository, installer_exit=1,
                                       argv=[outcome])
    check("--print-outcome after a failure written as a task prints the failed step and the "
          "task's subject and directory",
          code == 0 and errors == ""
          and printed == f"The --install step failed again on ned-box (exit 1); its output is in "
                         f"the open task with the subject \"{SUBJECT}\" in {list_directory}.\n",
          (code, printed, errors))
    code, calls, printed, errors = run(ned_box_reference=repository, keep_tasks=True,
                                       argv=[outcome])
    open_names = [path.name for path in sorted(list_directory.glob("*.json"))]
    check("--print-outcome after both steps succeed prints that, naming the tasks it marked "
          "completed",
          code == 0 and errors == "" and printed.startswith(
              "Both installer steps, --install and then --remove-not-in-table, exited 0 on "
              "ned-box; open tasks marked completed: ")
          and all(name in printed for name in open_names), (code, printed, errors))
    code, calls, printed, errors = run(ned_box_reference=repository, argv=[outcome])
    check("--print-outcome with no open task says none was marked",
          code == 0 and printed.endswith("open tasks marked completed: none.\n"), printed)
    run(ned_box_reference=repository, installer_exit=1)
    list_directory.chmod(0o500)
    try:
        code, calls, printed, errors = run(ned_box_reference=repository, keep_tasks=True,
                                           argv=[outcome])
    finally:
        list_directory.chmod(0o700)
    check("--print-outcome reports an open task it could not mark completed, which the hook's "
          "run leaves unreported, and still exits 0",
          code == 0 and errors == "" and "but marking the open task completed failed: "
          "PermissionError" in printed, (code, printed, errors))
    code, calls, printed, errors = run(mac_reference=repository, argv=[outcome])
    check("--print-outcome on the Mac after both steps succeed says so",
          code == 0 and printed == "Both installer steps, --install and then "
          "--remove-not-in-table, exited 0 on the Mac.\n", (code, printed, errors))
    code, calls, printed, errors = run(argv=[outcome])
    check("--print-outcome outside a reference-checkout says nothing was run and names both "
          "reference-checkouts",
          code == 0 and calls == [] and "is not a reference-checkout, so nothing was run; run "
          f"this in {elsewhere} on ned-box or " in printed, (code, calls, printed))
    reset()

    outside = scratch / "not-a-repository"
    outside.mkdir()
    reset()
    def run_outside(argv):
        printed, errors = io.StringIO(), io.StringIO()
        before = os.getcwd()
        os.chdir(outside)
        try:
            with redirect_stdout(printed), redirect_stderr(errors):
                code = after_merge.main({**os.environ, **seams}, argv=argv)
        finally:
            os.chdir(before)
        return code, printed.getvalue(), errors.getvalue()

    code, printed, errors = run_outside([])
    check("outside any git checkout nothing is done and nothing is printed",
          code == 0 and not installer_log.exists() and printed == errors == "",
          (code, printed, errors))
    code, printed, errors = run_outside([outcome])
    check("--print-outcome outside any git checkout says nothing was run and names both "
          "reference-checkouts",
          code == 0 and not installer_log.exists() and errors == ""
          and printed.startswith(f"{os.path.realpath(outside)} is not in a Git checkout, so "
                                 "nothing was run; run this in ")
          and " on ned-box or " in printed, (code, printed, errors))

    reset()
    helped = subprocess.run(["python3", str(PROGRAM_PATH), "--help"], cwd=repository,
                            capture_output=True, text=True,
                            env={**os.environ, **seams, NED_BOX_OVERRIDE: str(repository),
                                 "STAND_IN_INSTALLER_EXIT": "1"})
    check("--help prints the usage and exits 0 without running the installer or writing a task, "
          "even in a reference-checkout",
          helped.returncode == 0 and helped.stdout.lower().startswith("usage")
          and not installer_log.exists() and tasks() == [],
          (helped.returncode, helped.stdout, helped.stderr))

    table = json.loads((GENERAL_TOOLS / "scheduled-jobs-on-each-machine.json").read_text())
    check("the reference-checkouts are the clones the scheduled-jobs table runs jobs from",
          sorted(after_merge.REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME.values())
          == sorted(machine["clone"] for machine in table["machines"].values()),
          after_merge.REFERENCE_CHECKOUT_PATH_BY_MACHINE_NAME)
    installer_relative = after_merge.SCHEDULED_JOBS_INSTALLER_PATH_RELATIVE_TO_CLONE_TOP_DIRECTORY
    check("the installer the program runs by default is a file beside it",
          (GENERAL_TOOLS / Path(installer_relative).name).is_file()
          and (REPOSITORY_ROOT / installer_relative).is_file())

    git("checkout", "-q", "-b", "change")
    (repository / "README.md").write_text("words", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "change")
    git("checkout", "-q", "main")
    reset()
    hook_environment = {**os.environ, **seams, "STAND_IN_INSTALLER_EXIT": "1",
                        NED_BOX_OVERRIDE: str(repository)}
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
                 environment={**hook_environment, NED_BOX_OVERRIDE: str(elsewhere)})
    check("through the real post-merge hook in a checkout that is not a reference-checkout, "
          "the installer is not run and git's stderr is empty",
          merged.returncode == 0 and merged.stderr == "" and not installer_log.exists(),
          (merged.returncode, merged.stderr))

with tempfile.TemporaryDirectory() as scratch_name:
    # The real hook file, beside stand-ins at the two program paths it runs, so either program
    # can be made to fail. `git hook run` sends the hook's output to stderr.
    layout = Path(scratch_name)
    hook_copy = layout / "scripts" / "git-client-side-hooks" / "post-merge"
    hook_copy.parent.mkdir(parents=True)
    hook_copy.write_bytes((HOOKS_DIRECTORY / "post-merge").read_bytes())
    hook_copy.chmod(0o755)
    restart_stand_in = (layout / "nn-systems" / "nn-shared-database"
                        / "nn-shared-database-service-restart-after-merge.py")
    install_stand_in = layout / "nn-systems" / "general-tools" / PROGRAM_PATH.name
    for stand_in, variable in ((restart_stand_in, "RESTART_EXIT"), (install_stand_in, "INSTALL_EXIT")):
        stand_in.parent.mkdir(parents=True, exist_ok=True)
        stand_in.write_text(f"import os, sys\nprint('{stand_in.name} ran')\n"
                            f"sys.exit(int(os.environ['{variable}']))\n", encoding="utf-8")
    hook_repository = layout / "repository"
    subprocess.run(["git", "init", "-q", str(hook_repository)], check=True)
    subprocess.run(["git", "-C", str(hook_repository), "config", "core.hooksPath",
                    str(hook_copy.parent)], check=True)
    for restart_exit, install_exit, expected_nonzero in (("1", "0", True), ("0", "1", True),
                                                         ("0", "0", False)):
        ran = subprocess.run(["git", "-C", str(hook_repository), "hook", "run", "post-merge",
                              "--", "0"], capture_output=True, text=True,
                             env={**os.environ, "RESTART_EXIT": restart_exit,
                                  "INSTALL_EXIT": install_exit})
        check(f"the real post-merge hook with the restart exiting {restart_exit} and the install "
              f"exiting {install_exit} runs both and exits "
              f"{'nonzero' if expected_nonzero else '0'}",
              (ran.returncode != 0) == expected_nonzero
              and restart_stand_in.name in ran.stderr and install_stand_in.name in ran.stderr,
              (ran.returncode, ran.stdout, ran.stderr))

raise SystemExit(1 if failures else 0)
