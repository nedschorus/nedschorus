---
issue: "[One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents](https://github.com/nedschorus/nedschorus/issues/1515)"
---

# One Claude Code hook starts slow work early and a later hook adds the result, and a wiki page on hook techniques for controlling and instructing agents

A Claude Code hook that must answer before the agent's turn ends has little time, so slow work, such as a review of what the agent just wrote, cannot run there. This GHI proposes a technique: an earlier hook starts the slow work as soon as the work's input exists, and a later hook adds the result when the result is ready. The example: a MessageDisplay hook, which runs while the agent's reply streams to the screen, starts a background process; the Stop hook, which runs when the turn ends, then shows the result to the user as a `systemMessage`, or hands the result to the agent by blocking the stop with the result as the reason. The GHI also proposes a wiki page on hook techniques for controlling and instructing agents, with the order of hook events as measured.

## Why

The user, on 2026-10-16 at about 02:30Z, in merge-lane-2's agent-session on ned-box: "the ideal is that the MessageDisplay lets us do something ASAP, and by the time the next hook runs, and the something is ready, we can say/add the something. This might be a new trick or technique we can use to control and instruct agents - and someday we'll have a wiki page on that."

One GHI already pairs two hooks this way without naming the technique: GHI-MD `docs/issues/14-review-the-legacy-system-s-bad-phrase-list.md` (GHI [A project style guide](https://github.com/nedschorus/nedschorus/issues/14)) pairs a MessageDisplay mark with a Stop hook. Related GHIs: GHI [A fresh agent of the other agent-binary tries to break each proposal](https://github.com/nedschorus/nedschorus/issues/1230) rejected a MessageDisplay hook for spotting proposals. GHI [Move mechanical agent chores into programs and hooks](https://github.com/nedschorus/nedschorus/issues/1036) moves agent chores into hooks. GHI [A Stop hook's report inside a claude -p review cell displaces the cell's report](https://github.com/nedschorus/nedschorus/issues/397), closed, shows a Stop hook's output changing what a `claude -p` agent reports. No wiki page describes hook techniques or the hook event order: of the file names in `docs/nedschorus-wiki/` on main, only one contains "hook", the page on writing a hook's refusal message.

## What is measured

A canary test on ned-box, Claude Code 2.1.301, 2026-10-16. Its hooks, settings and logs are in the directory `nedlern@ned-box:/home/nedlern/nedschorus-logs/canaries/canary-2026-10-16-messagedisplay-then-stop-hook/`, where `hook-input.log` holds every hook input with its time and `interactive-pane.txt` holds the screen.

- MessageDisplay fires once for each batch of newly finished lines. The input field `final` is true once per message, not once per turn: a turn with a tool call has two messages and two `final` batches. No field marks the turn's last message.
- In the canary's agent-session, Stop fired 1 to 2 ms after the last `final` batch. In the user's agent-session, started with `--remote-control`, the last batch's MessageDisplay fired about 1 ms after Stop. So the slow work gains only the time the message takes to stream, not the whole turn, and the Stop hook cannot rely on MessageDisplay having fired first.
- The screen waits for the MessageDisplay hook: a hook that slept 3 seconds delayed the text by about 3 seconds (measured 2026-10-01 on Claude Code 2.1.287, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/message-display-hook-live-test-2026-10-01.md`). The hook must start the slow work in the background and return at once.
- Replacement text works only as `displayContent` inside `hookSpecificOutput`. A top-level `displayContent` is ignored, with no error.
- The replaced text showed in a plain tmux session. The replaced text did not show in the user's `--remote-control` agent-session, in iTerm2, or on his phone, although the hook fired.
- The model and the transcript never see `displayContent`. Under `claude -p`, stdout and the JSON `result` field do include `displayContent`.

From the hooks documentation, https://code.claude.com/docs/en/hooks: a Stop hook can make the agent continue at most 8 times in a row, and "The count of consecutive continuations resets each time Claude calls a tool"; all hooks that match an event run in parallel.

## Next action

1. Pick one real use, such as reviewing each reply for words from the style guide, and design the technique for that use: what the MessageDisplay hook starts, where the background process writes its result, and what the Stop hook does when the result is not ready yet. The design also answers what the measurements raise: what happens when Stop fires before the last MessageDisplay; whether a `final` batch before a tool call starts the work, given that no field marks the turn's last message; how a result reaches a user whose screen does not show `displayContent`; and how a Stop hook that hands results to the agent stays under the cap of 8 continuations.
2. Build the design and try the design on one agent-seat on ned-box, and measure how often the result is ready when Stop fires, in a plain tmux session and in a `--remote-control` agent-session.
3. Write the wiki page from those measurements and the facts above: the hook event order, what each hook can change and who sees the change, and the techniques that work.
