#!/usr/bin/env python3
"""Carry out the user's A, AO, Aa, D, Z, O2 or O3 answer to the waiting item of an
open approval-walk, or his A, AO or D answer to each part of it, or his moving on
from an item that asks no decision: give each text
the answer adds a cold-read-fast-read, then record the answer in the
walk-minutes and set their `#next_to_present` line to the next item; or record
the waiting item as settled without showing it to him.

Usage, from the agent-session's checkout:
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check
      [--obvious | --after-advisor | --disapproved | --deferred | --option N
       | --part-answer N=ANSWER ... | --moved-on-no-decision | --not-asked KIND|none
       | --already-decided USER_RULING | --now-over-later-already-decided
       | --moved-on REASON]
      --user-reply-as-typed REPLY    (every answer but --not-asked, --already-decided,
                                      --now-over-later-already-decided and --moved-on)
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py close
      [--hold-answer-until-new-item-answered]
  walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py approval-walk-waiting-item-cold-read-fast-read
      [--after-fixes-reread-only-when-facts-change]

The answer is an approval, A, unless a flag says otherwise: --obvious for AO,
--after-advisor for Aa, --disapproved for D, --deferred for Z, --option 2 or 3
for O2 or O3, which approve the item's "Option N" paragraph instead of its
recommendation. R, E and O decide nothing, so the program takes no flag for
them. --part-answer, given once for each part of an item that holds parts, as
in `--part-answer 1=A --part-answer 2=D`, gives that part its own answer, A, AO
or D. Z is not taken for a part, and a part number given twice is refused,
writing nothing. Three flags record an item the user is not shown, so that no
agent writes a deciding line by hand: --already-decided for an item an earlier
user-ruling decides as the item recommends, USER_RULING citing that ruling,
which adds the `#new` texts as A does; --now-over-later-already-decided, the
same with the now-over-later ruling as its citation; and --moved-on for an item the walk
leaves with no decision, REASON saying why, which changes nothing.
--moved-on-no-decision records that the user moved on from an
item that asks for no decision, such as a summary item: it needs no
`#case_against` line, runs no fast read, and close records the item as `<moved on, no
decision>`. It is refused, writing nothing, for an item that has a recommendation as
the short-answer hook reads it: text after its last "Recommendation:", outside
fenced or indented code and HTML comments, because that item asks for a decision.
It is refused too, writing nothing, when the item has no such recommendation but
does have one once a `<!--` inside an HTML tag opens no comment, as when the
`<!--` in an attribute, such as `<div title="<!--">`, hides the recommendation
from the short-answer hook's reading.

Every answer but --not-asked, --already-decided, --now-over-later-already-decided
and --moved-on, which record an item the user is not shown, needs --user-reply-as-typed, the user's reply
exactly as he typed it; check writes it, its whitespace runs squeezed to single
spaces, into the answer line right after the time of the answer, which check
writes in UTC marked Z, in the form `(YYYY-MM-DD HH:MMZ)`, as in ``in his words "`a
trivial - a bit longer doesn't matter.`"``, so that the minutes keep a
remark that rides with the answer. The reply, USER_RULING, REASON and the start
of each text in a status line are written as code spans, so that a
`#next_to_present` or `#approval_walk_paused` inside them is not read as the
walk's marker. A check without --user-reply-as-typed is refused, writing
nothing, and so is one that gives it with any of those four. A reply that is a
navigation word alone, next, N, continue or go, whatever its case and any
trailing period or exclamation mark, is refused for every answer but
--moved-on-no-decision, writing nothing: it approves nothing, and the
walk-me-through skill lets it advance only an item with no recommendation
outstanding.

The texts an answer adds are the item's lines that begin with the answer's
mark, `#new` or `#new_if_d`, as CHECK below describes them. A, AO, Aa, O2 and
O3 add the `#new` texts; D adds only the `#new_if_d` texts, the texts of the
alternative that D does instead of the item's recommendation. A line's mark
belongs to the whole item, not to a part, so answers to parts add the `#new`
texts when any part is A or AO, and the `#new_if_d` texts when any part is D.
An answer that adds no marked text gets no fast read, and its status line is
"no proposed text marked".

Every answer but O2, O3, --moved-on-no-decision, --already-decided and
--moved-on needs the item's
`#case_against` line, the first line of the item, outside fenced code, whose
first word after any list, quotation or emphasis marker is `#case_against`,
followed by a rating: none, weak, medium, strong or very strong. When the item
has that line, CHECK writes its rating into the answer line, whatever the
answer, as a hashtag right after the answer, as in
`approved #approved_obvious #case_against_weak`, so that one search finds every
rating beside its answer. When the item has no such line, CHECK refuses every
answer but those five, writing nothing. A
`#case_against` line that opens with no rating is refused for every answer,
those five included.

`--not-asked KIND` settles the item without the user, as kind KIND, 1 to 6, of
the walk-me-through skill's list of items that need no answer, after checking
what code can from the item's evidence lines, each opening with its marker:
`#not_asked_touches` lists the files the change edits or deletes;
`#not_asked_test` names the test that fails before a fix and passes after it;
`#not_asked_source` cites the ruling, merged code or command; `#not_asked_unused`
names a thing removed; `#not_asked_rename` gives the old name, then the new one,
separated by a space, each in backquotes when it holds a space itself, as in
#not_asked_rename `instruction guard` `instruction-file guard`; `#not_asked_glossary_term`
names each glossary term the change puts in, in backquotes when it holds a space;
`#not_asked_hashtag_marker` names each hashtag marker the change adds. Every kind needs a case against rated none or weak. Kind 1, text caught up,
needs touches, a source and a `#new` text; kind 2, a code fix, needs touches
and a test, and every touched file must exist except that test; kind 3, a
removal, needs touches, and each unused name must appear, by `git grep`, in no
file outside the touched ones and docs/walk/, or, with no unused line, every
touched file must be Markdown; kind 4, a rename, needs touches and a rename
line, the new name as the term of an entry, a line opening `- **<new name>**`
or, with an alias, `- **<new name> (aka <alias>)**`, in a `*-glossary.md` file,
and the old name in no file outside the touched ones and docs/walk/; kind 5,
carrying out a ruling, needs a source; kind 6, a glossary term put in or a
hashtag marker added, needs touches and a term or a marker line, every touched
file Markdown and not a `*-glossary.md` file, each term as the term of an entry
as for kind 4, and each marker, `#` then letters, digits, `_` or `-`, found
in no file but Markdown, in any letter case, either whole or as a part of it
that ends just before a `-` or ends with a `_` followed by no letter or digit,
so that no program reads it, by name or by a pattern such as
`#case_against_[a-z_]+`; for kinds 1 to 4
and 6 every touched file but a kind 2 test must exist. An unused or old name is searched for as written and,
when it has two or more words, with its words joined by hyphens, by underscores
and by nothing, a run of digits both kept with the letters before it and
split off as a word of its own; every
spelling ignores case and matches even inside a longer name, so `poem-list` is
also found in `poem_list_path`, `POEM_LIST` and `PoemList`, `sha256_of` in
`sha256_of_file`, and `reader` in `Reader` and `readers`. A
failed check is refused, writing nothing, with every problem listed; a `git
grep` that fails is a failure too. Otherwise CHECK fast-reads the `#new` texts as
for A, writes the line `<item>: settled without asking the user, not asked,
kind KIND #case_against_<rating> (...)`, and tells the agent to ask the advisor
and judge what code cannot before running CLOSE, which records the item as
`<accepted>`. The checks cannot tell a case against that names only cost from
another weak one, or a fix that matches its design from one that does not;
the agent judges those.

`--not-asked none` settles an item of none of those kinds, only when its
`#case_against` line rates the case against none or weak. It needs a touches line,
which may be empty for a change that touches no file, such as doing nothing;
an item without that line comes to the user. It refuses a touched file that is
not in the checkout. Rated none, it refuses a touched file the instruction-file
guard, .claude/guard-hooks/instruction-file-guard.py, protects, because an item
that adds words the user has not approved to such a file is shown to him.
Rated weak, it refuses only a touched Markdown file, a `.md` file, the guard
protects, because the user reviews the English agents follow and lets other code,
hooks included, settle; the agent judges what code cannot, that the case
against names only cost and that the change neither widens an agent's
permissions nor turns off a guard. The guard's own functions decide which files
it protects. The minutes write the answer as `not asked, case against none`,
or, rated weak, `not asked, case against weak, cost only`.

`--now-over-later-already-decided` is --already-decided with the citation
supplied by the program, NOW_OVER_LATER_USER_RULING_CITATION, the user-ruling
that he is always for building now when the agents recommend now over later;
what this docstring says of --already-decided holds for it. It is for an item whose
only choice is whether to build something now or later and which recommends
now, and APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ, below, says so in the
line that tells the agent to present the item. Before it writes anything, it
refuses an item that holds a `Part N.` paragraph, as the walk-me-through
UserPromptSubmit hook's part_starts finds one, a line opening `Option N`, or
a `#new_if_d` mark, since each of those is a choice the user makes, and
lists each such line by its line number in the walk-document.

The open approval-walk and its waiting items are found with
walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py,
beside this program and loaded by path, the module the walk-me-through Stop
hook uses too, so the
`#next_to_present` line and the walk-document's item headings are read exactly
as that hook reads them. When the checkout's docs/walk/ holds more than one
approval-walk that is open or paused, every step refuses, writing nothing,
names each one's walk-minutes and says which to close and how to merge them,
since an agent-seat keeps at most one approval-walk open.

CHECK finds the texts the answer adds: the item's lines whose first word,
after any list or quotation marker, outside fenced code, is a mark the answer adds;
the text is the rest of the line, without one pair of surrounding quotation
marks. Before it reads them, CHECK refuses, writing nothing, for every answer but
--deferred, --moved-on-no-decision and --moved-on, which add no text, when
any `#new` or `#new_if_d` line of the item has no text after its mark,
is inside fenced or indented code, has text cut from its own line as an HTML
comment, even one inside a code span, or opens a paragraph that runs onto the
lines right below it, since those texts would miss their fast read; the
refusal lists each such mark by its line number, gives the text joined into
one line where it can find it, from the run-on lines, from the rest of the
code block, or, for a mark with no text, from the lines running on right below
it or else the one fenced block or quotation after the blank lines below it,
and says how to rerun. A mark in an HTML comment is not refused, since the user
is not shown it. For each text it looks for a cold-read-record of this walk, one
whose name starts with the walk's name and a hyphen as every fast read this
program runs is named, holding a fast read's report and a file under target/
that contains the text, whitespace aside, in the checkout's cold-read-records/
and in the log-store's. Other records are not opened: the log-store holds
thousands, and a text fast-read outside this program is read again. The log-store's
cold-read-records directory is the path in cold-read-record-ship.py's
LOG_STORE_RECORDS_DESTINATION, read on ned-box as it is and on the Mac through
the Mac's mount of ned-box's home. For each text with none, it saves the text to
a scratch file and runs cold-read-fast-read.py --target on that file; the
scratch file's directory is removed when the fast read ends, whatever ends it,
SIGTERM and SIGHUP included, since the cold-read-record keeps its own copy. Then it
writes the answer line, which names each part's answer in part number order
when --part-answer is given, and one status line per text, naming its mark and
its number, from 1 in the walk-document's order, among the item's texts with
that mark, or "no proposed text
marked", into the walk-minutes, and prints the status lines, the judgement the
agent must make on new reports, and the close step to run. It appends one line
of counts to
walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv
beside the log-store's cold-read-records directory. A deferral and a move on
change nothing, so CHECK --deferred, CHECK --moved-on-no-decision and CHECK
--moved-on run no fast read, log no counts, and write only the answer line. When the `#next_to_present` line names more than
one item, CHECK refuses, writing nothing, because a run would record its one
answer, or its one set of part answers, for every item that line names; CHECK
then tells the agent to add a `#next_to_present` line naming one of those items
before each check run.

A fast read that prints a line opening FAILED, or exits nonzero, ends CHECK
before the walk-minutes are written: the program prints that line, or a FAILED
line of its own, then says the item stays waiting and tells the agent to ask
the user whether to run check again, and exits 1. The one exception is a fast
read that names its report on stdout and exits 1 because its record did not
reach the log-store, which its stderr says in a `record: FAILED` or
`record: REFUSED` line: its report is used like any other. A fast read whose
report is used but says on stderr that its record was not
shipped, or that its target changed during the read, has that line added to its
status line. An unshipped record, a log-store this machine cannot reach, and a
counts line that cannot be written are each printed after the rest, saying the
minutes record the answer, with exit 2; a changed target alone leaves the exit
code 0, since the report was written.

CLOSE reads the last answer line CHECK wrote. When the `#next_to_present` line
still names that line's items, it records the answer: that it took effect, or,
for answers to parts, a single line for the item naming each part's outcome,
or, for --moved-on-no-decision, that the user moved on from an item asking
no decision, or, for a deferral, that the item moves to just before the summary item, the item
whose heading's point opens with "summary"; an item deferred a second time
leaves the walk and stays open; for --already-decided or --moved-on, that the
walk does not come back to the item, with the ruling or the reason. For a
deferral it also puts `(deferred: moved to just before the summary item)` right
after the running count of the item's walk-document heading, before it writes
the minutes, so the heading says why the item comes late; in a walk with no
summary item a deferred item goes to the end and gets no note. CLOSE takes the
note out again when it records any other answer to the item, or a second
deferral, which drops the item from the walk. On a first deferral, CLOSE
leaves the heading as it is when it holds the note already, or when it names more items
than the deferred ones, such as `Items 3 to 5 of 9`; for the second, CLOSE
prints that it gave the heading no note. It then writes a `#next_to_present` line as the
minutes' last line, naming the next item: walking the walk-document's items in
order, unnumbered items included, a once-deferred item placed just before the
summary item, from the item after the answered one, and round again from the
first, the first item the minutes do not record; `none, closed` when there is
none. The minutes record an item with sub-steps, such as 3 with 3.1 and 3.2,
once they decide every one of its sub-steps, unless its own answer is held
and no line decides it yet. The summary item is the one whose heading's point, after its running
count, or its whole title when it has no number, opens with "summary". When
the next item is unnumbered, a `## <title>` heading as the walk finder reads
one, CLOSE first writes its running count into that heading, `## Item K of M:
<title>`, K one more than the highest whole number any item heading holds and
M the walk finder's count of the items shown and waiting, and names it with
the same K and M. The line naming the next item gives that counted M,
whatever M the walk-document's headings give.

RULING GIVEN. Once CLOSE has written the minutes for an answer that is not
held, it lists the open pull requests with `gh pr list`, run in the checkout,
and, for each answered item and each item whose held answer it decides with
it, posts on every pull request with a review holding the line
`#held_on_ruling <walk name> item <number>` the comment `#ruling_given <walk
name> item <number> <word>`, naming the same walk and item, so that a pull
request held on two items gets a comment for each that tells them apart. An
item the answer decides through its last sub-step gets a comment too, its word
its sub-steps' one word, moved_on ones left out, or part_answers when they
differ.
The walk name is the walk-minutes' file name without `-minutes.md`; a
review line matches only when, whitespace at its ends aside, it is that line
exactly. The word is `approved` for an answer recorded `<accepted>`, an
option, an already-decided item and an item settled without asking included;
`disapproved` for one recorded `<rejected>`; `deferred` for a deferral, a
second one included; `moved_on` for either move on; and `part_answers` for
answers to parts. merge-lane-2's pull request intake reads the comment. Each gh
call is stopped after GH_TIMEOUT_SECONDS. When the list cannot be had, or a
comment cannot be posted, the minutes stay as written: CLOSE prints, after the
rest, what failed and the gh command to run by hand, and exits 2. A held answer
gets no comment, since it records no ruling yet.

WALK ORDER. The unnumbered items, the summary item left out, are the items
not yet shown, and only they are sorted; a numbered item keeps its number and
its place. They come together, where the first of them comes on the round
above, or just before the summary item or a once-deferred item when one of
those comes sooner, in this order: an item after every item it waits on;
otherwise by category, the four of section 2 of
docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md
in the order WALK_CATEGORIES gives them, then by the day the item first
entered an approval-walk, then in walk-document order; an item waited on takes
the place the item waiting on it would take, when that is earlier. Any item
waiting on an item still to come, a deferred one included, is passed over.
Each such item gives its category on a line opening with
`#approval_walk_item_in_category_<category>`, each item it waits on on a line
`#approval_walk_item_waits_on <that item's heading title>`, the title after any
running count, in any case, and its day on a line
`#approval_walk_item_first_entered YYYY-MM-DD`, which CLOSE and the
APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ step write right under the
heading, with today's date, into each such item that has none. Both steps
refuse, writing nothing, when such an item has no category tag on a line that
opens with one, more than one, or one not in WALK_CATEGORIES; a waits-on title
no other item heading has; a first-entered date not written YYYY-MM-DD; or
when such items wait on each other in a circle. Only a line CLOSE
writes records anything: a line for an answer that took effect, for answers to
parts, for --moved-on-no-decision, for --already-decided or for --moved-on
decides its items; a line for a
deferral defers its items once. Every other line records nothing, whatever it
says, an agent's note included, so that a note such as `Items 3 to 5 revised
(item 3 is the change he approved today)` leaves items 3 to 5 waiting; CHECK's
answer lines and CLOSE's held-answer lines record nothing either.
CLOSE refuses, writing nothing, when a line after the
last answer line already opens with the last answer line's item and a colon, as
every line close writes for an answer does: that answer was closed already, and
no check has run since. When the `#next_to_present` line names other items than
the answer line, a new item a finding raised is waiting: the answer is recorded
as held until the user answers the new item, and the `#next_to_present` line is
written again, unchanged, as the minutes' last line. With
--hold-answer-until-new-item-answered, CLOSE first numbers the unnumbered item
right after the answered item's heading, as it numbers the next item, and
holds the answer for it the same way, its `#next_to_present` line naming it;
when the heading right after is not an unnumbered item's, or there is none,
or when that item waits on an item still to come, an unshown one, the summary
item or a numbered item the minutes do not decide, CLOSE refuses, writing
nothing. When CLOSE later records
the new item approved, disapproved or already decided, it also writes the
already-decided line, with the same outcome, for each item a held-answer line
holds for it that no close line decides yet; after a deferral, a move on or
answers to parts, the held item stays waiting, so the walk comes back to it.
Either way it prints the lines the agent's next message must include, the
status lines among them, and, when an item waits, the command that gives that
item its cold-read-fast-read before it is presented.

READ AHEAD. When CLOSE names a next item, it also starts the cold-read-fast-read
of the item the walk would present after that one, found as CLOSE finds the
next item, with the next item counted as decided, in a detached process of its
own session that close does not wait for; and it tells the agent to run
APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ, below, before presenting the
next item. That step starts the same read ahead, so a retried step or a
successor agent-session starts it too; a text whose read was started or written
before, whatever its outcome, is not read ahead again, so a failed read ahead is
never retried. The read ahead is a guess: when the walk presents another item
next, or the item's text changes before it is shown, the read is only left
unused; when it cannot be started, for example because the walk-document has two
headings for that item, close and the step print one line saying so and why,
and go on. The last item has no item after it, so no read ahead
starts while it is shown, and a close that writes `none, closed` starts none.
CLOSE names item 1 only when the walk comes round to it again, so no read ahead
covers item 1's first showing: the walk-me-through skill's cold-read-fast-read
of the whole walk before item 1 covers it. Item 2's read is run by the step after item 1's close,
since no read ahead was started while item 1 was shown.

APPROVAL-WALK-WAITING-ITEM-COLD-READ-FAST-READ gives the item the
`#next_to_present` line names its cold-read-fast-read, as its text stands: the
item's lines in the walk-document, heading and fenced code included, keyed by
the sha256 of that text unchanged, whitespace included. It first refuses,
as CHECK does and before it starts any read, an item with a `#new` or
`#new_if_d` mark whose text would not be read whole; then it refuses, also
before any read, an item whose text up to its first `###` sub-step, or one of
whose `###` sub-steps, holds more than 300 words, counting every run of
characters between spaces that holds a letter or a digit, on every line but
those opening `#approval_walk_item_`. When the line names one item that has
numbered sub-steps, such as `### Item 3.1 of 9`, the walk-minutes do not all
decide, the step then adds a `#next_to_present` line naming the first of them
instead, since the user is shown such an item one sub-step at a time, and
reads that sub-step as this paragraph says. A read of that key
that wrote its report is used, a read ahead included; one a read-ahead worker
still runs is waited for, for as long as the worker's process lives, since the
fast read ends its own run with timeouts of its own; otherwise the step runs the
read itself, saying why when a read ahead of the same text failed or its worker
ended without writing its outcome. A read ahead that fails, or never ends, so
costs at most the wait for one more read, and never lets the item be shown
unread. A read the step runs itself that fails prints its FAILED line, says not
to present the item yet and how to run the step again, and exits 1.

With --after-fixes-reread-only-when-facts-change, which the agent gives after
applying a read's findings to the item, a text with no read of its own is
compared with the text of the item's latest read that wrote its report. When
the change touches no fact, the step runs no read and says so; otherwise it
reads the item, listing the facts touched. The words of the two texts are
matched by difflib, and a word changed, added or removed is a fact when it holds
a digit or a backquote; is a Markdown link or holds an autolink or `://`;
ends in a file extension, a dot then a letter and at most four more letters or
digits, unless it is a letter abbreviation such as `e.g.`; or, without the
punctuation around it and a trailing `/`, is a path `git ls-files` lists in the
checkout, a directory holding one, or the file name of one. The change also
touches a fact when the text from "Recommendation:" or "The alternative:" to the
end of its line, or a `#case_against` line, differs. When `git ls-files` fails,
every changed word counts as a fact, so the item is read. Since the comparison
is always with the latest text read, wording fixes each let pass cannot add up
to a changed fact unread.

Before it reads, the step keeps each earlier version of the item: each text of
the item that a read wrote its report for, oldest first, goes below the item's
live version, after the versions kept there already and before the next item,
under `#### Withdrawn version <n> of item <N>`, n one more than the Withdrawn
headings there that name the item, and the step prints a line for each. A text
is the item's when it was read under the item's number, whatever M; a read
ahead of an unnumbered item is the item's once a read step uses it for the
item, as its text stands, and until then whatever number close expected to
give it, only when its title, the heading's text after the running count, is
the item's title and no other item's. A read outcome written before outcomes
said whether their number was expected counts as such a read ahead. A text is
kept from its first line that is not blank, its indentation and all, so an
indented code block stays code. A text is left out when, without its
heading line and with its whitespace runs squeezed, it is empty, is the live
version's text, or is already below the live version, as an agent may have
kept it by hand. So every text a fast read read, a text the agent then changed
to apply that read's findings included, stays in the walk-document, except a
read ahead no read step used whose item another item now shares a title with;
the walk finder reads an item only up to its first Withdrawn heading. An item
whose heading names other items too, or a `#next_to_present` line naming
several items, keeps none. When the copy `<key>.md` of a text read under the
item's number is missing, the step refuses, writing nothing and reading
nothing, and says where the read's cold-read-record keeps its own copy.

Each text read is kept in the directory
`docs/walk/<walk name>-item-cold-read-fast-read-review-status-per-text-hash/`,
beside the walk-minutes: `<key>.md` holds the text, the one an
--after-fixes-reread-only-when-facts-change step compares with;
`<key>-outcome.json` the read's outcome, done with its report and the fast
read's notes or failed with its FAILED line, with the item and the time it
ended; `<key>-started.json` the read-ahead worker's pid; and `<key>.log` the
worker's output. docs/walk/ is gitignored, and nc-systems/skills/walk-me-through/walk-files-ship.py ships
only the walk's own files, not this directory: each read's cold-read-record
keeps its own copy of the text read. The step
approval-walk-item-cold-read-fast-read-review-background-worker is that
detached read-ahead worker, which only close and the step above start.

No open approval-walk, or an item the walk-minutes or the walk-document do not
let the program find, is a failure: one line on stderr, exit 1.

Tool-messages-to-agent follow
docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import argparse
import collections
import contextlib
import datetime
import difflib
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY_TOP = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
FAST_READ_PROGRAM = REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-fast-read.py"
RECORD_SHIPPER_FILE = REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-record-ship.py"
RECORD_NAMES_FILE = REPOSITORY_TOP / "nc-systems" / "cold-read" / "cold-read-record-names-common.py"
PATH_CONSTANTS_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                       / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
COUNTS_LOG_FILE_NAME = "walk-me-through-answer-added-texts-cold-read-fast-read-already-done-or-had-to-run-counts-per-check.tsv"
RECORDS_DIRECTORY_NAME = "cold-read-records"
PROGRAM = "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close"

NEW_MARK, NEW_IF_D_MARK = "#new", "#new_if_d"
NEW_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*(#new(?:_if_d)?)\b[:\s]*(.*)$")
QUOTE_PAIRS = (('"', '"'), ("“", "”"), ("'", "'"))
FENCE_DELIMITER = re.compile(r"^\s*(?:>\s?)*\s*(?:`{3,}|~{3,})")
QUOTATION_LINE = re.compile(r"^\s*>")
QUOTATION_MARKERS = re.compile(r"^\s*(?:>\s?)*")
ANSWER_LINE = re.compile(r"^(?P<item>items? .+?): (?:the user answered|settled without asking the user,) "
                         r"(?P<answered>.+?)(?: #approved_(?:obvious|after_advisor))?(?: #case_against_[a-z_]+)? "
                         r"\([^)]*\)(?: in his words \".*\")?, which makes (?:its change\. Fast reads:|no change\.)$",
                         re.I)
MARKER_END = r"(?=[*_`]*(?:[:\s]|$))"
CASE_AGAINST_LINE = re.compile(rf"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_`]*#case_against{MARKER_END}[*_`]*[:\s]*(.*)$")
CASE_AGAINST_RATING = re.compile(r"(very strong|none|weak|medium|strong)\b", re.I)
CASE_AGAINST_HASHTAG = " #case_against_{rating}"
NOT_ASKED_RATINGS = ("none", "weak")
NOT_ASKED_KINDS = (1, 2, 3, 4, 5, 6)
NOT_ASKED_RATED_NONE = "none"
NOT_ASKED_RATED_WEAK = "weak"
NOT_ASKED_WEAK_COST_ONLY_LABEL = "case against weak, cost only"
INSTRUCTION_FILE_GUARD_FILE = REPOSITORY_TOP / ".claude" / "guard-hooks" / "instruction-file-guard.py"
OPTION_NUMBERS = (2, 3)
EVIDENCE_LINE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_`]*(#not_asked_(?:touches|test|source|unused|rename|glossary_term|hashtag_marker))"
                           rf"{MARKER_END}[*_`]*[:\s]*(.*)$")
TOUCHES, TEST, SOURCE, UNUSED, RENAME, GLOSSARY_TERM, ADDED_HASHTAG_MARKER = (
    f"#not_asked_{name}" for name in ("touches", "test", "source", "unused", "rename", "glossary_term", "hashtag_marker"))
HASHTAG_MARKER = re.compile(r"#[A-Za-z0-9_-]+")
NOT_MARKDOWN_FILES = ":(exclude)*.md"
GLOSSARY_FILES = "*-glossary.md"
STATUS_LINE_PREFIX = "- "
OBVIOUS_HASHTAG = " #approved_obvious"
AFTER_ADVISOR_HASHTAG = " #approved_after_advisor"
APPROVED, DISAPPROVED, DEFERRED, MOVED_ON = "approved", "disapproved", "deferred", "moved on, no decision"
ALREADY_DECIDED_PREFIX, MOVED_ON_PREFIX = "already decided by ", "moved on, no decision: "
NAVIGATION_WORD_ALONE = re.compile(r"^(?:next|n|continue|go)[.!]*$", re.I)
OUTCOMES = {APPROVED: "<accepted>", DISAPPROVED: "<rejected>"}
PART_WORDS = {"A": APPROVED, "AO": APPROVED + OBVIOUS_HASHTAG, "D": DISAPPROVED}
PART_ARGUMENT = re.compile(r"^(\d+)=(ao|a|d)$", re.I)
# ANSWER_LINE's `answered` loses a last part's hashtag, so close reads each part's word on its own.
PART_IN_ANSWER = re.compile(r"\bpart (\d+) ((?:dis)?approved)\b")
PART_ARGUMENT_PROBLEM = ("`{value}` is not a part's answer: give the part's number, `=`, then A, AO or D, as in "
                         "`1=A`; a part takes no Z, so a deferral is given to the whole item with --deferred")
PART_REPEATED = ("nothing written: --part-answer gives {parts} more than one answer.\n"
                 "Run check again giving each part's number once, with the letter the user gave that part.")

NO_PROPOSED_TEXT = "no proposed text marked"
STATUS_ALREADY_DONE = "`{mark}` text {number}, \"{excerpt}\": fast read already done ({record})."
STATUS_HAD_TO_BE_RUN = "`{mark}` text {number}, \"{excerpt}\": fast read had to be run ({record})."
STATUS_FAST_READ_NOTE = " The fast read also said: {note}"
# The fast read reports these on stderr after writing its report; an unshipped record also makes it exit 1.
FAST_READ_RECORD_NOT_SHIPPED_MARKERS = ("cold-read-fast-read: record: FAILED",
                                        "cold-read-fast-read: record: REFUSED")
FAST_READ_NOTE_MARKERS = FAST_READ_RECORD_NOT_SHIPPED_MARKERS + ("#cold_read_target_changed_during_run",)
HOLD_ANSWER_FLAG = "--hold-answer-until-new-item-answered"
CHECK_JUDGEMENT_LINES = (
    "Read the fast-read report of each text above whose status line says \"fast read had to be run\".",
    "If a finding holds and changes how a text is understood but not what the item decides, "
    "apply it to that text's marked line in the walk-document {document}.",
    "If a finding would change what the item decides, write that change as a new item right "
    "after {item} in the walk-document, headed `## <the point>` with no number, and give the close step below "
    "the flag `" + HOLD_ANSWER_FLAG + "`: it numbers the new item, holds {item}'s answer until the user answers "
    "it, and says when to present it.",
)
CHECK_CLOSE_LINE = "Then run `python3 {program} close --cwd {top}` and do what it prints."
COUNTS_NOT_LOGGED = (
    "The minutes record the answer, but the fast-read counts were not logged to {log}: {error}.",
    "Include this line in your next message to the user, and carry on as the lines above say.",
)
LOG_STORE_UNREACHABLE = ("this machine reaches the log-store at neither {paths}, so its cold-read-records were "
                         "not searched either")
RECORDS_NOT_SHIPPED = (
    "The minutes record the answer, but the fast read of `{mark}` text {number} did not ship its record: {note}",
    "The record stays at {record}; once ned-box can be reached, run `python3 {shipper} {record}`.",
    "If the line above says REFUSED, first rename {record} with a -2 suffix, or the next number not taken, "
    "and ship the renamed directory instead.",
    "Include these lines in your next message to the user, and carry on as the lines above say.",
)
FAST_READ_FAILED_LINES = (
    "The item stays waiting: the minutes do not record the answer.",
    "Tell the user the line above, and ask whether to run `python3 {program} check{flags}` again or "
    "answer the item another way.",
)
STOP_SIGNAL_SCRATCH_NOT_REMOVED_LINES = (
    "{program} check: a {signal} stopped this check step while a cold-read-fast-read was running, so the "
    "walk-minutes do not record the user's answer, and the scratch directory {directory}, which held the text "
    "sent to that cold-read-fast-read, could not be removed: {error}\n"
    "Run `chmod -R u+rwX {quoted_directory} && rm -rf {quoted_directory}`, because nothing else removes that "
    "directory, and the disk it is on can fill.\n"
    "Then run the same `python3 {quoted_program_path} check` command again, with the same answer, so that the "
    "walk-minutes record his answer.")
CHECK_MINUTES = ("{item}: the user answered {answered}{hashtag}{rating} ({date_and_time}){words}, which makes its change. "
                 "Fast reads:")
CHECK_NOT_ASKED_MINUTES = ("{item}: settled without asking the user, {answered}{rating} ({date_and_time}), which makes "
                           "its change. Fast reads:")
CHECK_DEFERRED_MINUTES = ("{item}: the user answered {answered}{rating} ({date_and_time}){words}, which makes no "
                          "change.")
USER_WORDS = ' in his words "{words}"'
CHECK_MOVED_ON_MINUTES = ("{item}: settled without asking the user, {answered}{rating} ({date_and_time}), which makes "
                          "no change.")
CLOSE_TOOK_EFFECT_MINUTES = "{item}: {answered}; every text the change adds has had a fast read. {outcome}"
CLOSE_PARTS_TOOK_EFFECT_MINUTES = "{item}: {parts}; every text the change adds has had a fast read."
CLOSE_DEFERRED_MINUTES = "{item}: deferred; it moves to just before the summary item. <open>"
# No fast-read clause in these two: the one-time conversion of older walk-minutes writes them too, with no fast read.
CLOSE_ALREADY_DECIDED_MINUTES = "{item}: already decided by {ruling}; the walk does not come back to it. {outcome}"
CLOSE_MOVED_ON_MINUTES = ("{item}: moved on, no decision: {reason}; the walk does not come back to it. "
                          "<moved on, no decision>")
CLOSE_MOVED_ON_NO_DECISION_MINUTES = "{item}: moved on; the item asked for no decision. <moved on, no decision>"
CLOSE_DEFERRED_AGAIN_MINUTES = "{item}: deferred a second time, so it leaves the walk and stays open. <open>"
MORE_THAN_ONE_UNCLOSED_APPROVAL_WALK = (
    "nothing written: more than one approval-walk is open or paused in {directory}, so this program cannot tell "
    "which approval-walk the user's answer belongs to, and records it in none. A paused approval-walk is one "
    "whose walk-minutes hold an `#approval_walk_paused` line after their last `#next_to_present` line. Their "
    "walk-minutes:\n"
    "{minutes}\n"
    "An agent-seat keeps at most one approval-walk open: a new subject that needs the user's rulings joins the open "
    "approval-walk as one item just after the item waiting for his answer, with sub-items when it needs them.\n"
    "For each of these approval-walks that has no item the user has yet to answer: add the line "
    "`#next_to_present none, closed` as the last line of its walk-minutes.\n"
    "If after that more than one of them still has items the user has yet to answer: keep the approval-walk whose "
    "item your last message to him showed; in its walk-document, move each other approval-walk's unanswered items "
    "into it as items of their own, just after the kept approval-walk's waiting item: first the items that block "
    "work, each prerequisite before the item it blocks; related items next to each other; and older items before "
    "newer ones; and renumber the items after it that he has not yet seen; then close each other approval-walk: add "
    "the line `#next_to_present none, closed` as the last line of its walk-minutes, and run "
    "`nc-systems/skills/walk-me-through/walk-files-ship.py <its name>`.\n"
    "Then run the command you just ran again.\n"
    "From now on, add a new subject that needs the user's rulings to the open approval-walk instead of opening a "
    "second one.")
CHECK_SEVERAL_WAITING = (
    "nothing written: the `#next_to_present` line in {minutes} names more than one item waiting, {item}, "
    "and one check run records one answer for all of them.\n"
    "For each of those items the user has answered, in the order he gave the answers: add the line "
    "`{one_item_line}`, with that item's number, as the minutes' last line, then run check with the flag for "
    "his answer to it, then close.\n"
    "Present the item that `close` names only after the last of those answers is recorded.\n"
    "If he has not answered some of those items, ask him to answer them.")
CLOSE_ALREADY_RECORDED = (
    "nothing written: the last answer line in {minutes}, for {item}, is already recorded by an earlier close, "
    "so no check has run since then.\n"
    "Run `python3 {program} check` first, with the flag for the user's answer as `--help` lists it, then close.\n"
    "If check failed, fix what it printed before running close.")
CLOSE_HELD_MINUTES = "{item}: answer held: {new_item}, raised by a fast-read finding, waits for the user's answer. <open>"
HELD_ANSWER_LINE = re.compile(r"^(items?\s[^:]*): answer held: (items?\s.+?), raised by a fast-read finding", re.I)
CLOSE_TOOK_EFFECT_LINES = (
    "{item}'s answer is recorded in the minutes, and its change may now be made.",
    "Your next message must include these lines, as they are:",
)
CLOSE_DEFERRED_LINES = (
    "{item} is deferred, and the minutes record it; it comes back just before the summary item.",
    "Your next message must include these lines, as they are:",
)
CLOSE_MOVED_ON_LINES = (
    "{item} asked for no decision, and the minutes record that the user moved on from it.",
)
CLOSE_DEFERRED_AGAIN_LINES = (
    "{item} is deferred a second time, so the minutes record it as open and it leaves the walk.",
    "Add it to your task list if it is not already a task.",
    "If a commit on your branch already makes the change this item asks about, undo that change in a new commit "
    "before the pull request, and say in the task that it was undone.",
    "Your next message must include these lines, as they are:",
)
CLOSE_HELD_LINES = (
    "{item}'s answer does not take effect yet: {new_item}, which a fast-read finding raised, waits for the "
    "user's answer, and the minutes record {item}'s answer as held until he answers {new_item}.",
    "Your next message must include these lines, as they are:",
)
CLOSE_TOOK_EFFECT_NEXT = (
    "If the change needs nothing more from the user, such as a text he has not yet seen, start it as the "
    "walk-me-through skill's sentence on ready work says; if it edits a file that work you dispatched "
    "earlier is still editing, start it when that earlier work finishes.",
)
CLOSE_NO_NEXT_ITEM = ("No item is left to present, and the minutes' `#next_to_present` line now reads "
                      "`none, closed`: go on to the walk-me-through skill's closing.")
NEXT_MARKER_LINE = "#next_to_present {value}"
CLOSED_MARKER_VALUE = "none, closed"
PROGRAM_LINE_ITEMS = re.compile(r"^(items?\s[^:]*): ", re.I)


def minutes_time(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _one_of(values):
    return "(?:" + "|".join(re.escape(str(value)) for value in values) + ")"


_PART_VALUE = r"part \d+ " + _one_of(f"{word} {outcome}" for word, outcome in OUTCOMES.items())
# The values close fills each placeholder with; {ruling} and {reason} carry the agent's own words, so any text.
PLACEHOLDER_VALUES = {
    "answered": _one_of([APPROVED, DISAPPROVED] + [f"{APPROVED} option {number}" for number in OPTION_NUMBERS]
                        + [f"not asked, kind {kind}" for kind in NOT_ASKED_KINDS]
                        + [f"not asked, case against {NOT_ASKED_RATED_NONE}",
                           f"not asked, {NOT_ASKED_WEAK_COST_ONLY_LABEL}"]),
    "outcome": _one_of(OUTCOMES.values()),
    "parts": rf"{_PART_VALUE}(?:, {_PART_VALUE})*",
    "ruling": ".+",
    "reason": ".+",
}


def after_the_items_pattern(template):
    """The part of a minutes line this program writes from template after `{item}: `, as a regular
    expression in which each other placeholder stands only for the values close fills it with."""
    # re.split with a group alternates literal text (even indexes) and placeholder names (odd indexes).
    return re.compile("^" + "".join(PLACEHOLDER_VALUES[piece] if index % 2 else re.escape(piece)
                                    for index, piece in enumerate(re.split(r"\{(\w+)\}",
                                                                           template[len("{item}: "):])))
                      + "$")


DECIDING_LINES = tuple(after_the_items_pattern(template) for template in (
    CLOSE_TOOK_EFFECT_MINUTES, CLOSE_PARTS_TOOK_EFFECT_MINUTES, CLOSE_ALREADY_DECIDED_MINUTES, CLOSE_MOVED_ON_MINUTES,
    CLOSE_MOVED_ON_NO_DECISION_MINUTES))
# The `#ruling_given` word of each of DECIDING_LINES; None where the line's outcome tag gives it.
DECIDING_LINE_WORDS = (None, "part_answers", None, "moved_on", "moved_on")
DEFERRING_LINES = tuple(after_the_items_pattern(template)
                        for template in (CLOSE_DEFERRED_MINUTES, CLOSE_DEFERRED_AGAIN_MINUTES))
# A one-item count as it stands in the heading's own line, after its heading or bold marks.
HEADING_COUNT_IN_LINE = re.compile(r"items?\s+\d+(?:\.\d+)*\s+of\s+\d+\b", re.I)
CLOSE_DEFERRED_HEADING_NOT_NOTED = ("Its heading in {document} names other items too, so it is not given the "
                                    "note {note}.")
SUMMARY_HEADING = re.compile(r"\bof\s+\d+\b[*_\s:.\-\u2013\u2014]*summary\b|^\s*##\s+[*_\s]*summary\b", re.I)
NEWLINE = "\n"
UNNUMBERED_HEADING_PARTS = re.compile(r"^(\s*##[ \t]+)(.*?)(?:[ \t]+#+)?[ \t]*$")
# The four categories of section 2 of
# docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md,
# in the order their items are shown.
WALK_CATEGORIES = ("must_fix_now", "fix_next", "fix_during_maintenance", "file_an_improvement_feature_or_change")
WALK_CATEGORY_TAG = "#approval_walk_item_in_category_"
WALK_WAITS_ON_TAG = "#approval_walk_item_waits_on"
WALK_FIRST_ENTERED_TAG = "#approval_walk_item_first_entered"
LINE_OPENING_MARKERS = r"^\s*(?:(?:[-*+]|\d+[.)]|>)\s+)*[*_`]*"
WALK_CATEGORY_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_CATEGORY_TAG))
# Words joined by single underscores, so the closing `_` or `__` of underscore emphasis is not read into the tag.
WALK_CATEGORY_TAGS_IN_LINE = re.compile(re.escape(WALK_CATEGORY_TAG) + r"(?:[^\W_]+(?:_[^\W_]+)*)?")
WALK_WAITS_ON_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_WAITS_ON_TAG) + MARKER_END
                                + r"[*_`]*[:\s]*(.*?)[*_`\s]*$")
WALK_FIRST_ENTERED_LINE = re.compile(LINE_OPENING_MARKERS + re.escape(WALK_FIRST_ENTERED_TAG) + MARKER_END
                                     + r"[*_`]*[:\s]*(.*?)[*_`\s]*$")
# A marked text ends above the first of these lines, because this program reads each on its own; a line opening
# with any other hashtag, such as a prose `#root_cause`, is part of the text.
MARKER_LINES_READ_ON_THEIR_OWN = (NEW_LINE, CASE_AGAINST_LINE, EVIDENCE_LINE, WALK_CATEGORY_LINE, WALK_WAITS_ON_LINE,
                                  WALK_FIRST_ENTERED_LINE)
WALK_ORDER_REFUSED = (
    "nothing written: {problem}\n"
    "Every item of the walk-document not yet shown to the user, headed `## <the point>` with no number, needs "
    "exactly one category line, so that this program can choose which of them he sees next: the items each "
    "waits on first, then by category, then by the day each first entered a walk, earlier first, then in "
    "walk-document order. "
    "The categories are the four of section 2 of "
    "docs/nedschorus-wiki/queue/nedschorus-goals-and-philosophy-founding-statement-and-agent-working-principles.md, "
    "shown in this order:\n"
    + "\n".join(f"  `{WALK_CATEGORY_TAG}{category}`" for category in WALK_CATEGORIES) + "\n"
    "If an item has no category line, more than one category tag, or a tag not in this list: leave it exactly one "
    "tag from this list, the one for how soon its work must happen, on a line of its own under its heading.\n"
    f"If an item must not be shown before another item: give it a line `{WALK_WAITS_ON_TAG} <the other item's "
    "title>`, the other item's heading without its `##` and any `Item N of M: `, one line for each item it waits "
    "on; an item already decided counts as done. If items wait on each other in a circle, take out the waits-on "
    "line that is not a real prerequisite.\n"
    "Then run `python3 {program} {step} --cwd {top}` again.\n"
    "From now on, write the category line, and a waits-on line for each item it waits on, into every item when you "
    "add it to a walk-document.")
CATEGORY_MISSING = "{item} has no `" + WALK_CATEGORY_TAG + "<category>` line."
CATEGORY_DOUBLED = "{item} has more than one category tag: {tags}."
CATEGORY_UNKNOWN = "{item} has the category tag `{tag}`, which is not one of the four categories."
WAITS_ON_UNKNOWN = "{item} waits on `{title}`, which is the title of no other item heading."
WAITS_ON_CIRCLE = "the items {items} wait on each other in a circle, so none of them can come first."
FIRST_ENTERED_UNREADABLE = (
    "{item} has the line `{line}`, whose date is not a date written YYYY-MM-DD. This program writes a line "
    f"`{WALK_FIRST_ENTERED_TAG} YYYY-MM-DD` on the day it first finds the item; write in it the day the item first "
    "entered an approval-walk, or delete the line, and this program writes today's date.")
NUMBERED_HEADING = "{marks}Item {number} of {total}: {title}"
NO_UNNUMBERED_ITEM_AFTER = (
    "nothing written: close was given " + HOLD_ANSWER_FLAG + ", but in {document} the heading right after "
    "{item}'s is {found}, not a new item's heading `## <the point>` with no number.\n"
    "If a fast-read finding would change what {item} decides, write that change as a new item right after "
    "{item}, headed `## <the point>`, then run close with " + HOLD_ANSWER_FLAG + " again.\n"
    "If no finding does, run close without " + HOLD_ANSWER_FLAG + ".")
HELD_NEW_ITEM_WAITS_ON_UNSHOWN = (
    "nothing written: close was given " + HOLD_ANSWER_FLAG + ", but in {document} the new item right after "
    "{item}, {new_item}, waits on {waited_on}, which the user has not ruled on yet. The new item is shown "
    "next, to settle {item}, so it cannot come after the item it waits on.\n"
    "Take the line `" + WALK_WAITS_ON_TAG + " <title>` that names {waited_on} out of {new_item}. If {new_item} "
    "depends on what {waited_on} would decide, add to {new_item} one sentence saying what {waited_on} proposes, "
    "as background, since the user rules on {new_item} first. "
    "Then run close with " + HOLD_ANSWER_FLAG + " again.")
GATHERING_WOULD_LOSE_AN_ITEM = (
    "walk-document not changed: close recorded the answer in {minutes}, but moving the items not yet shown "
    "together in {document} would have left fewer items than it found, so close wrote neither the walk-document "
    "nor a new `#next_to_present` line. This is a defect in this program.\n"
    "Tell the user this line, and send it to reboot-test with SendMessage, so that the program is fixed.\n"
    "Until then, show the user the next item yourself, and write its `#next_to_present` line into the minutes "
    "by hand.")
CLOSE_HELD_NEXT = ("Then run `{command}`, which gives {new_item} its cold-read-fast-read, do what it prints, and "
                   "present {new_item}. When the close step records the user's approval or disapproval of "
                   "{new_item}, it records the same outcome for {item}; after a deferral, a move on or answers to "
                   "parts, {item} stays waiting and the walk comes back to it.")
CLOSE_HELD_DECIDED = "{held}, whose answer was held for {item}, is recorded with {item}'s outcome."
HELD_RULING = "the user's answer to {new_item}, for which its answer was held"
CASE_AGAINST_MISSING = (
    "nothing written: {item} in {document} has no `#case_against` line, and every answer records the item's "
    "case-against rating beside it in the minutes, so the ratings can later be compared with the user's answers.\n"
    "Add one line to {item}, just before its recommendation, that opens with `#case_against` and your rating of "
    "its strongest case against, none, weak, medium, strong or very strong, as in "
    "`#case_against weak: the fix costs an hour of fast reads.` or `#case_against none.`; the rating is yours, so "
    "the user need not see the item again for it.\n"
    "Then run `python3 {program} check{flags}` again.\n"
    "From now on, write the `#case_against` line into each item before you show it.")
CASE_AGAINST_UNRATED = (
    "nothing written: the `#case_against` line of {item} in {document}, `{line}`, does not open with a rating, "
    "so no rating can be recorded beside the answer.\n"
    "Change that line so that `#case_against` is followed by one of none, weak, medium, strong or very strong, "
    "as in `#case_against weak: the fix costs an hour of fast reads.`, then run `python3 {program} check{flags}` "
    "again.")
USER_WORDS_MISSING = (
    "nothing written: check was given no --user-reply-as-typed, so the walk-minutes would record the answer "
    "without the reply it came from, and the walk-me-through skill records the user's own words beside the answer "
    "they count as.\n"
    "Run `python3 {program} check{flags} --user-reply-as-typed <his reply>` with the user's reply exactly as he "
    "typed it, quoted for the shell, as in `--user-reply-as-typed 'a but trivial'`.")
USER_WORDS_NOT_ASKED = (
    "nothing written: --user-reply-as-typed was given with {flag}, but an item settled without asking the "
    "user has no reply of his to record.\n"
    "If the user did answer the item, run check with the flag for his answer instead of {flag}.\n"
    "Otherwise run check again without --user-reply-as-typed.")
NAVIGATION_WORD_REFUSED = (
    "nothing written: the user's reply \"{words}\" is a navigation word alone, which does not approve, disapprove "
    "or defer {item}, so check does not record it as {answered}.\n"
    "If {item} ends with a recommendation, ask the user to answer it with A, AO, Aa, D or Z, because the "
    "walk-me-through skill lets a navigation word alone advance only when no recommendation is outstanding.\n"
    "If {item} asks for no decision, such as a summary item, run `python3 {program} check --moved-on-no-decision "
    "--user-reply-as-typed {quoted_words}`, then close.")
MOVED_ON_NO_DECISION_REFUSED = (
    "nothing written: {item} recommends \"{recommendation}\", so it asks for a decision, and --moved-on-no-decision "
    "records only a move on from an item that asks for none.\n"
    "If the user's reply already answers {item}, do not ask him again: run check with the flag for his answer, "
    "as below.\n"
    "If it does not, ask him to answer {item}, because the walk-me-through skill lets the walk move on from an "
    "item only once its recommendation is answered.\n"
    "The check command for each answer, with REPLY replaced by his reply as he typed it:\n{commands}")
MOVED_ON_NO_DECISION_HIDDEN_RECOMMENDATION = (
    "nothing written: {item} in the walk-document {document} shows no recommendation as this program cuts HTML "
    "comments, but recommends \"{recommendation}\" once a `<!--` inside an HTML tag opens no comment, as when the "
    "`<!--` in an attribute, such as `<div title=\"<!--\">`, hides the text after it. So check "
    "cannot tell whether {item} asks for a decision.\n"
    "If the user is meant to see that recommendation: rewrite each `<!--` in {item} that opens no comment, such as "
    "one in an attribute, as `&lt;!--`, then ask him to answer {item}, because the walk-me-through skill lets "
    "the walk move on from an item only once its recommendation is answered.\n"
    "If the recommendation is a hidden note: put it inside a comment that opens with `<!--` outside any tag and "
    "closes with `-->`, then run `python3 {program} check --moved-on-no-decision --user-reply-as-typed {quoted_words}` "
    "again.")
MOVED_ON_NO_DECISION_ANSWER_COMMANDS = (
    ("A", ""), ("AO", " --obvious"), ("Aa", " --after-advisor"), ("D", " --disapproved"), ("Z", " --deferred"))
MOVED_ON_NO_DECISION_OPTION_LINE = ("O{number}, for an item with an \"Option {number}\" paragraph: python3 {program} check "
                                    "--option {number} --user-reply-as-typed REPLY")
MOVED_ON_NO_DECISION_PART_LINE = ("An answer to each part of an item with parts, one flag per part: python3 {program} "
                                  "check --part-answer 1=A --part-answer 2=D --user-reply-as-typed REPLY")
UNREADABLE_NEW_MARKS = (
    "nothing written: {item} in the walk-document {document} has `#new` or `#new_if_d` marks whose text this "
    "program would not read whole, so an answer that adds such a text would be recorded without that text's "
    "cold-read-fast-read. This program reads a mark's text only from the rest of the mark's own line, outside "
    "fenced or indented code. The marks:\n{problems}\n"
    "Fix the marks from the last listed to the first, so that the line numbers above stay right.\n"
    "For a mark inside fenced or indented code that marks a text an answer adds: delete it, and any lines of its "
    "text, from the code, and write on a line of its own just after the code the line its entry gives after "
    "\"joined onto it:\", or the mark followed by the text you meant.\n"
    "For a mark inside fenced or indented code that is only an example: rewrite that line of the code so that it "
    "does not open with the mark, as in `Example: #new \"<text>\"`.\n"
    "For a mark whose text runs onto the lines below it: write the line its entry gives after \"joined onto it:\" "
    "in place of the mark's line, or the mark followed by the text you meant, and delete the lines its text ran "
    "onto.\n"
    "For a mark whose line holds `<!--`: move any HTML comment on that line to a line of its own, and if the "
    "mark's text holds `<!--`, write it there in words, as in `an HTML comment opening`.\n"
    "For a mark with no text after it: if a text was meant, write it after the mark, on the mark's line, and "
    "delete any lines below that held it; if none was meant, delete the mark.\n"
    "Then run `{command}` again.\n"
    "From now on, write every `#new` or `#new_if_d` text on one line, after its mark, outside fenced or indented "
    "code.")
UNREADABLE_BARE = "- line {line}: `{mark}` has no text after it on its line."
UNREADABLE_FENCED = "- line {line}: `{mark}` is inside fenced or indented code, where no mark's text is read."
UNREADABLE_RUN_ON = "- line {line}: the text of `{mark}` runs onto {below} right below it, where it is not read."
UNREADABLE_COMMENT_CUT = ("- line {line}: the line of `{mark}` holds `<!--`, so this program cuts text from it as an "
                          "HTML comment, even inside a code span, and would not read the line as written.")
UNREADABLE_JOINED = " The mark's line with its text joined onto it: {mark} {text}"
NOT_ASKED_REFUSED = (
    "nothing written: {item} cannot be settled without asking the user as {label}, because:\n{problems}\n"
    "If the item does not fit {label}, or the case against is more than cost, present {item} to the user as "
    "usual, then run check with the flag for his answer, as `--help` lists it.\n"
    "If the item fits and only its evidence lines are missing or wrong, fix them in {document} and run "
    "`python3 {program} check --not-asked {kind}` again.")
NOT_ASKED_RATING_PROBLEM = ("- its `#case_against` line rates the case against {rating}; only an item rated none, "
                            "or weak with a case against that names only cost, settles without the user.")
NOT_ASKED_NO_LINE_PROBLEM = "- it has no `{marker}` line; {why}"
NOT_ASKED_KINDS_NAMED = "none of the kinds 1 to 6 that `--help` lists under `--not-asked`"
NOT_ASKED_NOT_RATED_NONE_PROBLEM = ("- its `#case_against` line rates the case against {rating}; an item of "
                                    + NOT_ASKED_KINDS_NAMED + " settles without the user only when its case "
                                    "against is rated none, or weak with a case against that names only cost.")
NOT_ASKED_WEAK_GUARDED_MARKDOWN_PROBLEM = (
    "- `{marker}` names {path}, a Markdown file the instruction-file guard protects; this item is of "
    + NOT_ASKED_KINDS_NAMED + " and rated weak, and it changes such a file, so it is shown to the user.")
NOT_ASKED_GUARDED_FILE_PROBLEM = ("- `{marker}` names {path}, which the instruction-file guard protects; an item "
                                  "that adds words the user has not approved to such a file is shown to him, and "
                                  "one whose words a ruling of his gives settles as kind 1.")
NOT_ASKED_MISSING_PATH_PROBLEM = "- `{marker}` names {path}, which is not in the checkout {top}."
NOT_ASKED_NEW_FILE_PROBLEM = ("- `{marker}` names {path}, which is not in the checkout {top}; a code fix that "
                              "settles without the user adds no file but a test.")
NOT_ASKED_NOT_A_TEST_PROBLEM = "- `{marker}` names {path}, which is not a test file in the checkout {top}."
NOT_ASKED_NO_NEW_TEXT_PROBLEM = "- it has no `#new` line holding the changed text."
NOT_ASKED_STILL_USED_PROBLEM = ("- `{word}`, named on its `{marker}` line, is still named in {files}, which "
                                "its `{touches}` line does not list.")
NOT_ASKED_NOT_MARKDOWN_PROBLEM = ("- it has no `{marker}` line, and `{touches}` names {paths}, which are not "
                                  "Markdown standing instructions; name each thing removed on a `{marker}` line.")
NOT_ASKED_RENAME_SHAPE_PROBLEM = ("- its `{marker}` line `{value}` does not give the old name, then the new name, "
                                  "each in backquotes when it holds a space.")
NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM = ("- the new name `{new}` is the term of no entry, a line opening `- **{new}**` "
                                     "or `- **{new} (aka ...)**`, in a glossary file ({pattern}) in the checkout.")
NOT_ASKED_NO_TERM_OR_MARKER_PROBLEM = ("- it has neither a `{term}` line nor a `{marker}` line; name on a `{term}` line "
                                       "each glossary term the change puts in, and on a `{marker}` line each hashtag "
                                       "marker it adds.")
NOT_ASKED_GLOSSARY_OR_NOT_MARKDOWN_PROBLEM = (
    "- `{touches}` names {path}, which is not Markdown prose outside a glossary; kind 6 changes no code and no "
    "glossary, because a glossary entry decides what a term means.")
NOT_ASKED_TERM_NOT_IN_GLOSSARY_PROBLEM = ("- the term `{term}` is the term of no entry, a line opening `- **{term}**` "
                                          "or `- **{term} (aka ...)**`, in a glossary file ({pattern}) in the "
                                          "checkout.")
NOT_ASKED_MARKER_SHAPE_PROBLEM = ("- `{value}` on its `{marker}` line is not a hashtag marker, `#` then letters, "
                                  "digits, `_` or `-`.")
NOT_ASKED_MARKER_READ_PROBLEM = ("- the marker `{value}` is in {files}, which are not Markdown; a marker a program, "
                                 "a test or a setting reads changes what the program does, so the user sees it.")
NOT_ASKED_WHY = {
    TOUCHES: "list on it every file the change edits or deletes, separated by spaces.",
    TEST: "name on it the test that fails before the fix and passes after it.",
    SOURCE: "cite on it the ruling, the merged code or the command that shows the fact.",
    RENAME: "give on it the old name, then the new name, each in backquotes when it holds a space.",
}
NOT_ASKED_JUDGEMENT_LINES = (
    "{item} is recorded as settled without asking the user, {label}; the program checked only what code can.",
    "Before you run close, ask the advisor whether a later ruling or another open item overtakes {item}, and judge "
    "what the program could not, such as whether the case against names only cost and whether a fix matches its "
    "design.",
    "If the advisor objects, the advisor call fails, or your judgement is against settling, do not run close: "
    "present {item} to the user and run check with the flag for his answer, as `--help` lists it; that writes a new "
    "answer line, and close records only the last one, so this line is then set aside.",
)
# Code cannot see these in a change, so an item of no kind rated weak leaves them to the agent.
NOT_ASKED_WEAK_JUDGEMENT_LINE = (
    "{item} is of " + NOT_ASKED_KINDS_NAMED + " and its case against is rated weak: if its change "
    "widens an agent's permissions, as a settings change can, or turns off a guard, do not run close: present {item} to the user.")
GIT_GREP_FAILED = ("`git grep` failed with exit {code} in {top} while checking {item}'s evidence: {error}\n"
                   "Run `python3 {program} check --not-asked {kind}` again once; if it fails the same way, "
                   "present {item} to the user and run check with the flag for his answer, as `--help` lists it.")
CLOSE_NOT_SHOWN_LINES = (
    "{item} is recorded in the minutes as settled without being shown to the user.",
    "List it, with its number, in one line of your next message to the user.",
)
CLOSE_ALREADY_DECIDED_CHANGE = "Its change may now be made; the fast reads of the texts it adds:"
# Both line formats are agreed with merge-lane-2, whose hold command writes the first into its review and whose
# pull request intake reads the second; change neither without changing those programs.
HELD_ON_RULING_LINE = "#held_on_ruling {walk} item {number}"
RULING_GIVEN_LINE = "#ruling_given {walk} item {number} {word}"
RULING_GIVEN_WORDS = {OUTCOMES[APPROVED]: APPROVED, OUTCOMES[DISAPPROVED]: DISAPPROVED}
RULING_GIVEN_DEFERRED, RULING_GIVEN_MOVED_ON, RULING_GIVEN_PART_ANSWERS = "deferred", "moved_on", "part_answers"
GH_PROGRAM = "gh"
GH_TIMEOUT_SECONDS = 60
HELD_PULL_REQUESTS_LIST = ("pr", "list", "--state", "open", "--limit", "1000", "--json", "number,reviews")
HELD_PULL_REQUESTS_BY_HAND_JQ = ('.[] | select(any(.reviews[].body | split("\\n")[] | gsub("^\\\\s+|\\\\s+$"; ""); '
                                 '. == {line})) | .number')
RULING_GIVEN_POSTED = "The ruling on item {number} is posted as `{ruling}` on pull request {pull_request}, held on it."
RULING_GIVEN_LOOKUP_FAILED = (
    "The minutes record the answer to item {number}, but the open pull requests merge-lane-2 holds until that item "
    "is answered could not be looked up, so none of them carries the ruling: `gh pr list` {error}.",
    "Run `{list_command}` once; for each pull request number it prints, run `{comment_command}` with that number in "
    "place of <number>, because merge-lane-2 releases or answers a hold only when it reads that comment.",
    "If that fails too, tell the user: \"merge-lane-2 was not told that item {number} of {walk} is {word}, so the "
    "pull requests held until that ruling stay held; gh failed.\" A subagent passes this to the agent that "
    "dispatched it.",
)
RULING_GIVEN_POST_FAILED = (
    "The minutes record the answer to item {number}, but pull request {pull_request}, which merge-lane-2 holds until "
    "that item is answered, did not get the ruling's comment: `gh pr comment` {error}.",
    "Run `{comment_command}` once, because merge-lane-2 releases or answers the hold only when it reads that comment.",
    "If that fails too, tell the user: \"merge-lane-2 was not told that item {number} of {walk} is {word}, so pull "
    "request {pull_request} stays held; gh failed.\" A subagent passes this to the agent that dispatched it.",
)

WAITING_ITEM_READ_STEP = "approval-walk-waiting-item-cold-read-fast-read"
READ_AHEAD_WORKER_STEP = "approval-walk-item-cold-read-fast-read-review-background-worker"
AFTER_FIXES_FLAG = "--after-fixes-reread-only-when-facts-change"
ITEM_READS_DIRECTORY_SUFFIX = "-item-cold-read-fast-read-review-status-per-text-hash"
READ_DONE, READ_FAILED = "done", "failed"
READ_POLL_SECONDS = 2
FACT_LABELS = ("Recommendation:", "The alternative:")
# Spelled as the short-answer hook's RECOMMENDATION, so the two programs agree on which items hold a recommendation.
AUTOLINK = r"<[A-Za-z][A-Za-z0-9+.-]*:[^>\s]*>"
# A backquoted span, a Markdown link, an autolink, or any other run of non-space characters.
FACT_TOKEN = re.compile(r"`[^`\n]+`|!?\[[^\]\n]*\]\([^)\s]*\)|" + AUTOLINK + r"|\S+")
FILE_EXTENSION_END = re.compile(r"\w\.[A-Za-z][A-Za-z0-9]{0,4}$")
LETTER_ABBREVIATION = re.compile(r"(?:[A-Za-z]\.)+[A-Za-z]?")
TOKEN_EDGE_PUNCTUATION = "\"'“”‘’()[]{}<>*_.,;:!?"
FACTS_LISTED = 8
READ_STEP_COMMAND = "python3 {program} " + WAITING_ITEM_READ_STEP + "{flags} --cwd {top}"
CLOSE_READ_NEXT_ITEM = ("Then run `{command}`, which gives {next_item}, the item the minutes' `#next_to_present` "
                        "line now names, its cold-read-fast-read, and do what it prints before you present it.")
ITEM_READ_USED = "{item}: its cold-read-fast-read, of its text as it stands, {how}: {report}{notes}"
ITEM_READ_HOW_AHEAD = "was read ahead while the item before it was shown"
ITEM_READ_HOW_ALREADY = "was done earlier"
ITEM_READ_HOW_RUN = "had to be run now{why}"
ITEM_READ_RUN_AHEAD_FAILED = ", because the read started ahead of it failed: {line}"
ITEM_READ_RUN_AHEAD_ENDED = (", because the read started ahead of it ended without writing its outcome; its output "
                             "is in {log}")
ITEM_READ_RUN_FACTS = ", because your changes since its last cold-read-fast-read ({report}) touch {facts}"
ITEM_READ_NOT_RUN = ("{item}: no new cold-read-fast-read: your changes since its last one ({report}) touch no "
                     "number, path, file or program name, link, or line holding \"Recommendation:\", "
                     "\"The alternative:\" or `#case_against`.")
NOW_OVER_LATER_FLAG = "--now-over-later-already-decided"
NOW_OVER_LATER_USER_RULING_CITATION = (
    "the user-ruling at line 361 of nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/"
    "walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md, given with his answer to item 42 on "
    "2026-11-09: \"If the agents recommend now versus later, I'm always for now.\"")
OPTION_LINE = re.compile(LINE_OPENING_MARKERS + r"Option\s+\d")
NOW_OVER_LATER_REFUSED = (
    "nothing written: {item} in {document} was not recorded as already decided by the user-ruling that he is "
    "always for building now when the agents recommend now over later, because that user-ruling settles only an "
    "item whose one choice is now or later, and {item} holds other choices:\n{problems}\n"
    "Present {item} to the user, then run check with the flag for his answer, as `--help` lists it.")
NOW_OVER_LATER_PARTS = "- a `Part N.` paragraph, each part answered on its own, on line {lines}"
NOW_OVER_LATER_OPTIONS = "- a line opening `Option N`, another option he can pick, on line {lines}"
NOW_OVER_LATER_NEW_IF_D = "- a `#new_if_d` text, what his disapproval would do instead, on line {lines}"
SHORT_ANSWER_HOOK_FILE = HERE / ("walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-"
                                 "user-prompt-submit-hook.py")
ITEM_READ_LINES = (
    "Read that report and apply each finding that holds to {item} in the walk-document {document}; a finding that "
    "would change what the item decides becomes a new item, numbered as the walk-me-through skill's Re-planning "
    "section says.",
    "If you change {item} after this, run `{command}` and do what it prints; it reads {item} again only when your "
    "changes touch a fact.",
    "Then present {item}, unless its only choice is whether to build something now or later and it recommends now: "
    "then run `python3 {program} check " + NOW_OVER_LATER_FLAG + " --cwd {top}`, then the close command it prints.",
)
ITEM_READ_NOT_RUN_NEXT = "Present {item}."
ITEM_READ_SUB_STEP_NAMED = (
    "{item} is split into numbered sub-steps, which the user is shown one at a time, so the step added the line "
    "`#next_to_present {sub_step}` to {minutes}, naming the first sub-step of {item} the walk-minutes record no answer "
    "to, and reads {sub_step} instead of {item}.")
MARKDOWN_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*)$")
WITHDRAWN_VERSION_HEADING = "#### Withdrawn version {version} of item {number}"
NUMBER_PREDICTED = "number_predicted"
ITEM_NUMBER_PREDICTED_FLAG = "--item-number-predicted"
EARLIER_TEXT_KEPT = ("{item}: its earlier text, which the cold-read-fast-read {report} read, is now kept below its "
                     "live version in {document}, under `{heading}`; leave it there.")
EARLIER_TEXT_COPY_MISSING = (
    "nothing written and no cold-read-fast-read run: {item}'s earlier text, which the cold-read-fast-read {report} "
    "read, could not be kept below its live version in {document}, because {copy}, this program's copy of that "
    "text, is missing.\n"
    "Copy the one file under {target} to {copy}, then run `{command}` again; it then keeps that text below the "
    "live version itself.\n"
    "If {target} is gone too, do not present {item} yet: ask the user whether to go on without that text, and on "
    "his yes delete {outcome} and run `{command}` again; a subagent puts that question to the agent that "
    "dispatched it.")
ITEM_READ_FAILED_LINES = (
    "{item} has had no cold-read-fast-read of its text as it stands, so do not present it yet: the user is shown an "
    "item only after its cold-read-fast-read.",
    "Run `{command}` again once.",
    "If it fails again, ask the user whether to present {item} without its cold-read-fast-read, quoting the FAILED "
    "line above and recommending that you run the command again later; a subagent puts that question to the agent "
    "that dispatched it.",
)
READ_AHEAD_NOT_STARTED = ("No cold-read-fast-read could be started ahead for the item after {item}; this needs nothing "
                          "from you now, since when that item waits its read step reads it or reports the problem "
                          "again. The problem: {problem}")
GIT_LS_FILES_FAILED = "every changed word, since `git ls-files` failed in {top} ({error}) and file names were not known"
APPROVAL_WALK_ITEM_WORD_LIMIT = 300
# The user has not decided whether the hashtag marker lines, such as `#new`, `#new_if_d` and `#case_against`, and
# the texts quoted on `#old` and `#new` lines count toward the limit; until he does, only a line opening with one
# of these, which the item page shows apart from the item's text, is left out of the count.
APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS = ("#approval_walk_item_",)
APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE = re.compile(
    LINE_OPENING_MARKERS + "(?:" + "|".join(map(re.escape, APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS)) + ")")
# A run of characters between spaces that holds a letter or a digit, so Markdown's `##`, `-`, `>` and `|` are no words.
APPROVAL_WALK_ITEM_WORD = re.compile(r"\S*[^\W_]\S*")
APPROVAL_WALK_ITEM_SUB_STEP_HEADING_MARKUP = "###"
APPROVAL_WALK_ITEM_OVER_WORD_LIMIT = (
    "nothing read: {item} was not given its cold-read-fast-read, because the text from line {line} of the "
    "walk-document {document}, `{heading}`, has {count} words, over the limit of {limit} words for an item or a "
    "sub-step, and the user is shown no item longer than that. A word here is a run of characters between spaces or line "
    "breaks that holds a letter or a digit; every line of the item counts, heading, code and hashtag marker lines "
    "included, except a line opening with {left_out}, and each `###` sub-step, numbered or not, counts on its own.\n"
    "Split that text into `###` sub-steps, each within {limit} words, headed and ended as the walk-me-through skill's "
    "paragraph opening \"Limit each item to 300 words\" says; do not cut the text down to fit, since the user wants "
    "long material broken into steps, not compressed.\n"
    "Then run `{command}` again.\n"
    "From now on, write each item and each sub-step within {limit} words when you write it into the walk-document.")


class Failure(Exception):
    """A step that cannot go on; its argument is the line to print."""


class FastReadFailed(Exception):
    """A fast read failed; its argument is the FAILED line, printed as it is."""


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_walk_finder():
    return load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                       WALK_FINDER_FILE)


def reachable_log_store_records(record_shipper=None, ned_box_home=None, mac_mount=None):
    """Return (the log-store's cold-read-records directory as this machine reaches it, or None, and the paths
    tried): the path ned-box names it by, then the same path under the Mac's mount of ned-box's home."""
    if record_shipper is None:
        record_shipper = load_module("cold_read_record_ship", RECORD_SHIPPER_FILE)
        constants = load_module("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                                PATH_CONSTANTS_FILE)
        ned_box_home, mac_mount = constants.NED_BOX_HOME, constants.MAC_MOUNT_OF_NED_BOX_HOME
    _, path = record_shipper.split_destination(record_shipper.LOG_STORE_RECORDS_DESTINATION)
    candidates = [Path(str(path))]
    if str(path).startswith(ned_box_home + "/"):
        candidates.append(Path(mac_mount + str(path)[len(ned_box_home):]))
    return next((candidate for candidate in candidates if candidate.is_dir()), None), candidates


def the_open_walk(walk_finder, cwd):
    """Return (checkout top, minutes path, #next_to_present value, parser)."""
    top = walk_finder.checkout_top(Path(cwd))
    if top is None:
        raise Failure(f"{cwd} is not in a git checkout, so no approval-walk can be open there.")
    parser = walk_finder.markdown_parser()
    walk_directory = top / walk_finder.WALK_DIRECTORY
    try:
        walk = (walk_finder.the_one_unclosed_approval_walk_including_paused(walk_directory, parser)
                if walk_directory.is_dir() else None)
    except walk_finder.MoreThanOneUnclosedApprovalWalk as several:
        raise Failure(MORE_THAN_ONE_UNCLOSED_APPROVAL_WALK.format(
            directory=walk_directory, minutes="\n".join(f"  {path}" for path in several.minutes_paths)))
    if walk is None:
        raise Failure(f"no approval-walk is open in {walk_directory}.")
    minutes, value, _, paused = walk
    if paused:
        raise Failure(f"the approval-walk whose minutes are {minutes} is paused: an `#approval_walk_paused` line "
                      f"comes after its last `#next_to_present` line, so the walk has no item to check or close.\n"
                      f"If the user has said to resume the walk, add the line below at the end of those minutes, "
                      f"after the `#approval_walk_paused` line, which stays, and then run the command you just ran "
                      f"again:\n"
                      f"#next_to_present {value}\n"
                      f"Until the user says to resume the walk, leave it paused, do not run this program for it, "
                      f"and go on with the rest of your work.")
    return top, minutes, value, parser


def waiting_items(walk_finder, value, minutes):
    """Return (running count such as `item 4.1 of 6`, item numbers, M or None) of the `#next_to_present` value."""
    match = walk_finder.VALUE_COUNT.match(value)
    if not match:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, names no item.")
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`, {problem}.")
    return match[0], numbers, total


def item_line_ranges(walk_finder, minutes, value, numbers, total, parser, named_by=None):
    """Return (walk-document path, its text, its tokens, the (first, end) line ranges of the items numbered, the
    units of the items numbered as waiting_item_units returns them), finding the items as close does, so check
    refuses a walk-document close would refuse. A Failure names named_by as what named the items, by default the
    walk-minutes' last `#next_to_present` line."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        _, spans = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"{named_by or f'the last `#next_to_present` line in {minutes}'}, `{value}`: {problem}")
    text = document.read_text(encoding="utf-8")
    tokens = parser.parse(text)
    openings = walk_finder.item_opening_lines(text, parser, tokens)
    ranges = []
    for unit_numbers, unit_total, _, first, end in spans:
        if len(numbers) == 1 and len(unit_numbers) > 1:
            first, end = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, numbers[0], unit_numbers, unit_total)
        ranges.append((first, end))
    return document, text, tokens, ranges, spans


