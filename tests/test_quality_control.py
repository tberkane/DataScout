from __future__ import annotations

from datascout import LLMConfig, control_quality


def test_parses_issue_lines(fake_llm) -> None:
    fake_llm.replies = [
        "1: NA\nID 2: The count is lower than the previous report.\n**3**: Date is in the future.\nSummary: done"
    ]
    rows = [{"state": "AL", "count": 10, "url": "u"}, {"state": "AL", "count": 5}, {"state": "AZ", "count": 7}]
    issues = control_quality(rows, "App downloads", LLMConfig())
    assert issues == {"1": "NA", "2": "The count is lower than the previous report.", "3": "Date is in the future."}

    prompt = fake_llm.last_prompt
    assert "id,state,count\n1,AL,10\n2,AL,5\n3,AZ,7" in prompt
    assert "url" not in prompt.split("App downloads", 1)[1]


def test_uses_id_column_when_present(fake_llm) -> None:
    fake_llm.replies = ["7: NA"]
    assert control_quality([{"id": 7, "value": 1}], "d", LLMConfig()) == {"7": "NA"}
    assert "id,value\n7,1" in fake_llm.last_prompt


def test_empty_input_makes_no_call(fake_llm) -> None:
    assert control_quality([], "d", LLMConfig()) == {}
    assert fake_llm.calls == []
