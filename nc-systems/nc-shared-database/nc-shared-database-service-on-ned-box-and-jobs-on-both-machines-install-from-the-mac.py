#!/usr/bin/env python3
"""Install the nc-shared-database service on ned-box and its callers on both machines, from the Mac.

Usage:
  nc-systems/nc-shared-database/nc-shared-database-service-on-ned-box-and-jobs-on-both-machines-install-from-the-mac.py
      [--print]

  --print   print each step's machine and shell command, and run nothing

Run it on the Mac: only the Mac can open an ssh session to ned-box. It runs
these steps in order, each as one shell command on one machine, and stops at the
first that fails:

  1-2. both reference-checkouts, ~/Projects/nedschorus, hold main's commit that
       named the files nc-shared-database (MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD);
  3.   the Mac's token file is made, unless it already holds a token;
  4.   ned-box's token file is made, unless it already holds a token;
  5.   ned-box's accepted-tokens file is rewritten to hold both tokens: the
       Mac's goes to ned-box on ssh's standard input, never on a command line;
  6.   ned-box enables and starts the systemd user unit;
  7.   ned-box's firewall lets the home network reach port 8765, through
       `sudo -n`, which needs passwordless sudo there;
  8.   ned-box installs the nightly backup job;
  9.   the Mac installs the job that copies the newest backup to the Mac;
  10-13. on each machine, curl asks the service for the agent-seats with that
       machine's token, which must be answered 412, the token accepted and no
       generation ID sent, and without a token, which must be answered 401.

Every step can be run again: a token file that holds a token is kept, and the
unit, the firewall rule and the jobs are left as they are when already there.
Step 5 replaces any other token the accepted-tokens file held.

It installs nothing on any other machine, and does not check that the home
network is 10.0.1.0/24 or that the Mac reaches ned-box as ned-box.local; a wrong
one fails steps 10 to 13. A failed step leaves the steps before it done; running
the program again after the fix repeats them without harm and finishes the rest.

Exit codes: 0 every step passed; 1 a step failed, and the program printed which,
the command, its exit code and output, and what to do; 2 a bad invocation or a
machine that is not the Mac.
"""

import argparse
import importlib.util
import shlex
import subprocess
import sys
from pathlib import Path

_rerun_once_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    Path(__file__).resolve().parents[1] / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
_rerun_once_lines = importlib.util.module_from_spec(_rerun_once_lines_spec)
_rerun_once_lines_spec.loader.exec_module(_rerun_once_lines)

NED_BOX_SSH_TARGET = "nedlern@ned-box"
REFERENCE_CHECKOUT = "~/Projects/nedschorus"
MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD = "35c291170664bb6b7d70b7511550f5ebf7bf4ccb"
TOKEN_DIRECTORY = "~/.config/nedschorus"
TOKEN_FILE = f"{TOKEN_DIRECTORY}/nc-shared-database-service.token"
ACCEPTED_TOKENS_FILE = f"{TOKEN_DIRECTORY}/nc-shared-database-service-accepted-tokens"
NC_SHARED_DATABASE_SERVICE_TOKEN_FILE_PATH = Path(TOKEN_FILE).expanduser()
NC_SHARED_DATABASE_SERVICE_SYSTEMD_UNIT_FILE_PATH = f"{REFERENCE_CHECKOUT}/nc-systems/nc-shared-database/nc-shared-database-service.service"
SERVICE_URL = "http://ned-box.local:8765"
HOME_NETWORK = "10.0.1.0/24"
PORT = 8765
JOB_INSTALLER = "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py"
NED_BOX_JOB = "nc-shared-database-nightly-backup-with-integrity-check"
MAC_JOB = "nc-shared-database-newest-backup-copy-to-mac"
SSH_CANNOT_CONNECT_EXIT_CODE = 255
THIS_MACHINE_PLATFORM = sys.platform
MAC_TOKEN_STEP_NAME = "the Mac's token file is made"

PROGRAM_IN_REFERENCE_CHECKOUT = (f"{REFERENCE_CHECKOUT}/nc-systems/nc-shared-database/"
                                 f"{Path(__file__).name}")
INSTALL_RERUN_COMMAND = f"python3 {PROGRAM_IN_REFERENCE_CHECKOUT}"
INSTALL_RERUN_INSTRUCTION_LINE = f"To run this install again, run on the Mac: `{INSTALL_RERUN_COMMAND}`"
SUBAGENT_REPORT_TO_DISPATCHING_AGENT_INSTRUCTION_LINE = ("If you are a subagent, do not ask or tell the user anything: send this whole "
                 "report, and what you did, to the agent that dispatched you, which asks or "
                 "tells the user what the lines below say to.")


