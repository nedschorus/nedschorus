---
issue: "[Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17)"
---

# Code-design questions the user asked about, or decided, more than once in past designs

This file is step 1 of the next action in GHI [Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17), whose GHI-MD is `docs/issues/17-candidate-skill-design-change-read-only-evidence-grounded.md`. That GHI-MD's section headed Next action gives the four steps: this list is step 1; step 2 compares the list with the Anthropic code-architect agent and other published design guidance; step 3 writes the design skill, a skill under `.claude/skills/` that helps an agent design a program, tool or module; step 4 points the design-writing state of GHI [Build the design-to-main state machine: the Python machine, its per-state agent-instructions, and the nine items the design defers to the build](https://github.com/nedschorus/nedschorus/issues/282) at the skill. The list gives step 3 the questions about a design that the user asked, or decided, on more than one occasion, so that the skill can put each question to the agent that writes a design before the user has to ask it. Whether a design must answer every question, and how the counts weigh, is step 3's to decide. Each question below gives how often it came up and three citations, each of which is a line of a walk-minutes file that holds the user's words or records his decision; every line counted under each question is in the data named under How the list was made.

## How the list was made

A program found the sources; the judgments were made by subagents and by the agent that wrote this file, as CLAUDE.md's code-prompt-code rule asks; small programs did the counting. Every input, output and counting program of these steps is kept in the log-store at `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/ghi-17-code-design-questions-the-user-asked-of-past-designs-2026-11-13/`, so each count can be rerun and every counted line read.

1. The program `scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py` ran on 2026-11-13 on a checkout of origin/main as of that day. It reran the GHI-MD's search for designs, `grep -l '^kind: design' docs/issues/*.md`, which found 72 designs. For each design it found the cold-read-records in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/` that reviewed the design, and the walk-minutes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` and `/home/nedlern/agents/*/docs/walk/` on ned-box that were named after one of those cold-read-records, were named with the design's GHI number, or cited the design; its docstring says exactly how each kind of source is matched. It printed every line of those files in which the user speaks or a decision of his is recorded, with the Markdown heading the line sits under: 5,237 distinct lines from 197 walk-minutes files and 134 cold-read-triage files, covering 64 of the 72 designs. The other 8 designs have no such line in any of these sources: `docs/issues/152-genre-suffix-naming-for-non-reviewable-documents-log.md`, `docs/issues/1230-a-fresh-agent-of-the-other-agent-binary.md`, `docs/issues/1660-the-pull-request-head-test-run-takes-its.md`, `docs/issues/1772-shellcheck-checks-every-sh-file-a-pull-request.md`, `docs/issues/1854-programs-tell-a-broken-branch-reference-from-a.md`, `docs/issues/2161-build-the-emergency-stop-skill-which-writes-one.md`, `docs/issues/2210-a-program-that-moves-each-draft-and-candidate.md` and `docs/issues/2532-overview-claim-check-judge-again-only-new-changed.md`.
2. Ten Claude subagents, each given about 500 of those lines and the same prompt, `judge-brief.md` in the log-store directory above, judged which lines are the user's own questions about a design or his decisions on one, and phrased each kept line as a question that could be put to any design. They kept 1,446 lines (`judged/`).
3. The agent that wrote this file read the 870 distinct questions the subagents wrote and wrote 25 questions that cover most of them (`themes.md`). A further subagent sorted each of the 870 under one of the 25, or under none; a program confirmed that every one of the 870 was sorted (`theme-map.json`). Nine that fitted none of the 25 shared a subject of their own, which became the 26th question.
4. A program (`tally.py`) counted the occasions under each question. An occasion is the text under one Markdown heading of one walk-minutes file. Before counting it left out four kinds of line: a line the subagents marked as only repeating a decision recorded in another file (75 lines); a line whose quotation, as the subagent copied it, did not match its source line (41 lines, found by `verify_quotes.py`); a line sorted under no question (79 lines); and a line of a cold-read-triage file (17 lines), because such a line almost always repeats a decision given in an approval-walk. A line can be of more than one of these kinds. Then it counted each set of the user's words once across all 26 questions: a quotation that shares a stretch of 60 characters with one already counted is a copy of it, and was left out (10 lines). The counts rest on the 1,248 lines that remain (`by-theme.json`); a line the extraction program attached to several designs is one line.
5. The three citations under each question were chosen by the agent that wrote this file, all from walk-minutes in the log-store and from different files where it could. A program (`gen.py`) confirmed that each cited line is one of the lines counted under its question, and `verify_quotes.py` that the quotation is copied from that line. A quotation longer than about 230 characters is cut at a word with "..."; the full line is at the cited line number. Each citation says whether the line is a question of the user's or a decision of his, as the subagents judged it.

