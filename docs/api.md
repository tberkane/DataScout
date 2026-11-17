# API reference

Everything below is importable from `datascout` directly.

## Configuration

::: datascout.configs
    options:
      members: [LLMConfig, BrightDataConfig, JinaConfig, MistralOCRConfig]

## 1. Query generation

::: datascout.query_generation
    options:
      members: [generate_search_queries]

## 2. Web page retrieval

::: datascout.webpage_retrieval
    options:
      members: [retrieve_webpages, retrieve_webpages_streaming, rerank_results_jina_api, get_url_date, get_media_cloud_countries, get_media_cloud_sources, get_geolocation_countries]

## 3. Data extraction

::: datascout.data_extraction
    options:
      members: [generate_extraction_schema, parse_extraction_schema, extract_data, extract_data_streaming, is_grounded, SchemaError]

## 4. Quality control

::: datascout.quality_control
    options:
      members: [control_quality]
