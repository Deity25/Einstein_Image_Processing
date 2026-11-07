# Einstein Offline —  explained, line by line

This is an explanation of the working project, not just pseudocode. Open `server.py` and `index.html` beside this guide, find the corresponding function, and follow each line. Comments already appear throughout the source. The short `terminal_einstein.py` is also directly annotated above almost every executable line.

## 1. Why the app needs five technologies

**HTML** describes the chat box, buttons, and pet area. **CSS** styles those elements and puts the correct rectangle of a sprite sheet on screen. **JavaScript** changes animation states and sends user input to the local server. **Python** coordinates the response and manages the SQLite database. **Ollama** runs an LLM model locally. The model cannot see the browser directly: Python sends it a structured message.

```text
YOU -> HTML/JavaScript -> HTTP localhost:8765 -> Python
                                            | -> SQLite memory
                                            | -> Document search
                                            ` -> Ollama localhost:11434 -> LLM answer
LLM answer -> Python -> JSON -> JavaScript -> chat bubble + Einstein animation
```

## 2. How the animation works: literally every line

From `index.html`:

```js
const pet = document.querySelector('#pet');
const states = {
  idle: {row:0,frames:6,bubble:"Let's see what the data reveals..."},
  work: {row:7,frames:6,bubble:'Running a local experiment...'}
};
let current = 'idle';
let frame = 0;
setInterval(() => {
  const s = states[current];
  pet.style.backgroundPosition = `${-frame * 192}px ${-s.row * 208}px`;
  frame = (frame + 1) % s.frames;
}, 165);
```

| Code line | What it does and why |
|---|---|
| `document.querySelector('#pet')` | Finds the single HTML element that displays Einstein. |
| `const states = { ... }` | Maps semantic states to exact animation rows, frame counts, and short speech. |
| `row:0` | The idle pictures are in the top row of the atlas. |
| `frames:6` | There are six usable idle poses; do not advance into the empty cells. |
| `let current = 'idle'` | Stores the current animation state. `let` is used because it changes later. |
| `let frame = 0` | Starts the animation from the first image in the row. |
| `setInterval(() => { ... }, 165)` | Runs an animation tick every 165 milliseconds (~6 FPS). It does not require an internet connection. |
| `const s = states[current]` | Reads the row and number of frames for the current mode. |
| `-frame * 192` | Moves the background left 192 pixels per column. Minus is needed because CSS shifts the big image behind the frame window. |
| `-s.row * 208` | Moves the image up 208 pixels per animation row. |
| `backgroundPosition = ...` | Updates which region of the single WebP is visible. |
| `(frame + 1) % s.frames` | Advances and wraps back to zero at the end of the row. `%` is the remainder operator. |

**Why 192 and 208?** The whole spritesheet is 1536 × 1872 pixels. It has 8 columns (`1536 / 8 = 192`) and 9 rows (`1872 / 9 = 208`). An image cell is 192 × 208. The renderer clips the enormous sheet into one small visible viewport.

**Why not regenerate an image every frame?** Image generation is expensive and inconsistent. Pre-rendered images produce deterministic, lightweight animation.

### How Einstein reacts to chat events

```js
setMode('work');                       // Start the coding/busy row.
const answer = await api('/api/chat', {message:question}); // Send question to localhost.
addMessage('assistant', answer.answer); // Render plain text returned by Python.
setMode('success', 3000);              // Play celebration, then go idle after 3 sec.
```

If `api(...)` throws an error, the `catch` block displays an error response and calls `setMode('error', 5000)`. If you leave the interface unused, the inactivity timer calls `setMode('sleep')`. **The character is reacting to application events, not independently understanding your code.**

## 3. How Python opens the offline server

```python
HOST = "127.0.0.1"
PORT = 8765
ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
```

| Line | Purpose |
|---|---|
| `HOST = "127.0.0.1"` | Restricts the server to loopback, accessible from the same Mac only. |
| `PORT = 8765` | Chooses the listening port. |
| `ThreadingHTTPServer` | Handles browser requests; multiple requests may be processed concurrently. |
| `(HOST, PORT)` | Network address to bind. This is not an internet domain. |
| `Handler` | The class that knows what each URL endpoint does. |
| `.serve_forever()` | Keeps the server running until you press Control+C. |

A URL like `http://127.0.0.1:8765/api/chat` is on your own computer. It is different from a website, even though both use HTTP.

