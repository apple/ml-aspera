#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from importlib import resources
from pathlib import Path

import hydra
from hydra.utils import instantiate
from omegaconf import DictConfig, OmegaConf

from aspera.llm_evaluator import LLMEvaluator
from aspera.readers import load_json
from aspera.utils import get_commit_hash
from aspera.writers import save_json

logger = logging.getLogger(__name__)


def get_config_path() -> str:
    return str(resources.files("aspera.configs.llm_evaluator") / ".")


@hydra.main(config_name="guidelines_first", config_path=get_config_path())
def evaluate(cfg: DictConfig):
    logger.info(f"The hash of the branch the agent runs on: {get_commit_hash()}")
    if cfg.debug:
        logger.info(OmegaConf.to_yaml(cfg, resolve=True))
    evaluator: LLMEvaluator = instantiate(cfg.evaluator)
    logger.info(f"Evaluator: {evaluator.name}")
    logger.info(f"Predictions file: {cfg.results_file}")
    evaluator.evaluate()
    evaluator.write_results()
    f1_score, skipped_instances = evaluator.evaluator_agreement
    save_json(
        {
            "score": evaluator.get_score(),
            "judge_failure_rate": evaluator.get_judge_failure_rate(),
            "judge_f1_score": f1_score.f1,
            "judge_precision": f1_score.precision,
            "judge_recall": f1_score.recall,
            "skipped_instances": skipped_instances,
        },
        Path(cfg.output_dir) / "metrics.json",
    )
    logger.info(
        f"Agent at {cfg.results_file} scored {evaluator.get_score():.2f}% according "
        f"to {evaluator.name} assessment."
    )
    logger.info(
        f"{evaluator.name} evaluator precision: {100 * f1_score.precision:.2f}%."
    )
    logger.info(f"{evaluator.name} evaluator recall: {100 * f1_score.recall:.2f}%.")
    logger.info(
        f"Judge failure rate: {evaluator.get_judge_failure_rate():.2f}% "
        f"({skipped_instances} out of {evaluator.total_queries} not evaluated)"
    )
    try:
        execution_metrics = load_json(Path(cfg.results_file).parent / "metrics.json")
        logger.info(
            f"The same agent was evaluated at {execution_metrics['score']:.2f}% by execution"
        )
    except FileNotFoundError:
        pass
    logger.info(f"Results written to {evaluator.results_path}")
