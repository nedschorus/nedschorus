#!/usr/bin/env python3
"""Find the tool-messages-to-agent in a Python file's source, and say which
files are tests.

A tool-message-to-agent is recognized by its form alone: a string printed or
written to sys.stdout or sys.stderr; a string passed to a helper printer, a
function defined once at module level whose parameter reaches print,
sys.stdout.write, sys.stderr.write, `<parameter>.write` or another helper
printer, as text in say(stream, text) does, in the position or under the
keyword of that parameter; a string in a raise statement; a string
assigned to a name ending in one of AGENT_STRING_NAME_SUFFIXES, or in one of
them followed by S; the value, in a dict literal, of one of
TOOL_MESSAGE_TO_AGENT_HOOK_OUTPUT_KEYS, the keys through which a Claude Code hook's JSON
output reaches the agent, when that value is a string-building expression, as a local name's
binding below may be, or a name assigned a string once at module level; and the module docstring of a file
whose source holds the text __doc__ anywhere, comments and strings included,
since argparse prints __doc__ for --help. A string written in a function's return statement is a message too when a
call of that function, by its bare name, reaches one of the forms above the way a local name
may, below, as print(stopped_line(...)) does, or is carried by the binding of a local name that is
followed, as in text = f"failed: {detail()}" then print(text); a string that function's returned
call carries in turn follows the same way. The function is matched by its name alone, so every function of
that name in the file is followed. A dict literal's keys, a subscript's index and a comprehension's
if-conditions are not text, so in raise Answer(400, {"error": text}) only text is a message; nor is
a name a comprehension binds as its target, so " ".join(note for note in items) carries items, not
a local note. In a string literal's join, the literal is only the separator, so it is not a
message; the strings among the joined parts are, so "\\n".join(lines) is found through lines
alone. An empty string literal is no message either. A message built with + is one message,
its literal pieces joined and each other operand shown as {source}; an f-string
field in the chain keeps its conversion and format spec, {x!r} and {x:.1f}, as ast.unparse writes
the field of a standalone f-string. Each entry also holds literal_text, the words the message's
string literals give: its literal pieces, with each f-string field or non-literal + operand
replaced by the literal text of the strings its value may carry, so {'up' if ok else 'down'}
gives up down, while {name}, a subscript's key and a format spec give nothing, and a plain
string's braces stay as written; and text_as_agent_reads_it_with_placeholder_stand_ins,
the message as the agent reads it, with each placeholder shown as <its source>, or as its value
when it names a module-level string constant whose one assignment is the only binding of that
name anywhere in the file, as module_level_string_values_whose_name_the_file_binds_only_once says.
A message held in a local name is found when its own function's body binds the name, with =, an annotation or +=, to a
non-empty string literal, an f-string, a + chain holding a string literal, a string literal
% something or a string literal's join, or to a conditional expression with such a branch,
and the name reaches one of the forms above, or a return statement that returns the name or
a string built from it, directly or through another such local name; each binding is then
an entry at its own lines, labelled with the name, and only the binding's string-building
branches are read. A conditional expression's condition is not read, in a binding or at a
form, so its strings and names are not text. A local name that a return statement returns,
directly or in a string built from it, has its bindings listed whatever the function's caller
does with it, unlike a string written in the return statement itself, which is listed only
when a call of the function reaches a form, as above.

How a followed name may reach the form: directly, through a string literal's join, or as an
argument of the exception a raise statement builds. A name that reaches the form through any
other call, or inside a list or tuple that is returned, is not followed.

Where a followed name may be bound: in the function that holds the form. A function nested in
it follows only its own local names, never the outer function's, and names bound at module level
are not followed. A lambda or a class body nested in a function follows that function's local
names, with two exceptions: a lambda's parameter, or a name it binds with :=, hides the function's
local of the same name inside the lambda, and a name the class body binds, by assignment, import,
except ... as or a match capture, hides the function's local of the same name
everywhere in the class body, lambdas nested in it included. So when the class body assigns
`text`, a lambda in the class does not follow the function's local `text`, though Python's own
scoping would let it. A name a nested function, lambda or class body declares global hides the
function's local of the same name there. A comprehension's target hides the function's local of
the same name in the comprehension's later parts, though not in its first iterable, which Python
evaluates outside; a name read inside the target, as text is in `for messages[text] in items`, is
not bound by it. A function's or lambda's defaults and decorators, and a class's decorators, are
read in the scope the definition stands in; so are a function's annotations and a class's bases
and keywords, unless the definition has type parameters, as in class Holder[T]: then those, and
each type parameter's bound and default, are read with the type parameters' names hiding the
function's locals of the same names.

A message built any other way is not found.

An entry's kind is "prompt", text a program hands an agent as its instructions, when it was
found by following local names and reached the form through a local name containing
"prompt", in any case, or through a return statement in a function whose name contains
"prompt"; every other entry's kind is "message", text a program prints or reports. So the
strings that make up compose()'s returned local prompt are prompts, and a string printed,
raised or put in a hook's output, outside such a name, is a message. Nor is one passed to a
helper printer that is a method, is defined in another module or more than
once, or is called under another name; nor one that comes after a *starred
argument in the call; nor one whose parameter the helper prints only through a
call, such as json.dumps(payload), or only in a conditional expression's condition; nor one passed where an enclosing function's
parameter hides the helper printer's name; nor one that fills a helper's
*args or **kwargs, as in warn("text") for def warn(*parts): print(*parts). "systemMessage" is not
among the keys: Claude Code shows that text to the user, not to the agent.

A test file's strings are not tool-messages-to-agent: a test's copy of an
expected message is not handed to an agent.

scripts/pull-request-review-plan.py and
nc-systems/general-tools/python-edit-changed-tool-message-to-agent-strings-check-reminder-hook.py
load this file with importlib.util.spec_from_file_location, because Python
cannot import a hyphenated file name by name.
"""

