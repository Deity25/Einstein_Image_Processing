# Einstein Offline — animated companion + local AI (macOS)

**What you are installing:** A browser-based local Einstein app with an animated chibi Einstein pet, an offline Ollama AI, explicit persistent memory, simple document retrieval, and chat history. **This is independent of the Codex desktop pet.** The Codex pet provides animation only; this separate app provides the assistant functionality.

## One-time setup WITH internet

1. Install **Python 3.10 or newer** on your Mac if `python3 --version` doesn't work.
2. Download and install **Ollama** from its official website: <https://ollama.com/download/mac>. Open Ollama so its local service is running.
3. In Terminal, download a small model:

   ```bash
   ollama pull qwen3:1.7b
   ollama list
   ```

   This model is approximately **1.4 GB** to download. An alternative is `ollama pull llama3.2:3b` (approximately 2 GB) and then run `EINSTEIN_MODEL=llama3.2:3b python3 server.py`.
4. To import PDFs, optionally install `pypdf` while online:

   ```bash
   python3 -m pip install pypdf
   ```

   If your Python says it is externally managed, create a virtual environment: `python3 -m venv .venv`, then `source .venv/bin/activate`, then `pip install pypdf`. TXT, MD, CSV, JSON, Java, Python, JS, SQL, and other text files **do not need pypdf**.

## Start Einstein (internet NOT required after setup)

1. Download `Einstein_Offline_Assistant.zip` into Downloads.
2. In Terminal:

   ```bash
   cd ~/Downloads
   unzip -o Einstein_Offline_Assistant.zip
   cd Einstein_Offline_Assistant
   python3 server.py
   ```

3. Open: **http://127.0.0.1:8765**
4. Try turning off Wi-Fi after the model has been downloaded. Your app should still work. The model may take a few seconds to load initially.
5. Stop the server with **Control + C** in Terminal.

**Terminal-only chat:** Instead of `python3 server.py`, run `python3 terminal_einstein.py`.

You can also start the browser version by running `./start_mac.command` after `chmod +x start_mac.command`, provided Ollama is running. It opens your default browser.

## What the buttons do

- **Thinking / Success / Debug / Rest:** Preview four states from the included Einstein sprite sheet.
- **Import a local file:** The browser reads the file and sends it to the Python process at `127.0.0.1`. Python stores the extracted text in its local SQLite database. Existing imports with the same filename are replaced. Remove any file using its Remove button.
- **Remember a fact:** Explicitly save a note such as `My project uses Java 21`. The assistant can reuse it later. You can delete saved notes with Forget.
- **Chat:** Python searches relevant notes and imported passages, adds them as context, and submits a question to Ollama on this computer.
- **Close and reopen:** Notes, imported text, and recent chat history remain in the database file.

## Try the demo

1. Click **Import a local file** and select `examples/example_knowledge.txt`.
2. Ask: **Which database does Project Orion use?** It should retrieve a passage containing PostgreSQL. The *actual wording of the AI answer depends on the local model*.
3. Enter `Remember that my coding language is Java` as a chat message.
4. Close the app, start it again, and ask: `What coding language did I ask you to remember?`
5. Click **Forget** when you want to remove that saved fact.

## What is stored, and where?

- Your data is at `~/.einstein_offline/einstein.sqlite3`.
- It has `memories` (explicit notes), `documents` (imported text in overlapping pieces), and `chats` (conversation history).
- SQLite is **not encrypted by this program**. Keep macOS FileVault and device login enabled for stronger local protection.
- The local Python server binds only to `127.0.0.1:8765`; Ollama runs separately at `127.0.0.1:11434`. The app uses no external URLs, cloud API keys, remote analytics, or network fonts. The program cannot search the web.
- Deleting an imported document removes its searchable passages but does **not** remove facts repeated in previous chat messages or manually saved memories. Those may need separate deletion; delete the database file while the app is stopped if you want to remove *all* Einstein data.

## Limits you should know

- **Not a new ChatGPT model:** Ollama is the AI brain; the pet is a display layer.
- **Not model training:** Imported documents are searched and inserted into prompts; the base AI weights are not changed.
- **Memory is explicit:** Long-term notes are saved when you click Save or say “remember that”. Ordinary conversations are stored as history but not automatically converted into profile facts.
- **Simple text retrieval:** Keyword overlap works for modest amounts of notes. A production system should use an offline embedding index, chunk metadata, tests, and evaluation datasets.
- **PDFs:** Optional `pypdf` handles PDFs containing selectable text. Scanned/image PDFs require a separate OCR engine, not included here.
- **No voice input/output yet:** Spoken conversation needs an offline STT/TTS engine, such as Vosk or Whisper.cpp and Piper, installed separately.
- **No floating system-wide pet yet:** This version animates inside a local browser. Making it float above every app needs a native window or a desktop app wrapper.
- **Small models make mistakes:** Verify code and important answers. Imported file text should be treated as untrusted source material.
- **No automatic code execution or unapproved filesystem access:** You select which files to import, and the app never runs code found inside them.

## Files and engineering learning path

| File | Why it exists |
|---|---|
| `index.html` | UI, pure CSS, sprite animation, chat buttons, FileReader and browser `fetch` |
| `assets/spritesheet.webp` | 1536×1872 transparent atlas, 8×9 frames |
| `server.py` | HTTP API, SQLite, memory retrieval, Ollama local chat |
| `terminal_einstein.py` | A small commented command-line version for learning |
| `test_offline.py` | Offline unit/integration tests that mock actual model inference |
| `LINE_BY_LINE.md` | Explanation of key executable code, line by line |
| `video_source/build_video.py` | Source to regenerate the narrated 2m49s MP4 on a machine with Pillow, OpenCV, espeak, and FFmpeg |

To run tests without Ollama:

```bash
python3 test_offline.py
```

**Note:** These tests check storage, local HTTP API, and mocked model calls. I could not run inference on your specific Mac from here. Verify `ollama list`, actual answers, and animation on your machine after installing.

## Optional: install the visual Einstein pet in Codex too

The ZIP also includes `codex_pet/einstein-chibi/pet.json` and its sprite sheet. They are the animation-only Codex pet assets. They **do not** connect to the standalone offline assistant automatically.

```bash
cd codex_pet
bash install_to_codex_mac.command
```

Restart Codex and choose Einstein from Pets. This does not install Ollama, make Codex offline, or grant the pet its own memory.
