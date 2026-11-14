---
issue: "[Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17)"
---

# Code-design questions the user asked about, or decided, more than once in past designs

This file is step 1 of the next action in GHI [Candidate skill: design-change — read-only evidence-grounded design with one recommendation and honest exits](https://github.com/nedschorus/nedschorus/issues/17), whose GHI-MD is `docs/issues/17-candidate-skill-design-change-read-only-evidence-grounded.md`. It lists the questions about a design that the user asked, or decided, on more than one occasion, so that the design skill that step 3 of that next action writes can put each question to the agent that writes a design before the user has to ask it. Step 2 compares the list with published design guidance. Each question below gives how often it came up and three citations, each of which is a line of a walk-minutes file that holds the user's words or records his decision.

## How the list was made

A program found the sources and an agent judged them, as CLAUDE.md's code-prompt-code rule asks.

1. The program `scripts/design-ghi-md-approval-walk-minutes-and-cold-read-records-user-turns-with-file-and-line-extract.py` ran on 2026-11-13 against origin/main as of that day. It reran the GHI-MD's search for designs, `grep -l '^kind: design' docs/issues/*.md`, which found 72 designs. For each design it found the cold-read-records in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/` that reviewed the design, and the walk-minutes in `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` and `/home/nedlern/agents/*/docs/walk/` on ned-box that were named after one of those cold-read-records, were named with the design's GHI number, or cited the design. Its docstring says exactly how each kind of source is matched. It printed every line of those files in which the user speaks or a decision of his is recorded: 5,237 distinct lines from 197 walk-minutes files and 134 cold-read-triage files, about 64 of the 72 designs. The other 8 designs have no such line in any of these sources.
2. Ten subagents, each given about 500 of those lines, judged which lines are the user's own questions about a design or his decisions on one, and phrased each kept line as a question that could be put to any design. They kept 1,446 lines. A further subagent sorted those questions under 25 questions written after reading them; it found nine that fitted none of the 25 but shared a subject of their own, which became the 26th.
3. The count beside each question is the number of occasions on which the user raised it. An occasion is one section of one walk-minutes file, or one cold-read-triage file. A line that only repeats a decision recorded in another file was not counted, and when the same words of his appear in several files they were counted once. Lines whose quotation, as the subagent copied it, did not match its source line were left out of the counts: 41 of the 1,446.

What this method cannot tell:

- An approval-walk often covers several designs, so the program attaches a whole walk-minutes file to every design it cites. The subagents read every line and kept only those about a design, but which design a line is about rests on their judgment, not on the program.
- A one-letter answer, such as "A" or "y", says nothing on its own line about what was decided, so the subagents dropped those lines. Decisions recorded only that way are missing from the counts.
- The counts are approximate, since each kept line was sorted under exactly one question. They rank the questions; they do not measure them.
- Some walk-minutes report what the user said rather than quote it, so a citation quotes the walk-minutes line as written, which is sometimes the agent's account of his words.

## The questions, most often asked first

### 1. Is there a simpler design, a smaller scope, or a part that can be cut or deferred, that does the same job?

Raised on 58 occasions, in 54 files.

- On temp-file cleanup, he decided: "I'm wondering if this is too complicated. That is, I don't see why we can't give all agents all sorts of temp files, and then essentially every week just delete anything in a temp file that's more than a week old. And if there's ..." (`nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`, line 271)
- On agent-seat message queue, he decided: "Item 4, disapprove. Claude's already guarded, and this is kind of a weird edge case. The message queue was trying to solve a problem of messages not being delivered, which just like an odd, I would just keep it simple and go on ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-1115-agent-seat-message-queue-design-2026-11-05-minutes.md`, line 35)
- On conflict arbitrator, he asked: "I read item 19. It seems reasonable, but before we do this, I'm wondering if there's a better or simpler way to handle this stuff. It may be the arbitrator's overkill. It seems like one agent can just make something work ..." (`nedlern@ned-box:/home/nedlern/agents/reboot-test/docs/walk/agent-seat-git-worktrees-branches-checkout-refresh-and-cleanup-redesign-approval-walk-2026-11-03-minutes.md`, line 66)

### 2. Does this already exist in the project, or in a reputable outside tool, standard or published best practice?

Raised on 56 occasions, in 53 files.

- On freezing a pull request at ready, he asked: "This sounds reasonable. I'm not an expert on using Git. Is this a best practice? In which case, I'll approve it. If not, what should we be doing? You might need to pull an advisor in to check this stuff, since I can't advise." (`nedlern@ned-box:/home/nedlern/agents/reboot-test/docs/walk/agent-seat-git-worktrees-branches-checkout-refresh-and-cleanup-redesign-approval-walk-2026-11-03-minutes.md`, line 15)
- On new-term list excluding ordinary hyphenated words, he decided: "I believe we have a list of hyphenated words which are regular words ... So we have an MD file that contains the known normal words. ... we should exclude the standard words, and as we go, we can and find more standard words. We ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-skill-rebuild-ghi-md-decisions-2026-10-22-minutes.md`, line 75)
- On temp-file cleanup and daily cleanup job, he asked: "I'm assuming we actually do have a daily cleanup that'll clean up the right stuff. Otherwise we'll need to make sure that, and somebody should check to make sure it works with the system. And if it doesn't work, we'll have to ..." (`nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`, line 281)

### 3. Which steps need judgment, and can every other step be code (code-prompt-code)?

Raised on 44 occasions, in 43 files.

- On project goals and philosophies (code versus prose), he decided: "agents are extremely good at debugging and testing state machines and schemas and databases and code, and really have almost no clue of what to do with prose. So the more we can put into a machine, and the fewer, and then ..." (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 43)
- On CLAUDE.md code-prompt-code line, he decided: "it's a fundamental philosophy of this whole project that ... code beats prompts. And even from testing, you can test code, it's hard to test prompts. Certainly code is faster and more reliable. ... very little in this project is ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 63)
- On agent-seat database service local queue, he asked: "sounds increasingly like this needs to be code prompt code. ... we can assume that netbox is a necessary component of the architecture. ... right idea, but I'm not sure if your implementation is too prosy and not mechanical ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 331)

### 4. What review does each text or part get before it is approved or merged (cold read, advisor, independent reviewer), and is it enough?

Raised on 44 occasions, in 42 files.

- On handoff leftover branches and git identity, he decided: "I would bring an advisor to make sure this makes sense. This is only part of a larger system, so the whole system has to make sense for this to make sense. So I would have the advisor check, because I cannot" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-design-2026-11-01-minutes.md`, line 37)
- On cold-read and sanity-check review process, he asked: "I'm concerned cold read works because its isolated from code and tests ... Each form of MD, design, test plan, design contracts, needs a specialized prompt to write a good one and a specialized prompt (from anohther agent) to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md`, line 25)
- On fast reader context, he asked: "I'm wondering if the false positives, which you say were caused by the fast readers not having the right context ... could be easily fixed with by tweaking what context we give the fast readers" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`, line 163)

### 5. What measurement or evidence from real cases shows this is needed, works, or sets its limits and thresholds?

Raised on 42 occasions, in 39 files.

- On absolute-word warning hook, he decided: "ever is not going to work. You can assign a codex to scan the sessions dialogs to see maybe 10-20 corrections from one of those words - generally the correction is to simply state the rule, for instance do X, but almost never say ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md`, line 139)
- On explain skill method, he decided: "The explain skill should try to prompt the agent with a list of specific problems or concerns to check for ... I suggest you dispatch many subagents to look for 5-15 specific prompts to help explain, based on what has worked best ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/explain-skill-draft-2026-09-28-2-minutes.md`, line 48)
- On finding user-rulings, he decided: "an agent can judge what is a ruling and whether a new ruling overlaps an old one; the user settles differences; a new ruling marks which old rulings it supersedes or partly overlaps. He asked for data gathering on the existing ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fleet-restart-at-login-approval-walk-merging-all-open-approval-walks-and-questions-2026-10-15-minutes.md`, line 13)

