# nedschorus

- The legacy system at `~/Projects/nedlern` is read-only reference: read anything there freely; NOT: modify anything there or execute its code.
- Use standard SDLC terms.
- Write durable artifacts — committed files, issue bodies, commit messages — for a reader with zero context: the subject identifiable, the why stated, usable without the conversation that produced it.
- When writing instructions, absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions. Use them cautiously.
- When creating or inventing names, for directories, file names, globals, functions, classes, scripts, section headings, and other names likely to be grepped, use explicit, clear and precise multi-part names. Check newly invented names with glob (for path names) or grep (for names in files). If these checks return collisions or ambiguity, choose a more explicit name, with 3 or 4 parts, not 1 or 2. If the thing you are naming already has a name in the project, use the existing name instead of inventing a new one.
