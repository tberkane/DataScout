"""Fakes for every external service, so the tests need no API keys and no network."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

import datascout.data_extraction as data_extraction
import datascout.utils as utils
import datascout.webpage_retrieval as webpage_retrieval


def completion_response(content: str | None) -> SimpleNamespace:
    """A litellm-shaped response with one choice."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeLLM:
    """Replaces ``litellm.completion``; returns queued replies and records the calls."""

    def __init__(self) -> None:
        self.replies: list[str | None] = []
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return completion_response(self.replies.pop(0))

    @property
    def last_prompt(self) -> str:
        return str(self.calls[-1]["messages"][0]["content"])


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    llm = FakeLLM()
    monkeypatch.setattr(utils, "completion", llm)
    return llm


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status}")

    def json(self) -> Any:
        return self.payload


class FakeHTTP:
    """Replaces ``requests.post``; ``handler(url, json_body)`` returns the JSON payload."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.handler: Callable[[str, dict[str, Any]], Any] = lambda url, body: {}
        self.status = 200

    def __call__(self, url: str, headers: dict[str, str], json: dict[str, Any], timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(self.handler(url, json), self.status)


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> FakeHTTP:
    http = FakeHTTP()
    monkeypatch.setattr(webpage_retrieval.requests, "post", http)
    return http


class FakeCrawler:
    """Replaces ``crawl4ai.AsyncWebCrawler``. ``pages`` maps the crawled target to (extracted items, markdown)."""

    pages: dict[str, tuple[Any, str]] = {}
    crawled: list[str] = []
    browser_configs: list[Any] = []

    def __init__(self, config: Any) -> None:
        FakeCrawler.browser_configs.append(config)

    async def __aenter__(self) -> FakeCrawler:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def arun(self, url: str, config: Any) -> SimpleNamespace | None:
        FakeCrawler.crawled.append(url)
        if url not in self.pages:
            return None
        extracted, markdown = self.pages[url]
        content = extracted if isinstance(extracted, str) or extracted is None else json.dumps(extracted)
        return SimpleNamespace(extracted_content=content, markdown=markdown)


@pytest.fixture
def fake_crawler(monkeypatch: pytest.MonkeyPatch) -> type[FakeCrawler]:
    FakeCrawler.pages = {}
    FakeCrawler.crawled = []
    FakeCrawler.browser_configs = []
    monkeypatch.setattr(data_extraction, "AsyncWebCrawler", FakeCrawler)
    return FakeCrawler


class FakeMistral:
    """Replaces ``mistralai.Mistral``; OCR returns two pages of fixed Markdown."""

    calls: list[dict[str, Any]] = []

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.ocr = self

    def process(self, **kwargs: Any) -> SimpleNamespace:
        FakeMistral.calls.append(kwargs)
        return SimpleNamespace(pages=[SimpleNamespace(markdown="Page one."), SimpleNamespace(markdown="Page two.")])


@pytest.fixture
def fake_mistral(monkeypatch: pytest.MonkeyPatch) -> type[FakeMistral]:
    FakeMistral.calls = []
    monkeypatch.setattr(data_extraction, "Mistral", FakeMistral)
    return FakeMistral
