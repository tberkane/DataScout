# DataScout

**LLM-based web data collection for research dataset creation.**

[![CI](https://github.com/tberkane/DataScout/actions/workflows/ci.yml/badge.svg)](https://github.com/tberkane/DataScout/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-tberkane.github.io%2FDataScout-blue)](https://tberkane.github.io/DataScout/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Researchers often build datasets by hand from news articles, reports and government pages. DataScout
automates that with large language models. You describe the data you need, and it:

1. **generates search queries** from the description, optionally as templates filled with every value
   of your variables (states, countries, diseases, etc.);
2. **retrieves web pages** with Google search (through Bright Data), with date ranges, geolocation,
   news-only results and per-country news sources from Media Cloud to reduce bias toward a few
   large outlets, and **reranks** them with the Jina Reranker;
3. **extracts data points** from web pages and PDFs (via Mistral OCR) into a schema you review. Each
   data point keeps a verbatim quote, which DataScout checks against the page, plus a link that
   opens the page at that quote;
4. **flags data points** that look wrong or inconsistent with the rest of the dataset.

Each stage is a plain Python function, so a person can review and edit its output before the next
one runs. DataScout is the open-source implementation of
[*LLM-Based Web Data Collection for Research Dataset Creation*](https://doi.org/10.18653/v1/2025.findings-emnlp.674)
(Findings of EMNLP 2025).

## Install

```bash
pip install "datascout @ git+https://github.com/tberkane/DataScout@v0.1.0"
crawl4ai-setup  # installs the headless browser used for extraction
```

Python 3.10 or later. API keys: an LLM provider supported by [litellm](https://docs.litellm.ai/)
(e.g. `OPENAI_API_KEY`), Bright Data (`BRIGHT_DATA_API_KEY`, `BRIGHT_DATA_ZONE`), and optionally Jina
(`JINA_API_KEY`) and Mistral (`MISTRAL_API_KEY`, for PDFs).

## Example

```python
import asyncio, os
from datascout import (
    BrightDataConfig,
    LLMConfig,
    control_quality,
    extract_data,
    generate_extraction_schema,
    generate_search_queries,
    retrieve_webpages,
)

llm = LLMConfig(model="openai/gpt-4.1")
bright_data = BrightDataConfig(api_key=os.environ["BRIGHT_DATA_API_KEY"], zone=os.environ["BRIGHT_DATA_ZONE"])
description = "Reports of download counts of COVID contact tracing apps in different U.S. states."
variables = {"state_and_app_name": ["Alabama GuideSafe", "Arizona Covid Watch"]}

templates = generate_search_queries(description, 2, llm, variable_names=list(variables))
results = retrieve_webpages(templates, 1, bright_data, variables, start_date="2020-01-01", end_date="2022-12-31")
urls = [r["link"] for by_query in results.values() for rs in by_query.values() for r in rs]

schema = generate_extraction_schema(description, ["state", "date"], llm)  # review it
data = asyncio.run(extract_data(urls, schema, llm))
issues = control_quality(data, description, llm)
```

The [quickstart](https://tberkane.github.io/DataScout/quickstart/) and
[`examples/quickstart.ipynb`](examples/quickstart.ipynb) add reranking and explain each output.
[`examples/data/`](examples/data/) holds the datasets of the paper's three tasks.

## Documentation

<https://tberkane.github.io/DataScout/>: [quickstart](https://tberkane.github.io/DataScout/quickstart/),
[how it works](https://tberkane.github.io/DataScout/concepts/) (including limitations) and the
[API reference](https://tberkane.github.io/DataScout/api/).

## Development

```bash
pip install -e ".[dev]"
pytest                  # offline: LLM, search, crawler and OCR are mocked
ruff check . && mypy
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md) and
[ROADMAP.md](ROADMAP.md).

## Earlier name

Until version 0.1.0 this project was called `web-data-collection`. `import web_data_collection`
still works, with a `DeprecationWarning`, and will be removed in 1.0.

## Citation

If you use DataScout, please cite:

```bibtex
@inproceedings{berkane-etal-2025-llm,
    title = "{LLM}-Based Web Data Collection for Research Dataset Creation",
    author = "Berkane, Thomas and Charpignon, Marie-Laure and Majumder, Maimuna S.",
    booktitle = "Findings of the Association for Computational Linguistics: EMNLP 2025",
    year = "2025",
    address = "Suzhou, China",
    publisher = "Association for Computational Linguistics",
    pages = "12610--12622",
    doi = "10.18653/v1/2025.findings-emnlp.674",
    url = "https://aclanthology.org/2025.findings-emnlp.674/"
}
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
