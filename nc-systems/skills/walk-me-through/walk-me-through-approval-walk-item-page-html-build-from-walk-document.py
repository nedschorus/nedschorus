#!/usr/bin/env python3
"""Build the HTML page of one approval-walk item from its walk-document; did the page get written?

Exits 0 when the page was written, 1 when it was not, such as when the walk-document has no heading for the
item, and 2 when the program was called the wrong way, the walk-document cannot be read, or the program crashed.

The walk-me-through skill publishes each item as a private claude.ai Artifact page. Only an agent can call the
Artifact tool, so this program builds the page and the agent publishes the file it writes. The page holds, in
order, a `<title>` "Item N of M: <walk name>", or "Version K, Item N of M: <walk name>" with --version K; the
styles and fonts in walk-me-through-approval-walk-item-page-html-head-styles-and-fonts.html beside this file;
and a `<main>` with the walk's name and the item's text rendered from Markdown, its heading as the page's `<h1>`.
N and M are the running count of the item's heading; the walk name is the walk-document's file name without `.md`.

The item is found as the walk-me-through hooks and the walk check program find it, through
walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py: its unit runs from the heading that
names it to the next item or the next `Withdrawn` heading, a sub-step such as `### Item 4.1 of 9` being an item of
its own, and an item that shares a heading with others keeps only its own lines, under that heading. Since a
sub-step's closing line links to its item's page, item 4's page also carries, after its own lines, each of its
sub-steps' units, in the walk-document's order, each under its own heading; a sub-step's page, built with 4.1,
holds that sub-step alone. A version under a `Withdrawn` heading is on no page. The text is rendered with the shared
CommonMark parser, each line break kept, as the walk-document shows it. A paragraph that opens with
`Recommendation:` gets the class `rec`, and one that opens with `#approval_walk` gets the class `tag`.

It does not copy the files an item links into the page: each link stays as the walk-document writes it, so a
`file:///Volumes/nedhome/...` link opens only on the user's Mac. It does not leave out any line, the hashtag lines
meant for agents included, apart from the versions under `Withdrawn` headings. HTML in the walk-document is shown as text, so a placeholder such as `<walk name>`
written outside backquotes shows as written. It refuses an item number
that no heading names or that more than one heading names. It overwrites the output file without asking.
"""
import argparse
import html
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEAD_STYLES_AND_FONTS_FILE = HERE / "walk-me-through-approval-walk-item-page-html-head-styles-and-fonts.html"
FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
RECOMMENDATION_CLASS = "rec"
TAG_CLASS = "tag"
UNSAFE_LINK_SCHEMES = ("javascript:", "vbscript:", "data:")

# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
NO_HEADING = (
    "REFUSED: no page written: {document} has no heading for item {number}{problems}, so there is no text to put on the page; the items its headings number are {numbered}.\n"
    "If the item's heading has no running count yet, as in `## <the point>`, the item has not been shown: the walk check program, nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py, writes the count into the heading when the walk reaches the item, so build the page after that.\n"
    "If you meant another item, run this program again with that item's number, as the heading shows it, such as 4.1 for `### Item 4.1 of 9`.")
SEVERAL_HEADINGS = (
    "REFUSED: no page written: {document} has more than one heading for item {number}, so the page could show the wrong version:\n{headings}\n"
    "Put `Withdrawn: ` just before `Item` in each of those headings except the one whose text the user should see, as in `## Withdrawn: Item 4 of 9: <the point>`, then run this program again.")
PARSER_MISSING = (
    "FAILED: no page written: the Markdown parser markdown-it-py is not installed and installing it failed, so the item's text cannot be rendered.\n"
    "Install it with `python3 -m pip install --user --break-system-packages -r nc-systems/general-tools/python-libraries-pinned-requirements.txt`, fix what pip reports, then run this program again; the program itself tries the install again only 10 minutes after a failed one.\n"
    "The install said: {output}")
WRITE_FAILED = (
    "FAILED: no page written to {output}: {error}.\n"
    "Give an output path in a directory that exists and that you can write to, such as your scratchpad directory, then run this program again.")
MISSING_DOCUMENT = (
    "FAILED: the walk-document {document} cannot be read: {error}.\n"
    "Give the path of the walk-document itself, docs/walk/<walk name>.md, not its -minutes.md or -draft.md, then run this program again.")
CRASHED = (
    "FAILED: the item page builder crashed, so the page may not have been written: {error}\n"
    "Run it again once; if it crashes the same way, send the agent-seat ned-box-helper, which owns the walk-me-through skill, this error and the command you ran with the SendMessage tool, and meanwhile publish the item's text from the walk-document with the Artifact tool by hand.")
WRITTEN = "Wrote {output}: publish it with the Artifact tool; its title is \"{title}\"."