def command_text_to_run_on_the_mac_ssh_wrapped_when_for_ned_box(machine, command, for_the_user_to_type=False):
    """The command as run on the Mac, through ssh for a ned-box command; ssh -t only for a
    command the user types, because sudo then asks him for his password."""
    if machine == "mac":
        return command
    terminal = "-t " if for_the_user_to_type else ""
    return f"ssh {terminal}{NED_BOX_SSH_TARGET} {shlex.quote(command)}"


def install_step_failure_generic_advice(machine, command):
    return ("Find the cause in the Error output and Output lines above; when you can fix it, fix "
            "it and run the install again once. "
            + _rerun_once_lines.agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
                "FAILED: the nc-shared-database install stopped at step",
                phrase_a_stop_message_uses_for_the_command_the_agent_reruns="the install run again"))


def reference_checkout_missing_commit_failure_advice(machine, command):
    pull = f"git -C {REFERENCE_CHECKOUT} pull --ff-only"
    return (f"The reference-checkout {REFERENCE_CHECKOUT} on {machine} does not yet hold main's "
            f"commit {MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD[:9]}, which this install's files came "
            f"from. Fast-forward it to main by running on the Mac `{command_text_to_run_on_the_mac_ssh_wrapped_when_for_ned_box(machine, pull)}`, "
            "then run the install again. When the fast-forward fails, tell the user its output.")


def sudo_advice(machine, command):
    asking = command.replace("sudo -n ", "sudo ", 1)
    return ("ned-box's sudo asked for a password to change the firewall (ufw), and this program "
            "cannot type one. Ask the user to run, in a Terminal on his Mac, "
            f"`{command_text_to_run_on_the_mac_ssh_wrapped_when_for_ned_box(machine, asking, for_the_user_to_type=True)}`, which asks him "
            "for his ned-box password; when he says it succeeded, run the install again. When "
            "he cannot or will not, the install stays stopped at this step: say so to him.")


def service_wrong_http_answer_failure_advice(machine, command):
    log = command_text_to_run_on_the_mac_ssh_wrapped_when_for_ned_box("ned-box", "journalctl --user -u nc-shared-database-service -n 50")
    return ("The nc-shared-database service did not answer as this check needs. Read its log by "
            f"running on the Mac `{log}`, fix the cause it shows, then run the install again once. "
            "When it fails the same way, tell the user which step failed and the log's last "
            "lines.")


def reference_checkout_holds_commit_command():
    return (f"git -C {REFERENCE_CHECKOUT} merge-base --is-ancestor "
            f"{MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD} HEAD")


def service_token_file_create_unless_present_shell_command():
    return (f"mkdir -p {TOKEN_DIRECTORY} && "
            f"if ! test -s {TOKEN_FILE}; then umask 077 && "
            f"python3 -c 'import secrets; print(secrets.token_hex(32))' > {TOKEN_FILE}; fi")


def service_accepted_tokens_file_rewrite_shell_command():
    temporary = f"{ACCEPTED_TOKENS_FILE}.new"
    return (f"umask 077 && {{ cat; echo; cat {TOKEN_FILE}; }} | grep -v '^$' > {temporary} && "
            f"mv {temporary} {ACCEPTED_TOKENS_FILE}")


def service_status_code_command(with_token):
    header = f'-H "Authorization: Bearer $(cat {TOKEN_FILE})" ' if with_token else ""
    return (f"curl -s -o /dev/null -w '%{{http_code}}' --retry 5 --retry-connrefused "
            f"--retry-delay 1 --max-time 10 {header}{SERVICE_URL}/agent-seats")


def job_installed_command(job):
    return f"cd {REFERENCE_CHECKOUT} && python3 {JOB_INSTALLER} --install --job {job}"