### 6. Which document, record or copy is the single source of truth (the master), and how is drift between copies, or between design and code, prevented?

Raised on 42 occasions, in 36 files.

- On design vs code as master, he asked: "my rule was nothing obvious, and sometimes the details are very obscure, and in which case that would make sense to input in a design. ... the design is the master until the code is into production or on main ... there is going ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 555)
- On designs and overviews after code changes, he decided: "one of the concepts was that what you can see in the code, don't put in the design, don't put in the overview ... if the code changes, that overview is going to be obsolete, and there should be a maintenance process to deal with ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 13)
- On design material phasing, he decided: "the right place for a change to a design is the design ... no clear rule that a piece of material lives in exactly one of three places ... "I think we may need to formalize the phasing first, so we don't get overlapping docs."" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/five-seat-briefs-cold-read-findings-2026-09-16-minutes.md`, line 68)

### 7. What does the user see, and where (device, channel, alert), when this finds a problem or fails, and is he shown only what he must act on?

Raised on 41 occasions, in 40 files.

- On temp-folder cleanup programs and user-alerts, he asked: "writing a lot of user alerts sounds bad to me because I rarely even read user alerts ... basically anything that should be thrown away should be thrown away. It's very rare that something gets thrown away that can't be recreated ..." (`nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08-minutes.md`, line 56)
- On approval-walk item pages and ned-box web server, he decided: "I'm not sure if there's any time I want HTML pages to pop open into my browser on my Mac. I find that I want walks to be self-contained in the Claude CLI or the Claude app or the Claude remote control. ... We seem to have gotten ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 186)
- On meta-walk skill, he decided: "not sure I agree. I forget to ask for stuff, and there always seems to be partially completed walks, or tasks in the agents task list that maybe aren't put in front of me. and agents routinely say stuff like, when you get around ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/reboot-test-open-items-2026-09-29-minutes.md`, line 32)

