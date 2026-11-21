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
names it to the next item, a sub-step such as `### Item 4.1 of 9` being an item of its own. An item that shares a
heading with others keeps only its own lines, from its opening, such as `**Item 12:**`, to the next opening; with
no opening of its own, it keeps the heading's lines. A `Withdrawn` heading ends the item it falls in, and a
heading below it in its section starts no item, so the versions under it are on no page, with one exception: an
item's page carries whole, its Withdrawn versions included, a heading that names several of its sub-steps, such as
`### Items 4.1 and 4.2 of 9` on item 4's page.

The skill links a sub-step's closing line to the page of the item the sub-step belongs to, such as item 4's page
for sub-step 4.1, so item 4's page carries, after its own lines, each of its sub-steps under the sub-step's own
heading. It takes them wherever they sit below item 4, as the walk finder's
approval_walk_item_sub_step_units_below_item_in_walk_document says, so an item standing between two of them stays
off item 4's page and the sub-steps after it are on it, while an older version's `### Item 4.2 of 8` below a later
item stays off. A sub-step's own
page, built with 4.1, holds that sub-step's lines and its own sub-steps, such as 4.1.1, and none of its siblings':
under `### Items 4.1 and 4.2 of 9` it keeps only 4.1's lines, as for any heading shared by several items. Under a heading that names an item and its sub-steps, as in
`## Items 12 to 12.2 of 13`, item 12's page also carries the lines of each sub-step that has an opening of its
own, such as `**Item 12.1:**`, and leaves off a sub-step with none; it puts these lines in the walk-document's
order, each line once, so a sub-step's lines that item 12's own already hold are not repeated.

The text is rendered with the shared
CommonMark parser, each line break kept, as the walk-document shows it. A paragraph that opens with
`Recommendation:` gets the class `rec`, and one that opens with `#approval_walk` gets the class `tag`.

LINKS BETWEEN PAGES. The walk-minutes, the walk-document's sibling `<walk name>-minutes.md`, record each page's link
on an `#item_page` line, read through the walk finder's approval_walk_item_page_link_lines_oldest_first_from_walk_minutes. Every page gets,
above its heading, a "Previous" link to the page of the item before, the whole item with the highest number below
this item's whole number whose newest `#item_page` line with a link gives that link, and a "Next" link to the page of
the item after, the lowest such number above it; they open whole items' pages only, so sub-steps' lines are not read here, and
a failed publish's line gives no link. When there is no Previous link, such as when the walk-minutes are missing, the
program prints why.

The item after has no link yet when this item's first page is built, so that page cannot be given its Next link in the
same invocation of the program; on a whole item's first page, built without --version, the program prints the command that builds
the item before's page again, with --version set to that item's next version, to run once this item's page is
published and its `#item_page` line recorded; that page then gets its Next link to this one. An item's `#item_page`
lines with a link, read oldest first, count versions from 1, each one more than the line before or the version it
states when that is higher, so the last line's version is the highest; the item's next version is one more.
A stated version can skip ahead, because an agent may republish a page without recording a line for it, as when
`#item_page item 2 of 19 <link> (version 4)` follows a single earlier line for item 2; a bare line after it is then
version 5, and the item's next version 6. Building a page with --version prints the link it is to be published to, its
item's newest `#item_page` link, if any.

