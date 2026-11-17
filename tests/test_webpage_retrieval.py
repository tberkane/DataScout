from __future__ import annotations

import string
import time
import urllib.parse
from datetime import date, datetime, timedelta

import pytest
import requests
from hypothesis import given
from hypothesis import strategies as st

import datascout.webpage_retrieval as wr
from datascout import (
    BrightDataConfig,
    JinaConfig,
    get_geolocation_countries,
    get_media_cloud_countries,
    get_media_cloud_sources,
    get_url_date,
    rerank_results_jina_api,
    retrieve_webpages,
    retrieve_webpages_streaming,
)

BD = BrightDataConfig(api_key="bd-key", zone="serp")


def google_params(call: dict) -> dict[str, str]:
    url = call["json"]["url"]
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}


def serp(*links: str, kind: str = "organic") -> dict:
    return {kind: [{"link": link, "title": f"title {link}", "description": "d", "source": "S"} for link in links]}


# --- template expansion -------------------------------------------------------------------------

names = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=6)
values = st.lists(st.text(alphabet=string.ascii_letters + " ", min_size=1, max_size=8), min_size=1, max_size=3)


@given(
    variables=st.dictionaries(names, values, min_size=1, max_size=3), extra=st.text(string.ascii_lowercase, max_size=5)
)
def test_expansion_fills_every_combination(variables: dict[str, list[str]], extra: str) -> None:
    template = " ".join(f"{{{name}}}" for name in variables) + f" {extra}"
    queries = wr._expand_query_templates([template], variables)

    expected = 1
    for vals in variables.values():
        expected *= len(vals)
    assert len(queries) == expected
    for query in queries:
        assert "{" not in query.text
        assert query.combo is not None and len(query.combo) == len(variables)
        assert list(query.values) == list(variables)  # combination order follows the variables dict
        assert query.text == " ".join(query.combo) + f" {extra}"


def test_expansion_is_case_insensitive_and_keeps_plain_templates() -> None:
    queries = wr._expand_query_templates(["{State} cases", "no vars"], {"State": ["AL", "AZ"]})
    assert [(q.text, q.combo) for q in queries] == [("AL cases", ("AL",)), ("AZ cases", ("AZ",)), ("no vars", None)]
    assert [q.text for q in wr._expand_query_templates(["a", "b"], None)] == ["a", "b"]


def test_expansion_inserts_values_literally() -> None:
    (query,) = wr._expand_query_templates(["{x} y"], {"x": [r"a\1 b"]})
    assert query.text == r"a\1 b y"


# --- date chunks -------------------------------------------------------------------------------

days = st.dates(min_value=date(1990, 1, 1), max_value=date(2035, 12, 31))


