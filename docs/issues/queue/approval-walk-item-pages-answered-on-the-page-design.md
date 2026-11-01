---
kind: design
---

# Approval-walk item pages the user answers on, from the Claude app on the iPad or the Mac, with each answer recorded in the walk-minutes by code

This is a design, a GHI-MD pending approval and not yet filed. Open question 1 decides whether it replaces the text of GHI [Agents put each question for the user on a page that pops up on his Mac, and hold the dialog with him there](https://github.com/nedschorus/nedschorus/issues/1186), whose earlier design, a question page that a monitor on the Mac popped open, the user deferred on 2026-10-19, or is filed as a new GHI. Nothing is built yet. The next action: the user rules on the open questions at the end, as an approval-walk of fleet-restart-at-login; then build-slice 0, a short trial, checks the facts the design rests on before any code is written.

## Why

An approval-walk shows the user one item at a time in the agent-session's chat, and the item's last line links to the item page, a private claude.ai page holding the same item. Today he reads the page and then types his answer, such as A or D, into the chat. He wants to answer on the page itself.

- On 2026-10-19 he deferred GHI 1186's earlier design, "we can defer the pop-up thing, perhaps indefinitely", because "I've started using remote control a lot, and so I'm not using my Mac because I'm on an iPad" (item 1 of reboot-test's approval-walk reboot-test-questions-owed-to-the-user-2026-10-19).
- On 2026-10-28, in agent-instructions-editor's agent-session: "I love the item pages. The problem was that when I changed accounts they all became inaccessible, and that we ran into a limit of 100 new artifacts".
- On 2026-10-29, in prime-intellect's agent-session: "I thought we have a task or GHI to build our own md to html thing and server, so we have complete control." That became GHI [A read-only web server on ned-box renders Markdown files as web pages on the LAN, for approval-walk item pages and other pages agents publish to claude.ai that only show text](https://github.com/nedschorus/nedschorus/issues/2175), which he approved for his home network only on 2026-10-30 (item 11.1 of fleet-restart-at-login's approval-walk `ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29`).
- On 2026-11-01, in the same approval-walk, he wrote: "I do not want stuff to be self contained. I want them visible in walks." and "And ideally actionable". He then approved its item 16.3.5: pause GHI 2175's build, and write one design for answerable item pages that open on the iPad away from home, starting from GHI 1186's claude.ai page without its Mac pop-up, and choosing between claude.ai and a ned-box server. This file is that design.

## Constraints

