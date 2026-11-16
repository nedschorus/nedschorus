#!/usr/bin/env python3
"""Run install-scheduled-jobs-on-this-machine.py --install after a merge into a machine's reference-checkout.

Usage (git runs it from scripts/git-client-side-hooks/post-merge, in the
checkout's top directory, after every merge, a fast-forward included):
  nc-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py

Every checkout of the clone runs the same post-merge hook, because
core.hooksPath names the reference-checkout's hook directory. In any checkout
but a reference-checkout of REFERENCE_CHECKOUT_OF_MACHINE this program does
nothing. In one, it runs the installer beside this file with --install, so a
change merged into the table, scheduled-jobs-on-each-machine.json, or an
install that failed before, is put right at the next pull. The installer's
output is not passed on when it succeeds.

When the installer exits nonzero on ned-box, its exit code and output become
a task on the task list of OWNING_AGENT_SEAT, the agent-seat that owns the
installer, written with agent-seat-task-list-new-pending-task-write-common.py,
unless a task of the same subject not marked completed is already there.
Nothing is printed then. When the task cannot be written, or the installer
failed on the Mac, where OWNING_AGENT_SEAT's task list is not, a FAILED
message goes to standard error instead: git puts it on its own stderr, and
scripts/checkout-freshness-catch-up.py, which fast-forwards the
reference-checkout, shows the user any FAILED line there.

Git ignores a post-merge hook's exit code; the merge stands either way.

Exit codes: 0 not a reference-checkout, the install succeeded, or its failure
was written as a task; 1 the install failed and no task was written, with the
FAILED message on standard error.

Three environment variables replace a value for
tests/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat-test.py,
which runs no real install: SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE,
SCHEDULED_JOBS_INSTALL_AFTER_MERGE_INSTALLER_ENVIRONMENT_VARIABLE and
SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE
name them.
"""

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent
PROGRAM = "nc-systems/general-tools/install-scheduled-jobs-on-this-machine-after-reference-checkout-merge-and-report-install-failure-as-task-for-installer-owner-agent-seat.py"
INSTALLER_IN_CLONE = "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py"
OWNING_AGENT_SEAT = "reboot-test"
NED_BOX = "ned-box"
MAC = "the Mac"
EXIT_DONE = 0
EXIT_FAILED = 1

SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT")
SCHEDULED_JOBS_INSTALL_AFTER_MERGE_INSTALLER_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_SCHEDULED_JOBS_INSTALL_AFTER_MERGE_INSTALLER")
SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY")