def install_steps():
    """Each step: (name, machine, shell command, whether it reads the Mac's token on standard
    input, the output it must print or None, what to do when it fails)."""
    steps = [(f"the {machine} reference-checkout holds main's commit "
              f"{MAIN_COMMIT_EACH_REFERENCE_CHECKOUT_MUST_HOLD[:9]}", machine,
              reference_checkout_holds_commit_command(), False, None, reference_checkout_missing_commit_failure_advice)
             for machine in ("mac", "ned-box")]
    steps += [
        (MAC_TOKEN_STEP_NAME, "mac", service_token_file_create_unless_present_shell_command(), False, None,
         install_step_failure_generic_advice),
        ("ned-box's token file is made", "ned-box", service_token_file_create_unless_present_shell_command(),
         False, None, install_step_failure_generic_advice),
        ("ned-box's accepted-tokens file holds both tokens", "ned-box",
         service_accepted_tokens_file_rewrite_shell_command(), True, None, install_step_failure_generic_advice),
        ("ned-box enables and starts the service", "ned-box",
         f"systemctl --user enable --now {NC_SHARED_DATABASE_SERVICE_SYSTEMD_UNIT_FILE_PATH}", False, None, install_step_failure_generic_advice),
        ("ned-box's firewall opens the service's port to the home network", "ned-box",
         f"sudo -n ufw allow from {HOME_NETWORK} to any port {PORT} proto tcp "
         f"comment 'nc-shared-database service from LAN'", False, None, sudo_advice),
        ("ned-box installs the nightly backup job", "ned-box", job_installed_command(NED_BOX_JOB),
         False, None, install_step_failure_generic_advice),
        ("the Mac installs the backup copy job", "mac", job_installed_command(MAC_JOB), False,
         None, install_step_failure_generic_advice),
    ]
    for machine in ("mac", "ned-box"):
        steps.append((f"from the {machine}, the service accepts the token", machine,
                      service_status_code_command(True), False, "412", service_wrong_http_answer_failure_advice))
        steps.append((f"from the {machine}, the service refuses a request without a token",
                      machine, service_status_code_command(False), False, "401",
                      service_wrong_http_answer_failure_advice))
    return steps


def run_on(machine, command, standard_input):
    words = ["sh", "-c", command] if machine == "mac" else ["ssh", NED_BOX_SSH_TARGET, command]
    return subprocess.run(words, input=standard_input, capture_output=True, text=True)


def failure_report(number, name, machine, command, result, expected, advice):
    lines = [f"FAILED: the nc-shared-database install stopped at step {number} on {machine}, "
             f"whose goal is that {name}; it is not done. The steps before it passed and stay "
             f"done; running the install again repeats them without harm.",
             SUBAGENT_REPORT_TO_DISPATCHING_AGENT_INSTRUCTION_LINE,
             f"Command: {command}",
             f"Exit code: {result.returncode}"]
    if expected is not None:
        lines.append(f"The service answered {result.stdout.strip() or 'nothing'}; "
                     f"this step needs {expected}.")
    elif result.stdout.strip():
        lines.append(f"Output: {result.stdout.strip()}")
    lines.append(f"Error output: {result.stderr.strip() or '(none)'}")
    if machine == "ned-box" and result.returncode == SSH_CANNOT_CONNECT_EXIT_CODE:
        lines.append(f"ssh could not reach ned-box. Run `ssh {NED_BOX_SSH_TARGET} true` on the "
                     f"Mac; when it succeeds, run the install again.")
    else:
        lines.append(advice(machine, command))
    lines.append(INSTALL_RERUN_INSTRUCTION_LINE)
    return "\n".join(lines)


def main(arguments=None, run=run_on):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--print", action="store_true", dest="print_only")
    options = parser.parse_args(arguments)
    if options.print_only:
        for number, (name, machine, command, *_) in enumerate(install_steps(), 1):
            print(f"{number}. {name}, on {machine}:\n   {command}")
        return 0
    if THIS_MACHINE_PLATFORM != "darwin":
        print(f"REFUSED: the nc-shared-database install ran on {THIS_MACHINE_PLATFORM}, and it runs only on "
              f"the Mac, which alone can open an ssh session to ned-box; nothing was installed. "
              f"An agent on the Mac runs `{INSTALL_RERUN_COMMAND}`. From ned-box, ask the user to run "
              f"it in a Terminal on his Mac.", file=sys.stderr)
        return 2
    mac_token = None
    for number, (name, machine, command, reads_mac_token, expected, advice) in enumerate(
            install_steps(), 1):
        result = run(machine, command, mac_token if reads_mac_token else None)
        if result.returncode != 0 or (expected is not None and result.stdout.strip() != expected):
            print(failure_report(number, name, machine, command, result, expected, advice),
                  file=sys.stderr)
            return 1
        if name == MAC_TOKEN_STEP_NAME:
            mac_token = NC_SHARED_DATABASE_SERVICE_TOKEN_FILE_PATH.read_text(encoding="utf-8").strip()
        print(f"step {number} passed: {name}, on {machine}")
    print("The nc-shared-database service is installed: it answers both machines, with a token "
          "only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
