#!/usr/bin/env python3
"""Computer-side AI bridge for a TI-Nspire workflow.

The program deliberately uses the OpenAI-compatible REST shape without requiring
an SDK, so it works with OpenAI and compatible local/self-hosted endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import messagebox, scrolledtext, ttk
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ask(self, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")
        if not self.settings.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        payload = json.dumps(
            {
                "model": self.settings.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a concise math and science assistant for a "
                            "TI-Nspire calculator user. Show useful intermediate "
                            "steps, but keep the final answer easy to type."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            }
        ).encode("utf-8")
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        http_request = request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.settings.timeout) as response:
                result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"AI service returned HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"could not reach AI service: {exc.reason}") from exc

        try:
            return str(result["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("AI service returned an unexpected response") from exc


class BridgeHandler(BaseHTTPRequestHandler):
    client: AIClient

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._send_json(404, {"error": "not found"})
            return
        self._send_json(200, {"ok": True})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ask":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("request body must be a JSON object")
            answer = self.client.ask(str(body.get("question", "")))
            self._send_json(200, {"answer": answer})
        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            self._send_json(400, {"error": str(exc)})

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_http_server(client: AIClient, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("ConfiguredBridgeHandler", (BridgeHandler,), {"client": client})
    server = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def serial_worker(client: AIClient, port: str, stop: threading.Event, output: queue.Queue[str]) -> None:
    try:
        import serial
    except ImportError:
        output.put("Serial mode requires: pip install -r requirements.txt")
        return
    try:
        with serial.Serial(port, 115200, timeout=0.5) as connection:
            while not stop.is_set():
                raw = connection.readline()
                if not raw:
                    continue
                try:
                    message = json.loads(raw.decode("utf-8"))
                    answer = client.ask(str(message.get("question", "")))
                    response = {"id": message.get("id"), "answer": answer}
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
                    response = {"id": None, "error": str(exc)}
                connection.write((json.dumps(response) + "\n").encode("utf-8"))
    except OSError as exc:
        output.put(f"Serial connection failed: {exc}")


class App:
    def __init__(self, root: tk.Tk, client: AIClient, server: ThreadingHTTPServer, serial_port: str | None) -> None:
        self.root = root
        self.client = client
        self.server = server
        self.status = tk.StringVar(value=f"API listening on http://127.0.0.1:{server.server_port}")
        self.question = tk.Text(root, height=5, width=80)
        self.answer = scrolledtext.ScrolledText(root, height=14, width=80, wrap=tk.WORD)
        self.events: queue.Queue[str] = queue.Queue()
        self.stop_serial = threading.Event()

        root.title("TI-Nspire AI Bridge")
        root.minsize(620, 420)
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Question").pack(anchor=tk.W)
        self.question.pack(in_=frame, fill=tk.X, pady=(4, 8))
        ttk.Button(frame, text="Ask AI", command=self.ask).pack(anchor=tk.W)
        ttk.Label(frame, text="Answer").pack(anchor=tk.W, pady=(12, 4))
        self.answer.pack(in_=frame, fill=tk.BOTH, expand=True)
        ttk.Label(frame, textvariable=self.status).pack(anchor=tk.W, pady=(8, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        if serial_port:
            threading.Thread(
                target=serial_worker,
                args=(client, serial_port, self.stop_serial, self.events),
                daemon=True,
            ).start()
            self.status.set(f"API on port {server.server_port}; serial: {serial_port}")
        self.poll_events()

    def ask(self) -> None:
        question = self.question.get("1.0", tk.END).strip()
        self.answer.delete("1.0", tk.END)
        self.answer.insert(tk.END, "Thinking…")
        threading.Thread(target=self._ask_background, args=(question,), daemon=True).start()

    def _ask_background(self, question: str) -> None:
        try:
            answer = self.client.ask(question)
        except (ValueError, RuntimeError) as exc:
            answer = f"Error: {exc}"
        self.root.after(0, self._show_answer, answer)

    def _show_answer(self, answer: str) -> None:
        self.answer.delete("1.0", tk.END)
        self.answer.insert(tk.END, answer)

    def poll_events(self) -> None:
        try:
            self.status.set(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(250, self.poll_events)

    def close(self) -> None:
        self.stop_serial.set()
        self.server.shutdown()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--serial", help="optional serial port exposed by your setup")
    args = parser.parse_args()

    client = AIClient(Settings(os.environ.get("OPENAI_API_KEY", ""), args.base_url, args.model))
    server = start_http_server(client, args.host, args.port)
    root = tk.Tk()
    App(root, client, server, args.serial)
    root.mainloop()


if __name__ == "__main__":
    main()
