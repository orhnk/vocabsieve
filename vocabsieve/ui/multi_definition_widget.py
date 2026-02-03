from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject, pyqtSlot, QTimer

from .searchable_text_edit import SearchableTextEdit
from ..models import Definition, DisplayMode, DictionarySource
from ..tools import process_defi_anki, apply_word_rules
from loguru import logger
from typing import Optional
import concurrent.futures
import time
from ..global_names import MOD


DEFAULT_PLACEHOLDER_TEXT = f"Look up a word by double clicking it or by selecting it, then pressing {MOD}+D.\nUse Shift-{MOD}+D to look up the word without lemmatization."
NEXT_DEFINITION_SCROLL_COUNT_TRANSITION_THRESHOLD = 3
LONG_QUERY_WORD_THRESHOLD = 4


def choose_sources_for_query(sources: list[DictionarySource], query: str) -> list[DictionarySource]:
    """Return the preferred sources for a lookup query."""
    tokens = [token for token in query.split() if token]
    if len(tokens) > LONG_QUERY_WORD_THRESHOLD:
        for source in sources:
            if source.name == "Google Translate":
                return [source]
    return sources


def sign(number):
    if number > 0:
        return 1
    elif number < 0:
        return -1
    else:
        return 0


class ButtonsBoxWidget(QWidget):
    scrolled = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.scrolled_amount = 0

    def wheelEvent(self, event: QWheelEvent):
        if sign(event.angleDelta().y()) != sign(self.scrolled_amount):
            self.scrolled_amount = 0
        self.scrolled_amount += event.angleDelta().y()
        if self.scrolled_amount >= 120:
            self.scrolled.emit(-1)  # Scroll up = prev
            self.scrolled_amount = 0

        elif self.scrolled_amount <= -120:
            self.scrolled.emit(1)  # Scroll down = next
            self.scrolled_amount = 0
        event.accept()


class LookupWorker(QObject):
    # emit token, source_name, definitions
    got_definitions = pyqtSignal(int, str, object)
    finished = pyqtSignal(int)

    def __init__(self, source: DictionarySource, word: str, no_lemma: bool, rules: list[tuple[str, str]], token: int = 0):
        super().__init__()
        self.source = source
        self.word = word
        self.no_lemma = no_lemma
        self.rules = rules
        self.token = token

    def run(self):
        start = time.time()
        if QThread.currentThread().isInterruptionRequested():
            self.finished.emit(self.token)
            return
        try:
            definitions = self.source.define(self.word, no_lemma=self.no_lemma)
        except Exception as exc:  # Protect the UI thread from exceptions in sources
            logger.exception(f"LookupWorker: exception while looking up {self.word} in {self.source.name}: {exc}")
            definitions = []
        any_definitions = any(defi.definition is not None for defi in definitions)
        if not any_definitions and self.rules:
            logger.info(f"No definitions found for {self.word} in {self.source.name}, applying word rules")
            definitions = self.source.define(
                apply_word_rules(self.word, self.rules),
                no_lemma=self.no_lemma
            )
        if QThread.currentThread().isInterruptionRequested():
            self.finished.emit(self.token)
            return
        self.got_definitions.emit(self.token, self.source.name, definitions)
        logger.debug(f"LookupWorker: looked up {self.word} in {self.source.name} in {time.time()-start:.2f} seconds (token {self.token})")
        self.finished.emit(self.token)


class LocalLookupWorker(QObject):
    """Worker that performs local source lookups sequentially in a dedicated thread.

    Using a single worker avoids concurrent access to native/disk-backed local
    dictionary resources that may not be thread-safe and can cause crashes.
    """
    # emit token, source_name, definitions
    got_definitions = pyqtSignal(int, str, object)

    def __init__(self):
        super().__init__()

    @pyqtSlot(int, object, str, bool, object)
    def do_lookup(self, token, source, word, no_lemma, rules):
        try:
            definitions = source.define(word, no_lemma=no_lemma)
        except Exception as exc:
            logger.exception(f"LocalLookupWorker: exception while looking up {word} in {getattr(source, 'name', '?')}: {exc}")
            definitions = []
        any_definitions = any(getattr(d, 'definition', None) is not None for d in definitions)
        if not any_definitions and rules:
            try:
                alt = apply_word_rules(word, rules)
                definitions = source.define(alt, no_lemma=no_lemma)
            except Exception:
                pass
        self.got_definitions.emit(token, getattr(source, 'name', ''), definitions)