## 4. What SQLite does when you say Remember

```python
cx = sqlite3.connect(DB_FILE, timeout=15)
cx.row_factory = sqlite3.Row
cx.execute("INSERT INTO memories(note,created_at) VALUES (?,?)", (note,timestamp()))
```

| Line | Purpose |
|---|---|
| `sqlite3.connect(DB_FILE...)` | Opens a persistent local database file. If missing, SQLite can create it. |
| `timeout=15` | Wait up to 15 seconds for another transaction before reporting a locked database. |
| `row_factory = sqlite3.Row` | Enables access like `row['note']` rather than just numeric indexes. |
| `INSERT INTO memories` | Adds a new record to the `memories` table. |
| `(note,created_at)` | Defines which columns are populated. |
| `VALUES (?,?)` | Uses placeholders instead of directly inserting the note into SQL text; this prevents SQL injection. |
| `(note,timestamp())` | Supplies the two values that replace the question marks. |

The user can delete a memory with `DELETE FROM memories WHERE id=?`. The database survives closing the browser because it exists on disk at `~/.einstein_offline/einstein.sqlite3`.

**Important:** A note such as "I prefer Java" is stored as data, not taught to the model's weights. On future chats, Python retrieves it and includes it in the model's instructions as context.

## 5. What happens when you import a file

```python
filename = Path(filename).name[:180]
text = decode_file(filename, binary)
passages = split_chunks(text)
cx.execute("DELETE FROM documents WHERE source = ?", (filename,))
cx.executemany("INSERT INTO documents(source, part, content) VALUES (?,?,?)", rows)
```

1. `Path(filename).name` keeps the filename rather than accepting folder paths.
2. `[:180]` restricts its length in the database.
3. `decode_file` extracts text from accepted file types; optional `pypdf` handles digital PDFs.
4. `split_chunks` creates ~1100-character passages with ~140 characters of overlap. Overlap helps preserve a sentence crossing a boundary.
5. `DELETE ... WHERE source = ?` replaces a previously imported file with the same name, avoiding duplicate old passages.
6. `executemany(...)` inserts all passages efficiently as parameterized records.

**No imported code is executed.** A `.java` or `.py` file is simply read as text and stored for explanation.

## 6. Why retrieval matters

```python
words = keywords(question)
clauses = " OR ".join("lower(content) LIKE ?" for _ in words)
args = ["%" + w + "%" for w in words]
candidates = cx.execute(f"SELECT source,part,content FROM documents WHERE {clauses} LIMIT 250",args).fetchall()
```

| Line | Purpose |
|---|---|
| `keywords(question)` | Extracts useful words and ignores common English filler words. |
| `" OR ".join(...)` | Builds one condition per search word. Only the query structure is generated here; actual words are never interpolated into SQL. |
| `lower(content) LIKE ?` | Matches a keyword anywhere in a stored passage, ignoring case for ordinary Latin text. |
| `"%" + w + "%"` | `%` is SQLite's wildcard for characters before or after the word. |
| `cx.execute(...,args)` | Passes the keyword values separately to SQLite, rather than injecting raw values into SQL. |
| `LIMIT 250` | Bounds how many passages Python ranks at once. |
| `.fetchall()` | Retrieves the candidate passages from the local database. |

Python then counts keyword overlap and keeps the best four passages. This is intentionally a **simple keyword search**, so it can miss paraphrases or synonyms. A more advanced offline assistant would generate local embeddings, use vector similarity search, and rerank results.

## 7. How Ollama generates an answer with no internet

From `server.py`:

```python
payload = {"model": MODEL, "messages": messages, "stream": False,
           "options": {"temperature": 0.25, "num_ctx": 4096}}
request = Request(OLLAMA_URL + "/api/chat",
                  data=json.dumps(payload).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
with urlopen(request, timeout=180) as resp:
    data = json.load(resp)
answer = data.get("message", {}).get("content", "").strip()
```

