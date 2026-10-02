---
issue: "[A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14)"
---

# A project style guide: words to avoid, a mechanical checker, and a check on unbacked promises

## Why

The user reads agents' messages cold, across many agents' terminals, and loses time to words he cannot pin down. On 2026-09-30, in the merge-lane-backlog seat's approval-walk explain-skill-draft-2026-09-29-2, he directed a list of words agents should avoid, each with the reason and the word to write instead:

> "I have been thinking of having a 'bad' word list, an anti-glossary of sorts, words that should be avoided (and why). It, land, ... seem like good candidates"

He also named a second class, with a different reason and a different message to the agent:

> "agents saying they will remmember somethig, or will do something soon, but unless the todo soons are in a tasks list, or the remember somethings have some reminder or enforcmentt, those are 'bad' too - though for very different reasons - requiring very different 'error messages'."

He asked that the checker be mechanical and that each entry carry its replacement ("Is the style guide checker mechnical - if so good - I assume each word has the prefered alternative?"), and that the list be measured from the transcripts before the list is written ("we might want to review our jsonls for additional 'bad words'"). He approved filing the work ("y", 2026-09-30).

The legacy system's list failed as text alone. The legacy page records that "under heavy context ... the model falls back to training priors", and the one class the legacy system enforced at the moment of action, the postal softener guard, is the class that held (the legacy issue nedlern/nedlern#1513, cited by this issue's first version; the legacy issue's title is not readable from the fleet's account). So this issue builds the list and its enforcement together.

## What to build