It does not copy the files an item links into the page: each link stays as the walk-document writes it, so a
`file:///Volumes/nedhome/...` link opens only on the user's Mac. Of the lines the paragraphs above put on the page,
it leaves none out, the hashtag lines meant for agents included. HTML in the walk-document is shown as text, so a placeholder such as `<walk name>`
written outside backquotes shows as written. It refuses an item number
that no heading names or that more than one heading names. It overwrites the output file without asking.
"""
import argparse
import html
import importlib.util
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HEAD_STYLES_AND_FONTS_FILE = HERE / "walk-me-through-approval-walk-item-page-html-head-styles-and-fonts.html"
FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
RECOMMENDATION_CLASS = "rec"
TAG_CLASS = "tag"
UNSAFE_LINK_SCHEMES = ("javascript:", "vbscript:", "data:")

# Messages follow docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
NO_HEADING = (
    "REFUSED: no page written: {document} has no heading for item {number}{problems}, so there is no text to put on the page; the items its headings number are {numbered}.\n"
    "If the item's heading has no running count yet, as in `## <the point>`, the item has not been shown: the walk check program, nn-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py, writes the count into the heading when the walk reaches the item, so build the page after that.\n"
    "If you meant another item, run this program again with that item's number, as the heading shows it, such as 4.1 for `### Item 4.1 of 9`.")
SEVERAL_HEADINGS = (
    "REFUSED: no page written: {document} has more than one heading for item {number}, so the page could show the wrong version:\n{headings}\n"
    "Put `Withdrawn: ` just before `Item` in each of those headings except the one whose text the user should see, as in `## Withdrawn: Item 4 of 9: <the point>`, then run this program again.")
PARSER_MISSING = (
    "FAILED: no page written: the Markdown parser markdown-it-py is not installed and installing it failed, so the item's text cannot be rendered.\n"
    "Install it with `python3 -m pip install --user --break-system-packages -r nn-systems/general-tools/python-libraries-pinned-requirements.txt`, fix what pip reports, then run this program again; the program itself tries the install again only 10 minutes after a failed one.\n"
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
WRITTEN_REPUBLISH = ("Wrote {output}: publish it with the Artifact tool to {link}, the page's newest `#item_page` link; "
                     "its title is \"{title}\".")
NO_PREVIOUS_LINK = "The page has no Previous link: {reason}."
NO_MINUTES = "the walk-minutes {minutes} do not exist"
NO_ITEM_BEFORE = "no whole item numbered below {number} has an `#item_page` line with a link in {minutes}"
ITEM_BEFORE_NEXT_LINK = (
    "Item {before}'s page, {link}, has no Next link to this page yet, because this page has no link until it is published.\n"
    "Once you have published {output} and recorded its `#item_page` line in {minutes}, run\n"
    "{command}\n"
    "and publish the file it writes as it says, to {link}, so that item {before}'s page links to this one.")


class Refused(Exception):
    """The page cannot be built; the argument is the message for the agent."""


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def walk_finder_and_parser_module():
    walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common", FINDER_FILE)
    return walk_finder, load_module("markdown_commonmark_parser_with_tables_common",
                                    walk_finder.MARKDOWN_PARSER_MODULE_FILE)


def markdown_parser(parser_module):
    try:
        return parser_module.markdown_parser()
    except parser_module.MarkdownParserMissing as error:
        raise Refused(PARSER_MISSING.format(output=error.install_output)) from error


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
    (unit,) = naming
    heading, body = walk_finder.approval_walk_item_heading_and_item_page_body_lines(text, parser, units, unit, number)
    return body, heading, unit[1]


def whole_item_links(item_page_lines, walk_finder):
    """Return {whole item number: the link of its newest `#item_page` line that has one}."""
    return {int(number): link for number, link, _ in item_page_lines
            if "." not in number and link != walk_finder.ITEM_PAGE_PUBLISH_FAILED}


def next_version(item_page_lines, walk_finder, number):
    """Return the version the next republish of whole item number's page gets, as the module docstring says."""
    version = 0
    for each, link, stated in item_page_lines:
        if each == str(number) and link != walk_finder.ITEM_PAGE_PUBLISH_FAILED:
            version = max(stated or 0, version + 1)
    return version + 1


def neighbour_links(links, number):
    """Return ((number, link) of the item before, or None, (number, link) of the item after, or None)."""
    whole = int(number.split(".")[0])
    before = max((each for each in links if each < whole), default=None)
    after = min((each for each in links if each > whole), default=None)
    return ((before, links[before]) if before is not None else None,
            (after, links[after]) if after is not None else None)


