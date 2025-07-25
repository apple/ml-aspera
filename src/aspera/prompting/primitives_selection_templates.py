#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from textwrap import dedent


def agent_primitives_selection_template() -> str:
    template = """\
    You are a programmer using a Python library of personal assistant tools in order to write a program that executes a user query.
    You will be shown a query followed by the signatures from a Python module, and will be asked to formulate Python import statements importing any tools that might be relevant to writing a program that executes the user query.
    If there are no relevant tools in the current module being shown, simply output None.

    Module:
    {{ module }}
    Query: {{ query }}
    Think carefully, and output the relevant Python import statements, or None. Any code you write must be included
    in a Python markdown block (ie start with a "```python" sequence and end with "```").
    """
    return dedent(template)


def system_primitives_selection_template() -> str:
    template = """\
    You are a programmer using a Python library of personal assistant tools in order to write a program that executes a user query.
    You will be shown signatures from a Python module and a query, and will be asked to formulate Python import statements importing any tools that might be relevant to writing a program that executes the user query.
    """
    return dedent(template)


def system_primitives_selection_template_with_guidelines() -> str:
    template = """\
    You are a programmer using a Python library of personal assistant tools in order to write a program that executes a user query.
    You will be shown signatures from a Python module and a query, and will be asked to formulate Python import statements importing any tools that might be relevant to writing a program that executes the user query.

    {% if guidelines -%}
    When writing the program, you will be asked to follow the {{ guidelines | length }} structure guidelines listed below.
    {% for instruction in guidelines %}
    {{ loop.index }}. {{ instruction }}
    {%- endfor %}
    Use this additional information to guide your import decisions.
    {%- else %}
    {%- endif %}
    """
    return dedent(template)


def user_primitives_selection_template() -> str:
    template = """\
    Module:
    {{ module }}
    Query: {{ query }}

    Think carefully, and output the relevant Python import statements, or None. Any code you write must be included in a Python markdown block (ie start with a "```python" sequence and end with "```").
    If there are no relevant tools in the current module being shown, simply output None.
    """
    return dedent(template)


def agent_primitives_selection_template_with_guidelines() -> str:
    template = """\
    You are a programmer using a Python library of personal assistant tools in order to write a program that executes a user query.
    You will be shown signatures from a Python module and a query, and will be asked to formulate Python import statements importing any tools that might be relevant to writing a program that executes the user query.

    {% if guidelines -%}
    When writing the program, you will be asked to follow the {{ guidelines | length }} structure guidelines listed below.
    {% for instruction in guidelines %}
    {{ loop.index }}. {{ instruction }}
    {%- endfor %}
    Use this additional information to guide your import decisions.
    {%- else %}
    {%- endif %}

    Module:
    {{ module }}
    Query: {{ query }}

    Think carefully, and output the relevant Python import statements, or None. Any code you write must be included in a Python markdown block (ie start with a "```python" sequence and end with "```").
    If there are no relevant tools in the current module being shown, simply output None.
    """
    return dedent(template)
