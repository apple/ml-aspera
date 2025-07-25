#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from pathlib import Path

SRC_ROOT = "src"
PACKAGE_NAME = "aspera"
EXAMPLES_ROOT = f"{PACKAGE_NAME}.examples"
ExamplesModuleName = str
"""A .py file located under EXAMPLES_ROOT containing in-context examples for evaluation."""
IMPLEMENTATIONS_ROOT = "apps_implementation"
DOCS_ROOT = "apps"
APP_DOCS_ROOT = f"{PACKAGE_NAME}.{DOCS_ROOT}"
SIMULATION_TOOLS_IMPLEMENTATIONS_PATH = (
    f"{PACKAGE_NAME}.runtime_state_generation_tools_implementation"
)
SIMULATION_TOOLS_PATH = f"{PACKAGE_NAME}.runtime_state_generation_tools"
EVALUATION_TOOLS_IMPLEMENTATIONS_PATH = (
    f"{PACKAGE_NAME}.execution_evaluation_tools_implementation"
)
EVALUATION_TOOLS_PATH = f"{PACKAGE_NAME}.execution_evaluation_tools"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "aspera"
SHARD_SIZE = 32
QUERY_FILE_EXTENSION = "nt"
SESSION_LOG_NAME = "interaction"
CORRECTIONS_MODULE_NAME = "queries.py"
QUERY_ID_TO_SHARD_JSON = "query_id_to_shard.json"
QUERY_TO_QUERY_ID_JSON = "query_to_query_id.json"
STAGING_MODULE_NAME = "queries.py"
STAGING_MODULE_BACKUP = "queries_backup.py"
STAGING_STATE_MODULE_BACKUP = "queries_states_backup.py"
STAGING_EVAL_MODULE_BACKUP = "queries_eval_backup.py"
SESSION_LOG_EXTENSION = "json"
FEEDBACK_KEY = "feedback"
RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX = "setup_env"
PROGRAM_LINE_LENGTH = 80
EVALUATION_PROGRAM_FUNCTION_NAME_PREFIX = "evaluate"
