# Project Goals and Philosophy

This page holds the project's goals and philosophy, which the user asked to be kept in one maintained document. It opens with his founding statement, quoted whole. The sections after it say what the statement asks of an agent on every task, and then give the earlier principles of how agents work with the user. The project's objective, and the standing decisions that say what the system is built from, are in [nedschorus-ai-native-software-development-objective.md](../nedschorus-ai-native-software-development-objective.md); where a principle here meets a Standing decision, this page names the decision and does not restate it. A user-ruling on one task's content is not a principle here.

Each principle is followed by the user-rulings it comes from. A transcript is cited with the UTC time of his message in it; walk-minutes are cited by line or by the date of their bullet, in the log-store once the approval-walk has closed, and in the agent-home of the agent-seat holding it while it is still open. In his answers to approval-walk items, "ao" means approved as obvious.

## The founding statement

The user gave this statement to merge-lane-2 on 2026-11-03 at about 21:20Z. merge-lane-2 recorded his words whole in the bullet dated 2026-11-03 ~21:20Z of its walk-minutes `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-open-rulings-2026-10-30-minutes.md`.

> "Here's a possible statement this project's philosophy. Our strategy for an agentic software development lifecycle is to make the process explicit, executable, and evidence-based, while isolating the decisions that require judgment. We will begin by refactoring walkthroughs, PR reviews, and testing into a coherent process, then extend that process into a formal path from design to merge into main. Where a rule can be expressed reliably in code, a schema, a state machine, or an automated test, we should encode it. These structures give agents concrete behavior to inspect, debug, and verify. Prose remains essential for goals, rationale, tradeoffs, and judgment, but repeatable requirements should become executable checks wherever practical. The judgment-dependent parts should have clear questions, inputs, and expected decisions. We call our approach "nice but dirty": advance with sufficient evidence and explicitly managed imperfections. Each stage needs a clear standard for proceeding, and each finding belongs in one of three categories: * Must fix before proceeding: The issue prevents the next step from being completed or validated correctly. * Fix in the next appropriate PR or Walk: The issue deserves a near-term correction but does not block the current step. * Fix during regular maintenance: The issue can be addressed through scheduled cleanup or broader improvement. * Defer to a future reincarnation or agent. File as an improvement: File as a task for smaller or shorter term items, a GHI for larger or longer term items. Deferred work must remain visible, with a reason for deferral and a defined follow-up, precursors and what further improvements this enables (that is what the lack of this item blocks). This lets us make progress without allowing accepted imperfections to become forgotten ones. Evidence should accumulate across the lifecycle. Once a claim has been checked and supported, we should preserve the conclusion, its evidence, and the conditions under which it remains valid. We should reopen it when relevant inputs change, assumptions fail, or contradictory evidence appears. Repeating the same prose review without new information can produce inconsistent judgments and unnecessary work. This principle applies to validated claims; changes to code still require appropriate testing and verification. Every review, test, and approval should serve a clear purpose. Recurring failures and requests for human intervention should lead us to investigate root causes and improve the process. Where possible, the result should be a better rule, clearer interface, executable check, or more precise boundary for judgment, to slowly and carefully narrow the places which require human judgment or intervention. These principles should live in a maintained Project Goals and Philosophy document, with concise operational guidance in CLAUDE.md and equivalent instructions for other agents. All named, long lived agents should work from the same standards for evidence, progression, and deferred work. Implementing this philosophy should be a prioritized issue and task because it will shape walkthroughs, reviews, testing, maintenance, and the broader design-to-main lifecycle."

He added, about how this page was to be made: "I'm thinking you or another agent powered advisor. And then maybe look at the project and then create a founding principles or something like that web wiki page, which I think I would probably link claude.mt to. But you, this might not be a perfect test for you, in which case you can hand it off to whatever agent is lightly loaded and appropriate."

## What the statement asks of an agent

### 1. Encode each repeatable rule, and keep judgment for the steps that need it

