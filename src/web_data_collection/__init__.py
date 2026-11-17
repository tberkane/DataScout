"""Deprecated alias of `datascout`, the project's former name.

``import web_data_collection`` and ``import web_data_collection.<module>`` keep working, with a
``DeprecationWarning``. Import `datascout` instead; this alias will be removed in DataScout 1.0.
"""

import importlib
import sys
import warnings

from datascout import *  # noqa: F403
from datascout import __all__, __version__  # noqa: F401

warnings.warn(
    "'web_data_collection' has been renamed to 'datascout'. Import datascout instead; "
    "the old name will be removed in DataScout 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

for _name in (
    "configs",
    "data_extraction",
    "prompts",
    "quality_control",
    "query_generation",
    "utils",
    "webpage_retrieval",
):
    _module = importlib.import_module(f"datascout.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module
