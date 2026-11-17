from __future__ import annotations

import pytest

from datascout import LLMConfig, generate_search_queries


def test_plain_queries(fake_llm) -> None:
    fake_llm.replies = ['```json\n["cholera cases Yemen", "cholera outbreak report"]\n```']
    queries = generate_search_queries("Cholera case counts", 2, LLMConfig())
    assert queries == ["cholera cases Yemen", "cholera outbreak report"]
    assert "Generate 2 Google Search queries" in fake_llm.last_prompt
    assert "Cholera case counts" in fake_llm.last_prompt


def test_templates_use_normalized_variable_names(fake_llm) -> None:
    fake_llm.replies = ['["{state_and_app_name} downloads"]']
    queries = generate_search_queries("App downloads", 1, LLMConfig(), ["State and App Name"])
    assert queries == ["{state_and_app_name} downloads"]
    assert "['state_and_app_name']" in fake_llm.last_prompt


@pytest.mark.parametrize("n", [0, 11])
def test_num_queries_range(n: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 10"):
        generate_search_queries("x", n, LLMConfig())


@pytest.mark.parametrize("reply", ["not json", '{"q": "a"}', "[1, 2]"])
def test_bad_llm_output(fake_llm, reply: str) -> None:
    fake_llm.replies = [reply]
    with pytest.raises(ValueError, match="JSON list"):
        generate_search_queries("x", 1, LLMConfig())