1. **A style guide page** in `docs/nedschorus-wiki/`, with a "Words to avoid" section: one row per word or phrase, giving the word, why it misleads, and what to write instead. The standard name for such a list is a style guide's word list; Google's and Microsoft's developer style guides each keep one. Entries come from the measurement below, not from opinion. The list is one for the whole project, not one per system as the glossaries are (user, 2026-10-01). Candidates already ruled or proposed:
   - "it", "its", "they", "this", and "that" used as a pronoun, as in the CLAUDE.md bullet of PR [CLAUDE.md: write the noun instead of a pronoun, and say which "or"](https://github.com/nedschorus/nedschorus/pull/828).
   - "land", "landed": write "merge", "merged" (user-ruled 2026-09-30: "land-on-main is bad then. We should use merge or merged").
   - "or" without saying which "or" is meant.
   - six words that each carry several project meanings, with the name the user approved for each meaning in the approval-walk glossary-names-for-ambiguous-project-words-2026-10-01; written bare, each word keeps only its ordinary English meaning. An entry of this kind does not forbid the word: it reminds the writer which name each meaning takes.
     - "home": agent-home for the directory an agent-seat works in; canonical location for the one place a document or fact is kept.
     - "draft": -draft for the filename suffix; "pending approval" for text that waits for the user's approval; "the `draft` label" for the GitHub label; `docs/drafts/` for the directory.
     - "walk": approval-walk for the event; walk-document for the file `docs/walk/<name>.md`; approved-by-walk for the result; "put to the user in an approval-walk" for the act.
     - "seat": agent-seat for the identity; agent-session for one running conversation; "the agent-seat's name" for the name of an agent-seat; working directory for where an agent-session works; cold-read-cell for one reviewer in a cold-read-full-run.
     - "head": head commit for a pull request's newest commit; frozen-head for a head commit once pushed; `HEAD`, in capitals, for what a Git checkout has checked out.
     - "drain": queue-drain for the procedure that empties a queue; "is promoted to" for an item that leaves a queue for its destination.
   - the legacy list's overloaded words and deceptive phrases, where the measurement shows agents still use them.
   - the status-inflation class, "a 100% fail indicator" (user-ruled 2026-07-22): phrases that declare a fresh thing established, such as "standing doctrine"; the measurement looks for siblings such as "is now doctrine" and "established practice".
2. **A mechanical word checker**: a script holding the list, with no model in the loop, that reports each hit with its line and its replacement. The replacement is a word ("merge" for "land"), the names to choose from ("head commit or `HEAD`" for "head"), or, where no single word fits, an instruction ("write the noun" for "it"). A script cannot tell every "that" used as a pronoun from a joining "that", so the checker flags candidates and the writer judges each one. Code and quoted text are exempt, as in the CLAUDE.md bullet.

   **No model rewrites a flagged word; every hit goes back to the writer** (user-approved 2026-10-01, in the same approval-walk). Only the writer knows which meaning it intended: bare "head" is a head commit or `HEAD`, and a rewriting model without the session's context would guess. A guess shown to the user would also be text the writing agent never wrote and does not hold, so a sentence the user quotes back could not be found. The checker runs at four places, each through a Claude Code hook except the last:
   - **A markdown file**: a PostToolUse hook on the Write and Edit tools checks the text just written and hands the agent each hit's line and the names to choose from, while the file is open.
   - **A message to another agent**: a PreToolUse hook on the SendMessage tool stops the send until the agent rewrites the message, so the receiving agent never reads the listed word. A send the agent repeats unchanged passes, because the writer judges each candidate: a word used in its ordinary English meaning, or in quoted text, stays. The hook's refusal text tells the agent this outright, in one instruction line: when each flagged word is used in its ordinary English meaning or inside a quotation, send the same message again unchanged and it goes through (user-approved 2026-10-02; the line in the refusal text user-directed the same day). The hook keeps a hash of each message it refused in a state file of the agent-seat's own, so it can tell an identical second send.
   - **A message to the user**: a MessageDisplay hook marks the word on screen with its choices, such as "head (head commit or `HEAD`?)", without choosing one. The mark adds to the agent's words and removes none, so a sentence the user quotes back still holds the agent's own words. A Stop hook tells the writing agent which listed words its message used. No hook can make the agent rewrite a message before the user reads the message, because the message is the model's own output.
   - **A document put to review**: a section of the cold-read-fast-read report on every document the fast read reads, as a second pass, placed beside the section the report already adds for bare issue numbers in walk drafts (`nc-systems/cold-read/cold-read-fast-read.py`).

   The text each hook hands the agent follows CLAUDE.md's bullet on the text a program hands an agent at the moment the agent must act.

   **The MessageDisplay hook, measured 2026-10-01 on Claude Code 2.1.287** (`nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/message-display-hook-live-test-2026-10-01.md`): the hook runs before the text is shown, once per batch of completed lines. The screen showed only the hook's replacement and never the raw text, in an interactive run and in a headless run. The transcript, and what the model sees, keep the original text. The display waits for the hook: a hook that slept 3 seconds delayed the text by about 3 seconds, so the hook must be fast. Claude Code's code also has a path that shows the raw text first and rewrites the text when the hook returns; that path did not run in the test, and what selects that path is not measured. If that path runs, the mark appears a moment after the word instead of with the word.
3. **A promise check**, separate from the word checker: a promise phrase in an agent's message (the measured forms: "I'll bring you X", "I'll report when…", "Noted", "I'll hold", "from now on", "going forward", "from here on", "I'll … when/once <an event>" and "say the word and I'll …") passes only when the same turn backed the promise with the trigger that will make it happen (user-approved 2026-10-02). The principle: a rule names the trigger that enforces it, because a rule with no trigger depends on an agent remembering it.
   - **A promise to act later, or after an event**: passes when the same turn created or updated a task with a due time or a checkable prerequisite, which GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940) raises to the agent when it is due. A task with neither does not pass, because nothing makes it fire.
   - **A standing rule** ("from now on…", "going forward", "from here on", "Noted"): passes only when backed by the hook or test that enforces it, or by a task to build one together with a proposal to the user. A memory never passes: nothing forces an agent to read one.
   - **A hold** ("I'll hold"): passes with a task whose due time re-checks whether the hold can be released.

   The check's message is "you promised X: create the task now, or take the promise back", not a replacement word. The check runs as a Stop hook, so it can refuse the stop with that message and the agent's turn continues until the promise is backed or taken back. A promise is raised once per message, so the check cannot loop the agent: taking the promise back is a sentence to the user saying so. For a standing rule the check can see only that the turn created a task or changed a hook or test file, not that the change enforces the rule; the review of that change judges the fit.
4. **CLAUDE.md points to the page**, in its terms bullet, so every agent reads the rule before acting. The terms bullet gained, by the user's approval on 2026-09-30, the sentence "When you describe something a glossary names, use the glossary's term, spelled as the glossary spells it." in a pull request of its own.

## Supporting documents

