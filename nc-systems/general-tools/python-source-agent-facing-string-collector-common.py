#!/usr/bin/env python3
"""Find the agent-facing-messages in a Python file's source, and say which
files are tests.

An agent-facing-message is recognized by its form alone: a string printed or
written to sys.stdout or sys.stderr, a string in a raise statement, a string
assigned to a name ending in one of AGENT_STRING_NAME_SUFFIXES, and the module
docstring of a file that mentions __doc__, which argparse prints for --help.
A message built any other way, such as text put straight into a hook's JSON
output, is not found.

A test file's strings are not agent-facing-messages: a test's copy of an
expected message is not handed to an agent.

scripts/pull-request-review-plan.py and
nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py
load this file with importlib.util.spec_from_file_location, because Python
cannot import a hyphenated file name by name.
"""

import ast

AGENT_STRING_NAME_SUFFIXES = ("_ADVICE", "_MESSAGE", "_TEMPLATE", "_LINE", "_LINES", "_REFUSAL")


def path_is_test_file(path):
    return path.endswith("-test.py") or "tests" in path.split("/")[:-1]


def string_nodes_without_f_string_parts(expression):
    if isinstance(expression, ast.JoinedStr):
        yield expression
    elif isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        yield expression
    else:
        for child in ast.iter_child_nodes(expression):
            yield from string_nodes_without_f_string_parts(child)


class AgentFacingStringNodeCollector(ast.NodeVisitor):
    """Record string spans and their call, assignment or exception context."""

    def __init__(self):
        self.enclosing_names = []
        self.string_entries = []
        self.seen_node_contexts = set()

    def collect_expression_strings(self, expression, label):
        if expression is None:
            return
        if self.enclosing_names:
            label += f" in {'.'.join(self.enclosing_names)}()"
        for node in string_nodes_without_f_string_parts(expression):
            identity = (id(node), label)
            if identity in self.seen_node_contexts:
                continue
            self.seen_node_contexts.add(identity)
            self.string_entries.append({"line": node.lineno, "end_line": node.end_lineno,
                                        "label": label, "text": ast.unparse(node) if isinstance(node, ast.JoinedStr) else node.value})

    def visit_enclosing_definition(self, node):
        self.enclosing_names.append(node.name)
        self.generic_visit(node)
        self.enclosing_names.pop()

    visit_FunctionDef = visit_enclosing_definition
    visit_AsyncFunctionDef = visit_enclosing_definition
    visit_ClassDef = visit_enclosing_definition

    def visit_Call(self, node):
        call_name = ast.unparse(node.func)
        if call_name in ("print", "sys.stderr.write", "sys.stdout.write"):
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                self.collect_expression_strings(argument, call_name)
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.collect_expression_strings(node.exc, "raise")
        self.generic_visit(node)

    def visit_assignment_value(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id.endswith(AGENT_STRING_NAME_SUFFIXES):
                self.collect_expression_strings(node.value, f"{target.id} =")
        self.generic_visit(node)

    visit_Assign = visit_assignment_value
    visit_AnnAssign = visit_assignment_value
    visit_AugAssign = visit_assignment_value


def agent_facing_string_nodes_in_source(source):
    """Each entry holds line and end_line, counted from 1, label and text.
    Source that is None or does not parse yields no entries."""
    if source is None:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    collector = AgentFacingStringNodeCollector()
    if ("__doc__" in source and tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        collector.collect_expression_strings(tree.body[0].value, "module docstring (printed by --help)")
    collector.visit(tree)
    return sorted(collector.string_entries, key=lambda entry: (entry["line"], entry["label"]))