### 8. Who reads each text or message, what can that reader be assumed to know, and does it say plainly what happened and what to do?

Raised on 41 occasions, in 36 files.

- On reader categories for cold reads, he asked: "confused - so we have a user-reader who won't read code and won't remember almost anything outside the glossaries and claude.md, then we have a fresh-reader, who has the ability to read code, but probably hasn't, then we have ..." (`nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/fast-cold-read-build-ruling-check-questions-2026-10-13-minutes.md`, line 7)
- On acting on cold-read findings, he asked: "the more we use fast cold read, the more important to use it properly that is to give the writing agent not just the criticisms but what to do to address them. ... maybe the address part needs to be specific to where and how cold ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fast-cold-read-of-agent-facing-prose-design-questions-2026-10-10-minutes.md`, line 81)
- On ghi-info-ask replies out-of-scope and escalate, he decided: "Not great. Out-of-scope is not helpful response. I think better wording would be "Not a query re GHIs") It should respond with a error like - "GHI-info reports which issues relate to a querry" or something like tha. Also escalate ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/SKILL-ghi-write-2026-09-29-4-minutes.md`, line 15)

### 9. Which decisions or changes need the user's approval or reading, and which can agents settle without him?

Raised on 39 occasions, in 39 files.

- On guarded-file deletions, he decided: "I don't need to approve file deletions. I approve changes to some files because I'm concerned about wording. But when a file's deleted, I don't care. So maybe the rules needs to be clarified to not bug me about them. But I ..." (`nedlern@ned-box:/home/nedlern/agents/ned-box-helper/docs/walk/ned-box-helper-push-program-design-points-2026-11-03-minutes.md`, line 81)
- On agent-instructions approval: case-against ratings, he decided: "I'm really trying hard to find things I don't have to review. ... weak cases maybe can be auto-approved, but I'm not sure what those weak cases are yet ... Additions to rules, guards and agent instructions stay with him "with the ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, line 42)
- On items whose only case against is an earlier approved sentence, he decided: "Need to add another category to the list of items I don't need to review and should be auto-approved, which is items that the only case against is that it altered a sentence I or altered a sentence I approve word for word on a ..." (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 470)

### 10. What does the program do when a step, a dependency, a machine or an input fails, stops partway or is missing, and who is told?

Raised on 39 occasions, in 38 files.

- On root-cause research: kinds of problem, he decided: "I would differenciate account problems from network problems from access problems (need a password) from permission problems -though perhaps those are all infrastructure problems. A more fine grained understanding of problems (a ..." (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/codex-simplification-trawl-survivors-2026-10-10-minutes.md`, line 27)
- On Mac files copied to ned-box, he asked: "we also keep a local copy of those files for those cases where it's down, and then we send those files when the connection restarts. That seems reasonable, though it seems like we should not keep files that have been copied ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 429)
- On mac-claude test-strength findings and fix-round limit, he decided: "User asked for strict ... User raised a give-up escape valve: 8.1a = mac-claude says "design concern" on recurring same-kind findings ... merge-lane-2 stops after a third fix-round with blocking findings and tells the user" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/mac-claude-reviewer-brief-rebuild-2026-10-02-minutes.md`, line 83)

