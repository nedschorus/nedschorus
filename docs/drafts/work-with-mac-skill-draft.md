---
name: get-mac-work-done-from-ned-box
description: Use on ned-box when work needs the user's Mac, such as a Mac test run, a Mac setting, or a file or program only the Mac has, and before telling the user to run anything on his Mac. Gives the ways to get the work done without him, in order, and the traps of the /Volumes/nedhome mount, /tmp and reboots.
---

# Get Mac work done from ned-box

The user sits at his Mac, and wants agents on ned-box to get Mac work done without asking him. Try these ways in order. Way 1 needs nothing from him. Way 2 needs nothing from him while the Mac agent-seat it needs is running; otherwise it starts that agent-seat with way 4. Way 3 needs nothing from him. Way 4 asks him to run one line and to say when the script has finished. Way 5 asks him for more, and comes last. The Mac's home directory is `/Users/el`, and its clone of this repository is `/Users/el/Projects/nedschorus`, a different clone from any on ned-box.

1. **Do the work on ned-box, if it can happen there.** ned-box holds the log-store, `/home/nedlern/nedschorus-logs/`; the transcript mirror, which copies the Mac's agent-session transcripts and session-handoffs to `/home/nedlern/nedschorus-logs/transcripts/mac/projects/` and `/home/nedlern/nedschorus-logs/transcripts/mac/handoffs/`; the records of the Mac's daily full test runs of main, in `/home/nedlern/nedschorus-logs/daily-full-test-runs/mac/`; and git and `gh`, which reach GitHub and the branches the Mac has pushed there. Before you rely on the transcript mirror, read `/home/nedlern/nedschorus-logs/transcripts/mac/last-complete-mirror-pass-utc.txt`, the UTC time of the last complete mirror pass. Commits the Mac has not pushed, and Mac files this list does not name, are not on ned-box.
2. **For a Mac test run or other agent work only the Mac can do, message a Mac agent-seat** with the SendMessage tool. The Mac agent-seat cold-read-research is the one kept for Mac test runs, whatever its name suggests, and runs only when needed. Run ListAgents just before you send: it can list several rows under one agent-seat's name, most of them offline, and list the running agent-session under another name, such as a title taken from its conversation. Send to the row that is not offline, by the ref ListAgents prints for it. If none of the agent-seat's own rows is running but a row with a conversation title is, ask the agent-session behind that row which agent-seat it is before you send it work. If no row for the agent-seat you need is running, start the agent-seat with way 4, a script that runs `/Users/el/Projects/nedschorus/scripts/launch-claude-mac <agent-seat name> --no-attach` on the Mac and then opens an iTerm window onto the agent-seat with `/Users/el/Projects/nedschorus/scripts/open-iterm-window-running-command tmux -L <agent-seat name> attach -t <agent-seat name>`, so the user sees the agent-seat as he sees the others; then message it.
3. **To show the user something running on ned-box, open a window on his Mac** with `scripts/open-mac-window-from-ned-box.py <word> [<word> ...]`, for example `scripts/open-mac-window-from-ned-box.py tmux -L merge-lane-2 attach -t merge-lane-2`. The Mac opens an iTerm window running `ssh -t -- nedlern@ned-box <word> ...`, so the command runs on ned-box, not on the Mac: this way shows the user a program, and the work stays on ned-box. The Mac accepts at most 32 words, each made only of letters, digits and `_ . / : = @ % + , -`; the first word may not start with `-`; spaces, quotes and shell syntax such as pipes, `;` and `$VAR` are refused. Put a command that needs them in a script on ned-box and pass the script's path. The Mac logs every request. To open a file from ned-box in Typora on the Mac, run `scripts/open-file-in-typora-on-mac-from-ned-box.py <path under /home/nedlern/>`. If either program prints that the Mac could not be reached or refused the key, tell the user what it printed, remedy included.
4. **For Mac work no agent can do, write a script that the user runs with one command.** Store the script in `/home/nedlern/nedschorus-logs/one-off-scripts/`, named `mac-<what it acts on>-<what it does>.sh`, and tell the user one line: in a terminal on the Mac, run `bash /Volumes/nedhome/nedschorus-logs/one-off-scripts/<name>.sh`. The Mac mounts ned-box's `/home/nedlern` as `/Volumes/nedhome`, so the script also reads and writes ned-box's files through that mount. The script writes all its output to a `.out` file beside itself, so you read the result on ned-box and the user pastes nothing. Write the script so that it:
   - starts with a comment giving the line the user runs and what the script changes;
   - sends its output to the `.out` file, with these two lines after that comment:

     ```
     OUT="$(dirname "$0")/$(basename "$0" .sh).out"
     exec > >(tee "$OUT") 2>&1
     ```

   - prints `run at $(date -u +%FT%TZ) on $(hostname)` first, so you can tell this invocation's `.out` from an older one;
   - checks each precondition before it changes anything, and on a failed one prints a line starting `STOP:` that says nothing was changed, and exits nonzero;
   - copies a file to a dated backup before it edits that file.

   A script that must keep running while ned-box reboots must also run from a copy of itself in the Mac's `/tmp`, because the mount disappears during the reboot and bash reads a script as it runs. Such a script first copies itself to the Mac's `/tmp` and runs from there, so its two `.out` lines write the `.out` file in `/tmp`; at the end it remounts `/Volumes/nedhome` if the mount is gone, and copies the `.out` file back to `$ORIGINAL_SCRIPT_DIRECTORY`, beside the original script, retrying while the mount comes back. If the copy fails, the script tells the user to paste the `/tmp` file's path to you. Its ssh commands turn off the master connection the Mac's ssh configuration keeps open, because the reboot kills that connection, and they time out: `-o ControlMaster=no -o ControlPath=none -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=2`. These lines go between the opening comment and the two `.out` lines:

   ```
   NAME="$(basename "$0" .sh)"
   if [ "${RUNNING_FROM_LOCAL_COPY:-}" != yes ]; then
       cp "$0" "/tmp/$NAME.sh" || { echo "could not copy this script to /tmp; nothing was done"; exit 1; }
       RUNNING_FROM_LOCAL_COPY=yes ORIGINAL_SCRIPT_DIRECTORY="$(cd "$(dirname "$0")" && pwd)" exec bash "/tmp/$NAME.sh"
   fi
   ```

   A script needed a second time is no longer a one-off: move it into the repository's `scripts/` through a pull request, with a test, so it is reviewed and both clones get it.

   After the user says the script has finished, read its `.out` file before you report anything. If the `.out` file has a `STOP:` line, tell the user what stopped and fix the cause before you ask him to run the script again.
