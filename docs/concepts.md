# How it works

## Queries

`generate_search_queries` asks the LLM for short, literal queries that find pages with one or a few
data points, rather than pages listing a whole dataset. Given variable names, it returns templates
instead, and `retrieve_webpages` fills them with every combination of the values you pass, so
`{state}` × 50 states gives 50 queries per template.

## Search

Searches go to Google through the Bright Data SERP API, 20 results per page. DataScout searches and
fetches the result pages; it does not follow links from them. Options:

- **Date range**: `start_date` and `end_date` add Google's `after:`/`before:` operators. With
  `time_chunking=True` the range is split into periods of at most 366 days, each searched
  separately, which returns more results over long ranges.
- **Bias toward large outlets**: search results favour a few large, often English-language sites.
  `media_cloud_country` restricts results to that country's news sources, taken from bundled
  [Media Cloud](https://www.mediacloud.org/) collections (`get_media_cloud_countries()` lists them;
  the first 50 domains are used). `geolocation_country` runs the search as if from that country.
  `retrieve_webpages_streaming` can set either per variable value, such as each country's own news
  sources.
- **News only**: `news_only=True` searches Google News.

Each URL is returned once, the first time it is found. `rerank_results_jina_api` scores each result
(for example its title) against its query with the Jina Reranker, so you can drop irrelevant pages
before the more expensive extraction step.

## Extraction and grounding

The extraction schema is a small Pydantic class written as text. `generate_extraction_schema`
drafts it from your fields and description; you can edit it before use. The text is **parsed, not
executed**: `parse_extraction_schema` accepts only one class with `str`, `int`, `float` or `bool`
fields (optionally `Optional[...]` or `List[...]`) and literal `Field(...)` arguments, and raises
`SchemaError` for anything else.

[crawl4ai](https://github.com/unclecode/crawl4ai) loads each page in a headless browser, converts it
to Markdown and asks the LLM for every data point matching the schema. PDF URLs are skipped unless
`handle_pdfs=True`, in which case Mistral OCR reads them first.

To make hallucinations visible, DataScout adds a `grounding_quote` field: the LLM must copy a short
span of text from the page that supports the data point. The quote is then searched for in the page,
ignoring whitespace, punctuation and Markdown links. The result is in `is_grounded`. A grounded data
point's `source` is a [text fragment link](https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Fragment/Text_fragments)
that opens the page at the quote, so a person can check it in one click. Grounding shows that the
quote is on the page, not that the extracted values are correct.

## Quality control

`control_quality` sends the whole dataset to the LLM as CSV and asks it to list potential problems
with each row, including inconsistencies with other rows (for example a cumulative count that goes
down). It returns comments; it does not change or remove data.

## Limitations

- The quality of every stage depends on the LLM; results vary between models and runs.
- Search is Google through Bright Data only.
- Pages that block automated browsers, or need a login, can't be extracted.
- `get_url_date` guesses publication dates from page metadata with htmldate and can be wrong.
