from .base_tab import BaseTab
from PyQt5.QtWidgets import (
    QLabel,
    QFormLayout,
    QPushButton,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QHBoxLayout,
    QWidget,
    QMessageBox,
    QInputDialog,
)
from contextlib import contextmanager
from typing import Optional

from ..tools import addDefaultModel, getDeckList, getNoteTypes, getFields, getVersion
from ..global_names import settings, logger
from ..anki_templates import (
    ensure_templates_initialized,
    list_templates,
    get_current_template,
    get_template,
    update_template,
    delete_template,
    set_current_template_name,
    duplicate_template,
    AnkiTemplate,
)


class AnkiTab(BaseTab):
    def __init__(self):
        ensure_templates_initialized()
        self._loading_template = False
        self.current_template: AnkiTemplate = get_current_template()
        self._last_template_name: str = self.current_template.name
        user_note_type = self.current_template.note_type
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
        self.template_selector = QComboBox()
        self.template_selector.setObjectName("templateSelector")
        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("Template name")
        self.template_new_button = QPushButton("New template")
        self.template_save_button = QPushButton("Save template")
        self.template_delete_button = QPushButton("Delete template")
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

    def setupWidgets(self):
        self.default_notetype_button.setToolTip(
            "This will use the default note type provided by VocabSieve. It will be created if it does not exist.")
        self.default_notetype_button.clicked.connect(self.onDefaultNoteType)
        self.template_new_button.clicked.connect(self.on_template_new_clicked)
        self.template_save_button.clicked.connect(self.on_template_save_clicked)
        self.template_delete_button.clicked.connect(self.on_template_delete_clicked)
        self.template_selector.currentIndexChanged.connect(self.on_template_selected)
        self.refresh_template_selector()

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
        layout.addRow(QLabel("<h4>Templates</h4>"))
        layout.addRow(QLabel("Template"), self.template_selector)
        layout.addRow(QLabel("Template name"), self.template_name_edit)
        template_buttons = QWidget()
        button_layout = QHBoxLayout(template_buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(self.template_new_button)
        button_layout.addWidget(self.template_save_button)
        button_layout.addWidget(self.template_delete_button)
        layout.addRow(template_buttons)
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
        self.template_selector.setEnabled(value)
        self.template_name_edit.setEnabled(value)
        self.template_new_button.setEnabled(value)
        self.template_save_button.setEnabled(value)
        self.template_delete_button.setEnabled(value and self.template_selector.count() > 1)
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
        self.apply_template_to_controls(self.current_template)

    @contextmanager
    def _block_template_updates(self):
        previous = self._loading_template
        self._loading_template = True
        try:
            yield
        finally:
            self._loading_template = previous

    def refresh_template_selector(self, select_name: Optional[str] = None) -> None:
        templates = list_templates()
        if not templates:
            return
        if select_name is None:
            select_name = self.current_template.name if self.current_template else templates[0].name
        matching = next((tpl for tpl in templates if tpl.name == select_name), templates[0])
        with self._block_template_updates():
            self.template_selector.blockSignals(True)
            self.template_selector.clear()
            for template in templates:
                self.template_selector.addItem(template.name)
            if self.template_selector.findText(matching.name) == -1:
                self.template_selector.addItem(matching.name)
            self.template_selector.setCurrentText(matching.name)
            self.template_selector.blockSignals(False)
            self.template_name_edit.setText(matching.name)
        self.template_delete_button.setEnabled(len(templates) > 1 and self.template_save_button.isEnabled())
        self.template_new_button.setEnabled(self.enable_anki.isChecked())
        self.current_template = matching
        self._last_template_name = matching.name

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        if value is None:
            return
        text = value.strip()
        if text == "":
            return
        index = combo.findText(text)
        if index == -1:
            combo.addItem(text)
            index = combo.findText(text)
        combo.setCurrentIndex(index)

    def _collect_template_from_controls(self, name: str) -> AnkiTemplate:
        tags_text = self.tags.text().strip()
        tags_list = [tag for tag in tags_text.split() if tag]
        return AnkiTemplate(
            name=name,
            deck=self.deck_name.currentText().strip(),
            note_type=self.note_type.currentText().strip(),
            tags=tags_list,
            word_field=self.word_field.currentText().strip(),
            sentence_field=self.sentence_field.currentText().strip(),
            definition1_field=self.definition1_field.currentText().strip(),
            definition2_field=self.definition2_field.currentText().strip(),
            audio_field=self.pronunciation_field.currentText().strip(),
            image_field=self.image_field.currentText().strip(),
            frequency_field=self.frequency_field.currentText().strip(),
        )

    def apply_template_to_controls(self, template: AnkiTemplate) -> None:
        with self._block_template_updates():
            self.template_name_edit.setText(template.name)
            tags_text = " ".join(template.tags)
            if self.tags.text() != tags_text:
                self.tags.setText(tags_text)
            note_changed = self.note_type.currentText() != template.note_type
            self._set_combo_value(self.deck_name, template.deck)
            self._set_combo_value(self.note_type, template.note_type)
        if note_changed and self.enable_anki.isChecked():
            try:
                self.loadFields()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unable to load Anki fields for template %s: %s", template.name, exc)
        with self._block_template_updates():
            self._set_combo_value(self.word_field, template.word_field)
            self._set_combo_value(self.sentence_field, template.sentence_field)
            self._set_combo_value(self.definition1_field, template.definition1_field)
            self._set_combo_value(self.definition2_field, template.definition2_field)
            self._set_combo_value(self.pronunciation_field, template.audio_field)
            self._set_combo_value(self.image_field, template.image_field)
            self._set_combo_value(self.frequency_field, template.frequency_field)
        set_current_template_name(template.name)
        self.current_template = template
        self._last_template_name = template.name

    def on_template_selected(self, index: int) -> None:
        if self._loading_template:
            return
        if index < 0:
            name = self.template_selector.currentText().strip()
        else:
            name = self.template_selector.itemText(index).strip()
        if not name:
            return
        template = get_template(name)
        if template is None:
            return
        self.apply_template_to_controls(template)
        self.refresh_template_selector(select_name=template.name)

    def on_template_save_clicked(self) -> None:
        name = self.template_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Template name required", "Please enter a name before saving the template.")
            return
        existing = get_template(name)
        if existing and name != self._last_template_name:
            reply = QMessageBox.question(
                self,
                "Overwrite template?",
                f'A template named "{name}" already exists. Overwrite it?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        template = self._collect_template_from_controls(name)
        previous_name = None if name == self._last_template_name else self._last_template_name
        update_template(template, previous_name=previous_name)
        self.current_template = template
        self._last_template_name = template.name
        self.refresh_template_selector(select_name=template.name)
        set_current_template_name(template.name)

    def _suggest_new_template_name(self, base: str) -> str:
        existing = {tpl.name for tpl in list_templates()}
        seed = base.strip() or "Template"
        if seed not in existing:
            return seed
        suffix = 1
        while True:
            candidate = f"{seed} ({suffix})"
            if candidate not in existing:
                return candidate
            suffix += 1

    def on_template_new_clicked(self) -> None:
        current_name = self.template_selector.currentText().strip()
        suggestion = self._suggest_new_template_name(f"{current_name} copy" if current_name else "Template")
        name, ok = QInputDialog.getText(
            self,
            "Create new template",
            "New template name:",
            QLineEdit.Normal,
            suggestion,
        )
        if not ok:
            return
        new_name = name.strip()
        if not new_name:
            QMessageBox.warning(self, "Template name required", "Please provide a name for the new template.")
            return
        if get_template(new_name) is not None:
            QMessageBox.warning(
                self,
                "Template exists",
                f'A template named "{new_name}" already exists. Please choose a different name.',
            )
            return
        duplicated = duplicate_template(current_name, new_name) if current_name else None
        if duplicated is None:
            duplicated = self._collect_template_from_controls(new_name)
            update_template(duplicated, previous_name=None)
        self.current_template = duplicated
        self._last_template_name = duplicated.name
        self.refresh_template_selector(select_name=duplicated.name)
        self.apply_template_to_controls(duplicated)

    def on_template_delete_clicked(self) -> None:
        if self.template_selector.count() <= 1:
            QMessageBox.information(self, "Cannot delete", "At least one template must remain.")
            return
        name = self.template_selector.currentText().strip()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete template?",
            f'Are you sure you want to delete the template "{name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        next_template = delete_template(name)
        self.refresh_template_selector(select_name=next_template.name)
        self.apply_template_to_controls(next_template)