### 11. Is the rule enforced by code (a test, lint, hook or check at the moment of action) rather than by written instructions, and is each instruction delivered where and when the agent needs it?

Raised on 35 occasions, in 33 files.

- On where the now-over-later rule is given to the agent, he decided: "I don't want to make Claude.md more complicated. It's a limited resource and it's not particularly effective. However, this particular thing comes up in the process of a walk, and it seems like the walk could have a note in the ..." (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 383)
- On CLAUDE.md change vs enforcement ladder, he decided: "Claude.md is guarded by the user. Before asking them for a change, look at -file that lists all the ways we can coach and control agents --- and see if your idea can be implemented using one of those techniques. If the only ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-2026-10-09-minutes.md`, line 143)
- On the daily maintenance task-overlap check, he decided: "you should also add to the maintence GHI something like that - to check all tasks for what can be added to GHIs. ... I realized that as tasks are filed we should check them for overlap with GHIs, then daily maint can cover the ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-open-questions-and-skill-reviews-2026-10-14-minutes.md`, line 26)

### 12. When and how often is the work done, at what cost, and does it stay off the critical path and within the user's hours and usage limits?

Raised on 35 occasions, in 33 files.

- On mutation testing per merge, he decided: "we should scale the mutant testing to not be the critical path. Um, and I would have some background process try to go through mutants at whatever pace we can handle. And if it takes a week, it takes a week. And obviously, if we ..." (`nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08-minutes.md`, line 279)
- On judging which tasks are worth doing, he decided: "Given that we'll probably use this project for hundreds or thousands of days, the one-shot cost of doing things is almost irrelevant. So I think your criteria to decide what is efficient and not is wrong, because I would not ..." (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 448)
- On repeat cold-read-full-runs, he asked: "He asked whether, at some size of change, the result of a cold-read-full-run needs another cold-read-full-run; he hopes not, and suggested ... "if you think this needs another cold-read-full-run, do it". He asked for a Codex and ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-skill-rebuild-so-programs-do-the-mechanical-steps-2026-10-23-minutes.md`, line 17)

### 13. Has the failure this guard or check handles actually happened, and is the guard worth its cost, false alarms and complexity?

Raised on 33 occasions, in 33 files.

- On agent-seat message queue, he asked: "So you say that 11 messages were lost. Is that worth fixing? In other words, even if one time in 100 things go off because of a lost message, I don't think I'd complicate this system to increase its reliability unless there's a ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-1115-agent-seat-message-queue-design-2026-11-05-minutes.md`, line 20)
- On guard rule, he decided: "agents are "extremely resilient, extremely good at recovering from errors and finding obvious alternates", sometimes "too good at that" and do not report it, so there is "a somewhat higher bar to decide to add in guards and ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-remaining-items-minutes.md`, line 18)
- On maintenance windows, he decided: "it seems like this is over-engineering, that we should just let it run 24 hours a day, unless we actually do have capacity problems ... add a GHI to say at some point we can look for windows, maintenance windows beyond sleep time ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md`, line 133)

### 14. Is each term defined once, as a project-term, system-term or SDLC-term, with distinct concepts under distinct words?

Raised on 32 occasions, in 28 files.

- On project glossary names for ambiguous words, he decided: "home, land and draft need something in the project glossary, but I don't want bare words that conflict with english. so maybe agent-home, land-on-main (capture landed would just be standard english), and -draft (our first ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/glossary-names-for-ambiguous-project-words-2026-10-01-minutes.md`, line 7)
- On main-gatekeeper specification terms, he asked: "are you sure about this - these all seems like easily misunderstood or easily guessed wrong. ... Seems like some might be better written in plain words, and others, particularly ones with this project specific meansing need ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-3-main-gatekeeper-specification-cold-read-findings-2026-10-01-minutes.md`, line 87)
- On approval-waived change categories, he decided: "obvious-error fixes and non-functional changes are "quite different"; "If we need a single term for items that user approval requirement is waived maybe that's safe-changes?"; "I think we mixed these two up in previous ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/fleet-restart-at-login-approval-walk-merging-all-open-approval-walks-and-questions-2026-10-15-minutes.md`, line 17)

