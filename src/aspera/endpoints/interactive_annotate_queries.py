#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from importlib import resources

import hydra
from omegaconf import DictConfig, OmegaConf

from aspera.interactive.annotation_session import (
    QueryAnnotationSession,
    load_queries,
    next_step_message,
)
from aspera.interactive.utils import SessionEndException
from aspera.utils import generate_batches, get_commit_hash

logger = logging.getLogger(__name__)


def validate_batch_size(batch_size: int, generate_state_setup_code: bool):
    if generate_state_setup_code:
        assert batch_size == 1, (
            f"Batch size must be 1 when entities are generated in follow-up interaction. "
            f"Got {batch_size}"
        )


def main(config: DictConfig):
    validate_batch_size(
        config.batch_size, config.annotation.generate_environment_state_setup_code
    )
    session = QueryAnnotationSession(config)

    to_process = load_queries(session)
    for q_batch in generate_batches(to_process, config.batch_size):
        session.annotate_batch(q_batch)
        try:
            next_step_message()
        except SessionEndException:
            logger.info("Terminating session.")
            return
    # possibly annotate any queries for which the programs could not be parsed
    #  (eg because we ran out of output tokens before completing a program)
    outstanding_queries = session.retry_queries
    for q_batch in generate_batches(outstanding_queries, config.batch_size):
        session.annotate_batch(q_batch)
        try:
            next_step_message()
        except SessionEndException:
            logger.info("Terminating session.")
            return


@hydra.main(
    config_name="org_events",
    config_path="pkg://aspera.configs.query_label",
)
def annotate_queries(config: DictConfig):
    logger.info(f"Annotating complex queries {get_commit_hash()}")
    if config.annotation.debug:
        logger.info(OmegaConf.to_yaml(config, resolve=True))
    main(config)