def navigation_html(before, after):
    """Return the `<nav>` of Previous and Next links, or "" when there is neither."""
    links = ([f'<a href="{html.escape(before[1])}">Previous: item {before[0]}</a>'] if before else []) + (
        [f'<a href="{html.escape(after[1])}">Next: item {after[0]}</a>'] if after else [])
    return f'<nav class="pages">{" ".join(links)}</nav>\n' if links else ""


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


def approval_walk_item_page_html_and_title_build_from_walk_document(document, text, number, version,
                                                                    before=None, after=None):
    """Return (the page's HTML, its title) for item number of text, the walk-document at document; before and after
    are (number, link) of the pages the Previous and Next links open, or None for no link."""
    walk_finder, parser_module = walk_finder_and_parser_module()
    parser = markdown_parser(parser_module)
    render_parser = markdown_parser(parser_module)
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
            + navigation_html(before, after) + rendered_item_html(render_parser, heading, body) + "</main>\n")
    return page, title


def item_page_lines_or_none(minutes):
    """Return (the walk finder, the walk-minutes' `#item_page` lines), or None when the minutes file does not exist."""
    if not minutes.exists():
        return None
    walk_finder, parser_module = walk_finder_and_parser_module()
    return walk_finder, walk_finder.approval_walk_item_page_link_lines_oldest_first_from_walk_minutes(
        minutes.read_text(encoding="utf-8"), markdown_parser(parser_module))


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
    minutes = document.with_name(document.name.removesuffix(".md") + "-minutes.md")
    before = after = link = None
    notes = []
    try:
        # An item number no heading can name, such as x, gets no links and is left to the build's refusal below.
        numbered = re.fullmatch(r"\d+(?:\.\d+)*", arguments.item)
        found = item_page_lines_or_none(minutes) if numbered else None
        if not numbered:
            pass
        elif found is None:
            notes.append(NO_PREVIOUS_LINK.format(reason=NO_MINUTES.format(minutes=minutes)))
        else:
            walk_finder, item_page_lines = found
            before, after = neighbour_links(whole_item_links(item_page_lines, walk_finder), arguments.item)
            link = next((each for number, each, _ in reversed(item_page_lines) if number == arguments.item
                         and each != walk_finder.ITEM_PAGE_PUBLISH_FAILED), None)
            if before is None:
                notes.append(NO_PREVIOUS_LINK.format(reason=NO_ITEM_BEFORE.format(
                    number=arguments.item.split(".")[0], minutes=minutes)))
            # Next links open whole items' pages only, so a sub-step's page gives the item before nothing to rebuild.
            elif arguments.version is None and "." not in arguments.item:
                before_version = next_version(item_page_lines, walk_finder, before[0])
                before_output = Path(arguments.output).with_name(f"item-{before[0]}-version-{before_version}.html")
                command = shlex.join(["python3", str(Path(__file__).resolve()), str(document), str(before[0]), str(before_output),
                                      "--version", str(before_version)])
                notes.append(ITEM_BEFORE_NEXT_LINK.format(before=before[0], link=before[1], output=arguments.output,
                                                          minutes=minutes, command=command))
        page, title = approval_walk_item_page_html_and_title_build_from_walk_document(
            document, text, arguments.item, arguments.version, before, after)
    except Refused as refusal:
        print(refusal, file=sys.stderr)
        return 1
    try:
        Path(arguments.output).write_text(page, encoding="utf-8")
    except OSError as error:
        print(WRITE_FAILED.format(output=arguments.output, error=error), file=sys.stderr)
        return 1
    if arguments.version is not None and link is not None:
        print(WRITTEN_REPUBLISH.format(output=arguments.output, link=link, title=title))
    else:
        print(WRITTEN.format(output=arguments.output, title=title))
    for note in notes:
        print(note)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:  # noqa: BLE001 - any crash must exit 2, not Python's 1, which means "not written"
        print(CRASHED.format(error=f"{type(error).__name__}: {error}"), file=sys.stderr)
        sys.exit(2)
