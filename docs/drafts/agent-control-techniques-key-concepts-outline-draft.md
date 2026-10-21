# Key concepts for the agent-control techniques pages: an outline

A working outline, not for merging. One line per concept; the prose pages are written from it once it is right. *Proposed* marks what is not built; *question* marks what needs the user's ruling; the numbers in square brackets count this project's hooks on that Claude Code hook event today.

## 1. Purpose and stance

- Purpose: instruct and control agents, in what they do, what they say, and how they work with the user and with other agents.
- Scope: fixing a problem in agent behaviour. Out of scope, with one line and a link each: optimising instructions, code-prompt-code's internals, testing in general.
- Good enough, not perfect: a technique should be efficient, reasonably safe, and reasonably quick to build, run and maintain.
- Agents forget: their context fades as it grows, they cannot recall a note, and they may believe they remember what they do not. So whatever must be kept exactly goes in a file, never in an agent's memory.
- Detection comes first: an instruction, a block or a correction does nothing until something detects its moment.
- Every message to an agent teaches: whether the step worked; if not, why; and what to do now.

## 2. The act: what we shape

- A tool call: an edit, a shell command, a file write, a call to a subagent.
- A reply to the user.
- A message to another agent, and the brief a fresh-agent starts from.
- A task created, or marked done.
- A commit, a push, a pull request.

## 3. Moments: when a technique can act

- Before the work:
  - a session starts [SessionStart: 1];
  - a fresh subagent starts [SubagentStart: 0; can add context to the subagent];
  - the brief a program or an agent writes for a fresh-agent;
  - standing text loads: CLAUDE.md, the seat-brief [InstructionsLoaded can only observe].
- The user's prompt arrives [UserPromptSubmit: 3].
- As the act happens: just before a tool runs [PreToolUse: 10].
- After the act, as soon as it is detected (*question*: "ASAP-post-detection" as a glossary term):
  - just after a tool runs [PostToolUse: 9; PostToolUseFailure: 1];
  - the agent stops, or a subagent stops [Stop: 6; SubagentStop: 1];
  - a task is created or completed [TaskCreated, TaskCompleted: 0; can refuse with a message];
  - a watched file changes, by any means [FileChanged: 0; cannot block, and cannot tell the agent].
- On the user's screen only: a reply is displayed [MessageDisplay: 0; changes what the user sees, never what the agent knows].
- Outside the session: the merge gate and the reviewers at a pull request; scheduled jobs and watchers; the output of a program the agent runs.

## 4. Kinds of technique: what it does

- Do it instead: a program does the step; code-prompt-code hands only the judgment to a model.
- Detect: notice the moment, or the wrong act (section 5).
- Block: refuse the act.
  - hard-block: nothing overrides it.
  - soft-block: the agent clears it by writing its reason into the marker; each clear logged for review (*proposed*).
  - user-block: only the user's approval, quoted into the marker, clears it.
- Correct: undo or fix the act.
  - a program rewrites the act before it runs [PreToolUse `updatedInput`; not used here];
  - a program rewrites the result the agent sees [PostToolUse `updatedToolOutput`; not used here];
  - a program reverts the act and tells the agent;
  - the agent is told to correct it, and how;
  - Claude Code's rewind: still to be found out, GHI [Find whether Claude Code's rewind can correct an agent's wrong act, triggered by a program](https://github.com/nedschorus/nedschorus/issues/1758);
  - *question, pending*: which wrong acts a program may undo by itself.
- Instruct: tell the agent.
  - standing: CLAUDE.md, the seat-brief, the glossary; the weakest, fading over a long session;
  - on demand: a skill, triggered by its description;
  - just in time: a hook's added context, a program's output or error, a refusal's text;
  - at correction: the message that follows a detected mistake.
- Judge: what no check can decide.
  - another agent: a pull request reviewer, a cold reader, the advisor;
  - the user: an approval-walk.

## 5. Detection: what can trigger a technique

- A pattern in a command, a file or a reply: a keyword, a regular expression, a parsed shell command, parsed Markdown.
- A file name's prefix or suffix: `-nbd`, `-test.py`, `-prompt.md`, `-instructions.md`, `-design.md`, `-draft`.
- A path: a guarded-file, a memory directory, the log-store.
- A hashtag a program reads: `#next_to_present` in walk minutes; `#root_cause`, `#root_cause_not_fixed`, `#follow_up` in a pull request description; `#pre_approved_change` in a marker.
- A marker file: `.walk-approved`, `.location-write-approved`, `.backup-write-approved`.
- A changed hash: a guarded-file whose git blob hash changed without an approval.
- A skill's description matching the task in hand.
- A count from logs: a fourth cold-read-full-run of one change; repeated failures.
- A time: a daily job, such as the daily full test run.
- A model's judgment, as code-prompt-code: a cold reader, a reviewer.
- Quality: precise is best, and good enough is allowed. False positives are tolerable while they are rare or soft-blocked; the failure is so many that agents learn to ignore the true ones. False negatives are caught by a later detection.

## 6. Durable state: what agents must not be trusted to remember

- Files and markers: approvals, walk minutes, session-handoffs.
- Tags: hashtags in files and pull request descriptions, read by programs.
- Logs: the shared-log; the log-store (cold-read-records, walks, transcripts, session-dialogs).
- The task list; GHIs and their GHI-MDs.
- Why: it is exact, it lasts as long as needed, and a program can read it, so it can drive a detection.

## 7. The act's states

- Agent chooses an act → Pre-tool check.
- Pre-tool check → Tool runs (nothing detected; context added; a marker clears the block) | Hard-blocked | Soft-blocked | User-blocked.
- Each blocked state → Agent chooses an act (another way; with a reason; after the user's approval).
- Tool runs → Post-tool check → Done | Program corrects → Done | Agent corrects → Agent chooses an act.
- A reply → Stop check → shown to the user | sent back to the agent with an instruction.

## 8. The workflow: fixing a problem in agent behaviour

1. Notice: the user, a reviewer, an agent or a watcher sees the problem.
2. Measure: search past transcripts for how often it happens, in what pattern, and at which moment it could be caught. Build only when CLAUDE.md's rule on guards is met.
3. Choose: the flowchart; a program, a block, a detection after the act, a just-in-time instruction, judgment, and standing text last. Pick the moment and the kind together.
4. Write the agent-facing-message.
5. Cold-read it: a fresh-reader's misreadings often expose a flaw in the process itself; fix the process, not only the words.
6. Build and test: cause the failure in a test; run mutation testing on the code that handles it.
7. Review and merge: merge-lane-2.
8. Run: logs record each fire, clear and correction.
9. Re-measure: keep it, correct it or drop it; the page's "Tried, then corrected or dropped" list.

## 9. Pending

- The full technique inventory: Codex and a Claude subagent are reviewing the repository; their tables fill sections 4 and 5 with the files that build each technique.
- Exceptions: what stays off the pages, and why.
- Questions: "ASAP-post-detection" and "just-in-time" as glossary terms; "block-and-inform" (walk item 2); logging soft-block clears; MessageDisplay for fixes meant only for the user; FileChanged for guarded-files changed by shell commands (GHI [Catch a guarded file changed without the user's approval, ask him, and keep every version](https://github.com/nedschorus/nedschorus/issues/1268)); rewriting an act instead of refusing it.
