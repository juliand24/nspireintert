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

If you already installed the project before the certificate fix, run
`pip install -r requirements.txt` again. The bridge uses `certifi` for verified
TLS certificates and does not disable certificate checking.

The desktop window starts with the HTTP API and browser UI on
`http://127.0.0.1:8765`. Open that address in your browser to ask questions.
The default AI endpoint is OpenAI-compatible; it can be changed with:

```bash
python3 nspire_ai_bridge.py \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --port 8765
```

The browser's **AI settings** panel includes presets for OpenAI, Google Gemini
(OpenAI-compatible endpoint), and OpenRouter, plus a custom OpenAI-compatible
provider. It also accepts an API key through a password field. The key is held
only in memory by the running local process, is not returned by `/settings`, and
is cleared when the bridge stops. Leave the key field blank when changing other
settings to keep the current key. The Gemini preset uses `gemini-3.8-flash`;
Google may change model availability, so select a currently available model in
the settings panel if needed.

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

## Ndless/NavNet USB tunnel

For a CX II with Ndless, the project also exposes a newline-delimited JSON TCP
service on port `8766` by default:

```bash
python3 nspire_ai_bridge.py --nspire-port 8766
```

`ndless/nsocket_ai.c` is a small client for the `nsocket` NavNet project. It
uses the calculator's USB link through NavNet, while the nsocket computer-side
helper forwards the stream to this Python port. Build the client with the
`nsocket` library and Ndless SDK, then change `BRIDGE_HOST` and
`BRIDGE_PORT` in the source to match the host helper. This is a source
template, not a prebuilt `.tns` application: Ndless builds are tied to the
calculator OS/SDK version.

The host helper and calculator client must both be running; the regular TI USB
cable is transported through NavNet, not exposed as `/dev/cu.*`. If you do not
have the nsocket host helper installed, use the browser API until that
Ndless-specific component is built.

## Calculator-side companion

`calculator/nspire_ai.lua` is the source for a TI-Nspire Lua document. Do not
rename the `.lua` file to `.tns`; the calculator needs the script embedded in a
Lua document:

1. In TI-Nspire Student Software, create a new **Lua Script** document.
2. Open the script editor, replace its contents with
   `calculator/nspire_ai.lua`, and save the document as a `.tns` file.
3. Transfer that `.tns` document to the calculator and open it.

The stock Lua runtime cannot make arbitrary TCP or USB connections. The
companion therefore uses a visible JSON handoff:

1. Type a question and press **Enter**, then press **1**. The calculator shows
   the JSON request. Since stock Lua cannot copy it to the Mac, type the
   question into the Mac bridge browser instead.
2. Send it to the bridge, for example:

   ```bash
   curl -s http://127.0.0.1:8765/ask \
     -H 'Content-Type: application/json' \
     -d '{"question":"What is the derivative of x^2?"}'
   ```
3. Return to the calculator, press **Enter**, then press **2**, type the
   returned JSON, and press **Enter**. The answer is then displayed. For long
   answers this manual workflow is inconvenient; use the Mac browser directly
   unless you have Ndless and a real transport.

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