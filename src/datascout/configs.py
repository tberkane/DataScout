"""Configuration objects for the external services DataScout calls.

API keys are excluded from each config's ``repr`` so they don't end up in logs or notebook outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["BrightDataConfig", "JinaConfig", "LLMConfig", "MistralOCRConfig"]


@dataclass
class LLMConfig:
    """Settings for the LLM, called through [litellm](https://docs.litellm.ai/).

    Attributes:
        model: A litellm model string, e.g. ``"openai/gpt-4.1"`` or ``"mistral/mistral-large-latest"``.
        api_key: API key for the provider. If ``None``, litellm reads the provider's usual environment
            variable (e.g. ``OPENAI_API_KEY``).
        temperature: Sampling temperature for query generation, schema generation and quality control.
            Extraction uses the provider's default temperature.
    """

    model: str = "openai/gpt-4.1"
    api_key: str | None = field(default=None, repr=False)
    temperature: float | None = 0.2


@dataclass
class BrightDataConfig:
    """Settings for the [Bright Data](https://brightdata.com/) SERP API, used to run Google searches.

    Attributes:
        api_key: Bright Data API key.
        zone: Name of the Bright Data SERP zone.
        base_url: Endpoint of the Bright Data request API.
    """

    api_key: str = field(repr=False)
    zone: str
    base_url: str = "https://api.brightdata.com/request"


@dataclass
class MistralOCRConfig:
    """Settings for the Mistral OCR API, used to read PDFs.

    Attributes:
        api_key: Mistral API key.
        model: Mistral OCR model name.
    """

    api_key: str = field(repr=False)
    model: str = "mistral-ocr-latest"


@dataclass
class JinaConfig:
    """Settings for the [Jina Reranker](https://jina.ai/reranker/) API.

    Attributes:
        api_key: Jina API key.
        model: Reranker model name.
        base_url: Endpoint of the rerank API.
    """

    api_key: str = field(repr=False)
    model: str = "jina-reranker-v2-base-multilingual"
    base_url: str = "https://api.jina.ai/v1/rerank"