- **The pages open where he works:** the Claude app on the iPad through Claude Code's Remote Control, away from home included, and the Claude app or a browser on the Mac.
- **Account changes and deleted pages break pages.** A claude.ai page belongs to the account Claude Code on ned-box is logged in to. When he viewed under another account on 2026-10-29, the item pages stopped opening, and on 2026-11-01 the page this approval-walk used was deleted, so its link broke. Whatever is built, the chat stays complete: each item is shown in full in the agent's message, and an answer typed in the chat always works.
- **Code records the answer.** A press of a button on the page reaches the walk-minutes through the program that records typed answers today, `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, called by code, never by an agent restating the answer.

## Hosting: claude.ai, not a ned-box server

| | claude.ai item page | ned-box web server |
|---|---|---|
| Opens on the iPad away from home | yes | only through a tunnel, such as Tailscale, which nothing has set up |
| Tells the agent-session at once that he answered | yes, through "Send to Claude", below | no supported way: a program would have to start a turn in a running agent-session |
| Knows who pressed | yes: the platform stamps the comment's author | needs a login of its own |
| Survives an account change | no; the chat still works | yes |

The design uses claude.ai. A ned-box server would keep working through an account change, but it cannot wake the agent-session, so an answer on it would wait for the agent-session's next turn, and it needs a tunnel and a login of its own. GHI 2175 stays paused.

## How an answer travels

The Artifact tool's runtime capabilities, contract 0.2.96, read on 2026-11-01 in the type definitions `comments.d.ts` that Claude Code's built-in `artifact-capabilities` skill ships, outside this repository, offer one channel that wakes an agent-session: the `comments` capability's `sendToClaude`. A page that declares `capabilities: {comments: {}}` may call `sendToClaude({anchor, text})` from the viewer's own button press. It posts a comment thread as the viewer, and the platform sends it to the agent-sessions that watch the artifact; an agent-session watches an artifact it has published, or one it names to the ArtifactComments tool's `watch` action, and only a main agent-session, not a subagent, can watch. It works only for an editor of the artifact, which the user is as its owner, and the first such write on an artifact asks his consent once; if he declines, the call rejects `forbidden` for the rest of that page load, and the page says to answer in the chat. `canSendToClaude()` tells the page beforehand whether it can go through: `available`, `writers_only`, `no_session` or `off`. The other capabilities do not fit: `db` keeps answers that the agent-session must poll with the ArtifactData tool, which wakes nothing, as GHI 1186's earlier watcher did by reading an undocumented route with Claude Code's login token; `room` reaches only the views open at that moment, and keeps nothing.

1. **The page.** A new item page builder, written in build-slice 1, makes the page the agent publishes: the item's text, and below it buttons A, AO, Aa, D, Z and E and a text field for a short typed reply. An item with parts gets the buttons once per part, an item with options also gets O2 and O3, and an item that asks no decision gets one button, Next. On load the page calls `canSendToClaude()`. When it answers `available`, the buttons are enabled; otherwise they are disabled, and the page says to answer in the chat.
2. **A press.** Pressing D on item 16.3.5 of 25 calls `sendToClaude` with the text `walk-answer item 16.3.5 of 25: D`, anchored at the item's heading; a typed reply sends `walk-answer item 16.3.5 of 25: <his words>`. The item number lets code refuse an answer, from a page left open, for an item that is no longer waiting.
3. **The wake.** The ned-box agent-session that published the page watches it: a publish arms the watch and its comment replies when comment auto-replies, a Claude Code option, are on for that agent-session; build-slice 0 finds where the option is set, and the agent-seat's settings turn it on, with a test that fails when it is off. The comment starts a turn in that agent-session, which Remote Control shows on the iPad.
4. **The record.** This step holds only if build-slice 0 shows that a comment turn runs UserPromptSubmit hooks. The walk-me-through UserPromptSubmit hook, `nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, learns one more form: a turn that is an artifact comment sent to Claude, on the page the walk-minutes' last `#item_page` line names, whose text starts `walk-answer item <N> of <M>:`. When N is an item the walk-minutes' last `#next_to_present` line names, and the words after the colon read as one answer to the hook's existing parser, such as `D`, `1 a 2 d` or `next`, the hook runs `check` itself, with the answer's flag and a new flag, `--answer-from-item-page-comment <page link> <thread id>`, which writes the answer into the walk-minutes as `page <link>, thread <id>, answered <answer> with "<his words>" at <time>`, never as typed words. When `check` leaves nothing for the agent to judge, the hook runs `close` too; otherwise it hands the agent `close` and what `check` printed, as for a typed answer. When `check` refuses, the hook records nothing and hands the agent the refusal, to reply in the thread. Words that do not read as an answer, such as E or a question, reach the agent as an ordinary prompt from the page. When N is not a waiting item, the hook records nothing and tells the agent which item is waiting.
5. **The reply on the page.** The agent replies into the thread with the ArtifactComments tool in one line, such as "Recorded: item 16.3.5 disapproved; item 16.3.5.1 is next", resolves the thread, and republishes the page with the next item. The answer is already recorded, so an agent-session that ends before this step loses only the reply; its successor republishes the page when it resumes.

## Failures

- **Answered twice.** Whichever answer arrives first is recorded, and moves the `#next_to_present` line on. A page answer arriving second names an item no longer waiting, so step 4 refuses it and the agent says so in the thread. A typed answer arriving second answers the next item, as a typed answer does today; the agent's message after the page answer shows that next item, so he answers it having seen it, unless he typed before that message arrived. That last case is a risk this design accepts, as the chat already does when he types ahead.
- **No agent-session is listening.** After a session-handoff or a crash, no agent-session watches the page until the successor republishes it, which the walk-me-through skill already has it do when it resumes. Until then `canSendToClaude()` answers `no_session`, and the page tells him to answer in the chat.
- **The page breaks.** When a publish to the approval-walk's page is refused because the page is gone, the agent publishes a new page and records its link with a new subcommand of the check program, which writes and checks the `#item_page` line that step 4 reads from then on. When he views under another account, the page does not open, and he answers in the chat.
- **The comment does not reach the hook.** Build-slice 0 checks this. If a comment turn starts no UserPromptSubmit hook, step 4 moves to a hook that does see it; if none does, the page shows the item only, and he answers in the chat as today.

