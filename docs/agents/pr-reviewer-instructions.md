# PR reviewer instructions

This file's text is included verbatim in the prompt of every commissioned PR reviewer.
The instruments that commission reviewers read it at composition time and paste it in —
never point at it, never paraphrase it. (Ruled 2026-08-30: one copy, included everywhere;
a pointed-at rule gets skipped, a paraphrased one drifts.)

## Review scope: code blocks, prose does not

Ruled by the user 2026-08-30, after a one-file deletion PR cost four review rounds and
five hours on prose findings alone. Code needs reviewers; prose already has reviewers,
including the user.

- **Code is reviewed adversarially and blocks.** The class follows the CONTENT, not the
  file it sits in: `scripts/`, `.claude/hooks/`, `.claude/settings.json`, and every shell
  command, invocation, and code block embedded in any markdown file — commands inside
  skills included.
- **Operative prose is gospel — not reviewed, not reported on at all.** `CLAUDE.md`, any
  `CLAUDE.local.md`, everything under `.claude/skills/`. It reaches the PR already
  cold-read and walked with the user; a reviewer improving settled instruction text is a
  regression.
- **All other prose is silent — not a finding, not a remark, not a question.** `docs/`
  entire (designs and issue pair documents included), `nc-queue/`, ledgers, and provenance
  or recovery citations anywhere. Silent rather than non-blocking, because everything a
  reviewer writes gets read and "fixed" by another agent, and those fixes introduce
  defects.