# CommonMark's open tag, as the Markdown parser reads one; no `<!--` in it opens a comment.
HTML_OPEN_TAG = re.compile(r"""<[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*"""
                           r"""(?:\s*=\s*(?:[^"'=<>`\x00-\x20]+|'[^']*'|"[^"]*"))?)*\s*/?>""")


def comment_openings_in_tags_escaped(text):
    """Return text with each `<!--` inside an HTML open tag, such as `<div title="<!--">`, written as `&lt;!--`."""
    return HTML_OPEN_TAG.sub(lambda tag: tag[0].replace("<!--", "&lt;!--"), text)


def item_lines(walk_finder, minutes, value, numbers, total, parser):
    """Return (walk-document path, the lines of the items numbered, outside fenced code, the items' marks as
    new_marks returns them, the problem line of each mark whose text would not be read whole, the same lines
    as the first read with no `<!--` inside an HTML open tag opening a comment)."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = walk_finder.prose_lines(text, parser, tokens)
    marks = new_marks(text, tokens, ranges, lines)
    tag_comments_kept = walk_finder.prose_lines(comment_openings_in_tags_escaped(text), parser)
    return (document, [line for first, end in ranges for line in lines[first:end]], marks,
            unreadable_new_marks(marks),
            [line for first, end in ranges for line in tag_comments_kept[first:end]])


def item_text(walk_finder, minutes, value, numbers, total, parser, named_by=None, refused_unless_marks_read=None):
    """Return (walk-document path, the items' text as the user is shown it, heading and fenced code included).
    With refused_unless_marks_read, (item, command), a Failure when a mark's text would not be read whole."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser, named_by)
    unreadable = (unreadable_new_marks(new_marks(text, tokens, ranges, walk_finder.prose_lines(text, parser, tokens)))
                  if refused_unless_marks_read else [])
    if unreadable:
        item, command = refused_unless_marks_read
        raise Failure(UNREADABLE_NEW_MARKS.format(item=item, document=document, problems="\n".join(unreadable),
                                                  command=command))
    lines = text.split("\n")
    return document, "\n".join(line for first, end in ranges for line in lines[first:end]).strip()


def approval_walk_item_sub_step_units_right_after(all_units, unit):
    """Return the units of all_units, as item_unit_spans gives them, right after unit that are sub-steps of any
    item unit names, such as `### Item 3.1 of 9` and `### Item 3.1.1 of 9` after item 3, up to the first that is
    not, so an older version's `3.1 of 9` elsewhere in the walk-document is not among them."""
    found = []
    for each in [each for each in all_units if each[3] > unit[3]]:
        if not each[0] or not all(any(part.startswith(number + ".") for number in unit[0]) for part in each[0]):
            break
        found.append(each)
    return found


def approval_walk_item_word_counted_line_ranges(walk_finder, text, tokens, parser, spans, numbers):
    """Return the (first, end) line ranges counted for the items numbered, one per text the skill counts on its
    own: each numbered item's own lines, even under a heading it shares with other items; when several items
    are shown together, the lines of their shared heading above the first item's opening; and each of the
    item's numbered sub-steps, such as `### Item 3.1 of 9`, which item_unit_spans reads as units of their own,
    taken from the units right after the item's own that are sub-steps of any item of that unit, so an older
    version's `3.1 of 9` elsewhere is not counted, with the lines of a heading several sub-steps share above
    the first sub-step's opening."""
    openings = walk_finder.item_opening_lines(text, parser, tokens)
    all_units = walk_finder.item_unit_spans(text, parser)

    def own_range(unit, number):
        unit_numbers, unit_total, _, first, end = unit
        if len(unit_numbers) > 1:
            return walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, number, unit_numbers, unit_total)
        return first, end

    def shared_heading_text(unit):
        first_opening = min(own_range(unit, part)[0] for part in unit[0])
        return [(unit[3], first_opening)] if first_opening > unit[3] else []

    ranges = []
    for number in numbers:
        unit = next(unit for unit in spans if number in unit[0])
        ranges.append(own_range(unit, number))
        if len(numbers) > 1 and len(unit[0]) > 1:
            ranges += shared_heading_text(unit)
        for each in approval_walk_item_sub_step_units_right_after(all_units, unit):
            parts = [part for part in each[0] if part.startswith(number + ".") and part not in numbers]
            ranges += [own_range(each, part) for part in parts]
            if parts and len(each[0]) > 1:
                ranges += shared_heading_text(each)
    return sorted(set(ranges))