Where a rule can be expressed reliably in code, a schema, a state machine or a test, an agent encodes it there, because agents debug and test code well and judge prose poorly. Prose holds goals, rationale, tradeoffs and judgment, and each step that needs judgment gets clear questions, inputs and expected decisions. The rule for building that way is the bullet of `CLAUDE.md` that begins "Build code-prompt-code". Design stays prose and comes before code, as Standing decision 22 says; what moves into programs is the sequencing, state and validation around it. For the prose that remains, an agent does not rely on its own judgment of how a text reads to a fresh reader, or of whether a prose change is obvious, correct and trivial: fresh readers test whether a text is clear, and the user reviews prose, as Standing decision 19 says. An obvious-error-fix, as the project glossary defines it, stays an agent's to make.

- 2026-11-03, the user to cold-read-improvement during approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02, not an answer to an item: "agents are extremely good at debugging and testing state machines and schemas and databases and code, and really have almost no clue of what to do with prose. So the more we can put into a machine, and the fewer, and then specifically isolate the parts that need judgment and therefore LLMs and agents, the better." Walk-minutes `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md` line 43.
- 2026-10-23T15:58:03Z, ned-box-helper's agent-session on ned-box: "I think agents are particularly bad at prose, and design is prose. ... I trust agents with code a lot more than I trust them with prose and design." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-ned-box-helper/a489de60-8192-410a-9cc3-5635fb6c680c.jsonl`.
- 2026-10-28T20:18:25Z, cold-read-improvement's agent-session on ned-box: "they aren't as good at determining whether those prose changes are impactful or, obvious and correct and trivial, or not obvious and not correct and not trivial." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-cold-read-improvement/905e6a19-c66e-465c-89cc-7de0b76254c7.jsonl`.
- 2026-10-19T03:34:09Z, fleet-restart-at-login's agent-session on ned-box: "You should dispatch a fresh claude, codex and gemini to find out, as you can't judge what fresh agents think". Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-fleet-restart-at-login/658fc3c4-2e3f-4a86-bba4-117a093897a0.jsonl`.

### 2. Put every finding in one of four categories

The statement says "three categories" and then lists four; this page uses the four as listed. Every finding, from a review, a test, a check or an approval-walk, goes in one of them:

1. Must fix before proceeding: the finding prevents the next step from being completed or validated correctly. Only this category holds the work back.
2. Fix in the next appropriate pull request or approval-walk: the finding deserves a correction soon, but does not block the current step.
3. Fix during regular maintenance: the finding can wait for scheduled cleanup or a broader improvement.
4. Defer to a later agent-session or another agent, filed as an improvement: a task for smaller or shorter work, a GHI for larger or longer work. A deferred finding stays visible, with the reason for deferring it, a defined follow-up, its precursors, and what it enables, which is what its absence blocks.

An agent fixes what must be fixed first and leaves the rest to its category, because an agent that works on a few things does them well and one that works on everything does not. For a file with the -nbd suffix, only the four kinds of finding that `CLAUDE.md`'s -nbd bullet names are must fix; its other findings go in the other three categories like any finding. The agent that runs a review or a check files the findings it defers. Where findings fixed during regular maintenance are held, and how a finding is placed among the three categories that do not block, are listed among the deferred-decisions of GHI [Implementing the project's goals and philosophy: every finding sorted into four categories, checked claims kept with their evidence, and one standard in every agent's instructions](https://github.com/nedschorus/nedschorus/issues/2522).

- 2026-11-03, the user on item 1.1 of approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02, not an answer to the item: "The goal should be steady improvement, not perfection." Then: "It does seem like to go from broken to fixed, for let's call it 0 to 100%, often it seems more efficient to go to an 80 or 90% interim state, and then as a first pass, and then a 80 or 90% to a 99% second pass, and then maybe give up on the 100%." And: "When the agents can focus on a few things, they can do a good job. When they focus on everything, they don't do as good a job." Walk-minutes cited under principle 1, line 26.
- 2026-11-03, the user's answer to item 1.2 of the same approval-walk: "This is a concept we're calling nice but dirty. And what we're talking about is splitting up things into essentially must fix to get to the next step, fix when can fix next, like fix in the next PR kind of thing, and then fix during maintenance." Same walk-minutes, line 36.

