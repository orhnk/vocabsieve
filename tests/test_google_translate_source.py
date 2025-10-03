from pathlib import Path
import importlib.util
import sys

import pytest

from vocabsieve.models import DisplayMode, LemmaPolicy, SourceOptions

_module_path = Path(__file__).resolve().parents[1] / "vocabsieve" / "sources" / "google_translate_source.py"
_spec = importlib.util.spec_from_file_location("vocabsieve.sources.google_translate_source", _module_path)
assert _spec is not None and _spec.loader is not None
google_translate_source = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = google_translate_source
_spec.loader.exec_module(google_translate_source)
GoogleTranslateSource = google_translate_source.GoogleTranslateSource


@pytest.fixture
def source_options() -> SourceOptions:
    return SourceOptions(
        lemma_policy=LemmaPolicy.no_lemma,
        display_mode=DisplayMode.raw,
        skip_top=0,
        collapse_newlines=0,
    )


def test_google_translate_fallback(monkeypatch: pytest.MonkeyPatch, source_options: SourceOptions) -> None:
    requested_urls: list[str] = []

    def fake_cached_get(url: str):
        requested_urls.append(url)
        if "lingva.lunar.icu" in url:
            raise RuntimeError("bad gateway")

        class Response:
            def json(self):
                return {"translation": "hola"}

        return Response()

    monkeypatch.setattr(google_translate_source, "cached_get", fake_cached_get)

    src = GoogleTranslateSource("en", source_options, "https://lingva.lunar.icu", "es")
    result = src._lookup("hello")

    assert result.definition == "hola"
    assert len(requested_urls) == 2
    assert "lingva.lunar.icu" in requested_urls[0]
    assert "lingva.ml" in requested_urls[1]
    assert src.gtrans_api == "https://lingva.ml"


def test_google_translate_normalizes_hebrew(monkeypatch: pytest.MonkeyPatch, source_options: SourceOptions) -> None:
    requested_urls: list[str] = []

    def fake_cached_get(url: str):
        requested_urls.append(url)

        class Response:
            def json(self):
                return {"translation": "shalom"}

        return Response()

    monkeypatch.setattr(google_translate_source, "cached_get", fake_cached_get)

    src = GoogleTranslateSource("he", source_options, "https://lingva.ml", "he")
    result = src._lookup("שלום")

    assert result.definition == "shalom"
    assert any("/iw/iw/" in url for url in requested_urls)
    assert src.langcode == "he"