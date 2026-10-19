---
issue: "[Switch the agent-seats to another Claude account when the current account reaches its weekly usage limit](https://github.com/nedschorus/nedschorus/issues/1201)"
---

# Switch the agent-seats to another Claude account when the current account reaches its weekly usage limit

The user asked for this GHI on 2026-10-12 in the agent-session of the agent-seat prime-intellect on ned-box (transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-prime-intellect/bafa2657-92ad-439d-ac19-89fdad69d71e.jsonl`), separating it from the 5-hour limit: "But if the agent hits the weekly limit, that is a different problem, one that needs its own GHI. That requires logging out of all devices, and trying to login, which generates an email or a code, which has to be clicked on of filled in in the right place, which all can be done, but it's quite different, and even that only works we the user has access to multiple accounts, wich at least one that is not beyond it's 5 hour or weekly limit. So file that week limit switcher as a separate issue".

## Why

A Claude subscription has two usage limits: one over a 5-hour window and one over a week. When an agent-seat reaches the 5-hour limit, it can resume within hours, once the window resets; GHI [Wake an agent-seat when its 5-hour session limit resets](https://github.com/nedschorus/nedschorus/issues/1152) covers waking it then. When an agent-seat reaches the weekly limit, it cannot work on that account until the weekly reset, which can be days away. Waiting is the only remedy today.

Evidence from ned-box's transcripts (`~/.claude/projects/*/*.jsonl`, searched 2026-10-12 for "You've hit your weekly limit"):

- Three agent-sessions of the agent-seat cold-read-improvement stopped at 2026-10-12 03:03Z to 03:04Z with the message "You've hit your weekly limit · resets Oct 13, 9pm (America/Los_Angeles)", about 42 hours before the reset.
- Sessions of merge-lane-2 and fleet-restart-at-login carry the same message, some with "resets Sep 26, 4am (America/Los_Angeles)", so the weekly limit was reached in an earlier week too.

The message is written into the transcript as an assistant message whose model is `<synthetic>`, with the reset's date and time in the text. Other agent-seats on ned-box, prime-intellect among them, kept working after 03:04Z on 2026-10-12 on the same login, so the limit did not stop every agent-seat at the same moment; why was not established.

## The remedy the user described

Switch the agent-seats to another of the user's Claude accounts that is under both its 5-hour and its weekly limit: log out of all devices, log in with the other account, and complete the login by the link or the code that the login sends by email. This works only when the user has such an account; when none has room, the agent-seats wait for the reset, as they do today.

The switcher is a program outside Claude, already running before the limit is reached, such as a timer on ned-box: once the account is over its weekly limit, no Claude agent can act, so no agent can start or carry out the switch (user-ruled 2026-10-18, in prime-intellect's agent-session 1de807c5-e476-42c9-b4f9-6357a594345f: "the account switcher must be running before it's needed or an outside of Claude monitor").

The program outside Claude starts the switch. Where a step of the switch needs an AI agent, such as carrying out the login steps, that agent is Codex, OpenAI's coding agent, and never Claude, because Claude is over its limit. Codex does nothing else: it does not take over the agent-seats' work (user-ruled 2026-10-18, in prime-intellect's agent-session 1de807c5-e476-42c9-b4f9-6357a594345f, transcript `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern-agents-prime-intellect/1de807c5-e476-42c9-b4f9-6357a594345f.jsonl`: "Codex is not a fallback for Claude. But when Claude is unavailable and we need an ai to restart Claude by changing accounts we are going to use codex"). Codex is installed on ned-box today with a login of its own: `/usr/local/bin/codex` reports codex-cli 0.159.3, `codex login status` prints "Logged in using ChatGPT", and its login is stored in `~/.codex/auth.json`, apart from Claude's `~/.claude/.credentials.json` (all checked on ned-box, 2026-10-18). The project's program for giving Codex a task, `scripts/run-codex-task-from-brief.py`, which `docs/nedschorus-wiki/nedschorus-codex-and-gemini-operating-notes.md` tells agent-seats to use, denies Codex every credential file, `~/.claude/.credentials.json` among them, and closes Codex's stdin (its docstring and `nc-systems/cold-read/cold-read-cell-common.py`, on main), so as it stands it cannot let Codex change Claude's login. Whether Codex can carry out Claude's login, which sends a link or a code by email, was not checked.

## What exists today

- `claude auth status` prints the login method, organization and email of the account `claude` is logged in to. `claude auth logout` logs out. `claude auth login` signs in, with `--claudeai` for a Claude subscription, the default, and `--email <email>` to fill in the address on the login page. `claude setup-token` sets up a long-lived token for a Claude subscription; whether such a token lets a switch skip the email step was not checked. All from `claude --help` and `claude auth <command> --help` on ned-box, 2026-10-12.
- On ned-box, the login is stored in `~/.claude/.credentials.json`, one file for the user's account on the machine. Every running agent-seat on ned-box has `HOME=/home/nedlern` and no `CLAUDE_CONFIG_DIR` (read from `/proc/<pid>/environ` of each `claude` process, 2026-10-12), so all of them use that one login. Where the Mac stores its login was not checked.
- Claude Code passes the status line a `rate_limits` object with a `five_hour` and a `seven_day` window, each with `resets_at` and `used_percentage`; `scripts/session-statusline-command.py` shows both. So the weekly limit's reset time, and how much of it is used, are known to a program before the limit is reached.
- GHI [Tell the user when ned-box's claude is logged out or ned-box's subscription has run out](https://github.com/nedschorus/nedschorus/issues/337) covers telling the user when `claude` on ned-box is logged out or its subscription has run out; it stops at telling him.
- GHI [Relaunch stopped agent-seats with open tasks daily](https://github.com/nedschorus/nedschorus/issues/936) relaunches agent-seats that are not running, once a day. After a switch, the agent-seats need to run again on the new login.

## Questions for the user

1. Which accounts take part, and in what order?
2. Does the switcher switch accounts by itself, or does it propose the switch to the user and wait for his yes? And does it act when the limit is reached, or shortly before, from the status line's `seven_day` usage?
3. How does the link or code from the login email reach the login: does the user click it or type it each time, or does Codex or another program read it and fill it in?
4. Both machines, or ned-box only? The Mac's login was not checked. "Log out of all devices" is the user's step; `claude auth logout` logs out one machine, and how all devices are logged out was not checked.
5. What happens to agent-seats that are running when the login changes, since all of them on ned-box share one login file? And does a program switch back to the first account after its weekly reset?
6. Does a long-lived token from `claude setup-token`, made in advance for each account, remove the email step from a switch?
7. Do the terms of the user's Claude subscriptions bear on running the agent-seats across several accounts?

## Next action

Put the questions above to the user. From his answers, write the design of the switch in this GHI-MD, then give it the /cold-read that the ghi-write skill requires before an edit-GHI.
