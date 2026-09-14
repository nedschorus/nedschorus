#!/usr/bin/env python3
"""install-restart-live-seats-at-login-launch-agent — wire
restart-live-seats-at-login.py to login on the Mac (nedschorus#116, build
step 4).

Writes one LaunchAgent plist to ~/Library/LaunchAgents/. launchd loads every
plist there at the user's next login, and RunAtLoad makes this one run its
program then: at login, the program selects the seats that were running when
the machine stopped and brings them back, each in its own iTerm window.

What the plist says, and why:

  - The program is run from the durable checkout (--checkout, default
    ~/Projects/nedschorus), never from a worktree: worktrees are removed when
    their topic lands, and a plist pointing at one would run nothing at the
    next login and say so only in its output file.
  - PATH is set explicitly. launchd gives a job a bare PATH — no Homebrew,
    no ~/.local/bin — and the recovery tool the program runs needs tmux and
    gh, and the launcher needs claude. This is the same gap iTerm2's custom
    command has (the #116 design, § Constraints), closed there by a login
    shell and here by naming the directories.
  - LimitLoadToSessionType Aqua: the program opens iTerm windows, so it runs
    only in the graphical login session, never for an ssh login.
  - Output goes to a file beside the run log: at login there is no terminal
    to read it from.
  - No KeepAlive and no StartInterval: one run per login. A run that fails
    is not retried by launchd; its output file and the run log say what
    happened, and the recovery tool is run by hand.

Writing the plist does not load it: it takes effect at the next login. Pass
--bootstrap-now to load it into this login session at once, which with
RunAtLoad runs it immediately — that is the test path, with --label and
--handoff-dir pointed at throwaway values so the real run log and the real
seats are untouched. --remove unloads and deletes a plist by its label.

Usage:
  install-restart-live-seats-at-login-launch-agent.py [--checkout DIR]
      [--label LABEL] [--handoff-dir DIR] [--print | --bootstrap-now | --remove]
"""

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

DEFAULT_LABEL = "com.nedschorus.restart-live-seats-at-login"
PROGRAM_FILE_NAME = "restart-live-seats-at-login.py"
LAUNCHD_OUTPUT_FILE_NAME = "restart-live-seats-at-login-launchd-output.txt"
# The interpreter launchd runs: the system one, present without Homebrew.
PYTHON_PATH = "/usr/bin/python3"
# Where the fleet's binaries live on this Mac, measured 2026-09-14: claude in
# ~/.local/bin, tmux and gh in /opt/homebrew/bin; the rest is launchd's own.
LAUNCHD_PATH = "{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def default_launch_agents_directory() -> Path:
    return Path("~/Library/LaunchAgents").expanduser()


def launch_agent_plist(label: str, checkout: Path, handoff_directory,
                       home: Path = Path.home()) -> dict:
    """The plist as a dict — what plistlib writes. handoff_directory None
    means the program's default (~/.claude/handoffs); a directory is passed
    to the program and holds the output file, so a test install touches
    nothing of the real one."""
    program = checkout / "scripts" / PROGRAM_FILE_NAME
    arguments = [PYTHON_PATH, str(program)]
    output_directory = home / ".claude" / "handoffs"
    if handoff_directory is not None:
        arguments += ["--handoff-dir", str(handoff_directory)]
        output_directory = Path(handoff_directory)
    output_path = str(output_directory / LAUNCHD_OUTPUT_FILE_NAME)
    return {
        "Label": label,
        "ProgramArguments": arguments,
        "EnvironmentVariables": {"PATH": LAUNCHD_PATH.format(home=home)},
        "RunAtLoad": True,
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": output_path,
        "StandardErrorPath": output_path,
    }


def launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def install(label: str, checkout: Path, handoff_directory, launch_agents_directory: Path,
            bootstrap_now: bool, run=subprocess.run) -> int:
    program = checkout / "scripts" / PROGRAM_FILE_NAME
    if not program.is_file():
        print(f"install-restart-live-seats-at-login-launch-agent: no {PROGRAM_FILE_NAME} "
              f"under {checkout}/scripts — pass --checkout with the durable checkout",
              file=sys.stderr)
        return 1
    plist_path = launch_agents_directory / f"{label}.plist"
    launch_agents_directory.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps(
        launch_agent_plist(label, checkout, handoff_directory), sort_keys=False))
    print(f"install-restart-live-seats-at-login-launch-agent: wrote {plist_path}")
    if not bootstrap_now:
        print("  it loads at the next login, and runs then; nothing runs now")
        return 0
    # bootstrap refuses a label already loaded, so an earlier load of this
    # label — a previous test — is booted out first; a bootout of a label
    # that is not loaded fails and is ignored.
    run(["launchctl", "bootout", f"{launchd_domain()}/{label}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finished = run(["launchctl", "bootstrap", launchd_domain(), str(plist_path)])
    if finished.returncode != 0:
        print(f"  launchctl bootstrap failed (exit {finished.returncode}); the plist is "
              "written and still loads at the next login", file=sys.stderr)
        return 1
    print(f"  bootstrapped into {launchd_domain()}: it is running now (RunAtLoad); "
          f"its output is in the file the plist names")
    return 0


def remove(label: str, launch_agents_directory: Path, run=subprocess.run) -> int:
    plist_path = launch_agents_directory / f"{label}.plist"
    run(["launchctl", "bootout", f"{launchd_domain()}/{label}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if plist_path.is_file():
        plist_path.unlink()
        print(f"install-restart-live-seats-at-login-launch-agent: unloaded {label} and "
              f"removed {plist_path}")
    else:
        print(f"install-restart-live-seats-at-login-launch-agent: unloaded {label}; "
              f"there was no {plist_path} to remove")
    return 0


def main(argv=None, platform: str = sys.platform,
         launch_agents_directory: Path = None, run=subprocess.run) -> int:
    parser = argparse.ArgumentParser(
        description="Install the LaunchAgent that runs restart-live-seats-at-login "
                    "at login on the Mac.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--checkout", type=Path,
                        default=Path("~/Projects/nedschorus").expanduser(),
                        help="the durable checkout whose scripts/ the agent runs "
                             "(default ~/Projects/nedschorus)")
    parser.add_argument("--label", default=DEFAULT_LABEL,
                        help=f"the launchd label and plist name (default {DEFAULT_LABEL}); "
                             "a throwaway label for a test install")
    parser.add_argument("--handoff-dir", type=Path, default=None,
                        help="passed to the program, and holds its output file "
                             "(default: the program's own, ~/.claude/handoffs)")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--print", action="store_true",
                        help="print the plist and write nothing")
    action.add_argument("--bootstrap-now", action="store_true",
                        help="after writing, load it into this login session, which "
                             "runs it at once")
    action.add_argument("--remove", action="store_true",
                        help="unload the label and delete its plist")
    arguments = parser.parse_args(argv)
    if platform != "darwin":
        parser.error("LaunchAgents are macOS; on the box the sibling is a systemd unit")
    launch_agents_directory = launch_agents_directory or default_launch_agents_directory()

    if arguments.print:
        sys.stdout.write(plistlib.dumps(
            launch_agent_plist(arguments.label, arguments.checkout, arguments.handoff_dir),
            sort_keys=False).decode("utf-8"))
        return 0
    if arguments.remove:
        return remove(arguments.label, launch_agents_directory, run=run)
    return install(arguments.label, arguments.checkout, arguments.handoff_dir,
                   launch_agents_directory, arguments.bootstrap_now, run=run)


if __name__ == "__main__":
    sys.exit(main())
