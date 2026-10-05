# nedschorus SDLC terms

Standard terms of software engineering and of other computing fields, such as operating systems, networking or databases, that this project relies on, each used with its standard meaning; the /cold-read skill's step 8 also sends here a standard term the user directs in place of a coined one. One line per term, in alphabetical order: the term, then what this project uses it for. A term listed here is not a project-term and is never hyphenated; project-terms are listed in the glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`.

- **canonical location** — the one place where a document or fact is kept and updated, which every other mention points to.
- **head commit** — the newest commit of a pull request's branch, the commit a review is made against.
- **mutation testing** — putting a small fault into code on purpose and running the tests, to see whether a test fails; in this project, how a reviewer or an author shows that a change's tests check what the change does: with a key line of the change broken, at least one of those tests must fail.
- **topic branch** — in Git's sense, a branch for one topic, a feature or a bugfix; in this project, the branch a pull request merges. Not a seat-branch.
