#!/usr/bin/env python3
"""Find the agent-facing-messages in a Python file's source, and say which
files are tests.

An agent-facing-message is recognized by its form alone: a string printed or
written to sys.stdout or sys.stderr; a string passed to a helper printer, a
function defined once at module level whose parameter reaches print,
sys.stdout.write, sys.stderr.write, `<parameter>.write` or another helper
printer, as text in say(stream, text) does, in the position or under the
keyword of that parameter; a string in a raise statement; a string
assigned to a name ending in one of AGENT_STRING_NAME_SUFFIXES, or in one of
them followed by S; the value, in a dict literal, of one of
AGENT_FACING_HOOK_OUTPUT_KEYS, the keys through which a Claude Code hook's JSON
output reaches the agent, when that value is a string, an f-string or a name
assigned a string once at module level; and the module docstring of a file
that mentions __doc__, which argparse prints for --help. A message built with + is one message,
its literal pieces joined and each other operand shown as {source}; an f-string
field in the chain keeps its conversion and format spec, {x!r} and {x:.1f}, as ast.unparse writes
the field of a standalone f-string. Each entry also holds literal_text, the message's literal
pieces alone, outside every {...} placeholder. A message held in a
local variable, or built any other way, is not found. Nor is one passed to a
helper printer that is a method, is defined in another module or more than
once, is called under another name, sits after a *starred argument, or reaches
the printed text only through a call, such as json.dumps(payload); and a helper
printer's name is not followed where an enclosing function's parameter hides it. "systemMessage" is not
among the keys: Claude Code shows that text to the user, not to the agent.

A test file's strings are not agent-facing-messages: a test's copy of an
expected message is not handed to an agent.

scripts/pull-request-review-plan.py and
nc-systems/general-tools/python-edit-changed-agent-facing-message-check-reminder-hook.py
load this file with importlib.util.spec_from_file_location, because Python
cannot import a hyphenated file name by name.
"""

import ast

AGENT_STRING_NAME_SUFFIXES = ("_ADVICE", "_INSTRUCTION", "_LINE", "_MESSAGE", "_NOTICE", "_REASON",
                              "_REFUSAL", "_TEMPLATE")
AGENT_FACING_HOOK_OUTPUT_KEYS = ("additionalContext", "permissionDecisionReason", "reason", "stopReason")


def variable_name_has_agent_facing_message_suffix(name):
    stem = name[:-1] if name.endswith("S") else name
    return stem.endswith(AGENT_STRING_NAME_SUFFIXES)


def path_is_test_file(path):
    return path.endswith("-test.py") or "tests" in path.split("/")[:-1]


def is_string_literal_node(node):
    return isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, str))


def addition_chain_operands(expression):
    """The operands of a chain of + operators, left to right."""
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        return [*addition_chain_operands(expression.left), *addition_chain_operands(expression.right)]
    return [expression]


def f_string_field_text(field):
    """The whole field, such as {x!r} or {x:.1f}, as ast.unparse writes it inside a standalone f-string."""
    unparsed = ast.unparse(ast.JoinedStr(values=[field]))
    return unparsed[unparsed.index("{"):unparsed.rindex("}") + 1]


def message_text_of_addition_chain(operands, literal_only=False):
    """The literal pieces joined; an f-string field or another operand is shown as {source},
    or left out when literal_only."""
    pieces = []
    for operand in operands:
        if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
            pieces.append(operand.value)
        elif literal_only:
            if isinstance(operand, ast.JoinedStr):
                pieces.extend(part.value for part in operand.values if isinstance(part, ast.Constant))
        elif isinstance(operand, ast.JoinedStr):
            pieces.extend(part.value if isinstance(part, ast.Constant) else f_string_field_text(part)
                          for part in operand.values)
        else:
            pieces.append("{" + ast.unparse(operand) + "}")
    return "".join(pieces)


def string_nodes_without_f_string_parts(expression):
    """Each string literal, f-string or + chain holding a string literal, as one node; a + chain
    is one message, so its literal pieces are not yielded separately."""
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        operands = addition_chain_operands(expression)
        if any(is_string_literal_node(operand) for operand in operands):
            yield expression
            return
    if isinstance(expression, ast.JoinedStr):
        yield expression
    elif isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        yield expression
    else:
        for child in ast.iter_child_nodes(expression):
            yield from string_nodes_without_f_string_parts(child)


