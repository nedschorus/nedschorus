#!/usr/bin/env python3
"""Open an iTerm window, a Typora file or a browser page on this Mac, or send its agent-seat task lists, at ned-box's request.

Usage: SSH_ORIGINAL_COMMAND='<request>' scripts/mac-request-from-ned-box-forced-command.py

This program is the forced command of one line in the Mac's
~/.ssh/authorized_keys, the line that admits ned-box's key. sshd runs it in
place of whatever ned-box asked to run, and puts ned-box's request in
SSH_ORIGINAL_COMMAND. The request is never handed to a shell on the Mac: it is
split, checked word by word, and only then passed as separate arguments to
scripts/open-iterm-window-running-command, which opens a window running

    ssh -t -- nedlern@ned-box <word> <word> ...

Two guards keep every word part of the remote command. OpenSSH parses options
again when the word right after the destination starts with `-`, so a first
word such as `-oProxyCommand=/path` would set an option and run that program on
the Mac. The first word may therefore not start with `-`, and the `--` before
the destination ends option parsing as well.

So the most a request can do is open a window on the user's screen that runs a
command on ned-box, where ned-box's agents can already run anything.

THE ACCEPTED SHAPE:

    open-window <word> [<word> ...]

- The verb is exactly `open-window`, followed by 1 to MAXIMUM_WORD_COUNT words.
- Words are separated by single spaces. ssh joins its remote arguments with
  single spaces, so for words without whitespace the split gives back exactly
  the words the caller sent.
- Each word is 1 to MAXIMUM_WORD_LENGTH characters from SAFE_WORD_PATTERN:
  letters, digits and `_ . / : = @ % + , -`. None of those characters means
  anything to iTerm's command parser or to the shell on ned-box that runs the
  remote command, so the words need no quoting on either side, and quoting is
  what cannot be done safely through iTerm (its parser does not implement the
  POSIX '\\'' escape).
- The first word, the command's name, may not start with `-`.
- The whole request is at most MAXIMUM_REQUEST_LENGTH characters.

What the shape cannot express: shell syntax on ned-box (pipes, `;`, `$VAR`,
globs), quoted words, words with spaces. A caller that needs those puts them in
a script on ned-box and asks for a window running that script.

THE SECOND ACCEPTED SHAPE, a window onto one of ned-box's agent-seats:

    open-agent-seat-window <seat>

- The verb is exactly `open-agent-seat-window`, followed by exactly one word,
  the agent-seat's name, matching AGENT_SEAT_NAME_PATTERN: letters, digits,
  `_` and `-`, not starting with `-`, at most 64 characters. These are the
  names launch-claude-ubuntu accepts, so no request opens a window that its
  launcher refuses at once.
- The window runs this checkout's scripts/launch-claude-ubuntu <seat>, the
  same window the Mac's login restore opens onto each live box seat. That
  launcher reconnects when the ssh connection drops, which a window running
  `ssh -t -- nedlern@ned-box tmux attach` does not.

So the most this verb can do is open the window the user's own launcher opens
onto a seat.

THE THIRD ACCEPTED SHAPE, a file to open in Typora:

    open-in-typora <path>

- The verb is exactly `open-in-typora`, followed by exactly one word.
- The word is an absolute path on ned-box under NED_BOX_HOME, made of the
  SAFE_WORD_PATTERN characters, at most MAXIMUM_PATH_LENGTH long, with no
  empty, `.` or `..` component and no trailing `/`.
- The Mac reaches ned-box's home through the network mount MAC_MOUNT_OF_NED_BOX_HOME,
  so the path is mapped onto that mount. The mount must be mounted, the mapped
  path must be a file, and with every symlink resolved it must still lie
  inside the mount: a link that leads elsewhere on the Mac is refused.
- The file is opened with `open -a Typora <mapped path>`, given to `open` as
  an argument list, never to a shell. The mapped path always starts with `/`,
  so `open` cannot read it as an option.

So the most this verb can do is open, in Typora, a file the Mac can already
read from ned-box's home.

THE FOURTH ACCEPTED SHAPE, an HTML page to open in the default browser:

    open-in-browser <path>

- The verb is exactly `open-in-browser`, followed by exactly one word, checked
  as open-in-typora's path is, and further: the path lies under ned-box's
  log-store, NED_BOX_HOME/LOG_STORE_DIRECTORY_NAME/, and ends in
  BROWSER_PAGE_SUFFIX.
- It is mapped onto the mount and checked there the same way, symlinks
  resolved, and must still lie inside the mapped log-store.
- The page is opened with `open <mapped path>`, given to `open` as an argument
  list, so the Mac's default application for .html files, its browser, shows
  it. A page opened from a file runs no request to any server.

So the most this verb can do is open, with the Mac's default application for
it, a file named .html under ned-box's log-store, which the Mac can already
read. The name is checked, not the file a link leads to inside the log-store.

THE FIFTH ACCEPTED SHAPE, the Mac's agent-seat task lists, read:

    read-agent-seat-task-lists

- The request is exactly the verb, with no words after it.
- The Mac's task store, TASK_STORE_UNDER_HOME under its home, must be a
  directory; a missing store is refused with EXIT_NO_TASK_STORE.
- tar archives the store to standard output, which carries the archive and
  nothing else, so ned-box's scripts/seat-task-list-read.py can unpack it as
  it unpacks ned-box's own. Every message goes to standard error.
  COPYFILE_DISABLE keeps the Mac's tar from adding `._` extended-attribute
  files, which the reader would take for task files.
- Any tar failure exits EXIT_TAR_FAILED, so the reader can tell it from a
  refusal, which exits EXIT_REFUSED, as tar's own fatal status also does.

So the most this verb can do is hand ned-box a copy of the Mac's task lists.

Every request, accepted or refused, is appended to REQUEST_LOG_PATH, so the
user can see what ned-box asked his Mac to do. An accepted request is logged
before its window opens, and a request that cannot be logged opens no window:
otherwise a window could open on the user's screen that the log never records.
The outcome line after the opener returns is reported if it cannot be written,
but does not change the exit status, because the window has already opened and
a caller told it failed would ask for a second one.

NEDSCHORUS_MAC_WINDOW_OPENER overrides the opener's path, NEDSCHORUS_MAC_OPEN_PROGRAM
the program that opens Typora and the browser, NEDSCHORUS_NED_BOX_HOME ned-box's home and
NEDSCHORUS_MAC_NED_BOX_HOME_MOUNT the Mac's mount of it: the seams the test
suites use, so no test opens a real window or a real file. sshd does not pass
a client's environment to a forced command, so ned-box cannot set them.
"""

