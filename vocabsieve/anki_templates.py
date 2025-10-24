from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional

from .global_names import settings, logger

TEMPLATES_KEY = "anki/templates"
SELECTED_TEMPLATE_KEY = "anki/selected_template"
DEFAULT_TEMPLATE_NAME = "Default"
DISABLED_VALUE = "<disabled>"
ALLOWED_EMPTY_VALUE = ""


@dataclass(slots=True)
class AnkiTemplate:
    name: str
    deck: str
    note_type: str
    tags: list[str]
    word_field: str
    sentence_field: str
    definition1_field: str
    definition2_field: str
    audio_field: str
    image_field: str
    frequency_field: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "deck": self.deck,
            "note_type": self.note_type,
            "tags": list(self.tags),
            "word_field": self.word_field,
            "sentence_field": self.sentence_field,
            "definition1_field": self.definition1_field,
            "definition2_field": self.definition2_field,
            "audio_field": self.audio_field,
            "image_field": self.image_field,
            "frequency_field": self.frequency_field,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnkiTemplate":
        tags_value = data.get("tags", [])
        if isinstance(tags_value, str):
            tags_list = _split_tags(tags_value)
        elif isinstance(tags_value, Iterable):
            tags_list = [str(item) for item in tags_value if str(item)]
        else:
            tags_list = []
        return cls(
            name=str(data.get("name", DEFAULT_TEMPLATE_NAME)),
            deck=str(data.get("deck", "")),
            note_type=str(data.get("note_type", "")),
            tags=tags_list,
            word_field=str(data.get("word_field", "Word")),
            sentence_field=str(data.get("sentence_field", "Sentence")),
            definition1_field=str(data.get("definition1_field", "Definition")),
            definition2_field=str(data.get("definition2_field", DISABLED_VALUE)),
            audio_field=str(data.get("audio_field", DISABLED_VALUE)),
            image_field=str(data.get("image_field", DISABLED_VALUE)),
            frequency_field=str(data.get("frequency_field", DISABLED_VALUE)),
        )


def _split_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item for item in str(raw).split() if item]


def _read_templates_raw() -> list[dict]:
    stored = settings.value(TEMPLATES_KEY)
    if stored is None:
        return []
    if isinstance(stored, list):
        return [entry for entry in stored if isinstance(entry, dict)]
    if isinstance(stored, str):
        try:
            parsed = json.loads(stored)
        except json.JSONDecodeError as exc:
            logger.warning("Could not parse stored templates: %s", exc)
            return []
        if isinstance(parsed, list):
            return [entry for entry in parsed if isinstance(entry, dict)]
    return []


def _write_templates_raw(templates: list[dict]) -> None:
    settings.setValue(TEMPLATES_KEY, json.dumps(templates))


def _split_setting(key: str, default: str) -> str:
    value = settings.value(key, default)
    return str(value) if value is not None else default


def _build_default_template() -> AnkiTemplate:
    return AnkiTemplate(
        name=DEFAULT_TEMPLATE_NAME,
        deck=_split_setting("deck_name", "Default"),
        note_type=_split_setting("note_type", "vocabsieve-notes"),
        tags=_split_tags(_split_setting("tags", "vocabsieve")),
        word_field=_split_setting("word_field", "Word"),
        sentence_field=_split_setting("sentence_field", "Sentence"),
        definition1_field=_split_setting("definition1_field", "Definition"),
        definition2_field=_split_setting("definition2_field", DISABLED_VALUE),
        audio_field=_split_setting("pronunciation_field", DISABLED_VALUE),
        image_field=_split_setting("image_field", DISABLED_VALUE),
        frequency_field=_split_setting("frequency_field", DISABLED_VALUE),
    )


def load_templates() -> list[AnkiTemplate]:
    raw_templates = _read_templates_raw()
    templates: list[AnkiTemplate] = []
    for entry in raw_templates:
        try:
            templates.append(AnkiTemplate.from_dict(entry))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ignoring malformed template entry %s: %s", entry, exc)
    if not templates:
        default_template = _build_default_template()
        templates = [default_template]
        _write_templates_raw([default_template.to_dict()])
    return templates


