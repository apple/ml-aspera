#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.dataset_schema import EditedDataPoint


class EditFeedbackFormatter:

    def __call__(self, example: EditedDataPoint, *args, **kwargs) -> str:

        query = f"Query: {example['query']}"
        feedback = f"Developer feedback: {example['feedback']}"
        edited = f"Edited program: \n {example['edited_program']}"
        return f"{query}\n\n{feedback}\n\n{edited}"
