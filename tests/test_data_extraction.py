from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from datascout import (
    LLMConfig,
    MistralOCRConfig,
    SchemaError,
    extract_data,
    extract_data_streaming,
    generate_extraction_schema,
    is_grounded,
    parse_extraction_schema,
)
from datascout.data_extraction import _datapoints_from_result, _is_pdf_url, _remove_markdown_links

SCHEMA = '''class CholeraCases(BaseModel):
    """Weekly cholera reports."""
    country: str = Field(..., description="Country of the report")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    cholera_cases: int = Field(..., description="Number of reported cases")
'''


# --- schema parsing ------------------------------------------------------------------------------


def test_parse_schema_builds_model() -> None:
    model = parse_extraction_schema(SCHEMA)
    assert model.__name__ == "CholeraCases"
    assert list(model.model_fields) == ["country", "date", "cholera_cases"]
    assert model.model_fields["cholera_cases"].description == "Number of reported cases"
    parsed = model.model_validate({"country": "Yemen", "date": "2017-05-01", "cholera_cases": "12"})
    assert parsed.model_dump()["cholera_cases"] == 12
    with pytest.raises(ValidationError):
        model.model_validate({"country": "Yemen", "date": "2017-05-01"})


def test_parse_schema_accepts_common_llm_variants() -> None:
    schema = """```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Report(BaseModel):
  region: Optional[str] = Field(None, description="Region")
  tags: List[str] = Field(default=[], description="Tags")
  rate: float | None = Field(..., title="Rate")
  confirmed: bool
```"""
    model = parse_extraction_schema(schema)
    assert list(model.model_fields) == ["region", "tags", "rate", "confirmed"]
    assert model.model_validate({"rate": None, "confirmed": True}).model_dump()["region"] is None


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ("import os\nos.system('echo pwned')", "exactly one class"),
        ("class A(BaseModel):\n    x: str\nclass B(BaseModel):\n    y: str", "exactly one class"),
        ("class A(Exploit):\n    x: str", "inherit from BaseModel"),
        ("class A(BaseModel):\n    x: dict = Field(...)", "Unsupported field type"),
        ("class A(BaseModel):\n    x: Dict[str, int] = Field(...)", "Unsupported field type"),
        ("class A(BaseModel):\n    x: str | int = Field(...)", "Unsupported field type"),
        ("class A(BaseModel):\n    x: str = __import__('os')", "must be assigned Field"),
        ('class A(BaseModel):\n    x: str = Field(..., alias="y")', "only a default"),
        ("class A(BaseModel):\n    x: str = Field(description=open('f').read())", "literals"),
        ("class A(BaseModel):\n    def f(self): pass", "Unsupported statement"),
        ("class A(BaseModel):\n    grounding_quote: str", "reserved"),
        ("class A(BaseModel):\n    'only a docstring'", "no fields"),
        ("class A(BaseModel:\n", "not valid Python"),
    ],
)
def test_parse_schema_rejects(schema: str, message: str) -> None:
    with pytest.raises(SchemaError, match=message):
        parse_extraction_schema(schema)


def test_generate_extraction_schema(fake_llm) -> None:
    fake_llm.replies = ["```python\n" + SCHEMA + "```"]
    schema = generate_extraction_schema("Cholera case counts", ["country", "date"], LLMConfig())
    assert schema == SCHEMA.strip()
    assert "['country', 'date']" in fake_llm.last_prompt


# --- grounding -----------------------------------------------------------------------------------

words = st.lists(
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=8), min_size=1, max_size=30
)


@given(words=words, data=st.data())
def test_any_verbatim_span_is_grounded(words: list[str], data: st.DataObject) -> None:
    i = data.draw(st.integers(0, len(words) - 1))
    j = data.draw(st.integers(i + 1, len(words)))
    page = "# Title\n\n" + " ".join(f"[{w}](https://x.org/{w})" if k % 3 == 0 else w for k, w in enumerate(words))
    quote = " , ".join(words[i:j])  # different spacing and punctuation
    assert is_grounded(quote, page)


def test_grounding_rejects_missing_or_empty_quotes() -> None:
    page = "Officials reported 1,800 downloads on Monday."
    assert is_grounded("reported 1800 downloads", page)
    assert not is_grounded("reported 18000 downloads", page)
    assert not is_grounded("", page)
    assert not is_grounded(None, page)
    assert not is_grounded("!!!", page)
    assert not is_grounded("REPORTED 1800", page)  # case-sensitive


def test_remove_markdown_links() -> None:
    text = "See [the report](https://a.org) and ![chart](c.png) [][x] []( https://e.org) [ref][1]\n[1]: https://b.org"
    assert _remove_markdown_links(text) == "See the report and  [][x]  ref\n"


@pytest.mark.parametrize(
    ("url", "is_pdf"),
    [
        ("https://a.org/report.pdf", True),
        ("https://a.org/report.PDF?dl=1", True),
        ("https://a.org/get?file=report.pdf&x=1", True),
        ("https://pdfs.example.org/page", False),
        ("https://a.org/report.pdfx", False),
    ],
)
def test_is_pdf_url(url: str, is_pdf: bool) -> None:
    assert _is_pdf_url(url) is is_pdf


