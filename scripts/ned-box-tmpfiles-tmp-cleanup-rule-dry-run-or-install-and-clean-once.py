#!/usr/bin/env python3
"""Preview, or install, ned-box's /tmp cleanup rule kept in the repository.

The rule is config/ned-box-tmpfiles-tmp-cleanup-rule-ignoring-directory-access-time.conf;
its comments say why it differs from the distribution's rule.

With no flag: a dry run. Runs `systemd-tmpfiles --dry-run --clean <rule>` as the
calling user and prints how many entries directly inside /tmp and /var/tmp the rule
would remove, with a sample. Nothing is changed. Directories the calling user cannot
open are left out of the count, and the number of them is printed.

With --install-and-clean-once: the dry run first, then
`sudo install` of the rule as /etc/tmpfiles.d/tmp.conf, then one
`sudo systemd-tmpfiles --clean /etc/tmpfiles.d/tmp.conf`, which removes what the dry
run listed, without undo. The daily systemd-tmpfiles-clean.timer reads the installed
file from then on. sudo asks for the password, so run it from a terminal.
Running it again rewrites the same file and cleans again.

Each failed step prints what failed and what state it left, and the script exits 1.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
RULE_FILE = (Path(__file__).resolve().parents[1] / "config"
             / "ned-box-tmpfiles-tmp-cleanup-rule-ignoring-directory-access-time.conf")
INSTALLED_RULE_PATH = Path("/etc/tmpfiles.d/tmp.conf")
SAMPLE_SIZE = 10
# systemd-tmpfiles' exit code when an operation failed; as a non-root user the dry run
# exits with it because some directories in /tmp belong to other users.
SYSTEMD_TMPFILES_OPERATION_FAILED_EXIT_CODE = 73
TOP_LEVEL_REMOVAL_LINE = re.compile(r'^Would remove (?:directory )?"(/(?:var/)?tmp/[^/"]+)"$')
ANY_REMOVAL_LINE = re.compile(r'^Would remove ')
UNOPENABLE_DIRECTORY_LINE = re.compile(r'^Opening directory ".*" failed, ignoring: Permission denied$')
PROGRAM = "ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once"
DRY_RUN_COMMAND_LINE = f"python3 {Path(__file__).resolve()}"
INSTALL_COMMAND_LINE = f"{DRY_RUN_COMMAND_LINE} --install-and-clean-once"
# sudo cannot ask for the password without a terminal, as in an agent's shell.
# The durable checkout, not this file's path: an agent may run this from a worktree removed later.
USER_INSTALL_COMMAND_LINE = (
    "ssh -t nedlern@ned-box 'cd ~/Projects/nedschorus && git pull --ff-only && python3 "
    "scripts/ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once.py "
    "--install-and-clean-once'")
SUDO_NEEDS_THE_USER_LINE = (
    "When sudo said a terminal or a password is required, the user must run the install, "
    f"from a Terminal on his Mac: {USER_INSTALL_COMMAND_LINE}")


def dry_run(rule_file: Path, run=subprocess.run) -> int:
    """Print what the rule would remove; return 0, or 1 when the dry run failed."""
    command = ["systemd-tmpfiles", "--dry-run", "--clean", str(rule_file)]
    try:
        result = run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        print(f"{PROGRAM}: dry run failed: systemd-tmpfiles is not on PATH, so nothing "
              f"was counted and nothing was changed.\nRun `{DRY_RUN_COMMAND_LINE}` on ned-box, "
              "whose /tmp the rule is for.", file=sys.stderr)
        return 1
    lines = (result.stdout + result.stderr).splitlines()
    unopenable = [line for line in lines if UNOPENABLE_DIRECTORY_LINE.match(line)]
    accepted = result.returncode == 0 or (
        result.returncode == SYSTEMD_TMPFILES_OPERATION_FAILED_EXIT_CODE and unopenable)
    if not accepted:
        print(f"{PROGRAM}: dry run failed: `{' '.join(command)}` exited "
              f"{result.returncode}, so nothing was counted and nothing was changed. "
              "Its lines other than removals:", file=sys.stderr)
        for line in [line for line in lines if not ANY_REMOVAL_LINE.match(line)][:SAMPLE_SIZE]:
            print(f"  {line}", file=sys.stderr)
        print(f"When a line above names {rule_file}, correct that line of the rule file.\n"
              "Otherwise fix what the lines above name.\n"
              f"Then run `{DRY_RUN_COMMAND_LINE}` again.", file=sys.stderr)
        return 1
    top_level = [match.group(1) for line in lines
                 if (match := TOP_LEVEL_REMOVAL_LINE.match(line))]
    all_removals = sum(1 for line in lines if ANY_REMOVAL_LINE.match(line))
    print(f"The rule in {rule_file} would remove {len(top_level)} entries directly inside "
          f"/tmp and /var/tmp ({all_removals} paths, counting what is inside them).")
    if top_level:
        print(f"The first {min(SAMPLE_SIZE, len(top_level))}:")
        for path in top_level[:SAMPLE_SIZE]:
            print(f"  {path}")
    if unopenable:
        print(f"{len(unopenable)} directories could not be opened without root, so what is "
              "inside them is not counted.")
    return 0


def install_and_clean_once(rule_file: Path, run=subprocess.run) -> int:
    """Install the rule with sudo and clean once; return 0, or 1 at the first failed step."""
    install_command = ["sudo", "install", "-m", "0644", "-o", "root", "-g", "root",
                       str(rule_file), str(INSTALLED_RULE_PATH)]
    clean_command = ["sudo", "systemd-tmpfiles", "--clean", str(INSTALLED_RULE_PATH)]
    installed = run(install_command)
    if installed.returncode != 0:
        print(f"{PROGRAM}: install failed: `{' '.join(install_command)}` exited "
              f"{installed.returncode}, so {INSTALLED_RULE_PATH} was not written and nothing "
              f"was removed.\n{SUDO_NEEDS_THE_USER_LINE}\n"
              f"Otherwise fix what sudo printed above, then run `{INSTALL_COMMAND_LINE}` again on ned-box.\n"
              "If that run fails the same way, stop and give the user what sudo printed.",
              file=sys.stderr)
        return 1
    print(f"Installed {INSTALLED_RULE_PATH}; the daily cleaner uses it from now on.")
    cleaned = run(clean_command)
    if cleaned.returncode != 0:
        print(f"{PROGRAM}: clean failed: `{' '.join(clean_command)}` exited "
              f"{cleaned.returncode}. The rule is installed, and the daily cleaner uses it; "
              "systemd-tmpfiles may have removed some old entries before it failed.\nFix what systemd-tmpfiles printed above, then run "
              f"`{' '.join(clean_command)}` again.", file=sys.stderr)
        return 1
    print("Cleaned /tmp and /var/tmp once with the installed rule.")
    return 0


def main(argv=None, rule_file: Path = RULE_FILE, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install-and-clean-once", action="store_true",
                        help=f"after the dry run, install the rule as {INSTALLED_RULE_PATH} "
                             "and clean once, both with sudo")
    arguments = parser.parse_args(argv)
    if dry_run(rule_file, run) != 0:
        return 1
    if not arguments.install_and_clean_once:
        print("Nothing was changed. To install the rule and remove the entries counted above once, "
              f"run `{INSTALL_COMMAND_LINE}` on ned-box from a terminal; sudo asks for the "
              "password.")
        return 0
    return install_and_clean_once(rule_file, run)


if __name__ == "__main__":
    sys.exit(main())