def approval_walk_item_text_over_word_limit_refused(walk_finder, minutes, value, numbers, total, parser, item, command):
    """Raise Failure when an item's text up to its first `###` sub-step, a sub-step, or the text of a heading
    several items or sub-steps share above the first of them, has more words than APPROVAL_WALK_ITEM_WORD_LIMIT,
    naming the first such text. A sub-step is a `###` heading, numbered or not; a deeper heading is part of the
    text it falls in."""
    document, text, tokens, _, spans = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = text.split("\n")
    sub_steps = {token.map[0] for token in tokens if token.type == "heading_open" and token.level == 0
                 and token.map is not None and token.markup == APPROVAL_WALK_ITEM_SUB_STEP_HEADING_MARKUP}
    for first, end in approval_walk_item_word_counted_line_ranges(walk_finder, text, tokens, parser, spans, numbers):
        starts = sorted({first} | {line for line in sub_steps if first < line < end})
        for start, stop in zip(starts, starts[1:] + [end]):
            count = sum(len(APPROVAL_WALK_ITEM_WORD.findall(line)) for line in lines[start:stop]
                        if not APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE.match(line))
            if count > APPROVAL_WALK_ITEM_WORD_LIMIT:
                raise Failure(APPROVAL_WALK_ITEM_OVER_WORD_LIMIT.format(
                    item=item, line=start + 1, document=document, heading=lines[start].strip(), count=count,
                    limit=APPROVAL_WALK_ITEM_WORD_LIMIT, command=command,
                    left_out=" or ".join(f"`{opening}`" for opening in APPROVAL_WALK_ITEM_WORD_COUNT_LEFT_OUT_LINE_OPENINGS)))