import ast

AGENT_STRING_NAME_SUFFIXES = ("_ADVICE", "_INSTRUCTION", "_LINE", "_MESSAGE", "_NOTICE", "_REASON",
                              "_REFUSAL", "_TEMPLATE")
TOOL_MESSAGE_TO_AGENT_HOOK_OUTPUT_KEYS = ("additionalContext", "permissionDecisionReason", "reason", "stopReason")


def variable_name_has_tool_message_to_agent_suffix(name):
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


def is_addition_chain_holding_string_literal(expression):
    return (isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add)
            and any(is_string_literal_node(operand) for operand in addition_chain_operands(expression)))


def f_string_field_text(field):
    """The whole field, such as {x!r} or {x:.1f}, as ast.unparse writes it inside a standalone f-string."""
    unparsed = ast.unparse(ast.JoinedStr(values=[field]))
    return unparsed[unparsed.index("{"):unparsed.rindex("}") + 1]


def message_text_of_addition_chain(operands, literal_only=False):
    """The literal pieces joined; an f-string field or another operand is shown as {source},
    or, when literal_only, as literal_text_carried_by_placeholder gives it."""
    pieces = []
    for operand in operands:
        if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
            pieces.append(operand.value)
        elif literal_only:
            pieces.append(literal_text_carried_by_placeholder(operand))
        elif isinstance(operand, ast.JoinedStr):
            pieces.extend(part.value if isinstance(part, ast.Constant) else f_string_field_text(part)
                          for part in operand.values)
        else:
            pieces.append("{" + ast.unparse(operand) + "}")
    return "".join(pieces)


def string_nodes_without_f_string_parts(expression):
    """Each string literal, f-string or + chain holding a string literal, as one node; a + chain
    is one message, so its literal pieces are not yielded separately."""
    if is_addition_chain_holding_string_literal(expression):
        yield expression
        return
    if isinstance(expression, ast.JoinedStr):
        yield expression
    elif isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        if expression.value:
            yield expression
    elif is_join_on_string_literal(expression):
        # The separator only glues the parts: alone it is no message a reader could check.
        for argument in expression.args:
            yield from string_nodes_without_f_string_parts(argument)
    else:
        for child in text_carrying_children(expression):
            yield from string_nodes_without_f_string_parts(child)


COMPREHENSION_TYPES = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def text_carrying_children(expression):
    """The child nodes whose text the expression's value may carry: a conditional expression's
    branches, not its condition; a dict literal's values, not its keys; a subscript's value, not
    its index; a comprehension's element, or a dict comprehension's value, and the iterables it
    loops over, not its targets or if-conditions; and every child of any other node."""
    if isinstance(expression, ast.IfExp):
        return [expression.body, expression.orelse]
    if isinstance(expression, ast.Dict):
        return [value for value in expression.values if value is not None]
    if isinstance(expression, ast.Subscript):
        return [expression.value]
    if isinstance(expression, COMPREHENSION_TYPES):
        element = expression.value if isinstance(expression, ast.DictComp) else expression.elt
        return [element, *(generator.iter for generator in expression.generators)]
    return list(ast.iter_child_nodes(expression))


