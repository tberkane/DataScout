"""Stage 1: generate search queries (or query templates) from a dataset description."""

from __future__ import annotations

import json

from .configs import LLMConfig
from .prompts import GENERATE_QUERIES_PROMPT, GENERATE_QUERIES_WITH_VARIABLES_PROMPT
from .utils import completion_text, normalize_variable_name, strip_code_fences

__all__ = ["generate_search_queries"]

MAX_QUERIES = 10


def generate_search_queries(
    dataset_description: str,
    num_queries: int,
    llm_config: LLMConfig,
    variable_names: list[str] | None = None,
) -> list[str]:
    """Ask the LLM for Google search queries that find data points matching ``dataset_description``.

    With ``variable_names``, the LLM returns *templates* instead, such as
    ``"{state} COVID app download count"``. `datascout.retrieve_webpages` fills them with every
    combination of variable values. Variable names are normalized (lowercase, spaces replaced by
    underscores) the same way there.

    Args:
        dataset_description: Plain-language description of the data to collect.
        num_queries: Number of queries to generate, from 1 to 10.
        llm_config: LLM settings.
        variable_names: Names of the placeholder variables each template must contain.

    Returns:
        The generated queries or templates.

    Raises:
        ValueError: If ``num_queries`` is out of range or the LLM output is not a JSON list of strings.
    """
    if not 1 <= num_queries <= MAX_QUERIES:
        raise ValueError(f"num_queries must be between 1 and {MAX_QUERIES}, got {num_queries}")

    if variable_names:
        prompt = GENERATE_QUERIES_WITH_VARIABLES_PROMPT.format(
            variable_names=[normalize_variable_name(n) for n in variable_names],
            num_queries=num_queries,
            dataset_description=dataset_description,
        )
    else:
        prompt = GENERATE_QUERIES_PROMPT.format(num_queries=num_queries, dataset_description=dataset_description)

    content = strip_code_fences(completion_text(prompt, llm_config))
    try:
        queries = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Expected a JSON list of queries from the LLM, got: {content[:200]!r}") from exc
    if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
        raise ValueError(f"Expected a JSON list of strings from the LLM, got: {content[:200]!r}")
    return queries