def proposed_texts(marks_found, marks):
    """Return (mark, text) for each mark of new_marks' list that is one of marks, outside code and with a text,
    in the document's order. The text is every line new_marks gives the mark, so it is the text that
    unreadable_new_marks judged."""
    texts = []
    for mark in marks_found:
        if mark.mark not in marks or mark.in_code:
            continue
        text = unquoted(lines_joined(mark.text_lines))
        if text:
            texts.append((mark.mark, text))
    return texts


def unquoted(text):
    """Return text stripped, without one pair of surrounding quotation marks."""
    text = text.strip()
    for opening, closing in QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
            return text[1:-1].strip()
    return text


def lines_joined(lines):
    """Return lines as one line, whitespace runs squeezed."""
    return squeezed(" ".join(lines))


def unquoted_lines(lines):
    """Return lines below a mark without their quotation markers; the mark's own text keeps a leading `>`."""
    return [QUOTATION_MARKERS.sub("", line) for line in lines]


def lines_until_blank_or_fence(lines, first, end):
    """Return the lines from first up to end, without their quotation markers, stopping before a blank line or a
    fence delimiter."""
    taken = []
    for line in lines[first:end]:
        if not line.strip() or FENCE_DELIMITER.match(line):
            break
        taken.append(line)
    return unquoted_lines(taken)


def block_right_below(lines, first, end):
    """Return the lines a mark with no text on its line may have meant: the lines that run on right below it,
    or else the one fenced block or quotation after the blank lines below it; [] when there is neither."""
    if first < end and lines[first].strip() and not FENCE_DELIMITER.match(lines[first]):
        return lines_until_blank_or_fence(lines, first, end)
    while first < end and not lines[first].strip():
        first += 1
    if first < end and FENCE_DELIMITER.match(lines[first]):
        return lines_until_blank_or_fence(lines, first + 1, end)
    if first < end and QUOTATION_LINE.match(lines[first]):
        return lines_until_blank_or_fence(lines, first, end)
    return []


NewMark = collections.namedtuple("NewMark", "mark number in_code comment_cut text_lines below")
NewMark.__doc__ = """One `#new` or `#new_if_d` mark: mark, its 0-based line number, whether it is inside fenced or
indented code, whether text was cut from its line as an HTML comment, text_lines, the mark's own text as written followed by every line its text runs onto, and below,
for a mark in code or with no text, the lines it may have meant; lines below the mark's own line lose their
quotation markers."""


def new_marks(text, tokens, ranges, shown):
    """Return a NewMark for each `#new` or `#new_if_d` mark in the ranges outside an HTML comment, in order;
    shown are the walk finder's prose_lines of text, from which every HTML comment is cut.
    This is the one place that decides where a marked text ends, so that check reads the text
    unreadable_new_marks judged: at the end of its Markdown paragraph, or before the first line below it that
    this program reads on its own, such as the next `#new` or a `#case_against` line, even when Markdown keeps
    that line in the same paragraph."""
    lines = text.split("\n")
    code, paragraphs = {}, []
    for token in tokens:
        if token.map is None:
            continue
        if token.type in ("fence", "code_block"):
            code.update((number, token.map[1]) for number in range(*token.map))
        elif token.type == "paragraph_open":
            paragraphs.append(token.map)
    marks = []
    for first, end in ranges:
        for number in range(first, end):
            match = NEW_LINE.match(lines[number] if number in code else shown[number])
            if not match:
                continue
            if number in code:
                below = lines_until_blank_or_fence(lines, number + 1, min(code[number], end))
                marks.append(NewMark(match[1], number, True, False, [match[2]], below))
                continue
            comment_cut = shown[number] != lines[number]
            if not unquoted(match[2]):
                marks.append(NewMark(match[1], number, False, comment_cut, [match[2]],
                                     block_right_below(lines, number + 1, end)))
                continue
            paragraph_end = max((paragraph[1] for paragraph in paragraphs if paragraph[0] <= number < paragraph[1]),
                                default=number + 1)
            text_end = next((below for below in range(number + 1, paragraph_end)
                             if any(marker.match(lines[below]) for marker in MARKER_LINES_READ_ON_THEIR_OWN)),
                            paragraph_end)
            marks.append(NewMark(match[1], number, False, comment_cut,
                                 [match[2]] + unquoted_lines(lines[number + 1:min(text_end, end)]), []))
    return marks


def unreadable_new_marks(marks):
    """Return one problem line for each of new_marks' marks whose text check would not read whole: one with no
    text on its line, one inside fenced or indented code, one with text cut from its line as an HTML comment, and
    one whose text runs onto the lines right below it."""
    problems = []
    for found in marks:
        mark, line = found.mark, found.number + 1
        if found.comment_cut:
            problems.append(UNREADABLE_COMMENT_CUT.format(line=line, mark=mark))
        elif found.in_code or not unquoted(found.text_lines[0]):
            problem = UNREADABLE_FENCED if found.in_code else UNREADABLE_BARE
            joined = lines_joined(([found.text_lines[0]] if found.in_code else []) + found.below)
            problems.append(problem.format(line=line, mark=mark)
                            + (UNREADABLE_JOINED.format(mark=mark, text=joined) if joined else ""))
        elif len(found.text_lines) > 1:
            last = found.number + len(found.text_lines)
            below = f"line {line + 1}" if last == line + 1 else f"lines {line + 1} to {last}"
            problems.append(UNREADABLE_RUN_ON.format(line=line, mark=mark, below=below)
                            + UNREADABLE_JOINED.format(mark=mark, text=lines_joined(found.text_lines)))
    return problems




def squeezed(text):
    return " ".join(text.split())


def walk_fast_read_name(walk_name, *parts):
    """The target name of a fast read this program runs for the walk, which starts its cold-read-record's name;
    fast_read_record_holding finds the walk's records by the walk_name- prefix this gives."""
    return "-".join([walk_name, *(file_name_part(str(part)) for part in parts)])


def fast_read_record_holding(text, record_directories, walk_name):
    """Return the walk's cold-read-record directory whose fast read read the text, or None."""
    wanted = squeezed(text)
    record_names = load_module("cold_read_record_names", RECORD_NAMES_FILE)
    prefix = walk_fast_read_name(walk_name) + "-"
    for directory in record_directories:
        if not directory.is_dir():
            continue
        for record in sorted(directory.iterdir()):
            if not record.name.startswith(prefix):
                continue
            report = record_names.cold_read_record_file_path_prefixed_name_else_name_before_prefix(
                record, record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME)
            if not report.is_file() or not (record / "target").is_dir():
                continue
            for target in (record / "target").rglob("*"):
                if target.is_file() and wanted in squeezed(target.read_text(encoding="utf-8", errors="replace")):
                    return record
    return None


STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


@contextlib.contextmanager
def scratch_directory_removed_on_every_exit():
    """Make a scratch directory and yield its path; remove it when the block ends, however the block ends. A
    SIGTERM or SIGHUP during the block removes it and then ends the program as that signal's default does; one
    the program was started with ignored, as under nohup, stays ignored.

    The handler raises nothing: an exception raised inside subprocess's own code, between Popen._wait()'s lock
    acquire and its try, leaves the lock held, and the wait() that subprocess.run() then makes blocks forever.
    stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py raises, so it does not fit here.
    """
    made = []

    def remove_then_end(number, _):
        for directory in made:
            try:
                shutil.rmtree(directory)
            except OSError as error:
                print(STOP_SIGNAL_SCRATCH_NOT_REMOVED_LINES.format(
                    program=PROGRAM, signal=signal.Signals(number).name,
                    quoted_program_path=shlex.quote(str(Path(__file__).resolve())), directory=directory,
                    quoted_directory=shlex.quote(directory), error=error), file=sys.stderr)
        signal.signal(number, signal.SIG_DFL)
        os.kill(os.getpid(), number)

    previous = {number: signal.signal(number, remove_then_end)
                for number in STOP_SIGNALS if signal.getsignal(number) != signal.SIG_IGN}
    try:
        # Blocked until the path is in made, so a stop signal between the two cannot leave the directory behind.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, STOP_SIGNALS)
        try:
            scratch = tempfile.mkdtemp(prefix=PROGRAM + "-")
            made.append(scratch)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        yield scratch
    finally:
        for directory in made:
            shutil.rmtree(directory)
        for number, handler in previous.items():
            signal.signal(number, handler)


