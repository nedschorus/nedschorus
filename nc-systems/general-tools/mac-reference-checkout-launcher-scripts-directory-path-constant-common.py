#!/usr/bin/env python3
"""Name the scripts directory of the Mac's reference-checkout, once for every program.

The launchers, launch-claude-ubuntu and launch-claude-mac, are not on the Mac's PATH, so a
command a program prints for the user to type in a Mac Terminal names them by this path.
The value does not end in a slash.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "mac_reference_checkout_launcher_scripts_directory_path_constant_common", <path>)
"""

MAC_REFERENCE_CHECKOUT_LAUNCHER_SCRIPTS_DIRECTORY_PATH = "/Users/el/Projects/nedschorus/scripts"