## Approvals of guarded-files

An item that approves a new version of a guarded-file, such as the guarded-file backup hook, puts the user's words into `.walk-approved`, and checks compare them with his typed words in the transcript. Until the user rules otherwise (open question 3), such an item's page disables its buttons and asks for the answer in the chat. The page builder decides which items these are, by testing the paths the item's change touches with the instruction-file guard's own test for a guarded-file.

## The build-slices

Each build-slice is one pull request that leaves main working, except build-slice 0, which merges no code.

0. **The trial.** On one test page published from a ned-box agent-session: a button calling `sendToClaude` from the Claude app on the iPad starts a turn in that agent-session; the turn's text is captured; and a UserPromptSubmit hook is shown to run on that turn. The trial also records whether comment auto-replies are on for agent-seat agent-sessions. Its results are written into this GHI-MD.
1. **The page and the record.** An item page builder in the repository, `nc-systems/skills/walk-me-through/walk-me-through-answerable-item-page-html-builder.py`, which GHI [Approval-walk item page publisher copying linked files into the page as timestamped copies, so short repository and log-store paths open on the iPad](https://github.com/nedschorus/nedschorus/issues/2168)'s publisher would use too; the hook's new form; and `check`'s new flag; with tests that feed the hook the comment turn build-slice 0 captured.
2. **The skill.** The walk-me-through skill's paragraph on publishing item pages says to publish them with `capabilities: {comments: {}}`, and to reply in and resolve the thread after a page answer. This is an instruction change, which goes to the user before it is made.

## Open questions

1. **Replace GHI 1186's text, or file a new GHI?** ghi-guide-agent, asked on 2026-11-01, found no other GHI that covers this and left the choice to the user, because he deferred GHI 1186. Recommendation: replace GHI 1186's text with this design, because every question to the user now goes through an approval-walk item, so answerable item pages do what GHI 1186 was for. The alternative: file this as a new GHI, and leave GHI 1186 deferred.
2. **Hosting.** Recommendation: claude.ai, as the section "Hosting" says; GHI 2175 stays paused, and closes unbuilt once build-slice 1 works. The alternative: resume GHI 2175, adding a tunnel, a login and a way to wake the agent-session.
3. **Guarded-file approvals on the page.** Recommendation: keep them in the chat, as the section "Approvals of guarded-files" says. The alternative: accept a page answer in `.walk-approved`, which needs the transcript checks to read comment turns.
4. **A typed reply on the page.** Recommendation: include the text field, so that E and short answers in his own words work from the page. The alternative: buttons only.

## Relations

- GHI [A read-only web server on ned-box renders Markdown files as web pages on the LAN, for approval-walk item pages and other pages agents publish to claude.ai that only show text](https://github.com/nedschorus/nedschorus/issues/2175): paused by item 16.3.5 on 2026-11-01; its open questions wait for this design.
- GHI [Approval-walk item page publisher copying linked files into the page as timestamped copies, so short repository and log-store paths open on the iPad](https://github.com/nedschorus/nedschorus/issues/2168): the page publisher whose pages this design's builder would make.
- GHI [Approve obvious approval-walk items automatically, by criteria drawn from the user's tracked obvious approvals, after the advisor checks each one](https://github.com/nedschorus/nedschorus/issues/1809): decides a walk item by criteria, not by a page answer.
- GHI 1186's earlier trial page, [Question Page Trial](https://claude.ai/artifact/6dLHXaM8yPxEe1Uc2HH3PY), and its database read recipe, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/agent-instructions-editor/artifact-db-read-trial-2026-10-12/artifact_db_read.py`.
- Search receipt: ghi-guide-agent on 2026-11-01, open and closed GHIs, asked about answerable approval-walk item pages: GHIs 1186, 2175, 2168 and 1809 are related, and no closed GHI matches.
