#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from importlib import resources

import hydra
from omegaconf import DictConfig

from aspera.interactive.generation_session import (
    QueryGenerationSession,
    maybe_change_focus,
    next_step_message,
)
from aspera.interactive.utils import SessionEndException
from aspera.readers import count_shards
from aspera.utils import get_commit_hash

logger = logging.getLogger(__name__)


def main(config: DictConfig):
    session_id = count_shards(config.output_dir)
    logger.info(f"Session ID: {session_id}")
    session = QueryGenerationSession(config)
    while True:
        session.generate_queries()
        try:
            next_step_message()
            maybe_change_focus(session)
        except SessionEndException:
            logger.info("Terminating session.")
            return


@hydra.main(
    config_name="org_events",
    config_path="pkg://aspera.configs.query_gen",
)
def generate_complex_queries(config: DictConfig):
    logger.info(f"Generating complex queries from hash: {get_commit_hash()}")
    main(config)