What this method cannot tell:

- An approval-walk often covers several designs, so the program attaches a whole walk-minutes file to every design it cites; 176 of the 197 walk-minutes files were found only that way. The subagents read every line and kept only those about a design, but which design a line is about rests on their judgment, not on the program.
- A one-letter answer, such as "A" or "y", says nothing on its own line about what was decided, so the subagents dropped those lines. Decisions recorded only that way are missing from the counts.
- The counts are approximate, since each kept line was sorted under exactly one question. They rank the questions; they do not measure them.
- Some walk-minutes report what the user said rather than quote it, so a citation quotes the walk-minutes line as written, which is sometimes the agent's account of his words.

## The questions, most often asked first

### 1. Is there a simpler design, a smaller scope, or a part that can be cut or deferred, that does the same job?

Raised on 58 occasions, in 54 files.

- A decision on agent-seat message queue: "Item 4, disapprove. Claude's already guarded, and this is kind of a weird edge case. The message queue was trying to solve a problem of messages not being delivered, which just like an odd, I would just keep it simple and go on ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-1115-agent-seat-message-queue-design-2026-11-05-minutes.md`, line 35)
- A decision on loose-ends skill: "this sounds too tricky. We only review for loose ends occassionally. Just have our normal codex and claude subagents look for loose ends. However maybe we strengthen that by having a Opus 5.5 at Max, and a Codex Astra and a ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/loose-ends-skill-finds-forgotten-asks-between-the-user-and-agents-design-2026-10-21-minutes.md`, line 53)
- A decision on memory maintenance: "on an earlier project he guarded writes to the memory file, which is probably too much work here. Instead, a maintenance pass on memory files at session reincarnation might work, even for a persistent headless agent like ghi-info." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/five-seat-briefs-cold-read-findings-2026-09-16-minutes.md`, line 80)

### 2. Does this already exist in the project, or in a reputable outside tool, standard or published best practice?

Raised on 56 occasions, in 53 files.

- A decision on new-term list excluding ordinary hyphenated words: "I believe we have a list of hyphenated words which are regular words ... So we have an MD file that contains the known normal words. ... we should exclude the standard words, and as we go, we can and find more standard words. We ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-skill-rebuild-ghi-md-decisions-2026-10-22-minutes.md`, line 75)
- A decision on message queue: "if we're going to design some sort of message queue situation, well, there's plenty of message queue stuff that we can draw from, so we should just do it whatever way they do it. But we do have a database, and if that's useful ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 326)
- A question on agent-facing error messages: "But do we have a good page or section on how to construct high quailty error messages for agents? I'd think you would have needed that before you composed these replacement messages. And where does that page live? And how to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/move-mechanical-agent-chores-ghi-1036-rework-2026-10-09-draft-2026-10-09-3-minutes.md`, line 22)

### 3. Which steps need judgment, and can every other step be code (code-prompt-code)?

Raised on 44 occasions, in 43 files.

- A decision on CLAUDE.md code-prompt-code line: "it's a fundamental philosophy of this whole project that ... code beats prompts. And even from testing, you can test code, it's hard to test prompts. Certainly code is faster and more reliable. ... very little in this project is ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 63)
- A question on record shippers and agent chores automation: "why run by hand when they can just be scheduled? Why give agents extra burden? ... why don't we just copy these immediately into the store - why batch them up at all? ... a script might have to pass back to the agent anything it ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/783-design-revision-five-fixes-and-decisions-2026-10-02-minutes.md`, line 35)
- A question on agent-seat database service local queue: "sounds increasingly like this needs to be code prompt code. ... we can assume that netbox is a necessary component of the architecture. ... right idea, but I'm not sure if your implementation is too prosy and not mechanical ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 331)

### 4. What review does each text or part get before it is approved or merged (cold read, advisor, independent reviewer), and is it enough?

Raised on 43 occasions, in 41 files.