- The measurement: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/style-guide-word-count-2026-09-30.md`, with its script `style-guide-word-count-2026-09-30.py` beside it, written by a background agent started 2026-09-30: counts of each candidate word and promise phrase over 30 days of agent messages to the user, whether a task followed each promise, and the words the user himself asked about. Its headline, over 2026-08-31 to 2026-09-30 (266 sessions, 21,991 agent messages the user sees, 3,949 of his typed messages):
  - Sentence-opening "It" appears in 15.4% of agent messages; "that" as a pronoun 163 times per 1,000 messages, "this" 84.
  - Overloaded words from the legacy list: "fix" 201 per 1,000 messages, "check" 171, "state" 76.
  - "land" and its forms 144 per 1,000 against 342 for "merge"; "or" 351, about a fifth of which is the walk prompt "Y, N or D"; "draft" 75.
  - Bare project nouns the glossary defines only in hyphenated form: "walk" in 20.4% of messages, "seat" 18.0%, "head" 9.1%, "sweep" 8.3%.
  - 592 first-person promises; 47.0% were backed by a task, reminder or background job in the same response. The promise forms listed above never occur; the real forms are "I'll bring you X" (130), "I'll report when it lands" (106), "Noted" (78), "I'll hold" (51) and "from now on" (40), so the promise check keys on those.
  - 234 of the 282 messages in which he said he was confused were about a whole message, not one word: a word list clears only part of his confusion.
- The rerun of that measurement, 2026-10-02, at the user's request to add "going forward": `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/promise-phrase-count-2026-10-02.md`, with its script `promise-phrase-count-2026-10-02.py` beside it (the 2026-09-30 script with more promise phrases, over 2026-08-31 to 2026-10-02: 24,073 agent messages). Strong promises, with the share backed in the same response by a task, a reminder or a background job:
  - "I'll bring" 178 (44%), "I'll report" 115 (53%), "Noted" 84 (37%), "from now on" 55 (47%; 15% when a `TaskUpdate` tool call, mostly a status change, does not count as backing), "I'll hold" 53 (57%), "I'll carry" 30 (47%).
  - "going forward" 12 (17%; 8% without `TaskUpdate`): the lowest backed share of any phrase seen ten or more times.
  - "moving forward", "won't happen again", "lesson learned", "I'll keep that in mind" and "I'll always" or "I'll never" do not occur; "I promise" occurs once.
- The forms the phrase list misses, found 2026-10-02 by Codex over 4,000 sampled sentences that hold a future or commitment marker and match no listed phrase: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/promise-phrase-codex-mining-2026-10-02.md`. Most frequent in the sample: "say so", "tell me", "say the word" or "say which", followed by "and I'll …" (93 together); "I'll merge", "post", "send", "show", "push" or "review" "… when" or "once" an event happens (about 40); "I won't touch", "start" or "merge" "… until" (17); "from here on" (3). Codex judged 35 of 200 sentences it read closely to be promises nothing backs.
- The cold-read reviewers' complaints, counted 2026-09-30 over the 2,911 reports in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`: "it" quoted as unclear in 133 reports, "this" 21, "its" 18, "they" 13, "that" 9; "only" 41, "never" 34, "or" 29, "every" 26.
- The legacy list: [command-vocabulary.md](https://github.com/nedlern/nedlern/blob/main/docs/wiki/reference/command-vocabulary.md), § Overloaded Words to Avoid and § Deceptive Phrases That Hide Intent; on the user's Mac at `/Users/el/Projects/nedlern/docs/wiki/reference/command-vocabulary.md`.
- The legacy checker spec, never built: [console-banned-wording-checker-spec.md](https://github.com/nedlern/nedlern/blob/main/docs/working/proposed/console-banned-wording-checker-spec.md); on the Mac at `/Users/el/Projects/nedlern/docs/working/proposed/console-banned-wording-checker-spec.md`.
- The legacy enforcement that held: [postal-softener-guard.py](https://github.com/nedlern/nedlern/blob/main/.claude/hooks/postal-softener-guard.py), a fail-open reminder at the moment of action.

The nedlern repository is private; the fleet's `mac-claude` account cannot open those links, and the user can. The Mac clone at `/Users/el/Projects/nedlern` is on its `main` at `4fb0cb84` (2026-08-05) and holds all three files.

## Next action

Read the measurement, draft the page's first entries (word, why, write instead), and put them to the user in an approval-walk, one class of words per item. The build need not wait for that approval-walk: the first build starts with the entries the user has already approved, the pronoun words, "land" and the six words of item 1.

A subagent of the agent-seat merge-lane-backlog builds the checker (user, 2026-10-01), each step in its own pull request, in this order:
1. the list and the script, with the PostToolUse hook on Write and Edit;
2. the PreToolUse hook on SendMessage;
3. the MessageDisplay mark, with the Stop hook;
4. the cold-read-fast-read section;
5. the promise check of item 3, after the idle check of GHI [Tasks raise themselves when their due time passes or their prerequisite is met](https://github.com/nedschorus/nedschorus/issues/940) is built.

## Trigger to close

The style guide page is on main with entries the user approved, the word checker runs at the four places item 2 names, the promise check runs, and CLAUDE.md points to the page.
