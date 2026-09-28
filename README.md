# TI-Nspire AI Bridge

This project is a small computer-side bridge for using an AI assistant alongside a
TI-Nspire CX II/CX II CAS. It provides:

- a Tkinter desktop window for asking questions and copying answers;
- a local HTTP API (`/ask`) that other calculator-side tools can call;
- an optional newline-delimited JSON serial transport for a USB/serial adapter or
  an Ndless serial program.

## Important connection detail

The standard TI-Nspire USB connection is not a normal network adapter and Texas
Instruments does not document a general-purpose HTTP or serial API for it. The
bridge therefore keeps the computer transport explicit: use the local API when
your calculator-side program can reach the computer, or use a serial device
(`--serial`) when your setup exposes one. This is safer and more reliable than
claiming that any USB cable alone can carry arbitrary application data.

## Setup

Python 3.10+ is required. An API key is read from `OPENAI_API_KEY` and never
stored by the program.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
python3 nspire_ai_bridge.py
```

The desktop window starts with the HTTP API and browser UI on
`http://127.0.0.1:8765`. Open that address in your browser to ask questions.
The default AI endpoint is OpenAI-compatible; it can be changed with:

```bash
python3 nspire_ai_bridge.py \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --port 8765
```

For a serial transport, first identify the port (`/dev/cu.usbserial-*` on
macOS, `COM3` on Windows, or `/dev/ttyUSB0` on Linux), then run:

```bash
python3 nspire_ai_bridge.py --serial /dev/cu.usbserial-0001
```

Serial requests and responses are one JSON object per line:

```json
{"id":"1","question":"What is the derivative of x^2?"}
{"id":"1","answer":"2x"}
```

## Calculator-side companion

`calculator/nspire_ai.lua` is a standard TI-Nspire Lua document script. Transfer
it to the calculator as a `.tns` Lua document using TI-Nspire Student Software
or TI-Nspire Computer Link, then open the document.

The stock Lua runtime cannot make arbitrary TCP or USB connections. The
companion therefore uses a visible JSON handoff:

1. Type a question and press **Enter**, then press **1**. Read the displayed
   JSON request and enter the same request on the computer.
2. Send it to the bridge, for example:

   ```bash
   curl -s http://127.0.0.1:8765/ask \
     -H 'Content-Type: application/json' \
     -d '{"question":"What is the derivative of x^2?"}'
   ```
3. Return to the calculator, press **2**, enter the returned JSON, and press
   **Enter**. The answer is then displayed.

This is an honest stock-firmware workflow. Fully automatic live communication
requires an Ndless program and a supported USB/serial transport; the bridge's
`--serial` mode is ready for that transport, but a regular TI cable does not
provide it by itself.

The standard TI-Nspire Student Software connection is for file transfer; it does
not make the Mac's web server available to a Lua document. A fully automatic
connection requires an Ndless program exposing a supported serial transport,
usually with a USB-to-serial adapter.

The local API accepts:

```bash
curl -X POST http://127.0.0.1:8765/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Solve 2x + 3 = 11"}'
```

Only bind to a non-loopback address on a trusted private network. The endpoint
does not include authentication, because the default is intentionally local-only.