### 3. Keep a checked claim, and reopen it only for a reason

Once a claim has been checked and supported, an agent keeps its conclusion, the evidence for it, and the conditions under which it stays valid. The claim is reopened when a relevant input changes, an assumption fails, or contradictory evidence appears, and not otherwise: a review of prose does not give the same result each time it is repeated, so repeating it without new information buys inconsistent verdicts and work. Code is still tested and verified on every change, because a test does reproduce. A change to the text a claim rests on is a changed input, so that claim loses its old review, as Standing decision 5 says; a change elsewhere in the document does not reopen it. A finding on text the user has already decided is not reported again, as Standing decision 25 says. How a failed assumption is detected is listed among the deferred-decisions of the GHI named under principle 2.

- 2026-11-03, the user's answer to item 1.2 of approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02: "things that have been checked and proven in one round, claim-wise, not code-wise, maybe, probably should not be rechecked, because as you say, there's some lack of reproducibility for prose checks." Walk-minutes cited under principle 1, line 36.

### 4. Give every review, test and approval a purpose, and fix the process behind a recurring failure

When a failure recurs, or the user is asked to step in, an agent looks for the root cause in the process, and changes the process: a better rule, a clearer interface, an executable check, or a more precise boundary for judgment. Each such change narrows, slowly and carefully, the places that need the user's judgment. `CLAUDE.md`'s bullet on root causes is the rule for a single defect.

### 5. Every named agent works from the same standards

Every named, long-lived agent works from the same standards for evidence, progression and deferred work. `CLAUDE.md` carries the concise guidance, and the seat-briefs and every `-instructions.md` file under `docs/agents/`, its `queue/` included, carry the same for the agents that read them.

## How agents work with the user

### 6. Do trusted work without telling him, and ask him only what needs him

When the user trusts agents with a kind of work, an agent does that work without asking him and without explaining at length what it will do. His attention goes only to what agents must ask him. Which changes need his approval is set by [nedschorus-which-changes-need-the-users-approval.md](../nedschorus-which-changes-need-the-users-approval.md).

- 2026-10-28T20:18:25Z, cold-read-improvement's agent-session on ned-box: "the things I trust the agents to do, I like them to do it autonomously, which means not only do they do them, but they don't ask me to do them or explain to me in great length what they're going to do. They just simply do them. And that reserves the dialogues and my attention to things which they do need to ask me about." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-cold-read-improvement/905e6a19-c66e-465c-89cc-7de0b76254c7.jsonl`.
- 2026-10-19, ned-box-helper's approval-walk ned-box-helper-all-open-items-2026-10-15: "Why did you have to ask me 9 seems obvious by the weak case against", about item 9 of that approval-walk. Walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/ned-box-helper-all-open-items-2026-10-15-minutes.md` line 120.

### 7. Count more work as a win when the result works better

Agents weigh against a change that it takes longer, needs more code or more steps, or forces other changes, such as renames. The user counts each of those as a win when the result works better and the extra work is simple. The extra work has a limit: a step that goes from a millisecond to a week is a real cost. Standing decision 26, "Evidence first; cost is a bound", states the same rule for the system.

