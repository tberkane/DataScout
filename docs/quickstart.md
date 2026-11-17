# Quickstart

This walks through the four stages on the example from the paper: reported download counts of
COVID-19 contact-tracing apps in U.S. states. The same code is in
[`examples/quickstart.ipynb`](https://github.com/tberkane/DataScout/blob/main/examples/quickstart.ipynb).

!!! warning "Paid API calls"
    Running this makes LLM, Bright Data and Jina requests on your accounts.

## Setup

```bash
pip install "datascout @ git+https://github.com/tberkane/DataScout@v0.1.0"
crawl4ai-setup
export OPENAI_API_KEY=...        # or the key of another litellm provider
export BRIGHT_DATA_API_KEY=...
export BRIGHT_DATA_ZONE=...      # your Bright Data SERP zone
export JINA_API_KEY=...          # optional, for reranking
export MISTRAL_API_KEY=...       # optional, for PDFs
```

```python
import os
from datascout import BrightDataConfig, JinaConfig, LLMConfig

llm = LLMConfig(model="openai/gpt-4.1")  # reads OPENAI_API_KEY
bright_data = BrightDataConfig(api_key=os.environ["BRIGHT_DATA_API_KEY"], zone=os.environ["BRIGHT_DATA_ZONE"])
jina = JinaConfig(api_key=os.environ["JINA_API_KEY"])

description = "Reports of download counts of COVID contact tracing apps in different U.S. states."
variables = {"state_and_app_name": ["Alabama GuideSafe", "Arizona Covid Watch"]}
```

## 1. Generate search queries

```python
from datascout import generate_search_queries

templates = generate_search_queries(description, 2, llm, variable_names=list(variables))
# e.g. ['{state_and_app_name} COVID contact tracing app download count', ...]
```

Edit the list freely; templates are just strings with `{variable}` placeholders.

## 2. Retrieve and rerank web pages

```python
from datascout import rerank_results_jina_api, retrieve_webpages

results = retrieve_webpages(templates, 1, bright_data, variables, start_date="2020-01-01", end_date="2022-12-31")
pages = [dict(r, query=q) for by_query in results.values() for q, rs in by_query.items() for r in rs]

scores = rerank_results_jina_api([p["query"] for p in pages], [p["title"] for p in pages], jina)
score = {(s["query"], s["text"]): s["score"] for s in scores}
relevant = [p for p in pages if score[(p["query"], p["title"])] > 0.4]
```

`retrieve_webpages` returns `{variable values: {query: [result, ...]}}`; each result has a `link`,
`title` and `description`. Other options: `time_chunking=True` (one search per year of the range),
`news_only=True`, `geolocation_country="United States"` and `media_cloud_country="United States"`
(see [How it works](concepts.md#search)).

## 3. Extract data points

```python
from datascout import extract_data, generate_extraction_schema

schema = generate_extraction_schema(description, ["state", "date"], llm)
print(schema)  # review and edit it

data = await extract_data([p["link"] for p in relevant], schema, llm)  # in a notebook; use asyncio.run() in a script
```

Each data point has the schema's fields plus `grounding_quote`, `is_grounded` and `source`, a link
that opens the page at the quote when it was found.

## 4. Check quality

```python
from datascout import control_quality

issues = control_quality(data, description, llm)
# {'1': 'NA', '2': 'The count is lower than an earlier report for the same app.', ...}
```

Keys are 1-based row numbers in `data`; `"NA"` means the LLM saw no problem.