import importlib.util
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ned_box_home_specification = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_home_path_constants = importlib.util.module_from_spec(_ned_box_home_specification)
_ned_box_home_specification.loader.exec_module(ned_box_home_path_constants)

PROGRAM = "mac-request-from-ned-box-forced-command"
REQUEST_VERB = "open-window"
AGENT_SEAT_WINDOW_VERB = "open-agent-seat-window"
# launch-claude-ubuntu refuses any other seat name; its test checks the two rules agree.
AGENT_SEAT_NAME_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}")
LAUNCH_CLAUDE_UBUNTU_PATH = Path(__file__).with_name("launch-claude-ubuntu")
SAFE_WORD_PATTERN = re.compile(r"[A-Za-z0-9_./:=@%+,-]+")
MAXIMUM_WORD_COUNT = 32
MAXIMUM_WORD_LENGTH = 256
MAXIMUM_REQUEST_LENGTH = 2048
NED_BOX_SSH_DESTINATION = "nedlern@ned-box"
DEFAULT_WINDOW_OPENER = Path(__file__).with_name("open-iterm-window-running-command")
REQUEST_LOG_PATH = Path.home() / ".claude" / "mac-window-opened-for-ned-box.log"
TYPORA_VERB = "open-in-typora"
TYPORA_APPLICATION = "Typora"
NED_BOX_HOME = ned_box_home_path_constants.NED_BOX_HOME
MAC_MOUNT_OF_NED_BOX_HOME = ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME
MAXIMUM_PATH_LENGTH = 1024
DEFAULT_OPEN_PROGRAM = "/usr/bin/open"
OPEN_IN_BROWSER_REQUEST_VERB = "open-in-browser"
LOG_STORE_DIRECTORY_NAME = "nedschorus-logs"
BROWSER_PAGE_SUFFIX = ".html"
AGENT_SEAT_TASK_LISTS_READ_VERB = "read-agent-seat-task-lists"
TASK_STORE_UNDER_HOME = Path(".claude") / "tasks"