- A decision on handoff leftover branches and git identity: "I would bring an advisor to make sure this makes sense. This is only part of a larger system, so the whole system has to make sense for this to make sense. So I would have the advisor check, because I cannot" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-design-2026-11-01-minutes.md`, line 37)
- A question on cold-read and sanity-check review process: "I'm concerned cold read works because its isolated from code and tests ... Each form of MD, design, test plan, design contracts, needs a specialized prompt to write a good one and a specialized prompt (from anohther agent) to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md`, line 25)
- A question on fast reader context: "I'm wondering if the false positives, which you say were caused by the fast readers not having the right context ... could be easily fixed with by tweaking what context we give the fast readers" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`, line 163)

### 5. What measurement or evidence from real cases shows this is needed, works, or sets its limits and thresholds?

Raised on 42 occasions, in 39 files.

- A decision on absolute-word warning hook: "ever is not going to work. You can assign a codex to scan the sessions dialogs to see maybe 10-20 corrections from one of those words - generally the correction is to simply state the rule, for instance do X, but almost never say ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md`, line 139)
- A decision on explain skill method: "The explain skill should try to prompt the agent with a list of specific problems or concerns to check for ... I suggest you dispatch many subagents to look for 5-15 specific prompts to help explain, based on what has worked best ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/explain-skill-draft-2026-09-28-2-minutes.md`, line 48)
- A decision on finding user-rulings: "an agent can judge what is a ruling and whether a new ruling overlaps an old one; the user settles differences; a new ruling marks which old rulings it supersedes or partly overlaps. He asked for data gathering on the existing ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fleet-restart-at-login-approval-walk-merging-all-open-approval-walks-and-questions-2026-10-15-minutes.md`, line 13)

### 6. Which document, record or copy is the single source of truth (the master), and how is drift between copies, or between design and code, prevented?

Raised on 42 occasions, in 36 files.

- A question on design vs code as master: "my rule was nothing obvious, and sometimes the details are very obscure, and in which case that would make sense to input in a design. ... the design is the master until the code is into production or on main ... there is going ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 555)
- A decision on designs and overviews after code changes: "one of the concepts was that what you can see in the code, don't put in the design, don't put in the overview ... if the code changes, that overview is going to be obsolete, and there should be a maintenance process to deal with ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 13)
- A decision on design material phasing: "the right place for a change to a design is the design ... no clear rule that a piece of material lives in exactly one of three places ... "I think we may need to formalize the phasing first, so we don't get overlapping docs."" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/five-seat-briefs-cold-read-findings-2026-09-16-minutes.md`, line 68)

### 7. What does the user see, and where (device, channel, alert), when this finds a problem or fails, and is he shown only what he must act on?

Raised on 41 occasions, in 40 files.

- A decision on approval-walk item pages and ned-box web server: "I'm not sure if there's any time I want HTML pages to pop open into my browser on my Mac. I find that I want walks to be self-contained in the Claude CLI or the Claude app or the Claude remote control. ... We seem to have gotten ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 186)
- A decision on reporting pre-approved changes: "anything he need not approve he does not want to see at all, "unless, of course, it breaks later"; "if we're telling them they don't have to get my approval, we can also say they don't have to report it to me"" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fleet-restart-at-login-approval-walk-merging-all-open-approval-walks-and-questions-2026-10-15-minutes.md`, line 31)
- A decision on program alerts reaching the user: "he often works from an iPad or phone, not the Mac, and is nearly always in a walk; he asked to look into replacing "open a page in the Mac browser" with inserting the alert into a walk as the next item" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-ten-pending-decisions-approval-walk-2026-10-25-minutes.md`, line 47)

### 8. Who reads each text or message, what can that reader be assumed to know, and does it say plainly what happened and what to do?

Raised on 41 occasions, in 36 files.

- A question on acting on cold-read findings: "the more we use fast cold read, the more important to use it properly that is to give the writing agent not just the criticisms but what to do to address them. ... maybe the address part needs to be specific to where and how cold ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`, line 81)
- A decision on ghi-info-ask replies out-of-scope and escalate: "Not great. Out-of-scope is not helpful response. I think better wording would be "Not a query re GHIs") It should respond with a error like - "GHI-info reports which issues relate to a querry" or something like tha. Also escalate ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/SKILL-ghi-write-2026-09-29-4-minutes.md`, line 15)
- A decision on rebuild exit codes: "that sounds nutty - if 0 is success, then just return additional context if there is some. Success/Fail and context should be separate. do uou agree? If so are there other system that this is not handled correctly?" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/783-design-open-questions-pinning-and-three-gaps-2026-10-04-minutes.md`, line 57)

### 9. Which decisions or changes need the user's approval or reading, and which can agents settle without him?

Raised on 38 occasions, in 38 files.

- A decision on agent-instructions approval: case-against ratings: "I'm really trying hard to find things I don't have to review. ... weak cases maybe can be auto-approved, but I'm not sure what those weak cases are yet ... Additions to rules, guards and agent instructions stay with him "with the ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, line 42)
- A question on shared-log maintenance job approvals: "I'm trying to minimize the number of items I have to review and approve ... So it sounds like you're trying to undo that. ... the cases that we've decided that don't need my vision or approval aren't particularly judgment-based ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 254)
- A decision on agent-instructions-editor requests from other agent-seats: "he does not want to review every request from other agents ("99% of the time I'm behind those requests"; quote him or limit him to his usual important prose review; involve him only to break repeated change/problem/fix cycles" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-seat-brief-2026-10-05-minutes.md`, line 9)

