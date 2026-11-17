"""Stage 4: flag extracted data points that look wrong or inconsistent with the rest of the dataset."""

from __future__ import annotations

import io
import re
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .configs import LLMConfig
from .prompts import QUALITY_CONTROL_PROMPT
from .utils import completion_text

__all__ = ["control_quality"]

# "3: text", "ID 3: text", "{3}: text", "- 3: text", "**3**: text"
_ISSUE_LINE = re.compile(r"^\W*(?:id\W*)?(\d+)\W*:\s*(.*)$", re.IGNORECASE)


def control_quality(
    extracted_data: Sequence[Mapping[str, Any]],
    dataset_description: str,
    llm_config: LLMConfig,
) -> dict[str, str]:
    """Have the LLM review the whole dataset and describe potential problems with each row.

    The rows are sent as CSV, without their ``url`` column. Rows are identified by their ``id`` field
    if they have one, otherwise by their 1-based position.

    Args:
        extracted_data: Data points, e.g. from `datascout.extract_data`.
        dataset_description: The description the data was collected for.
        llm_config: LLM settings.

    Returns:
        A mapping from row ID (as a string) to the LLM's comment. The comment is ``"NA"`` when the LLM
        found no issue. Lines of the response that don't start with a row ID are ignored.
    """
    if not extracted_data:
        return {}

    df = pd.DataFrame(list(extracted_data))
    if "url" in df.columns:
        df = df.drop(columns="url")
    if "id" in df.columns:
        df = df.set_index("id")
    else:
        df.index = df.index + 1
        df.index.name = "id"

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=True)

    prompt = QUALITY_CONTROL_PROMPT.format(
        dataset_description=dataset_description, extracted_data=csv_buffer.getvalue()
    )
    content = completion_text(prompt, llm_config)

    issues: dict[str, str] = {}
    for line in content.strip().splitlines():
        match = _ISSUE_LINE.match(line.strip())
        if match:
            issues[match.group(1)] = match.group(2).strip()
    return issues
