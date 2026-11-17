"""Stage 2: run search queries, filter them by date, country and news source, and rerank the results.

Searches go to Google through the [Bright Data](https://brightdata.com/) SERP API. Two options
reduce search-engine bias toward a few large outlets: restricting results to a country's news
sources from [Media Cloud](https://www.mediacloud.org/) collections, and geolocating the search
in a country.
"""

from __future__ import annotations

import itertools
import json
import logging
import re
import urllib.parse
from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Optional

import requests
from htmldate import find_date

from .configs import BrightDataConfig, JinaConfig
from .utils import normalize_variable_name, timeout_function

__all__ = [
    "SearchResult",
    "VariableCombo",
    "get_geolocation_countries",
    "get_media_cloud_countries",
    "get_media_cloud_sources",
    "get_url_date",
    "rerank_results_jina_api",
    "retrieve_webpages",
    "retrieve_webpages_streaming",
]

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
RESULTS_PER_PAGE = 20
MAX_DAYS_PER_CHUNK = 366
MAX_MEDIA_CLOUD_SITES = 50
REQUEST_TIMEOUT = 60

SearchResult = dict[str, str]
"""A search result: ``link``, ``title``, ``description`` and, for news searches, ``source``."""

VariableCombo = Optional[tuple[str, ...]]  # noqa: UP045 - runtime alias, kept readable in docs
"""The variable values a query was filled with, in the order of ``search_query_variables``, or ``None``."""


@dataclass(frozen=True)
class _Query:
    text: str
    combo: VariableCombo = None
    values: Mapping[str, str] = field(default_factory=dict)  # normalized variable name -> value


@cache
def _load_json(name: str) -> dict[str, Any]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def get_media_cloud_countries() -> list[str]:
    """Countries for which a Media Cloud news-source collection is bundled."""
    return list(_load_json("country_to_mc_sources.json"))


def get_media_cloud_sources(collection: str) -> list[str]:
    """Domains of the news sources in a country's Media Cloud collection.

    Args:
        collection: A country name from `get_media_cloud_countries`.

    Raises:
        ValueError: If there is no collection for that country.
    """
    sources = _load_json("country_to_mc_sources.json")
    if collection not in sources:
        raise ValueError(f"No Media Cloud collection for {collection!r}; see get_media_cloud_countries()")
    return list(sources[collection])


def get_geolocation_countries() -> list[str]:
    """Countries that searches can be geolocated in."""
    return list(_load_json("country_to_code.json"))


def _country_code(country: str) -> str:
    codes = _load_json("country_to_code.json")
    if country not in codes:
        raise ValueError(f"Unknown geolocation country {country!r}; see get_geolocation_countries()")
    return str(codes[country])


def _fill_placeholder(template: str, name: str, value: str) -> str:
    """Replace every ``{name}`` in ``template`` (case-insensitively) with ``value``, taken literally."""
    return re.compile(re.escape(f"{{{name}}}"), re.IGNORECASE).sub(lambda _match: value, template)


def _expand_query_templates(templates: Sequence[str], variables: Mapping[str, Sequence[str]] | None) -> list[_Query]:
    """Fill each template's ``{variable}`` placeholders with every combination of variable values.

    Placeholders are matched case-insensitively against the normalized variable names. A template
    without placeholders is kept as is. Combinations follow the order of ``variables``.
    """
    if not variables:
        return [_Query(t) for t in templates]

    normalized = {normalize_variable_name(k): list(v) for k, v in variables.items()}
    queries = []
    for template in templates:
        names = [n for n in normalized if f"{{{n}}}" in template.lower()]
        if not names:
            queries.append(_Query(template))
            continue
        for combo in itertools.product(*(normalized[n] for n in names)):
            text = template
            for name, value in zip(names, combo, strict=True):
                text = _fill_placeholder(text, name, value)
            queries.append(_Query(text, tuple(combo), dict(zip(names, combo, strict=True))))
    return queries


