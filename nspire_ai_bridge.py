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
import ssl
import threading
import tkinter as tk
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import messagebox, scrolledtext, ttk
from typing import Any
from urllib import error, request

import certifi


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0
    temperature: float = 0.2
    system_prompt: str = (
        "You are a concise math and science assistant for a TI-Nspire calculator "
        "user. Show useful intermediate steps, but keep the final answer easy to type."
    )


PROVIDERS = {
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Google Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash"),
    "OpenRouter": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "Custom OpenAI-compatible": ("", ""),
}


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
                "temperature": self.settings.temperature,
                "messages": [
                    {
                        "role": "system",
                        "content": self.settings.system_prompt,
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
            tls_context = ssl.create_default_context(cafile=certifi.where())
            with request.urlopen(
                http_request, timeout=self.settings.timeout, context=tls_context
            ) as response:
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
        if self.path == "/":
            self._send_html()
            return
        if self.path == "/health":
            self._send_json(200, {"ok": True})
            return
        if self.path == "/settings":
            self._send_json(200, self._public_settings())
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/settings":
            self._update_settings()
            return
        if self.path != "/ask":
            self._send_json(404, {"error": "not found"})
            return
        try:
            body = self._read_json()
            if not isinstance(body, dict):
                raise ValueError("request body must be a JSON object")
            answer = self.client.ask(str(body.get("question", "")))
            self._send_json(200, {"answer": answer})
        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            self._send_json(400, {"error": str(exc)})

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length))

    def _public_settings(self) -> dict[str, Any]:
        settings = self.client.settings
        return {
            "base_url": settings.base_url,
            "model": settings.model,
            "timeout": settings.timeout,
            "temperature": settings.temperature,
            "system_prompt": settings.system_prompt,
            "api_key_configured": bool(settings.api_key),
            "api_key_hint": ("configured" if settings.api_key else "not configured"),
        }

    def _update_settings(self) -> None:
        try:
            body = self._read_json()
            if not isinstance(body, dict):
                raise ValueError("settings must be a JSON object")
            settings = self.client.settings
            if "base_url" in body:
                base_url = str(body["base_url"]).strip()
                if not base_url.startswith(("http://", "https://")):
                    raise ValueError("base URL must start with http:// or https://")
                settings.base_url = base_url
            if "api_key" in body:
                api_key = str(body["api_key"]).strip()
                if api_key:
                    settings.api_key = api_key
            if "model" in body:
                settings.model = str(body["model"]).strip()
                if not settings.model:
                    raise ValueError("model must not be empty")
            if "timeout" in body:
                settings.timeout = float(body["timeout"])
                if not 1 <= settings.timeout <= 600:
                    raise ValueError("timeout must be between 1 and 600 seconds")
            if "temperature" in body:
                settings.temperature = float(body["temperature"])
                if not 0 <= settings.temperature <= 2:
                    raise ValueError("temperature must be between 0 and 2")
            if "system_prompt" in body:
                settings.system_prompt = str(body["system_prompt"]).strip()
                if not settings.system_prompt:
                    raise ValueError("system prompt must not be empty")
            self._send_json(200, self._public_settings())
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc)})

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self) -> None:
        page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TI-Nspire AI Bridge</title>
  <style>
    body { max-width: 760px; margin: 2rem auto; padding: 0 1rem;
           font: 16px system-ui, sans-serif; color: #192d4b; }
    textarea { box-sizing: border-box; width: 100%; min-height: 130px;
               padding: .75rem; font: inherit; }
    button { margin-top: .75rem; padding: .6rem 1rem; cursor: pointer; }
    pre { white-space: pre-wrap; background: #eef3f9; padding: 1rem;
          min-height: 100px; color: #222; }
    details { margin-top: 1.5rem; padding: 1rem; background: #f5f6f8; }
    label { display: block; margin-top: .7rem; }
    input, settings-textarea { box-sizing: border-box; width: 100%; padding: .5rem; }
    .settings-prompt { min-height: 80px; }
    .warning { color: #8a4b00; }
    #status { color: #555; }
  </style>
</head>
<body>
  <h1>TI-Nspire AI Bridge</h1>
  <p>Ask a question here, or use the <code>/ask</code> API from your calculator.</p>
  <p id="connection">Checking computer bridge...</p>
  <textarea id="question" placeholder="Type your question..."></textarea>
  <br>
  <button id="ask">Ask AI</button>
  <p id="status"></p>
  <h2>Answer</h2>
  <pre id="answer">No answer yet.</pre>
  <details>
    <summary><strong>AI settings</strong></summary>
    <p class="warning">The key is kept only in this running Mac process and is cleared when the bridge stops. Never share it.</p>
    <label>Provider
      <select id="provider">
        <option>OpenAI</option>
        <option>Google Gemini</option>
        <option>OpenRouter</option>
        <option>Custom OpenAI-compatible</option>
      </select>
    </label>
    <label>API key <input id="api-key" type="password" autocomplete="off"
      placeholder="Enter a key; leave blank to keep the current key"></label>
    <label>Model <input id="model" placeholder="gpt-4o-mini"></label>
    <label>API base URL <input id="base-url" placeholder="https://api.openai.com/v1"></label>
    <label>Timeout (seconds) <input id="timeout" type="number" min="1" max="600"></label>
    <label>Temperature (0 to 2) <input id="temperature" type="number" min="0" max="2" step="0.1"></label>
    <label>System instruction <textarea id="system-prompt" class="settings-prompt"></textarea></label>
    <button id="save-settings">Save settings</button>
    <span id="settings-status"></span>
  </details>
  <script>
    const question = document.getElementById("question");
    const answer = document.getElementById("answer");
    const status = document.getElementById("status");
    const settingsStatus = document.getElementById("settings-status");
    const providers = {
      "OpenAI": ["https://api.openai.com/v1", "gpt-4o-mini"],
      "Google Gemini": ["https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash"],
      "OpenRouter": ["https://openrouter.ai/api/v1", "openai/gpt-4o-mini"],
      "Custom OpenAI-compatible": ["", ""]
    };
    document.getElementById("provider").addEventListener("change", () => {
      const values = providers[document.getElementById("provider").value];
      if (values[0]) document.getElementById("base-url").value = values[0];
      if (values[1]) document.getElementById("model").value = values[1];
    });
    function showSettings(settings) {
      document.getElementById("model").value = settings.model;
      document.getElementById("base-url").value = settings.base_url;
      document.getElementById("timeout").value = settings.timeout;
      document.getElementById("temperature").value = settings.temperature;
      document.getElementById("system-prompt").value = settings.system_prompt;
      document.getElementById("api-key").placeholder =
        settings.api_key_configured ? "Key configured; enter a new key to replace it" : "Enter an API key";
    }
    fetch("/settings").then((response) => response.json()).then(showSettings);
    document.getElementById("save-settings").addEventListener("click", async () => {
      settingsStatus.textContent = "Saving...";
      try {
        const response = await fetch("/settings", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            model: document.getElementById("model").value,
            base_url: document.getElementById("base-url").value,
            api_key: document.getElementById("api-key").value,
            timeout: Number(document.getElementById("timeout").value),
            temperature: Number(document.getElementById("temperature").value),
            system_prompt: document.getElementById("system-prompt").value
          })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not save settings");
        showSettings(data);
        document.getElementById("api-key").value = "";
        settingsStatus.textContent = " Saved.";
      } catch (error) {
        settingsStatus.textContent = " Error: " + error.message;
      }
    });
    fetch("/health").then((response) => {
      if (!response.ok) throw new Error("bridge is not healthy");
      document.getElementById("connection").textContent =
        "Computer bridge connected. Calculator transport: manual handoff.";
    }).catch(() => {
      document.getElementById("connection").textContent =
        "Computer bridge is not responding.";
    });
    document.getElementById("ask").addEventListener("click", async () => {
      const text = question.value.trim();
      if (!text) { status.textContent = "Enter a question first."; return; }
      status.textContent = "Thinking...";
      answer.textContent = "";
      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: text})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Request failed");
        answer.textContent = data.answer;
        status.textContent = "Done.";
      } catch (error) {
        answer.textContent = "Error: " + error.message;
        status.textContent = "";
      }
    });
  </script>
</body>
</html>"""
        encoded = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
