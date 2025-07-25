#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from copy import deepcopy
from typing import Any

from omegaconf import DictConfig
from rich.prompt import Prompt

from aspera.completer.utils import MessageList, get_message, print_messages
from aspera.constants import SESSION_LOG_NAME
from aspera.dataset_schema import (
    AnnotatedDatapoints,
    DataPoint,
    EditedDataPoint,
    create_datapoints,
)
from aspera.interactive.display import (
    display_edits_multitable,
    display_programs,
    display_queries,
)
from aspera.interactive.session import InteractiveSession
from aspera.interactive.utils import SessionEndException
from aspera.prompting.user_turn_prompts import (
    ProgramGenerationFeedbackUserTurnTemplate,
    UserTurnTemplate,
)
from aspera.readers import query_loader

logger = logging.getLogger(__name__)


def assert_queries_match(datapoints: list[DataPoint], queries: list[str]):
    dp_queries = {q.query for q in datapoints}
    assert all(q in dp_queries for q in queries)


class QueryAnnotationSession(InteractiveSession):
    def __init__(self, config: DictConfig):
        super().__init__(config)
        # queries for which we could not parse the output from the completion
        # (eg because the completion was terminated due to completion length
        # errors)
        self._unparsed_queries: list[str] = []

    @property
    def retry_queries(self):
        """Returns all queries which could not be annotated
        (eg because the output token budget did not allow us to
        process all the queries)."""
        to_return = deepcopy(self._unparsed_queries)
        self._unparsed_queries = []
        return to_return

    def _maybe_collect_feedback(
        self,
        datapoints: list[EditedDataPoint] | None,
    ) -> list[EditedDataPoint] | None:
        """In-place filter `datapoints` to retain only those to be fed back into the model for
        feedback."""
        if datapoints is None:
            return
        while True:
            continue_input = Prompt.ask(
                "[bold green]Would you like to send feedback to the model about generated programs? (yes/no)[/bold green]",  # noqa
                default="no",
            )
            if continue_input.lower() in ["yes", "no"]:
                break
        if continue_input.lower() == "yes":
            self._console.print(
                "Enter comma-separated list of query IDs to incude as feedback or press Enter if none:",  # noqa
                style="info",
            )
            for i, datapoint in enumerate(datapoints):
                datapoint["query_id"] = str(i)
            display_edits_multitable(datapoints)
            feedback_input = Prompt.ask("Feedback IDs")
            if feedback_input:
                feedback_ids = {id_.strip() for id_ in set(feedback_input.split(","))}
                return [e for e in datapoints if e["query_id"] in feedback_ids]

    def _maybe_update_chat_history_with_feedback(
        self,
        datapoints: list[EditedDataPoint] | None,
        session_messages: MessageList,
        current_completion: str,
    ):
        """Update the chat history with a turn providing the agent with feedback
        on the programs generated at the previous interaction."""
        if not datapoints or datapoints is None:
            return
        # extend the chat history with the last assistant response
        existing_messages = {m["content"] for m in self._chat_history}
        state_update = [
            m for m in session_messages if m["content"] in existing_messages
        ]
        state_update.append(get_message(current_completion, role="assistant"))
        # create feedback turn from edited programs
        templates = self._templates
        turn_template = ProgramGenerationFeedbackUserTurnTemplate(
            template_factory=templates.user_program_edit_feedback
        )
        self._chat_history.append(turn_template.get_prompt({"feedback": datapoints}))
        if self._show_messages:
            print_messages(self._chat_history)

    def get_session_state(
        self, completion: str, messages: MessageList
    ) -> dict[str, Any]:
        session_state = {
            "chat_history": messages,
            "last_user_turn": messages[-1]["content"],
            "completion": completion,
            "queries": self.processed_queries,
            "unparsed_queries": self._unparsed_queries,
            "budget": self._completer.budget_info,
        }
        return session_state

    def annotate_batch(self, queries: list[str]):
        """Annotate a list of queries with Python programs."""
        messages = deepcopy(self._chat_history)
        templates = self._templates
        # the system turn is added in the superclass during initialisation
        messages.append(
            UserTurnTemplate(template_factory=templates.annotation_request).get_prompt(
                {"queries": queries}
            ),
        )
        log_opts = {"overwrite_last": True, "overwrite_fields": ["budget"]}
        llm_output = self._generate_programs(
            messages, log_name=SESSION_LOG_NAME, log_opts=log_opts
        )
        datapoints: list[DataPoint] = create_datapoints(
            llm_output.programs, queries, self._scenario, self._unparsed_queries
        )
        display_programs(datapoints)
        assert_queries_match(datapoints, queries)
        self.processed_queries += [q.query for q in datapoints]
        annotated_queries: AnnotatedDatapoints = (
            self._session_manager.annotate_query_execution(
                data=datapoints, scenario=self._scenario
            )
        )
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
        # optionally feedback corrected programs to the model to (hopefully) avoid correcting
        # the same mistake ad nauseam
        feedback_datapoints = self._maybe_collect_feedback(annotated_queries.edited)
        self._maybe_update_chat_history_with_feedback(
            feedback_datapoints, messages, llm_output.completion
        )
        session_state = self.get_session_state(llm_output.completion, messages)
        self._save(**session_state)

    def _initialise_queries(self):
        """Remember queries that have already been processed, to
        support skipping them if annotation proceeds over multiple
        interactive sessions."""
        if self._session_log is None:
            self._unparsed_queries = []
            self.processed_queries = []
            return
        logger.info("Loading previously annotated queries")
        self._unparsed_queries = self._session_log.unparsed_queries
        self.processed_queries = self._session_log.queries


def next_step_message():
    continue_input = Prompt.ask(
        "[bold green]Annotate another batch of queries? (yes/no)[/bold green]",  # noqa
        default="yes",
        choices=["yes", "no"],
    )
    if continue_input.lower() == "no":
        raise SessionEndException


def load_queries(session: QueryAnnotationSession) -> list[str]:
    """Load the queries, skipping any queries already
    processed if the session was restored."""

    all_queries = list(session.config.queries)
    in_corpus = query_loader(session.config.annotation.corpus_dir)
    all_queries = [q for q in all_queries if q not in in_corpus]
    if annotated := session.processed_queries:
        logger.info(
            "Interactive session restored; the following queries will be skipped:"
        )
        display_queries(annotated)
        to_process = [q for q in all_queries if q not in annotated]
        assert len(to_process) != len(all_queries)
        return to_process
    return all_queries