### 10. What does the program do when a step, a dependency, a machine or an input fails, stops partway or is missing, and who is told?

Raised on 38 occasions, in 37 files.

- A question on Mac files copied to ned-box: "we also keep a local copy of those files for those cases where it's down, and then we send those files when the connection restarts. That seems reasonable, though it seems like we should not keep files that have been copied ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 429)
- A decision on unresponsive pull-request authors: "10 - I think we'd need to check if the agent is alive - I think the scripts know how to do that. If not alive reincarnate it - the scripts know how to do that too. If it's alive and messaging is working a reminder makes perfect ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-items-walk-2026-10-05-minutes.md`, line 41)
- A question on root-cause skill and arbitrator: "we'll need a root cause skill for agents to get guidance on how to look further than their tasks, deeper back in the pipeline. and at what point to give up and maybe hand that to a specialized root cause agent" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`, line 51)

### 11. When and how often is the work done, at what cost, and does it stay off the critical path and within the user's hours and usage limits?

Raised on 35 occasions, in 33 files.

- A question on checks across the system: "I'm getting a little nervous that we're going to slow down the system with all these checks, but it seems like the alternative is worse ... at some point, I guess we'll have to do some performance analysis of time and tokens to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 66)
- A decision on ned-box test runs in isolated environments: "I'd think we'd need one test system per agent doing tests. The more code and tests we have the more important this is, to virtualize tests - which is my guess for a solution. It's OK if there are minor exceptions to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-head-test-runs-in-isolated-test-environments-2026-10-14-minutes.md`, line 5)
- A question on repeat cold-read-full-runs: "He asked whether, at some size of change, the result of a cold-read-full-run needs another cold-read-full-run; he hopes not, and suggested ... "if you think this needs another cold-read-full-run, do it". He asked for a Codex and ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-skill-rebuild-so-programs-do-the-mechanical-steps-2026-10-23-minutes.md`, line 17)

### 12. Is the rule enforced by code (a test, lint, hook or check at the moment of action) rather than by written instructions, and is each instruction delivered where and when the agent needs it?

Raised on 35 occasions, in 33 files.

- A decision on CLAUDE.md change vs enforcement ladder: "Claude.md is guarded by the user. Before asking them for a change, look at -file that lists all the ways we can coach and control agents --- and see if your idea can be implemented using one of those techniques. If the only ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-2026-10-09-minutes.md`, line 143)
- A decision on checks and maintenance backups: "My goal is to have many ASAP checks, and then some maint backups, or maybe maint backups for all, just in case something slips by. So we should review all checks to see which might need a main backup, and we should have a ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-open-questions-and-skill-reviews-2026-10-14-minutes.md`, line 31)
- A decision on archiving -draft/-candidate files: "I am concerned about the objection that the agent seat that wrote the file must remember to approve it. It seems like we could code prompt code this or automate this ... when something merges or is dropped, it knows what draft it ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, line 283)

### 13. Has the failure this guard or check handles actually happened, and is the guard worth its cost, false alarms and complexity?

Raised on 33 occasions, in 33 files.

