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

The desktop window starts with the HTTP API on `http://127.0.0.1:8765`. The
default endpoint is OpenAI-compatible; it can be changed with:

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

The local API accepts:

```bash
curl -X POST http://127.0.0.1:8765/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Solve 2x + 3 = 11"}'
```

Only bind to a non-loopback address on a trusted private network. The endpoint
does not include authentication, because the default is intentionally local-only.