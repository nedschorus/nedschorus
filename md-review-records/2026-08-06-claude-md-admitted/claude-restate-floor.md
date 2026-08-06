<!-- provenance: runtime=claude model=claude-sonnet-5 effort=high cell=restate tier=floor target=/Users/el/Projects/nedschorus/docs/drafts/claude-md-admitted.md -->

# nedschorus

1. This sentence identifies the current repository by its filesystem path, `~/Projects/nedschorus`, and assigns it the abbreviation "NC" for use elsewhere.

2. This sentence establishes that a separate, older system located at `~/Projects/nedlern` is to be treated only as reference material, not as an active project to be modified. The part after the colon ("read anything there freely") means its contents may be read without restriction. The part after the semicolon, marked "NOT:", lists three forbidden actions in that location: writing (creating or modifying files), committing (recording changes to version control), or running (executing code, scripts, or commands) — I read "run anything there" as executing any process or command within or against that directory/repository.

3. This instructs using standard, conventional software-development-lifecycle terminology (SDLC = "software development lifecycle") — i.e., established industry vocabulary for describing development stages and artifacts (such as "bug," "feature," "release," "deploy") — rather than inventing idiosyncratic terms.

4. This instructs that any lasting written output ("durable artifact") should be written so a reader with no background knowledge of the conversation that produced it can still understand and use it, and specifies three requirements introduced by the colon: the subject/topic must be identifiable (clear what it's about), the reason or motivation ("the why") must be explicitly stated rather than left implicit, and the artifact must be usable ("actionable") without needing access to or knowledge of the conversation that created it.

5. This states that commands or rules phrased in absolute, unconditional terms using words like "always" or "never" carry a risk of producing bad or unintended results ("backfire") when situations arise that were not anticipated when the rule was made — i.e., rigid absolute rules may fail to hold up under circumstances the rule-writer didn't foresee.

6. This instructs that such absolute-imperative rules ("always"/"never" phrasing) should be employed sparingly or with care, presumably because of the risk just described — this could mean either being careful about phrasing new rules in absolute terms, or being careful when following/applying existing absolute rules.

7. This instructs that whenever a new name is being created for things like directories, file names, global variables, functions, and similar items (the "etc." implying other unlisted but similar categories), the chosen name should be explicit (unambiguous), clear (easily understood), and precise (specific rather than vague), and should be made of multiple parts/words rather than being a single word.

8. This instructs verifying any newly invented name by searching for it: using "glob" (a file/path pattern-matching search) to check names used for paths, or using "grep" (a text-content search tool) to check names that appear inside files, such as identifiers in code.

9. This states that if the searches from the previous sentence turn up a "collision" (the name already exists elsewhere, creating a conflict) or "ambiguity" (the name's meaning or referent could be confused with something else), then a more explicit replacement name should be chosen, and specifies that this replacement should have 3 or 4 distinct parts/words rather than only 1 or 2, implying that names with more components are less prone to collision or ambiguity.

10. This instructs that if the thing being named already has an established name somewhere else in the project, that existing name should be reused rather than inventing a new, different name for the same thing.

