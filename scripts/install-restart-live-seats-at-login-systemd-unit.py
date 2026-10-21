#!/usr/bin/env python3
"""install-restart-live-seats-at-login-systemd-unit — wire
restart-live-seats-at-login.py to boot on the box (nedschorus#116, build
step 4, the box half; the Mac half is the LaunchAgent written by
install-restart-live-seats-at-login-launch-agent.py).

Writes one systemd USER unit to ~/.config/systemd/user/ and enables it. The
box has lingering on for the seat user, so the user manager starts at boot
without a login, and an enabled unit under default.target runs then: the
program selects the seats that were running when the machine stopped and
brings them back, each detached on its own tmux server.

What the unit says, and why:

  - A user unit, not a system unit beside fleet-tmux.service: no root, the
    user manager already runs at boot (Linger=yes, measured 2026-09-14), and
    the seats it launches belong to the seat user anyway.
  - KillMode=process. A oneshot service kills whatever is left in its
    control group when its main process exits, and the seats this program
    launches are detached tmux servers left behind by it — so by default
    they would die the moment the restart finished. Measured 2026-09-14 on
    the box with a probe unit: with KillMode=process the tmux server was
    alive after the unit went inactive; without it, no server was running.
    RemainAfterExit was rejected: it keeps the unit active, so a later stop
    or restart of the unit would kill every seat it launched.
  - The program is run from the durable checkout (--checkout, default
    ~/Projects/nedschorus), never from a worktree that is removed when its
    topic lands.
  - PATH is set explicitly, as the Mac plist does: the recovery tool needs
    tmux, and the supervisor needs claude in ~/.local/bin. The user manager's
    PATH held both when measured, but a boot-time manager's environment is
    not promised to match one measured over ssh.
  - Output is appended to a file beside the run log, as on the Mac, so the
    two machines' records read the same way; the journal has it too.
  - Type=oneshot with no Restart: one run per boot. A run that fails is not
    retried; its output file and the run log say what happened.

The product install writes, reloads, and enables: it runs at the next boot
and nothing runs now. --start-now writes, reloads, and starts WITHOUT
enabling, which runs it at once — the test path, with --unit-name and
--handoff-dir pointed at throwaway values so the real run log and the real
seats are untouched, and so the throwaway does not run at every boot. It
refuses the product unit name, and any name the manager reports enabled:
start leaves an enable symlink in place, so a test start of an enabled
unit would both run at every boot and — under --handoff-dir — rewrite the
unit boot runs to point at the throwaway directory (PR #358 review, items
1 and 2). --remove disables, deletes, and reloads.

Usage:
  install-restart-live-seats-at-login-systemd-unit.py [--checkout DIR]
      [--unit-name NAME] [--handoff-dir DIR] [--print | --start-now | --remove]
"""

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_rerun_then_stop_next_step_lines_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "failed-command-rerun-then-stop-next-step-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

DEFAULT_UNIT_NAME = "restart-live-seats-at-login"
PROGRAM_FILE_NAME = "restart-live-seats-at-login.py"
SYSTEMD_OUTPUT_FILE_NAME = "restart-live-seats-at-login-systemd-output.txt"
PYTHON_PATH = "/usr/bin/python3"
# The boot-time manager needs ~/.local/bin for claude and /usr/bin for tmux and gh.
SYSTEMD_PATH = "{home}/.local/bin:/usr/local/bin:/usr/bin:/bin"


def default_user_unit_directory() -> Path:
    return Path("~/.config/systemd/user").expanduser()


def output_directory_of(handoff_directory, home: Path = Path.home()) -> Path:
    """Return the absolute output directory, using the program default if unspecified."""
    if handoff_directory is None:
        return home / ".claude" / "handoffs"
    return Path(os.path.abspath(handoff_directory))


