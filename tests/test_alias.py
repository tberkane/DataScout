from __future__ import annotations

import importlib
import sys

import pytest

import datascout


def test_old_package_name_still_works() -> None:
    sys.modules.pop("web_data_collection", None)
    with pytest.warns(DeprecationWarning, match="renamed to 'datascout'"):
        old = importlib.import_module("web_data_collection")
    assert old.retrieve_webpages is datascout.retrieve_webpages
    assert old.__all__ == datascout.__all__

    from web_data_collection.webpage_retrieval import retrieve_webpages_streaming

    assert retrieve_webpages_streaming is datascout.retrieve_webpages_streaming
    assert old.data_extraction is sys.modules["datascout.data_extraction"]


def test_public_api_is_exported() -> None:
    for name in datascout.__all__:
        assert hasattr(datascout, name), name
