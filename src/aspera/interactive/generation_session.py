#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
import random
from copy import deepcopy

from hydra.utils import instantiate
from omegaconf import DictConfig
from rich.prompt import Prompt

from aspera.completer.utils import ChatMessage, MessageList
from aspera.constants import SESSION_LOG_NAME
from aspera.dataset_schema import AnnotatedDatapoints, DataPoint, create_datapoints
from aspera.interactive.annotation_manager import GenerationManager
from aspera.interactive.console_messages import CHANGE_GENERATION_FOCUS
from aspera.interactive.display import display_programs
from aspera.interactive.session import InteractiveSession
from aspera.interactive.utils import SessionEndException
from aspera.prompting.user_turn_prompts import (
    QueryHistoryUserTurnTemplate,
    UserTurnTemplate,
)

logger = logging.getLogger(__name__)

FOCUS_PROMPTS = (
    "Fantastic, these are some interesting examples. Keeping in mind our guidelines above let us \
    generate 10 more examples.Ensure they are distinct from the ones we provided and the ones you generated.",
    "We really seem to have under-explored our codebase a bit. There are no complex scenarios using the\
    `find_event` API. Moreover, `show_as_status` and `attendees_to_avoid` are also infrequently used, \
    as is perhaps `ends_at`. Finally, we don't seem to have queries that explore the organisational \
    hierarchy in detail - there are a lot of complex user behaviours that can be supported through our \
    interfaces and imagining `members` of the organisation. Let's see 20 programs,\
    different to the ones above and the best you can do.",
    "We have many good queries for event scheduling but the user probably wants to achieve much more \
    than scheduling. Let’s focus on really interesting, creative and natural queries where the \
    user manages their calendar. This can mean, for example,  swapping events order, creating new \
    events depending on a variety of conditions (eg dictated by other events, past events, \
    room availability, etc) cancelling events based on a variety of conditions (eg other meetings \
    in the calendar, room availability, attendees etc). Also, find_past_events is a really nice \
    tool we haven’t used much so far, let’s think of some cool queries with it too. \
    Queries should not be overly verbose, as usual.",
    "You can see we have a variety of queries. Now focus on attributes, functions and methods that are \
    not commonly used when solving these queries. Use your creativity to create natural, interesting tasks \
    that use our application backend that are not overly verbose or have overly long solutions. \
    Do not repeat or paraphrase any of the above queries, *do not schedule* any meetings!",
)
"""Examples of prompt to encourage diversity in query generation."""


class QueryGenerationSession(InteractiveSession):

    def __init__(self, config: DictConfig):
        super().__init__(config)
        self._session_manager = GenerationManager(config)
        self.processed_queries = list(instantiate(config.queries))
        self.batch_size = self.config.n_queries.initial
        # an instruction displayed at the start of the user turn that can
        # influence the content of the  generated queries
        # (eg "Focus on generating programs that require availability checking
        #   and conditional statements")
        #
        self._focus = ""
        random.seed(0)

    @staticmethod
    def generate_query_placeholders(count: int) -> list[str]:
        return [
            "Query: COPY QUERY FROM DOCSTRING (EDIT IF NEEDED)" for _ in range(count)
        ]

    @property
    def focus(self) -> str:
        return self._focus

    @focus.setter
    def focus(self, value: str):
        self._focus = value

    def _update_processed_queries(self, datapoints: AnnotatedDatapoints):
        for example in datapoints.edited + datapoints.correct:
            self.processed_queries.append(example.query)

    def get_generation_start_turn(self) -> ChatMessage:
        """Returns a user turn prompt that starts the
        query generation."""
        if self.processed_queries:
            return QueryHistoryUserTurnTemplate(
                template_factory=self._templates.user_start_with_query_history
            ).get_prompt(
                self._scenario,
                queries=self.processed_queries,
                focus=self._focus,
                n_programs=self.config.n_queries.initial,
            )
        return UserTurnTemplate(template_factory=self._templates.user_start).get_prompt(
            self._scenario, n_programs=self.config.n_queries.initial
        )

    def prepare_for_eval_assets_generation(self, messages: MessageList):
        """The initial user turn states the number of queries to be generated.
        Meanwhile, eval assets are generated for one query at a time, so
        the information in the user turn may be inconsistent with what is
        shown in the chat history."""
        if self.batch_size == 1:
            return
        messages.pop()
        messages.append(
            UserTurnTemplate(template_factory=self._templates.user_start).get_prompt(
                self._scenario, n_programs=1
            ),
        )

    def maybe_permute_history(self, annotated_datapoints: AnnotatedDatapoints):
        """Permute the query history if there is a single data-point that was
        quarantined. In this case, because, of caching, we'd get stuck generating
        the same thing."""
        if (
            len(annotated_datapoints.all) == 1
            and len(annotated_datapoints.discarded) == 1
        ):
            random.shuffle(self.processed_queries)

    def generate_queries(self):
        messages = deepcopy(self._chat_history)
        messages.append(self.get_generation_start_turn())
        log_opts = {"overwrite_last": True, "overwrite_fields": ["budget"]}
        llm_output = self._generate_programs(
            messages, log_name=SESSION_LOG_NAME, log_opts=log_opts
        )
        programs = llm_output.programs
        datapoints: list[DataPoint] = create_datapoints(
            programs,
            self.generate_query_placeholders(len(programs)),
            self._scenario,
        )
        display_programs(datapoints)
        annotated_queries: AnnotatedDatapoints = (
            self._session_manager.inspect_queries_and_execution_plans(
                data=datapoints, scenario=self._scenario
            )
        )
        self.maybe_permute_history(annotated_queries)
        self.prepare_for_eval_assets_generation(messages)
        # evaluation assets (ie runtime state setup code and query execution eval code
        #  are added to the annotated queries)
        self._maybe_generate_evaluation_assets(annotated_queries, messages)
        self._session_manager.save_assets(
            annotated_queries,
            self._scenario,
            self._selected_simulation_tools,
            self._selected_evaluation_tools,
        )
        # runs the setup code and the program and save the initial and final (ie after
        # executing the query) database states
        self._save_environment_state(annotated_queries)
        self._update_processed_queries(annotated_queries)
        session_state = self.get_session_state(llm_output.completion, messages)
        self._save(**session_state)


def maybe_change_focus(session: QueryGenerationSession):
    """We can influence what the LLM focuses on when generating
    the next query by instructions displayed at the start of
    the generation prompt."""

    session._console.print(CHANGE_GENERATION_FOCUS, style="info")
    session._console.print(f"The current focus is: {session.focus}")
    choice = Prompt.ask(
        "[bold red]Change focus?[/bold red]", default="no", choices=["yes", "no"]
    )
    if choice == "yes":
        user_input = Prompt.ask(
            "[bold green]Enter the focus instruction: [/bold green]"
        )
        session.focus = user_input.strip()


def next_step_message():
    continue_input = Prompt.ask(
        "[bold green]Generate more queries? (yes/no)[/bold green]",  # noqa
        default="yes",
        choices=["yes", "no"],
    )
    if continue_input.lower() == "no":
        raise SessionEndException
