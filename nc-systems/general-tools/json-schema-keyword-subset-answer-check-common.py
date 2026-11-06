#!/usr/bin/env python3
"""Check a model's structured answer against the JSON Schema the model was given.

answer_problems checks the keywords in CHECKED_SCHEMA_KEYWORDS and the types in
JSON_TYPES, and nothing else; a schema keyword outside them is not checked.
So a caller first runs schema_keywords_and_types_the_answer_check_does_not_enforce
on its schema and refuses to run when it lists anything, rather than accept
answers that break a rule no one checks. The agent-binaries enforce a schema
by their own rules, which a caller cannot see, so the caller checks the
answer here as well.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "json_schema_keyword_subset_answer_check_common", <path>)
"""

CHECKED_SCHEMA_KEYWORDS = {"description", "type", "enum", "minLength", "minimum", "required",
                           "additionalProperties", "properties", "items"}
JSON_TYPES = {"object": dict, "array": list, "string": str, "integer": int}


def schema_keywords_and_types_the_answer_check_does_not_enforce(schema, where="the schema"):
    """Return each keyword or type in schema that answer_problems does not check."""
    found = [f"{where}: {keyword}" for keyword in schema if keyword not in CHECKED_SCHEMA_KEYWORDS]
    if "type" in schema and schema["type"] not in JSON_TYPES:
        found.append(f"{where}: type {schema['type']}")
    nested = [(property_schema, f"{where}.{name}")
              for name, property_schema in schema.get("properties", {}).items()]
    if "items" in schema:
        nested.append((schema["items"], f"{where}[]"))
    for nested_schema, nested_where in nested:
        found += schema_keywords_and_types_the_answer_check_does_not_enforce(
            nested_schema, nested_where)
    return found


def answer_problems(value, schema, where="the answer"):
    """Return what makes value not one the schema accepts; empty when the schema accepts it."""
    expected = schema.get("type")
    if expected and (not isinstance(value, JSON_TYPES[expected]) or isinstance(value, bool)):
        return [f"{where} is {type(value).__name__}, not {expected}"]
    problems = []
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where} {value!r} is not one of "
                        f"{', '.join(str(allowed) for allowed in schema['enum'])}")
    if "minLength" in schema and len(value) < schema["minLength"]:
        problems.append(f"{where} is shorter than {schema['minLength']} characters")
    if "minimum" in schema and value < schema["minimum"]:
        problems.append(f"{where} {value} is below the minimum {schema['minimum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        problems += [f"{where} has no {key}" for key in schema.get("required", [])
                     if key not in value]
        if schema.get("additionalProperties") is False:
            problems += [f"{where} has {key}, which the schema does not allow"
                         for key in sorted(set(value) - set(properties))]
        for key, property_schema in properties.items():
            if key in value:
                problems += answer_problems(value[key], property_schema, f"{where}'s {key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            problems += answer_problems(item, schema["items"], f"{where}[{index}]")
    return problems