- A question on agent-seat message queue: "So you say that 11 messages were lost. Is that worth fixing? In other words, even if one time in 100 things go off because of a lost message, I don't think I'd complicate this system to increase its reliability unless there's a ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-1115-agent-seat-message-queue-design-2026-11-05-minutes.md`, line 20)
- A decision on guard rule: "agents are "extremely resilient, extremely good at recovering from errors and finding obvious alternates", sometimes "too good at that" and do not report it, so there is "a somewhat higher bar to decide to add in guards and ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-remaining-items-minutes.md`, line 18)
- A decision on maintenance windows: "it seems like this is over-engineering, that we should just let it run 24 hours a day, unless we actually do have capacity problems ... add a GHI to say at some point we can look for windows, maintenance windows beyond sleep time ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 133)

### 14. How is what the design produces kept current and clean over time (staleness, maintenance checks, leftovers, growth)?

Raised on 32 occasions, in 32 files.

- A decision on fixed strings written as hashtags in GHI-MDs: "maybe we need a maintenance check to see about cleaning up the other things that should be #hashtags. We'll need a maintenance check, even if there's a one-time, because it'll slowly get drift. Doesn't sound like there's any ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/issue-design-file-edits-and-alert-term-approval-walk-2026-10-27-minutes.md`, line 17)
- A question on issue-marker duplicates upkeep: "confused. does it work like this - 1 add guids to the ghi-mds. 2 - check for dups. 3-have an agent merge them - cold read - then have me review the final. ... Sounds like another item for daily maintence to check and resolve ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/783-design-open-questions-pinning-and-three-gaps-2026-10-04-minutes.md`, line 51)
- A decision on file naming conventions: "just because we have done something in the past doesn't mean we didn't goof up. Especially if the rule was added after the name or file was created. ... everything else we should follow our own conventions. ... And if we find ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md`, line 99)

### 15. Is each term defined once, as a project-term, system-term or SDLC-term, with distinct concepts under distinct words?

Raised on 32 occasions, in 28 files.

- A decision on project glossary names for ambiguous words: "home, land and draft need something in the project glossary, but I don't want bare words that conflict with english. so maybe agent-home, land-on-main (capture landed would just be standard english), and -draft (our first ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/glossary-names-for-ambiguous-project-words-2026-10-01-minutes.md`, line 7)
- A question on main-gatekeeper specification terms: "are you sure about this - these all seems like easily misunderstood or easily guessed wrong. ... Seems like some might be better written in plain words, and others, particularly ones with this project specific meansing need ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-3-main-gatekeeper-specification-cold-read-findings-2026-10-01-minutes.md`, line 87)
- A decision on approval-waived change categories: "obvious-error fixes and non-functional changes are "quite different"; "If we need a single term for items that user approval requirement is waived maybe that's safe-changes?"; "I think we mixed these two up in previous ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fleet-restart-at-login-approval-walk-merging-all-open-approval-walks-and-questions-2026-10-15-minutes.md`, line 17)

### 16. Do the design's categories, states or cases cover every case, with no gap or overlap, including the default one?

Raised on 31 occasions, in 31 files.

- A decision on log-suffix rule scope: "I think you've pointed out a real flaw in this design, in that code or Python or scripts could legitimately have a log or report or capture a draft or candidate or analysis suffix. ... we're going to have to limit this to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, line 294)
- A question on agent-session names across account changes: "it does seem to work when there's normal reincarnations, but when I have to change accounts, it seems like I have to manually I don't know if it works. I don't think it detects changing of accounts ... maybe we should clean up ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-design-2026-11-01-minutes.md`, line 203)
- A question on question-check Stop hook: "I thought hooks had to run in like a few seconds. And if you bring in another model into check, won't that take too long? ... It doesn't seem to differentiate direct questions to the user, which need to be answered, from ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 230)

### 17. Where is each file, rule or record kept (repository or log-store, which directory, which system owns it), so that the reader who needs it finds it?

Raised on 30 occasions, in 26 files.