def _get_date_chunks(start_date: str, end_date: str) -> list[dict[str, str]]:
    """Split an inclusive date range into contiguous chunks of at most 366 days, as equal in length as possible.

    Args:
        start_date: First day, ``YYYY-MM-DD``.
        end_date: Last day, ``YYYY-MM-DD``.

    Returns:
        ``[{"start": ..., "end": ...}, ...]`` in chronological order.

    Raises:
        ValueError: If a date is malformed or ``start_date`` is after ``end_date``.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if start > end:
        raise ValueError(f"start_date {start_date} is after end_date {end_date}")

    total_days = (end - start).days + 1
    num_chunks = -(-total_days // MAX_DAYS_PER_CHUNK)
    base, extra = divmod(total_days, num_chunks)

    chunks = []
    current = start
    for i in range(num_chunks):
        chunk_end = current + timedelta(days=base + (1 if i < extra else 0) - 1)
        chunks.append({"start": current.strftime("%Y-%m-%d"), "end": chunk_end.strftime("%Y-%m-%d")})
        current = chunk_end + timedelta(days=1)
    return chunks


def _date_chunks(start_date: str | None, end_date: str | None, time_chunking: bool) -> list[dict[str, str | None]]:
    if not time_chunking:
        return [{"start": start_date, "end": end_date}]
    if not (start_date and end_date):
        raise ValueError("time_chunking requires both start_date and end_date")
    return [{"start": c["start"], "end": c["end"]} for c in _get_date_chunks(start_date, end_date)]


def _build_search_query(
    query: str,
    start_date: str | None,
    end_date: str | None,
    media_cloud_sources: Sequence[str] | None,
    num_mc_sites: int = MAX_MEDIA_CLOUD_SITES,
) -> str:
    """Add Google ``after:``/``before:`` date filters and ``site:`` filters for up to ``num_mc_sites`` sources."""
    if start_date:
        query = f"{query} after:{start_date}"
    if end_date:
        query = f"{query} before:{end_date}"
    if media_cloud_sources:
        query = f"{query} {' OR '.join(f'site:{site}' for site in media_cloud_sources[:num_mc_sites])}"
    return query


def _fetch_results_page(
    search_query: str,
    page: int,
    bright_data_config: BrightDataConfig,
    news_only: bool,
    country_code: str | None,
) -> list[SearchResult]:
    """Fetch one page of Google results (20 per page) through Bright Data."""
    url = (
        f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}"
        f"&start={page * RESULTS_PER_PAGE}&brd_json=1&num={RESULTS_PER_PAGE}"
    )
    if news_only:
        url += "&tbm=nws"
    if country_code:
        url += f"&gl={country_code}"

    response = requests.post(
        bright_data_config.base_url,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {bright_data_config.api_key}"},
        json={"zone": bright_data_config.zone, "url": url, "format": "raw"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    for item in payload.get("news" if news_only else "organic", []):
        result = {
            "link": item.get("link", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
        }
        if news_only:
            result["source"] = item.get("source", "")
        results.append(result)
    logger.debug("Retrieved %d results for %r (page %d)", len(results), search_query, page + 1)
    return results


def _stream_query(
    query: str,
    date_chunks: Sequence[Mapping[str, str | None]],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    media_cloud_sources: Sequence[str] | None,
    geolocation_country: str | None,
    news_only: bool,
    seen_urls: set[str],
) -> Generator[tuple[str, SearchResult], None, None]:
    """Yield ``(search query as sent, result)`` for every result not seen before, across date chunks and pages."""
    country_code = _country_code(geolocation_country) if geolocation_country else None
    for chunk in date_chunks:
        search_query = _build_search_query(query, chunk["start"], chunk["end"], media_cloud_sources)
        for page in range(results_pages_per_query):
            for result in _fetch_results_page(search_query, page, bright_data_config, news_only, country_code):
                if result["link"] not in seen_urls:
                    seen_urls.add(result["link"])
                    yield search_query, result


def retrieve_webpages(
    search_query_templates: Sequence[str],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    search_query_variables: Mapping[str, Sequence[str]] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    time_chunking: bool = False,
    media_cloud_country: str | None = None,
    geolocation_country: str | None = None,
    news_only: bool = False,
) -> dict[VariableCombo, dict[str, list[SearchResult]]]:
    """Run the search queries and collect the results.

    Templates are filled with every combination of ``search_query_variables`` (see
    `datascout.generate_search_queries`). Each URL is returned once, the first time it is
    found.

    Args:
        search_query_templates: Queries, or templates with ``{variable}`` placeholders.
        results_pages_per_query: Result pages to fetch per query and date chunk (20 results each).
        bright_data_config: Bright Data settings.
        search_query_variables: Values for each template variable, e.g. ``{"state": ["Alabama", "Arizona"]}``.
        start_date: Only return pages from this date on (``YYYY-MM-DD``).
        end_date: Only return pages up to this date (``YYYY-MM-DD``).
        time_chunking: Search each period of at most 366 days separately, which returns more results
            over long ranges. Requires both dates.
        media_cloud_country: Only return pages from that country's Media Cloud news sources (the first
            50 domains of the collection).
        geolocation_country: Run the search as if from that country.
        news_only: Search Google News instead of web results.

    Returns:
        ``{variable value combination: {query: [result, ...]}}``. The combination is ``None`` for
        queries without variables.

    Raises:
        ValueError: For an unknown country, malformed dates, or ``time_chunking`` without both dates.
        requests.HTTPError: If a Bright Data request fails.
    """
    queries = _expand_query_templates(search_query_templates, search_query_variables)
    logger.debug("Expanded %d templates into %d queries", len(search_query_templates), len(queries))
    date_chunks = _date_chunks(start_date, end_date, time_chunking)
    media_cloud_sources = get_media_cloud_sources(media_cloud_country) if media_cloud_country else None

    results: dict[VariableCombo, dict[str, list[SearchResult]]] = {}
    seen_urls: set[str] = set()
    for query in queries:
        bucket = results.setdefault(query.combo, {}).setdefault(query.text, [])
        for _, result in _stream_query(
            query.text,
            date_chunks,
            results_pages_per_query,
            bright_data_config,
            media_cloud_sources,
            geolocation_country,
            news_only,
            seen_urls,
        ):
            bucket.append(result)
    return results


def retrieve_webpages_streaming(
    search_query_templates: Sequence[str],
    results_pages_per_query: int,
    bright_data_config: BrightDataConfig,
    search_query_variables: Mapping[str, Sequence[str]] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    time_chunking: bool = False,
    media_cloud_country: str | None = None,
    geolocation_country: str | None = None,
    news_only: bool = False,
    variable_name_with_assigned_countries: str | None = None,
    variable_values_media_cloud_countries: Mapping[str, str] | None = None,
    variable_values_geolocation_countries: Mapping[str, str] | None = None,
) -> Generator[tuple[VariableCombo, str, SearchResult], None, None]:
    """Like `retrieve_webpages`, but yield each result as soon as it arrives.

    This version can also set the country per variable value, e.g. a different Media Cloud
    collection for each state in ``{"state": [...]}``. Name the variable in
    ``variable_name_with_assigned_countries`` and map its values to countries.

    Args:
        search_query_templates: See `retrieve_webpages`.
        results_pages_per_query: See `retrieve_webpages`.
        bright_data_config: See `retrieve_webpages`.
        search_query_variables: See `retrieve_webpages`.
        start_date: See `retrieve_webpages`.
        end_date: See `retrieve_webpages`.
        time_chunking: See `retrieve_webpages`.
        media_cloud_country: See `retrieve_webpages`.
        geolocation_country: See `retrieve_webpages`.
        news_only: See `retrieve_webpages`.
        variable_name_with_assigned_countries: The variable whose values have their own countries.
        variable_values_media_cloud_countries: ``{variable value: Media Cloud country}``.
        variable_values_geolocation_countries: ``{variable value: geolocation country}``.

    Yields:
        ``(variable value combination, search query as sent including date and site filters, result)``.

    Raises:
        ValueError: If countries are set both globally and per variable value, plus the errors of
            `retrieve_webpages`.
    """
    if variable_name_with_assigned_countries and (media_cloud_country or geolocation_country):
        raise ValueError("Assign countries either globally or per variable value, not both")

    queries = _expand_query_templates(search_query_templates, search_query_variables)
    logger.debug("Expanded %d templates into %d queries", len(search_query_templates), len(queries))
    date_chunks = _date_chunks(start_date, end_date, time_chunking)
    media_cloud_sources = get_media_cloud_sources(media_cloud_country) if media_cloud_country else None
    per_value_sources = {
        value: get_media_cloud_sources(country)
        for value, country in (variable_values_media_cloud_countries or {}).items()
    }
    assigned = normalize_variable_name(variable_name_with_assigned_countries or "")

    seen_urls: set[str] = set()
    for query in queries:
        sources, country = media_cloud_sources, geolocation_country
        value = query.values.get(assigned) if assigned else None
        if value is not None:
            sources = per_value_sources.get(value, sources)
            country = (variable_values_geolocation_countries or {}).get(value, country)
        for search_query, result in _stream_query(
            query.text, date_chunks, results_pages_per_query, bright_data_config, sources, country, news_only, seen_urls
        ):
            yield query.combo, search_query, result


def rerank_results_jina_api(
    queries: Sequence[str], documents: Sequence[str], jina_config: JinaConfig
) -> list[dict[str, Any]]:
    """Score how relevant each document (e.g. a result title) is to its query with the Jina Reranker.

    Documents are grouped by query and each group is ranked in one request.

    Args:
        queries: The query for each document.
        documents: The documents, aligned with ``queries``.
        jina_config: Jina settings.

    Returns:
        ``[{"query": ..., "text": document, "score": relevance}, ...]``, grouped by query in order of
        first appearance, most relevant first within each group.

    Raises:
        ValueError: If ``queries`` and ``documents`` have different lengths.
        requests.HTTPError: If a Jina request fails.
    """
    if len(queries) != len(documents):
        raise ValueError(f"Got {len(queries)} queries but {len(documents)} documents")
    if not documents:
        return []

    groups: dict[str, list[str]] = {}
    for query, document in zip(queries, documents, strict=True):
        groups.setdefault(query, []).append(document)

    reranked = []
    for query, group in groups.items():
        response = requests.post(
            jina_config.base_url,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {jina_config.api_key}"},
            json={
                "model": jina_config.model,
                "query": query,
                "top_n": len(group),
                "documents": group,
                "return_documents": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        for ranked in response.json()["results"]:
            reranked.append({"query": query, "text": ranked["document"]["text"], "score": ranked["relevance_score"]})
    return reranked


def get_url_date(url: str, timeout: float = 5) -> str | None:
    """Guess a web page's publication date with [htmldate](https://htmldate.readthedocs.io/).

    Args:
        url: The page URL. htmldate downloads it.
        timeout: Give up after this many seconds.

    Returns:
        The date as ``YYYY-MM-DD``, or ``None`` if none was found, the download failed, or it timed out.
    """
    try:
        date = timeout_function(find_date, args=(url,), kwargs={"extensive_search": True}, timeout=timeout)
    except Exception as exc:  # htmldate raises various errors on unreachable or malformed pages
        logger.warning("Error extracting date from %s: %s", url, exc)
        return None
    return str(date) if date else None