### 15. How is what the design produces kept current and clean over time (staleness, maintenance checks, leftovers, growth)?

Raised on 32 occasions, in 32 files.

- On fixed strings written as hashtags in GHI-MDs, he decided: "maybe we need a maintenance check to see about cleaning up the other things that should be #hashtags. We'll need a maintenance check, even if there's a one-time, because it'll slowly get drift. Doesn't sound like there's any ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/issue-design-file-edits-and-alert-term-approval-walk-2026-10-27-minutes.md`, line 17)
- On issue-marker duplicates upkeep, he asked: "confused. does it work like this - 1 add guids to the ghi-mds. 2 - check for dups. 3-have an agent merge them - cold read - then have me review the final. ... Sounds like another item for daily maintence to check and resolve ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/783-design-open-questions-pinning-and-three-gaps-2026-10-04-minutes.md`, line 51)
- On file naming conventions, he decided: "just because we have done something in the past doesn't mean we didn't goof up. Especially if the rule was added after the name or file was created. ... everything else we should follow our own conventions. ... And if we find ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-combined-open-items-2026-10-22-minutes.md`, line 99)

### 16. Do the design's categories, states or cases cover every case, with no gap or overlap, including the default one?

Raised on 31 occasions, in 31 files.

- On log-suffix rule scope, he decided: "I think you've pointed out a real flaw in this design, in that code or Python or scripts could legitimately have a log or report or capture a draft or candidate or analysis suffix. ... we're going to have to limit this to ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-editor-open-decisions-2026-10-26-minutes.md`, line 294)
- On agent-session names across account changes, he asked: "it does seem to work when there's normal reincarnations, but when I have to change accounts, it seems like I have to manually I don't know if it works. I don't think it detects changing of accounts ... maybe we should clean up ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-design-2026-11-01-minutes.md`, line 203)
- On question-check Stop hook, he asked: "I thought hooks had to run in like a few seconds. And if you bring in another model into check, won't that take too long? ... It doesn't seem to differentiate direct questions to the user, which need to be answered, from ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 230)

### 17. Where is each file, rule or record kept (repository or log-store, which directory, which system owns it), so that the reader who needs it finds it?

Raised on 30 occasions, in 26 files.

- On cold-read records to log-store, he decided: "we should separate the system from its logs, or the stuff that needs to work and be worked on, from the incidental byproducts of that work ... main - github is where the system goes, and the logs should just go to a networked ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-records-branch-and-agent-instructions-queue-minutes.md`, line 39)
- On CLAUDE.md versus reviewer instructions, he asked: "I think you're suggesting we update Claude MD. I don't know if this is appropriate for Claude. I think this is more of a reviewer thing. Um, Claude is written by every agent, large and small, pretty much. And every codex, large ..." (`nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08-minutes.md`, line 341)
- On approval-walk storage, he asked: "What's the right data structure for a walk? And I guess we can have a data structure captured in a MD file or a text file, but we can also have it in a database. ... if it's inserts and deletes and names and things like that ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 302)

### 18. What is the root cause, and does the design fix it there rather than work around one case?

Raised on 28 occasions, in 28 files.

- On benchmark GHI-MD sandbox, he asked: "is this a general problme, that is not specific to this issue? ask the ghi-info agent if other ghis would be affect by this, particularly anything in the design-to-main pipeline ... why do we need to hide other directories - or ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/agent-instructions-and-hooks-change-benchmark-sanity-check-triage-2026-10-10-minutes.md`, line 16)
- On mistake reporting and correction, he asked: "it seems like the Git mistakes reflect some underlying problem, some root cause ... I don't know if we have a mistake reporting structure ... mistakes maintenance is sort of generally designed to be a kind of backup to a primary ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-carried-items-2026-10-28-minutes.md`, line 189)
- On idle sweep, he asked: "Does the idle sweep? Just seems like something is wrong here. Either the idles, the agents. Yeah, let's try to figure out what's going on here. This isn't the only time things, the idle sweep isn't doing the right thing or isn't ..." (`nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`, line 287)