def text_of_string_node(node):
    if isinstance(node, ast.BinOp):
        return message_text_of_addition_chain(addition_chain_operands(node))
    return ast.unparse(node) if isinstance(node, ast.JoinedStr) else node.value


def placeholder_sources_of_string_node(node):
    """The source of each {...} placeholder the agent receives as a value, left to right: an f-string's
    fields and a + chain's operands that are not string literals; empty for a plain string literal, whose
    braces, if any, reach the agent as written."""
    operands = addition_chain_operands(node) if isinstance(node, ast.BinOp) else [node]
    sources = []
    for operand in operands:
        if isinstance(operand, ast.JoinedStr):
            sources.extend(f_string_field_text(part) for part in operand.values if not isinstance(part, ast.Constant))
        elif not (isinstance(operand, ast.Constant) and isinstance(operand.value, str)):
            sources.append("{" + ast.unparse(operand) + "}")
    return tuple(sources)


def render_string_node_text_as_agent_reads_it_with_placeholder_stand_ins(node, module_string_values,
                                                                       names_being_expanded=frozenset()):
    """The text as the agent reads it, without Python's quotes and prefixes: a name that
    module_string_values maps, given as a + operand or an f-string field with no conversion or format
    spec, becomes its value, rendered the same way; any other f-string field or non-literal operand
    becomes <its source>, as {path} becomes <path>. So does a name whose value is being expanded
    already, so that two constants naming each other end. module_string_values holds only the names
    module_level_string_values_whose_name_the_file_binds_only_once keeps, so where a name stands in
    the file never changes what it renders as."""
    def render(part):
        return render_string_node_text_as_agent_reads_it_with_placeholder_stand_ins(
            part, module_string_values, names_being_expanded)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value if isinstance(part, ast.Constant)
                       else render(part.value)
                       if part.conversion == -1 and part.format_spec is None
                       else "<" + ast.unparse(part.value) + ">"
                       for part in node.values)
    if is_addition_chain_holding_string_literal(node):
        return "".join(render(operand) for operand in addition_chain_operands(node))
    if isinstance(node, ast.Name) and node.id in module_string_values and node.id not in names_being_expanded:
        return render_string_node_text_as_agent_reads_it_with_placeholder_stand_ins(
            module_string_values[node.id], module_string_values, names_being_expanded | {node.id})
    return "<" + ast.unparse(node) + ">"


def literal_text_of_string_node(node):
    """The words the node's string literals give: its literal pieces, with each f-string field or
    non-literal + operand replaced by literal_text_carried_by_placeholder. A plain string literal
    is its value, braces included, since its braces reach the agent as written."""
    if isinstance(node, ast.BinOp):
        return message_text_of_addition_chain(addition_chain_operands(node), literal_only=True)
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value if isinstance(part, ast.Constant)
                       else literal_text_carried_by_placeholder(part.value) for part in node.values)
    return node.value


def literal_text_carried_by_placeholder(expression):
    """The literal text of each string the expression's value may carry, space-separated, as
    string_nodes_without_f_string_parts finds them: up and down in {'up' if ok else 'down'};
    nothing from a name, a subscript's key, a join's separator or a format spec."""
    return " ".join(literal_text_of_string_node(node) for node in string_nodes_without_f_string_parts(expression))


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