def test_datapoints_from_result() -> None:
    page = "Alabama reported 1,800 downloads."
    items = [
        {"state": "AL", "grounding_quote": "reported 1,800 downloads", "error": False},
        {"state": "AZ", "grounding_quote": "made up", "error": False},
        {"error": True, "content": "rate limited"},
        "not a dict",
        {"state": "CA", "grounding_quote": "Alabama reported"},
    ]
    import json

    out = _datapoints_from_result("https://a.org/x", json.dumps(items), page)
    assert out == [
        {
            "state": "AL",
            "grounding_quote": "reported 1,800 downloads",
            "is_grounded": True,
            "source": "https://a.org/x#:~:text=reported%201%2C800%20downloads",
        },
        {"state": "AZ", "grounding_quote": "made up", "is_grounded": False, "source": "https://a.org/x"},
        {
            "state": "CA",
            "grounding_quote": "Alabama reported",
            "is_grounded": True,
            "source": "https://a.org/x#:~:text=Alabama%20reported",
        },
    ]
    assert _datapoints_from_result("u", '{"state": "AL"}', None)[0]["is_grounded"] is False
    assert _datapoints_from_result("u", "not json", page) == []
    assert _datapoints_from_result("u", '"a string"', page) == []
    assert _datapoints_from_result("u", None, page) == []


# --- extraction with a fake crawler ---------------------------------------------------------------


async def test_extract_data(fake_crawler, fake_mistral) -> None:
    fake_crawler.pages = {
        "https://a.org/1": (
            [{"country": "Yemen", "grounding_quote": "Yemen 12 cases", "error": False}],
            "Yemen: 12 cases",
        ),
        "https://a.org/2": ("garbage", ""),
        "raw:Page one.\nPage two.": (
            [{"country": "Chad", "grounding_quote": "Page two", "error": False}],
            "Page one.\nPage two.",
        ),
    }
    urls = ["https://a.org/1", "https://a.org/2", "https://a.org/missing", "https://a.org/r.pdf"]

    skipped = await extract_data(urls, SCHEMA, LLMConfig(api_key="k"))
    assert [d["country"] for d in skipped] == ["Yemen"]
    assert "https://a.org/r.pdf" not in fake_crawler.crawled
    assert fake_crawler.browser_configs[0].verbose is False

    with_pdfs = await extract_data(
        urls, SCHEMA, LLMConfig(), handle_pdfs=True, mistral_ocr_config=MistralOCRConfig("m"), verbose=True
    )
    assert [(d["country"], d["is_grounded"]) for d in with_pdfs] == [("Yemen", True), ("Chad", True)]
    assert with_pdfs[1]["source"] == "https://a.org/r.pdf#:~:text=Page%20two"
    assert fake_mistral.calls[0]["document"] == {"type": "document_url", "document_url": "https://a.org/r.pdf"}
    assert fake_crawler.browser_configs[-1].verbose is True


async def test_extract_data_streaming_marks_each_url(fake_crawler) -> None:
    fake_crawler.pages = {"https://a.org/1": ([{"country": "Yemen", "grounding_quote": "x"}], "")}
    items = [i async for i in extract_data_streaming(["https://a.org/1", "https://a.org/r.pdf"], SCHEMA, LLMConfig())]
    assert items == [
        {"country": "Yemen", "grounding_quote": "x", "is_grounded": False, "source": "https://a.org/1"},
        {"url_done": "https://a.org/1"},
        {"url_done": "https://a.org/r.pdf"},
    ]


async def test_extraction_config_sent_to_crawl4ai(fake_crawler, monkeypatch: pytest.MonkeyPatch) -> None:
    import datascout.data_extraction as de

    seen = {}
    original = de._run_config

    def spy(model, llm_config, extra_instruction):  # type: ignore[no-untyped-def]
        seen["model"] = model
        config = original(model, llm_config, extra_instruction)
        seen["strategy"] = config.extraction_strategy
        return config

    monkeypatch.setattr(de, "_run_config", spy)
    await extract_data(
        ["https://a.org/1"], SCHEMA, LLMConfig(model="openai/gpt-4.1-mini"), extra_instruction="Only 2017."
    )
    assert list(seen["model"].model_fields)[-1] == "grounding_quote"
    assert seen["strategy"].instruction.endswith("Only 2017.")
    assert "CholeraCases" in seen["strategy"].instruction
    assert "grounding_quote" in seen["strategy"].schema["properties"]


async def test_extract_data_errors(fake_crawler) -> None:
    with pytest.raises(ValueError, match="mistral_ocr_config is required"):
        await extract_data(["https://a.org/1"], SCHEMA, LLMConfig(), handle_pdfs=True)
    with pytest.raises(SchemaError):
        await extract_data(["https://a.org/1"], "print('hi')", LLMConfig())
    assert fake_crawler.crawled == []