### 19. Which outside limits, platforms or machines does the design depend on (quotas, accounts, platform behaviour, both machines), and has their behaviour been confirmed?

Raised on 28 occasions, in 27 files.

- On wake at limit resets / account cycling, he decided: "anthropic is removing the 5 hour limit, so that can be simplfied. ... I cycle the accounts as necessary. ... what we'll need to do is an external watcher. And when the weekly limit gets consumed, we will need to log out of both ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/reboot-test-remote-control-never-connected-reconnect-2026-11-01-minutes.md`, line 26)
- On messages to agent-seats and wait time, he decided: "We have to be careful with talking to agent seats. They tend to change names after logins and logouts of different accounts. And I don't see why you have to wait 24 hours. That seems like I guess this doesn't happen that much ..." (`nedlern@ned-box:/home/nedlern/agents/reboot-test/docs/walk/agent-seat-git-worktrees-branches-checkout-refresh-and-cleanup-redesign-approval-walk-2026-11-03-minutes.md`, line 44)
- On ned-box as server for Mac data, he decided: "I do want the NetBox to be the server. I do want the Mac to use the server. Anything the server needs, it seems like it should be put on the server, probably in the same command that stores it on the Mac." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 113)

### 20. Has the user already decided this, and is every decision, deferred item and follow-up recorded durably so it is carried forward?

Raised on 27 occasions, in 27 files.

- On ruling-agent, he asked: "I wonder how agents know if I've approved something, because I may approve it in one place and they may execute in a different place. ... we'll call it a ruling agent, a agent that tracks my approvals and can be quickly ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-items-2026-11-01-minutes.md`, line 234)
- On loose-ends and half-finished tasks, he decided: "Walking through all the tasks is too much. There could be 100 tasks ... So we want to try to concentrate our energy to actually get things into production. And defer in a memorable way, which is a task list or GHI things" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/prime-intellect-open-decisions-for-the-user-2026-10-22-2-minutes.md`, line 85)
- On main-gatekeeper follow-up of requests in review, he asked: "when you say close do you mean reject? I'm a bit concerned that we may assign tasks to agents that might not be reincarnated, so I'm thinking the daily maintence cycle could check for problems like this? ... Typically what should ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-3-main-gatekeeper-specification-cold-read-findings-2026-10-01-minutes.md`, line 33)

### 21. Does each name say plainly what it names, follow the naming rules and not collide with another name?

Raised on 26 occasions, in 24 files.

- On log-store transcripts/ folder name, he decided: "10, no. We use the word transcripts in other ways. That's just going to confuse the crap out of people to use the same word in different places. I'm surprised that passed the naming rule convention. ... Just keep the name as log ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-open-items-2026-10-22-minutes.md`, line 152)
- On title of the refresh-agent GHI ('nightly'), he decided: "I'm fine with this new GHI. I don't think nightly is probably a poor wording choice, because probably whenever there's a break, and nightly there will be almost always be breaks, pretty much always be breaks, but there might be ..." (`nedlern@ned-box:/home/nedlern/agents/prime-intellect/docs/walk/ghi-783-ghi-md-picks-and-renames-approval-walk-2026-11-05-minutes.md`, line 24)
- On draft-md skill name and pre-writing instructions, he asked: "should we call it draft-md or write-md? We are using draft to mean a preliminary version, which this might be. Also MD's manually created like these probably should be cold-read or might want other pre-writing instructions" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-md-reconciliation-disagreements-2026-09-30-minutes.md`, line 53)

### 22. Which agent or component owns each piece of work or state, so that no two do the same job and none is left unowned?

Raised on 24 occasions, in 22 files.

- On merge-lane-2 role, he decided: "actually, you're not the right agent to do this. You should really stay focused on merging. So you try to package this up probably as a GHI and assign it to another agent. Find the agent that's the least burdened." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 204)
- On merge-lane-2 role; overview refresh, he decided: "why are you dealing with refreshed overviews - you should concentrate on merges. Can you hand that off to another ned-box agent, or commssion one to deal with refrehsed overviews?" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-waiting-on-user-walk-2026-10-07-minutes.md`, line 17)
- On overview refresh reminder, he asked: "My concern is that if only one seat reminds me, what if I close that seat? Does it matter which seat reminds me? If not, then as long as I get reminded at least once a day, that should work." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-fourteen-decisions-2026-09-30-minutes.md`, line 60)

### 23. Does ready work start without waiting on the user, and do agents keep working rather than block or idle?

Raised on 20 occasions, in 20 files.

- On maintenance questions to the user, he decided: "I actually like it when agents continue working because I hate to be a blocking item. But if I haven't answered the question, they just have to keep repeating it, which isn't the same as blocking ... blocking is a bad idea ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md`, line 254)
- On the user's place in the state machine, he decided: "while I don't want to read code changes, I do want to be asked to read any natural language changes in the design or test design ... I am a gate ... Because I'm a gate I need to minimize when agents are blocked by me with careful ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/2026-09-03-ai-native-architecture-overview-decisions-minutes.md`, line 59)
- On fix-round limit, he decided: "I think we should leave very practical advice on what the agents should do after it stopped, so that you don't have to ask me questions like this one, which is, yes, we should basically ship what we've got when it's good enough ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 247)

