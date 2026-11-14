#!/usr/bin/env python3
"""Name the scripts directory of the Mac's reference-checkout, and the launcher commands in it, once for every program.

The launchers, launch-claude-ubuntu and launch-claude-mac, are not on the Mac's PATH, so a
command a program prints for the user to type in a Mac Terminal names them by this path.
The value does not end in a slash.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "mac_reference_checkout_launcher_scripts_directory_path_constant_common", <path>)
"""

MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH = "/Users/el/Projects/nedschorus/scripts"


def mac_reference_checkout_launcher_path_agent_seat_start_command_text_for_user_to_type(launcher_name: str, agent_seat: str) -> str:
    """Return the command the user types in a Mac Terminal to start agent_seat with launcher_name.

    launcher_name is launch-claude-ubuntu, for an agent-seat on ned-box, or launch-claude-mac.
    """
    return f"{MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH}/{launcher_name} {agent_seat}"