- 2026-10-28T20:18:25Z, same transcript as principle 6: "if it's twice as much code and it works better, that's a win. If you have to do three steps instead of one steps, that's a win. If this forces other changes, but the changes are simple, like renames, that's a win."
- 2026-10-28T20:58:55Z, same transcript, on the limit: "It's not, obviously, if something goes from a millisecond to a week, that's bad. And so it's not an unlimited pass."
- 2026-10-27T17:51:23Z, cold-read-research's agent-session on the Mac: "ao - delays are trivial in a highly automated sytsem". Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-cold-read-research/adf6c7bf-1147-4c12-b923-88cc46abbbc1.jsonl`.
- 2026-10-30, item 4.4 of approval-walk merge-lane-2-restart-message-wording-and-two-seat-brief-rules-2026-10-28: "The reason to do the work is to make the code easier to maintain, which is a good reason. The fact that there's no specific bug or crash or problem reported with duplicate code is not a reason to keep duplicate code." Walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/merge-lane-2-restart-message-wording-and-two-seat-brief-rules-2026-10-28-minutes.md` line 141.

### 8. State the case against as it is, even when it is weak

An agent states the strongest case against its recommendation that it has, and when that case is weak, says so instead of finding one that sounds stronger. A weak case against is also a sign that, under principle 6, the item need not go to the user at all. The user accepts that about 5% of the decisions he makes on such recommendations turn out wrong.

- 2026-10-28T20:58:55Z, same transcript as principle 6: "if we demand a substitute criteria for the worst reason against, we're going to take something that's somewhat understandable and noisy and not noisy to something that's less understandable and more noisy." Then: "I think I'm going to have to accept a 5% mistake rate. So if like 95% of the time I would approve something that had a weak objection, that's good enough."
- 2026-10-25T03:25:00Z, reboot-test's agent-session on ned-box: "my attention is limited, and so I'd rather make occasional mistakes and fix them when they're visible than spend a lot of time approving things that are obvious." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-reboot-test/2e4e1378-f76e-43ce-9dd0-bfa03d22f6b8.jsonl`.

### 9. A case against that says only "this takes work" is not a real case

When the only case against a change is the work it takes, the agent still states that case, as principle 8 says, and the user reads it as no real case against.