EXIT_OPENED = 0
EXIT_REFUSED = 2
EXIT_OPENER_FAILED = 1
EXIT_LOG_UNWRITABLE = 3
EXIT_NO_TASK_STORE = 4
EXIT_TAR_FAILED = 5


class RequestRefused(Exception):
    pass


def window_command_words(request):
    """The words to run on ned-box, from one request; raises RequestRefused."""
    if request is None:
        raise RequestRefused(
            "no request: SSH_ORIGINAL_COMMAND is unset, so this login asked for an interactive shell, which this key is not allowed")
    if len(request) > MAXIMUM_REQUEST_LENGTH:
        raise RequestRefused(f"the request is {len(request)} characters, over the limit of {MAXIMUM_REQUEST_LENGTH}")
    if request == "":
        raise RequestRefused("the request is empty")
    words = request.split(" ")
    if words[0] != REQUEST_VERB:
        raise RequestRefused(f"the request does not start with the verb {REQUEST_VERB!r}")
    command_words = words[1:]
    if not command_words:
        raise RequestRefused(f"{REQUEST_VERB} names no command to run on ned-box")
    if len(command_words) > MAXIMUM_WORD_COUNT:
        raise RequestRefused(f"the request has {len(command_words)} words, over the limit of {MAXIMUM_WORD_COUNT}")
    if command_words[0].startswith("-"):
        raise RequestRefused("the first word starts with '-', which ssh could read as an option rather than a command")
    for position, word in enumerate(command_words, start=1):
        if word == "":
            raise RequestRefused(f"word {position} is empty: words are separated by exactly one space")
        if len(word) > MAXIMUM_WORD_LENGTH:
            raise RequestRefused(f"word {position} is {len(word)} characters, over the limit of {MAXIMUM_WORD_LENGTH}")
        if not SAFE_WORD_PATTERN.fullmatch(word):
            raise RequestRefused(
                f"word {position} holds a character outside letters, digits and _ . / : = @ % + , - "
                "(quotes, spaces, shell syntax and control characters cannot pass safely through iTerm and ned-box's shell)")
    return command_words


def window_command(command_words):
    return ["ssh", "-t", "--", NED_BOX_SSH_DESTINATION, *command_words]


def agent_seat_window_seat_name(request):
    """The agent-seat an open-agent-seat-window request names; raises RequestRefused."""
    if request is None:
        raise RequestRefused(
            "no request: SSH_ORIGINAL_COMMAND is unset, so this login asked for an interactive shell, which this key is not allowed")
    words = request.split(" ")
    if words[0] != AGENT_SEAT_WINDOW_VERB:
        raise RequestRefused(f"the request does not start with the verb {AGENT_SEAT_WINDOW_VERB!r}")
    if len(words) != 2:
        raise RequestRefused(
            f"{AGENT_SEAT_WINDOW_VERB} takes exactly one agent-seat name, and the request has {len(words) - 1} words after the verb")
    if not AGENT_SEAT_NAME_PATTERN.fullmatch(words[1]):
        raise RequestRefused(
            "the agent-seat name is empty, over 64 characters, starts with '-', "
            "or holds a character other than letters, digits, _ and -")
    return words[1]


def agent_seat_window_command(seat):
    return [str(LAUNCH_CLAUDE_UBUNTU_PATH), seat]


