#!/usr/bin/env python3
"""Install the nc-shared-database service on ned-box and its callers on both machines, from the Mac.

Usage:
  nc-systems/nc-shared-database/nc-shared-database-service-install-on-both-machines-from-the-mac.py
      [--print]

  --print   print each step's machine and shell command, and run nothing

Run it on the Mac: only the Mac can open an ssh session to ned-box. It runs
these steps in order, each as one shell command on one machine, and stops at the
first that fails:

  1-2. both reference-checkouts, ~/Projects/nedschorus, hold main's commit that
       named the files nc-shared-database (FIRST_MAIN_COMMIT_WITH_THESE_FILES);
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
import subprocess
import sys
from pathlib import Path

NED_BOX_SSH_TARGET = "nedlern@ned-box"
REFERENCE_CHECKOUT = "~/Projects/nedschorus"
FIRST_MAIN_COMMIT_WITH_THESE_FILES = "35c291170664bb6b7d70b7511550f5ebf7bf4ccb"
TOKEN_DIRECTORY = "~/.config/nedschorus"
TOKEN_FILE = f"{TOKEN_DIRECTORY}/nc-shared-database-service.token"
ACCEPTED_TOKENS_FILE = f"{TOKEN_DIRECTORY}/nc-shared-database-service-accepted-tokens"
MAC_TOKEN_FILE_PATH = Path(TOKEN_FILE).expanduser()
UNIT_FILE = f"{REFERENCE_CHECKOUT}/nc-systems/nc-shared-database/nc-shared-database-service.service"
SERVICE_URL = "http://ned-box.local:8765"
HOME_NETWORK = "10.0.1.0/24"
PORT = 8765
JOB_INSTALLER = "nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py"
NED_BOX_JOB = "nc-shared-database-nightly-backup-with-integrity-check"
MAC_JOB = "nc-shared-database-newest-backup-copy-to-mac"
SSH_CANNOT_CONNECT_EXIT_CODE = 255
PLATFORM = sys.platform
MAC_TOKEN_STEP_NAME = "the Mac's token file is made"

GENERIC_ADVICE = ("Find the cause in the output above. When you can fix it, fix it and run this "
                  "program again once. When it fails the same way, or the fix needs the user, "
                  "such as a setting only he can change, tell him which step failed, on which "
                  "machine, and the output above.")
REFERENCE_CHECKOUT_ADVICE = (f"That machine's reference-checkout, {REFERENCE_CHECKOUT}, has not "
                             "fast-forwarded to main yet. Run `git -C ~/Projects/nedschorus pull "
                             "--ff-only` on that machine, then run this program again.")
SUDO_ADVICE = ("ned-box's sudo needs a password for ufw, and this program cannot type one. Ask "
               "the user to run the command above in a Terminal on his Mac as `ssh -t "
               "nedlern@ned-box '<the command>'`, which asks him for the password; then run "
               "this program again.")
SERVICE_ANSWER_ADVICE = ("Read the service's log on ned-box with `ssh nedlern@ned-box "
                         "'journalctl --user -u nc-shared-database-service -n 50'`, fix the "
                         "cause, then run this program again once.")
SUBAGENT_LINE = ("If you are a subagent, report this failure to the agent that dispatched you "
                 "instead of telling the user.")


def reference_checkout_holds_commit_command():
    return (f"git -C {REFERENCE_CHECKOUT} merge-base --is-ancestor "
            f"{FIRST_MAIN_COMMIT_WITH_THESE_FILES} HEAD")


def token_file_made_unless_present_command():
    return (f"mkdir -p {TOKEN_DIRECTORY} && "
            f"if ! test -s {TOKEN_FILE}; then umask 077 && "
            f"python3 -c 'import secrets; print(secrets.token_hex(32))' > {TOKEN_FILE}; fi")


def accepted_tokens_file_written_command():
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
              f"{FIRST_MAIN_COMMIT_WITH_THESE_FILES[:9]}", machine,
              reference_checkout_holds_commit_command(), False, None, REFERENCE_CHECKOUT_ADVICE)
             for machine in ("mac", "ned-box")]
    steps += [
        (MAC_TOKEN_STEP_NAME, "mac", token_file_made_unless_present_command(), False, None,
         GENERIC_ADVICE),
        ("ned-box's token file is made", "ned-box", token_file_made_unless_present_command(),
         False, None, GENERIC_ADVICE),
        ("ned-box's accepted-tokens file holds both tokens", "ned-box",
         accepted_tokens_file_written_command(), True, None, GENERIC_ADVICE),
        ("ned-box enables and starts the service", "ned-box",
         f"systemctl --user enable --now {UNIT_FILE}", False, None, GENERIC_ADVICE),
        ("ned-box's firewall opens the service's port to the home network", "ned-box",
         f"sudo -n ufw allow from {HOME_NETWORK} to any port {PORT} proto tcp "
         f"comment 'nc-shared-database service from LAN'", False, None, SUDO_ADVICE),
        ("ned-box installs the nightly backup job", "ned-box", job_installed_command(NED_BOX_JOB),
         False, None, GENERIC_ADVICE),
        ("the Mac installs the backup copy job", "mac", job_installed_command(MAC_JOB), False,
         None, GENERIC_ADVICE),
    ]
    for machine in ("mac", "ned-box"):
        steps.append((f"from the {machine}, the service accepts the token", machine,
                      service_status_code_command(True), False, "412", SERVICE_ANSWER_ADVICE))
        steps.append((f"from the {machine}, the service refuses a request without a token",
                      machine, service_status_code_command(False), False, "401",
                      SERVICE_ANSWER_ADVICE))
    return steps


def run_on(machine, command, standard_input):
    words = ["sh", "-c", command] if machine == "mac" else ["ssh", NED_BOX_SSH_TARGET, command]
    return subprocess.run(words, input=standard_input, capture_output=True, text=True)


def failure_report(number, name, machine, command, result, expected, advice):
    lines = [f"FAILED: step {number}, {name}, on {machine}. The steps before it passed and stay "
             f"done; running this program again repeats them without harm.",
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
                     f"Mac; when it succeeds, run this program again.")
    else:
        lines.append(advice)
    lines.append(SUBAGENT_LINE)
    return "\n".join(lines)


def main(arguments=None, run=run_on):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--print", action="store_true", dest="print_only")
    options = parser.parse_args(arguments)
    if options.print_only:
        for number, (name, machine, command, *_) in enumerate(install_steps(), 1):
            print(f"{number}. {name}, on {machine}:\n   {command}")
        return 0
    if PLATFORM != "darwin":
        print("REFUSED: this program runs on the Mac, which alone can open an ssh session to "
              "ned-box. Run it in a Terminal on the Mac, in the reference-checkout "
              "~/Projects/nedschorus.", file=sys.stderr)
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
            mac_token = MAC_TOKEN_FILE_PATH.read_text(encoding="utf-8").strip()
        print(f"step {number} passed: {name}, on {machine}")
    print("The nc-shared-database service is installed: it answers both machines, with a token "
          "only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