5. **Ask the user only for a password, a browser login or something physical**, such as power or a cable. Name the machine, and give the exact command where there is one. Where the step needing him is a password a command asks for, put the command in a way 4 script, so that, besides running the script, typing the password is all he does.

## Traps

- `/Volumes/nedhome` does not remount by itself after ned-box reboots. Remount it on the Mac with `open 'smb://nedlern@10.0.1.106/nedhome'`, ned-box's wired IP address; if that fails, use `open 'smb://nedlern@10.0.1.39/nedhome'`, its Wi-Fi IP address. Outside ssh, the Mac cannot look up the host name ned-box, so a script that remounts uses the IP addresses, the wired one first.
- ned-box's `/tmp` is a tmpfs, emptied at every reboot, the scratchpad directory Claude Code gives each agent-session included, and files left untouched for 10 days there are deleted. macOS deletes files in its `/tmp` left untouched for 3 days. Keep anything needed later in the log-store.
- The Mac's ssh configuration points both `ned` and `ned-box` at 10.0.1.106, ned-box's wired IP address, and keeps one master connection open for 10 minutes after the last use, which later ssh commands reuse; a ned-box reboot kills that connection.
- `ned` is a host alias in the Mac's ssh configuration and means nothing on ned-box. `scripts/launch-claude-ubuntu` connects to `ned` unless `NEDSCHORUS_AGENT_BOX` names another ssh destination, so when you run it on ned-box, set `NEDSCHORUS_AGENT_BOX=nedlern@ned-box`, as the skill `start-new-agent-seat-on-ned-box` says.
