from ast import parse
from flask import Flask, render_template, flash, request, redirect, url_for, send_from_directory
from waitress import serve
from requests import get
import os
import re
from loguru import logger
from ..global_names import settings
from .utils import getEpubMetadata
from PyQt5.QtCore import QCoreApplication, QObject, QTimer
import threading
DEBUGGING = None
if os.environ.get("VOCABSIEVE_DEBUG"):
    DEBUGGING = True
    QCoreApplication.setApplicationName(
        "VocabSieve" + os.environ.get("VOCABSIEVE_DEBUG", ""))
else:
    QCoreApplication.setApplicationName("VocabSieve")
QCoreApplication.setOrganizationName("FreeLanguageTools")

app = Flask(__name__)


class ReaderServer(QObject):
    def __init__(self, parent, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.parent = parent

    def start_api(self):
        """ Main server application """

        # NOTE: Flask routes are registered when the server thread starts.
        # We keep them inside this method so they can reference `self`.

        @app.route("/home")
        @app.route("/")
        def home():
            books_dir = settings.value("books_dir")
            book_files = []
            books = []
            if books_dir:
                for file in os.listdir(books_dir):
                    if file.endswith(".epub"):
                        book_files.append(file)
            for book in book_files:
                metadata = getEpubMetadata(os.path.join(books_dir, book))
                metadata['path'] = book
                books.append(metadata)
            return render_template('home.html', books=books)

        @app.route('/read/<path:path>')
        def read_epub(path):
            books_dir = settings.value("books_dir")
            if not books_dir:
                return "No books directory set"
            book_url = url_for('send_epub', path=path)
            metadata = getEpubMetadata(os.path.join(books_dir, path))
            return render_template('read.html',
                                   book_url=book_url,
                                   book_title=metadata['title'],
                                   book_author=metadata['author'])

        @app.route('/books/<path:path>')
        def send_epub(path):
            books_dir = settings.value("books_dir")
            if not books_dir:
                return "No books directory set"
            return send_from_directory(books_dir, path)

        @app.route('/api/clipboard', methods=['POST'])
        def api_clipboard():
            """Accept clipboard/primary-selection text forwarded from an external watcher.

            This is primarily a Wayland workaround: compositors may prevent unfocused
            applications from reading clipboard content directly. Tools like `wl-paste`
            run in the user's session and can read the selection/clipboard reliably.

            Expected JSON:
              {"text": "...", "selection": false}
            """
            # Basic hardening: only accept loopback connections.
            # (waitress sets REMOTE_ADDR)
            if request.remote_addr not in ("127.0.0.1", "::1"):
                return ("forbidden", 403)

            payload = request.get_json(silent=True) or {}
            text = payload.get("text", "")
            selection = bool(payload.get("selection", False))
            if not isinstance(text, str) or not text.strip():
                return ("", 204)

            logger.debug(
                f"/api/clipboard received ({'primary' if selection else 'clipboard'}) len={len(text)}"
            )

            # Marshal to Qt main thread; don't touch widgets from the server thread.
            def _deliver():
                try:
                    # Reuse existing behavior where possible.
                    # We set the clipboard contents then trigger the same handler.
                    # If Wayland blocks reads when unfocused, this still works because
                    # the value is already inside the Qt clipboard for our process.
                    from PyQt5.QtWidgets import QApplication
                    from PyQt5.QtGui import QClipboard

                    if selection and QApplication.clipboard().supportsSelection():
                        QApplication.clipboard().setText(text, QClipboard.Selection)
                        self.parent.clipboardChanged(even_when_focused=True, selection=True)
                    else:
                        QApplication.clipboard().setText(text)
                        self.parent.clipboardChanged(even_when_focused=True)
                except Exception:
                    # Avoid taking down the web reader server on UI errors.
                    pass

            try:
                # QTimer.singleShot(0, ...) is thread-safe in Qt and executes on the
                # thread that owns this QObject (the UI thread in our app).
                QTimer.singleShot(0, _deliver)
            except Exception:
                _deliver()

            return ("ok", 200)

        # `waitress.serve(...)` blocks, so we must run it off the UI thread.
        # This method may be invoked from a QThread or directly from the UI
        # (depending on platform/packaging), so we always move the actual serve
        # call to a daemon thread.
        def _serve():
            serve(app, host=self.host, port=self.port)

        t = threading.Thread(
            target=_serve,
            name=f"vocabsieve-reader-server:{self.host}:{self.port}",
            daemon=True,
        )
        t.start()