| Line | Purpose |
|---|---|
| `"model": MODEL` | Chooses the locally downloaded model (`qwen3:1.7b` by default). |
| `"messages": messages` | Passes the user question, recent history, saved notes, and retrieved file passages. |
| `"stream": False` | Waits for one complete answer instead of receiving many incremental chunks. This is simpler for a beginner. |
| `"temperature": 0.25` | Requests relatively conservative generation, although it does not guarantee correctness. |
| `"num_ctx": 4096` | Requests a 4096-token context window to bound resource use. |
| `Request(...)` | Builds an HTTP request to `http://127.0.0.1:11434/api/chat`. |
| `json.dumps(payload)` | Serializes Python structures into JSON understood by Ollama. |
| `.encode('utf-8')` | Converts the JSON string to bytes for the HTTP connection. |
| `Content-Type: application/json` | Tells Ollama that the request body is JSON. |
| `method='POST'` | Sends information for inference rather than just fetching a page. |
| `urlopen(...,timeout=180)` | Calls the local model and limits waiting to three minutes. |
| `json.load(resp)` | Parses Ollama's JSON response into Python objects. |
| `.get('message',{}).get('content','')` | Safely extracts text from the assistant's response. |
| `.strip()` | Removes leading/trailing whitespace. |

A locally downloaded model may still hallucinate. Using documents as context reduces some mistakes but does not eliminate them.

## 8. What does the browser send to Python?

```js
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: {'Content-Type':'application/json'},
  body: JSON.stringify({message: question})
});
const result = await response.json();
```

| Line | Purpose |
|---|---|
| `fetch('/api/chat', ...)` | Requests the endpoint on the same host that served the page. It doesn't include an external URL. |
| `await` | Pauses this asynchronous function until the request finishes, without freezing the whole browser. |
| `method:'POST'` | Sends data to Python. |
| `headers` | Declares JSON data format. |
| `JSON.stringify(...)` | Converts a JavaScript object into JSON text. |
| `message:question` | Adds the user's typed question to the request body. |
| `response.json()` | Parses the returned JSON, including the answer and source names. |

## 9. Why the project has two different kinds of memory

- **Conversation history**: last exchanges stored in `chats` for follow-up coherence; not automatically promoted into facts.
- **Explicit facts**: `memories` contains notes you save or send with `remember that ...`.
- **Document library**: `documents` contains retrieved pieces of your imported information.

The program stores all three in SQLite, but the language model itself does not permanently learn from them. Every new question includes selected context again.

## 10. Follow a complete question through the system

Suppose you import the bundled demo document and ask: **Which database does Project Orion use?**

1. `index.html` reads your typing and calls `sendMessage()`.
2. The pet state changes from `idle` to `work`.
3. Browser `fetch` posts your question to `/api/chat`.
4. Python handler validates the incoming JSON.
5. `relevant_documents()` finds the imported passage with `PostgreSQL`.
6. `relevant_memories()` retrieves any relevant notes you explicitly saved.
7. `make_messages()` builds a system message with those passages and notes.
8. `ollama_chat()` sends the complete prompt to the predownloaded local Ollama model.
9. The model's response comes back as JSON. Python stores question and answer in `chats`.
10. Browser `addMessage()` displays the response and `setMode('success', 3000)` plays the celebration animation.

**If Ollama is not installed**, step 8 fails gracefully: Python returns a helpful error, the UI displays it, and Einstein uses his debugging animation. A pet alone cannot answer questions without a language model.

## 11. Experiment in Terminal

```bash
# From the extracted Einstein_Offline_Assistant folder:
python3 test_offline.py            # Test storage and HTTP routes without any model.
python3 terminal_einstein.py       # Chat in text-only Terminal.
python3 server.py                  # Run the browser UI locally.
open http://127.0.0.1:8765        # Launch it in your browser.
```

For understanding the code fully, read the short `terminal_einstein.py` from top to bottom first, then `server.py`, then the `<script>` in `index.html`. The CSS is presentation; the Python and JavaScript sections contain the application logic.
