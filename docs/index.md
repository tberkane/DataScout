# DataScout

DataScout collects research datasets from the web with large language models (LLMs). You describe
the data you need, such as *"reported cholera case counts by country and week"*, and DataScout:

1. **generates search queries** from the description, optionally as templates filled with every
   value of your variables (states, countries, diseases, etc.);
2. **retrieves web pages** with Google search, with optional date ranges, geolocation, news-only
   results and per-country news-source filters, and **reranks** them by relevance;
3. **extracts data points** from each page (and from PDFs, through OCR) into a schema you review,
   keeping a verbatim quote for each one and checking that the quote is really on the page;
4. **flags data points** that look wrong or inconsistent with the rest of the dataset.

Each stage is a plain Python function, so you can inspect and edit its output before running the
next one. A person stays in the loop: DataScout gathers candidates and their sources, and you decide
what goes into the dataset.

DataScout is the open-source implementation of the framework described in
[Berkane, Charpignon and Majumder, *LLM-Based Web Data Collection for Research Dataset Creation*, Findings of EMNLP 2025](https://doi.org/10.18653/v1/2025.findings-emnlp.674).

## Install

DataScout is not on PyPI yet. Install it from GitHub (Python 3.10 or later):

```bash
pip install "datascout @ git+https://github.com/tberkane/DataScout@v0.1.0"
crawl4ai-setup  # installs the headless browser used to fetch pages
```

Then follow the [quickstart](quickstart.md).

## External services

DataScout calls paid services that need API keys:

| Service | Used for | Needed by |
| --- | --- | --- |
| An LLM provider through [litellm](https://docs.litellm.ai/) (e.g. OpenAI) | queries, schemas, extraction, quality control | every stage |
| [Bright Data](https://brightdata.com/) SERP API | Google searches | `retrieve_webpages` |
| [Jina Reranker](https://jina.ai/reranker/) | relevance scores | `rerank_results_jina_api` (optional) |
| [Mistral OCR](https://mistral.ai/) | reading PDFs | `extract_data(handle_pdfs=True)` (optional) |

The test suite mocks all of them and runs offline.

## Earlier name

DataScout was called `web-data-collection` until version 0.1.0. `import web_data_collection` still
works but emits a `DeprecationWarning`; it will be removed in 1.0.
