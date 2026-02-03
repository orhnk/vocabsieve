"""Wayland clipboard watcher helper.

This module implements a small helper process that runs `wl-paste --watch` for
both the regular clipboard and the primary selection and forwards changes to
VocabSieve over localhost.

It's intended to work around Wayland compositors (e.g. Hyprland) that prevent
unfocused applications from reading clipboard contents.

Usage (typically launched by the app):
  python -m vocabsieve.clipboard_watch --host 127.0.0.1 --port 39285

The server endpoint is implemented by ReaderServer at:
  http://<host>:<port>/api/clipboard
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from typing import Optional

import requests


def _post(host: str, port: int, text: str, selection: bool) -> None:
    url = f"http://{host}:{port}/api/clipboard"
    try:
        requests.post(
            url,
            json={"text": text, "selection": selection},
            timeout=1.5,
        )
    except Exception:
        # Don't crash a watch loop on a transient error.
        pass


def _watch_once(host: str, port: int, selection: bool) -> int:
    """Run a wl-paste watcher loop.

    Returns process return code.
    """

    # If the user has cliphist (common on Hyprland setups), we can piggyback on
    # it to avoid duplicating clipboard-history storage and to integrate cleanly
    # with their existing workflow.
    #
    # This does *not* replace our forwarding behavior; we still forward the
    # current clipboard to VocabSieve by running ourselves in "--deliver" mode.
    use_cliphist = False
    cliphist = os.environ.get("VOCABSIEVE_CLIPHIST", "auto")
    if cliphist in ("1", "true", "yes", "on"):
        use_cliphist = True
    elif cliphist == "auto":
        try:
            from shutil import which

            use_cliphist = which("cliphist") is not None
        except Exception:
            use_cliphist = False

    deliver_cmd = [
        sys.executable,
        "-m",
        "vocabsieve.clipboard_watch",
        "--deliver",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if selection:
        deliver_cmd += ["--primary"]

    cmd = ["wl-paste", "--watch"]
    if selection:
        cmd += ["--primary"]

    if use_cliphist:
        # Run through a shell so we can pipe wl-paste's output into cliphist and
        # then into our deliver command (needs stdin).
        #
        # NOTE: This is intentionally simple and local; it only handles text.
        primary_arg = " --primary" if selection else ""
        deliver_tail = " ".join(
            [
                "'" + p.replace("'", "'\\''") + "'"
                if any(ch in p for ch in " \t\n\"'$")
                else p
                for p in deliver_cmd
            ]
        )
        shell_cmd = (
            f"wl-paste --watch{primary_arg} sh -lc "
            f"'cliphist store >/dev/null 2>&1; {deliver_tail} < /dev/stdin'"
        )
        try:
            proc = subprocess.run(["bash", "-lc", shell_cmd], check=False)
            return int(proc.returncode)
        except FileNotFoundError:
            return 127

    # Fallback: plain forwarding.
    cmd += deliver_cmd

    try:
        proc = subprocess.run(cmd, check=False)
        return int(proc.returncode)
    except FileNotFoundError:
        # wl-paste missing
        return 127


def deliver_mode(host: str, port: int, selection: bool) -> None:
    """Read text from stdin and forward it to the running app."""
    data = sys.stdin.read()
    if not data:
        return
    _post(host, port, data, selection)


def watch_mode(host: str, port: int) -> int:
    """Start two watcher loops (clipboard + primary selection)."""

    # Restart loops if wl-paste exits (it can, depending on compositor).
    def _loop(selection: bool) -> None:
        backoff = 0.2
        while True:
            rc = _watch_once(host, port, selection=selection)
            if rc == 127:
                # wl-paste not installed; no point retrying.
                return
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 5.0)

    t1 = threading.Thread(target=_loop, args=(False,), daemon=True)
    t2 = threading.Thread(target=_loop, args=(True,), daemon=True)
    t1.start()
    t2.start()

    # Keep process alive.
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("VOCABSIEVE_READER_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("VOCABSIEVE_READER_PORT", "39285")))
    p.add_argument("--deliver", action="store_true", help="Internal: deliver stdin to server")
    p.add_argument("--primary", action="store_true", help="Internal: treat stdin as primary selection")
    ns = p.parse_args(argv)

    if ns.deliver:
        deliver_mode(ns.host, ns.port, selection=ns.primary)
        return 0

    return watch_mode(ns.host, ns.port)


if __name__ == "__main__":
    raise SystemExit(main())