def calls_and_parameters_they_see(nodes, parameters):
    """Each call among the nodes, with the parameters a name in it still refers to: inside a
    nested lambda its own parameters and the names it binds with := hide them, inside a nested
    function its parameters and the names its body binds, as scope_assigned_names says, and inside a nested class body the names that body binds, in the whole
    class, functions and lambdas nested in it included, though Python skips class scope for those.
    A comprehension's target hides them in the comprehension's later parts, as
    comprehension_parts_with_names_they_hide says. A nested definition's defaults, decorators and
    bases see the parameters as its enclosing scope does, less its type parameters' names in the
    parts type_parameter_scope_expressions names."""
    for node in nodes:
        if isinstance(node, COMPREHENSION_TYPES):
            for part, hidden in comprehension_parts_with_names_they_hide(node):
                yield from calls_and_parameters_they_see([part], parameters - hidden)
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            yield from calls_and_parameters_they_see(definition_time_expressions(node), parameters)
            yield from calls_and_parameters_they_see(type_parameter_scope_expressions(node),
                                                     parameters - type_parameter_names(node))
            if isinstance(node, ast.Lambda):
                hidden = function_parameter_names(node) | scope_assigned_names(node)
            elif isinstance(node, ast.ClassDef):
                hidden = scope_assigned_names(node)
            else:
                hidden = function_parameter_names(node) | scope_assigned_names(node)
            yield from calls_and_parameters_they_see(
                [node.body] if isinstance(node, ast.Lambda) else node.body, parameters - hidden)
            continue
        if isinstance(node, ast.Call):
            yield node, parameters
        yield from calls_and_parameters_they_see(ast.iter_child_nodes(node), parameters)


def function_parameter_names(function):
    arguments = function.args
    return {argument.arg for argument in [*arguments.posonlyargs, *arguments.args,
                                          *arguments.kwonlyargs, arguments.vararg,
                                          arguments.kwarg] if argument is not None}


def helper_printers_in_tree(tree):
    """Each function defined once at module level that prints one of its own parameters, mapped to
    (positions, names) of those parameters. A parameter is printed when an argument of print, of
    sys.stdout.write or sys.stderr.write, of `<parameter>.write`, as in say(stream, text), or of a
    call to another helper printer in a printed position carries its text, as names_carried_as_text
    says, where no nested lambda, function or class body hides the parameter's name."""
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
            # A parameter named like a helper printer hides it inside this function.
            visible_helper_printers = {name: entry for name, entry in helper_printers.items()
                                       if name not in parameters}
            printed = set()
            for call, visible in calls_and_parameters_they_see(function.body, parameters):
                for argument in printed_arguments(call, visible_helper_printers, visible):
                    printed.update(name for name in names_carried_as_text(argument) if name in visible)
            if not printed:
                continue
            entry = ({index for index, name in enumerate(positional) if name in printed}, printed)
            if helper_printers.get(function.name) != entry:
                helper_printers[function.name] = entry
                changed = True
    return helper_printers