- A decision on cold-read records to log-store: "we should separate the system from its logs, or the stuff that needs to work and be worked on, from the incidental byproducts of that work ... main - github is where the system goes, and the logs should just go to a networked ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-records-branch-and-agent-instructions-queue-minutes.md`, line 39)
- A question on approval-walk storage: "What's the right data structure for a walk? And I guess we can have a data structure captured in a MD file or a text file, but we can also have it in a database. ... if it's inserts and deletes and names and things like that ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 302)
- A decision on objective page and notes page split: "None of this will go into claude.md - that is not appropriate. This is the objective.md wiki page ... BOth the objective page and the notes pages, should be well constructed, human readable docs - one high level, one detail." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`, line 53)

### 18. What is the root cause, and does the design fix it there rather than work around one case?

Raised on 28 occasions, in 28 files.

- A question on benchmark GHI-MD sandbox: "is this a general problme, that is not specific to this issue? ask the ghi-info agent if other ghis would be affect by this, particularly anything in the design-to-main pipeline ... why do we need to hide other directories - or ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md`, line 16)
- A question on mistake reporting and correction: "it seems like the Git mistakes reflect some underlying problem, some root cause ... I don't know if we have a mistake reporting structure ... mistakes maintenance is sort of generally designed to be a kind of backup to a primary ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 189)
- A decision on ghi-issue-write.py renaming: "That sounds like a crappy tool. Is that our tool? If it is, just upgrade it and then fix it. ... I should not have to be a typist for you. ... Seems root cause and fix for real." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-items-2026-11-01-minutes.md`, line 29)

### 19. Which outside limits, platforms or machines does the design depend on (quotas, accounts, platform behaviour, both machines), and has their behaviour been confirmed?

Raised on 28 occasions, in 27 files.

- A decision on wake at limit resets / account cycling: "anthropic is removing the 5 hour limit, so that can be simplfied. ... I cycle the accounts as necessary. ... what we'll need to do is an external watcher. And when the weekly limit gets consumed, we will need to log out of both ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/reboot-test-remote-control-never-connected-reconnect-2026-11-01-minutes.md`, line 26)
- A decision on ned-box as server for Mac data: "I do want the NetBox to be the server. I do want the Mac to use the server. Anything the server needs, it seems like it should be put on the server, probably in the same command that stores it on the Mac." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 113)
- A question on cold-read-fast-read Gemini Flash speed: "Gemini 3 Flash is so incredibly slow. It's not so slow when I use it in the web. So I'm wondering if we were using it correctly ... the main one is determining why Flash is so friggin' slow. And I'm just thinking we're doing ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-fast-read-speed-and-design-drift-2026-11-02-minutes.md`, line 25)

### 20. Has the user already decided this, and is every decision, deferred item and follow-up recorded durably so it is carried forward?

Raised on 27 occasions, in 27 files.

- A question on ruling-agent: "I wonder how agents know if I've approved something, because I may approve it in one place and they may execute in a different place. ... we'll call it a ruling agent, a agent that tracks my approvals and can be quickly ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-items-2026-11-01-minutes.md`, line 234)
- A decision on loose-ends and half-finished tasks: "Walking through all the tasks is too much. There could be 100 tasks ... So we want to try to concentrate our energy to actually get things into production. And defer in a memorable way, which is a task list or GHI things" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-decisions-for-the-user-2026-10-22-2-minutes.md`, line 85)
- A question on main-gatekeeper follow-up of requests in review: "when you say close do you mean reject? I'm a bit concerned that we may assign tasks to agents that might not be reincarnated, so I'm thinking the daily maintence cycle could check for problems like this? ... Typically what should ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-3-main-gatekeeper-specification-cold-read-findings-2026-10-01-minutes.md`, line 33)

### 21. Does each name say plainly what it names, follow the naming rules and not collide with another name?

Raised on 26 occasions, in 24 files.

- A decision on log-store transcripts/ folder name: "10, no. We use the word transcripts in other ways. That's just going to confuse the crap out of people to use the same word in different places. I'm surprised that passed the naming rule convention. ... Just keep the name as log ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-open-items-2026-10-22-minutes.md`, line 152)
- A decision on the supports tag and naming: "The supporting tag should name its issues by GHI number, not title, as only the number is invariant. Who is to say that a heading never changes? ... To me it seems like the ghi.md file name and ghi name should match." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/SKILL-ghi-write-2026-09-29-4-minutes.md`, line 31)
- A question on draft-md skill name and pre-writing instructions: "should we call it draft-md or write-md? We are using draft to mean a preliminary version, which this might be. Also MD's manually created like these probably should be cold-read or might want other pre-writing instructions" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-md-reconciliation-disagreements-2026-09-30-minutes.md`, line 53)

