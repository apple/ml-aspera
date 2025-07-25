#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import ast
import json
import logging
from functools import cached_property
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from aspera.aliases import ProgramStr, Query, QueryIdx
from aspera.code_utils.utils import remove_import_statements
from aspera.completer import CompleterType
from aspera.completer.utils import CompletionApiError, LLMPrompt
from aspera.constants import ExamplesModuleName
from aspera.evaluator import EvaluationResult, Evaluator, F1Score
from aspera.parser import (
    DocstringExtractor,
    ParserType,
    ProgramFinderError,
    ReturnValueExtractor,
)
from aspera.prompting.system_turn_prompts import LLMEvaluatorSystemTurnTemplate
from aspera.prompting.user_turn_prompts import UserTurnTemplate

logger = logging.getLogger(__name__)

GuidelineType = str
# see src/aspera/scenario.py::Guideline for types
SkippedInstances = int
# the number of instances skipped in F1 calculation
NOT_EVALUATED = "NOT_EVALUATED"
# update this if you are running the LLMEvaluator in
# debug mode to evaluate the first few datapoints
MAX_RESULTS_EVALUATED_DEBUG = 10

return_value_parser = ReturnValueExtractor()
docstring_parser = DocstringExtractor()


class EvaluationError(Exception):
    pass


class LLMJudgement(BaseModel):

    correct: bool | str
    assessment: str

    @classmethod
    def failed_to_judge(cls) -> "LLMJudgement":
        return cls(
            correct=NOT_EVALUATED,
            assessment="",
        )

    @classmethod
    def from_string(cls, program: ProgramStr) -> "LLMJudgement":
        try:
            ret_value = return_value_parser(program)
            assessment = docstring_parser(program)
            return cls(
                correct=ast.literal_eval(ret_value),
                assessment=assessment,
            )
        except (ValueError, IndentationError, SyntaxError) as e:
            logger.warning(
                f"LLM judgement could not be parsed. The program was {program}."
            )
            logger.warning(f"The exception was: {e}")
            return cls.failed_to_judge()