def typora_path_on_ned_box(request, ned_box_home=NED_BOX_HOME):
    """The ned-box path an open-in-typora request names; raises RequestRefused.

    Checks the text alone, so ned-box can run it before sending."""
    return ned_box_file_path_in_request(request, TYPORA_VERB, ned_box_home)


def open_in_browser_request_html_page_path_check(request, ned_box_home=NED_BOX_HOME):
    """The ned-box path an open-in-browser request names; raises RequestRefused.

    Checks the text alone, so ned-box can run it before sending."""
    path = ned_box_file_path_in_request(request, OPEN_IN_BROWSER_REQUEST_VERB, ned_box_home)
    pages_prefix = f"{ned_box_home.rstrip('/')}/{LOG_STORE_DIRECTORY_NAME}/"
    if not path.startswith(pages_prefix):
        raise RequestRefused(f"the page is not under {pages_prefix}, the only place pages are opened from")
    if not path.endswith(BROWSER_PAGE_SUFFIX):
        raise RequestRefused(f"the page's name does not end in {BROWSER_PAGE_SUFFIX}")
    return path


def ned_box_file_path_in_request(request, verb, ned_box_home):
    """The one absolute ned-box path a `<verb> <path>` request names; raises RequestRefused."""
    if request is None:
        raise RequestRefused(
            "no request: SSH_ORIGINAL_COMMAND is unset, so this login asked for an interactive shell, which this key is not allowed")
    if len(request) > MAXIMUM_REQUEST_LENGTH:
        raise RequestRefused(f"the request is {len(request)} characters, over the limit of {MAXIMUM_REQUEST_LENGTH}")
    words = request.split(" ")
    if words[0] != verb:
        raise RequestRefused(f"the request does not start with the verb {verb!r}")
    if len(words) != 2:
        raise RequestRefused(f"{verb} takes exactly one path, and the request has {len(words) - 1} words after the verb")
    path = words[1]
    if path == "":
        raise RequestRefused(f"{verb} names no path")
    if len(path) > MAXIMUM_PATH_LENGTH:
        raise RequestRefused(f"the path is {len(path)} characters, over the limit of {MAXIMUM_PATH_LENGTH}")
    if not SAFE_WORD_PATTERN.fullmatch(path):
        raise RequestRefused(
            "the path holds a character outside letters, digits and _ . / : = @ % + , - "
            "(spaces, quotes and control characters cannot pass through ssh as one word)")
    home_prefix = ned_box_home.rstrip("/") + "/"
    if not path.startswith(home_prefix):
        raise RequestRefused(f"the path is not under {home_prefix}, the only place the Mac can see on ned-box")
    components = path[len(home_prefix):].split("/")
    if any(component in ("", ".", "..") for component in components):
        raise RequestRefused("the path has an empty, '.' or '..' component, or ends in '/'; give the file's plain absolute path")
    return path


def ned_box_file_on_mac(ned_box_path, ned_box_home=NED_BOX_HOME, mount=MAC_MOUNT_OF_NED_BOX_HOME, within=""):
    """The Mac path of a checked ned-box path, through the mount; raises RequestRefused.

    With every symlink resolved, the file must lie inside the mount, or inside
    `within`, a directory under it, when one is given."""
    if not os.path.ismount(mount):
        raise RequestRefused(f"{mount}, the Mac's mount of ned-box's home, is not mounted; the Mac must mount ned-box's home there")
    relative = ned_box_path[len(ned_box_home.rstrip("/")) + 1:]
    mac_path = os.path.join(mount, relative)
    if not os.path.lexists(mac_path):
        raise RequestRefused(f"there is no {mac_path} on the Mac, which is {ned_box_path} on ned-box")
    resolved = os.path.realpath(mac_path)
    boundary = os.path.join(mount, within) if within else mount
    if os.path.commonpath([resolved, os.path.realpath(boundary)]) != os.path.realpath(boundary):
        raise RequestRefused(f"{mac_path} is a link that leads outside {boundary}, to {resolved}")
    if not os.path.isfile(resolved):
        raise RequestRefused(f"{mac_path} is not a file")
    return mac_path