@given(start=days, length=st.integers(min_value=0, max_value=4000))
def test_date_chunks_partition_the_range(start: date, length: int) -> None:
    end = start + timedelta(days=length)
    chunks = wr._get_date_chunks(start.isoformat(), end.isoformat())
    parsed = [(datetime.strptime(c["start"], "%Y-%m-%d"), datetime.strptime(c["end"], "%Y-%m-%d")) for c in chunks]

    assert chunks[0]["start"] == start.isoformat() and chunks[-1]["end"] == end.isoformat()
    assert len(chunks) == -(-(length + 1) // 366)
    sizes = [(e - s).days + 1 for s, e in parsed]
    assert sum(sizes) == length + 1
    assert max(sizes) <= 366 and max(sizes) - min(sizes) <= 1
    for (_, prev_end), (next_start, _) in zip(parsed, parsed[1:], strict=False):
        assert next_start - prev_end == timedelta(days=1)


def test_date_chunk_errors() -> None:
    with pytest.raises(ValueError, match="after"):
        wr._get_date_chunks("2021-01-02", "2021-01-01")
    with pytest.raises(ValueError):
        wr._get_date_chunks("2021-13-01", "2022-01-01")
    with pytest.raises(ValueError, match="requires both"):
        retrieve_webpages(["q"], 1, BD, start_date="2020-01-01", time_chunking=True)


# --- country data -------------------------------------------------------------------------------


def test_bundled_country_data() -> None:
    assert "United States" in get_media_cloud_countries()
    assert "United States" in get_geolocation_countries()
    sources = get_media_cloud_sources("United States")
    assert sources and all(isinstance(s, str) for s in sources)
    sources.clear()  # callers get a copy, not the cached list
    assert get_media_cloud_sources("United States")
    with pytest.raises(ValueError, match="No Media Cloud collection"):
        get_media_cloud_sources("Atlantis")
    with pytest.raises(ValueError, match="Unknown geolocation country"):
        wr._country_code("Atlantis")


def test_build_search_query_truncates_sites() -> None:
    query = wr._build_search_query("q", "2020-01-01", "2020-12-31", [f"s{i}.com" for i in range(60)])
    assert query.startswith("q after:2020-01-01 before:2020-12-31 site:s0.com OR site:s1.com")
    assert query.count("site:") == 50
    assert wr._build_search_query("q", None, None, None) == "q"


# --- retrieval -----------------------------------------------------------------------------------


def test_retrieve_webpages_groups_and_dedups(fake_http) -> None:
    pages = {
        ("AL app", "0"): serp("a", "b", "a"),
        ("AL app", "20"): serp("c"),
        ("AZ app", "0"): serp("b", "d"),
        ("AZ app", "20"): serp(),
    }
    fake_http.handler = lambda url, body: pages[
        (google_params({"json": body})["q"], google_params({"json": body})["start"])
    ]

    results = retrieve_webpages(["{state} app"], 2, BD, {"state": ["AL", "AZ"]})

    assert {k: {q: [r["link"] for r in v] for q, v in d.items()} for k, d in results.items()} == {
        ("AL",): {"AL app": ["a", "b", "c"]},
        ("AZ",): {"AZ app": ["d"]},
    }
    first = fake_http.calls[0]
    assert first["url"] == BD.base_url
    assert first["headers"]["Authorization"] == "Bearer bd-key"
    assert first["json"]["zone"] == "serp" and first["json"]["format"] == "raw"
    assert google_params(first) == {"q": "AL app", "start": "0", "brd_json": "1", "num": "20"}
    assert first["timeout"] > 0


def test_retrieve_webpages_filters(fake_http) -> None:
    fake_http.handler = lambda url, body: serp("n1", kind="news")
    results = retrieve_webpages(
        ["flood"],
        1,
        BD,
        start_date="2020-01-01",
        end_date="2021-06-30",
        time_chunking=True,
        media_cloud_country="United States",
        geolocation_country="United States",
        news_only=True,
    )
    assert len(fake_http.calls) == 2  # two date chunks, one page each
    params = [google_params(c) for c in fake_http.calls]
    assert params[0]["tbm"] == "nws" and params[0]["gl"] == "us"
    assert "after:2020-01-01 before:2020-09-30" in params[0]["q"]
    assert "after:2020-10-01 before:2021-06-30" in params[1]["q"]
    assert params[0]["q"].count("site:") == 50
    assert results == {None: {"flood": [{"link": "n1", "title": "title n1", "description": "d", "source": "S"}]}}


def test_retrieve_webpages_http_error(fake_http) -> None:
    fake_http.status = 500
    with pytest.raises(requests.HTTPError):
        retrieve_webpages(["q"], 1, BD)


def test_streaming_yields_combo_query_and_result(fake_http) -> None:
    fake_http.handler = lambda url, body: serp("x", "y")
    items = list(retrieve_webpages_streaming(["{s} app"], 1, BD, {"s": ["AL", "AZ"]}, start_date="2020-01-01"))
    assert items == [
        (("AL",), "AL app after:2020-01-01", {"link": "x", "title": "title x", "description": "d"}),
        (("AL",), "AL app after:2020-01-01", {"link": "y", "title": "title y", "description": "d"}),
    ]


def test_streaming_countries_per_variable_value(fake_http) -> None:
    fake_http.handler = lambda url, body: serp(google_params({"json": body})["q"][:2])
    list(
        retrieve_webpages_streaming(
            ["{State} {topic}"],
            1,
            BD,
            {"State": ["Kenya", "Peru", "Chad"], "topic": ["floods"]},
            variable_name_with_assigned_countries="State",
            variable_values_media_cloud_countries={"Kenya": "Kenya"},
            variable_values_geolocation_countries={"Peru": "Peru"},
        )
    )
    kenya, peru, chad = (google_params(c) for c in fake_http.calls)
    assert "site:" in kenya["q"] and "gl" not in kenya
    assert "site:" not in peru["q"] and peru["gl"] == "pe"
    assert "site:" not in chad["q"] and "gl" not in chad


def test_streaming_rejects_global_and_per_value_countries() -> None:
    with pytest.raises(ValueError, match="not both"):
        next(
            retrieve_webpages_streaming(
                ["q"], 1, BD, geolocation_country="Peru", variable_name_with_assigned_countries="s"
            )
        )


# --- reranking and dates -------------------------------------------------------------------------


def test_rerank_groups_documents_by_query(fake_http) -> None:
    def handler(url: str, body: dict) -> dict:
        ranked = sorted(body["documents"], key=len, reverse=True)
        return {"results": [{"document": {"text": t}, "relevance_score": len(t) / 10} for t in ranked]}

    fake_http.handler = handler
    jina = JinaConfig(api_key="jina-key")
    out = rerank_results_jina_api(["q1", "q2", "q1"], ["a", "bb", "ccc"], jina)
    assert out == [
        {"query": "q1", "text": "ccc", "score": 0.3},
        {"query": "q1", "text": "a", "score": 0.1},
        {"query": "q2", "text": "bb", "score": 0.2},
    ]
    assert fake_http.calls[0]["json"]["documents"] == ["a", "ccc"]
    assert fake_http.calls[0]["json"]["model"] == jina.model
    assert fake_http.calls[0]["url"] == jina.base_url


def test_rerank_edge_cases(fake_http) -> None:
    assert rerank_results_jina_api([], [], JinaConfig("k")) == []
    with pytest.raises(ValueError, match="2 queries but 1 documents"):
        rerank_results_jina_api(["a", "b"], ["x"], JinaConfig("k"))
    assert fake_http.calls == []


def test_get_url_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wr, "find_date", lambda url, extensive_search: "2020-09-28")
    assert get_url_date("https://example.org") == "2020-09-28"

    monkeypatch.setattr(wr, "find_date", lambda url, extensive_search: None)
    assert get_url_date("https://example.org") is None

    def forbidden(url: str, extensive_search: bool) -> str:
        raise ValueError("403")

    monkeypatch.setattr(wr, "find_date", forbidden)
    assert get_url_date("https://example.org") is None

    monkeypatch.setattr(wr, "find_date", lambda url, extensive_search: time.sleep(2))
    assert get_url_date("https://example.org", timeout=0.05) is None