### 24. How is each part tested, and does every change carry a test that fails without it?

Raised on 13 occasions, in 13 files.

- On testing AI components, he decided: "I'd just try to keep the AI components of tests to be with fresh agents, minimal context, minimal prompts or instructions. Of course we should mock up the tests to see if they work both the the ai component says yes or no, so ..." (`nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-every-open-decision-2026-10-15-minutes.md`, line 258)
- On memory review test fixtures, he decided: "some of our tests require known inputs to see if they generate known outputs. And the way we do that is through frozen or synthetic data. I can understand that, but it might be nice if we could use frozen data too, and upgrade ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/daily-memory-review-fourteen-decisions-2026-09-30-minutes.md`, line 72)
- On fix-round convergence process, he asked: "the lack of coordination between changes and testing those changes seems broken and a process problem that could be fixed, particularly as we ready for (and perhaps tweak the design of0 design-to-main system." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-fix-round-convergence-process-walk-2026-10-10-minutes.md`, line 12)

### 25. Which model or service does each judgment step, and how is the quality of its judgments measured and tested on real cases?

Raised on 11 occasions, in 11 files.

- On three-model naming check, he decided: "Gemini 3.8 is fast, maybe sol is too slow, if so pick a faster codex agent. I guess Haiku might be OK. ... set up a test/trial/benchmark to see what agents/efforts work well enough. ... find the best (fast and high quality) combo ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-decisions-whose-approval-starts-work-2026-10-17-minutes.md`, line 22)
- On cold-read-fast-read reader bake-off, he decided: "if we're going to do a bake-off, we want to see if two or three agents performs better than one ... correct positives and correct negatives and false positives and false negatives ... Opus Max to make sure the masters is good ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-research-fast-read-speed-and-design-drift-2026-11-02-minutes.md`, line 26)
- On question-check Stop hook model check, he decided: "It sounds like we may need a regular maintenance check on the quality or veracity of the Haiku check on whether, on what things are need to be added to the walk versus what things are just information. ... are we sure we're doing ..." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ghi-972-agent-seat-database-service-design-mac-task-lists-fallback-decision-and-cold-read-findings-approval-walk-2026-10-29-minutes.md`, line 252)

### 26. How is each review finding graded and routed (fix now, fix next, maintenance, filed), and which findings block a merge?

Raised on 6 occasions, in 6 files.

- On review findings grades and round limit, he decided: "talking to you and other agents about coming up with a gradation system of must fix now, fix next release, or next item in the walk. Nit fix during maintenance or other maintenance-y kind of things." (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`, line 290)
- On overview claim check and finding ranks, he decided: "The goal should be steady improvement, not perfection. So maybe we need to rate or categorize claim validities in the like supported, not supported must change, and not supported consider changing later" (`nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`, line 26)
- On nice-but-dirty review rule, he decided: "a review finding on nice-but-dirty code blocks only when it shows a limit broken, a failing test still blocks, and code that needs nice-but-dirty code is nice-but-dirty too" (`nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/pull-request-1188-decision-and-retired-alert-watcher-removal-2026-10-13-minutes.md`, line 35)
