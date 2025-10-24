import json
from dataclasses import dataclass
from typing import Any, Optional

from .global_names import settings, logger

TEMPLATE_KEY = "anki/templates"
ACTIVE_TEMPLATE_KEY = "anki/active_template"
DEFAULT_TEMPLATE_NAME = "Default"


@dataclass(frozen=True)
class AnkiTemplateSpec:
    name: str
    deck_name: str
    note_type: str
    word_field: str
    sentence_field: str
    definition1_field: str
    definition2_field: str
    pronunciation_field: str
    image_field: str
    frequency_field: str
    tags: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "deck_name": self.deck_name,
            "note_type": self.note_type,
            "word_field": self.word_field,
            "sentence_field": self.sentence_field,
            "definition1_field": self.definition1_field,
            "definition2_field": self.definition2_field,
            "pronunciation_field": self.pronunciation_field,
            "image_field": self.image_field,
            "frequency_field": self.frequency_field,
            "tags": self.tags,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AnkiTemplateSpec":
        return AnkiTemplateSpec(
            name=str(data.get("name", "")).strip(),
            deck_name=_coerce_str(data.get("deck_name")),
            note_type=_coerce_str(data.get("note_type")),
            word_field=_coerce_str(data.get("word_field")),
            sentence_field=_coerce_str(data.get("sentence_field")),
            definition1_field=_coerce_str(data.get("definition1_field")),
            definition2_field=_coerce_str(data.get("definition2_field")),
            pronunciation_field=_coerce_str(data.get("pronunciation_field")),
            image_field=_coerce_str(data.get("image_field")),
            frequency_field=_coerce_str(data.get("frequency_field")),
            tags=_coerce_str(data.get("tags")),
        )


DEFAULT_TEMPLATE = AnkiTemplateSpec(
    name=DEFAULT_TEMPLATE_NAME,
    deck_name="Default",
    note_type="vocabsieve-notes",
    word_field="Word",
    sentence_field="Sentence",
    definition1_field="Definition",
    definition2_field="Definition#2",
    pronunciation_field="Pronunciation",
    image_field="Image",
    frequency_field="Frequency Stars",
    tags="vocabsieve",
)


def initialize_templates() -> None:
    templates = load_templates(raw_only=True)
    if not templates:
        save_templates([DEFAULT_TEMPLATE])
        set_active_template(DEFAULT_TEMPLATE.name)
        return

    names = {tpl.name for tpl in templates}
    updated = False
    if DEFAULT_TEMPLATE_NAME not in names:
        templates.insert(0, DEFAULT_TEMPLATE)
        updated = True
    active = active_template_name()
    if not active or active not in names:
        set_active_template(templates[0].name)
    if updated:
        save_templates(templates)


def active_template_name() -> str:
    value = settings.value(ACTIVE_TEMPLATE_KEY, DEFAULT_TEMPLATE_NAME)
    if not value:
        return DEFAULT_TEMPLATE_NAME
    return str(value)


def set_active_template(name: str) -> None:
    settings.setValue(ACTIVE_TEMPLATE_KEY, name)
    settings.sync()


def load_templates(raw_only: bool = False) -> list[AnkiTemplateSpec]:
    raw_value = settings.value(TEMPLATE_KEY)
    templates: list[AnkiTemplateSpec] = []
    if isinstance(raw_value, str):
        try:
            data = json.loads(raw_value)
        except json.JSONDecodeError:
            logger.warning("Failed to decode Anki templates from settings; resetting to defaults")
            data = []
    else:
        data = []

    for entry in data:
        if isinstance(entry, dict):
            template = AnkiTemplateSpec.from_dict(entry)
            if template.name:
                templates.append(template)

    if not templates and not raw_only:
        templates = [DEFAULT_TEMPLATE]
        save_templates(templates)
        set_active_template(DEFAULT_TEMPLATE.name)
        return templates

    if not raw_only:
        names = {tpl.name for tpl in templates}
        if DEFAULT_TEMPLATE_NAME not in names:
            templates.insert(0, DEFAULT_TEMPLATE)
            save_templates(templates)
        if active_template_name() not in {tpl.name for tpl in templates}:
            set_active_template(templates[0].name)
    return templates


def save_templates(templates: list[AnkiTemplateSpec]) -> None:
    if not templates:
        templates = [DEFAULT_TEMPLATE]
    templates = _ensure_default_first(templates)
    serialized = [tpl.to_dict() for tpl in templates]
    settings.setValue(TEMPLATE_KEY, json.dumps(serialized))
    settings.sync()


def upsert_template(template: AnkiTemplateSpec) -> None:
    templates = load_templates(raw_only=True)
    replaced = False
    for idx, existing in enumerate(templates):
        if existing.name == template.name:
            templates[idx] = template
            replaced = True
            break
    if not replaced:
        templates.append(template)
    templates = _ensure_default_first(templates)
    save_templates(templates)


def delete_template(name: str) -> bool:
    if name == DEFAULT_TEMPLATE_NAME:
        return False
    templates = load_templates(raw_only=True)
    filtered = [tpl for tpl in templates if tpl.name != name]
    if len(filtered) == len(templates):
        return False
    save_templates(filtered)
    if active_template_name() == name:
        set_active_template(filtered[0].name if filtered else DEFAULT_TEMPLATE_NAME)
    return True


def get_template(name: str) -> Optional[AnkiTemplateSpec]:
    for template in load_templates():
        if template.name == name:
            return template
    return None


def apply_template(template: AnkiTemplateSpec) -> None:
    settings.setValue("deck_name", template.deck_name)
    settings.setValue("note_type", template.note_type)
    settings.setValue("word_field", template.word_field)
    settings.setValue("sentence_field", template.sentence_field)
    settings.setValue("definition1_field", template.definition1_field)
    settings.setValue("definition2_field", template.definition2_field)
    settings.setValue("pronunciation_field", template.pronunciation_field)
    settings.setValue("image_field", template.image_field)
    settings.setValue("frequency_field", template.frequency_field)
    settings.setValue("tags", template.tags)
    set_active_template(template.name)
    settings.sync()


def apply_template_by_name(name: str) -> Optional[AnkiTemplateSpec]:
    template = get_template(name)
    if template is None:
        logger.warning(f"Requested Anki template '{name}' does not exist")
        return None
    apply_template(template)
    return template


def _ensure_default_first(templates: list[AnkiTemplateSpec]) -> list[AnkiTemplateSpec]:
    default_entries = [tpl for tpl in templates if tpl.name == DEFAULT_TEMPLATE_NAME]
    others = [tpl for tpl in templates if tpl.name != DEFAULT_TEMPLATE_NAME]
    ordered = []
    if default_entries:
        ordered.append(default_entries[0])
    else:
        ordered.append(DEFAULT_TEMPLATE)
    existing_names = {ordered[0].name}
    for tpl in others:
        if tpl.name not in existing_names:
            ordered.append(tpl)
            existing_names.add(tpl.name)
    return ordered


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