### 22. Which agent or component owns each piece of work or state, so that no two do the same job and none is left unowned?

Raised on 24 occasions, in 22 files.

- A question on overview refresh reminder: "My concern is that if only one seat reminds me, what if I close that seat? Does it matter which seat reminds me? If not, then as long as I get reminded at least once a day, that should work." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-fourteen-decisions-2026-09-30-minutes.md`, line 60)
- A question on backlog triage role: "if we ever run out of stuff to keep 3-5 agents busy, I'll ask some agent for recommendations on the next task/GHI or finding from the field to work on. Maybe that should be call the projecct manager?" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`, line 49)
- A decision on cold-read-fast-read of files outside the repository: "Our revisioins to cold read should really help in any case. ... Y but I think other agents are alread doing this. You may have to trawl walks or the transcripts" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`, line 131)

### 23. Does ready work start without waiting on the user, and do agents keep working rather than block or idle?

Raised on 20 occasions, in 20 files.

- A decision on maintenance questions to the user: "I actually like it when agents continue working because I hate to be a blocking item. But if I haven't answered the question, they just have to keep repeating it, which isn't the same as blocking ... blocking is a bad idea ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md`, line 254)
- A decision on the user's place in the state machine: "while I don't want to read code changes, I do want to be asked to read any natural language changes in the design or test design ... I am a gate ... Because I'm a gate I need to minimize when agents are blocked by me with careful ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`, line 59)
- A decision on fix-round limit: "I think we should leave very practical advice on what the agents should do after it stopped, so that you don't have to ask me questions like this one, which is, yes, we should basically ship what we've got when it's good enough ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 247)

### 24. How is each part tested, and does every change carry a test that fails without it?

Raised on 13 occasions, in 13 files.

- A decision on memory review test fixtures: "some of our tests require known inputs to see if they generate known outputs. And the way we do that is through frozen or synthetic data. I can understand that, but it might be nice if we could use frozen data too, and upgrade ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-fourteen-decisions-2026-09-30-minutes.md`, line 72)
- A question on fix-round convergence process: "the lack of coordination between changes and testing those changes seems broken and a process problem that could be fixed, particularly as we ready for (and perhaps tweak the design of0 design-to-main system." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-fix-round-convergence-process-walk-2026-10-10-minutes.md`, line 12)
- A question on coverage-type values: "I'm wondering if we need an explicit known test besides human, or besides human or user or something. Because cannot be tested and can be tested by a human are different. And right now, I think it's confusing, and I don't like ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md`, line 134)

### 25. Which model or service does each judgment step, and how is the quality of its judgments measured and tested on real cases?

Raised on 11 occasions, in 11 files.

- A decision on three-model naming check: "Gemini 3.8 is fast, maybe sol is too slow, if so pick a faster codex agent. I guess Haiku might be OK. ... set up a test/trial/benchmark to see what agents/efforts work well enough. ... find the best (fast and high quality) combo ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-decisions-whose-approval-starts-work-2026-10-17-minutes.md`, line 22)
- A decision on cold-read-fast-read reader bake-off: "if we're going to do a bake-off, we want to see if two or three agents performs better than one ... correct positives and correct negatives and false positives and false negatives ... Opus Max to make sure the masters is good ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-fast-read-speed-and-design-drift-2026-11-02-minutes.md`, line 26)
- A decision on question-check Stop hook model check: "It sounds like we may need a regular maintenance check on the quality or veracity of the Haiku check on whether, on what things are need to be added to the walk versus what things are just information. ... are we sure we're doing ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 252)

### 26. How is each review finding graded and routed (fix now, fix next, maintenance, filed), and which findings block a merge?

Raised on 6 occasions, in 6 files.

- A decision on review findings grades and round limit: "talking to you and other agents about coming up with a gradation system of must fix now, fix next release, or next item in the walk. Nit fix during maintenance or other maintenance-y kind of things." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 290)
- A question on restater scoring: "It seems that some catches are important, and some are not, and anti-catches (stupid) are easy to ignore. What do you think? ... Are you sure a judge can't determine if there are any critical findings? Why not?" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-perfect-test-cases-minutes.md`, line 121)
- A decision on review finding categories: "We've now added another category of block. There's now, instead of just blocking, fix next, or as soon as possible, but not blocking, fix during maintenance. We also have a file and fix later, smaller items as tasks, larger items ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 328)