def run_fast_read(text, name, fast_read_program):
    """Fast-read the text from a scratch file; return (the report's directory, the lines the fast read printed
    on stderr about an unshipped record or a changed target), or raise FastReadFailed.

    The scratch directory is removed on every exit, SIGTERM and SIGHUP included: the fast read keeps its own copy
    of the text in its record's target/, which is where a later check looks for it."""
    with scratch_directory_removed_on_every_exit() as scratch:
        target = Path(scratch) / f"{name}.md"
        target.write_text(text + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(fast_read_program), "--target", str(target)],
                                capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    failed = [line for line in lines if line.startswith("FAILED")]
    if failed:
        raise FastReadFailed(failed[0])
    notes = [line.strip() for line in result.stderr.split("\n")
             if any(marker in line for marker in FAST_READ_NOTE_MARKERS)]
    # Exit 1 means other failures too, so only the stderr line says the record was all that failed.
    only_the_record_not_shipped = result.returncode == 1 and any(
        note.startswith(FAST_READ_RECORD_NOT_SHIPPED_MARKERS) for note in notes)
    if (result.returncode != 0 and not only_the_record_not_shipped) or not lines[-1]:
        raise FastReadFailed(f"FAILED: {fast_read_program} --target {target} exited {result.returncode} "
                             f"without naming a report; its stderr: {result.stderr.strip()[-500:]}")
    return Path(lines[-1]).parent, notes


def excerpt(walk_finder, text):
    """The start of text, as a code span, so that no marker in it is read from the minutes."""
    return walk_finder.text_wrapped_as_markdown_code_span(text if len(text) <= 60 else text[:57].rstrip() + "...")


def file_name_part(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def append_to_minutes(minutes, lines):
    existing = minutes.read_text(encoding="utf-8")
    separator = "" if existing.endswith("\n") else "\n"
    with open(minutes, "a", encoding="utf-8") as file:
        file.write(separator + "\n".join(lines) + "\n")


def part_answer(value):
    """Return (part number, A, AO or D) from a --part-answer value such as `2=ao`."""
    match = PART_ARGUMENT.match(value)
    if not match:
        raise argparse.ArgumentTypeError(PART_ARGUMENT_PROBLEM.format(value=value))
    return int(match[1]), match[2].upper()


def not_asked_kind(value):
    """Return the --not-asked value: a kind, 1 to 6, or `none` for an item of no kind whose case against is
    rated none, or weak with a case against that names only cost."""
    if value.strip().lower() == NOT_ASKED_RATED_NONE:
        return NOT_ASKED_RATED_NONE
    if value.strip() in {str(kind) for kind in NOT_ASKED_KINDS}:
        return int(value)
    kinds = ", ".join(str(kind) for kind in NOT_ASKED_KINDS)
    raise argparse.ArgumentTypeError(f"`{value}` is not a kind: give {kinds} or none")


def not_asked_label(kind, rating=None):
    """How the minutes and messages name a --not-asked value: `kind 3`, `case against none`, or, for `none` on an
    item rated weak, `case against weak, cost only`."""
    if kind in NOT_ASKED_KINDS:
        return f"kind {kind}"
    return NOT_ASKED_WEAK_COST_ONLY_LABEL if rating == NOT_ASKED_RATED_WEAK else "case against none"  # pragma: no mutate, rating is a rating word and weak sorts after the others, so `>=` acts as `==`


def guarded_paths(top, paths):
    """Return the paths, relative to the checkout top, that instruction-file-guard.py protects."""
    guard = load_module("instruction_file_guard", INSTRUCTION_FILE_GUARD_FILE)
    return [path for path in paths if any(protects(str(top / path)) for protects in (
        guard.is_protected, guard.is_reusable_prompt, guard.is_reviewed_document))]


def answered_word(arguments, walk_finder, rating=None):
    """The answer as the walk-minutes write it: approved, disapproved, approved option N, or each part's word,
    as in `part 1 approved #approved_obvious, part 2 disapproved`."""
    if arguments.part_answer:
        return ", ".join(f"part {number} {PART_WORDS[letter]}" for number, letter in sorted(arguments.part_answer))
    if arguments.disapproved:
        return DISAPPROVED
    if arguments.deferred:
        return DEFERRED
    if arguments.moved_on_no_decision:
        return MOVED_ON
    if arguments.option is not None:
        return f"{APPROVED} option {arguments.option}"
    if arguments.not_asked is not None:
        return f"not asked, {not_asked_label(arguments.not_asked, rating)}"
    if arguments.already_decided is not None:
        return ALREADY_DECIDED_PREFIX + walk_finder.text_wrapped_as_markdown_code_span(arguments.already_decided)
    if arguments.moved_on is not None:
        return MOVED_ON_PREFIX + walk_finder.text_wrapped_as_markdown_code_span(arguments.moved_on)
    return APPROVED


def marks_the_answer_adds(arguments):
    """The marks of the texts the answer adds: `#new_if_d` for D, `#new` for any other answer, and for
    answers to parts, the marks of the parts' answers."""
    if arguments.part_answer:
        letters = {letter for _, letter in arguments.part_answer}
        return {mark for mark, adds in ((NEW_MARK, letters != {"D"}), (NEW_IF_D_MARK, "D" in letters)) if adds}
    return {NEW_IF_D_MARK} if arguments.disapproved else {NEW_MARK}


def answer_hashtag(arguments):
    """The hashtag the walk-minutes write right after an AO or Aa approval, or nothing."""
    if arguments.obvious:
        return OBVIOUS_HASHTAG
    if arguments.after_advisor:
        return AFTER_ADVISOR_HASHTAG
    return ""


def answer_check_commands(program):
    """The check command for each answer an item can take, to print where the agent chose the wrong flag."""
    commands = [f"{answer}: python3 {program} check{flag} --user-reply-as-typed REPLY"
                for answer, flag in MOVED_ON_NO_DECISION_ANSWER_COMMANDS]
    commands += [MOVED_ON_NO_DECISION_OPTION_LINE.format(number=number, program=program) for number in OPTION_NUMBERS]
    commands.append(MOVED_ON_NO_DECISION_PART_LINE.format(program=program))
    return "\n".join(commands)


def check_flags(arguments):
    """The flags this check step was run with, to repeat in the command it tells the agent to rerun."""
    flags = ""
    if arguments.obvious:
        flags += " --obvious"
    if arguments.after_advisor:
        flags += " --after-advisor"
    if arguments.disapproved:
        flags += " --disapproved"
    if arguments.deferred:
        flags += " --deferred"
    if arguments.moved_on_no_decision:
        flags += " --moved-on-no-decision"
    if arguments.moved_on is not None:
        flags += f" --moved-on {shlex.quote(arguments.moved_on)}"
    if arguments.option is not None:
        flags += f" --option {arguments.option}"
    if arguments.not_asked is not None:
        flags += f" --not-asked {arguments.not_asked}"
    if arguments.now_over_later_already_decided:
        flags += " " + NOW_OVER_LATER_FLAG
    elif arguments.already_decided is not None:
        flags += f" --already-decided {shlex.quote(arguments.already_decided)}"
    for number, letter in arguments.part_answer or []:
        flags += f" --part-answer {number}={letter}"
    if (arguments.user_reply_as_typed or "").strip():
        flags += f" --user-reply-as-typed {shlex.quote(arguments.user_reply_as_typed)}"
    return flags


def case_against_rating(lines, item, document, arguments):
    """Return the rating on the item's first `#case_against` line, as in `very strong`, or None when the item
    has none and the answer, O2, O3 or --moved-on-no-decision, does not need one; raise Failure when an answer that needs one finds
    none, or a line that opens with no rating."""
    for line in lines:
        match = CASE_AGAINST_LINE.match(line)
        if not match:
            continue
        rating = CASE_AGAINST_RATING.match(match[1])
        if rating is None:
            raise Failure(CASE_AGAINST_UNRATED.format(item=item, document=document, line=line.strip(),
                                                      program=Path(__file__).resolve(),
                                                      flags=check_flags(arguments)))
        return rating[1].lower()
    if (arguments.option is not None or arguments.moved_on_no_decision or arguments.already_decided is not None
            or arguments.moved_on is not None):
        return None
    raise Failure(CASE_AGAINST_MISSING.format(item=item, document=document, program=Path(__file__).resolve(),
                                              flags=check_flags(arguments)))


def evidence(lines):
    """Return {marker: [the values of each of the item's lines opening with that `#not_asked_` marker]}."""
    found = collections.defaultdict(list)
    for line in lines:
        match = EVIDENCE_LINE.match(line)
        if match:
            found[match[1]].append(match[2].strip())
    return found


def words(values):
    """The paths or names on evidence lines, without code marks or separating commas."""
    return [word.strip("`,;") for value in values for word in value.split() if word.strip("`,;")]


def rename_names(value):
    """The names on a rename line: each name in backquotes, which may hold spaces, or else each word."""
    return [(quoted or word).strip(",;") for quoted, word in re.findall(r"`([^`]+)`|([^\s`]+)", value)
            if (quoted or word).strip(",;")]


def files_matching(top, options, pattern, item, kind, pathspec=None):
    """Return the checkout files, tracked or untracked, outside the walk directory, in which `git grep` with
    the options given finds the pattern."""
    command = ["git", "-C", str(top), "grep", "--untracked", "-l", *options, "-e", pattern]
    if pathspec:
        command += ["--", pathspec]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise Failure(GIT_GREP_FAILED.format(code=result.returncode, top=top, item=item, kind=kind,
                                             error=result.stderr.strip(), program=Path(__file__).resolve()))
    return {path for path in result.stdout.split("\n") if path and not path.startswith("docs/walk/")}


def spellings(name):
    """The name, lowercased, and, when it has two or more words, its words joined by hyphens, by underscores and
    by nothing; a digit run is split both ways, kept with the letters before it and as a word of its own, so
    `sha256_of` gives both `sha256-of` and `sha-256-of`."""
    found = {name.lower()}
    for pattern in (r"[A-Z]+[0-9]*(?![a-z])|[A-Z]?[a-z]+[0-9]*|[0-9]+", r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+"):
        parts = [part.lower() for part in re.findall(pattern, name)]
        if len(parts) > 1:
            found |= {separator.join(parts) for separator in ("-", "_", "")}
    return sorted(found)


def files_naming(top, name, item, kind):
    """Return the files outside the walk directory that hold one of the name's spellings, ignoring case,
    anywhere: a name written `poem-list` in prose is `poem_list_path` or `PoemList` in code."""
    found = set()
    for spelling in spellings(name):
        found |= files_matching(top, ["-i", "-F"], spelling, item, kind)
    return found


def glossary_entry_files(top, name, item, kind):
    """Return the glossary files with an entry whose term is the name, as in `- **poem-index** — ...` or
    `- **poem-index (aka PI)** — ...`; a name a glossary only mentions, such as an example of a bad name, is not one
    it lists."""
    escaped = re.sub(r"([.\[\]()*+?{}|^$\\])", r"\\\1", name)
    return files_matching(top, ["-i", "-E"], rf"^- \*\*{escaped}( \(aka [^)]*\))?\*\*", item, kind, GLOSSARY_FILES)


def not_asked_problems(kind, rating, lines, marks, top, item):
    """Return the lines saying why the item cannot be settled as the kind given, from what code can check."""
    problems = []
    found = evidence(lines)
    if kind == NOT_ASKED_RATED_NONE:
        if rating not in NOT_ASKED_RATINGS:
            problems.append(NOT_ASKED_NOT_RATED_NONE_PROBLEM.format(rating=rating))
        # An empty touches line is a change that touches no file; only a missing line is refused.
        if TOUCHES not in found:
            problems.append(NOT_ASKED_NO_LINE_PROBLEM.format(marker=TOUCHES, why=NOT_ASKED_WHY[TOUCHES]))
        touched = words(found[TOUCHES])
        for path in touched:
            if not (top / path).exists():
                problems.append(NOT_ASKED_MISSING_PATH_PROBLEM.format(marker=TOUCHES, path=path, top=top))
        for path in guarded_paths(top, touched):
            if rating != NOT_ASKED_RATED_WEAK:  # pragma: no mutate, rating is a rating word and weak sorts after the others, so `<` acts as `!=`
                problems.append(NOT_ASKED_GUARDED_FILE_PROBLEM.format(marker=TOUCHES, path=path))
            elif path.endswith(".md"):
                problems.append(NOT_ASKED_WEAK_GUARDED_MARKDOWN_PROBLEM.format(marker=TOUCHES, path=path))
        return problems
    if rating not in NOT_ASKED_RATINGS:
        problems.append(NOT_ASKED_RATING_PROBLEM.format(rating=rating))
    needed = {1: (TOUCHES, SOURCE), 2: (TOUCHES, TEST), 3: (TOUCHES,), 4: (TOUCHES, RENAME), 5: (SOURCE,),
              6: (TOUCHES,)}[kind]
    for marker in needed:
        if not words(found[marker]):
            problems.append(NOT_ASKED_NO_LINE_PROBLEM.format(marker=marker, why=NOT_ASKED_WHY[marker]))
    touched = words(found[TOUCHES])
    if kind == 1 and not proposed_texts(marks, {NEW_MARK}):
        problems.append(NOT_ASKED_NO_NEW_TEXT_PROBLEM)
    tests = words(found[TEST])
    for path in touched if kind != 5 else []:
        if not (top / path).exists():
            # A code fix may add the test that shows it; any other new file is an addition the user sees.
            if kind == 2 and path in tests:
                continue
            problem = NOT_ASKED_NEW_FILE_PROBLEM if kind == 2 else NOT_ASKED_MISSING_PATH_PROBLEM
            problems.append(problem.format(marker=TOUCHES, path=path, top=top))
    if kind == 2:
        for path in tests:
            if "test" not in Path(path).name or not ((top / path).is_file() or path in touched):
                problems.append(NOT_ASKED_NOT_A_TEST_PROBLEM.format(marker=TEST, path=path, top=top))
    if kind == 3:
        unused = words(found[UNUSED])
        for word in unused:
            others = sorted(files_naming(top, word, item, kind) - set(touched))
            if others:
                problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=word, marker=UNUSED, files=", ".join(others),
                                                                   touches=TOUCHES))
        not_markdown = [path for path in touched if not path.endswith(".md")]
        if not unused and not_markdown:
            problems.append(NOT_ASKED_NOT_MARKDOWN_PROBLEM.format(marker=UNUSED, touches=TOUCHES,
                                                                  paths=", ".join(not_markdown)))
    if kind == 4:
        for value in found[RENAME]:
            names = rename_names(value)
            if len(names) != 2:
                problems.append(NOT_ASKED_RENAME_SHAPE_PROBLEM.format(marker=RENAME, value=value))
                continue
            old, new = names
            if not glossary_entry_files(top, new, item, kind):
                problems.append(NOT_ASKED_NOT_IN_GLOSSARY_PROBLEM.format(new=new, pattern=GLOSSARY_FILES))
            others = sorted(files_naming(top, old, item, kind) - set(touched))
            if others:
                problems.append(NOT_ASKED_STILL_USED_PROBLEM.format(word=old, marker=RENAME, files=", ".join(others),
                                                                   touches=TOUCHES))
    if kind == 6:
        problems += glossary_term_or_marker_problems(found, touched, top, item)
    return problems


def marker_reader_pattern(marker):
    """The `git grep -E` pattern for code that reads `marker`: the marker whole; or a part of it that ends just
    before a `-`, as `\\b` patterns read `#approval_walk_paused` in `#approval_walk_paused-note`; or a part that
    ends with `_` and is followed by no letter or digit, as `#case_against_[a-z_]+` reads `#case_against_strong`.
    A marker is otherwise found only whole: `#new` is not `#new_if_d`, nor `#newer`."""
    parts = [f"{marker}([^A-Za-z0-9_-]|$)"]
    for end, character in enumerate(marker):
        if character == "-":
            parts.append(f"{marker[:end]}([^A-Za-z0-9_-]|$)")
        elif character == "_":
            parts.append(f"{marker[:end + 1]}([^A-Za-z0-9]|$)")
    return "|".join(f"({part})" for part in parts)


def glossary_term_or_marker_problems(found, touched, top, item):
    """Return why a kind 6 item, a glossary term put in or a hashtag marker added to Markdown prose, cannot settle."""
    problems = []
    terms = [name for value in found[GLOSSARY_TERM] for name in rename_names(value)]
    markers = words(found[ADDED_HASHTAG_MARKER])
    if not terms and not markers:
        problems.append(NOT_ASKED_NO_TERM_OR_MARKER_PROBLEM.format(term=GLOSSARY_TERM, marker=ADDED_HASHTAG_MARKER))
    for path in touched:
        if not path.endswith(".md") or fnmatch.fnmatch(Path(path).name, GLOSSARY_FILES):
            problems.append(NOT_ASKED_GLOSSARY_OR_NOT_MARKDOWN_PROBLEM.format(touches=TOUCHES, path=path))
    for term in terms:
        if not glossary_entry_files(top, term, item, 6):
            problems.append(NOT_ASKED_TERM_NOT_IN_GLOSSARY_PROBLEM.format(term=term, pattern=GLOSSARY_FILES))
    for value in markers:
        if not HASHTAG_MARKER.fullmatch(value):
            problems.append(NOT_ASKED_MARKER_SHAPE_PROBLEM.format(value=value, marker=ADDED_HASHTAG_MARKER))
            continue
        readers = sorted(files_matching(top, ["-E", "-i"], marker_reader_pattern(value), item, 6, NOT_MARKDOWN_FILES))
        if readers:
            problems.append(NOT_ASKED_MARKER_READ_PROBLEM.format(value=value, files=", ".join(readers)))
    return problems


def now_over_later_problems(walk_finder, minutes, value, numbers, total, parser):
    """Return (walk-document path, one line for each kind of choice besides now or later that the item holds:
    `Part N.` paragraphs, `Option N` lines and `#new_if_d` marks, each with its 1-based line numbers)."""
    document, text, tokens, ranges, _ = item_line_ranges(walk_finder, minutes, value, numbers, total, parser)
    lines = walk_finder.prose_lines(text, parser, tokens)
    hook = load_module("walk_me_through_user_short_answer_hook", SHORT_ANSWER_HOOK_FILE)
    found = {
        NOW_OVER_LATER_PARTS: [line for line, _ in hook.part_starts(tokens)
                               if any(first <= line < end for first, end in ranges)],
        NOW_OVER_LATER_OPTIONS: [number for first, end in ranges for number in range(first, end)
                                 if OPTION_LINE.match(lines[number])],
        NOW_OVER_LATER_NEW_IF_D: [mark.number for mark in new_marks(text, tokens, ranges, lines)
                                  if mark.mark == NEW_IF_D_MARK],
    }
    return document, [problem.format(lines=", ".join(str(number + 1) for number in sorted(set(numbers))))
                      for problem, numbers in found.items() if numbers]


