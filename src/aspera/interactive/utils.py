#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from datetime import datetime
from pathlib import Path

from aspera.completer.utils import MessageList
from aspera.constants import SESSION_LOG_NAME
from aspera.interactive.annotation_manager import relative_to_root
from aspera.readers import load_json
from aspera.utils import get_commit_hash
from aspera.writers import save_json

logger = logging.getLogger(__name__)


def save_progress(
    chat_history: MessageList,
    last_user_turn: str,
    completion: str,
    queries: list[str],
    budget: dict[str, str | int],
    odir: Path,
    *,
    session_id: int,
    overwrite_last: bool = False,
    overwrite_fields: list[str] = None,
    log_name: str = SESSION_LOG_NAME,
    unparsed_queries: list[str] | None = None,
):
    """Save the raw completer outputs and the number of tokens spent in the current session.

    Parameters
    ----------
    chat_history
        Chat history that can be used for resuming annotation session. This history only
        stores the initial system turn and (user_annotation_request, assistant, user_feedback)
        triples which are logged if the user passes feedback to the model.
    last_user_turn
        The last turn the agent was prompted with.
    completion
        The last agent response.
    queries
        All the queries the agent has been asked to label so far.
    budget
        Information regarding how many tokens were spend in the current session.
    unparsed_queries
        Queries that the agent was prompted with for labelling but for which the solution
        could not be parsed due to a parser error (e.g. completion truncated due too length).
        Only passed for if the session is run in annotation mode (ie plans, states and
        evaluation code are generated given a human- or machine-authored query)
    session_id
        A log file is create for each session. The session id of the last session is used for
        restoring the state of the session.
    odir
        Output directory, a subdirectory of session_logs in repository root.
    overwrite_last
        The log file contains one entry per interaction step, where an interaction step involves
        a round of interaction with the agent. This flag overrides the last entry in the log file
        as opposed to creating a new one. If `override_fields` is provided, then only those
        fields will be overwritten.
    overwrite_fields
        Which data of the last logged session should be overwritten.
    log_name
        The name of the log to be created, suffixed with `session_id`.
    """

    progress = {
        "chat_history": chat_history,
        "last_user_turn": last_user_turn,
        "completion": completion,
        "queries": queries,
        "unparsed_queries": unparsed_queries or [],
        "budget": budget,
        "commit_hash": get_commit_hash(),
        "timestamp": datetime.utcnow().isoformat(),
    }
    opath = odir / f"{log_name}_{session_id}.json"
    if opath.exists():
        current_progress = load_json(opath)
        if overwrite_last:
            fields = overwrite_fields or []
            for f in fields:
                match f:
                    case "budget":
                        spent_tokens = (
                            sum(v for v in budget.values() if isinstance(v, int)) > 0
                        )
                        if spent_tokens:
                            current_progress[-1][f] = budget
                    case _:
                        current_progress[-1][f] = progress[f]

        else:
            current_progress.append(progress)
    else:
        current_progress = [progress]
    logger.info(f"Saving progress to {relative_to_root(opath)}")
    save_json(current_progress, opath)


class SessionEndException(Exception):
    pass
