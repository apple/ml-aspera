#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import json
import logging
import random
from pathlib import Path

import hydra
from hydra.utils import instantiate
from omegaconf import DictConfig, OmegaConf

from aspera.agent.base_agent import BaseAgent
from aspera.completer.utils import CompletionError
from aspera.utils import get_commit_hash

logger = logging.getLogger(__name__)


@hydra.main(
    config_name="complete_codebase_knowledge",
    config_path="pkg://aspera.configs.agent",
)
def run_agent(cfg: DictConfig):
    # environment state is randomised
    random.seed(0)
    logger.info(f"The hash of the branch the agent runs on: {get_commit_hash()}")
    output_dir = Path(cfg.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(config=cfg, f=output_dir / "config.yaml")

    if cfg.debug:
        logger.info(OmegaConf.to_yaml(cfg, resolve=True))
    agent: BaseAgent = instantiate(cfg.agent)
    results = []
    total_queries, prompt_violation = 0, 0
    assert isinstance(cfg.start, int), isinstance(cfg.end, int)
    for i, user_query in enumerate(agent.task_iterator()):
        if int(user_query.query_id) not in range(cfg.start, cfg.end + 1):
            continue
        total_queries += 1
        logger.info(f"Solving query {user_query.query_id}")
        try:
            solution = agent.plan(user_query)
        except CompletionError as e:
            assert "Invalid prompt" in str(e) or "do not have" in str(e)
            prompt_violation += 1
            logger.warning(f"Prompt violation for query {user_query.query_id}")
            continue
        result = agent.submit_solution(user_query, solution)
        this_query_annotation = agent.evaluator.load_annotation(user_query.query)
        result.state_generation_programs = (
            this_query_annotation.state_generation_programs
        )
        result.evaluation_programs = this_query_annotation.evaluation_programs
        results.append(result)
        result.make_executable_script(
            this_query_annotation.scenario,
            cfg.gold_sources_dir,
            cfg.executable_output_dir,
        )

    results_path = output_dir / "results.jsonl"
    with open(results_path, "w") as f_out_results:
        for i in range(0, len(results)):
            result = results[i]
            f_out_results.write(f"{result.model_dump_json()}\n")
            if cfg.prompts_output_dir:
                with open(
                    Path(cfg.prompts_output_dir) / f"query_{result.query_id}.txt", "w"
                ) as f_out_prompts:
                    for message in result.prompt.messages:
                        f_out_prompts.write(message["content"])
            if cfg.completion_output_dir:
                with open(
                    Path(cfg.completion_output_dir) / f"query_{result.query_id}.txt",
                    "w",
                ) as f_out_completion:
                    f_out_completion.write(result.raw_completion)

    metrics_path = output_dir / "metrics.json"
    score = agent.score
    score -= prompt_violation / total_queries
    macro_f1 = agent.evaluator.get_primitives_selection_macro_f1()
    micro_f1 = agent.evaluator.get_primitives_selection_micro_f1()
    with open(metrics_path, "w") as f_out_metrics:
        json.dump(
            {
                "score": score,
                "primitives_selection_macro_f1": macro_f1,
                "primitives_selection_micro_f1": micro_f1,
                "parser_failure_rate": agent.parser_failure_rate,
                "solution_error_rate": agent.solution_err_rate,
                "handback_control_error_rate": agent.control_handover_err_rate,
                "handback_control_error_rate_normalise": agent.control_handover_err_rate_normalised,
                "execution_error_count": agent.execution_error_rate,
                "bad_import_error_rate": agent.bad_import_error_rate,
                "bad_import_queries": agent.bad_import_queries,
                "import_lenient_score": agent.import_lenient_score,
            },
            f_out_metrics,
        )
    if prompt_violation > 0:
        logger.info(f"A prediction could not be made for {prompt_violation} queries")
    if agent.parser_failure_rate > 0.0:
        logger.warning(f"Parser failure rate: {agent.parser_failure_rate:.2f}%")
    logger.info(f"{agent.name} scored {score:.2f}%.")
    logger.info(
        f"Of all {agent.name} errors {agent.solution_err_rate:.2f}% were task completion failures."
    )
    logger.info(
        f"In {agent.control_handover_err_rate:.2f}% of task completion failures, {agent.name} "
        "hands back control to the user when this is not expected"
    )
    logger.info(f"Import-lenient score: {agent.import_lenient_score:.2f}%.")
    if macro_f1 and micro_f1:
        logger.info(f"tool retrieval macro F1 score: {macro_f1:.2f}.")
        logger.info(f"tool retrieval micro F1 score: {micro_f1:.2f}.")
    logger.info(f"Results written to {results_path}")
