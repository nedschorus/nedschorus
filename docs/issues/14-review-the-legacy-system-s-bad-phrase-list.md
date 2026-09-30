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

1. **A style guide page** in `docs/nedschorus-wiki/`, with a "Words to avoid" section: one row per word or phrase, giving the word, why it misleads, and what to write instead. The standard name for such a list is a style guide's word list; Google's and Microsoft's developer style guides each keep one. Entries come from the measurement below, not from opinion. Candidates already ruled or proposed:
   - "it", "its", "they", "this", and "that" used as a noun, as in the CLAUDE.md bullet of PR [CLAUDE.md: write the noun instead of a pronoun, and say which "or"](https://github.com/nedschorus/nedschorus/pull/828).
   - "land", "landed": write "merge", "merged" (user-ruled 2026-09-30: "land-on-main is bad then. We should use merge or merged").
   - "or" without saying which "or" is meant.
   - bare "home" and bare "draft", once the glossary work names their meanings ("agent-home" and a "-draft" suffix were his proposals, 2026-09-30). The glossary work is task #417 of the merge-lane-backlog seat, "Glossary clarification of ambiguous project words".
   - the legacy list's overloaded words and deceptive phrases, where the measurement shows agents still use them.
   - the status-inflation class, "a 100% fail indicator" (user-ruled 2026-07-22): phrases that declare a fresh thing established, such as "standing doctrine"; the measurement looks for siblings such as "is now doctrine" and "established practice".
2. **A mechanical word checker**: a script holding the list, with no model in the loop, that prints each hit with its line and its replacement. The replacement is a word ("merge" for "land") or, where no single word fits, an instruction ("write the noun" for "it"). A script cannot tell every "that" used as a noun from a joining "that", so the checker flags candidates and the writer judges each one. Code and quoted text are exempt, as in the CLAUDE.md bullet. First place: a section of the cold-read-fast-read report, beside the section it already adds for bare issue numbers (`nc-systems/cold-read/cold-read-fast-read.py`). Second place, after the first is measured: a Stop hook that reads each message an agent sends the user and tells the agent which listed words it used. A Stop hook cannot change a message already shown; the legacy spec below records a `MessageDisplay` hook, measured on Claude Code 2.1.212, that runs before display, which must be re-verified before relying on the hook.
3. **A promise check**, separate from the word checker: a promise phrase in an agent's message (the measured forms: "I'll bring you X", "I'll report when…", "Noted", "I'll hold", "from now on") passes only when the same turn created a task or a reminder with one of Claude Code's tools TaskCreate, CronCreate or ScheduleWakeup. The check's message is "you promised X: create the task now, or take the promise back", not a replacement word.
4. **CLAUDE.md points to the page**, in its terms bullet, so every agent reads the rule before acting. The terms bullet gained, by the user's approval on 2026-09-30, the sentence "When you describe something a glossary names, use the glossary's term, spelled as the glossary spells it." in a pull request of its own.

## Supporting documents

- The measurement: `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-backlog/style-guide-word-count-2026-09-30.md`, with its script `style-guide-word-count-2026-09-30.py` beside it, written by a background agent started 2026-09-30: counts of each candidate word and promise phrase over 30 days of agent messages to the user, whether a task followed each promise, and the words the user himself asked about. Its headline, over 2026-08-31 to 2026-09-30 (266 sessions, 21,991 agent messages the user sees, 3,949 of his typed messages):
  - Sentence-opening "It" appears in 15.4% of agent messages; "that" as a pronoun 163 times per 1,000 messages, "this" 84.
  - Overloaded words from the legacy list: "fix" 201 per 1,000 messages, "check" 171, "state" 76.
  - "land" and its forms 144 per 1,000 against 342 for "merge"; "or" 351, about a fifth of which is the walk prompt "Y, N or D"; "draft" 75.
  - Bare project nouns the glossary defines only in hyphenated form: "walk" in 20.4% of messages, "seat" 18.0%, "head" 9.1%, "sweep" 8.3%.
  - 592 first-person promises; 47.0% were backed by a task, reminder or background job in the same response. The promise forms listed above never occur; the real forms are "I'll bring you X" (130), "I'll report when it lands" (106), "Noted" (78), "I'll hold" (51) and "from now on" (40), so the promise check keys on those.
  - 234 of the 282 messages in which he said he was confused were about a whole message, not one word: a word list clears only part of his confusion.
- The cold-read reviewers' complaints, counted 2026-09-30 over the 2,911 reports in `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/`: "it" quoted as unclear in 133 reports, "this" 21, "its" 18, "they" 13, "that" 9; "only" 41, "never" 34, "or" 29, "every" 26.
- The legacy list: [command-vocabulary.md](https://github.com/nedlern/nedlern/blob/main/docs/wiki/reference/command-vocabulary.md), § Overloaded Words to Avoid and § Deceptive Phrases That Hide Intent; on the user's Mac at `/Users/el/Projects/nedlern/docs/wiki/reference/command-vocabulary.md`.
- The legacy checker spec, never built: [console-banned-wording-checker-spec.md](https://github.com/nedlern/nedlern/blob/main/docs/working/proposed/console-banned-wording-checker-spec.md); on the Mac at `/Users/el/Projects/nedlern/docs/working/proposed/console-banned-wording-checker-spec.md`.
- The legacy enforcement that held: [postal-softener-guard.py](https://github.com/nedlern/nedlern/blob/main/.claude/hooks/postal-softener-guard.py), a fail-open reminder at the moment of action.

The nedlern repository is private; the fleet's `mac-claude` account cannot open those links, and the user can. The Mac clone at `/Users/el/Projects/nedlern` is on its `main` at `4fb0cb84` (2026-08-05) and holds all three files.

## Next action

Read the measurement, draft the page's first entries (word, why, write instead), and put them to the user in an approval-walk, one class of words per item. Then build the checker's cold-read-fast-read section, then the promise check, each in its own pull request.

## Trigger to close

The style guide page is on main with entries the user approved, the word checker runs in the cold-read-fast-read report, and the promise check runs; the Stop hook is built or ruled out on measured evidence.