def check(arguments):
    if arguments.now_over_later_already_decided:
        arguments.already_decided = NOW_OVER_LATER_USER_RULING_CITATION
    part_numbers = [number for number, _ in arguments.part_answer or []]
    repeated = sorted({number for number in part_numbers if part_numbers.count(number) > 1})
    if repeated:
        raise Failure(PART_REPEATED.format(parts=", ".join(f"part {number}" for number in repeated)))
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, numbers, total = waiting_items(walk_finder, value, minutes)
    if numbers[1:]:
        raise Failure(CHECK_SEVERAL_WAITING.format(minutes=minutes, item=item, one_item_line=NEXT_MARKER_LINE.format(
            value=f"item <number>{f' of {total}' if total else ''}")))
    words = " ".join((arguments.user_reply_as_typed or "").split())
    program = Path(__file__).resolve()
    not_shown_flag = ("--not-asked" if arguments.not_asked is not None
                      else NOW_OVER_LATER_FLAG if arguments.now_over_later_already_decided
                      else "--already-decided" if arguments.already_decided is not None
                      else "--moved-on" if arguments.moved_on is not None else None)
    if not_shown_flag and words:
        raise Failure(USER_WORDS_NOT_ASKED.format(flag=not_shown_flag))
    if not not_shown_flag and not words:
        raise Failure(USER_WORDS_MISSING.format(program=program, flags=check_flags(arguments)))
    if NAVIGATION_WORD_ALONE.match(words) and not arguments.moved_on_no_decision:
        raise Failure(NAVIGATION_WORD_REFUSED.format(words=words, item=item,
                                                     answered=answered_word(arguments, walk_finder),
                                                     program=program, quoted_words=shlex.quote(words)))
    if arguments.now_over_later_already_decided:
        document, problems = now_over_later_problems(walk_finder, minutes, value, numbers, total, parser)
        if problems:
            raise Failure(NOW_OVER_LATER_REFUSED.format(item=item, document=document, problems="\n".join(problems)))
    in_his_words = USER_WORDS.format(words=walk_finder.text_wrapped_as_markdown_code_span(words)) if words else ""
    document, lines, marks, unreadable, tag_comments_kept = item_lines(walk_finder, minutes, value, numbers, total,
                                                                       parser)
    rating = case_against_rating(lines, item, document, arguments)
    rated = CASE_AGAINST_HASHTAG.format(rating=rating.replace(" ", "_")) if rating else ""
    recommendation = walk_finder.approval_walk_item_last_recommendation_text_from_item_lines(lines)
    if arguments.moved_on_no_decision and recommendation is not None:
        raise Failure(MOVED_ON_NO_DECISION_REFUSED.format(
            item=item, recommendation=recommendation,
            commands=answer_check_commands(program)))
    hidden = (walk_finder.approval_walk_item_last_recommendation_text_from_item_lines(tag_comments_kept)
              if arguments.moved_on_no_decision and recommendation is None else None)
    if hidden is not None:
        raise Failure(MOVED_ON_NO_DECISION_HIDDEN_RECOMMENDATION.format(
            item=item, document=document, recommendation=hidden, program=program, quoted_words=shlex.quote(words)))
    if arguments.deferred or arguments.moved_on_no_decision or arguments.moved_on is not None:
        now = datetime.datetime.now().astimezone()
        no_change = CHECK_MOVED_ON_MINUTES if arguments.moved_on is not None else CHECK_DEFERRED_MINUTES
        append_to_minutes(minutes, [no_change.format(item=item, answered=answered_word(arguments, walk_finder),
                                                     rating=rated,
                                                     words=in_his_words, date_and_time=minutes_time(now))])
        print(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
        return 0
    if unreadable:
        raise Failure(UNREADABLE_NEW_MARKS.format(item=item, document=document, problems="\n".join(unreadable),
                                                  command=f"python3 {program} check{check_flags(arguments)}"))
    if arguments.not_asked is not None:
        problems = not_asked_problems(arguments.not_asked, rating, lines, marks, top, item)
        if problems:
            raise Failure(NOT_ASKED_REFUSED.format(item=item, kind=arguments.not_asked,
                                                   label=not_asked_label(arguments.not_asked, rating),
                                                   problems="\n".join(problems),
                                                   document=document, program=Path(__file__).resolve()))
    texts = proposed_texts(marks, marks_the_answer_adds(arguments))
    log_store_records, tried = (None, []) if arguments.cold_read_records and arguments.counts_log \
        else reachable_log_store_records()
    record_directories = arguments.cold_read_records or (
        [top / RECORDS_DIRECTORY_NAME] + ([log_store_records] if log_store_records else []))
    walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    statuses, already_done, had_to_be_run, problems = [], 0, 0, []
    counted = collections.Counter()
    for mark, text in texts:
        counted[mark] += 1
        number = counted[mark]
        record = fast_read_record_holding(text, record_directories, walk_name)
        if record is not None:
            already_done += 1
            statuses.append(STATUS_ALREADY_DONE.format(mark=mark, number=number, excerpt=excerpt(walk_finder, text),
                                                       record=record))
            continue
        name = walk_fast_read_name(walk_name, item, mark, number)
        record, notes = run_fast_read(text, name, arguments.fast_read_program)
        had_to_be_run += 1
        statuses.append(STATUS_HAD_TO_BE_RUN.format(mark=mark, number=number, excerpt=excerpt(walk_finder, text),
                                                    record=record)
                        + "".join(STATUS_FAST_READ_NOTE.format(note=note) for note in notes))
        for note in notes:
            if note.startswith(FAST_READ_RECORD_NOT_SHIPPED_MARKERS):
                problems += [line.format(mark=mark, number=number, note=note, record=record,
                                         shipper=RECORD_SHIPPER_FILE)
                             for line in RECORDS_NOT_SHIPPED]
    if not texts:
        statuses.append(NO_PROPOSED_TEXT)
    now = datetime.datetime.now().astimezone()
    not_asked = arguments.not_asked is not None or arguments.already_decided is not None
    answer_minutes = CHECK_NOT_ASKED_MINUTES if not_asked else CHECK_MINUTES
    append_to_minutes(minutes, [answer_minutes.format(item=item, answered=answered_word(arguments, walk_finder, rating),
                                                      hashtag=answer_hashtag(arguments), rating=rated,
                                                      words=in_his_words, date_and_time=minutes_time(now))]
                      + [STATUS_LINE_PREFIX + status for status in statuses])
    output = list(statuses)
    if had_to_be_run:
        output += [line.format(document=document, item=item) for line in CHECK_JUDGEMENT_LINES]
    if arguments.not_asked is not None:
        output += [line.format(item=item, label=not_asked_label(arguments.not_asked, rating))
                   for line in NOT_ASKED_JUDGEMENT_LINES]
        if arguments.not_asked == NOT_ASKED_RATED_NONE and rating == NOT_ASKED_RATED_WEAK:  # pragma: no mutate, not_asked_kind returns the constant itself and weak sorts after the other rating words, so `is` and `>=` act as `==`
            output.append(NOT_ASKED_WEAK_JUDGEMENT_LINE.format(item=item))
    output.append(CHECK_CLOSE_LINE.format(program=Path(__file__).resolve(), top=shlex.quote(str(top))))
    log = arguments.counts_log or (log_store_records.parent / COUNTS_LOG_FILE_NAME if log_store_records else None)
    try:
        if log is None:
            raise OSError(LOG_STORE_UNREACHABLE.format(paths=" or ".join(str(path) for path in tried)))
        with open(log, "a", encoding="utf-8") as file:
            file.write("\t".join([now.isoformat(timespec="seconds"), walk_name, item,
                                  f"texts={len(texts)}", f"already_done={already_done}",
                                  f"had_to_be_run={had_to_be_run}"]) + "\n")
    except OSError as error:
        problems += [line.format(log=log or "the log-store", error=error) for line in COUNTS_NOT_LOGGED]
    print("\n".join(output + problems))
    return 2 if problems else 0


def items_named(numbers, total):
    return f"item{'s' if numbers[1:] else ''} {' and '.join(numbers)} of {total}"


def item_reads_directory(walk_finder, minutes):
    return minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ITEM_READS_DIRECTORY_SUFFIX)


def text_key(text):
    # Whitespace is kept: inside a code span or fenced code it changes what the user is shown.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    """Write value to path whole: a reader sees the old file or the new one, never half of one."""
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def read_outcome(reads, key):
    """Return the outcome a read of the text keyed key wrote, or None while it has written none."""
    path = reads / f"{key}-outcome.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def worker_alive(reads, key):
    """Whether a read-ahead worker started for the text keyed key is still running."""
    started = reads / f"{key}-started.json"
    if not started.is_file():
        return False
    try:
        os.kill(json.loads(started.read_text(encoding="utf-8"))["pid"], 0)
    except ProcessLookupError:
        return False
    return True


def record_read(reads, key, item, text, outcome, number_predicted=False):
    """Keep the text read beside the read's outcome, for a later AFTER_FIXES_FLAG read to compare against.
    number_predicted marks a read ahead of an unnumbered item, whose number is only the one close expects to give it,
    until read_ahead_bound_to_item binds it to the item the read step uses it for."""
    (reads / f"{key}.md").write_text(text + "\n", encoding="utf-8")
    predicted = {NUMBER_PREDICTED: True} if number_predicted else {}
    write_json(reads / f"{key}-outcome.json", dict(outcome, item=item, finished=time.time(), **predicted))


def read_ahead_bound_to_item(reads, key, outcome, item):
    """Write and return the outcome of the read ahead at key as item's own read, NUMBER_PREDICTED false: the read
    step used it for item, so it stays item's read whatever title, text or number the item has later."""
    bound = dict(outcome, item=item, **{NUMBER_PREDICTED: False})
    write_json(reads / f"{key}-outcome.json", bound)
    return bound


def fast_read_outcome(text, name, fast_read_program):
    """Fast-read the text and return the outcome a read-ahead worker writes: done with the report and the fast
    read's notes, or failed with its FAILED line."""
    try:
        record, notes = run_fast_read(text, name, fast_read_program)
    except FastReadFailed as failure:
        return {"status": READ_FAILED, "failed": failure.args[0]}
    record_names = load_module("cold_read_record_names", RECORD_NAMES_FILE)
    report = record_names.cold_read_record_file_path_prefixed_name_else_name_before_prefix(
        record, record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME)
    return {"status": READ_DONE, "report": str(report), "notes": notes}


def read_ahead_worker(arguments):
    """The detached process close starts: fast-read the text kept at --text-file and write its outcome."""
    reads, key = arguments.text_file.parent, arguments.text_file.stem
    text = arguments.text_file.read_text(encoding="utf-8").rstrip("\n")
    record_read(reads, key, arguments.item, text, fast_read_outcome(text, arguments.name, arguments.fast_read_program),
                arguments.item_number_predicted)
    return 0


def start_read_ahead(reads, item, text, name, fast_read_program, top, number_predicted=False):
    """Start a detached read-ahead worker on the text, unless a read of the same text was started or written
    before, whatever its outcome: a read ahead is never retried, so a failed one leaves the read to the read step."""
    key = text_key(text)
    if (reads / f"{key}-outcome.json").is_file() or (reads / f"{key}-started.json").is_file():
        return
    reads.mkdir(exist_ok=True)
    text_file = reads / f"{key}.md"
    text_file.write_text(text + "\n", encoding="utf-8")
    # Its own session, and no pipe to this process, so close returns at once and the read outlives it.
    with open(reads / f"{key}.log", "w", encoding="utf-8") as log:
        worker = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), READ_AHEAD_WORKER_STEP,
                                   "--text-file", str(text_file), "--item", item, "--name", name,
                                   "--fast-read-program", str(fast_read_program)]
                                  + ([ITEM_NUMBER_PREDICTED_FLAG] if number_predicted else []),
                                  stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=top, start_new_session=True)
    write_json(reads / f"{key}-started.json", {"pid": worker.pid, "item": item})


def start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, total, fast_read_program):
    """Start the read ahead of the item the walk would present after the items numbered, if there is one.
    An unnumbered item is read as close will number it, with the number and M close would give it then.
    Return None, or a line saying why no read ahead could be started: the read ahead is a guess, so its
    failure never stops close or the read step."""
    named = items_named(numbers, total)
    try:
        count, order, summary, units, placing = walk_document_items(walk_finder, minutes, named, numbers, total,
                                                                    parser, WAITING_ITEM_READ_STEP, top)
        text = minutes.read_text(encoding="utf-8")
        decided, deferrals = minutes_record(walk_finder, text, parser)
        after = next_item(order, summary, numbers, numbers, decided | set(numbers), deferrals, placing,
                          held_answers_unresolved(walk_finder, text, parser))
        if not after:
            return None
        if isinstance(after[0], int):
            number = walk_finder.approval_walk_next_unnumbered_item_number(units)
            after_named = items_named([number], count)
            text = unnumbered_item_text_once_numbered(walk_finder, minutes, after[0], units, number, count)
        else:
            after_named = items_named(after, total)
            _, text = item_text(walk_finder, minutes, after_named, after, total, parser,
                                named_by=f"the item after {named}")
        walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
        start_read_ahead(item_reads_directory(walk_finder, minutes), after_named, text,
                         walk_fast_read_name(walk_name, after_named), fast_read_program, top,
                         number_predicted=isinstance(after[0], int))
    except Failure as problem:
        return READ_AHEAD_NOT_STARTED.format(item=named, problem=problem)
    return None


def tracked_names(top):
    """Return the paths `git ls-files` lists in top, their directories and their file names, or raise OSError."""
    result = subprocess.run(["git", "-C", str(top), "ls-files", "-z"], capture_output=True, text=True)
    if result.returncode != 0:
        raise OSError(f"exit {result.returncode}: {result.stderr.strip()}")
    names = set()
    for path in filter(None, result.stdout.split("\0")):
        parts = path.split("/")
        names.update("/".join(parts[:end]) for end in range(1, len(parts) + 1))
        names.add(parts[-1])
    return names


def is_fact(token, names):
    """Whether a changed token is a number, a path, a file or program name, or a link."""
    if re.search(r"\d", token) or "`" in token or "](" in token or "://" in token or re.search(AUTOLINK, token):
        return True
    core = token.strip(TOKEN_EDGE_PUNCTUATION).rstrip("/")
    return core in names or (bool(FILE_EXTENSION_END.search(core)) and not LETTER_ABBREVIATION.fullmatch(core))


def labelled_parts(text):
    """Return, for each fact label and the `#case_against` line, what the text holds from the label on."""
    lines = text.split("\n")
    parts = [squeezed(line[line.index(label):]) for label in FACT_LABELS for line in lines if label in line]
    return parts + [squeezed(line) for line in lines if CASE_AGAINST_LINE.match(line)]


def approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read(before, after, top):
    """Return the facts the change from before to after touches, as words to list; empty when it touches none.
    When `git ls-files` fails and any word changed, the list holds one line saying so instead of the names."""
    facts = [f"\"{part[:40]}\"" for part in
             sorted(set(labelled_parts(before)) ^ set(labelled_parts(after)))]
    old, new = FACT_TOKEN.findall(before), FACT_TOKEN.findall(after)
    changed = [token for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
               if tag != "equal" for token in old[i1:i2] + new[j1:j2]]
    try:
        names = tracked_names(top)
    except OSError as error:
        return facts + [GIT_LS_FILES_FAILED.format(top=top, error=error)] if changed else facts
    return facts + [token for token in dict.fromkeys(changed) if is_fact(token, names)]


def latest_read(reads, item):
    """Return (key, outcome) of the latest read of the item that wrote its report, or None; a read ahead that no read
    step has used is no item's read."""
    done = []
    for path in reads.glob("*-outcome.json") if reads.is_dir() else []:
        outcome = json.loads(path.read_text(encoding="utf-8"))
        if outcome["item"] == item and outcome["status"] == READ_DONE and not outcome.get(NUMBER_PREDICTED):
            done.append((outcome["finished"], path.name[:-len("-outcome.json")], outcome))
    return max(done)[1:] if done else None


def heading_body(walk_finder, text):
    """Return an item's text without its heading, which changes with M and the deferred note alone: a `#` heading
    line goes whole; a bold paragraph's first line keeps its text after the running count, which can hold the item's
    recommendation."""
    first, _, rest = text.partition("\n")
    if first.lstrip().startswith("#"):
        return blank_lines_stripped(rest)
    return blank_lines_stripped(item_title(walk_finder, first) + "\n" + rest)


def blank_lines_stripped(text):
    """The text without its leading and trailing blank lines; a first line's indentation stays, as an indented code
    block needs it to stay code."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def item_title(walk_finder, line):
    """The text of an item's heading line without its `#` marks, running count, deferred note and the emphasis
    delimiters around the count, which renumbering the item does not change; every other character stays."""
    line = walk_finder.approval_walk_item_heading_with_deferred_note_removed(line).lstrip("#").strip()
    count = walk_finder.HEADING_COUNT.match(line)
    if not count:
        return line
    opener = re.match(r"[*_]*", line)[0]
    title = line[count.end():].lstrip(" :,.;")
    if opener and title.startswith(opener):
        return title[len(opener):].lstrip(" :,.;").rstrip()
    # The emphasis that opened before the count closes after the title; a delimiter inside a code span, or with
    # a space before it, as in `x ** 2`, closes nothing.
    code = [span.span() for span in walk_finder.CODE_SPAN.finditer(title)]
    closer = next((found.start() for found in re.finditer(re.escape(opener), title) if opener
                   and found.start() > 0 and not title[found.start() - 1].isspace()
                   and not any(start <= found.start() < end for start, end in code)), None)
    if closer is not None:
        title = title[:closer] + title[closer + len(opener):]
    return title.rstrip()


def earlier_read_texts_of_item(walk_finder, minutes, value, numbers, total, parser, reads, command):
    """Return [(key, outcome, text)] for each text of the waiting item that a read wrote its report for, oldest read
    first. A read ahead of an unnumbered item that no read step has used, whatever number close expected to give
    it, counts only when its text's title is the item's title now and no other item's. An item that shares its
    heading with others, or several waiting items, have none. Raise Failure, before anything is written, when the
    copy of a text read under the item's number is missing."""
    if len(numbers) != 1 or not reads.is_dir():
        return []
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    # A walk-document missing, or without the item, is walk_document_items' refusal to give, naming the minutes'
    # `#next_to_present` line.
    try:
        text = document.read_text(encoding="utf-8")
        units = walk_finder.item_unit_spans(text, parser)
        unit = walk_finder.waiting_item_units(document, value, numbers, total, parser, units)[1][0]
    except (OSError, walk_finder.UnusableRange):
        return []
    if len(unit[0]) != 1:
        return []
    lines = text.split("\n")
    title = item_title(walk_finder, lines[unit[3]])
    title_unique = [item_title(walk_finder, lines[other[3]]) for other in units].count(title) == 1
    item = items_named(numbers, total or unit[1])
    earlier = []
    for path in reads.glob("*-outcome.json"):
        outcome = json.loads(path.read_text(encoding="utf-8"))
        predicted = outcome.get(NUMBER_PREDICTED)
        # Every outcome's item was written by items_named, so it always parses.
        numbered = walk_finder.parse_items(outcome["item"])[0] == numbers
        if outcome["status"] != READ_DONE or not (numbered or (predicted and title_unique)):
            continue
        key = path.name[:-len("-outcome.json")]
        copy = reads / f"{key}.md"
        if not copy.is_file():
            # Without its copy, a read ahead under another number cannot be told to be this item's.
            if not numbered:
                continue
            raise Failure(EARLIER_TEXT_COPY_MISSING.format(
                item=item, report=outcome["report"], document=document, copy=copy,
                outcome=reads / f"{key}-outcome.json", target=Path(outcome["report"]).parent / "target",
                command=command))
        copied = copy.read_text(encoding="utf-8")
        if predicted and not (title_unique and item_title(walk_finder, copied.split("\n", 1)[0]) == title):
            continue
        earlier.append((outcome["finished"], key, outcome, copied))
    return [entry[1:] for entry in sorted(earlier)]


def earlier_read_texts_kept_as_withdrawn_versions(walk_finder, minutes, value, numbers, total, parser, earlier, item,
                                                  live_text):
    """Put each of earlier, as earlier_read_texts_of_item returns them, that is neither the live text nor already
    below it, under a WITHDRAWN_VERSION_HEADING after the item's live version; return a line for each."""
    if not earlier:
        return []
    number = numbers[0]
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    unit = walk_finder.waiting_item_units(document, value, numbers, total, parser)[1][0]
    lines, kept = text.split("\n"), []
    for _, outcome, copied in earlier:
        body = heading_body(walk_finder, copied)
        spans = walk_finder.item_unit_spans("\n".join(lines), parser)
        # From the live version's end to the next item: the versions already kept there, and any notes.
        start = next(other[4] for other in spans if other[3] == unit[3])
        below = min([other[3] for other in spans if other[3] > unit[3]] + [len(lines)])
        if squeezed(body) in (squeezed(heading_body(walk_finder, live_text)), "") or squeezed(body) in squeezed(
                "\n".join(lines[start:below])):
            continue
        prose = walk_finder.prose_lines("\n".join(lines), parser)
        version = 1 + sum(1 for line in prose[start:below]
                          if (heading := MARKDOWN_HEADING.match(line))
                          and walk_finder.WITHDRAWN_HEADING.match(heading[1])
                          and number in walk_finder.withdrawn_heading_items(heading[1]))
        while below > 0 and not lines[below - 1].strip():
            below -= 1
        heading = WITHDRAWN_VERSION_HEADING.format(version=version, number=number)
        # One element per line: item_unit_spans counts lines, so a later span must see each of them.
        lines[below:below] = ["", heading, ""] + body.split("\n")
        kept.append(EARLIER_TEXT_KEPT.format(item=item, report=outcome["report"], document=document,
                                             heading=heading))
    if kept:
        document.write_text("\n".join(lines), encoding="utf-8")
    return kept


def approval_walk_item_first_numbered_sub_step_without_answer(walk_finder, minutes, value, numbers, total, parser):
    """Return the sub-step, such as 3.1, of the one item numbers names, such as 3, that holds the sub-step
    next_item names first among the item's sub-steps and theirs, such as 3.1.1, taken from the walk-document's
    units right after the item's own; next_item's rule decides, so the read step and the close step name the
    same sub-step. When the walk-document has no heading for that sub-step, such as no 3.1 above 3.1.1, the
    shortest of the named sub-step's levels below the item that has one, such as 3.1.1 for 3.1.1.1. None when
    numbers names several items or next_item names none."""
    if len(numbers) != 1:
        return None
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    all_units = walk_finder.item_unit_spans(document.read_text(encoding="utf-8"), parser)
    unit = walk_finder.waiting_item_units(document, value, numbers, total, parser, all_units)[1][0]
    sub_steps = [part for each in approval_walk_item_sub_step_units_right_after(all_units, unit)
                 for part in each[0] if part.startswith(numbers[0] + ".")]
    text = minutes.read_text(encoding="utf-8")
    decided, deferrals = minutes_record(walk_finder, text, parser)
    named = next_item(sub_steps, None, [], [], decided, deferrals,
                      unresolved=held_answers_unresolved(walk_finder, text, parser))
    if not named:
        return None
    # A walk-document may give sub-sub-steps 2.1.1 to 2.1.3 no heading for 2.1: step into the next level that has one.
    parts = named[0][len(numbers[0]) + 1:].split(".")
    return next(level for level in (numbers[0] + "." + ".".join(parts[:depth]) for depth in range(1, len(parts) + 1))
                if level in sub_steps)


