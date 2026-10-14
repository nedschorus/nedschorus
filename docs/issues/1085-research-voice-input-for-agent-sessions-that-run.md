---
issue: "[Research voice input for agent-sessions that run on ned-box](https://github.com/nedschorus/nedschorus/issues/1085)"
---

# Research voice input for agent-sessions that run on ned-box

## Problem

The user wants to speak to his agents instead of typing to them. He sits at a Mac. Most agent-seats run on ned-box, the Ubuntu machine on the same LAN, each in its own tmux server. He reaches them from iTerm2 windows on the Mac over ssh, with [`scripts/launch-claude-ubuntu`](https://github.com/nedschorus/nedschorus/blob/main/scripts/launch-claude-ubuntu) `<name>` or `ssh -t nedlern@ned-box tmux -L <name> attach -t <name>`. He reaches some agent-sessions through Remote Control in the Claude app instead.

## What is known

- A Claude Code plugin runs on ned-box, so a plugin cannot reach the Mac's microphone.
- Two ways that need nothing built were suggested to him: macOS Dictation (press Fn twice), which types into the focused ssh window, and the voice input of the Claude app through Remote Control. On 2026-10-05 he said neither works for him (approval-walk merge-lane-2-remaining-questions-walk-2026-10-05, item 1, in a merge-lane-2 agent-session). How each one failed is not recorded.

## Next action

An agent first asks the user how Dictation and Remote Control voice input failed for him. Then the agent researches options for both ways he reaches agents, the ssh windows and Remote Control, for example speech-to-text on the Mac that types into the ssh window. The agent brings back a short comparison with a recommendation for the user to rule on. Building anything waits for that ruling.
