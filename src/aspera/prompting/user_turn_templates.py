#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from textwrap import dedent


def start_turn() -> str:
    template = """\
    Now it's your turn, help us out generate programs representing complex user utterances. Let us
    start with {{ n_programs }} programs.

    ```python
    """
    return dedent(template)


def start_turn_with_query_history() -> str:
    template = """\
    You have done a stellar job generating some brilliant programs and user queries already. To remind
    you of work you completed and keep things brief, we only show the queries extracted from the docstrings
    of programs you generated:
    {% for q in queries %}
    {{ loop.index }}. {{ q }}
    {%- endfor %}

    Now we have to generate more programs representing complex user utterances. Crucially, these should
    represent a complex set of new user queries, where the user tries to complete different tasks
    from the ones you generated above. *Do not merely paraphrase the queries you already generated* when
    synthesizing programs - think of new and original complex user tasks that our application backend
    supports.
    {% if focus -%}
    {{ focus }}

    {% endif -%}

    Let us generate {{ n_programs }} programs.

    ```python"""
    return dedent(template)


def annotation_start_turn() -> str:
    template = """\
    Now it's your turn. Please translate the queries below into `python` (3.11) programs using the examples
    above to guide your response format. The response should be inside a Python markdown block.
    {% for q in queries %}
    {{ loop.index }}. {{ q }}
    {%- endfor %}

    ```python"""
    return dedent(template)


def agent_user_turn_with_return_type_instruction() -> str:
    template = """\
    Now it's your turn. Please translate the query below into a `python` (3.11) program using the examples
    above to guide your response format. The response should be inside a Python markdown block.
    Write your solution inside a function with no arguments. There is no need to show example usage -
    do not call your solutions.

    {% if return_type -%}
    The return type of the solution should be `{{ return_type }}`.
    {%- endif %}
    {% for q in queries %}
    Query: {{ q }}
    {%- endfor %}

    ```python"""
    return dedent(template)


def annotation_edit_feedback() -> str:
    template = """\
    We have identified issues with your work. Please use the feedback below to guide your future responses.
    {% for example in feedback %}
    {{ loop.index }}. {{ example | edit_feedback_formatter }}
    {%- endfor %}"""
    return dedent(template)


def entity_generation_followup_prompt():
    """A user turn which follows-up the query & program generation to help simulate the
    environment state."""
    template = """\
    For testing purposes, we need to generate the underlying runtime state of the user device. Your task
    is to carefully analyse `{{ plan_name }}` along with the application code above and assist our testing team
    in setting up the runtime environment such that `{{ plan_name }}` can be executed and its outputs verified.
    To do so, you will need to generate a `python` function named `{{ setup_function_name }}`.

    We have implemented additional tooling you may find helpful for completing this task:

    ```python
    {{ setup_code }}
    ```

    You may use additional knowledge and create your own functions if needed - custom functions should be
    defined inside the `{{ setup_function_name }}` function. Note how we import modules in the standard
    python library locally inside the `{{ setup_function_name }}` and how our application code does not
    need to be imported (we automatically do so when we run the code).

    Here are some comprehensive examples your testing team colleagues shared to help you generate
    a high quality program that sets up the runtime environment correctly.

    ```python
    {{ runtime_setup_examples }}
    ```

    {% if guidelines.runtime_setup -%}
    ### Runtime environment setup guidelines ###
    The examples above follow the {{ guidelines.runtime_setup | length }} setup guidelines listed below.
    Do the same, clearly stating when you follow them in your comments, as demonstrated above.
    {% for instruction in guidelines.runtime_setup %}
    {{ loop.index }}. {{ instruction }}
    {%- endfor %}
    {%- else %}
    {%- endif %}

    Let's now write `{{ setup_function_name }}`, our developers wrote some TODOs to get you started.

    ```python
    {{ state_function_def }}
    ```"""
    return dedent(template)


def eval_function_followup_prompt():
    """A user turn which follows-up the query & runtime state generation programs that
    asks the LLM to generate test functions given a plan and the runtime state setup code.
    """
    template = """\
    We need some test code to check that `{{ plan_name }}` executes correctly on the user device.
    After a careful analysis of `{{ plan_name }}` and `{{ setup_function_name }}` (defined below),
    your task is to write a function `{{ test_function_name }}` to do so.

    We have implemented additional tooling you may find helpful for completing this task:

    ```python
    {{ setup_code }}
    ```

    ```python
    {{ testing_code }}
    ```

    You may use additional knowledge and create your own functions if needed - custom functions should be
    defined inside the `{{ test_function_name }}` function. Note how we import modules in the standard
    python library locally inside the `{{ test_function_name }}` and how our application code does not
    need to be imported (we automatically do so when we run the code).

    Here are some comprehensive examples your testing team colleagues wrote:

    ```python
    {{ evaluation_examples }}
    ```
    {% if guidelines.evaluation -%}
    ### Testing guidelines ###
    The examples above follow the {{ guidelines.evaluation | length }} setup guidelines listed below.
    Do the same, clearly stating when you follow them in your comments, as demonstrated above.
    {% for instruction in guidelines.evaluation %}
    {{ loop.index }}. {{ instruction }}
    {%- endfor %}
    {%- else %}
    {%- endif %}

     Here is the code that sets up the runtime environment for `{{ plan_name }}` execution:

     ```python
     {{ runtime_setup_program }}
     ```

    Write `{{ test_function_name }}`:

    ```python
    {{ eval_function_def }}
    ```"""
    return dedent(template)


def llm_evaluator():
    template = """\
    You should now evaluate the following program, which is executed at the current date, which is returned by now_()
    (Tuesday, 25th June 2024, 9:06 AM).

    Make sure to wrap your assessment (ie the `is_correct` function) in a Python markdown block
    (ie start with a '```python' string and end with '```'). Including code to fix any mistakes is not necessary
    - just provide a clear an concise docstring to explain your judgement. Ensure you escape any quotes you include
    appropriately so your docstrings are valid.

    # Request: {{ query }}
    {{ plan }}
    # Assessment:
    """
    return dedent(template)


def llm_evaluator_assessment_docstrings():
    template = """\
    You should now evaluate the following program, which is executed at the current date, which is returned by now_()
    (Tuesday, 25th June 2024, 9:06 AM).

    Make sure to wrap your assessment (ie the `is_correct` function) in a Python markdown block
    (ie start with a '```python' string and end with '```').

    Assessment docstrings:

    1. Including code to fix any mistakes is not necessary - just provide a clear an concise docstring to explain your judgement.
    2. Our docs rendering engine does not support Python markdown *inside* `is_correct` docstrings - if you must include code to highlight key issues, start snippets with <code/> and end them with </code>.
    3. Ensure you escape any quotes you include appropriately so that the docstrings can be parsed by our engine, which uses `ast.parse`

    # Request: {{ query }}
    {{ plan }}
    # Assessment:
    """
    return dedent(template)