class MultiDefinitionWidget(SearchableTextEdit):
    nextDefinitionScrollTransitionCounter = 0
    _local_lookup_signal = pyqtSignal(int, object, str, bool, object)

    def __init__(self, word_widget: Optional[QLineEdit] = None):
        super().__init__()
        # token increments on each lookup; used to ignore stale results
        self._lookup_token = 0
        self.sources: list[DictionarySource] = []
        self._active_sources: list[DictionarySource] = []
        self.word_widget = word_widget
        self.current_target: str = ""
        self._layout = QVBoxLayout(self)
        self.definitions: list[Definition] = []
        self.currentIndex = 0
        self.currentDefinition: Optional[Definition] = None
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self._layout.setAlignment(Qt.AlignBottom)
        buttons_box_widget = ButtonsBoxWidget(self)
        self._layout.addWidget(buttons_box_widget)
        buttons_box_layout = QHBoxLayout(buttons_box_widget)
        buttons_box_widget.scrolled.connect(self.move_)

        prev_button = QPushButton("<")
        prev_button.setFocusPolicy(Qt.NoFocus)
        self.counter = QLabel("0/0")
        self.counter.setAlignment(Qt.AlignCenter)
        next_button = QPushButton(">")
        next_button.setFocusPolicy(Qt.NoFocus)
        buttons_box_layout.addWidget(prev_button)
        buttons_box_layout.addWidget(next_button)
        buttons_box_layout.addWidget(self.counter)
        buttons_box_layout.addWidget(self.info_label)
        prev_button.clicked.connect(self.back)
        next_button.clicked.connect(self.forward)

        self.threads = []
        self.workers = []
        self._worker_threads: dict[int, QThread] = {}
        self._thread_workers: dict[int, LookupWorker] = {}
        self._source_results = {}
        self._pending_source_names = set()
        # Dedicated single-thread worker for local (disk/native) sources
        self._local_thread = QThread()
        self._local_worker = LocalLookupWorker()
        self._local_worker.moveToThread(self._local_thread)
        # connect signal to perform lookups on the local worker in its thread
        self._local_lookup_signal.connect(self._local_worker.do_lookup)
        self._local_worker.got_definitions.connect(self.appendDefinition)
        self._local_thread.start()
        # Thread pool for internet lookups to avoid creating many short-lived
        # QThreads, which is expensive. Use a modest number of workers.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        # Simple in-memory cache for recent lookups: maps query -> {source_name: definitions}
        # This allows instant display for repeated lookups and then refreshes in background.
        self._cache = {}

    def wheelEvent(self, event):
        if len(self.sources) > 1:
            if self.verticalScrollBar().value() == self.verticalScrollBar().minimum() and event.angleDelta().y() > 0:
                self.nextDefinitionScrollTransitionCounter += 1
                if self.nextDefinitionScrollTransitionCounter > NEXT_DEFINITION_SCROLL_COUNT_TRANSITION_THRESHOLD:
                    self.back()
                    return

            elif self.verticalScrollBar().value() == self.verticalScrollBar().maximum() and event.angleDelta().y() < 0:
                self.nextDefinitionScrollTransitionCounter += 1
                if self.nextDefinitionScrollTransitionCounter > NEXT_DEFINITION_SCROLL_COUNT_TRANSITION_THRESHOLD:
                    self.forward()
                    return

            else:
                self.nextDefinitionScrollTransitionCounter = 0

        super().wheelEvent(event)

    def setSourceGroup(self, sources: list[DictionarySource]):
        self.sources = sources
        if not self.sources:
            self.setPlaceholderText(
                "Hint: No sources are set, so no lookups can be performed. Go to Configure -> Sources to add some sources.")
        else:
            self.setPlaceholderText(DEFAULT_PLACEHOLDER_TEXT)

    def lookup(self, word: str, no_lemma: bool, rules: list[tuple[str, str]]):
        self.reset()
        self.current_target = word
        self._active_sources = choose_sources_for_query(self.sources, word)
        if len(self._active_sources) < len(self.sources):
            logger.debug("Long query detected; using Google Translate only")
        logger.debug(f"Looking up {word} in {self._active_sources}")
        self._pending_source_names = {source.name for source in self._active_sources}
        self._source_results = {}
        # If we have cached results for this query, show them immediately
        cached = self._cache.get(word)
        if cached:
            # shallow copy cached results into _source_results so UI can use them
            self._source_results = {k: list(v) for k, v in cached.items()}
            # determine which sources still need fresh results
            self._pending_source_names = {s.name for s in self._active_sources} - set(self._source_results.keys())
            # populate with cached results (may be final if nothing pending)
            self.populateDefinitions(final=(not self._pending_source_names))
        if self._active_sources:
            self.setPlaceholderText(f"Looking up \"{word}\"...")
        # bump token so previous results are ignored
        self._lookup_token += 1
        token = self._lookup_token
        for source in self._active_sources:
            self._lookup_in_source(source, word, no_lemma=no_lemma, rules=rules, token=token)

    def _lookup_in_source(self, source: DictionarySource, word: str,
                          no_lemma: bool, rules: list[tuple[str, str]], token: int = 0) -> None:
        # Run internet sources in their own threads to parallelize network I/O.
        # Run local sources via the dedicated local worker to avoid concurrent
        # access to potentially non-thread-safe native/disk-backed resources.
        if source.INTERNET:
            # Submit internet-based lookup to shared thread pool. When the
            # future completes, schedule appendDefinition to run on the Qt
            # main thread via QTimer.singleShot(0,...).
            def task():
                try:
                    definitions = source.define(word, no_lemma=no_lemma)
                except Exception as exc:
                    logger.exception(f"Executor lookup: exception while looking up {word} in {getattr(source,'name','?')}: {exc}")
                    definitions = []
                return definitions

            future = self._executor.submit(task)

            def _on_done(fut, src_name=source.name, tok=token):
                try:
                    definitions = fut.result()
                except Exception:
                    definitions = []
                # schedule appendDefinition on the main thread
                QTimer.singleShot(0, lambda: self.appendDefinition(tok, src_name, definitions))

            future.add_done_callback(_on_done)
        else:
            # delegate to the single-threaded local worker via a queued signal
            try:
                self._local_lookup_signal.emit(token, source, word, no_lemma, rules)
            except Exception:
                # Fallback: run inline if signalling fails
                self.appendDefinition(token, source.name, source.define(word, no_lemma=no_lemma))

    def _cleanup_thread(self, thread: QThread | None) -> None:
        if thread is None:
            return
        worker = self._thread_workers.pop(id(thread), None)
        if worker is not None:
            self._worker_threads.pop(id(worker), None)
            try:
                self.workers.remove(worker)
            except ValueError:
                pass
        try:
            self.threads.remove(thread)
        except ValueError:
            pass
        # If local thread is stopping as part of cleanup, make sure to keep it running until explicit close

    @pyqtSlot(int, str, object)
    def appendDefinition(self, token: int, source_name: str, definitions_obj):
        # Ignore results from previous lookups
        if token != getattr(self, '_lookup_token', 0):
            logger.debug(f"Ignoring stale definition result for token {token} (current {getattr(self, '_lookup_token', 0)})")
            return
        if isinstance(definitions_obj, list):
            definitions = list(definitions_obj)
        elif definitions_obj is None:
            definitions = []
        elif isinstance(definitions_obj, Definition):
            definitions = [definitions_obj]
        else:
            try:
                definitions = list(definitions_obj)
            except TypeError:
                definitions = []
        self._source_results[source_name] = definitions
        self._pending_source_names.discard(source_name)
        is_final = not self._pending_source_names
        # If final results for a token, update cache for this target
        if is_final and getattr(self, 'current_target', None):
            try:
                # store shallow copy of the dict to avoid mutation races
                self._cache[self.current_target] = {k: list(v) for k, v in self._source_results.items()}
            except Exception:
                pass
        self.populateDefinitions(final=is_final)

    def populateDefinitions(self, final: bool = False):
        """Aggregate definitions we have so far and update the display."""
        if not self._active_sources:
            return

        aggregated: list[Definition] = []
        for source in self._active_sources:
            items = self._source_results.get(source.name)
            if not items:
                continue
            aggregated.extend(items)

        filtered = [defi for defi in aggregated if defi.definition is not None]

        previous_definition = self.currentDefinition
        previous_count = len(self.definitions)

        self.definitions = filtered

        if self.definitions:
            if previous_definition and previous_definition in self.definitions:
                self.currentIndex = self.definitions.index(previous_definition)
            elif previous_count == 0:
                self.currentIndex = 0
            else:
                self.currentIndex = min(self.currentIndex, len(self.definitions) - 1)
            self.setPlaceholderText(DEFAULT_PLACEHOLDER_TEXT)
            self.updateIndex()
        elif final:
            self.currentDefinition = None
            self.currentIndex = 0
            self.setText("")
            self.info_label.setText("")
            self.counter.setText("0/0")
            if self.word_widget:
                self.word_widget.setText(self.current_target)
            self.setPlaceholderText("No definitions found for \"" + self.current_target
                                    + "\". You can still type in a definition manually to add to Anki.")


    def getFirstDefinition(self, target) -> Optional[Definition]:
        """
        Blocking function to get the first definition from all sources
        For use outside of the main interface
        """
        for source in self.sources:
            logger.debug("Getting definition from source " + source.name)
            for defi in source.define(target):
                logger.debug("Got definition from source " + defi.source + ": " + str(defi))
                if defi.definition is not None:
                    return defi
        return None

    def updateIndex(self):
        if not self.definitions:
            return
        self.counter.setText(f"{self.currentIndex+1}/{len(self.definitions)}")
        if defi := self.definitions[self.currentIndex]:
            self.setCurrentDefinition(defi)

    def setCurrentDefinition(self, defi: Definition):
        self.currentDefinition = defi
        source_name = defi.source
        source = self.getSource(source_name)
        if defi.definition is not None and source is not None:
            match source.display_mode:
                case DisplayMode.markdown_html | DisplayMode.html:
                    self.setHtml(defi.definition)
                case _:
                    self.setText(defi.definition)
            self.info_label.setText(f"<strong>{defi.headword}</strong> in <em>{defi.source}</em>")
            if self.word_widget:
                self.word_widget.setText(defi.headword)

    def setCurrentIndex(self, index: int):
        self.currentIndex = index
        self.updateIndex()

    def move_(self, amount: int):
        if amount > 0:
            for _ in range(amount):
                self.forward()
        else:
            for _ in range(-amount):
                self.back()

    def back(self):
        self.nextDefinitionScrollTransitionCounter = 0
        if self.currentIndex > 0:
            self.setCurrentIndex(self.currentIndex - 1)
        else:  # wrap around
            self.setCurrentIndex(len(self.definitions) - 1)

    def forward(self):
        self.nextDefinitionScrollTransitionCounter = 0
        if self.currentIndex < len(self.definitions) - 1:
            self.setCurrentIndex(self.currentIndex + 1)
        else:  # wrap around
            self.setCurrentIndex(0)

    def first(self):
        if self.definitions:
            self.setCurrentIndex(0)

    def last(self):
        if self.definitions:
            self.setCurrentIndex(len(self.definitions) - 1)

    def reset(self):
        self._stop_all_threads()
        self.definitions = []
        self.currentDefinition = None
        self.currentIndex = 0
        self.setText("")
        self.info_label.setText("")
        self.counter.setText("0/0")
        self._active_sources = []
        self._source_results = {}
        self._pending_source_names = set()
        # TODO try to remove references to threads and workers without crashing # pylint: disable=fixme
        self._worker_threads.clear()
        self._thread_workers.clear()

    def getSource(self, source_name: str) -> Optional[DictionarySource]:
        for source in self.sources:
            if source.name == source_name:
                return source
        return None

    def _stop_all_threads(self):
        if not self.threads:
            return
        active_threads = list(self.threads)
        active_workers = list(self.workers)
        for worker in active_workers:
            try:
                worker.got_definitions.disconnect(self.appendDefinition)
            except (TypeError, RuntimeError):
                pass
            thread = self._worker_threads.get(id(worker))
            if isinstance(thread, QThread):
                # request interruption but do not block waiting for thread exit
                thread.requestInterruption()
                try:
                    thread.quit()
                except Exception:
                    pass
        for thread in active_threads:
            # request interruption and request thread to quit; non-blocking
            try:
                thread.requestInterruption()
                thread.quit()
            except Exception:
                pass
            worker = self._thread_workers.get(id(thread))
            if isinstance(worker, LookupWorker):
                try:
                    worker.got_definitions.disconnect(self.appendDefinition)
                except Exception:
                    pass
                # schedule deletion when thread finishes (thread.finished handlers will cleanup)
            self._cleanup_thread(thread)
        self.threads = [thread for thread in self.threads if thread.isRunning()]
        pruned_workers = []
        for worker in self.workers:
            thread = self._worker_threads.get(id(worker))
            if isinstance(thread, QThread) and thread.isRunning():
                pruned_workers.append(worker)
        self.workers = pruned_workers
        # Stop local worker thread if present
        try:
            if hasattr(self, '_local_thread') and isinstance(self._local_thread, QThread):
                if self._local_thread.isRunning():
                    # request non-blocking quit for local worker thread
                    try:
                        self._local_thread.quit()
                    except Exception:
                        pass
        except Exception:
            pass
        # Shutdown executor used for internet lookups
        try:
            if hasattr(self, '_executor'):
                self._executor.shutdown(wait=False)
        except Exception:
            pass

    def closeEvent(self, event):
        self._stop_all_threads()
        super().closeEvent(event)

    def toAnki(self, defi: Optional[Definition] = None) -> str:
        """Process definitions before sending to Anki"""
        # Figure out display mode of current source
        maybe_user_typed_text = self.toPlainText().replace("\n", "<br>")
        if defi is not None:  # for non-interactive use
            self.setCurrentDefinition(defi)
        if self.currentDefinition is None:  # This means no definition is found but maybe the user typed in something
            return maybe_user_typed_text
        source_name = self.currentDefinition.source
        source = self.getSource(source_name)
        if source is None:
            raise ValueError(f"Source {source_name} not found, cannot process definition for Anki")

        return process_defi_anki(self.toPlainText(), self.toMarkdown(), self.currentDefinition, source)
