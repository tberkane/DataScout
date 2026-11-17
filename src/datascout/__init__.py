"""DataScout: LLM-based web data collection for research dataset creation.

The pipeline has four stages, each a plain function so that a person can review its output before
the next one runs:

1. `generate_search_queries` turns a dataset description into search queries or templates.
2. `retrieve_webpages` runs them (with date, country and news-source filters), and
   `rerank_results_jina_api` scores the results' relevance.
3. `generate_extraction_schema` drafts a schema, and `extract_data` extracts grounded
   data points from the pages.
4. `control_quality` flags data points that look wrong.
"""

import logging
from importlib.metadata import PackageNotFoundError, version

from .configs import BrightDataConfig, JinaConfig, LLMConfig, MistralOCRConfig
from .data_extraction import (
    SchemaError,
    extract_data,
    extract_data_streaming,
    generate_extraction_schema,
    is_grounded,
    parse_extraction_schema,
)
from .quality_control import control_quality
from .query_generation import generate_search_queries
from .webpage_retrieval import (
    get_geolocation_countries,
    get_media_cloud_countries,
    get_media_cloud_sources,
    get_url_date,
    rerank_results_jina_api,
    retrieve_webpages,
    retrieve_webpages_streaming,
)

try:
    __version__ = version("datascout")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without installing
    __version__ = "0+unknown"

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "BrightDataConfig",
    "JinaConfig",
    "LLMConfig",
    "MistralOCRConfig",
    "SchemaError",
    "__version__",
    "control_quality",
    "extract_data",
    "extract_data_streaming",
    "generate_extraction_schema",
    "generate_search_queries",
    "get_geolocation_countries",
    "get_media_cloud_countries",
    "get_media_cloud_sources",
    "get_url_date",
    "is_grounded",
    "parse_extraction_schema",
    "rerank_results_jina_api",
    "retrieve_webpages",
    "retrieve_webpages_streaming",
]
