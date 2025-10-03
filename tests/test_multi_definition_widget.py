from dataclasses import dataclass

from vocabsieve.models import Definition, DisplayMode
from vocabsieve.ui.multi_definition_widget import (
    LONG_QUERY_WORD_THRESHOLD,
    MultiDefinitionWidget,
    choose_sources_for_query,
)


@dataclass
class DummySource:
    name: str
    display_mode: DisplayMode = DisplayMode.plaintext
    INTERNET: bool = False

    def define(self, word: str, no_lemma: bool = False):
        raise NotImplementedError


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


def test_append_definition_updates_while_pending_sources(qapp):
    widget = MultiDefinitionWidget()
    sources = [
        DummySource("Fast", display_mode=DisplayMode.plaintext),
        DummySource("Slow", display_mode=DisplayMode.plaintext),
    ]
    widget.sources = sources
    widget._active_sources = sources
    widget.current_target = "hola"
    widget._pending_source_names = {source.name for source in sources}
    widget._source_results = {}

    widget.appendDefinition(
        "Fast",
        [Definition(headword="hola", lookup_term="hola", source="Fast", definition="hello")],
    )

    assert widget.definitions
    assert widget.currentDefinition is not None
    assert widget.currentDefinition.source == "Fast"
    assert widget.counter.text() == "1/1"
    assert widget._pending_source_names == {"Slow"}
    assert "hello" in widget.toPlainText()

    widget.appendDefinition("Slow", [])
    assert widget._pending_source_names == set()
    assert len(widget.definitions) == 1
    widget.deleteLater()