class AgentFacingStringNodeCollector(ast.NodeVisitor):
    """Record string spans and their call, assignment or exception context."""

    def __init__(self, module_string_values=None, helper_printers=None, text_returning_function_names=(),
                 rendered_module_string_values=None):
        self.enclosing_names = []
        # The parameter names of each enclosing function, which hide a helper printer's name.
        self.enclosing_parameter_names = []
        self.string_entries = []
        # (id(node), label) -> the entry recorded for that node in that context.
        self.entries_by_node_context = {}
        # Name -> the string expression assigned to the name, once, at module level.
        self.module_string_values = module_string_values or {}
        # Function name -> (positions, names) of the parameters it prints.
        self.helper_printers = helper_printers or {}
        # For each enclosing function, its local name -> the string expressions bound to it.
        self.enclosing_local_string_bindings = []
        # Functions whose returned strings are collected, and those this pass found called for text.
        self.text_returning_function_names = set(text_returning_function_names)
        self.function_names_called_for_text = set()
        # The module constants a placeholder renders as their values.
        self.rendered_module_string_values = (self.module_string_values if rendered_module_string_values is None
                                              else rendered_module_string_values)

    def collect_expression_strings(self, expression, label, kind="message"):
        if expression is None:
            return
        if self.enclosing_names:
            label += f" in {'.'.join(self.enclosing_names)}()"
        for node in string_nodes_without_f_string_parts(expression):
            identity = (id(node), label)
            if identity in self.entries_by_node_context:
                if kind == "prompt":
                    self.entries_by_node_context[identity]["kind"] = "prompt"
                continue
            entry = {"line": node.lineno, "end_line": node.end_lineno, "label": label,
                     "text": text_of_string_node(node), "literal_text": literal_text_of_string_node(node),
                     "placeholder_value_source_code_texts": placeholder_sources_of_string_node(node),
                     "text_as_agent_reads_it_with_placeholder_stand_ins":
                         render_string_node_text_as_agent_reads_it_with_placeholder_stand_ins(
                             node, self.rendered_module_string_values),
                     "kind": kind}
            self.entries_by_node_context[identity] = entry
            self.string_entries.append(entry)

    def visit_scope(self, node):
        """Visit the expressions a function, lambda or class definition evaluates where it
        stands, such as defaults, decorators and bases, in the enclosing scope, less its type
        parameters' names where type_parameter_scope_expressions says, then its body in
        its own scope. A function's body follows only its own local names. A lambda's or a class
        body's follows the enclosing scope's, less the names the lambda takes as parameters or
        binds with `:=`, or the class body assigns or declares global; the class body's names stay hidden in the functions and lambdas
        nested in the class. Its own parameters hide a helper printer's name, as the enclosing
        function's still do."""
        for expression in definition_time_expressions(node):
            self.visit(expression)
        self.visit_with_names_hidden(type_parameter_scope_expressions(node), type_parameter_names(node))
        outer = self.enclosing_local_string_bindings[-1] if self.enclosing_local_string_bindings else {}
        if isinstance(node, ast.Lambda):
            parameters = function_parameter_names(node)
            hidden = parameters | scope_assigned_names(node)
            bindings = {name: values for name, values in outer.items() if name not in hidden}
        elif isinstance(node, ast.ClassDef):
            parameters = set()
            assigned = scope_assigned_names(node)
            bindings = {name: values for name, values in outer.items() if name not in assigned}
        else:
            parameters = function_parameter_names(node)
            bindings = local_string_bindings(node)
        self.enclosing_parameter_names.append(parameters)
        self.enclosing_local_string_bindings.append(bindings)
        if isinstance(node, ast.Lambda):
            self.visit(node.body)
        else:
            self.enclosing_names.append(node.name)
            for statement in node.body:
                self.visit(statement)
            self.enclosing_names.pop()
        self.enclosing_local_string_bindings.pop()
        self.enclosing_parameter_names.pop()

    visit_FunctionDef = visit_scope
    visit_AsyncFunctionDef = visit_scope
    visit_Lambda = visit_scope
    visit_ClassDef = visit_scope

    def visit_with_names_hidden(self, nodes, hidden):
        """Visit the nodes with the innermost function's locals of the hidden names not followed."""
        if not hidden:
            for node in nodes:
                self.visit(node)
            return
        has_locals = bool(self.enclosing_local_string_bindings)
        if has_locals:
            outer = self.enclosing_local_string_bindings[-1]
            self.enclosing_local_string_bindings.append(
                {name: values for name, values in outer.items() if name not in hidden})
        for node in nodes:
            self.visit(node)
        if has_locals:
            self.enclosing_local_string_bindings.pop()

    def visit_comprehension_parts(self, node):
        """Visit a comprehension's parts, each with the targets bound before it hiding the
        innermost function's locals of those names."""
        for part, hidden in comprehension_parts_with_names_they_hide(node):
            self.visit_with_names_hidden([part], hidden)

    visit_ListComp = visit_comprehension_parts
    visit_SetComp = visit_comprehension_parts
    visit_GeneratorExp = visit_comprehension_parts
    visit_DictComp = visit_comprehension_parts

    def collect_local_strings_reaching(self, expression, is_prompt=False):
        """Collect, at its own lines, each string bound to a local name of the innermost
        function whose text the expression carries, as names_carried_as_text says, and through
        those strings each local they carry in turn. A string is a prompt when is_prompt is set
        or it reaches the expression through a name containing "prompt"."""
        if expression is None or not self.enclosing_local_string_bindings:
            return
        bindings = self.enclosing_local_string_bindings[-1]
        pending = [(name, is_prompt) for name in names_carried_as_text(expression)]
        followed = set()
        while pending:
            name, reached_as_prompt = pending.pop()
            reached_as_prompt = reached_as_prompt or "prompt" in name.lower()
            if (name, reached_as_prompt) in followed or name not in bindings:
                continue
            followed.add((name, reached_as_prompt))
            for value in bindings[name]:
                self.collect_expression_strings(value, f"{name} =",
                                                "prompt" if reached_as_prompt else "message")
                self.function_names_called_for_text.update(function_names_called_for_text(value))
                pending.extend((used, reached_as_prompt) for used in names_carried_as_text(value))

    def collect_sink_expression(self, expression, label):
        self.collect_expression_strings(expression, label)
        self.collect_local_strings_reaching(expression)
        if expression is not None:
            self.function_names_called_for_text.update(function_names_called_for_text(expression))

    def is_helper_printer_call(self, call_name):
        return call_name in self.helper_printers and not any(
            call_name in names for names in self.enclosing_parameter_names)

    def visit_Call(self, node):
        call_name = ast.unparse(node.func)
        if call_name in PRINTING_CALL_NAMES or self.is_helper_printer_call(call_name):
            label = call_name if call_name in PRINTING_CALL_NAMES else call_name + "()"
            for argument in printed_arguments(node, self.helper_printers):
                self.collect_sink_expression(argument, label)
        self.generic_visit(node)

    def visit_Raise(self, node):
        self.collect_sink_expression(node.exc, "raise")
        if isinstance(node.exc, ast.Call):
            for argument in node.exc.args:
                self.collect_local_strings_reaching(argument)
                self.function_names_called_for_text.update(function_names_called_for_text(argument))
        self.generic_visit(node)

    def visit_assignment_value(self, node):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and variable_name_has_tool_message_to_agent_suffix(target.id):
                self.collect_sink_expression(node.value, f"{target.id} =")
        self.generic_visit(node)

    visit_Assign = visit_assignment_value
    visit_AnnAssign = visit_assignment_value
    visit_AugAssign = visit_assignment_value

    def visit_Dict(self, node):
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value in TOOL_MESSAGE_TO_AGENT_HOOK_OUTPUT_KEYS):
                continue
            label = f'"{key.value}" value'
            if isinstance(value, ast.Name):
                if self.enclosing_local_string_bindings and value.id in self.enclosing_local_string_bindings[-1]:
                    self.collect_local_strings_reaching(value)
                # A name ending in a suffix is collected already, at its assignment.
                elif value.id in self.module_string_values and not variable_name_has_tool_message_to_agent_suffix(value.id):
                    self.collect_expression_strings(self.module_string_values[value.id], f"{label} {value.id} =")
            elif string_building_parts(value):
                self.collect_sink_expression(value, label)
        self.generic_visit(node)

    def visit_Return(self, node):
        is_prompt = bool(self.enclosing_names) and "prompt" in self.enclosing_names[-1].lower()
        if (node.value is not None and self.enclosing_names
                and self.enclosing_names[-1] in self.text_returning_function_names):
            self.collect_expression_strings(node.value, "return", "prompt" if is_prompt else "message")
            self.function_names_called_for_text.update(function_names_called_for_text(node.value))
        # A local returned inside a list, a tuple or a call is data, such as a command's argument.
        if isinstance(node.value, ast.Name) or (node.value is not None and string_building_parts(node.value)):
            self.collect_local_strings_reaching(node.value, is_prompt=is_prompt)
        self.generic_visit(node)


