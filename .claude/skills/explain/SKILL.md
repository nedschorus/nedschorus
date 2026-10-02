---
name: explain
description: Re-explain a message the user could not follow, so he can understand it without this agent-session's context. Use when the user types /explain; says he is confused, lost, or does not understand or follow; asks what a word, name or number means; asks you to explain a message again, go slower, or say the message in plain English; asks what you are proposing; or checks his reading with "I think you are saying…".
---

# Explain

The user often reads your messages cold. He works in several agents' terminals,
often on another machine, and comes to yours without the context you have built
up this agent-session. When he cannot follow a message, at least one piece is
usually missing: a word he does not know, a pointer to something he cannot see,
the purpose of the program or rule the message is about, or one real example of
that program or rule at work.

## Which message

Find the message he is reacting to: the message he quotes or names; otherwise
the most recent message you sent him, a progress note included, since he
sometimes answers progress notes. His words may have crossed your latest
message: he sometimes writes while you are still writing, so his words can
answer the message before your latest one. If his words fit an earlier message
better than your latest one, answer the earlier message, and say which message
you are answering by quoting its first words. If he names a word several
messages used, take the most recent message on the subject he is asking about.
Right after a session-handoff the message may be your predecessor's: look in
the conversation-tail your initial-agent-instructions name, or, when the
conversation-tail leaves the message out, in the complete dialog saved beside
the conversation-tail.

Work through the checks below in their numbered order, and skip a check that
has nothing to act on, such as check 11 when the message proposed no text and
cited no output. In the reply itself, a correction check 1 calls for comes
first, and the answer check 3 calls for comes next.

Keep each reply to about 300 words. When the explanation needs more, send the
explanation in parts of about 300 words, one part at a time: end each part but
the last by saying what the next part covers, and send the next part when he
says next.
The checks apply to the whole explanation, not to each part: run check 13 once,
on the whole explanation, before you send the first part, and end the last part
on check 12's closing line.

## Check the facts first

1. **Check the evidence before you re-explain.** Re-read the user-ruling, file,
   code or measurement the message rested on, as that evidence stands now, or,
   for a claim about what happened, the record of that time; do not work from
   memory. For a user-ruling, his latest ruling on the subject wins, one he gave
   in this conversation included; otherwise read the user-ruling where it is
   recorded: a `(user-ruled …)` line in a file, or the walk-minutes, which are
   in `docs/walk/` of the checkout that ran the approval-walk and in the
   log-store under `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/`. A
   task's description is an agent's summary: use a task's description to find
   the user-ruling, never as the user-ruling. If you cannot re-read the
   evidence, say so. If anything was wrong, say so first: correct the wrong
   claim, and correct, shrink or withdraw anything built on it.
2. **Split what the message welded together.** If one sentence carried two
   things, such as two rules, two situations, or a script and an agent, name
   each and give each its own sentence. If he is deciding something, leave out
   of your reply whichever of the two things his decision does not depend on.

## Answer first

3. **Answer what he asked, before anything but check 1's correction:** "Yes" or
   "No" to a question that takes a yes or a no, followed by what is true: "No,
   weekly."; what X is, in one sentence, to "what is X?". If he wrote "I think
   you are saying…", say whether he has the message right, then correct each
   point he has wrong. When he quotes words, explain the words he quoted.
4. **Explain one point in full:** the point his decision rests on, or, if he is
   deciding nothing, the point he asked about. Answer each of his other
   questions in a line, in his order. Carry at most one decision: if the message
   held several decisions, explain the decision he asked about, or else the
   message's first decision, and say in one line, before your closing line, that
   you can take the other decisions one at a time with /walk-me-through. Never
   cut a missing fact to fit the 300 words: the missing fact goes in the next
   part.

## Say what the program, word or rule is

5. **Say what the program, word or rule is for, and what it does today, before
   what is wrong with it.** For a program or a process, say what it tries to
   achieve, who or what runs it, and what triggers it; for a word, a number or
   a rule, say what it refers to.
6. **Use project-terms, system-terms and SDLC-terms as written, and coin none.**
   Use each project-term and system-term spelled as its glossary spells it, and
   name each software-engineering concept by its SDLC-term. Define a term only
   when he asks what the term means. Delete or replace every term you coined
   that he has not approved, and never coin a new term in a reply, even to
   replace another.
7. **Replace each reference to an earlier message display with the thing
   referred to.** For "as I said", "above", an option letter, an item number on
   its own, or a label you gave something earlier, say the thing itself. Write
   the noun instead of "it", "its", "they" or "this", and instead of "that" used
   as a noun, unless the noun is in the same sentence and no other noun there
   could be meant. When "or" could mean one-or-the-other or one-or-both, write
   which. Write each identifier in full, in the form the file
   `nc-systems/skills/explain/explain-how-to-write-an-identifier-instructions.md` gives. After a
   session-handoff, restate the whole point, not the point's label or its last
   sentence.
