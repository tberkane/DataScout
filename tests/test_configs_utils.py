from __future__ import annotations

import threading
import time

import pytest

from datascout import BrightDataConfig, JinaConfig, LLMConfig, MistralOCRConfig
from datascout.utils import (
    completion_text,
    normalize_variable_name,
    perform_completion,
    strip_code_fences,
    timeout_function,
)


def test_configs_keep_keys_out_of_repr() -> None:
    configs = [
        LLMConfig(api_key="sk-secret"),
        BrightDataConfig("bd-secret", "zone1"),
        MistralOCRConfig("mi-secret"),
        JinaConfig("jina-secret"),
    ]
    for config in configs:
        assert "secret" not in repr(config)
    assert BrightDataConfig("k", "z").base_url == "https://api.brightdata.com/request"
    assert LLMConfig().model == "openai/gpt-4.1"


def test_perform_completion_passes_settings(fake_llm) -> None:
    fake_llm.replies = ["hi"]
    perform_completion("hello", LLMConfig(model="m", api_key="k", temperature=0.5))
    assert fake_llm.calls == [
        {"model": "m", "api_key": "k", "temperature": 0.5, "messages": [{"role": "user", "content": "hello"}]}
    ]


def test_completion_text_rejects_empty(fake_llm) -> None:
    fake_llm.replies = [None]
    with pytest.raises(ValueError, match="empty response"):
        completion_text("x", LLMConfig())


@pytest.mark.parametrize(
    ("raw", "clean"),
    [('```json\n["a"]\n```', '["a"]'), ("```python\nclass A: ...\n```", "class A: ..."), (" plain ", "plain")],
)
def test_strip_code_fences(raw: str, clean: str) -> None:
    assert strip_code_fences(raw) == clean


def test_normalize_variable_name() -> None:
    assert normalize_variable_name("State And App") == "state_and_app"


def test_timeout_function_returns_result() -> None:
    assert timeout_function(lambda a, b=0: a + b, args=(1,), kwargs={"b": 2}) == 3


def test_timeout_function_times_out() -> None:
    started = time.monotonic()
    assert timeout_function(time.sleep, args=(2,), timeout=0.05, default_value="late") == "late"
    assert time.monotonic() - started < 1


def test_timeout_function_reraises() -> None:
    def boom() -> None:
        raise KeyError("x")

    with pytest.raises(KeyError):
        timeout_function(boom)


def test_timeout_function_works_off_the_main_thread() -> None:
    results: list[object] = []
    worker = threading.Thread(target=lambda: results.append(timeout_function(lambda: "ok")))
    worker.start()
    worker.join()
    assert results == ["ok"]
