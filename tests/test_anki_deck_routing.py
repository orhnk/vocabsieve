from vocabsieve.models import AnkiSettings, SRSNote
from vocabsieve.tools import prepareAnkiNoteDict, get_deck_name_for_language


def _build_settings(deck: str = "Vocabsieve") -> AnkiSettings:
    return AnkiSettings(
        deck=deck,
        model="vocabsieve-notes",
        word_field="Word",
        sentence_field="Sentence",
        definition1_field="Definition",
        definition2_field="Definition 2",
        audio_field="Audio",
        image_field="Image",
        tags=None,
    )


def test_prepare_note_uses_language_subdeck_for_known_language():
    settings = _build_settings()
    note = SRSNote(word="Haus")

    payload = prepareAnkiNoteDict(settings, note, "de")

    assert payload["deckName"] == "Vocabsieve::German"


def test_prepare_note_uses_language_code_when_unknown():
    settings = _build_settings()
    note = SRSNote(word="saluton")

    payload = prepareAnkiNoteDict(settings, note, "xx")

    assert payload["deckName"] == "Vocabsieve::xx"


def test_prepare_note_uses_language_only_when_no_base_deck():
    settings = _build_settings(deck="")
    note = SRSNote(word="hola")

    payload = prepareAnkiNoteDict(settings, note, "es")

    assert payload["deckName"] == "Spanish"


def test_get_deck_name_for_language_falls_back_to_base_when_language_missing():
    settings = _build_settings()

    deck_name = get_deck_name_for_language(settings, None)

    assert deck_name == "Vocabsieve"