def is_string_expression(expression):
    """A string literal, an f-string, or a + of such expressions."""
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        return is_string_expression(expression.left) and is_string_expression(expression.right)
    return isinstance(expression, ast.JoinedStr) or (
        isinstance(expression, ast.Constant) and isinstance(expression.value, str))


def string_building_parts(expression):
    """The parts of the expression that build a string: the expression itself when it is a
    non-empty string literal, an f-string, a + chain with a string literal or f-string among its
    operands, a string literal % something, or a string literal's join; and such parts among the branches of a
    conditional expression, its condition left out."""
    if isinstance(expression, ast.IfExp):
        return [*string_building_parts(expression.body), *string_building_parts(expression.orelse)]
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        builds = any(is_string_literal_node(operand) for operand in addition_chain_operands(expression))
    elif isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Mod):
        builds = is_string_literal_node(expression.left)
    elif isinstance(expression, ast.Constant):
        builds = isinstance(expression.value, str) and expression.value != ""
    else:
        builds = isinstance(expression, ast.JoinedStr) or is_join_on_string_literal(expression)
    return [expression] if builds else []


def is_join_on_string_literal(expression):
    return (isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute)
            and expression.func.attr == "join" and is_string_literal_node(expression.func.value))


def names_carried_as_text(expression):
    """The names whose text the expression's value carries: those outside a call and those in the
    arguments of a string literal's join, in the children text_carrying_children names. A name a
    comprehension binds as its target is the comprehension's own, so it is left out there."""
    if isinstance(expression, ast.Name):
        yield expression.id
    elif is_join_on_string_literal(expression):
        for argument in expression.args:
            yield from names_carried_as_text(argument)
    elif isinstance(expression, COMPREHENSION_TYPES):
        bound = set()
        # The first iterable is evaluated outside the comprehension, before any target is bound.
        for generator in expression.generators:
            yield from (name for name in names_carried_as_text(generator.iter) if name not in bound)
            bound |= comprehension_target_names(generator.target)
        element = expression.value if isinstance(expression, ast.DictComp) else expression.elt
        yield from (name for name in names_carried_as_text(element) if name not in bound)
    elif not isinstance(expression, ast.Call):
        for child in text_carrying_children(expression):
            yield from names_carried_as_text(child)


