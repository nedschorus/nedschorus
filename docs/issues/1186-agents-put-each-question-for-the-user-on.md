---
issue: "[Agents put each question for the user on a page that pops up on his Mac, and hold the dialog with him there](https://github.com/nedschorus/nedschorus/issues/1186)"
---

# Agents put each question for the user on a page that pops up on his Mac, and hold the dialog with him there

This is a design. An agent-seat that needs the user's decision puts the question, with its context, on a private Claude artifact page. A monitor on the Mac opens the page in his browser at once. He answers there with Y, N, D or NVM, or writes to the agent-seat, which replies on the same page until the question is decided. A watcher on ned-box tells the asking agent-seat within seconds when he writes. At first only a few questions go to a page: those that keep a pull request from merging, or that hold up work the agent-seat cannot do another way, such as a pull request it cannot open until he chooses between two designs. Every other question stays in the agent-seat's window, unless he asks the agent-seat to put it on a page, which he can do for any question at any time. Nothing is built yet except a trial page; the next action is build-slice 1.

## The problem

An agent-seat that needs the user's answer asks in its own terminal window and waits, and nothing tells him the question is there:

- **Questions asked in one window get missed.** The pull request [The walk and seat shippers judge a shipment by what the store holds](https://github.com/nedschorus/nedschorus/pull/918) waited 20 hours because its author asked him to approve one paragraph in one agent-seat's window alone; GHI [Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152) records the stall.
- **Push notifications do not reach him.** Claude Code's PushNotification tool sends nothing while the agent-session's terminal counts as active; two test notifications on 2026-10-09 were both held back. His phone's notifications are off.
- **He reads the last message first.** A question further up a window is missed, and a question repeated into every window while he is away clutters them.

## The design

### The page

- **One page per context.** Questions that share a context share a page, shown with that context once; a question with a context of its own gets a page of its own. Each page is a private Claude artifact that the asking agent-seat publishes with Claude Code's Artifact tool and that only the user can open.
- **The page carries everything he needs to decide**, because it pops up with nothing else around it: which agent-seat asks, on which machine, and what it is working on; the question; what each answer does; the recommendation and the strongest case against it; and links to whatever he may want to open. When the questions are proposed changes to a Markdown file, the page shows the whole file rendered, with each change marked up where it falls, deleted text struck through and added text highlighted, built with the open-source libraries `marked` and `jsdiff`.
- **The dialog happens on the page.** A message box sends with Enter and starts a new line with Shift+Enter. He can ask, object or add a point, and the agent-seat replies in the same thread.
- **Every question ends in a decision:** Y, which approves; N, which declines; D, not now, after which the agent-seat keeps the question as a task and asks again when it next needs the answer; or NVM, never mind, which drops the question. When the agent-seat asks a deferred question again, it reopens the same page by putting its link back on the list. Words that plainly approve, such as "yes" or "do it", count as Y. Words that ask something, doubt the proposal or answer several questions without saying which answer goes with which do not decide anything; the agent-seat replies on the page.
- **Spun-off work.** When the dialog starts new work, the agent-seat adds it to its task list; when the new work needs his decision, it gets a page of its own.

### Asking a question

- The agent-seat publishes the page, then adds the page's link to the list of pages waiting on him, `/home/nedlern/nedschorus-logs/questions-for-the-user/pages-waiting.txt`, one link per line. Agent-seats add and remove links only through the asking script, which locks the list and replaces it whole, so two agent-seats never overwrite each other and the Mac never reads half a file.
- The agent-seat starts the watcher for that page as a background command, so the agent-seat can work on while the watcher waits; the watcher exits when he writes or decides, and Claude Code tells the agent-session when its background command ends. The agent-seat writes its replies into the page's dialog with Claude Code's ArtifactData tool, and after each reply, and after each decision while other questions on the page are still open, starts the watcher again.
- While the page waits, every message the agent-seat ends a turn with in its own window ends with one line naming the question and its link, so the window agrees with the page.
- When he decides a question, the agent-seat records the decision, his words and the time wherever it records his answers today, such as an approval-walk's minutes or a task, and carries it out. When every question on the page is decided, the agent-seat removes the link from the list, and the Mac monitor then closes the page.
- A page that is withdrawn because the agent-seat no longer needs the answer is removed from the list the same way, with a last message on the page saying why.

### The watcher on ned-box

- A small Python script reads the page's database every 5 to 10 seconds through the HTTP route Claude Code's own artifact tools use, `POST https://api.anthropic.com/api/frame/db/agent`, with the login token Claude Code keeps in `~/.claude/.credentials.json`. It only reads the token, never refreshes it; the agent-sessions running on ned-box keep it fresh.
- When it finds a new message or a decision from him, it prints it and exits. When the route refuses a check for too many requests, it waits longer before the next one.
- **It shows its own health on the page.** After every check it writes the time and the result into the page's database; the page shows a warning when the last good check is more than 30 seconds old or the last check failed, naming what failed, for example an expired login after he switches accounts. The watcher keeps checking, and the warning clears at its next good check.
- **The route is internal and undocumented**, so it may change with any Claude Code release. After a minute of failed checks, the watcher also exits with the error, so the asking agent-seat knows; the agent-seat then checks the page with Claude Code's own artifact tools, and a Haiku subagent is enough for that, until the watcher works again.
- The watcher copies every decision and the whole dialog into files under `/home/nedlern/nedschorus-logs/questions-for-the-user/`, so programs and checks on ned-box read his answers from plain files.

### The monitor on the Mac

- A small program on the Mac, started at login, reads the list of waiting pages through the Mac's mount of ned-box's home every 5 seconds, giving each read at most 2 seconds.
- It opens each new link in his default browser at once. While a page is open, it does nothing more; when he closes a page that is still on the list, it opens it again. When a link leaves the list, it closes that page. It finds the open pages by asking the browser for its tabs, which Safari and Chrome answer to a short AppleScript; build-slice 2 starts by checking that his default browser does.
- It opens only links that start with `https://claude.ai/artifact/`.
- After every successful read it writes the time to a heartbeat file beside the list. An agent-seat that finds the heartbeat more than 30 seconds old asks in its window instead, and says that the Mac monitor looks down.
- The monitor is a Mac file, so the Mac's own agent-seats build and install it.

### Answers and approvals

- Every rule and program that takes his answer today assumes he typed it into an agent-session's terminal; the survey `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/agent-instructions-editor/user-answer-rules-survey-2026-10-10.md` lists 67 of them. A page answer is a record of its own, kept in the page's database and in the watcher's files, and cited as `page <link>, decided <Y, N, D or NVM> with "<his words>" at <time>`; it is never passed off as typed words.
- Until build-slice 4, a question asking him to approve a change to a file the instruction-file guard protects, and every other approval that a program or a verifying agent checks against a transcript, stays in the agent-seat's window. An agent never writes its own summary of a page answer into an approval marker.

## The build-slices

Each build-slice is one pull request that leaves main working.

1. **The watcher, the page template and the asking script, on ned-box,** with tests that run against a test page, never a live one. The test: an agent-seat on ned-box asks the user one real question; he opens the link by hand, writes once and decides; the agent-seat replies on the page and records his decision.
2. **The Mac monitor,** built and installed by the Mac's agent-seats.
3. **The rules for agent-seats.** `CLAUDE.md` says which questions go to a page on the agent-seat's own initiative, that any question goes to a page when he asks for one, and how to ask; the walk-me-through skill says that a decision on a page counts as his reply; and the other rules the survey marks for a decision go to him one by one, among them merge-lane-2's "no external channels" in its seat-brief, `/home/nedlern/agents/merge-lane-2/CLAUDE.local.md`. Each is an instruction change, which goes to him before it is made.
4. **Approvals on the page.** `scripts/search-user-messages-in-transcripts.py` also searches the watcher's files, the instruction-file guard accepts in `.walk-approved` a citation of a page decision only when it finds that decision in those files, and the rules that check a quoted approval accept the citation form. Each change goes to him before it is made.

## Relations

- Trial page: [Question Page Trial](https://claude.ai/artifact/6dLHXaM8yPxEe1Uc2HH3PY), where the page, the dialog, the database copy and the watcher's read were each shown to work on 2026-10-12; the read recipe is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/agent-instructions-editor/artifact-db-read-trial-2026-10-12/artifact_db_read.py`.
- GHI [A small service on ned-box keeps one record of every agent-seat on both machines](https://github.com/nedschorus/nedschorus/issues/972): a web server on ned-box, which this design no longer needs.
- GHI [Wake idle agent-seats that have unfinished work, after a usage limit resets and after a change request goes unanswered](https://github.com/nedschorus/nedschorus/issues/1152): wakes agent-seats; this design reaches the user.
- GHI [Seat mailboxes across machines and runtimes](https://github.com/nedschorus/nedschorus/issues/749): messages between agent-seats.
- Search receipt: ghi-info on 2026-10-10, asked twice, open and closed GHIs: no GHI covers a single place for the user's questions.

## Provisional additions (not yet vetted by the user)

- fleet-restart-at-login, 2026-10-14: Idea: an HTML page for approval-walk items, where a short end-of-turn summary opens the full item (task #187).
