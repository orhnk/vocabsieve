import os
import sqlite3
from datetime import datetime as dt
from PyQt5.QtWidgets import QLabel
from slpp import slpp
from typing import TYPE_CHECKING
from .GenericImporter import GenericImporter
from .utils import koreader_scandir, findDBpath, findHistoryPath
from .models import ReadingNote
from ..models import LookupRecord
from ..global_names import settings, logger
from ..ui.main_window_base import MainWindowBase
import time

if TYPE_CHECKING:
    from ..main import MainWindow


def getBookMetadata(path):
    _, ext = os.path.splitext(path)
    notepath = os.path.join(path.removesuffix(ext) + ".sdr", f"metadata{ext}.lua")

    try:
        with open(notepath, encoding='utf8') as f:
            data = slpp.decode(" ".join("\n".join(f.readlines()[1:]).split(" ")[1:]))
            try:
                booklang = data['doc_props']['language']  # type: ignore
                booktitle = data['doc_props']['title']  # type: ignore
            except TypeError:
                booklang = settings.value("target_language", "en")
                booktitle = os.path.basename(path).removesuffix(ext)
            except KeyError:
                booklang = settings.value("target_language", "en")
                booktitle = os.path.basename(path).removesuffix(ext)
            return booklang, booktitle
    except Exception as e:
        logger.warning(f"Failed to read KOReader metadata at {notepath}: {repr(e)}")
        return settings.value("target_language", "en"), os.path.basename(path).removesuffix(ext)


class KoreaderVocabImporter(GenericImporter):
    def __init__(self, parent: "MainWindow", path, book_paths=None, settings_paths=None):
        self.splitter = parent.splitter
        self.book_paths = book_paths or [path]
        self.settings_paths = settings_paths or [path]
        super().__init__(parent, "KOReader vocab builder", path, "koreader-vocab")

    def getNotes(self):
        bookfiles = koreader_scandir(self.book_paths)
        langcode = settings.value("target_language", "en")
        metadata = []
        for bookfile in bookfiles:
            metadata.append(getBookMetadata(bookfile))

        books_in_lang = [book[1] for book in metadata if book[0].startswith(langcode)]
        logger.debug(f"Books in language {langcode}: {books_in_lang}")
        logger.debug(
            f"Other books have been skipped. They are {', '.join([book[1] for book in metadata if not book[0].startswith(langcode)])}")
        search_paths = [self.path] + self.settings_paths + self.book_paths
        self.dbpath = findDBpath(search_paths)
        logger.debug("KOReader vocab db path: " + self.dbpath)
        con = sqlite3.connect(self.dbpath)
        cur = con.cursor()
        count = 0

        bookmap = {}

        for bookid, bookname in cur.execute("SELECT id, name FROM title"):
            if bookname in books_in_lang:
                bookmap[bookid] = bookname

        reading_notes = []
        for timestamp, word, title_id, prev_context, next_context in cur.execute(
                "SELECT create_time, word, title_id, prev_context, next_context FROM vocabulary"):
            if title_id in bookmap:
                if prev_context and next_context:
                    ctx = prev_context.strip() + f" {word} " + next_context.strip()  # ensure space before and after
                else:
                    continue
                sentence = ""
                for sentence_ in self.splitter.split(ctx):
                    if word in sentence_:
                        sentence = sentence_
                if sentence:
                    count += 1
                    #items.append((word, sentence, str(dt.fromtimestamp(timestamp).astimezone())[:19], bookmap[title_id]))
                    reading_notes.append(
                        ReadingNote(
                            lookup_term=word,
                            sentence=sentence,
                            book_name=bookmap[title_id],
                            date=str(dt.fromtimestamp(timestamp).astimezone())[:19]
                        )
                    )

        self._layout.addRow(QLabel("Vocabulary database: " + self.dbpath))
        self._layout.addRow(QLabel(f"Found {count} notes in Vocabulary Builder in language '{langcode}'"))

        try:
            self.histpath = findHistoryPath(search_paths)
            logger.debug("KOReader history path: " + self.histpath)
            d = []
            if not self.histpath:
                raise FileNotFoundError("lookup_history.lua not found")
            with open(self.histpath, encoding="utf-8", errors="replace") as f:
                raw = f.read()
                if "LookupHistoryEntry" in raw:
                    content = raw.split("LookupHistoryEntry")[1:]
                    for item in content:
                        d.append(slpp.decode(item))
                else:
                    # Fallback: parse as a Lua table saved by LuaData
                    start = raw.find("{")
                    end = raw.rfind("}")
                    if start == -1 or end == -1:
                        raise ValueError("lookup_history.lua does not contain a Lua table")
                    data = slpp.decode(raw[start:end + 1])
                    lookup_history = data.get("lookup_history") if isinstance(data, dict) else None
                    if isinstance(lookup_history, dict):
                        for key in sorted(lookup_history.keys()):
                            d.append({"data": {str(key): lookup_history[key]}})
                    elif isinstance(lookup_history, list):
                        for item in lookup_history:
                            d.append({"data": {"1": item}})
        except Exception as e:
            logger.error("Failed to find or open lookup_history.lua. Lookups will not be tracked this time.")
            logger.error(e)
            logger.error("Make sure that it is located somewhere under the selected KOReader directories.")
            self._layout.addRow(
                QLabel("Failed to find/read lookup_history.lua. Lookups will not be tracked this time."))
        else:
            entries = [entry['data'].get(next(iter(entry['data']))) for entry in d]
            entries = [entry for entry in entries if entry]
            entries = [(entry.get('word'), entry.get('book_title', ''), entry.get('time')) for entry in entries]
            count = 0
            lookups_count_before = self._parent.rec.countLookups(langcode)
            for word, booktitle, timestamp in entries:
                if not word or not timestamp:
                    continue
                if booktitle in books_in_lang:
                    count += 1
                    self._parent.rec.recordLookup(
                        LookupRecord(
                            word=word,
                            language=langcode,
                            source="koreader"
                        ),
                        timestamp,
                        commit=False
                    )
            self._parent.rec.conn.commit()
            lookups_count_after = self._parent.rec.countLookups(langcode)
            self._layout.addRow(QLabel("Lookup history: " + self.histpath))
            self._layout.addRow(
                QLabel(f"Found {count} lookups in {langcode}, added { lookups_count_after - lookups_count_before } to lookup database."))

        return reading_notes