def waiting_item_read(arguments, sub_step_of=None):
    """Give the item the `#next_to_present` line names its cold-read-fast-read, as its text stands.

    sub_step_of is (the sub-step's `#next_to_present` value, the item it is a sub-step of, the arguments of
    earlier_read_texts_kept_as_withdrawn_versions for that item and each item above it) when the line names an
    item split into numbered sub-steps: the sub-step is read in its place, and its line is added to the walk-minutes,
    and each such item's earlier read texts are kept as withdrawn versions, only once every refusal has passed, so a
    refused read leaves the walk-minutes and the walk-document as they were."""
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    if sub_step_of:
        value = sub_step_of[0]
    _, numbers, total = waiting_items(walk_finder, value, minutes)
    program = Path(__file__).resolve()
    reads = item_reads_directory(walk_finder, minutes)
    rerun = READ_STEP_COMMAND.format(
        program=program, flags=" " + AFTER_FIXES_FLAG if arguments.after_fixes_reread_only_when_facts_change else "",
        top=shlex.quote(str(top)))
    # Before walk_document_items, which can write: a missing copy refuses with nothing written.
    earlier = earlier_read_texts_of_item(walk_finder, minutes, value, numbers, total, parser, reads, rerun)
    count, _, _, _, _ = walk_document_items(walk_finder, minutes, value, numbers, total, parser,
                                                WAITING_ITEM_READ_STEP, top)
    total = total or count
    item = items_named(numbers, total)
    command = READ_STEP_COMMAND.format(program=program, flags=" " + AFTER_FIXES_FLAG, top=shlex.quote(str(top)))
    document, text = item_text(walk_finder, minutes, value, numbers, total, parser,
                               refused_unless_marks_read=(item, command))
    # Before the kept versions are written, so a refused item's document is left as it was.
    approval_walk_item_text_over_word_limit_refused(walk_finder, minutes, value, numbers, total, parser, item, command)
    sub_step = approval_walk_item_first_numbered_sub_step_without_answer(walk_finder, minutes, value, numbers, total,
                                                                         parser)
    keep = (walk_finder, minutes, value, numbers, total, parser, earlier, item, text)
    if sub_step:
        return waiting_item_read(arguments, (items_named([sub_step], total), item,
                                             (sub_step_of[2] if sub_step_of else []) + [keep]))
    if sub_step_of:
        # An item read before it was split keeps that text, as an item revised after its read does.
        for above in sub_step_of[2]:
            for line in earlier_read_texts_kept_as_withdrawn_versions(*above):
                print(line)
        append_to_minutes(minutes, [NEXT_MARKER_LINE.format(value=item)])
        print(ITEM_READ_SUB_STEP_NAMED.format(item=sub_step_of[1], sub_step=item, minutes=minutes))
    for line in earlier_read_texts_kept_as_withdrawn_versions(walk_finder, minutes, value, numbers, total, parser,
                                                              earlier, item, text):
        print(line)
    not_started = start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, total,
                                                 arguments.fast_read_program)
    if not_started:
        print(not_started)
    key = text_key(text)
    while read_outcome(reads, key) is None and worker_alive(reads, key):
        time.sleep(READ_POLL_SECONDS)
    outcome, ahead = read_outcome(reads, key), (reads / f"{key}-started.json").is_file()
    if outcome and outcome["status"] == READ_DONE and outcome.get(NUMBER_PREDICTED):
        outcome = read_ahead_bound_to_item(reads, key, outcome, item)
    why = ""
    if outcome and outcome["status"] == READ_DONE:
        how = ITEM_READ_HOW_AHEAD if ahead else ITEM_READ_HOW_ALREADY
    else:
        if ahead:
            why = (ITEM_READ_RUN_AHEAD_FAILED.format(line=outcome["failed"]) if outcome
                   else ITEM_READ_RUN_AHEAD_ENDED.format(log=reads / f"{key}.log"))
        latest = latest_read(reads, item) if arguments.after_fixes_reread_only_when_facts_change else None
        if latest is not None:
            last_text = (reads / f"{latest[0]}.md").read_text(encoding="utf-8").rstrip("\n")
            facts = approval_walk_item_before_and_after_fixes_compare_for_changed_fact_words_needing_another_cold_read_fast_read(last_text, text, top)
            if not facts:
                print("\n".join([ITEM_READ_NOT_RUN.format(item=item, report=latest[1]["report"]),
                                 ITEM_READ_NOT_RUN_NEXT.format(item=item)]))
                return 0
            why = ITEM_READ_RUN_FACTS.format(report=latest[1]["report"], facts=", ".join(facts[:FACTS_LISTED]))
        walk_name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
        outcome = fast_read_outcome(text, walk_fast_read_name(walk_name, item), arguments.fast_read_program)
        reads.mkdir(exist_ok=True)
        (reads / f"{key}-started.json").unlink(missing_ok=True)
        record_read(reads, key, item, text, outcome)
        if outcome["status"] == READ_FAILED:
            print("\n".join([outcome["failed"]]
                            + [line.format(item=item, command=command.replace(" " + AFTER_FIXES_FLAG, ""))
                               for line in ITEM_READ_FAILED_LINES]))
            return 1
        how = ITEM_READ_HOW_RUN.format(why=why)
    notes = "".join(STATUS_FAST_READ_NOTE.format(note=note) for note in outcome["notes"])
    print("\n".join([ITEM_READ_USED.format(item=item, how=how, report=outcome["report"], notes=notes)]
                    + [line.format(item=item, document=document, command=command, program=program,
                                   top=shlex.quote(str(top))) for line in ITEM_READ_LINES]))
    return 0


def last_answer(walk_finder, minutes, parser):
    """Return (item, answered, status lines) of the walk-minutes' last answer line, or raise Failure when
    there is none or a close already recorded it."""
    lines = walk_finder.prose_lines(minutes.read_text(encoding="utf-8"), parser)
    for index in range(len(lines) - 1, -1, -1):
        match = ANSWER_LINE.match(lines[index])
        if match:
            statuses = []
            for line in lines[index + 1:]:
                if not line.startswith(STATUS_LINE_PREFIX):
                    break
                statuses.append(line[len(STATUS_LINE_PREFIX):])
            # Every line close writes for an answer opens with its item; without this, a close after a
            # check that failed reads the earlier, already closed answer as one held for a new item.
            if any(line.startswith(match["item"] + ": ") for line in lines[index + 1:]):
                raise Failure(CLOSE_ALREADY_RECORDED.format(minutes=minutes, item=match["item"],
                                                            program=Path(__file__).resolve()))
            return match["item"], match["answered"], statuses
    raise Failure(f"{minutes} has no line recording the user's answer; run "
                  f"`python3 {Path(__file__).resolve()} check` first, with the flag for the user's answer as "
                  f"`--help` lists it.")


def walk_document_items(walk_finder, minutes, value, numbers, total, parser, step, top, stamp=True):
    """Return (M as the walk finder counts it, the walk-document's items in order, the summary item or None, its
    units, the placing of the items not yet shown), an item being its number, or, for an unnumbered item, its
    heading's line index, an int, which unnumbered_item_numbered numbers when it is shown.

    The placing maps each unnumbered item but the summary item to (its sort key, the items it waits on), as
    unshown_items_placing reads them; first, with stamp, it writes the `#approval_walk_item_first_entered` line, with
    today's date, into each such item that has none. Raise Failure, writing nothing, when an item's lines do not let
    it be placed."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8") if document.is_file() else ""
    units = walk_finder.item_unit_spans(text, parser) if document.is_file() else None
    try:
        walk_finder.waiting_item_units(document, value, numbers, total, parser, units)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    today = datetime.date.today().isoformat()
    try:
        order, summary, placing = walk_document_order(walk_finder, text, units, parser, document, today)
        stamped = unshown_items_first_entered_stamped(walk_finder, text, units, parser, today) if stamp else text
        if stamped != text:
            # Placed before the write, so a stamped document that no longer places writes nothing.
            units = walk_finder.item_unit_spans(stamped, parser)
            order, summary, placing = walk_document_order(walk_finder, stamped, units, parser, document, today)
    except WalkOrderUnusable as problem:
        raise Failure(WALK_ORDER_REFUSED.format(problem=problem, program=Path(__file__).resolve(), step=step,
                                                top=shlex.quote(str(top))))
    if stamped != text:
        document.write_text(stamped, encoding="utf-8")
    count = walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units)
    return count, order, summary, units, placing


def walk_document_order(walk_finder, text, units, parser, document, today):
    """Return (the items of units in walk-document order, the summary item or None, the placing of the unshown
    items), as walk_document_items' docstring says."""
    lines = text.split("\n")
    order, summary = [], None
    for unit in units:
        unit_numbers, first = unit[0], unit[3]
        keys = [first] if walk_finder.approval_walk_unit_is_unnumbered_item(unit) else unit_numbers
        order += [key for key in keys if key not in order]
        if keys and SUMMARY_HEADING.search(
                walk_finder.approval_walk_item_heading_with_deferred_note_removed(lines[first])):
            summary = keys[0]
    return order, summary, unshown_items_placing(walk_finder, text, units, parser, document, today)


class WalkOrderUnusable(Exception):
    """An unshown item's category, waits-on or first-entered lines that do not let it be placed; its argument says
    which."""


def unshown_units(walk_finder, units, lines):
    """The unnumbered units of units, the summary item's left out."""
    return [unit for unit in units if walk_finder.approval_walk_unit_is_unnumbered_item(unit)
            and not SUMMARY_HEADING.search(walk_finder.approval_walk_item_heading_with_deferred_note_removed(
                lines[unit[3]]))]


def heading_title(walk_finder, line):
    """The title of an item heading: its text after the `##` marks and any running count, deferred note and
    backticks left out, with its spaces squeezed, in lower case; a `#approval_walk_item_waits_on` line's title is
    read the same way."""
    # Without backticks, since the waits-on line's reading drops a closing one along with closing emphasis marks.
    heading = walk_finder.approval_walk_item_heading_with_deferred_note_removed(line).replace("`", "")
    parts = UNNUMBERED_HEADING_PARTS.match(heading)
    title = parts[2] if parts else heading.lstrip("#")
    title = re.sub(r"^[*_\s]*items?\s+[\d.]+(?:\s*(?:,|&|\band\b|\bto\b|-|–)\s*[\d.]+)*\s+of\s+\d+\b"
                   r"[*_\s:.\-–—]*", "", title, flags=re.I)
    return squeezed(title.strip(" *_")).lower()


def unshown_items_first_entered_stamped(walk_finder, text, units, parser, today):
    """text with a line `#approval_walk_item_first_entered today` written right under the heading of each unshown item
    that has no such line."""
    lines = text.split("\n")
    prose = walk_finder.prose_lines(text, parser)
    unstamped = [unit[3] for unit in unshown_units(walk_finder, units, lines)
                 if not any(WALK_FIRST_ENTERED_LINE.match(line) for line in prose[unit[3] + 1:unit[4]])]
    for first in reversed(unstamped):
        # The blank line after it keeps a next line, such as indented code, from joining the tag's paragraph.
        after = [""] if first + 1 < len(lines) and lines[first + 1].strip() else []
        lines[first + 1:first + 1] = ["", f"{WALK_FIRST_ENTERED_TAG} {today}"] + after
    return "\n".join(lines)


def unshown_items_placing(walk_finder, text, units, parser, document, today):
    """Return {heading line of an unshown item: ((category rank, first-entered date, heading line), {items it waits
    on})}, an item it waits on given as walk_document_items gives items; raise WalkOrderUnusable when an unshown
    item has no category tag, more than one, or one not in WALK_CATEGORIES, an unreadable first-entered date, or a
    `#approval_walk_item_waits_on` title that no other item heading has, or when unshown items wait on each other in
    a circle."""
    lines = text.split("\n")
    prose = walk_finder.prose_lines(text, parser)
    titles = {}
    for unit in units:
        key = unit[3] if walk_finder.approval_walk_unit_is_unnumbered_item(unit) else None
        for item in [key] if key is not None else unit[0]:
            titles.setdefault(heading_title(walk_finder, lines[unit[3]]), []).append(item)
    placing = {}
    for unit in unshown_units(walk_finder, units, lines):
        first, end = unit[3], unit[4]
        item = f"the item `{lines[first].strip()}` in {document}"
        tags = [tag for line in prose[first + 1:end] if WALK_CATEGORY_LINE.match(line)
                for tag in WALK_CATEGORY_TAGS_IN_LINE.findall(line)]
        if not tags:
            raise WalkOrderUnusable(CATEGORY_MISSING.format(item=item))
        if len(tags) > 1:
            raise WalkOrderUnusable(CATEGORY_DOUBLED.format(item=item, tags=", ".join(f"`{tag}`" for tag in tags)))
        category = tags[0][len(WALK_CATEGORY_TAG):]
        if category not in WALK_CATEGORIES:
            raise WalkOrderUnusable(CATEGORY_UNKNOWN.format(item=item, tag=tags[0]))
        entered = next((match for match in map(WALK_FIRST_ENTERED_LINE.match, prose[first + 1:end]) if match), None)
        try:
            date = datetime.date.fromisoformat(entered[1]).isoformat() if entered else today
        except ValueError:
            raise WalkOrderUnusable(FIRST_ENTERED_UNREADABLE.format(item=item, line=entered[0].strip()))
        waits_on = set()
        for match in filter(None, map(WALK_WAITS_ON_LINE.match, prose[first + 1:end])):
            title = heading_title(walk_finder, "## " + match[1].lstrip("# "))
            named = [other for other in titles.get(title, []) if other != first]
            if not named:
                raise WalkOrderUnusable(WAITS_ON_UNKNOWN.format(item=item, title=match[1]))
            waits_on.update(named)
        placing[first] = ((WALK_CATEGORIES.index(category), date, first), waits_on)
    circle = waiting_circle(placing)
    if circle:
        raise WalkOrderUnusable(WAITS_ON_CIRCLE.format(
            items=", ".join(f"`{lines[item].strip()}`" for item in circle) + f" in {document}"))
    return placing


def waiting_circle(placing):
    """The items of a circle of unshown items each waiting on the next, in walk-document order, or []."""
    state = {}

    def visit(item, path):
        state[item] = "visiting"
        for other in sorted(other for other in placing[item][1] if other in placing):
            if state.get(other) == "visiting":
                return path[path.index(other):]
            if other not in state:
                found = visit(other, path + [other])
                if found:
                    return found
        state[item] = "done"
        return []

    for item in sorted(placing):
        if item not in state:
            found = visit(item, [item])
            if found:
                return sorted(found)
    return []


def unshown_items_in_walk_order(items, placing):
    """items, unshown items of placing, in the order the walk shows them: an item after every one of items it
    waits on, and otherwise the item whose own sort key, or the key of an item waiting on it directly or through
    others, is lowest first, so an item that unblocks another comes as early as that other item would."""
    waiting_on = {item: placing[item][1] & set(items) for item in items}
    effective = {}

    def lowest_key(item, seen=()):
        if item not in effective:
            dependents = [other for other in items if item in waiting_on[other] and other not in seen]
            effective[item] = min([placing[item][0]] + [lowest_key(other, seen + (item,)) for other in dependents])
        return effective[item]

    ordered, remaining = [], list(items)
    while remaining:
        ready = [item for item in remaining if not waiting_on[item] & set(remaining)]
        chosen = min(ready, key=lambda item: (lowest_key(item), placing[item][0]))
        ordered.append(chosen)
        remaining.remove(chosen)
    return ordered


def unshown_items_gathered_behind_chosen(walk_finder, minutes, chosen, units, placing, parser, answered_numbers,
                                         total):
    """Rewrite the walk-document so that the unshown items placing holds stand together where the first of them
    stands, or after the whole item, sub-steps and withdrawn versions included, of the answered items,
    answered_numbers, when the first of them stands above it, their unit chosen by total, the `#next_to_present`
    line's M, as waiting_item_units chooses between two headings for one item, chosen first and the others in the
    order unshown_items_in_walk_order gives; return chosen's heading line and the units of the rewritten
    walk-document. A later close walks on from chosen, so the items still unshown
    come next, and items numbered later stand in the order they were shown."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    spans = {unit[3]: (unit[3], unit[4]) for unit in units if unit[3] in placing}
    rest = unshown_items_in_walk_order([item for item in placing if item != chosen], placing)
    # close's walk_document_items already ran waiting_item_units on the waiting items, which hold answered_numbers,
    # with this total, so it cannot raise UnusableRange here.
    _, answered_units = walk_finder.waiting_item_units(document, None, answered_numbers, total, parser, units)
    insert_line = walk_finder.approval_walk_document_new_item_insert_line_number_past_whole_item_sub_steps_and_withdrawn_versions
    start = max([min(spans)] + [insert_line(units, unit, len(lines)) for unit in answered_units])
    kept = [(index, line) for index, line in enumerate(lines)
            if not any(first <= index < end for first, end in spans.values())]
    joined = []
    chosen_line = None
    # An item whose last line is not blank, moved above a `**Item N of M**` paragraph, would make that
    # paragraph a continuation of its own and so hide the numbered item; a blank line at every join keeps
    # each block a paragraph of its own.
    for item, block in ([(None, [line for index, line in kept if index < start])]
                        + [(item, lines[spans[item][0]:spans[item][1]]) for item in [chosen] + rest]
                        + [(None, [line for index, line in kept if index >= start])]):
        if joined and block and joined[-1].strip() and block[0].strip():
            joined.append("")
        if item == chosen:
            chosen_line = len(joined)
        joined.extend(block)
    text = "\n".join(joined)
    gathered_units = walk_finder.item_unit_spans(text, parser)
    if sorted(unit[0] for unit in gathered_units) != sorted(unit[0] for unit in units):
        raise Failure(GATHERING_WOULD_LOSE_AN_ITEM.format(document=document, minutes=minutes))
    document.write_text(text, encoding="utf-8")
    return chosen_line, gathered_units


def numbered_heading(heading, number, total):
    """The unnumbered item heading `## <title>` with the running count `Item number of total: ` before its title."""
    marks, title = UNNUMBERED_HEADING_PARTS.match(heading).groups()
    return NUMBERED_HEADING.format(marks=marks, number=number, total=total, title=title)


def unnumbered_item_numbered(walk_finder, minutes, first, units):
    """Write the running count `Item K of M: ` into the unnumbered item heading on line first of the walk-document,
    K and M as the walk finder's approval_walk_next_unnumbered_item_number and approval_walk_item_total_shown_and_waiting_counted_from_walk_document give them for
    units, the walk-document's units; return K."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    number = walk_finder.approval_walk_next_unnumbered_item_number(units)
    lines[first] = numbered_heading(lines[first], number, walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units))
    document.write_text("\n".join(lines), encoding="utf-8")
    return number


def unnumbered_item_text_once_numbered(walk_finder, minutes, first, units, number, total):
    """Return the text of the unnumbered item whose heading is on line first of the walk-document, as item_text
    will give it once unnumbered_item_numbered has written `Item number of total: ` into that heading."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    lines = document.read_text(encoding="utf-8").split("\n")
    end = next(unit[4] for unit in units if unit[3] == first)
    lines[first] = numbered_heading(lines[first], number, total)
    return "\n".join(lines[first:end]).strip()


def new_item_for_held_answer_numbered(walk_finder, minutes, value, answered_numbers, parser, placing, summary,
                                      decided):
    """Number the unnumbered item right after the answered items' unit in the walk-document, as the close step's
    HOLD_ANSWER_FLAG asks, and return the `#next_to_present` value naming it; raise Failure, writing nothing, when
    the unit right after is not unnumbered, or when it waits on an item still to come: an unshown item of placing,
    the walk-document's placing of its unshown items, the summary item, or a numbered item that is neither answered
    now nor among decided, the items the minutes decide, an item whose sub-steps are all answered now or decided
    counting as decided."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    units = walk_finder.item_unit_spans(text, parser)
    try:
        _, answered_units = walk_finder.waiting_item_units(document, value, answered_numbers, None, parser, units)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last `#next_to_present` line in {minutes}, `{value}`: {problem}")
    after = units.index(answered_units[-1]) + 1
    if after == len(units) or not walk_finder.approval_walk_unit_is_unnumbered_item(units[after]):
        found = (f"`{text.split(NEWLINE)[units[after][3]].strip()}`" if after < len(units)
                 else "none, since it is the last item")
        raise Failure(NO_UNNUMBERED_ITEM_AFTER.format(document=document, item=" and ".join(answered_numbers),
                                                      found=found))
    lines = text.split(NEWLINE)
    decided = decided_with_items_whose_sub_steps_are_all_decided(
        [number for unit in units for number in unit[0]], decided | set(answered_numbers),
        held_answers_unresolved(walk_finder, minutes.read_text(encoding="utf-8"), parser))
    # An unnumbered item is keyed by its heading's line index, an int; a numbered one by its number, a str.
    to_come = sorted((other for other in placing.get(units[after][3], (None, set()))[1]
                      if other in placing or other == summary
                      or (isinstance(other, str) and other not in decided)),
                     key=str)
    if to_come:
        raise Failure(HELD_NEW_ITEM_WAITS_ON_UNSHOWN.format(
            document=document, item=" and ".join(answered_numbers), new_item=f"`{lines[units[after][3]].strip()}`",
            waited_on=", ".join(f"`{lines[other].strip()}`" if isinstance(other, int) else f"item {other}"
                                for other in to_come)))
    number = unnumbered_item_numbered(walk_finder, minutes, units[after][3], units)
    return f"item {number} of {walk_finder.approval_walk_item_total_shown_and_waiting_counted_from_walk_document(units)}"


def deferred_item_heading_noted(walk_finder, minutes, numbers, total, parser, noted=True):
    """With noted, put the deferred note right after the running count of the walk-document heading that names
    exactly the items numbered, whatever M it gives, unless it already holds the note; return the lines to print
    when no such heading exists. Without noted, take the note out of that heading, if it holds it, and return no
    lines. Of two such headings, as in a walk-document renumbered before numbers were never reused, the one whose
    M is total, the `#next_to_present` line's, is taken, or the first when none or both are."""
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    text = document.read_text(encoding="utf-8")
    lines = text.split("\n")
    note = walk_finder.APPROVAL_WALK_DEFERRED_ITEM_HEADING_NOTE_AFTER_RUNNING_COUNT
    naming = [unit for unit in walk_finder.item_unit_spans(text, parser) if unit[0] == numbers]
    picked = [unit for unit in naming if unit[1] == total]
    for _, _, _, first, _ in (picked if len(picked) == 1 else naming)[:1]:
        heading = lines[first]
        if noted and note not in heading:
            end = HEADING_COUNT_IN_LINE.search(heading).end()
            lines[first] = f"{heading[:end]} {note}{heading[end:]}"
        elif not noted:
            lines[first] = walk_finder.approval_walk_item_heading_with_deferred_note_removed(heading)
        if lines[first] != heading:
            document.write_text("\n".join(lines), encoding="utf-8")
        return []
    return [CLOSE_DEFERRED_HEADING_NOT_NOTED.format(document=document, note=note)] if noted else []


