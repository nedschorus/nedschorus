---
issue: "[Approval-walk items keep agent detail on marked lines that the user's view leaves out](https://github.com/nedschorus/nedschorus/issues/2390)"
---

# Approval-walk items keep agent detail on marked lines that the user's view leaves out

In short: each approval-walk item becomes two views of one text. The user sees a plain item, on its page and in the message: what changes and why, and his decision. Agents and code also see marked lines in the same item, each opening with a hashtag, holding the files a change touches, the command that finds them, and the evidence. The walk check program validates those lines, and the agent that builds the approved work reads them. Nothing is lost, and nothing is looked up twice.

The user approved this plan on 2026-11-01, as item 6.2 of cold-read-improvement's approval-walk `cold-read-improvement-handoff-intake-decisions-2026-10-31`. Nothing is built yet. The next action is to write the design for the work below, naming each hashtag and the validation of its lines, and give it its cold read; the changes to `.claude/skills/walk-me-through/SKILL.md` then go to the user for approval.

Sources: the walk-document `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31.md`, sections "Item 6.1" and "Item 6.2", and its walk-minutes beside it, `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/cold-read-improvement-handoff-intake-decisions-2026-10-31-minutes.md`, lines 89 to 110. Neither file is on main; both reach the log-store when the approval-walk closes.

## Why

Today each item is one text, which three readers share: the user, who reads it in the message and on its page; the walk check program, `nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py`, and the walk hooks under `nc-systems/skills/walk-me-through/`; and the cold-read-fast-read that the skill runs on every item before it is shown. That cold-read-fast-read is written for "a future agent who has only this info", so it asks for full file paths, and agents add them to the user's text.

So item 5 of that walk reached the user with five file paths, a constant from the code and a `git grep` command in its recommendation. The user, 2026-11-01, answering item 6: "what is this junk at the bottom of the page --- ... I do not want to see details like this so if the walk needs them for mechnanical or other reasons that's fine, but don't put them in the item page I see when I click on the item page."

Item 6.1 then proposed keeping such detail out of items and putting it in the task that carries the approved work. The user approved it ("ao"), then revised it the same day: "you can put stuff in a walk that I don't see ... I want to click on something and see it. That doesn't need to be the only record or file or recording or file or whatever of stuff to do. I would think it would be efficient for the walk to compile stuff for the walk or agents or code that would make it more efficient. That would be different from what it compiles for me and what I see. ... It would be different in the sense that I don't want the detail and the detail might be useful to the agent. ... So I see what I need and it gets what it gets, without having to reinvent it or duplicate it". Item 6.2, this plan, replaced item 6.1's direction; he approved it as obvious: "ao - case against is merely this takes work."

## What exists to build on

- The walk check program already reads marked evidence lines inside an item for items the user is not asked about: `#not_asked_touches` and four others of the `#not_asked_` family, validated by its `not_asked_problems` function (paths exist, names unused). The agent view mostly exists already, for one kind of item.
- GHI [Approval-walk item page publisher copying linked files into the page as timestamped copies, so short repository and log-store paths open on the iPad](https://github.com/nedschorus/nedschorus/issues/2168) is the vehicle for a committed program that builds each item page; today agents build pages by hand.
- GHI [The walk-me-through check program reads untagged walk-minutes lines as decisions by their keywords](https://github.com/nedschorus/nedschorus/issues/1930) covers the check program reading tagged lines, the mechanism to extend.
- GHI [ruling-agent keeps user-rulings, checks approval-walk items against them](https://github.com/nedschorus/nedschorus/issues/2118) plans `#rulings_checked` lines in items; those become agent lines too.

## The work

1. **Agent lines in every item.** Any item may carry lines that open with an agent hashtag, of fixed kinds that code checks: the `#not_asked_` evidence kinds, generalized to every item, and one for a command. The design names any new hashtag, after the naming check. The plain text still says what changes; an agent line never holds a decision, and no agent line opens with `Recommendation:`, which the hook that expands the user's short answer, `nc-systems/skills/walk-me-through/walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py`, reads as the recommendation.
2. **The user's view leaves agent lines out.** The page builder, which also prints the plain item as Markdown for the message, committed under the item page publisher GHI above, drops agent lines and writes `#case_against` as plain words. It shows a `#new` text under the words "If you approve, the new text:" and a `#new_if_d` text under "If you disapprove, the new text:", and so does the message; the walk-document keeps the hashtags (user-ruling: item 5.2.5.2 of ned-box-helper's approval-walk `ned-box-helper-open-items-2026-10-27`, approved by the user and accepted by cold-read-improvement on 2026-10-31). [PR 2387, Question-check Stop hook: an item's #new line shown as "If you approve, the new text:" is the item's own text](https://github.com/nedschorus/nedschorus/pull/2387), still open, makes the Stop hook that refuses a question asked outside an item read those two phrases. The skill's two "as the walk-document has it" rules (`.claude/skills/walk-me-through/SKILL.md`, the paragraphs on presenting an item and publishing its page) and the two matching instruction texts in `walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py` become "as the page builder renders it", with their tests.
3. **The walk check program validates agent lines on every item** that carries them, with the validator it already uses for not-asked items, and the agent that builds the approved work reads them from the walk-document.
4. **The cold-read-fast-read reads the user's view.** On the walk route it is given the rendered item and told that references belong on agent lines, so it stops asking for paths in the user's text.
5. **Code writes the approval the instruction-file guard reads.** The walk check program already records the user's exact words on the answer line; it writes the `.walk-approved` marker file from that line, where an agent now copies it by hand, for an approving answer to an item whose change edits a file the guard protects.

Each part is its own small pull request. Part 2 needs the page builder of the item page publisher GHI, so that program is built first. Every change to `.claude/skills/walk-me-through/SKILL.md` goes to the user for approval first.

## Open questions (added by the agent that filed this GHI, not from the user)

1. Which agent-seat builds each part: ned-box-helper owns the walk-me-through skill; cold-read-improvement owns the cold-read-fast-read.
2. When the walk check program validates an item's agent lines: before the item is first shown, so that a bad path never meets an answer the user has already given, or at the answer.
3. Where a link goes that the user must open to decide: it stays in the plain text he sees, and the design says how the walk check program tells it from detail that belongs on an agent line.