def function_names_called_for_text(expression):
    """The bare names of the calls whose results the expression's value carries as text, found
    where names_carried_as_text finds names."""
    if isinstance(expression, ast.Call):
        if isinstance(expression.func, ast.Name):
            yield expression.func.id
        elif is_join_on_string_literal(expression):
            for argument in expression.args:
                yield from function_names_called_for_text(argument)
    else:
        for child in text_carrying_children(expression):
            yield from function_names_called_for_text(child)


def definition_time_expressions(definition):
    """The expressions a function, lambda or class definition evaluates in the scope it stands
    in, its own type parameters' names not visible: decorators and parameter defaults, and, for
    a definition without type parameters, parameter and return annotations and a class's bases
    and keywords."""
    if isinstance(definition, ast.Lambda):
        arguments = definition.args
        return [*arguments.defaults, *(default for default in arguments.kw_defaults if default is not None)]
    expressions = list(definition.decorator_list)
    if isinstance(definition, ast.FunctionDef | ast.AsyncFunctionDef):
        arguments = definition.args
        expressions += [*arguments.defaults, *(default for default in arguments.kw_defaults if default is not None)]
    if not type_parameter_names(definition):
        expressions += annotation_and_base_expressions(definition)
    return expressions


def annotation_and_base_expressions(definition):
    """A function's parameter and return annotations, or a class's bases and keywords."""
    if isinstance(definition, ast.ClassDef):
        return [*definition.bases, *(keyword.value for keyword in definition.keywords)]
    arguments = definition.args
    annotations = [argument.annotation for argument in
                   [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                    arguments.vararg, arguments.kwarg] if argument is not None]
    return [annotation for annotation in [*annotations, definition.returns] if annotation is not None]


def type_parameter_scope_expressions(definition):
    """The expressions of a definition with type parameters, as in class Holder[T: bound], that
    see those parameters' names (PEP 695): each type parameter's bound and default, and the
    annotations, bases and keywords annotation_and_base_expressions names. Empty for a
    definition without type parameters."""
    if not type_parameter_names(definition):
        return []
    bounds_and_defaults = [expression for parameter in definition.type_params
                           for expression in (getattr(parameter, "bound", None),
                                              getattr(parameter, "default_value", None))
                           if expression is not None]
    return [*bounds_and_defaults, *annotation_and_base_expressions(definition)]


def type_parameter_names(definition):
    """The names of a definition's type parameters, as T in class Holder[T]."""
    return {parameter.name for parameter in getattr(definition, "type_params", [])}


def comprehension_target_names(target):
    """The names a comprehension's target binds: those it stores to. A name read inside the
    target, as text is in `for messages[text] in items`, is not bound."""
    return {node.id for node in ast.walk(target) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}


def comprehension_parts_with_names_they_hide(comprehension):
    """Each part of a comprehension, in the order Python evaluates them, with the target names
    bound before it, which refer to the comprehension's own names there: the first iterable,
    evaluated outside before any target is bound, sees none; each later iterable, target,
    condition and the element see the targets bound so far."""
    bound = frozenset()
    for generator in comprehension.generators:
        yield generator.iter, bound
        bound = bound | comprehension_target_names(generator.target)
        yield generator.target, bound
        for condition in generator.ifs:
            yield condition, bound
    elements = ([comprehension.key, comprehension.value] if isinstance(comprehension, ast.DictComp)
                else [comprehension.elt])
    for element in elements:
        yield element, bound