8. **Call each thing by one name, and say who acts at each step.** Use the
   existing name of each file, option or party, the same name every time, and
   say so when one does not exist yet. Say which agent, script or person acts
   at each step; never write "the fix escalates". If he has his own name for a
   thing, use his name, and give the existing name once beside it.

## Show a real example

9. **Trace one real example from start to outcome.** Take a named file, run,
   agent-seat or pull request: where it starts, who acts, the steps in order,
   and what he would see at the end. Give a rule after its example, unless the
   rule is what he asked for. If no real example exists, say so, then answer
   directly or use an example you label as made up; never offer an invented
   example as evidence that something happened.
10. **When the message is about a problem, say whether the problem has actually
    happened, how often, and what it costs.** Give the real incident and its
    date, what goes wrong if nothing is done, and whether the problem resolves
    on its own; if the problem has never happened, say so. If nothing is at
    stake, say so, and if the message proposed something, recommend dropping
    what it proposed.
11. **When the message proposes a change to text, or cites output, show the
    exact text.** For a proposed change, quote the current text with where it
    is, then the proposed text in full. Show a prompt, a warning or the lines
    of a command's output that matter, as they appear, then explain each
    reference, identifier and coined term in those lines. Never paraphrase the
    text "roughly".

## End on one closing line

12. **End on one closing line.** When he has something to decide, the closing
    line is one ask, stated as what each answer does: say what he is deciding,
    your recommendation and why, and what each answer causes: "Y: … N: nothing
    changes.", or one line per option when there are more than two options,
    which together are the closing line. Answer any option he proposed himself.
    Word the ask so that Y cannot be read as agreeing to the opposite. When an
    approval-walk item is waiting on his answer, the closing line is that item's
    own ask, restated. Otherwise the closing line is "Nothing needs you." Put
    nothing after the closing line.

## Have a fresh-reader read your reply before you send it

13. **Have one fresh-reader read your draft reply, unless he typed
    `/explain fast`.** Run this command from the repository root with a timeout
    of ten minutes, putting his words and your draft reply in place of the
    placeholders:

    ```
    nc-systems/skills/explain/explain-reply-cold-read-fast-read.py <<'END_OF_EXPLAIN_REPLY'
    The user wrote: "<his words>"
    The reply to him:
    <your draft reply>
    END_OF_EXPLAIN_REPLY
    ```

    The command takes one or two minutes and prints the fresh-reader's findings,
    with an instruction wherever you must act. If the command prints neither
    findings nor instructions, send your reply anyway, with one line before your
    closing line saying the fresh-reader's read failed. Fix what would also stop
    him, cutting before adding; skip requests to define a project-term, a
    system-term, an SDLC-term or a term he uses himself, and requests to cover a
    case you left out on purpose. Send once; do not run the command again on
    your fix. A fresh-reader can catch a path that does not resolve, but not a
    false claim about what happened outside the reply: catching a false claim is
    check 1's job.

## What you may change, and what you may not

- You may correct, shrink or withdraw what the message proposed, saying so. A
  corrected proposal replaces the old proposal; never offer both as options.
- A fact the message left out, such as a plan already decided, what triggers the
  program, or a premise the message rested on, is a missing piece: put the fact
  in.
- Add no proposal, option or scope of your own, and do not end on "worth a
  task?". An option he proposes now is his: answer it.
- Do not repeat the message in its own words at greater length.

## When he asks about one thing

`/explain <thing>`, or a plain question such as "what is X?" or "what does Y
mean?", narrows the reply to that one thing, whether a word, a number or a
sentence. When the first word after /explain is `fast`, the word `fast` skips
check 13 and is not the thing; any words after `fast` are the thing. Explain
the thing itself, not every other word in the message, and re-explain the
surrounding point only if the thing makes no sense without the surrounding
point. If no earlier message contains the thing, answer his question as a plain
question.

## When you cannot tell what was unclear

When he says only that he is confused, and names nothing: say that you are
guessing, name the one to three things most likely to have been opaque, and
explain those things. When the message holds no decision, your closing line
names what else you could unpack, in place of "Nothing needs you." Do not ask
him which point confused him and wait: he is
usually reading across several agents at once, so a question costs him a round
trip that a guess does not.

When he is confused a second time about the same thing, stop rewording. Go
back to check 1: the claim may be wrong, or the thing you keep explaining may
not need to exist. If he gave his reading, say whether it is right and correct
each point that is not. If he is confused a third time, make your closing line
an offer to take the explanation one point at a time with /walk-me-through.