def _load(module_name, file_name):
    specification = importlib.util.spec_from_file_location(module_name, GENERAL_TOOLS / file_name)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ned_box_paths = _load("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                      "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
mac_reference_checkout = _load(
    "mac_reference_checkout_launcher_scripts_directory_path_constant_common",
    "mac-reference-checkout-launcher-scripts-directory-path-constant-common.py")
agent_seat_task_list = _load("agent_seat_task_list_new_pending_task_write_common",
                             "agent-seat-task-list-new-pending-task-write-common.py")

REFERENCE_CHECKOUT_OF_MACHINE = {
    NED_BOX: f"{ned_box_paths.NED_BOX_HOME}/Projects/nedschorus",
    MAC: str(Path(mac_reference_checkout.MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH).parent),
}
INSTALL_FAILED_TASK_SUBJECT = (
    "Scheduled jobs: install-scheduled-jobs-on-this-machine.py --install failed after a pull "
    "into ned-box's reference-checkout")


def install_command_text(reference_checkout):
    return f"python3 {reference_checkout}/{INSTALLER_IN_CLONE} --install"


def install_failed_task_description(reference_checkout, exit_code, output):
    return (
        f"After a merge into ned-box's reference-checkout, {reference_checkout}, its post-merge "
        f"hook ran `{install_command_text(reference_checkout)}`, which exited {exit_code}, so "
        f"ned-box's crontab may not hold the jobs that "
        f"nc-systems/general-tools/scheduled-jobs-on-each-machine.json gives it. The installer "
        f"printed:\n{output}\n"
        f"Run `{install_command_text(reference_checkout)}` on ned-box, and fix what its FAILED "
        f"or \"not run\" lines name.\n"
        f"When the cause is in the installer or the table, fix it in a pull request; the "
        f"post-merge hook runs --install again at the next pull into the reference-checkout.\n"
        f"When the fix needs something only the user can do, tell him what failed, quoting the "
        f"installer's lines, and what he must do.\n"
        f"Mark this task completed once --install exits 0 in the reference-checkout. Until "
        f"then the post-merge hook opens no second task with this subject, so a failure at a "
        f"later pull adds nothing to your list; rerun --install to see the latest output.")


def failed_message(machine, reference_checkout, exit_code, output, why_no_task):
    return (
        f"{PROGRAM}: FAILED — after a merge into {machine}'s reference-checkout, "
        f"{reference_checkout}, `{install_command_text(reference_checkout)}` exited {exit_code}, "
        f"so {machine}'s scheduled jobs may not be what "
        f"nc-systems/general-tools/scheduled-jobs-on-each-machine.json says. The failure belongs "
        f"to the agent-seat {OWNING_AGENT_SEAT} on ned-box, which owns the installer, and was "
        f"not handed to it: {why_no_task}\n"
        f"Give this whole message to {OWNING_AGENT_SEAT}, which finds the cause and fixes it; an "
        f"agent sends it with SendMessage addressed to {OWNING_AGENT_SEAT}. If you are a "
        f"subagent, give this message to the agent that dispatched you instead.\n"
        f"The installer printed:\n{output}")


def open_task_with_subject_exists(list_directory, subject):
    for path in list_directory.glob("*.json"):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if task.get("status") != "completed" and task.get("subject") == subject:
            return True
    return False


def main(environment=None):
    environment = os.environ if environment is None else environment
    reference_checkouts = dict(REFERENCE_CHECKOUT_OF_MACHINE)
    if environment.get(SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE):
        reference_checkouts[NED_BOX] = environment[
            SCHEDULED_JOBS_INSTALL_AFTER_MERGE_NED_BOX_REFERENCE_CHECKOUT_ENVIRONMENT_VARIABLE]
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        return EXIT_DONE
    checkout = os.path.realpath(top.stdout.strip())
    machine = next((name for name, path in reference_checkouts.items()
                    if os.path.realpath(path) == checkout), None)
    if machine is None:
        return EXIT_DONE
    reference_checkout = reference_checkouts[machine]
    installer = environment.get(SCHEDULED_JOBS_INSTALL_AFTER_MERGE_INSTALLER_ENVIRONMENT_VARIABLE) \
        or str(GENERAL_TOOLS / Path(INSTALLER_IN_CLONE).name)
    installed = subprocess.run([sys.executable, installer, "--install"],
                               capture_output=True, text=True)
    if installed.returncode == 0:
        return EXIT_DONE
    output = "\n".join(part for part in (installed.stdout.strip(), installed.stderr.strip())
                       if part) or "(nothing)"
    if machine != NED_BOX:
        print(failed_message(machine, reference_checkout, installed.returncode, output,
                             f"{OWNING_AGENT_SEAT}'s task list is on ned-box, and this program "
                             f"writes a task only on ned-box."), file=sys.stderr)
        return EXIT_FAILED
    task_lists_directory = Path(
        environment.get(SCHEDULED_JOBS_INSTALL_AFTER_MERGE_TASK_LISTS_DIRECTORY_ENVIRONMENT_VARIABLE)
        or Path.home() / ".claude" / "tasks")
    list_directory = task_lists_directory / f"nedschorus-{OWNING_AGENT_SEAT}-tasks"
    try:
        list_directory.mkdir(parents=True, exist_ok=True)
        if not open_task_with_subject_exists(list_directory, INSTALL_FAILED_TASK_SUBJECT):
            agent_seat_task_list.agent_seat_task_list_new_pending_task_write(
                list_directory, INSTALL_FAILED_TASK_SUBJECT,
                install_failed_task_description(reference_checkout, installed.returncode, output))
    except OSError as error:
        print(failed_message(machine, reference_checkout, installed.returncode, output,
                             f"writing the task to {list_directory} failed: "
                             f"{type(error).__name__}: {error}"), file=sys.stderr)
        return EXIT_FAILED
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