def text_of_string_node(node):
    if isinstance(node, ast.BinOp):
        return message_text_of_addition_chain(addition_chain_operands(node))
    return ast.unparse(node) if isinstance(node, ast.JoinedStr) else node.value


def literal_text_of_string_node(node):
    """The node's literal words alone, outside every {...} placeholder."""
    if isinstance(node, ast.BinOp):
        return message_text_of_addition_chain(addition_chain_operands(node), literal_only=True)
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values if isinstance(part, ast.Constant))
    return node.value


PRINTING_CALL_NAMES = ("print", "sys.stderr.write", "sys.stdout.write")
PRINT_KEYWORDS_NOT_PRINTED = ("file", "flush")


def call_arguments_by_parameter(call, positions, names):
    """The call's arguments that fill the given parameter positions or names; arguments after
    a *starred one are left out, since their positions are unknown."""
    for index, argument in enumerate(call.args):
        if isinstance(argument, ast.Starred):
            break
        if index in positions:
            yield argument
    for keyword in call.keywords:
        if keyword.arg in names:
            yield keyword.value


def printed_arguments(call, helper_printers, receiver_names=()):
    """The arguments a call prints: every argument of print or sys.stdout/sys.stderr.write, or of
    `<name>.write` when name is in receiver_names, and the printed parameters' arguments of a
    call to a helper printer."""
    call_name = ast.unparse(call.func)
    is_write_to_receiver = (isinstance(call.func, ast.Attribute) and call.func.attr == "write"
                            and isinstance(call.func.value, ast.Name)
                            and call.func.value.id in receiver_names)
    if call_name in PRINTING_CALL_NAMES or is_write_to_receiver:
        yield from call.args
        yield from (keyword.value for keyword in call.keywords
                    if not (call_name == "print" and keyword.arg in PRINT_KEYWORDS_NOT_PRINTED))
    elif isinstance(call.func, ast.Name) and call.func.id in helper_printers:
        yield from call_arguments_by_parameter(call, *helper_printers[call.func.id])


def names_outside_calls(expression):
    """The names in the expression that are not inside a call, so print(text + "\\n") prints text
    but print(json.dumps(payload)) does not print payload's strings as they are."""
    if isinstance(expression, ast.Call):
        return
    if isinstance(expression, ast.Name):
        yield expression.id
    for child in ast.iter_child_nodes(expression):
        yield from names_outside_calls(child)


def function_parameter_names(function):
    arguments = function.args
    return {argument.arg for argument in [*arguments.posonlyargs, *arguments.args,
                                          *arguments.kwonlyargs, arguments.vararg,
                                          arguments.kwarg] if argument is not None}


def helper_printers_in_tree(tree):
    """Each function defined once at module level that prints one of its own parameters, mapped to
    (positions, names) of those parameters. A parameter is printed when it appears in an argument
    of print, of sys.stdout.write or sys.stderr.write, of `<parameter>.write`, as in
    say(stream, text), or of a call to another helper printer in a printed position."""
    definitions = {}
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.setdefault(statement.name, []).append(statement)
    functions = [found[0] for found in definitions.values() if len(found) == 1]
    helper_printers = {}
    changed = True
    while changed:
        changed = False
        for function in functions:
            positional = [argument.arg for argument in
                          [*function.args.posonlyargs, *function.args.args]]
            parameters = function_parameter_names(function)
            printed = set()
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    for argument in printed_arguments(node, helper_printers, parameters):
                        printed.update(name for name in names_outside_calls(argument)
                                       if name in parameters)
            if not printed:
                continue
            entry = ({index for index, name in enumerate(positional) if name in printed}, printed)
            if helper_printers.get(function.name) != entry:
                helper_printers[function.name] = entry
                changed = True
    return helper_printers