class Refused(Exception):
    """The page cannot be built; the argument is the message for the agent."""


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def item_lines_and_count(walk_finder, document, text, number, parser):
    """Return (the item's Markdown lines, its heading line, the heading's M) for item number of text."""
    units = walk_finder.item_unit_spans(text, parser)
    naming = [unit for unit in units if number in unit[0]]
    if not naming:
        problems = "".join(f"; {unit[2]}" for unit in units if unit[2])
        numbered = ", ".join(each for unit in units for each in unit[0]) or "none"
        raise Refused(NO_HEADING.format(document=document, number=number, problems=problems, numbered=numbered))
    lines = text.split("\n")
    if len(naming) > 1:  # pragma: no mutate, naming is not empty here, so > 1 and != 1 pick the same lists
        headings = "\n".join(f"line {unit[3] + 1}: {lines[unit[3]]}" for unit in naming)
        raise Refused(SEVERAL_HEADINGS.format(document=document, number=number, headings=headings))
    numbers, total, _, first, end = naming[0]
    heading = walk_finder.approval_walk_item_heading_with_deferred_note_removed(lines[first])
    start = first
    if len(numbers) > 1:
        openings = walk_finder.item_opening_lines(text, parser)
        start, end = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
            openings, first, end, number, numbers, total)
    body = lines[start + 1:end] if start == first else lines[start:end]
    # The skill links a sub-step's closing line to its item's page, so the item's page carries its sub-steps.
    # Each sub-step's unit already ends at its first Withdrawn heading, so withdrawn versions stay off the page.
    for sub_numbers, _, _, sub_first, sub_end in units:
        if sub_numbers and all(each.startswith(number + ".") for each in sub_numbers):
            body += ["", walk_finder.approval_walk_item_heading_with_deferred_note_removed(lines[sub_first])]
            body += lines[sub_first + 1:sub_end]
    return body, heading, total


def rendered_item_html(parser, heading, body):
    """Return the HTML of the heading line as `<h1>` and of the body lines, each line break kept."""
    heading_tokens = parser.parse(heading.lstrip("#").strip() if heading.lstrip().startswith("#") else heading)
    heading_html = parser.renderer.render(heading_tokens, parser.options, {}).strip()
    if heading_html.startswith("<p>") and heading_html.endswith("</p>"):
        heading_html = heading_html[len("<p>"):-len("</p>")]
    tokens = parser.parse("\n".join(body))
    for index, token in enumerate(tokens):
        if token.type == "paragraph_open" and token.level == 0 and index + 1 < len(tokens):
            content = tokens[index + 1].content
            if content.startswith("Recommendation:"):
                token.attrSet("class", RECOMMENDATION_CLASS)
            elif content.startswith("#approval_walk"):
                token.attrSet("class", TAG_CLASS)
    options = type(parser.options)({**parser.options, "breaks": True})
    return f"<h1>{heading_html}</h1>\n" + parser.renderer.render(tokens, options, {})


def approval_walk_item_page_html_and_title_build_from_walk_document(document, text, number, version):
    """Return (the page's HTML, its title) for item number of text, the walk-document at document."""
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common", FINDER_FILE)
    parser_module = load_module("markdown_commonmark_parser_with_tables_common", walk_finder.MARKDOWN_PARSER_MODULE_FILE)
    try:
        parser = parser_module.markdown_parser()
        render_parser = parser_module.markdown_parser()
    except parser_module.MarkdownParserMissing as error:
        raise Refused(PARSER_MISSING.format(output=error.install_output)) from error
    # The finder reads HTML blocks as the hooks do; the page shows them as text, so a placeholder such as
    # <walk name> outside backquotes is not taken for a tag that hides it or, like <style>, the rest of the page.
    render_parser.disable(["html_inline", "html_block"])
    # markdown-it refuses file: links by default, and the walk-me-through skill writes files as file:///Volumes/... links.
    render_parser.validateLink = lambda url: not url.strip().lower().startswith(UNSAFE_LINK_SCHEMES)
    body, heading, total = item_lines_and_count(walk_finder, document, text, number, parser)
    walk_name = Path(document).name.removesuffix(".md")
    title = f"Item {number} of {total}: {walk_name}"
    if version is not None:
        title = f"Version {version}, {title}"
    page = (f"<title>{html.escape(title)}</title>\n" + HEAD_STYLES_AND_FONTS_FILE.read_text(encoding="utf-8")
            + "<main>\n" + f'<div class="eyebrow">Approval-walk {html.escape(walk_name)}</div>\n'
            + rendered_item_html(render_parser, heading, body) + "</main>\n")
    return page, title


def version_number(value):
    number = int(value)
    if number < 2:
        raise argparse.ArgumentTypeError("the first page has no version; a republished page is version 2 or later")
    return number


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], epilog=__doc__.split("\n\n")[1])
    parser.add_argument("walk_document", help="the walk-document, docs/walk/<walk name>.md")
    parser.add_argument("item", help="the item's number as its heading gives it, such as 4 or 4.1")
    parser.add_argument("output", help="the HTML file to write, such as one in your scratchpad directory")
    parser.add_argument("--version", type=version_number, metavar="K",
                        help="a republished page's version, 2 or later; the title then opens `Version K, `")
    arguments = parser.parse_args(argv)
    document = Path(arguments.walk_document)
    try:
        text = document.read_text(encoding="utf-8")
    except OSError as error:
        print(MISSING_DOCUMENT.format(document=document, error=error), file=sys.stderr)
        return 2
    try:
        page, title = approval_walk_item_page_html_and_title_build_from_walk_document(document, text, arguments.item, arguments.version)
    except Refused as refusal:
        print(refusal, file=sys.stderr)
        return 1
    try:
        Path(arguments.output).write_text(page, encoding="utf-8")
    except OSError as error:
        print(WRITE_FAILED.format(output=arguments.output, error=error), file=sys.stderr)
        return 1
    print(WRITTEN.format(output=arguments.output, title=title))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 - any crash must exit 2, not Python's 1, which means "not written"
        print(CRASHED.format(error=f"{type(error).__name__}: {error}"), file=sys.stderr)
        sys.exit(2)
