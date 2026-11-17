# Changelog

All notable changes to DataScout are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Before 1.0, minor versions may change the API.

## [0.1.0] - 2026-11-18

First tagged release. The project was renamed from `web-data-collection` to DataScout; the code is
the implementation of the EMNLP 2025 Findings paper, with the changes below.

### Added

- `datascout` package (src layout, single `pyproject.toml`, typed, `py.typed`) with the four
  pipeline stages: `generate_search_queries`; `retrieve_webpages` / `retrieve_webpages_streaming`
  with date ranges, time chunking, geolocation, news-only search and Media Cloud source filters,
  plus `rerank_results_jina_api` and `get_url_date`; `generate_extraction_schema` and
  `extract_data` / `extract_data_streaming` with grounding checks and PDF OCR; `control_quality`.
- `parse_extraction_schema` and `SchemaError`: schemas are parsed into Pydantic models instead of
  executed.
- `is_grounded` and `get_media_cloud_sources` in the public API; `verbose` option for extraction
  (crawl4ai's progress log is off by default).
- Offline test suite (mocked LLM, HTTP, crawler and OCR; Hypothesis property tests), ruff, mypy,
  GitHub Actions CI, and a documentation site.
- `web_data_collection` alias package, so existing code keeps working (deprecated).

### Changed

- Configuration classes are dataclasses, and their API keys are hidden from `repr`.
- The non-streaming functions now share the streaming ones' code; results are deduplicated per URL
  across all queries, including duplicates within one results page.
- Invalid arguments raise `ValueError` instead of `AssertionError`, and search errors propagate as
  `requests.HTTPError` instead of a bare `Exception`.
- HTTP requests to Bright Data and Jina time out after 60 seconds.
- The CSV sent for quality control has an `id` header for its index column.

### Fixed

- `get_url_date` used `SIGALRM`, which fails outside the main thread (e.g. in web servers) and on
  Windows, and could leave an alarm pending; it now uses a thread.
- Template variables are filled in a fixed order (they followed set order, which varied between
  runs) and case-insensitively; per-variable-value countries now apply to the right variable.
- Time chunking could produce a chunk longer than 366 days.
- Extraction crashed on data points without an `error` key, treated any URL containing ".pdf" as a
  PDF, and required the schema to use four-space indentation.
- `control_quality` crashed on reply lines that did not start with a row number.

### Deprecated

- `import web_data_collection`: use `import datascout`. The alias will be removed in 1.0.

[0.1.0]: https://github.com/tberkane/DataScout/releases/tag/v0.1.0