def minutes_record(walk_finder, minutes_text, parser):
    """Return (the item numbers a line this program wrote decides, a Counter of how many lines this program
    wrote defer each item); every other line, an agent's note included, records nothing."""
    words, deferrals = minutes_ruling_words(walk_finder, minutes_text, parser)
    return set(words), deferrals


def minutes_ruling_words(walk_finder, minutes_text, parser):
    """Return ({each item number a line this program wrote decides: the `#ruling_given` word of the last such
    line}, a Counter of how many lines this program wrote defer each item), read as minutes_record reads."""
    words, deferrals = {}, collections.Counter()
    for line in walk_finder.prose_lines(minutes_text, parser):
        match = PROGRAM_LINE_ITEMS.match(line)
        if not match:
            continue
        rest = line[match.end():]
        decides = [index for index, pattern in enumerate(DECIDING_LINES) if pattern.match(rest)]
        if not decides and not any(pattern.match(rest) for pattern in DEFERRING_LINES):
            continue
        try:
            items, _ = walk_finder.parse_items(match[1])
        except walk_finder.UnusableRange:
            continue
        if decides:
            word = DECIDING_LINE_WORDS[decides[0]] or RULING_GIVEN_WORDS[rest.rsplit(" ", 1)[-1]]
            words.update(dict.fromkeys(items, word))
        else:
            deferrals.update(items)
    return words, deferrals


def held_answers(walk_finder, minutes_text, parser):
    """Return [(held items' text, their numbers, new items' text, their numbers)] for each held-answer line."""
    holds = []
    for line in walk_finder.prose_lines(minutes_text, parser):
        match = HELD_ANSWER_LINE.match(line)
        if not match:
            continue
        try:
            holds.append((match[1], set(walk_finder.parse_items(match[1])[0]), match[2],
                          set(walk_finder.parse_items(match[2])[0])))
        except walk_finder.UnusableRange:
            continue
    return holds


def held_answers_unresolved(walk_finder, minutes_text, parser):
    """Return the item numbers a held-answer line holds and no line this program wrote decides."""
    decided, _ = minutes_record(walk_finder, minutes_text, parser)
    return {number for _, held_numbers, _, _ in held_answers(walk_finder, minutes_text, parser)
            for number in held_numbers} - decided


def items_decided_through_sub_steps(items, words, unresolved=frozenset()):
    """Return {item: its `#ruling_given` word} for each item of items, such as 3, not in words, the decided items
    with their words, nor in unresolved, the items whose held answer is unresolved, that has sub-steps among items,
    such as 3.1 and 3.2, every one of them in words or, deeper, decided through its own sub-steps; an item is never
    decided through its parent. Its word is its sub-steps' one word once moved_on is left out, moved_on when that
    leaves none, and part_answers when it leaves more than one."""
    words, inferred = dict(words), {}
    numbered = [item for item in items if isinstance(item, str)]
    # Deepest first, so a sub-step decided through its own sub-steps, as 5.2 through 5.2.1, counts for its parent.
    for item in sorted(numbered, key=lambda number: -number.count(".")):
        if item in words or item in unresolved:
            continue
        sub_steps = [other for other in numbered if other.rsplit(".", 1)[0] == item and other != item]
        if sub_steps and all(other in words for other in sub_steps):
            ruled = {words[other] for other in sub_steps} - {RULING_GIVEN_MOVED_ON}
            words[item] = inferred[item] = (RULING_GIVEN_MOVED_ON if not ruled else ruled.pop() if len(ruled) == 1
                                            else RULING_GIVEN_PART_ANSWERS)
    return inferred


def decided_with_items_whose_sub_steps_are_all_decided(items, decided, unresolved=frozenset()):
    """decided, plus each item items_decided_through_sub_steps finds decided through its sub-steps."""
    return set(decided) | set(items_decided_through_sub_steps(items, dict.fromkeys(decided), unresolved))


def next_item(order, summary, answered_numbers, waiting_numbers, decided, deferrals, placing=None,
              unresolved=frozenset()):
    """Return the item numbers the `#next_to_present` line must name next, or [] when the minutes record
    every item.

    Items shown with the answered one that the minutes do not record yet stay waiting. Otherwise the walk
    goes through the walk-document's items in order, as walk_document_items gives them, unnumbered ones
    included, an item deferred once and not decided moved to just
    before the summary item, or to the end when there is none, and names the first item the minutes do
    not record. It starts at the last answered item, or, when that item was just deferred, at the first
    item after it in the walk-document that is not deferred, and goes round once. The unshown items placing
    holds come together, in the order unshown_items_in_walk_order gives, where the first of them comes on that
    round, or just before the summary item or a deferred item when one of those comes sooner; an item is passed
    over while an item it waits on is still to come. An item whose sub-steps are all decided counts as decided,
    unless it is in unresolved, as decided_with_items_whose_sub_steps_are_all_decided says.
    """
    placing = placing or {}
    decided = decided_with_items_whose_sub_steps_are_all_decided(order, decided, unresolved)
    recorded = {item for item in order if item in decided or deferrals[item] > 1}
    still_waiting = [item for item in waiting_numbers if item not in recorded and item not in answered_numbers]
    if still_waiting:
        return still_waiting
    waiting_deferred = [item for item in order if item not in recorded and item in deferrals]
    in_place = [item for item in order if item not in waiting_deferred]
    cut = in_place.index(summary) if summary in in_place else len(in_place)
    walk = in_place[:cut] + waiting_deferred + in_place[cut:]
    answered = [index for index, item in enumerate(order) if item in answered_numbers]
    anchors = [item for item in order[answered[-1]:] if item in in_place] if answered else []
    start = walk.index(anchors[0]) if anchors else 0
    to_come = [item for item in walk[start:] + walk[:start] if item not in recorded]
    unshown = [item for item in to_come if item in placing]
    if unshown:
        late = [index for index, item in enumerate(to_come) if item == summary or item in waiting_deferred]
        cut = min([to_come.index(unshown[0])] + late)
        shown = [item for item in to_come if item not in placing]
        before = len([item for item in to_come[:cut] if item not in placing])
        to_come = shown[:before] + unshown_items_in_walk_order(unshown, placing) + shown[before:]
    return [item for item in to_come if not placing.get(item, (None, set()))[1] & set(to_come)][:1]


def held_items_decided_with(walk_finder, minutes, parser, answered_numbers, item, outcome):
    """Return the close lines that give outcome to each item whose answer the minutes hold for the answered
    items, directly or through a chain of held items, and that no close line decides yet."""
    text = minutes.read_text(encoding="utf-8")
    decided, _ = minutes_record(walk_finder, text, parser)
    holds = held_answers(walk_finder, text, parser)
    # An item held for an item this close decides is decided too, so it releases the items held for it in turn.
    released, lines = set(answered_numbers), []
    progress = True
    while progress:
        progress = False
        for held_text, held_numbers, new_text, new_numbers in holds:
            if new_numbers <= released and not held_numbers <= decided:
                decided.update(held_numbers)
                released.update(held_numbers)
                progress = True
                ruled_by = item if new_numbers <= set(answered_numbers) else new_text
                lines.append(CLOSE_ALREADY_DECIDED_MINUTES.format(
                    item=held_text, ruling=HELD_RULING.format(new_item=ruled_by), outcome=outcome))
    return lines


def gh_failure(command, top, gh_program, timeout):
    """Run gh with command in top; return (its stdout, None), or (None, what went wrong) when it cannot be run,
    exits nonzero or outlasts timeout."""
    try:
        result = subprocess.run([gh_program, *command], cwd=top, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"did not end within {timeout} seconds"
    except OSError as error:
        return None, f"could not be run: {error}"
    if result.returncode != 0:
        return None, f"exited {result.returncode}: {squeezed(result.stderr.strip()) or 'it printed nothing on stderr'}"
    return result.stdout, None


def pull_requests_held_on(lines, top, gh_program, timeout):
    """Return ({held line: [the open pull requests whose review holds that line on a line of its own]}, None), or
    (None, what went wrong) when the open pull requests cannot be listed."""
    output, error = gh_failure(HELD_PULL_REQUESTS_LIST, top, gh_program, timeout)
    if error:
        return None, error
    try:
        pull_requests = json.loads(output)
        held = {line: [] for line in lines}
        for pull_request in pull_requests:
            found = {line.strip() for review in pull_request["reviews"] for line in (review["body"] or "").split("\n")}
            for line in lines:
                if line in found:
                    held[line].append(pull_request["number"])
    except (ValueError, TypeError, KeyError) as error:
        return None, f"printed what is not a list of pull requests with their reviews: {error!r}"
    return held, None


def ruling_given_comments_posted(walk_name, rulings, top, gh_program, timeout):
    """Post a `#ruling_given` comment on every open pull request held on the ruling of each item of rulings,
    [(item number, the word)]; return the lines to print, and whether any comment
    could not be posted."""
    lines = {HELD_ON_RULING_LINE.format(walk=walk_name, number=number): (number, word) for number, word in rulings}
    held, error = pull_requests_held_on(list(lines), top, gh_program, timeout)
    in_top = f"cd {shlex.quote(str(top))} && gh "
    output, failed = [], bool(error)
    for line, (number, word) in lines.items():
        body = RULING_GIVEN_LINE.format(walk=walk_name, number=number, word=word)
        values = {"number": number, "walk": walk_name, "word": word}
        if error:
            list_command = (in_top + shlex.join(HELD_PULL_REQUESTS_LIST) + " --jq "
                            + shlex.quote(HELD_PULL_REQUESTS_BY_HAND_JQ.format(line=json.dumps(line))))
            output += [text.format(error=error, list_command=list_command, **values,
                                   comment_command=in_top + "pr comment <number> --body " + shlex.quote(body))
                       for text in RULING_GIVEN_LOOKUP_FAILED]
            continue
        for pull_request in held[line]:
            command = ("pr", "comment", str(pull_request), "--body", body)
            _, post_error = gh_failure(command, top, gh_program, timeout)
            if post_error:
                failed = True
                output += [text.format(error=post_error, pull_request=pull_request, **values,
                                       comment_command=in_top + shlex.join(command))
                           for text in RULING_GIVEN_POST_FAILED]
            else:
                output.append(RULING_GIVEN_POSTED.format(number=number, pull_request=pull_request, ruling=body))
    return output, failed


def close(arguments):
    walk_finder = load_walk_finder()
    top, minutes, value, parser = the_open_walk(walk_finder, arguments.cwd)
    item, answered, statuses = last_answer(walk_finder, minutes, parser)
    waiting, waiting_numbers, total = waiting_items(walk_finder, value, minutes)
    try:
        answered_numbers, _ = walk_finder.parse_items(item)
    except walk_finder.UnusableRange as problem:
        raise Failure(f"the last answer line in {minutes}, `{item}`, {problem}.")
    if arguments.hold_answer_until_new_item_answered:
        # Placed first, unstamped, so an unplaceable walk-document, or a new item that waits on one not yet shown,
        # numbers nothing and writes nothing.
        _, _, summary, _, placing = walk_document_items(walk_finder, minutes, value, waiting_numbers, total, parser,
                                                        f"close {HOLD_ANSWER_FLAG}", top, stamp=False)
        decided, _ = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
        value = new_item_for_held_answer_numbered(walk_finder, minutes, value, answered_numbers, parser, placing,
                                                  summary, decided)
        waiting, waiting_numbers, total = waiting_items(walk_finder, value, minutes)
    if not set(answered_numbers) <= set(waiting_numbers):
        append_to_minutes(minutes, [CLOSE_HELD_MINUTES.format(item=item, new_item=waiting),
                                    NEXT_MARKER_LINE.format(value=value)])
        output = ([line.format(item=item, new_item=waiting) for line in CLOSE_HELD_LINES] + statuses
                  + [CLOSE_HELD_NEXT.format(item=item, new_item=waiting, command=READ_STEP_COMMAND.format(
                      program=Path(__file__).resolve(), flags="", top=shlex.quote(str(top))))])
        print("\n".join(output))
        return 0
    count, order, summary, units, placing = walk_document_items(walk_finder, minutes, value, waiting_numbers, total,
                                                                parser, "close", top)
    # Only a plain decision passes to the items held for this one; after a deferral, a move on or answers to parts
    # they stay waiting, so the walk shows them to the user.
    held_outcome = None
    if answered == MOVED_ON:
        recorded, word = CLOSE_MOVED_ON_NO_DECISION_MINUTES.format(item=item), RULING_GIVEN_MOVED_ON
        output = [line.format(item=item) for line in CLOSE_MOVED_ON_LINES]
    elif answered == DEFERRED:
        _, deferrals = minutes_record(walk_finder, minutes.read_text(encoding="utf-8"), parser)
        again = any(deferrals[number] for number in answered_numbers)
        recorded = (CLOSE_DEFERRED_AGAIN_MINUTES if again else CLOSE_DEFERRED_MINUTES).format(item=item)
        lines = CLOSE_DEFERRED_AGAIN_LINES if again else CLOSE_DEFERRED_LINES
        word = RULING_GIVEN_DEFERRED
        # A walk with no summary item puts a deferred item last, where it needs no note; an item deferred again
        # leaves the walk, so the note that says where it went is taken out.
        noted = not again and summary is not None
        output = ([line.format(item=item) for line in lines]
                  + deferred_item_heading_noted(walk_finder, minutes, answered_numbers, total, parser, noted)
                  + statuses)
    elif answered.startswith(MOVED_ON_PREFIX):
        recorded = CLOSE_MOVED_ON_MINUTES.format(item=item, reason=answered[len(MOVED_ON_PREFIX):])
        word = RULING_GIVEN_MOVED_ON
        output = [line.format(item=item) for line in CLOSE_NOT_SHOWN_LINES]
    elif answered.startswith(ALREADY_DECIDED_PREFIX):
        held_outcome = OUTCOMES[APPROVED]
        recorded = CLOSE_ALREADY_DECIDED_MINUTES.format(item=item, ruling=answered[len(ALREADY_DECIDED_PREFIX):],
                                                      outcome=held_outcome)
        output = ([line.format(item=item) for line in CLOSE_NOT_SHOWN_LINES] + [CLOSE_ALREADY_DECIDED_CHANGE]
                  + statuses + list(CLOSE_TOOK_EFFECT_NEXT))
    else:
        parts = PART_IN_ANSWER.findall(answered)
        if parts:
            recorded = CLOSE_PARTS_TOOK_EFFECT_MINUTES.format(item=item, parts=", ".join(
                f"part {number} {word} {OUTCOMES[word]}" for number, word in parts))
            word = RULING_GIVEN_PART_ANSWERS
        else:
            held_outcome = OUTCOMES[DISAPPROVED if answered == DISAPPROVED else APPROVED]
            recorded = CLOSE_TOOK_EFFECT_MINUTES.format(item=item, answered=answered, outcome=held_outcome)
        output = ([line.format(item=item) for line in CLOSE_TOOK_EFFECT_LINES] + statuses
                  + list(CLOSE_TOOK_EFFECT_NEXT))
    if answered != DEFERRED:
        deferred_item_heading_noted(walk_finder, minutes, answered_numbers, total, parser, noted=False)
    before = minutes.read_text(encoding="utf-8")
    inferred_before = items_decided_through_sub_steps(order, minutes_ruling_words(walk_finder, before, parser)[0],
                                                      held_answers_unresolved(walk_finder, before, parser))
    append_to_minutes(minutes, [recorded])
    word = RULING_GIVEN_WORDS[held_outcome] if held_outcome else word
    rulings = [(number, word) for number in answered_numbers]
    if held_outcome:
        held = held_items_decided_with(walk_finder, minutes, parser, answered_numbers, item, held_outcome)
        if held:
            append_to_minutes(minutes, held)
        for line in held:
            deferred_item_heading_noted(walk_finder, minutes, walk_finder.parse_items(line.split(": ")[0])[0], total,
                                        parser, noted=False)
        output += [CLOSE_HELD_DECIDED.format(item=item, held=line.split(": ")[0]) for line in held]
        rulings += [(number, word) for line in held
                    for number in walk_finder.parse_items(line.split(": ")[0])[0]]
    after = minutes.read_text(encoding="utf-8")
    words, deferrals = minutes_ruling_words(walk_finder, after, parser)
    unresolved = held_answers_unresolved(walk_finder, after, parser)
    # An item this close decides through its last sub-step gets its ruling too, so a pull request held on it moves.
    rulings += [(number, inferred_word) for number, inferred_word
                in items_decided_through_sub_steps(order, words, unresolved).items() if number not in inferred_before]
    numbers = next_item(order, summary, answered_numbers, waiting_numbers, set(words), deferrals, placing,
                        unresolved)
    if numbers and isinstance(numbers[0], int):
        first = numbers[0]
        if first in placing:  # Not the summary item, which stays where it is.
            first, units = unshown_items_gathered_behind_chosen(walk_finder, minutes, first, units, placing, parser,
                                                                answered_numbers, total)
        numbers = [unnumbered_item_numbered(walk_finder, minutes, first, units)]
    named = items_named(numbers, count)
    append_to_minutes(minutes, [NEXT_MARKER_LINE.format(value=named if numbers else CLOSED_MARKER_VALUE)])
    if numbers:
        not_started = start_read_ahead_of_item_after(walk_finder, top, minutes, parser, numbers, count,
                                                     arguments.fast_read_program)
        output += [not_started] if not_started else []
    output.append(CLOSE_READ_NEXT_ITEM.format(next_item=named, command=READ_STEP_COMMAND.format(
        program=Path(__file__).resolve(), flags="", top=shlex.quote(str(top)))) if numbers else CLOSE_NO_NEXT_ITEM)
    # Last, so a gh that fails or hangs cannot keep the answer or the next item out of the minutes.
    ruling_lines, ruling_failed = ruling_given_comments_posted(
        minutes.name[:-len(walk_finder.MINUTES_SUFFIX)], rulings, top, arguments.gh_program, arguments.gh_timeout)
    print("\n".join(output + ruling_lines))
    return 2 if ruling_failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("check", "close", WAITING_ITEM_READ_STEP, READ_AHEAD_WORKER_STEP))
    answer = parser.add_mutually_exclusive_group()
    answer.add_argument("--obvious", action="store_true", help="check: the answer was AO, approve as obvious")
    answer.add_argument("--after-advisor", action="store_true",
                        help="check: the answer was Aa, approve after an advisor check")
    answer.add_argument("--disapproved", action="store_true", help="check: the answer was D, disapprove; reads only the `#new_if_d` texts")
    answer.add_argument("--deferred", action="store_true", help="check: the answer was Z, defer")
    answer.add_argument("--moved-on-no-decision", action="store_true",
                        help="check: the user's reply moved on from an item that asks no decision, such as a "
                             "summary item; records no decision")
    answer.add_argument("--option", type=int, choices=OPTION_NUMBERS,
                        help="check: the answer was O2 or O3, approving the item's \"Option N\" paragraph")
    answer.add_argument("--already-decided", metavar="USER_RULING",
                        help="check: not shown, since an earlier user-ruling decides the item as it recommends; "
                             "USER_RULING cites it")
    answer.add_argument(NOW_OVER_LATER_FLAG, action="store_true",
                        help="check: not shown, since its only choice is whether to build something now or later "
                             "and it recommends now; records it as already decided by the user's answer to item 42 "
                             "of walk-me-through-skill-refactor-approval-walk-2026-11-02, \"If the agents recommend "
                             "now versus later, I'm always for now.\"; refused for an item with parts, Option "
                             "paragraphs or `#new_if_d` texts")
    answer.add_argument("--moved-on", metavar="REASON",
                        help="check: not shown, and the walk moves on from the item with no decision, for REASON")
    answer.add_argument("--part-answer", type=part_answer, action="append", metavar="N=ANSWER",
                        help="check: part N of the item was answered ANSWER, A, AO or D; give it once for each part")
    answer.add_argument("--not-asked", type=not_asked_kind, metavar="KIND",
                        help="check: the user is not asked; settle the item as kind KIND, 1 to 6, of the "
                             "walk-me-through skill's list of items that need no answer, if its evidence lines pass, "
                             "or, as `none`, an item of no kind whose case against is rated none, or weak with "
                             "a case against that names only cost")
    parser.add_argument("--user-reply-as-typed", metavar="REPLY",
                        help="check: the user's reply exactly as he typed it, written into the minutes beside the "
                             "answer; needed for every answer but --not-asked, --already-decided, "
                             f"{NOW_OVER_LATER_FLAG} and --moved-on")
    parser.add_argument(HOLD_ANSWER_FLAG, action="store_true",
                        help="close: a fast-read finding raised the new item written right after the answered "
                             "one; number it and hold the answer until the user answers it")
    parser.add_argument(AFTER_FIXES_FLAG, action="store_true",
                        help=f"{WAITING_ITEM_READ_STEP}: you changed the item since its last cold-read-fast-read; "
                             "read it again only when the change touches a fact")
    parser.add_argument("--text-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--item", help=argparse.SUPPRESS)
    parser.add_argument("--name", help=argparse.SUPPRESS)
    parser.add_argument(ITEM_NUMBER_PREDICTED_FLAG, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cwd", default=os.getcwd(), help="a directory in the walk's checkout")
    parser.add_argument("--cold-read-records", type=Path, action="append",
                        help="a cold-read-records directory to search instead of the defaults; repeatable")
    parser.add_argument("--fast-read-program", type=Path, default=FAST_READ_PROGRAM)
    parser.add_argument("--counts-log", type=Path)
    parser.add_argument("--gh-program", default=GH_PROGRAM, help=argparse.SUPPRESS)
    parser.add_argument("--gh-timeout", type=float, default=GH_TIMEOUT_SECONDS, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    try:
        return {"check": check, "close": close, WAITING_ITEM_READ_STEP: waiting_item_read,
                READ_AHEAD_WORKER_STEP: read_ahead_worker}[arguments.step](arguments)
    except Failure as failure:
        print(f"{PROGRAM} {arguments.step}: {failure.args[0]}", file=sys.stderr)
        return 1
    except FastReadFailed as failure:
        print("\n".join([failure.args[0]] + [line.format(program=Path(__file__).resolve(),
                                                          flags=check_flags(arguments))
                                              for line in FAST_READ_FAILED_LINES]))
        return 1


if __name__ == "__main__":
    sys.exit(main())