class LLMEvaluator(Evaluator):

    def __init__(
        self,
        res_path: str,
        out_dir: str,
        queries_dir: str,
        completer: CompleterType,
        parser: ParserType,
        system: Callable[..., str],
        user: Callable[..., str],
        examples_module: ExamplesModuleName,
        guidelines: dict[str, list[str]] | None = None,
        debug: bool = False,
    ):
        super().__init__(Path(queries_dir))
        self._correct: dict[Query, bool | str] = {}
        with open(res_path, "r") as f_in:
            self._results = [
                EvaluationResult.model_validate(json.loads(line)) for line in f_in
            ]
        self._results.sort(key=lambda x: int(x.query_id))
        if debug:
            logger.warning(
                "You are running the LLM evaluator in debug mode. "
                f"{MAX_RESULTS_EVALUATED_DEBUG} will be evaluated"
            )
            self._results = self._results[:MAX_RESULTS_EVALUATED_DEBUG]
        self.total_queries = len(self._results)
        self._completer = completer
        self._parser = parser.parser
        self._system_template: Callable[..., str] = system
        self._user_template: Callable[..., str] = user
        self._guidelines: dict[GuidelineType, list[str]] = guidelines or {}
        self._examples_module = examples_module
        self._judge_failures_cnt = 0
        self._res_path = Path(res_path)
        self._out_dir = Path(out_dir)
        self._prompts: dict[QueryIdx, LLMPrompt] = {}

    @property
    def name(self) -> str:
        return self._completer.model_name

    def _make_prompt(self, result: EvaluationResult) -> LLMPrompt:
        """Create a prompt for an LLM that can judge the correctness of the
        generated program."""
        annotation = self.load_annotation(result.query)
        annotation.scenario.guidelines.generation_labelling = self._guidelines.get(
            "generation_labelling", []
        )
        messages = [
            LLMEvaluatorSystemTurnTemplate(
                template_factory=self._system_template
            ).get_prompt(
                annotation.scenario,
                examples_module=self._examples_module,
            ),
            UserTurnTemplate(template_factory=self._user_template).get_prompt(
                {
                    "query": result.query,
                    "plan": remove_import_statements(result.solution),
                }
            ),
        ]
        return LLMPrompt(messages=messages)

    def _ask_llm_for_judgement(self, result: EvaluationResult) -> LLMJudgement:
        """Creates a prompt for the LLM evaluator and calls the LLM for evaluation.

        Returns
        -------
        LLMJudgement, an object containing the LLM correctness assessment and justification
        for it.
        """
        prompt = self._make_prompt(result)
        self._prompts[result.query_id] = prompt
        completion = self._completer.complete(prompt)
        try:
            parsed = self._parser(completion)
            judgement = LLMJudgement.from_string(parsed)
        except ProgramFinderError:
            judgement = LLMJudgement.failed_to_judge()
            judgement.assessment = completion
        if judgement.correct == NOT_EVALUATED:
            logger.warning(
                f"Could not evaluate query {result.query_id}: {result.query}"
            )
            logger.warning(f"Completion: {completion}")
        return judgement

    def _update_with_llm_judgement(self, result: EvaluationResult):
        """Updates a result with an LLM correctness judgement."""
        try:
            judgement = self._ask_llm_for_judgement(result)
        except CompletionApiError as e:
            assert "Invalid prompt" in str(e)
            logger.warning(
                f"Could not evaluate query {result.query_id} due to prompt violation error"
            )
            self._judge_failures_cnt += 1
            self._correct[result.query] = NOT_EVALUATED
            result.reference_free_correct = NOT_EVALUATED
            result.reference_free_correct_explanation = str(e)
            return
        match (is_correct := judgement.correct):
            case True | False:
                self._correct[result.query] = is_correct
                result.reference_free_correct = is_correct
                result.reference_free_correct_explanation = judgement.assessment
            case val if isinstance(val, str):
                self._correct[result.query] = NOT_EVALUATED
                logger.warning(f"Could not evaluate query {result.query}")
                self._judge_failures_cnt += 1
                result.reference_free_correct = NOT_EVALUATED
                assessment = (
                    judgement.assessment
                    if isinstance(judgement.assessment, str)
                    else NOT_EVALUATED
                )
                result.reference_free_correct_explanation = assessment

    @property
    def evaluator_agreement(self) -> tuple[F1Score, SkippedInstances]:
        """Calculate the F1 score of the LLM evaluator, taking the
        execution-based evaluation labels as ground truth."""
        true_positive, predicted_positive, actual_positive, skipped = 0, 0, 0, 0
        for r in self._results:
            if isinstance(r.reference_free_correct, str):
                skipped += 1
                logger.warning(
                    f"Judged failed to evaluate query {r.query_id}. "
                    "Skipping instance in judge eval score estimation"
                )
                continue
            execution = r.correct
            judge = r.reference_free_correct
            true_positive += int(execution & judge)
            predicted_positive += int(judge)
            actual_positive += int(execution)
        precision = positive_predictive_value = true_positive / predicted_positive
        recall = true_positive_rate = true_positive / actual_positive
        f1 = (2 * positive_predictive_value * true_positive_rate) / (
            positive_predictive_value + true_positive_rate
        )
        return F1Score(precision=precision, recall=recall, f1=f1), skipped

    def evaluate(self):
        """Updates the results with LLM correctness judgement."""
        for result in self._results:
            logger.info(f"Evaluating query: {result.query_id}")
            self._update_with_llm_judgement(result)

    def get_score(self) -> float:
        """Returns the score the agent achieved on the benchmark."""
        if not self._correct:
            return 0.0

        # Calculate the proportion of correct evaluations
        correct_count = sum(
            [int(v) for v in self._correct.values() if isinstance(v, bool)]
        )
        total_count = self.total_queries

        return (100 * correct_count) / total_count

    def get_judge_failure_rate(self) -> float:
        if not self._correct:
            return 0.0

        failed_count = len([v for v in self._correct.values() if v == NOT_EVALUATED])
        total_count = self.total_queries

        return (100 * failed_count) / total_count

    @cached_property
    def results_path(self) -> Path:
        return Path(self._out_dir) / "results.json"

    @cached_property
    def prompts_path(self) -> Path:
        pth = Path(self._out_dir) / "evaluator_prompts"
        if not pth.exists():
            pth.mkdir(parents=True, exist_ok=True)
        return pth

    def write_results(self):
        """Write the llm assessment to a results file."""
        with open(self.results_path, "w") as f_out_results:
            for i in range(0, len(self._results)):
                result = self._results[i]
                f_out_results.write(f"{result.model_dump_json()}\n")
        for query_id, prompt in self._prompts.items():
            with open(self.prompts_path / f"query_{query_id}.txt", "w") as f_out_prompt:
                for message in prompt.messages:
                    f_out_prompt.write(message["content"])
