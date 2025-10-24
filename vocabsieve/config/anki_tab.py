from .base_tab import BaseTab
from PyQt5.QtWidgets import (
    QLabel,
    QFormLayout,
    QPushButton,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QInputDialog,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSlot
from typing import Optional

from ..anki_templates import (
    AnkiTemplateSpec,
    DEFAULT_TEMPLATE_NAME,
    active_template_name,
    apply_template,
    apply_template_by_name,
    delete_template,
    initialize_templates,
    load_templates,
    upsert_template,
)
from ..tools import addDefaultModel, getDeckList, getNoteTypes, getFields, getVersion
from ..global_names import settings, logger


class AnkiTab(BaseTab):
    def __init__(self):
        user_note_type = settings.value("note_type")
        super().__init__()
        if not user_note_type and not settings.value("internal/added_default_note_type"):
            try:
                self.onDefaultNoteType()
                settings.setValue("internal/added_default_note_type", True)
            except Exception:
                pass

    def initWidgets(self):
        self.enable_anki = QCheckBox("Enable sending notes to Anki")
        self.anki_api = QLineEdit()
        self.deck_name = QComboBox()
        self.tags = QLineEdit()
        self.note_type = QComboBox()
        self.sentence_field = QComboBox()

        self.word_field = QComboBox()
        self.frequency_field = QComboBox()
        self.definition1_field = QComboBox()
        self.definition2_field = QComboBox()
        self.pronunciation_field = QComboBox()
        self.image_field = QComboBox()
        self.default_notetype_button = QPushButton(
            "Use default note type ('vocabsieve-notes', will be created if it does not exist)")
        self.template_selector = QComboBox()
        self.template_apply_button = QPushButton("Load template")
        self.template_save_button = QPushButton("Save template")
        self.template_save_as_button = QPushButton("Save as new template")
        self.template_delete_button = QPushButton("Delete template")

    def setupWidgets(self):
        self.default_notetype_button.setToolTip(
            "This will use the default note type provided by VocabSieve. It will be created if it does not exist.")
        self.default_notetype_button.clicked.connect(self.onDefaultNoteType)
        initialize_templates()
        self.template_apply_button.clicked.connect(self.on_template_apply)
        self.template_save_button.clicked.connect(self.on_template_save)
        self.template_save_as_button.clicked.connect(self.on_template_save_as)
        self.template_delete_button.clicked.connect(self.on_template_delete)
        self.template_selector.currentTextChanged.connect(self.on_template_current_changed)
        self.refresh_templates()

    def loadDecks(self):
        logger.debug("Loading decks")
        api = self.anki_api.text()
        decks = getDeckList(api)
        logger.info(f"Decks: {decks}")
        self.deck_name.blockSignals(True)
        self.deck_name.clear()
        self.deck_name.addItems(decks)
        self.deck_name.setCurrentText(settings.value("deck_name"))
        self.deck_name.blockSignals(False)

        note_types = getNoteTypes(api)
        self.note_type.blockSignals(True)
        self.note_type.clear()
        self.note_type.addItems(note_types)
        self.note_type.setCurrentText(settings.value("note_type"))
        self.note_type.blockSignals(False)

    def loadFields(self):
        logger.debug("Loading fields")
        api = self.anki_api.text()

        current_type = self.note_type.currentText()
        if current_type == "":
            return

        fields = getFields(api, current_type)
        # Temporary store fields
        sent = self.sentence_field.currentText()
        word = self.word_field.currentText()
        freq_stars = self.frequency_field.currentText()
        def1 = self.definition1_field.currentText()
        def2 = self.definition2_field.currentText()
        pron = self.pronunciation_field.currentText()
        img = self.image_field.currentText()

        # Block signals temporarily to avoid warning dialogs
        self.sentence_field.blockSignals(True)
        self.word_field.blockSignals(True)
        self.frequency_field.blockSignals(True)
        self.definition1_field.blockSignals(True)
        self.definition2_field.blockSignals(True)
        self.pronunciation_field.blockSignals(True)
        self.image_field.blockSignals(True)

        self.sentence_field.clear()
        self.sentence_field.addItems(fields)

        self.word_field.clear()
        self.word_field.addItems(fields)

        self.frequency_field.clear()
        self.frequency_field.addItem("<disabled>")
        self.frequency_field.addItems(fields)

        self.definition1_field.clear()
        self.definition1_field.addItems(fields)

        self.definition2_field.clear()
        self.definition2_field.addItem("<disabled>")
        self.definition2_field.addItems(fields)

        self.pronunciation_field.clear()
        self.pronunciation_field.addItem("<disabled>")
        self.pronunciation_field.addItems(fields)

        self.image_field.clear()
        self.image_field.addItem("<disabled>")
        self.image_field.addItems(fields)

        self.sentence_field.setCurrentText(settings.value("sentence_field"))
        self.word_field.setCurrentText(settings.value("word_field"))
        self.frequency_field.setCurrentText(settings.value("frequency_field"))
        self.definition1_field.setCurrentText(settings.value("definition1_field"))
        self.definition2_field.setCurrentText(settings.value("definition2_field"))
        self.pronunciation_field.setCurrentText(settings.value("pronunciation_field"))
        self.image_field.setCurrentText(settings.value("image_field"))

        if self.sentence_field.findText(sent) != -1:
            self.sentence_field.setCurrentText(sent)
        if self.word_field.findText(word) != -1:
            self.word_field.setCurrentText(word)
        if self.frequency_field.findText(freq_stars) != -1:
            self.frequency_field.setCurrentText(freq_stars)
        if self.definition1_field.findText(def1) != -1:
            self.definition1_field.setCurrentText(def1)
        if self.definition2_field.findText(def2) != -1:
            self.definition2_field.setCurrentText(def2)
        if self.pronunciation_field.findText(pron) != -1:
            self.pronunciation_field.setCurrentText(pron)
        if self.image_field.findText(img) != -1:
            self.image_field.setCurrentText(img)

        self.sentence_field.blockSignals(False)
        self.word_field.blockSignals(False)
        self.frequency_field.blockSignals(False)
        self.definition1_field.blockSignals(False)
        self.definition2_field.blockSignals(False)
        self.pronunciation_field.blockSignals(False)
        self.image_field.blockSignals(False)
        logger.debug("Fields loaded")

    def onDefaultNoteType(self):
        try:
            addDefaultModel(settings.value("anki_api", 'http://127.0.0.1:8765'))
        except Exception as e:
            logger.error(e)
        self.loadDecks()
        self.loadFields()
        self.note_type.setCurrentText("vocabsieve-notes")
        self.sentence_field.setCurrentText("Sentence")
        self.word_field.setCurrentText("Word")
        self.definition1_field.setCurrentText("Definition")
        self.definition2_field.setCurrentText("Definition#2")
        self.pronunciation_field.setCurrentText("Pronunciation")
        self.image_field.setCurrentText("Image")

    def setupLayout(self):
        layout = QFormLayout(self)
        layout.addRow(QLabel("<h3>Anki settings</h3>"))
        layout.addRow(self.enable_anki)
        layout.addRow(
            QLabel("<i>◊ If disabled, notes will not be sent to Anki, but only stored in a local database.</i>")
        )
        layout.addRow(QLabel("<hr>"))
        layout.addRow(QLabel('AnkiConnect API'), self.anki_api)
        layout.addRow(QLabel("Deck name"), self.deck_name)
        layout.addRow(QLabel('Default tags'), self.tags)
        layout.addRow(QLabel("<hr>"))
        layout.addRow(QLabel("Templates"))
        layout.addRow(QLabel("Available templates"), self.template_selector)
        layout.addRow(self.template_apply_button, self.template_save_button)
        layout.addRow(self.template_save_as_button, self.template_delete_button)
        layout.addRow(QLabel("<hr>"))
        layout.addRow(self.default_notetype_button)
        layout.addRow(QLabel("Note type"), self.note_type)
        layout.addRow(
            QLabel('Field name for "Sentence"'),
            self.sentence_field)
        layout.addRow(
            QLabel('Field name for "Word"'),
            self.word_field)
        #layout.addRow(
        #    QLabel('Field name for "Frequency Stars"'),
        #    self.frequency_field)
        layout.addRow(
            QLabel('Field name for "Definition"'),
            self.definition1_field)
        layout.addRow(
            QLabel('Field name for "Definition#2"'),
            self.definition2_field)
        layout.addRow(
            QLabel('Field name for "Pronunciation"'),
            self.pronunciation_field)
        layout.addRow(
            QLabel('Field name for "Image"'),
            self.image_field)

    def toggle_anki_settings(self, value: bool):
        self.anki_api.setEnabled(value)
        self.tags.setEnabled(value)
        self.note_type.setEnabled(value)
        self.deck_name.setEnabled(value)
        self.sentence_field.setEnabled(value)
        self.word_field.setEnabled(value)
        self.frequency_field.setEnabled(value)
        self.definition1_field.setEnabled(value)
        self.definition2_field.setEnabled(value)
        self.pronunciation_field.setEnabled(value)
        self.image_field.setEnabled(value)
        # TODO: Implement these in the tracking tab # pylint: disable=fixme
        #self.anki_query_mature.setEnabled(value)
        #self.anki_query_young.setEnabled(value)
        #self.preview_mature_button.setEnabled(value)
        #self.preview_young_button.setEnabled(value)
        #self.open_fieldmatcher.setEnabled(value)

    def setupAutosave(self):
        self.register_config_handler(self.anki_api, 'anki_api', 'http://127.0.0.1:8765')
        self.register_config_handler(self.enable_anki, 'enable_anki', True)
        self.enable_anki.clicked.connect(self.toggle_anki_settings)
        self.toggle_anki_settings(self.enable_anki.isChecked())
        api = self.anki_api.text()
        try:
            _ = getVersion(api)
        except Exception:
            logger.warning("AnkiConnect API is not available, disabling Anki settings for now")
            self.toggle_anki_settings(False)
        else:
            self.loadDecks()
            self.loadFields()
            self.register_config_handler(
                self.deck_name, 'deck_name', 'Default')
            self.register_config_handler(self.tags, 'tags', 'vocabsieve')
            self.register_config_handler(self.note_type, 'note_type', 'vocabsieve-notes')
            self.register_config_handler(
                self.sentence_field, 'sentence_field', 'Sentence')
            self.register_config_handler(self.word_field, 'word_field', 'Word')
            self.register_config_handler(self.frequency_field, 'frequency_field', 'Frequency Stars')
            self.register_config_handler(
                self.definition1_field, 'definition1_field', 'Definition')
            self.register_config_handler(
                self.definition2_field,
                'definition2_field',
                '<disabled>')
            self.register_config_handler(
                self.pronunciation_field,
                'pronunciation_field',
                "<disabled>")
            self.register_config_handler(self.image_field, 'image_field', "<disabled>")

        self.note_type.currentTextChanged.connect(self.loadFields)

    def refresh_templates(self) -> None:
        templates = load_templates()
        active = active_template_name()
        self.template_selector.blockSignals(True)
        self.template_selector.clear()
        for template in templates:
            self.template_selector.addItem(template.name)
        index = self.template_selector.findText(active)
        if index >= 0:
            self.template_selector.setCurrentIndex(index)
        self.template_selector.blockSignals(False)
        self.on_template_current_changed(self.template_selector.currentText())

    def on_template_current_changed(self, name: str) -> None:
        allow_edit = bool(name) and name != DEFAULT_TEMPLATE_NAME
        self.template_save_button.setEnabled(allow_edit)
        self.template_delete_button.setEnabled(allow_edit)
        self.template_apply_button.setEnabled(bool(name))

    def on_template_apply(self) -> None:
        name = self.template_selector.currentText()
        if not name:
            return
        template = apply_template_by_name(name)
        if template is None:
            QMessageBox.warning(self, "Template missing", f"Template '{name}' is not available.")
            self.refresh_templates()
            return
        self.apply_template_to_widgets(template)
        logger.info(f"Applied Anki template '{template.name}' from settings tab")

    def on_template_save(self) -> None:
        name = self.template_selector.currentText()
        if not name:
            return
        if name == DEFAULT_TEMPLATE_NAME:
            QMessageBox.information(
                self,
                "Read-only template",
                "The default template cannot be overwritten. Use 'Save as new template' instead.",
            )
            return
        template = self.collect_current_template(name)
        upsert_template(template)
        if active_template_name() == name:
            apply_template(template)
        logger.info(f"Updated Anki template '{name}'")
        self.refresh_templates()

    def on_template_save_as(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save template", "Template name:")
        if not accepted:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid name", "Template name cannot be empty.")
            return
        template = self.collect_current_template(name)
        upsert_template(template)
        apply_template(template)
        self.refresh_templates()
        logger.info(f"Saved Anki template '{name}'")

    def on_template_delete(self) -> None:
        name = self.template_selector.currentText()
        if not name:
            return
        if name == DEFAULT_TEMPLATE_NAME:
            QMessageBox.information(
                self,
                "Read-only template",
                "The default template cannot be deleted.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Delete template",
            f"Are you sure you want to delete the template '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        if delete_template(name):
            logger.info(f"Deleted Anki template '{name}'")
        else:
            logger.warning(f"Could not delete Anki template '{name}'")
        self.refresh_templates()

    def collect_current_template(self, name: str) -> AnkiTemplateSpec:
        return AnkiTemplateSpec(
            name=name,
            deck_name=self.deck_name.currentText(),
            note_type=self.note_type.currentText(),
            word_field=self.word_field.currentText(),
            sentence_field=self.sentence_field.currentText(),
            definition1_field=self.definition1_field.currentText(),
            definition2_field=self.definition2_field.currentText(),
            pronunciation_field=self.pronunciation_field.currentText(),
            image_field=self.image_field.currentText(),
            frequency_field=self.frequency_field.currentText(),
            tags=self.tags.text().strip(),
        )

    def apply_template_to_widgets(self, template: AnkiTemplateSpec) -> None:
        self._set_combo_value(self.deck_name, template.deck_name)
        self._set_combo_value(self.note_type, template.note_type)
        try:
            self.loadFields()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Unable to refresh fields while applying template '{template.name}': {exc}")
        self._set_combo_value(self.word_field, template.word_field)
        self._set_combo_value(self.sentence_field, template.sentence_field)
        self._set_combo_value(self.definition1_field, template.definition1_field)
        self._set_combo_value(self.definition2_field, template.definition2_field)
        self._set_combo_value(self.pronunciation_field, template.pronunciation_field)
        self._set_combo_value(self.image_field, template.image_field)
        self._set_combo_value(self.frequency_field, template.frequency_field)
        self.tags.blockSignals(True)
        self.tags.setText(template.tags)
        self.tags.blockSignals(False)

    def _set_combo_value(self, combo: QComboBox, value: Optional[str]) -> None:
        if value is None:
            value = ""
        combo.blockSignals(True)
        if value and combo.findText(value) == -1:
            combo.addItem(value)
        combo.setCurrentText(value)
        combo.blockSignals(False)