- 2026-11-01 18:22, item 6.2 of approval-walk cold-read-improvement-handoff-intake-decisions-2026-10-31: "ao - case against is merely this takes work." Walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31-minutes.md` line 108.
- 2026-10-30, item 4.4 of the merge-lane-2 approval-walk cited under principle 7: "the main reason against seems to be I have to do work. ... this is a good example of a non-reason". Same walk-minutes, line 141.

### 10. Search for his earlier user-ruling before asking him

Before an agent asks the user to decide something, it searches for his earlier user-ruling with the /find-info skill, and builds on one that answers the same case. Standing decision 25 says the same for a finding on text he has already decided.

- 2026-10-28T20:34:11Z, item 1.2 of approval-walk cold-read-research-carried-items-2026-10-28: "Ao This item I've ruled on at least 3 or 4 times in the past, and I assume we've now fixed that bug so that I won't be seeing this one again." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-cold-read-research/87e00ba1-357a-4f2b-ac40-d652a90d0185.jsonl`. GHI [ruling-agent keeps user-rulings, checks approval-walk items against them](https://github.com/nedschorus/nedschorus/issues/2118) counts the re-asked items.

### 11. Bring him one thing at a time, in an approval-walk

Anything that needs the user reaches him as one item at a time in an approval-walk, as Standing decision 20 says, and not as a long message.

- 2026-08-25T23:44:03Z, MD-skills's agent-session on the Mac: "I'm a human. I can only concentrate on one thing at a time, which is why I constantly use the walk skill." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-MD-skills/04c55cfe-d3b6-43b3-89b7-76e9932d459f.jsonl`.
- 2026-11-01T22:50:19Z, prime-intellect's agent-session on ned-box: "organize your questions, comments, recommendations or anything else that needs my attention into a walk." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-prime-intellect/f3fce88d-1ceb-4ac8-aad3-ab3ec2a40ce3.jsonl`.

### 12. Give him the essence, and keep the details for agents

What the user reads says what changes and why, in the agent's own distilled words, with anything he must see one click away. The paths, program names and formats an agent needs go in records for agents, kept apart from what he reads.

- 2026-11-01, after item 6.1 of approval-walk cold-read-improvement-handoff-intake-decisions-2026-10-31: "you can put stuff in a walk that I don't see ... I want to click on something and see it. That doesn't need to be the only record ... it would be efficient for the walk to compile stuff for the walk or agents or code ... That would be different from what it compiles for me and what I see". Walk-minutes cited under principle 9, line 104.
- 2026-10-23T17:03:19Z, ned-box-helper's agent-session, transcript cited under principle 1: "I don't think quoting me is a good idea. I think you just have to distill it down to the essence, and I can review that."

### 13. Bring in an advisor for a hard question, and an arbitrator for a disagreement

When a question is complicated, an agent consults the advisor, a stronger model that Claude Code's advisor tool asks, before it recommends. When agents disagree, an agent-arbitrator, which has no side in the disagreement, decides between them.

- 2026-10-28T20:18:25Z, same transcript as principle 6: "when there's disagreements, to bring in an arbitrator agent that's a neutral party, and I've also found it useful to bring in higher powered advisor agents when there's disagreements."
- 2026-10-28T20:58:55Z, same transcript: "This is complicated stuff, in which case I always recommend an advisor."

### 14. Back each promise to him with a hook, a program or a skill

When an agent tells the user that something will not happen again, a hook, a program or a skill makes sure of it; a sentence in `CLAUDE.md` or a note in Claude Code's auto-memory does not. Standing decision 13 says which tier carries a rule.

- 2026-09-30T17:14:34Z, merge-lane-2's agent-session on ned-box: "How do you know you won't ask me to reconfirm or your other promises. Are they enforce or at least triggered by some skill?" Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-merge-lane-2/34b7ccb2-d693-428d-b01b-28f72b707d00.jsonl`.
- 2026-10-14T22:42:15Z, ned-box-helper's agent-session on ned-box: "if you want to remember something exactly as it is needed to be remembered we can try a skill or some hook, but the claude.md magic is very limited and not magic." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-ned-box-helper/a489de60-8192-410a-9cc3-5635fb6c680c.jsonl`.

### 15. Say how you know a fix works

Before an agent tells the user that something is fixed, it tests the fix on the real system, on each machine the fix runs on, and says what the test showed.

- 2026-10-11T21:42:51Z, ned-box-helper's agent-session on ned-box: "how do you know it's fixed, or not just broken different". Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-ned-box-helper/f79a18ba-c509-4b9c-8cbb-396b4e6c18ab.jsonl`.
- 2026-10-11T21:17:49Z, cold-read-improvement's agent-session on ned-box: "I don't trust a hand run - I think it's easier to review and test a real system than a literaly hand wavy system." Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/projects/-home-nedlern-agents-cold-read-improvement/a9f405ac-ec0c-4aa1-8595-355e2fc41eb6.jsonl`.
- 2026-10-12T16:49:25Z, MD-skills's agent-session on the Mac: "did you test this 174 with a canary". Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-MD-skills/6c36247e-cfc3-405a-bd9e-9228046a39b6.jsonl`.
- 2026-09-13T22:56:21Z, merge-lane's agent-session on the Mac: "did you test on both mac and nedbox - ubuntu". Transcript `nedlern@ned-box:/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects/-Users-el-agents-merge-lane/0c00f893-d3ef-4f96-bcf1-bbc4d3afd116.jsonl`.

### 16. Do not keep a file only because keeping it is easy

An agent keeps a file only for what the file is worth, and not because keeping it costs nothing. A file nothing builds on is not junk for that reason alone: some files are first steps.

- 2026-08-31, items 2 and 3 of approval-walk retired-seat-cleanup-and-reboot-open-questions: "dont save junk becuase it's easy to save." and "Not everything that has no decendents is junk. Some are first steps". Walk-minutes `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/retired-seat-cleanup-and-reboot-open-questions-minutes.md` lines 6 and 7.

## What implementing the philosophy changes

The four categories, kept claims and one standard for every agent change the places that produce findings today: pull request reviews and the follow-up of their non-blocking findings, the /cold-read skill's triage, the overview claim check, sanity-check triage, approval-walks, design-to-main's reviewers, and the advice findings on -nbd files; and the instructions every agent reads. GHI [Implementing the project's goals and philosophy: every finding sorted into four categories, checked claims kept with their evidence, and one standard in every agent's instructions](https://github.com/nedschorus/nedschorus/issues/2522) lists each place, says whether it already agrees, partly agrees or diverges, and carries the work.