def unit_text(unit_name: str, checkout: Path, handoff_directory,
              home: Path = Path.home()) -> str:
    """Return the systemd unit text."""
    # The manager does not resolve paths against the invoking shell's working directory.
    checkout = Path(os.path.abspath(checkout))
    program = checkout / "scripts" / PROGRAM_FILE_NAME
    command = f"{PYTHON_PATH} {program}"
    output_directory = output_directory_of(handoff_directory, home)
    if handoff_directory is not None:
        command += f" --handoff-dir {output_directory}"
    output_path = output_directory / SYSTEMD_OUTPUT_FILE_NAME
    return (
        "[Unit]\n"
        f"Description={unit_name}: bring back the seats that were running when this "
        "machine stopped (nedschorus#116)\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "KillMode=process\n"
        f"Environment=PATH={SYSTEMD_PATH.format(home=home)}\n"
        f"ExecStart={command}\n"
        f"StandardOutput=append:{output_path}\n"
        f"StandardError=append:{output_path}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def systemctl(run, *arguments):
    return run(["systemctl", "--user", *arguments])


# is-enabled exits nonzero both for these states, which it prints on stdout, and when it
# cannot ask the manager at all, as when the user bus is unreachable.
SYSTEMCTL_IS_ENABLED_NOT_ENABLED_STATES = (
    "disabled", "linked", "linked-runtime", "masked", "masked-runtime", "not-found", "bad")


class SystemctlCouldNotAnswer(Exception):
    """systemctl exited nonzero without printing an answer; the message names the command and its error."""


def unit_is_enabled(unit_name: str, run=subprocess.run) -> bool:
    """Return whether systemctl reports the unit enabled; raise SystemctlCouldNotAnswer when it cannot tell."""
    command = ["systemctl", "--user", "is-enabled", f"{unit_name}.service"]
    asked = run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if asked.returncode == 0:
        return True
    if (asked.stdout or "").strip() in SYSTEMCTL_IS_ENABLED_NOT_ENABLED_STATES:
        return False
    error_text = " ".join((asked.stderr or "").split())
    failure = SystemctlCouldNotAnswer(
        f"`{' '.join(command)}` exited {asked.returncode}"
        + (f": {error_text}" if error_text else ", printing nothing on stderr"))
    failure.error_text = error_text
    raise failure


def install(unit_name: str, checkout: Path, handoff_directory, unit_directory: Path,
            start_now: bool, run=subprocess.run, home: Path = None) -> int:
    home = home or Path.home()
    program = Path(os.path.abspath(checkout)) / "scripts" / PROGRAM_FILE_NAME
    if not program.is_file():
        print(f"install-restart-live-seats-at-login-systemd-unit: no {PROGRAM_FILE_NAME} "
              f"under {checkout}/scripts — pass --checkout with the durable checkout",
              file=sys.stderr)
        return 1
    try:
        enabled = start_now and unit_is_enabled(unit_name, run)
    except SystemctlCouldNotAnswer as failure:
        print(f"install-restart-live-seats-at-login-systemd-unit: {failure}; so whether "
              f"{unit_name} is enabled is unknown, and nothing was written or started.",
              file=sys.stderr)
        rerun = shlex.join([str(Path(__file__).resolve()), "--start-now", "--unit-name",
                            unit_name, "--checkout", str(checkout)]
                           + (["--handoff-dir", str(handoff_directory)]
                              if handoff_directory else []))
        if failure.error_text:
            print("When systemctl's error says it could not connect to the user bus, run "
                  f"`{rerun}` from a login session of the user whose manager runs the unit, "
                  "such as an ssh login.", file=sys.stderr)
            print(f"Otherwise fix what systemctl's error names, then run `{rerun}`.",
                  file=sys.stderr)
        else:
            print(f"Run `{rerun}` on ned-box, the machine whose user manager runs the unit.",
                  file=sys.stderr)
            print(next_step_lines.rerun_then_stop_line(
                f"`{rerun}`", "install-restart-live-seats-at-login-systemd-unit",
                failure="fails the same way", error_included=None), file=sys.stderr)
        return 1
    if enabled:
        # Starting preserves enable symlinks; rewriting an enabled unit would alter future boots.
        print(f"install-restart-live-seats-at-login-systemd-unit: {unit_name} is enabled, "
              "so a test start would leave it running at every boot with this run's "
              "arguments; --remove it first, or pass a throwaway --unit-name",
              file=sys.stderr)
        return 1
    unit_path = unit_directory / f"{unit_name}.service"
    unit_directory.mkdir(parents=True, exist_ok=True)
    # StandardOutput=append: cannot create directories; startup fails before the program can mkdir.
    output_directory_of(handoff_directory, home).mkdir(parents=True, exist_ok=True)
    unit_path.write_text(unit_text(unit_name, checkout, handoff_directory, home=home),
                         encoding="utf-8")
    print(f"install-restart-live-seats-at-login-systemd-unit: wrote {unit_path}")
    reloaded = systemctl(run, "daemon-reload")
    if reloaded.returncode != 0:
        print(f"  systemctl --user daemon-reload failed (exit {reloaded.returncode}); the "
              "unit is written but the manager has not read it", file=sys.stderr)
        return 1
    if start_now:
        # Throwaway test units must not run at boot.
        started = systemctl(run, "start", f"{unit_name}.service")
        if started.returncode != 0:
            print(f"  systemctl --user start failed (exit {started.returncode})",
                  file=sys.stderr)
            return 1
        print("  started, not enabled: it has run now, and will not run at boot; "
              "its output is in the file the unit names")
        return 0
    enabled = systemctl(run, "enable", f"{unit_name}.service")
    if enabled.returncode != 0:
        print(f"  systemctl --user enable failed (exit {enabled.returncode}); the unit "
              "is written but will not run at boot", file=sys.stderr)
        return 1
    print("  enabled: it runs at the next boot; nothing runs now")
    return 0


def remove(unit_name: str, unit_directory: Path, run=subprocess.run) -> int:
    """Disable and remove the unit, returning nonzero on failure."""
    # A missing unit need not disable successfully; a failed reload still leaves stale manager state.
    unit_path = unit_directory / f"{unit_name}.service"
    had_file = unit_path.is_file()
    disabled = systemctl(run, "disable", f"{unit_name}.service").returncode == 0
    if had_file:
        unit_path.unlink()
    failed = []
    if had_file and not disabled:
        failed.append(f"disable failed, so {unit_name} may still be enabled")
    if systemctl(run, "daemon-reload").returncode != 0:
        failed.append("daemon-reload failed, so the manager still holds the old unit")
    print("install-restart-live-seats-at-login-systemd-unit: "
          + (f"disabled {unit_name} and " if disabled else "")
          + (f"removed {unit_path}" if had_file else f"there was no {unit_path} to remove"))
    for reason in failed:
        print(f"  {reason} — is the user manager reachable from this session?",
              file=sys.stderr)
    return 1 if failed else 0


def main(argv=None, platform: str = sys.platform, unit_directory: Path = None,
         run=subprocess.run, home: Path = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the systemd user unit that runs restart-live-seats-at-login "
                    "at boot on the box.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--checkout", type=Path,
                        default=Path("~/Projects/nedschorus").expanduser(),
                        help="the durable checkout whose scripts/ the unit runs "
                             "(default ~/Projects/nedschorus)")
    parser.add_argument("--unit-name", default=DEFAULT_UNIT_NAME,
                        help=f"the unit's name (default {DEFAULT_UNIT_NAME}); a throwaway "
                             "name for a test install")
    parser.add_argument("--handoff-dir", type=Path, default=None,
                        help="passed to the program, and holds its output file "
                             "(default: the program's own, ~/.claude/handoffs)")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--print", action="store_true",
                        help="print the unit and write nothing")
    action.add_argument("--start-now", action="store_true",
                        help="after writing, start it at once without enabling it; "
                             "refused for the product unit name and for any enabled unit")
    action.add_argument("--remove", action="store_true",
                        help="disable the unit and delete its file")
    arguments = parser.parse_args(argv)
    if platform == "darwin":
        parser.error("systemd units are for the box; on the Mac the sibling is the "
                     "LaunchAgent, install-restart-live-seats-at-login-launch-agent.py")
    if arguments.start_now and arguments.unit_name == DEFAULT_UNIT_NAME:
        # A test start would overwrite the product unit's boot arguments.
        parser.error(f"--start-now needs a throwaway --unit-name: {DEFAULT_UNIT_NAME} is "
                     "the unit boot runs")
    unit_directory = unit_directory or default_user_unit_directory()

    if arguments.print:
        sys.stdout.write(unit_text(arguments.unit_name, arguments.checkout,
                                   arguments.handoff_dir))
        return 0
    if arguments.remove:
        return remove(arguments.unit_name, unit_directory, run=run)
    return install(arguments.unit_name, arguments.checkout, arguments.handoff_dir,
                   unit_directory, arguments.start_now, run=run, home=home)


if __name__ == "__main__":
    sys.exit(main())
