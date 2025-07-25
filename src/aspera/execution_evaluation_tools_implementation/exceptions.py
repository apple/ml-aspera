#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
class SolutionError(Exception):
    """Should always be raised inside `evaluate_*` functions whenever an assertion fails."""