def append_to_request_log(outcome, request):
    """Append one line; return the OSError's text when the line was not written, else None."""
    try:
        REQUEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REQUEST_LOG_PATH.open("a") as log:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            log.write(f"{stamp} {outcome} {request!r}\n")
    except OSError as error:
        return str(error)
    return None


def open_in_typora(request):
    ned_box_home = os.environ.get("NEDSCHORUS_NED_BOX_HOME") or NED_BOX_HOME
    mount = os.environ.get("NEDSCHORUS_MAC_NED_BOX_HOME_MOUNT") or MAC_MOUNT_OF_NED_BOX_HOME
    try:
        mac_path = ned_box_file_on_mac(typora_path_on_ned_box(request, ned_box_home), ned_box_home, mount)
    except RequestRefused as refusal:
        log_error = append_to_request_log("refused", request)
        print(f"{PROGRAM}: Typora was not opened, because {refusal}.", file=sys.stderr)
        print(f"To open a file in Typora, run on ned-box: scripts/open-file-in-typora-on-mac-from-ned-box.py <path of a file under {ned_box_home}/>", file=sys.stderr)
        print("If you already ran that with an existing file, tell the user this reason and the file you wanted shown.", file=sys.stderr)
        if log_error:
            print(f"The refusal could not be added to the request log {REQUEST_LOG_PATH} either: {log_error}", file=sys.stderr)
        return EXIT_REFUSED
    log_error = append_to_request_log("accepted", request)
    if log_error:
        print(f"{PROGRAM}: Typora was not opened, because the request could not be added to the request log {REQUEST_LOG_PATH}: {log_error}.", file=sys.stderr)
        print("Every file ned-box opens on the Mac is logged first, so none opens unlogged. Tell the user this error.", file=sys.stderr)
        return EXIT_LOG_UNWRITABLE
    open_program = os.environ.get("NEDSCHORUS_MAC_OPEN_PROGRAM") or DEFAULT_OPEN_PROGRAM
    result = subprocess.run([open_program, "-a", TYPORA_APPLICATION, mac_path], capture_output=True, text=True)
    if result.returncode != 0:
        log_error = append_to_request_log(f"open-failed-{result.returncode}", request)
        print(f"{PROGRAM}: open exited {result.returncode}, so Typora may not have opened {mac_path}: {result.stderr.strip()}", file=sys.stderr)
        print("Whatever the error, tell the user this error and the file you wanted shown; if it says Typora cannot be found, add that Typora is not installed on the Mac.", file=sys.stderr)
        if log_error:
            print(f"The failure could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        return EXIT_OPENER_FAILED
    log_error = append_to_request_log("opened", request)
    print(f"{PROGRAM}: opened {mac_path} in Typora on the Mac")
    if log_error:
        print(f"{PROGRAM}: Typora opened the file, but its outcome could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        print("Do not ask for the file again. Tell the user this error.", file=sys.stderr)
    return EXIT_OPENED


def open_in_browser(request):
    ned_box_home = os.environ.get("NEDSCHORUS_NED_BOX_HOME") or NED_BOX_HOME
    mount = os.environ.get("NEDSCHORUS_MAC_NED_BOX_HOME_MOUNT") or MAC_MOUNT_OF_NED_BOX_HOME
    try:
        mac_path = ned_box_file_on_mac(open_in_browser_request_html_page_path_check(request, ned_box_home), ned_box_home, mount,
                                       within=LOG_STORE_DIRECTORY_NAME)
    except RequestRefused as refusal:
        log_error = append_to_request_log("refused", request)
        print(f"{PROGRAM}: the page was not opened, because {refusal}.", file=sys.stderr)
        print(f"To open a page in the Mac's browser, run on ned-box: scripts/open-html-page-in-mac-browser-from-ned-box.py "
              f"<path of a .html file under {ned_box_home}/{LOG_STORE_DIRECTORY_NAME}/>", file=sys.stderr)
        print("If you already ran that with an existing page, tell the user this reason and the page you wanted shown.", file=sys.stderr)
        if log_error:
            print(f"The refusal could not be added to the request log {REQUEST_LOG_PATH} either: {log_error}", file=sys.stderr)
        return EXIT_REFUSED
    log_error = append_to_request_log("accepted", request)
    if log_error:
        print(f"{PROGRAM}: the page was not opened, because the request could not be added to the request log {REQUEST_LOG_PATH}: {log_error}.", file=sys.stderr)
        print("Every page ned-box opens on the Mac is logged first, so none opens unlogged. Tell the user this error.", file=sys.stderr)
        return EXIT_LOG_UNWRITABLE
    open_program = os.environ.get("NEDSCHORUS_MAC_OPEN_PROGRAM") or DEFAULT_OPEN_PROGRAM
    result = subprocess.run([open_program, mac_path], capture_output=True, text=True)
    if result.returncode != 0:
        log_error = append_to_request_log(f"open-failed-{result.returncode}", request)
        print(f"{PROGRAM}: open exited {result.returncode}, so the browser may not have opened {mac_path}: {result.stderr.strip()}", file=sys.stderr)
        print("Tell the user this error and the page you wanted shown, which he can open himself at that path.", file=sys.stderr)
        if log_error:
            print(f"The failure could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        return EXIT_OPENER_FAILED
    log_error = append_to_request_log("opened", request)
    print(f"{PROGRAM}: opened {mac_path} in the Mac's browser")
    if log_error:
        print(f"{PROGRAM}: the browser opened the page, but its outcome could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        print("Do not ask for the page again. Tell the user this error.", file=sys.stderr)
    return EXIT_OPENED


def agent_seat_task_lists_read(request):
    if request != AGENT_SEAT_TASK_LISTS_READ_VERB:
        log_error = append_to_request_log("refused", request)
        print(f"{PROGRAM}: the task lists were not sent, because {AGENT_SEAT_TASK_LISTS_READ_VERB} takes no words after it.",
              file=sys.stderr)
        print(f"Send the request {AGENT_SEAT_TASK_LISTS_READ_VERB} alone; on ned-box, scripts/seat-task-list-read.py sends it.",
              file=sys.stderr)
        if log_error:
            print(f"The refusal could not be added to the request log {REQUEST_LOG_PATH} either: {log_error}", file=sys.stderr)
        return EXIT_REFUSED
    store = Path.home() / TASK_STORE_UNDER_HOME
    if not store.is_dir():
        log_error = append_to_request_log("no-task-store", request)
        print(f"{PROGRAM}: the task lists were not sent, because there is no task store at {store} on the Mac.", file=sys.stderr)
        print("Tell the user; no agent-seat on the Mac has written a task list yet, or the store has moved.", file=sys.stderr)
        if log_error:
            print(f"This could not be added to the request log {REQUEST_LOG_PATH} either: {log_error}", file=sys.stderr)
        return EXIT_NO_TASK_STORE
    log_error = append_to_request_log("accepted", request)
    if log_error:
        print(f"{PROGRAM}: the task lists were not sent, because the request could not be added to the request log "
              f"{REQUEST_LOG_PATH}: {log_error}.", file=sys.stderr)
        print("Every request ned-box makes of the Mac is logged first. Tell the user this error.", file=sys.stderr)
        return EXIT_LOG_UNWRITABLE
    sys.stdout.flush()
    result = subprocess.run(["tar", "-C", str(store), "-cf", "-", "."], stdout=sys.stdout.buffer, stderr=subprocess.PIPE,
                            env={**os.environ, "COPYFILE_DISABLE": "1"})
    if result.returncode != 0:
        log_error = append_to_request_log(f"tar-failed-{result.returncode}", request)
        print(f"{PROGRAM}: tar exited {result.returncode}, so the archive of {store} may be incomplete: "
              f"{result.stderr.decode('utf-8', 'replace').strip()}", file=sys.stderr)
        print("Run the read again; if it fails twice, tell the user this error.", file=sys.stderr)
        if log_error:
            print(f"The failure could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        return EXIT_TAR_FAILED
    log_error = append_to_request_log("sent", request)
    if log_error:
        print(f"{PROGRAM}: the task lists were sent, but the outcome could not be added to the request log "
              f"{REQUEST_LOG_PATH}: {log_error}. Tell the user this error.", file=sys.stderr)
    return EXIT_OPENED


def main():
    # sshd passes a forced command no arguments, so only a person running it by hand reaches this.
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    request = os.environ.get("SSH_ORIGINAL_COMMAND")
    if request is not None and request.split(" ")[0] == AGENT_SEAT_TASK_LISTS_READ_VERB:
        return agent_seat_task_lists_read(request)
    if request is not None and request.split(" ")[0] == TYPORA_VERB:
        return open_in_typora(request)
    if request is not None and request.split(" ")[0] == OPEN_IN_BROWSER_REQUEST_VERB:
        return open_in_browser(request)
    try:
        if request is not None and request.split(" ")[0] == AGENT_SEAT_WINDOW_VERB:
            command = agent_seat_window_command(agent_seat_window_seat_name(request))
        else:
            command = window_command(window_command_words(request))
    except RequestRefused as refusal:
        log_error = append_to_request_log("refused", request)
        print(f"{PROGRAM}: no window was opened, because {refusal}.", file=sys.stderr)
        if request is not None and request.split(" ")[0] == AGENT_SEAT_WINDOW_VERB:
            print("To open an agent-seat's window, run on ned-box: scripts/open-mac-window-from-ned-box.py --agent-seat <seat>, "
                  "naming one agent-seat.", file=sys.stderr)
        else:
            print(f"Send a request of the form: {REQUEST_VERB} <word> [<word> ...], each word made of letters, digits and _ . / : = @ % + , -", file=sys.stderr)
            print("To open an agent-seat's window instead, run on ned-box: scripts/open-mac-window-from-ned-box.py --agent-seat <seat>", file=sys.stderr)
            print("To open a file in Typora instead, run on ned-box: scripts/open-file-in-typora-on-mac-from-ned-box.py <path>", file=sys.stderr)
            print("To open an HTML page in the browser instead, run on ned-box: scripts/open-html-page-in-mac-browser-from-ned-box.py <path>", file=sys.stderr)
            print("If the command needs shell syntax or quoted words, put it in a script on ned-box and ask for a window running that script.", file=sys.stderr)
        if log_error:
            print(f"The refusal could not be added to the request log {REQUEST_LOG_PATH} either: {log_error}", file=sys.stderr)
        return EXIT_REFUSED
    log_error = append_to_request_log("accepted", request)
    if log_error:
        print(f"{PROGRAM}: no window was opened, because the request could not be added to the request log {REQUEST_LOG_PATH}: {log_error}.", file=sys.stderr)
        print("Every window ned-box opens on the Mac is logged first, so none opens unlogged. Tell the user this error.", file=sys.stderr)
        return EXIT_LOG_UNWRITABLE
    opener = os.environ.get("NEDSCHORUS_MAC_WINDOW_OPENER") or str(DEFAULT_WINDOW_OPENER)
    result = subprocess.run(["/bin/sh", opener, *command],
                            capture_output=True, text=True)
    if result.returncode != 0:
        log_error = append_to_request_log(f"opener-failed-{result.returncode}", request)
        print(f"{PROGRAM}: the window opener exited {result.returncode}, so no window may have opened: {result.stderr.strip()}", file=sys.stderr)
        print("Tell the user the command you wanted shown, and this error.", file=sys.stderr)
        if log_error:
            print(f"The opener's failure could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        return EXIT_OPENER_FAILED
    log_error = append_to_request_log("opened", request)
    if result.stdout:
        sys.stdout.write(result.stdout)
    print(f"{PROGRAM}: opened a window on the Mac running: {' '.join(command)}")
    if log_error:
        print(f"{PROGRAM}: the window opened, but its outcome could not be added to the request log {REQUEST_LOG_PATH}: {log_error}", file=sys.stderr)
        print("Do not ask for the window again. Tell the user this error.", file=sys.stderr)
    return EXIT_OPENED


if __name__ == "__main__":
    sys.exit(main())
