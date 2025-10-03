from dataclasses import dataclass

from vocabsieve.ui.multi_definition_widget import (
    LONG_QUERY_WORD_THRESHOLD,
    choose_sources_for_query,
)


@dataclass
class DummySource:
    name: str


def test_choose_sources_short_query_returns_all_sources():
    sources = [DummySource("Wiktionary (English)"), DummySource("Google Translate")]
    result = choose_sources_for_query(sources, "three word query")
    assert result == sources


def test_choose_sources_long_query_prefers_google_translate():
    sources = [
        DummySource("Wiktionary (English)"),
        DummySource("Google Translate"),
        DummySource("Custom Dict"),
    ]
    query = "one two three four five"
    result = choose_sources_for_query(sources, query)
    assert [source.name for source in result] == ["Google Translate"]


def test_choose_sources_long_query_without_google_uses_all_sources():
    sources = [DummySource("Wiktionary (English)"), DummySource("Custom Dict")]
    query = " ".join(["word"] * (LONG_QUERY_WORD_THRESHOLD + 1))
    result = choose_sources_for_query(sources, query)
    assert result == sources
