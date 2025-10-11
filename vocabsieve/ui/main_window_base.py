from PyQt5.QtWidgets import QMainWindow, QWidget, QGridLayout, QLabel, QPushButton, QCheckBox, \
    QStatusBar, QMenuBar, \
    QSizePolicy, QApplication, QLineEdit, QComboBox
from PyQt5.QtGui import QDesktopServices, QKeyEvent
from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QObject, QEvent
from .audio_selector import AudioSelector

from .multi_definition_widget import MultiDefinitionWidget
from .word_record_display import WordRecordDisplay

from ..global_names import app_title, settings, datapath, MOD, logger
from ..constants import langcodes

from ..record import Record
from ..local_dictionary import LocalDictionary
from ..dictionary import langs_supported
from .searchable_boldable_text_edit import SearchableBoldableTextEdit
from .freq_display_widget import FreqDisplayWidget
from .about import AboutDialog
from .logview import LogView
from ..models import AnkiSettings, WordActionWeights, KeyAction

import platform
import os
from sentence_splitter import SentenceSplitter, SentenceSplitterException


# If on macOS, display the modifier key as "Cmd", else display it as "Ctrl".
# For whatever reason, Qt automatically uses Cmd key when Ctrl is specified on Mac
# so there is no need to change the keybind, only the display text

