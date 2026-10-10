# Skills glossary

This page defines the system-terms of this project's skills: the terms they alone use. Every project-term is defined in the project glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`, and this page uses it as defined there.

- **cold-read-cell** — one fresh-agent reviewing one cold-read-target under one reviewer prompt; a cold-read-full-run is six of them.
- **cold-read-fast-read** — one fast-clarify cold-read-cell on the fast cold-read-tier, run by `nc-systems/cold-read/cold-read-fast-read.py`; it is either the whole review or the step before a cold-read-full-run.
- **cold-read-full-run** — the /cold-read skill's run of six cold-read-cells, four on the defect-hunt prompt and two on the terminology prompt, launched by `nc-systems/cold-read/cold-read-grid.py`.
- **cold-read-record** — the directory holding the reports of one cold-read-full-run or cold-read-fast-read, a copy of its cold-read-target taken at launch, and, once its findings are triaged, `triage.md`; shipped to the log-store.
- **cold-read-target** — the document under review; a run that makes a cold-read-record copies it there at launch.
- **cold-read-tier** — the label, `deep`, `second` or `fast`, that sets which model a cold-read-cell asks its agent-binary for, and at what reasoning effort.
- **key-term** — in a cold-read-target, a term that is a project-term or a system-term, or should be one.
- **sanity-check-attack** — one stance the /sanity-check instrument takes on a document, run as its own prompt: the cut-attack (what should be deleted), the mechanization-attack (which English instruction should be code), the fresh-eyes-attack (an independent design built from the problem alone).
- **sanity-check-cell** — one fresh agent running one sanity-check-attack with `claude` or with `codex`; a run is six, the three attacks with `claude` and the three with `codex`.
- **sanity-check-record** — the directory one /sanity-check run leaves behind, holding its reports; kept as a log.
- **sanity-check-request** — the file the requesting agent writes for the fresh-eyes-attack: a problem statement plus off-limits and read-first lists.
- **walk-document** — the file `docs/walk/<name>.md`, the text of an approval-walk as presented to the user.
- **walk-minutes** — the document the /walk-me-through skill uses to record the outcome of each item of an approval-walk.
