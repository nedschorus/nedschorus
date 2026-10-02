# What the ghi-write-tool says when ghi-info raises a ruling question

Before create-GHI files an issue, or edit-GHI lands an edit, the ghi-write-tool (`scripts/ghi-issue-write.py`) asks ghi-info whether an open issue already covers the draft. ghi-info can answer with a ruling question instead: the draft may conflict with something the user ruled, or ghi-info cannot tell whether an old ruling still applies. Only the user can answer a ruling question, so the tool stops the write until the user has answered. A run stopped by a ruling question exits 67 and writes nothing: no issue, no branch, no pull request. ghi-info raises at most one ruling question per run.

ghi-info starts each ruling question with the number of the issue that holds the ruling. For example, from ghi-info:

> #783 the ruling that a closed issue is frozen may not cover an issue that is reopened

Do what the user's answer says. If the answer changes the draft, change it before you rerun; if the answer is that the write should not happen, do not rerun. When the answer lets the write go on, rerun the same command with `--ruling-question-answered 783`. The rerun asks ghi-info again. If ghi-info raises a ruling question again, the write goes on only if that question names an issue number you gave; if ghi-info raises none, the write goes on as any other write does. If ghi-info now raises a question about a different issue, the run stops again, and you ask the user that question too.

If `scripts/ghi-info-ask.py` signals a ruling question but the question itself never reaches the tool, the tool treats that as no answer from ghi-info. It reports `adjudication skipped: ghi-info did not answer`, and the write goes on.

Each section below gives one text the tool prints or sends, word for word, and when you see it. The tool fills in the words in braces when it prints the text:

- `{issue}`: the issue number at the start of ghi-info's question.
- `{sentence}`: the rest of ghi-info's question, as ghi-info wrote it. The sentence can run over several lines.
- `{rerun_options}`: `--ruling-question-answered` with each issue number you have already given, then with `{issue}`. For example: `--ruling-question-answered 783 --ruling-question-answered 860`.

The user approved the wording of every stop word for word, except each stop's first line, which says what was stopped and why. Those first lines were written after the approval, and the last section of this file lists them. `scripts/ghi-issue-write-test.py` fails when any text here and the tool's text differ.

## The first ruling question

You see this when ghi-info raises a ruling question that starts with an issue number, and you gave no `--ruling-question-answered`. The run exits 67.

The program's name for this text: `RULING_QUESTION_FIRST_STOP_TEMPLATE`. The first line was added after the user's approval.

```text
The write stopped: ghi-info cannot tell whether a ruling of the user's still applies to this draft.
Ask the user this question from ghi-info, word for word: #{issue} — {sentence}
Do not file or edit the issue until the user has answered.
When the user has answered, rerun this command with {rerun_options}.
```

## A ruling question about another issue

You see this on a rerun on which you gave `--ruling-question-answered` with one or more numbers, when ghi-info's question names an issue that is not among them. Your earlier answer still counts: `{rerun_options}` keeps the numbers you already gave and adds the new one. The run exits 67.

The program's name for this text: `RULING_QUESTION_ANOTHER_ISSUE_STOP_TEMPLATE`. The first line was added after the user's approval.

```text
The write stopped again: ghi-info raised a question about a ruling in another issue, one the user has not answered yet.
Ask the user this second question from ghi-info, word for word: #{issue} — {sentence}
Do not file or edit the issue until the user has answered.
When the user has answered, rerun this command with {rerun_options}.
```

## A ruling question that names no issue

You see this when ghi-info's question does not start with an issue number. A number later in the sentence does not count. The tool needs the number to recognise the answer on the rerun, so ask the user which issue holds the ruling, and keep any numbers you already gave. The run exits 67. The rerun goes on only if ghi-info's next question starts with a number you gave. If ghi-info's next question again names no issue, or the user cannot name the issue, the tool cannot go on: tell the user so, and do not rerun again.

The program's name for this text: `RULING_QUESTION_NAMING_NO_ISSUE_STOP_TEMPLATE`. The first line was added after the user's approval.

```text
The write stopped: ghi-info raised a question about a ruling of the user's without naming the issue that holds the ruling, so this program cannot tell when the user has answered it.
Ask the user this question from ghi-info, word for word, and ask which issue holds the ruling: {sentence}
When the user has answered, rerun this command with --ruling-question-answered followed by that issue's number.
```

## The option given without an issue number

You see this when you give `--ruling-question-answered` with nothing after it, or with something that is not an issue number. The usual cause is typing `#783` unquoted: the shell reads everything from `#` onward as a comment, so the tool receives the option with nothing after it. Write the number without `#`. The run exits 64 before ghi-info is asked or anything is written.

The program's name for this text: `RULING_QUESTION_ANSWERED_WITHOUT_NUMBER_MESSAGE`. The first line was added after the user's approval.

```text
Nothing was asked or written: --ruling-question-answered was given without an issue number, so this program cannot tell which question the user answered.
Give --ruling-question-answered the issue number at the start of the question the user answered, for example --ruling-question-answered 783.
```

## The rerun goes on

You see this on a rerun whose ruling question names an issue you gave. This line is a report, not an instruction. The write goes on. The next line is ghi-info's question as `scripts/ghi-info-ask.py` printed it.

The program's name for this text: `RULING_QUESTION_ANSWERED_REPORT_LINE`.

```text
adjudication: ghi-info raised a question about one of the user's rulings; --ruling-question-answered says the user has answered it, so the write proceeds. The question:
```

## What --help says about the option

You see this in `scripts/ghi-issue-write.py create --help` and `scripts/ghi-issue-write.py edit --help`.

The program's name for this text: `RULING_QUESTION_ANSWERED_HELP`.

```text
the issue number at the start of a ruling question from ghi-info that the user has answered; give the option once for each answered question
```

## What the tool asks ghi-info

ghi-info sees this text, not you. It opens every request the tool sends ghi-info, before the draft's title and text. The text offers ghi-info the ruling question for a draft that conflicts with one of the user's rulings.

The program's name for this text: `RULING_QUESTION_REQUEST_REPLY_SHAPES`.

```text
Does an open issue already cover this ground? Reply with exactly one line: `verdict: too-similar #n`, `verdict: related #n,#m`, or `verdict: unrelated`; or, when the draft conflicts with a ruling the user made, `ask-user-about-ruling: #<issue> <one sentence naming the ruling and the doubt>`, where #<issue> is the issue that holds the ruling.
```

## Lines added after the user's approval

The user approved the four texts above that stop or refuse a run, word for word, without these lines. Each line became the first line of its text afterwards, to say what was stopped and why.

```text
The write stopped: ghi-info cannot tell whether a ruling of the user's still applies to this draft.
The write stopped again: ghi-info raised a question about a ruling in another issue, one the user has not answered yet.
The write stopped: ghi-info raised a question about a ruling of the user's without naming the issue that holds the ruling, so this program cannot tell when the user has answered it.
Nothing was asked or written: --ruling-question-answered was given without an issue number, so this program cannot tell which question the user answered.
```