def ensure_templates_initialized() -> list[AnkiTemplate]:
    return load_templates()


def list_templates() -> list[AnkiTemplate]:
    return load_templates()


def get_template(name: str) -> Optional[AnkiTemplate]:
    for template in load_templates():
        if template.name == name:
            return template
    return None


def save_templates(templates: list[AnkiTemplate]) -> None:
    _write_templates_raw([template.to_dict() for template in templates])


def get_current_template_name() -> str:
    templates = load_templates()
    stored = settings.value(SELECTED_TEMPLATE_KEY, type=str)
    if isinstance(stored, str):
        for template in templates:
            if template.name == stored:
                return stored
    selected = templates[0]
    settings.setValue(SELECTED_TEMPLATE_KEY, selected.name)
    return selected.name


def get_current_template() -> AnkiTemplate:
    name = get_current_template_name()
    template = get_template(name)
    if template is None:
        templates = load_templates()
        template = templates[0]
        settings.setValue(SELECTED_TEMPLATE_KEY, template.name)
    return template


def apply_template_to_settings(template: AnkiTemplate) -> None:
    settings.setValue("deck_name", template.deck)
    settings.setValue("note_type", template.note_type)
    settings.setValue("tags", " ".join(template.tags))
    settings.setValue("word_field", template.word_field)
    settings.setValue("sentence_field", template.sentence_field)
    settings.setValue("definition1_field", template.definition1_field)
    settings.setValue("definition2_field", template.definition2_field)
    settings.setValue("pronunciation_field", template.audio_field)
    settings.setValue("image_field", template.image_field)
    settings.setValue("frequency_field", template.frequency_field)


def normalize_field_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    if name in {DISABLED_VALUE, ALLOWED_EMPTY_VALUE}:
        return None
    return name


def set_current_template_name(name: str) -> None:
    template = get_template(name)
    if template is None:
        templates = load_templates()
        template = templates[0]
    settings.setValue(SELECTED_TEMPLATE_KEY, template.name)
    apply_template_to_settings(template)


def update_template(template: AnkiTemplate, previous_name: Optional[str] = None) -> None:
    templates = load_templates()
    updated_templates: list[AnkiTemplate] = []
    replaced = False
    for existing in templates:
        if previous_name and existing.name == previous_name and template.name != previous_name:
            continue
        if existing.name == template.name:
            updated_templates.append(template)
            replaced = True
        else:
            updated_templates.append(existing)
    if not replaced:
        updated_templates.append(template)
    save_templates(updated_templates)
    current_name = settings.value(SELECTED_TEMPLATE_KEY, type=str)
    if current_name in {previous_name, template.name, None, ""}:
        set_current_template_name(template.name)
    elif current_name not in {tpl.name for tpl in updated_templates}:
        set_current_template_name(updated_templates[0].name)


def delete_template(name: str) -> AnkiTemplate:
    templates = load_templates()
    remaining = [template for template in templates if template.name != name]
    if not remaining:
        remaining = [_build_default_template()]
    save_templates(remaining)
    set_current_template_name(remaining[0].name)
    return remaining[0]


def duplicate_template(source_name: str, new_name: str) -> Optional[AnkiTemplate]:
    source = get_template(source_name)
    if source is None:
        return None
    duplicate = AnkiTemplate(
        name=new_name,
        deck=source.deck,
        note_type=source.note_type,
        tags=list(source.tags),
        word_field=source.word_field,
        sentence_field=source.sentence_field,
        definition1_field=source.definition1_field,
        definition2_field=source.definition2_field,
        audio_field=source.audio_field,
        image_field=source.image_field,
        frequency_field=source.frequency_field,
    )
    update_template(duplicate, previous_name=None)
    return duplicate

