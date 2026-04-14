"""
Local HTTP server for the interactive comparison review workflow.

Starts a lightweight server that:
- Serves the comparison report HTML at /
- Accepts POST /submit with per-image feedback JSON
- Accepts POST /finalize to create a PR (when no corrections remain)
- Returns status via GET /status
- Shuts down cleanly via POST /shutdown

The server runs in a background thread so the calling code can wait
for feedback submissions and process them in the main thread.

Usage (from the skill or from Python):
    from lib.local_server import CompareServer

    server = CompareServer(report_html="<html>...</html>")
    server.start()                # starts serving in background
    print(f"Open: {server.url}")  # e.g. http://localhost:54321

    # Wait for feedback submission
    feedback = server.wait_for_feedback()   # blocks until POST /submit
    if feedback is None:
        # User finalized (no corrections)
        ...
    else:
        # feedback is a list of dicts with corrections
        ...

    server.update_report(new_html)  # serve updated report on next request
    server.stop()
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

log = logging.getLogger("compare-server")


class _ReportHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the comparison review server."""

    # Suppress default stderr logging for each request
    def log_message(self, format: str, *args: Any) -> None:
        log.debug(format, *args)

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send_html(self.server.report_html)

        elif self.path == "/status":
            self._send_json({
                "status": self.server.state,
                "iteration": self.server.iteration,
                "pr_url": self.server.pr_url,
                "message": self.server.status_message,
            })

        elif self.path == "/log":
            self._send_json({"lines": list(self.server.log_lines)})

        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()

        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/submit":
            self._handle_submit()
        elif self.path == "/finalize":
            self._handle_finalize()
        elif self.path == "/shutdown":
            self._send_json({"status": "shutting_down"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        # CORS preflight
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ------------------------------------------------------------------
    # Submit / Finalize handlers
    # ------------------------------------------------------------------

    def _handle_submit(self) -> None:
        """Handle feedback submission (corrections or finalization)."""
        raw = self._read_body()
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        items = data.get("items", [])

        # Store feedback for the main thread to pick up (empty list is valid — means "no corrections this round")
        self.server.state = "processing"
        self.server.status_message = f"Processing {len(items)} correction(s)..." if items else "Acknowledged — advancing iteration..."
        self.server._feedback_event_data = items
        self.server._feedback_event.set()

        # Spawn auto-processor if there are corrections and paths are configured
        if items and self.server.corrections_path and self.server.pairs_path:
            threading.Thread(
                target=self.server._spawn_auto_processor,
                daemon=True,
            ).start()

        self._send_json({
            "status": "processing",
            "message": f"Processing {len(items)} correction(s). Watch the live log below — the page will refresh when updated." if items
                       else "Acknowledged. Refreshing report...",
        })

    def _handle_finalize(self) -> None:
        """Handle final submission with no corrections (create PR)."""
        self.server.state = "finalizing"
        self.server.status_message = "Creating PR with skill updates..."
        self.server._feedback_event_data = None  # None signals "finalize"
        self.server._feedback_event.set()

        self._send_json({
            "status": "finalizing",
            "message": "Creating PR with before/after comparison images...",
        })


class CompareServer:
    """
    Local HTTP server for the interactive comparison review workflow.

    The server runs in a background thread. The calling code uses
    wait_for_feedback() to block until the user submits feedback
    or finalizes (no corrections).
    """

    def __init__(self, report_html: str = "", host: str = "127.0.0.1", port: int = 0):
        """
        Args:
            report_html: Initial HTML content for the comparison report.
            host: Bind address (default: localhost only).
            port: Port number. 0 = auto-select a free port.
        """
        self._host = host
        self._port = port or _find_free_port(host)
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

        # Shared state between handler and caller
        self.report_html = report_html
        self.state = "ready"          # ready, processing, finalizing, done
        self.iteration = 0
        self.pr_url = ""
        self.status_message = ""

        # Live log lines streamed to the browser
        self.log_lines: list[str] = []

        # Paths for auto-processor spawning (set by run_compare_server.py)
        self.corrections_path: str = ""
        self.pairs_path: str = ""

        # Synchronization: the main thread waits on this event
        self._feedback_event = threading.Event()
        self._feedback_event_data: list[dict] | None = None

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def start(self) -> None:
        """Start the server in a background thread."""
        self._server = HTTPServer((self._host, self._port), _ReportHandler)
        # Attach shared state to the server so the handler can access it
        self._server.report_html = self.report_html  # type: ignore[attr-defined]
        self._server.state = self.state  # type: ignore[attr-defined]
        self._server.iteration = self.iteration  # type: ignore[attr-defined]
        self._server.pr_url = self.pr_url  # type: ignore[attr-defined]
        self._server.status_message = self.status_message  # type: ignore[attr-defined]
        self._server.log_lines = self.log_lines  # type: ignore[attr-defined]
        self._server.corrections_path = self.corrections_path  # type: ignore[attr-defined]
        self._server.pairs_path = self.pairs_path  # type: ignore[attr-defined]
        self._server._feedback_event = self._feedback_event  # type: ignore[attr-defined]
        self._server._feedback_event_data = self._feedback_event_data  # type: ignore[attr-defined]
        self._server._spawn_auto_processor = self._spawn_auto_processor  # type: ignore[attr-defined]

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log.info(f"Compare server started at {self.url}")

    def stop(self) -> None:
        """Shut down the server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("Compare server stopped")

    def wait_for_feedback(self, timeout: float | None = None) -> list[dict] | None:
        """
        Block until the user submits feedback or finalizes.

        Returns:
            list[dict]: Feedback items if corrections were submitted.
            None: If the user finalized (no corrections).

        Raises:
            TimeoutError: If timeout is reached without feedback.
        """
        self._feedback_event.clear()
        if not self._feedback_event.wait(timeout=timeout):
            raise TimeoutError("No feedback received within timeout")

        data = self._server._feedback_event_data if self._server else None
        return data

    def update_report(self, new_html: str) -> None:
        """Replace the served report HTML with an updated version."""
        self.report_html = new_html
        self.log_lines.clear()
        if self._server:
            self._server.report_html = new_html  # type: ignore[attr-defined]
            self.iteration += 1
            self._server.iteration = self.iteration  # type: ignore[attr-defined]
            self.state = "ready"
            self._server.state = "ready"  # type: ignore[attr-defined]
            self.status_message = "Updated report ready for review."
            self._server.status_message = self.status_message  # type: ignore[attr-defined]

    def _spawn_auto_processor(self) -> None:
        """Spawn lib/auto_process.py as a subprocess and stream its output to log_lines."""
        _lib = Path(__file__).parent
        script = str(_lib / "auto_process.py")
        cmd = [
            sys.executable, script,
            "--corrections", self.corrections_path,
            "--pairs", self.pairs_path,
        ]
        self.log_lines.clear()
        self.log_lines.append("Auto-processor starting...")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            for line in proc.stdout:  # type: ignore[union-attr]
                self.log_lines.append(line.rstrip())
            proc.wait()
        except Exception as exc:
            self.log_lines.append(f"ERROR spawning auto-processor: {exc}")

    def set_pr_url(self, url: str) -> None:
        """Set the PR URL after finalization."""
        self.pr_url = url
        if self._server:
            self._server.pr_url = url  # type: ignore[attr-defined]
        self.state = "done"
        if self._server:
            self._server.state = "done"  # type: ignore[attr-defined]
        self.status_message = f"PR created: {url}"
        if self._server:
            self._server.status_message = self.status_message  # type: ignore[attr-defined]


def _find_free_port(host: str = "127.0.0.1") -> int:
    """Find a free TCP port on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