class MainWindowBase(QMainWindow):
    audio_fetched = pyqtSignal(dict)
    target_language_changed = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(app_title(True))
        self.setFocusPolicy(Qt.StrongFocus)
        self.widget = QWidget()
        self.rec = Record(settings, datapath)
        lang_code = settings.value("target_language", "en") or "en"
        if not isinstance(lang_code, str):
            lang_code = str(lang_code)
        self._current_target_language = lang_code
        self._updating_target_language_combo = False
        try:
            self.splitter = SentenceSplitter(language=lang_code)
        except SentenceSplitterException:
            logger.error(
                "Sentence splitter failed to initialize for '%s'. Falling back to English splitter.",
                lang_code,
            )
            self.splitter = SentenceSplitter(language="en")
        self.setCentralWidget(self.widget)
        self.previousWord = ""
        self.audio_path = ""
        self.prev_clipboard = ""
        self.image_path = ""
        self.is_wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland"

        self.scaleFont()
        self.initWidgets()
        self.resize(int(550 / self.devicePixelRatioF()), int(900 / self.devicePixelRatioF()))
        self.setupWidgetsV()

        # Setup Key monitoring to monitor the shit key

        self.shift_pressed: bool = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.is_wayland and event.key() == Qt.Key.Key_Shift:
            self.shift_pressed = True
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if self.is_wayland and event.key() == Qt.Key.Key_Shift:
            self.shift_pressed = False
        else:
            super().keyReleaseEvent(event)

    def scaleFont(self) -> None:
        font = QApplication.font()
        font.setPointSize(
            int(font.pointSize() * settings.value("text_scale", type=int) / 100))
        QApplication.setFont(font)
        self.setFont(font)

    def initWidgets(self) -> None:
        self.namelabel = QLabel(
            "<h2 style=\"font-weight: normal;\">" + app_title(False) + "</h2>")
        self.menu = QMenuBar(self)
        self.sentence = SearchableBoldableTextEdit()
        self.sentence.setPlaceholderText(
            "Sentence copied to the clipboard will show up here.")
        self.sentence.setMinimumHeight(50)
        #self.sentence.setMaximumHeight(300)
        self.word = QLineEdit()
        self.word.setPlaceholderText("Word")
        self.target_language_combo = QComboBox()
        self.target_language_combo.setObjectName("targetLanguageCombo")
        self._populateTargetLanguageCombo()
        self.syncTargetLanguageCombo(apply=False)
        self.target_language_combo.currentIndexChanged.connect(self._onTargetLanguageIndexChanged)
        self.definition = MultiDefinitionWidget(self.word)
        self.definition.setMinimumHeight(70)
        #self.definition.setMaximumHeight(1800)
        self.definition2 = MultiDefinitionWidget()
        self.definition2.setMinimumHeight(70)
        #self.definition2.setMaximumHeight(1800)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText(
            "Tags to be used, separated by spaces")
        self.sentence.setToolTip(
            "Look up a word by double clicking it. Or, select it"
            ", then press \"Get definition\".")

        self.toanki_button = QPushButton(f"Add note [{MOD}+S]")
        self.view_last_note_button = QPushButton("View last note")
        self.view_last_note_button.setToolTip(f"View the last added note. [{MOD}+Shift+F]")

        self.read_button = QPushButton("Read clipboard")
        self.read_button.setToolTip(
            f"Read the clipboard contents to Sentence field [{MOD}+V]"
        )
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.stats_label = QLabel()

        self.single_word = QCheckBox("Single word lookups")
        self.single_word.setChecked(True)
        self.single_word.setToolTip(
            "If enabled, vocabsieve will act as a quick dictionary and look up any single words copied to the clipboard.\n"
            "This can potentially send your clipboard contents over the network if an online dictionary service is used.\n"
            "This is INSECURE if you use password managers that copy passwords to the clipboard.")
        self.lookup_definition_on_doubleclick = QCheckBox(
            "Lookup definition on double click")
        self.lookup_definition_on_doubleclick.setToolTip(
            f"Disable this if you want to use 3rd party dictionaries with copied text (e.g. with mpvacious).[{MOD}+2]")
        self.lookup_definition_on_doubleclick.clicked.connect(
            lambda v: settings.setValue("lookup_definition_on_doubleclick", v))
        self.lookup_definition_on_doubleclick.setChecked(
            settings.value("lookup_definition_on_doubleclick", True, type=bool))
        self.lookup_definition_when_hovering = QCheckBox("Lookup definition when hovering")
        self.lookup_definition_when_hovering.setToolTip("Hover over a word and press [Shift] to look its definition up")
        self.lookup_definition_when_hovering.clicked.connect(
            lambda v: settings.setValue("lookup_definition_when_hovering", v))
        self.lookup_definition_when_hovering.setChecked(
            settings.value("lookup_definition_when_hovering", True, type=bool))

        self.web_button = QPushButton(f"Open webpage")
        self.web_button.setToolTip(
            f"Open the webpage for the selected word. [{MOD}+1]")
        self.freq_widget = FreqDisplayWidget()
        self.freq_widget.setPlaceholderText("Word frequency")

        self.audio_selector = AudioSelector()

        self.definition.setReadOnly(
            not (
                settings.value(
                    "allow_editing",
                    True,
                    type=bool)))
        self.definition2.setReadOnly(
            not (
                settings.value(
                    "allow_editing",
                    True,
                    type=bool)))

        self.image_viewer = QLabel("<center><b>&lt;No image&gt;</center>")
        self.image_viewer.setScaledContents(True)
        self.image_viewer.setToolTip(f"{MOD}+W to clear the image.")
        self.image_viewer.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image_viewer.setStyleSheet(
            '''
                border: 1px solid black;
            '''
        )
        self.word_record_display = WordRecordDisplay()

    def setupWidgetsV(self) -> None:
        """Prepares vertical layout"""

        layout = QGridLayout(self.widget)
        layout.addWidget(self.namelabel, 0, 0, 1, 2)

        layout.addWidget(self.single_word, 1, 0, 1, 2)
        layout.addWidget(self.lookup_definition_on_doubleclick, 2, 0, 1, 2)
        layout.addWidget(self.lookup_definition_when_hovering, 3, 0, 1, 2)

        layout.addWidget(self.read_button, 4, 0)
        layout.addWidget(self.web_button, 4, 1)
        layout.addWidget(self.image_viewer, 0, 2, 6, 1)
        layout.addWidget(self.target_language_combo, 5, 0, 1, 2)
        layout.addWidget(self.sentence, 6, 0, 1, 3)
        layout.setRowStretch(6, 1)

        layout.setRowStretch(8, 2)
        layout.setRowStretch(10, 2)
        if settings.value("sg2_enabled", False, type=bool):
            layout.addWidget(self.definition, 8, 0, 2, 3)
            layout.addWidget(self.definition2, 10, 0, 2, 3)
        else:
            layout.addWidget(self.definition, 8, 0, 4, 3)

        layout.addWidget(self.word_record_display, 11, 2)

        layout.addWidget(self.audio_selector, 14, 0, 1, 3)
        layout.setRowStretch(14, 1)

        layout.addWidget(self.freq_widget, 15, 0)
        layout.addWidget(self.word, 15, 1, 1, 2)

        layout.addWidget(self.tags, 16, 0, 1, 3)

        layout.addWidget(self.view_last_note_button, 17, 0)
        layout.addWidget(self.toanki_button, 17, 1, 1, 2)

        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 5)
        self._layout = layout

    def _populateTargetLanguageCombo(self) -> None:
        self.target_language_combo.clear()
        options = sorted(langs_supported.items(), key=lambda item: item[1].lower())
        for code, name in options:
            self.target_language_combo.addItem(name, code)

    def syncTargetLanguageCombo(self, apply: bool = False) -> None:
        lang_code = settings.value("target_language", "en") or "en"
        self._updating_target_language_combo = True
        try:
            index = self.target_language_combo.findData(lang_code)
            if index < 0:
                index = self.target_language_combo.findData("en")
            if index < 0 and self.target_language_combo.count() > 0:
                index = 0
            if index >= 0:
                self.target_language_combo.setCurrentIndex(index)
        finally:
            self._updating_target_language_combo = False
        if apply:
            self._setTargetLanguage(lang_code, persist=False)

    def _onTargetLanguageIndexChanged(self, index: int) -> None:
        if self._updating_target_language_combo or index < 0:
            return
        code = self.target_language_combo.itemData(index)
        if not code:
            return
        self._setTargetLanguage(str(code), persist=True)

    def _setTargetLanguage(self, code: str, *, persist: bool, force: bool = False) -> None:
        if not code:
            code = "en"
        if not isinstance(code, str):
            code = str(code)
        if code not in langcodes:
            logger.warning("Unknown target language '%s', defaulting to English.", code)
            code = "en"
        previous = self._current_target_language
        if persist:
            if settings.value("target_language", "en") != code:
                settings.setValue("target_language", code)
                settings.sync()
        final_code = self._apply_sentence_splitter(code)
        if final_code != code:
            if settings.value("target_language", "en") != final_code:
                settings.setValue("target_language", final_code)
                settings.sync()
            self.syncTargetLanguageCombo(apply=False)
        if not force and previous == final_code:
            return
        if hasattr(self, "initSources"):
            self.initSources()
        self.target_language_changed.emit(final_code)

    def _apply_sentence_splitter(self, code: str) -> str:
        try:
            self.splitter = SentenceSplitter(language=code)
        except SentenceSplitterException:
            logger.error(
                "Sentence splitter failed for language '%s'. Falling back to English splitter only.",
                code,
            )
            self.splitter = SentenceSplitter(language="en")
        self._current_target_language = code
        return code

    def onHelp(self) -> None:
        url = f"https://docs.freelanguagetools.org/"
        QDesktopServices.openUrl(QUrl(url))

    def onAbout(self) -> None:
        self.about_dialog = AboutDialog()
        self.about_dialog.exec_()

    def onOpenLogs(self):
        self.logview = LogView()
        self.logview.exec_()

    def getAnkiSettings(self) -> AnkiSettings:
        return AnkiSettings(
            deck=settings.value("deck_name", "Default"),
            model=settings.value("note_type", "vocabsieve-notes"),
            word_field=settings.value("word_field", "Word"),
            sentence_field=settings.value("sentence_field", "Sentence"),
            definition1_field=settings.value("definition1_field", "Definition"),
            definition2_field=settings.value("definition2_field"),
            audio_field=settings.value("pronunciation_field"),
            image_field=settings.value("image_field"),
        )

    def getWordActionWeights(self) -> WordActionWeights:
        return WordActionWeights(
            seen=settings.value("tracking/w_seen", 8, type=int),
            lookup=settings.value("tracking/w_lookup", 15, type=int),
            anki_mature_ctx=settings.value("tracking/w_anki_ctx", 30, type=int),
            anki_mature_tgt=settings.value("tracking/w_anki_word", 70, type=int),
            anki_young_ctx=settings.value("tracking/w_anki_ctx_y", 20, type=int),
            anki_young_tgt=settings.value("tracking/w_anki_word_y", 40, type=int),
            threshold=settings.value("tracking/known_threshold", 100, type=int),
            threshold_cognate=settings.value("tracking/known_threshold_cognate", 25, type=int)
        )