class AgentFacingStringNodeCollector(ast.NodeVisitor):
    """Record string spans and their call, assignment or exception context."""

    def __init__(self, module_string_values=None, helper_printers=None):
        self.enclosing_names = []
        # The parameter names of each enclosing function, which hide a helper printer's name.
        self.enclosing_parameter_names = []
        self.string_entries = []
        self.seen_node_contexts = set()
        # Name -> the string expression assigned to the name, once, at module level.
        self.module_string_values = module_string_values or {}
        # Function name -> (positions, names) of the parameters it prints.
        self.helper_printers = helper_printers or {}

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
                                        "label": label, "text": text_of_string_node(node),
                                        "literal_text": literal_text_of_string_node(node)})

    def visit_enclosing_definition(self, node):
        self.enclosing_names.append(node.name)
        self.generic_visit(node)
        self.enclosing_names.pop()

    def visit_function_definition(self, node):
        self.enclosing_parameter_names.append(function_parameter_names(node))
        self.visit_enclosing_definition(node)
        self.enclosing_parameter_names.pop()

    visit_FunctionDef = visit_function_definition
    visit_AsyncFunctionDef = visit_function_definition
    visit_ClassDef = visit_enclosing_definition

    def is_helper_printer_call(self, call_name):
        return call_name in self.helper_printers and not any(
            call_name in names for names in self.enclosing_parameter_names)

    def visit_Call(self, node):
        call_name = ast.unparse(node.func)
        if call_name in PRINTING_CALL_NAMES or self.is_helper_printer_call(call_name):
            label = call_name if call_name in PRINTING_CALL_NAMES else call_name + "()"
            for argument in printed_arguments(node, self.helper_printers):
                self.collect_expression_strings(argument, label)
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.collect_expression_strings(node.exc, "raise")
        self.generic_visit(node)

    def visit_assignment_value(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and variable_name_has_agent_facing_message_suffix(target.id):
                self.collect_expression_strings(node.value, f"{target.id} =")
        self.generic_visit(node)

    visit_Assign = visit_assignment_value
    visit_AnnAssign = visit_assignment_value
    visit_AugAssign = visit_assignment_value

    def visit_Dict(self, node):
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value in AGENT_FACING_HOOK_OUTPUT_KEYS):
                continue
            label = f'"{key.value}" value'
            if isinstance(value, ast.Name):
                # A name ending in a suffix is collected already, at its assignment.
                if value.id in self.module_string_values and not variable_name_has_agent_facing_message_suffix(value.id):
                    self.collect_expression_strings(self.module_string_values[value.id],
                                                    f"{label} {value.id} =")
            elif is_string_expression(value):
                self.collect_expression_strings(value, label)
        self.generic_visit(node)


def is_string_expression(expression):
    """A string literal, an f-string, or a + of such expressions."""
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        return is_string_expression(expression.left) and is_string_expression(expression.right)
    return isinstance(expression, ast.JoinedStr) or (
        isinstance(expression, ast.Constant) and isinstance(expression.value, str))


def module_level_string_values(tree):
    """Each name assigned a string expression exactly once at module level, and
    no other way there, mapped to that expression."""
    assignments = {}
    for statement in tree.body:
        targets = (statement.targets if isinstance(statement, ast.Assign)
                   else [statement.target] if isinstance(statement, (ast.AnnAssign, ast.AugAssign)) else [])
        for target in targets:
            if isinstance(target, ast.Name):
                value = statement.value if not isinstance(statement, ast.AugAssign) else None
                assignments.setdefault(target.id, []).append(value)
    return {name: values[0] for name, values in assignments.items()
            if len(values) == 1 and values[0] is not None and is_string_expression(values[0])}


def agent_facing_string_nodes_in_source(source):
    """Each entry holds line and end_line, counted from 1, label, text and literal_text.
    Source that is None or does not parse yields no entries."""
    if source is None:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    collector = AgentFacingStringNodeCollector(module_level_string_values(tree),
                                               helper_printers_in_tree(tree))
    if ("__doc__" in source and tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        collector.collect_expression_strings(tree.body[0].value, "module docstring (printed by --help)")
    collector.visit(tree)
    return sorted(collector.string_entries, key=lambda entry: (entry["line"], entry["label"]))
