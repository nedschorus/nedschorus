#!/usr/bin/env python3
"""Name ned-box's home directory and the Mac's mount of it, once for every program.

The Mac mounts ned-box's home over the network, so a file ned-box knows as
NED_BOX_HOME/<rest> opens on the Mac as MAC_MOUNT_OF_NED_BOX_HOME/<rest>.
Neither value ends in a slash; a program that compares prefixes adds its own.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "ned_box_home_directory_and_its_mac_mount_point_path_constants_common", <path>)

scripts/locate-file-copies-across-machines.py is sent over ssh alone and keeps
its own copy of the pair; its test fails when the copy differs from this file.
"""

NED_BOX_HOME = "/home/nedlern"
MAC_MOUNT_OF_NED_BOX_HOME = "/Volumes/nedhome"
