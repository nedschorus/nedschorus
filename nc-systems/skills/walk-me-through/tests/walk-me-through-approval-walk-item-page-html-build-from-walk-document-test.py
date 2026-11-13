#!/usr/bin/env python3
"""Cases for the program that builds an approval-walk item's HTML page from its walk-document.

Each case runs the program as a subprocess on a scratch walk-document, except the missing-parser case, which loads
the program and makes its parser module raise. Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PROGRAM = HERE / "walk-me-through-approval-walk-item-page-html-build-from-walk-document.py"
HEAD_STYLES_AND_FONTS = (HERE / "walk-me-through-approval-walk-item-page-html-head-styles-and-fonts.html").read_text(
    encoding="utf-8")
WALK = "item-page-test-walk-2026-11-11"
failures = []

WALK_DOCUMENT = """# A walk

The opening, which mentions Item 4 of 9 in passing.

## Item 3 of 9 (deferred: moved to just before the summary item): the opening sentence

#approval_walk_item_first_entered 2026-11-05

The sentence is in [the design](file:///Volumes/nedhome/agents/x/design.md), not [a script](javascript:alert(1)).
#new_if_d A line right below, kept on its own line.

- a list item

A page titled "Item N of M: <walk name>", and a bare <style> tag.

#case_against weak: it takes an hour.

Recommendation: change it.

## Item 4 of 9: a filter

A filter would hide old rows.

### Item 4.1 of 9: the filter's default

Off by default.

Recommendation: leave the filter out.

## Items 5 and 6 of 9: two small corrections

Item 5 of 9 fixes a path. Recommendation: fix the path.

**Item 6 of 9** drops a sentence. Recommendation: drop it.

```
## Item 7 of 9: an example heading inside code
```

## Item 8 of 9: a heading written twice

The first version.

## Item 8 of 9: a heading written twice, again

The second version.

## Item 9 of 9: summary

Recommendation: close.
"""


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(*arguments):
    return subprocess.run([sys.executable, str(PROGRAM), *map(str, arguments)], capture_output=True, text=True)


def built(scratch, item, *extra, document=WALK_DOCUMENT):
    walk_document = scratch / f"{WALK}.md"
    walk_document.write_text(document, encoding="utf-8")
    output = scratch / f"item-{item}.html"
    output.unlink(missing_ok=True)
    result = run(walk_document, item, output, *extra)
    return result, output.read_text(encoding="utf-8") if output.exists() else ""


def run_page_cases(scratch):
    result, page = built(scratch, "3")
    main = page[page.find("<main>"):]
    check("an item's page is written, exit 0, and the program names the file and the title to publish",
          result.returncode == 0 and f"its title is \"Item 3 of 9: {WALK}\"" in result.stdout
          and "publish it with the Artifact tool" in result.stdout, result)
    check("the page opens with its title, then the styles and fonts, then <main>, so no text sits inside a <style>",
          page.startswith(f"<title>Item 3 of 9: {WALK}</title>\n" + HEAD_STYLES_AND_FONTS + "<main>\n")
          and page.rstrip().endswith("</main>"), page[:300])
    check("the heading becomes the <h1>, without the deferred note",
          "<h1>Item 3 of 9: the opening sentence</h1>" in main, main)
    check("the heading is not repeated in the body below the <h1>",
          main.count("Item 3 of 9") == 1 and "<h2>" not in main, main)
    check("the walk's name is on the page", f'<div class="eyebrow">Approval-walk {WALK}</div>' in main, main)
    check("a paragraph opening with Recommendation: gets the class rec",
          '<p class="rec">Recommendation: change it.</p>' in main, main)
    check("a paragraph opening with #approval_walk gets the class tag",
          '<p class="tag">#approval_walk_item_first_entered 2026-11-05</p>' in main, main)
    check("a file:/// link stays a link to the file as written, since the page copies no file",
          '<a href="file:///Volumes/nedhome/agents/x/design.md">the design</a>' in main, main)
    check("a javascript: link is not made a link", 'href="javascript:' not in main, main)
    check("a line right below another keeps its line break, and hashtag lines stay on the page",
          "<br />\n#new_if_d A line right below" in main and "#case_against weak" in main, main)
    check("a list is rendered as a list", "<li>a list item</li>" in main, main)
    check("a placeholder in angle brackets, and a bare <style>, show as text, not as tags that hide them",
          "&lt;walk name&gt;" in main and "a bare &lt;style&gt; tag" in main and "<style>" not in main, main)
    check("the page holds only its own item", "a filter" not in main, main)


def run_unit_cases(scratch):
    _, page = built(scratch, "4")
    check("an item's page carries its sub-step under the sub-step's own heading, and stops before the next item",
          "A filter would hide old rows." in page and "<h3>Item 4.1 of 9: the filter's default</h3>" in page
          and "Off by default." in page and "two small corrections" not in page, page)
    result, page = built(scratch, "4.1")
    check("a sub-step's page holds the sub-step alone, its ### heading as the <h1>",
          result.returncode == 0 and "<h1>Item 4.1 of 9: the filter's default</h1>" in page
          and "Off by default." in page and "A filter would hide" not in page, page)
    result, page = built(scratch, "6")
    check("an item that shares a heading keeps its own lines under that heading",
          result.returncode == 0 and "<h1>Items 5 and 6 of 9: two small corrections</h1>" in page
          and "drops a sentence" in page and "fixes a path" not in page, page)
    result, page = built(scratch, "3", "--version", "2")
    check("--version 2 opens the title with Version 2", result.returncode == 0
          and page.startswith(f"<title>Version 2, Item 3 of 9: {WALK}</title>"), page[:200])


# An item whose own text is only its tags, its content in sub-steps, each version replaced later under a Withdrawn
# heading, some of them after the sub-steps.
PARENT_WITH_WITHDRAWN_VERSIONS_AND_SUB_STEPS = """# A walk

## Item 4 of 46: the item before, whose number begins item 45's

Recommendation: keep it.

## Item 45 of 46: the paused walk: refresh its rewrite, or drop it

#approval_walk_item_first_entered 2026-11-11

#approval_walk_item_in_category_fix_next

#### Withdrawn version 1 of item 45

#approval_walk_item_first_entered 2026-11-12

Withdrawn one: the search-file guard names one dash-name.

Recommendation: approve both, from withdrawn one.

#### Withdrawn version 2 of item 45

Withdrawn two: the two rulings disagree here.

Recommendation: refresh, from withdrawn two.

### Item 45.1 of 46: what the paused walk holds

Current 45.1: the first ruling has you answer 31 items one by one.

No decision here; type N or next to continue.

#### Withdrawn version 1 of item 45.1

Withdrawn 45.1: the first ruling has you review this rewrite item by item.

### Item 45.2 of 46 (deferred: moved to just before the summary item): refresh the rewrite, or drop it

Current 45.2: the paused walk closes, and 27 of the 30 items are settled.

#case_against medium: nothing starts until PR 2958 merges.

Recommendation: refresh the rewrite.

#### Withdrawn version 1 of item 45

Withdrawn three: a third withdrawn version of item 45, after its sub-steps.

#### Withdrawn version 1 of item 45.2

Withdrawn 45.2: the old walk closes.

## The next, unnumbered item

The next item's text.
"""


def run_parent_with_sub_steps_case(scratch):
    result, page = built(scratch, "45", document=PARENT_WITH_WITHDRAWN_VERSIONS_AND_SUB_STEPS)
    main = page[page.find("<main>"):]
    check("an item whose own text is only tags gets a page with its current sub-steps in full, in order",
          result.returncode == 0 and "<h1>Item 45 of 46: the paused walk: refresh its rewrite, or drop it</h1>" in main
          and main.find("<h3>Item 45.1 of 46: what the paused walk holds</h3>")
          < main.find("Current 45.1: the first ruling has you answer 31 items")
          < main.find("<h3>Item 45.2 of 46: refresh the rewrite, or drop it</h3>")
          < main.find("Current 45.2: the paused walk closes")
          < main.find('<p class="rec">Recommendation: refresh the rewrite.</p>')
          and main.find("<h3>Item 45.1") > main.find("#approval_walk_item_in_category_fix_next") > 0, main)
    check("the item's page leaves out every withdrawn version, of the item and of its sub-steps, and the next items",
          not any(text in main for text in ("Withdrawn", "withdrawn one", "withdrawn two", "Withdrawn three",
                                            "Withdrawn 45.1", "Withdrawn 45.2", "2026-11-12", "the item before",
                                            "The next item's text")), main)
    check("a deferred sub-step's heading shows without the deferred note", "(deferred" not in main, main)
    result, page = built(scratch, "4", document=PARENT_WITH_WITHDRAWN_VERSIONS_AND_SUB_STEPS)
    check("item 4's page does not take item 45's sub-steps for its own",
          result.returncode == 0 and "Recommendation: keep it." in page and "45." not in page, page)
    shared = """# A walk

## Items 12 to 12.2 of 13: a group

**Item 12:** the item's own text.

**Item 12.1:** the first sub-step's text.

#### Withdrawn version 1 of item 12.1

The withdrawn sub-step text.

**Item 12.2:** the second sub-step's text.

## Item 13 of 13: next

The next item's text.
"""
    result, page = built(scratch, "12", document=shared)
    check("under a heading that names an item and its sub-steps, the item's page carries each sub-step's own lines",
          result.returncode == 0 and page.find("the item's own text") < page.find("the first sub-step's text")
          < page.find("the second sub-step's text") and "withdrawn sub-step" not in page
          and "The next item's text" not in page, page)
    result, page = built(scratch, "12.1", document=shared)
    check("under that heading, a sub-step's page holds that sub-step alone",
          result.returncode == 0 and "the first sub-step's text" in page and "the item's own text" not in page
          and "the second sub-step's text" not in page, page)


def run_refusal_cases(scratch):
    result, page = built(scratch, "7")
    check("an item no heading names, here one only inside code, is refused with exit 1 and no page",
          result.returncode == 1 and page == "" and "REFUSED: no page written" in result.stderr
          and "has no heading for item 7" in result.stderr and "Traceback" not in result.stderr
          and "the items its headings number are 3, 4, 4.1, 5, 6, 8, 8, 9" in result.stderr, result)
    result, page = built(scratch, "8")
    check("an item two headings name is refused with exit 1, naming both lines and how to withdraw one",
          result.returncode == 1 and page == "" and "more than one heading for item 8" in result.stderr
          and "Put `Withdrawn: ` just before `Item`" in result.stderr, result)
    lines = WALK_DOCUMENT.split("\n")
    first = lines.index("## Item 8 of 9: a heading written twice") + 1
    second = lines.index("## Item 8 of 9: a heading written twice, again") + 1
    check("the refusal names each heading for the item with its line number",
          f"line {first}: ## Item 8 of 9: a heading written twice\n" in result.stderr
          and f"line {second}: ## Item 8 of 9: a heading written twice, again\n" in result.stderr, result.stderr)
    withdrawn = WALK_DOCUMENT.replace("## Item 8 of 9: a heading written twice\n",
                                      "## Withdrawn: Item 8 of 9: a heading written twice\n")
    result, page = built(scratch, "8", document=withdrawn)
    check("following the refusal's instruction, Withdrawn: on one heading, builds the other version's page",
          result.returncode == 0 and "The second version." in page and "The first version." not in page, result)
    result, _ = built(scratch, "3", "--version", "1")
    check("--version 1 is called the wrong way: exit 2", result.returncode == 2 and "version 2 or later" in result.stderr,
          result)
    result = run(scratch / "no-such-walk.md", "3", scratch / "out.html")
    check("a walk-document that cannot be read exits 2, naming it, with no page",
          result.returncode == 2 and "no-such-walk.md cannot be read: [Errno 2] No such file or directory" in result.stderr
          and not (scratch / "out.html").exists(), result)
    walk_document = scratch / f"{WALK}.md"
    walk_document.write_text(WALK_DOCUMENT, encoding="utf-8")
    result = run(walk_document, "3", scratch / "no-such-directory" / "out.html")
    check("an output path that cannot be written exits 1 and says no page was written",
          result.returncode == 1 and "FAILED: no page written to" in result.stderr and "No such file or directory" in result.stderr
          and "directory that exists" in result.stderr, result)
    walk_document.write_bytes(b"## Item 1 of 1: x\n\xff\xfe\n")
    result = run(walk_document, "1", scratch / "out.html")
    check("a crash, here a walk-document that is not UTF-8, exits 2, not 1, with one line and no traceback",
          result.returncode == 2 and result.stderr.startswith("FAILED: the item page builder crashed")
          and "Run it again once" in result.stderr
          and "Traceback" not in result.stderr, result)


def run_parser_missing_case(scratch):
    specification = importlib.util.spec_from_file_location("item_page_builder", PROGRAM)
    builder = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(builder)

    class MarkdownParserMissing(Exception):
        def __init__(self, install_output):
            super().__init__(install_output)
            self.install_output = install_output

    def markdown_parser():
        raise MarkdownParserMissing("pip: no network")

    real_load_module = builder.load_module

    def load_module(name, path):
        module = real_load_module(name, path)
        if name == "markdown_commonmark_parser_with_tables_common":
            module.MarkdownParserMissing = MarkdownParserMissing
            module.markdown_parser = markdown_parser
        return module

    builder.load_module = load_module
    walk_document = scratch / f"{WALK}.md"
    walk_document.write_text(WALK_DOCUMENT, encoding="utf-8")
    output = scratch / "parser-missing.html"
    code = builder.main([str(walk_document), "3", str(output)])
    check("a Markdown parser that cannot be installed exits 1 with no page", code == 1 and not output.exists(), code)
    try:
        builder.approval_walk_item_page_html_and_title_build_from_walk_document(walk_document, WALK_DOCUMENT, "3", None)
        check("the missing-parser refusal says what the install said and how to install it", False, "no refusal")
    except builder.Refused as refusal:
        check("the missing-parser refusal says what the install said and how to install it",
              "pip: no network" in str(refusal) and "--user --break-system-packages -r nc-systems/general-tools/python-libraries-pinned-requirements.txt" in str(refusal),
              str(refusal))


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_page_cases(scratch)
    run_unit_cases(scratch)
    run_parent_with_sub_steps_case(scratch)
    run_refusal_cases(scratch)
    run_parser_missing_case(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