def scope_assigned_names(scope):
    """The names a function's, lambda's or class's own body binds: names it stores to, outside a
    comprehension's target, which is the comprehension's own; names it imports, catches with
    except ... as, or captures in a match pattern; the functions and classes it defines; and the
    names it declares global, which refer to the module's names, not the enclosing function's. A
    name it declares nonlocal is left out, since it binds the enclosing function's name."""
    nodes = list(nodes_in_own_scope(scope))
    comprehension_targets = {id(name) for node in nodes if isinstance(node, ast.comprehension)
                             for name in ast.walk(node.target)}
    names = set()
    nonlocal_names = set()
    for node in nodes:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and id(node) not in comprehension_targets:
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
        elif isinstance(node, ast.Nonlocal):
            nonlocal_names.update(node.names)
        elif isinstance(node, ast.Global):
            names.update(node.names)
    return (names | {definition.name for definition in scope_direct_definitions(scope)}) - nonlocal_names


def scope_body_nodes(scope):
    """A function's or class's body statements, or a lambda's body expression, as a list."""
    return [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)


def scope_direct_definitions(scope):
    """The functions and classes defined in the scope's own body, not inside a nested one."""
    found = []
    pending = scope_body_nodes(scope)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append(node)
            continue
        if isinstance(node, ast.Lambda):
            continue
        pending.extend(ast.iter_child_nodes(node))
    return found


def nodes_in_own_scope(function):
    """The nodes of the function's, lambda's or class's body, leaving out the bodies of the
    functions, lambdas and classes defined inside it, which have names of their own."""
    pending = scope_body_nodes(function)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield node
        pending.extend(ast.iter_child_nodes(node))


def local_string_bindings(function):
    """Each plain name the function's own body assigns, with =, an annotation or +=, a
    string-building expression, mapped to every such expression, in every branch."""
    bindings = {}
    for node in nodes_in_own_scope(function):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) or (isinstance(node, ast.AugAssign)
                                                  and isinstance(node.op, ast.Add)):
            targets = [node.target]
        else:
            continue
        parts = string_building_parts(node.value) if node.value is not None else []
        for target in targets:
            if parts and isinstance(target, ast.Name):
                bindings.setdefault(target.id, []).extend(parts)
    return bindings


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


def binding_count_of_each_name_anywhere_in_the_file(tree):
    """Each name, with how many times the file binds it: assignment and every other store, including a
    loop's, a comprehension's and a := target; deletion; a parameter of any function or lambda; an
    import; except ... as; a match capture; a function or class definition's name; a type parameter;
    and a global or nonlocal declaration, which counts as a binding of its own."""
    counts = {}
    def count(name):
        counts[name] = counts.get(name, 0) + 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            count(node.id)
        elif isinstance(node, ast.arg):
            count(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                count(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            count(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            count(node.rest)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                count(name)
        elif isinstance(node, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple)):
            count(node.name)
    return counts


def module_level_string_values_whose_name_the_file_binds_only_once(tree, module_string_values):
    """The module constants whose one module-level assignment is the only binding of their name
    anywhere in the file, so a placeholder naming one means that constant wherever it stands. A
    name a function also binds, takes as a parameter, declares global or loops over keeps its
    <source> stand-in, which may hide a value Python would use, but never shows a wrong one."""
    counts = binding_count_of_each_name_anywhere_in_the_file(tree)
    return {name: value for name, value in module_string_values.items() if counts.get(name) == 1}


def tool_message_to_agent_string_nodes_in_source(source):
    """Each entry holds line and end_line, counted from 1, label, text, literal_text,
    placeholder_value_source_code_texts, text_as_agent_reads_it_with_placeholder_stand_ins and kind,
    "prompt" or "message".
    Source that is None or does not parse yields no entries."""
    if source is None:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    module_string_values = module_level_string_values(tree)
    rendered_module_string_values = module_level_string_values_whose_name_the_file_binds_only_once(
        tree, module_string_values)
    helper_printers = helper_printers_in_tree(tree)
    # A pass can find a function called for text only after visiting its definition, and a
    # followed function's return can name another, so passes repeat until none is new.
    followed = set()
    while True:
        collector = AgentFacingStringNodeCollector(module_string_values, helper_printers, followed,
                                                   rendered_module_string_values)
        if ("__doc__" in source and tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)):
            collector.collect_expression_strings(tree.body[0].value, "module docstring (printed by --help)")
        collector.visit(tree)
        if collector.function_names_called_for_text <= followed:
            break
        followed |= collector.function_names_called_for_text
    return sorted(collector.string_entries, key=lambda entry: (entry["line"], entry["label"]))
