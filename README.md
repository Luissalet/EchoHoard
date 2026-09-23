# Echo's Hoard

Everything you copy, kept on your own PC, searchable, with the things you copy often pinned. The app watches your clipboard in the background; an assistant reaches the same history through MCP, so it can answer "what was that URL I copied an hour ago", paste back the last thing you copied, or put new text on your clipboard for you.

Everything stays on the machine: SQLite for the clip history, PNG files for images, no accounts, no network.

Part of the Hoard family (see `faustus-plugin.json`).

## What it does

- **Clips** = whatever you copy: text, or an image (stored as a PNG file, with an OCR-free placeholder like "[imagen 1254×1254]" for the text). Each clip tracks kind, a one-line preview, the source app/window when known, first/last seen, how many times the same content was copied, pinned, label, tags.
- **Dedupe**: copying the same content again bumps `last_seen_at`/`times` on the existing clip instead of creating a new one.
- **Kind detection**: url, email, path, code, number, image, or plain text — from the content alone (see `echo/detect.py`).
- **Sensitive content** (privacy first): a clip that looks like a password, an API key/token, a credit card number (Luhn-checked) or an IBAN is flagged `sensitive` and its real content is replaced by a placeholder like `[oculto: contraseña]` **before it ever reaches the database** — not hidden in the UI, never stored. The assistant never receives it, not even partially. A per-app exclusion list (`ECHO_EXCLUDE_APPS`, default `KeePass,1Password,Bitwarden,keepassxc`) skips capture entirely for password managers. A pause switch stops capture (UI + tool).
- **Retention**: everything is kept for `ECHO_RETENTION_DAYS` (default 30) unless pinned; capped at `ECHO_MAX_CLIPS` (default 5000), oldest unpinned dropped first; images capped at `ECHO_MAX_IMAGE_MB` (default 200) total. A soft delete keeps a 24h undo window before the janitor purges it for good. Housekeeping runs at startup and every 10 minutes.
- **Search**: FTS5 over text/label/tags/source window title, diacritics-insensitive, prefix match, filterable by kind/pinned/time/app.
- **Capture backend** (`echo/backends/`): a small interface (`read()`, `write()`, `foreground()`) with three implementations — Windows (`ctypes` against user32/kernel32, no pywin32, polls `GetClipboardSequenceNumber` cheaply and only reads on change; retries a locked clipboard a few times, then skips that change rather than crashing), generic/cross-platform (`pyperclip`, polling text by comparing sha256; no images, no source app), and a fake backend used by tests. Selected by `ECHO_BACKEND` (`auto`/`windows`/`generic`/`fake`).

## Requirements

- Windows 10/11 (also runs on Linux/macOS with the generic backend, without images or source-app detection), Python 3.11+ (3.13 fine), Node 22 only to build the client.
- Python's `sqlite3` must have FTS5 (the official Windows builds do). The app fails loudly at startup otherwise.

## Install and run (Windows)

```bat
git clone <this repo> echo-hoard
cd echo-hoard
python -m venv venv
venv\Scripts\pip install -r requirements.txt
npm install
npm run build
venv\Scripts\python -m echo
```

Open http://127.0.0.1:5188, go to **Historial** to see and search what you've copied, **Fijados** for your pinned clips, and **Estado** to pause/resume watching and purge old clips.

- `python scripts/launch.py` starts the app on a free port and opens the browser.
- `python scripts/dev.py` runs uvicorn `--reload` + the Vite dev server (proxying `/api`).

## Configuration (environment)

| Variable | Default | Meaning |
| --- | --- | --- |
| `ECHO_PORT` / `PORT` | `5188` | Preferred port; `PORT_STRICT=1` pins it, otherwise the first free port from there. |
| `ECHO_DATA_DIR` | `<repo>/data` | Database (`echo-hoard.db`), `images/`, `mcp-token`. |
| `ECHO_BACKEND` | `auto` | `auto` \| `windows` \| `generic` \| `fake`. |
| `ECHO_AUTOSTART` | `1` | `0` disables starting the watcher automatically with the app. |
| `ECHO_RETENTION_DAYS` | `30` | Unpinned clips older than this are purged; `0` keeps forever. |
| `ECHO_MAX_CLIPS` | `5000` | Cap on unpinned clips; oldest dropped first. |
| `ECHO_MAX_IMAGE_MB` | `200` | Cap on total image storage; oldest images dropped first. |
| `ECHO_EXCLUDE_APPS` | `KeePass,1Password,Bitwarden,keepassxc` | Comma-separated process names never captured. |
| `ECHO_ALLOWED_HOSTS` | | Extra host names accepted behind a tunnel (see below). |

### Access from your phone (behind a tunnel)

The server binds 127.0.0.1 and only answers requests whose `Host` is `localhost`, `127.0.0.1` or `[::1]`. To reach it from your phone through a tunnel that fronts the app, list the extra host names in `ECHO_ALLOWED_HOSTS`, comma-separated, exact names or `*.suffix`: `ECHO_ALLOWED_HOSTS=my-pc.example,*.ts.net`. Port and letter case are ignored, and the `Origin` of API calls must resolve to one of those hosts too (any scheme or port). Cross-site *fetches* are still refused; opening the app from another page (a link, a bookmarklet, the share sheet) is a normal navigation and works.

Once opened through the tunnel, the browser offers to install it (PWA).

## API

All JSON; errors are `{ "error": "..." }`.

- `GET /api/health` → `{ service: "echo-hoard", version, dataDirConfigured }`; `GET /api/status`
- `POST /api/pause`, `POST /api/resume`
- `GET /api/clips?kind&pinned&since&until&app&limit&offset`, `POST /api/clips` `{text}` (sets the clipboard AND stores it), `GET/PATCH/DELETE /api/clips/{id}`, `POST /api/clips/{id}/restore`, `POST /api/clips/{id}/copy` (put it back on the clipboard), `GET /api/clips/{id}/image`
- `DELETE /api/clips?before=<iso>` (bulk purge, irreversible; UI confirms)
- `GET /api/search?q&kind&pinned&since&until&app&limit`
- `GET /api/agent/tools` (catalog + instructions), `POST /api/agent/call` (Bearer token from `data/mcp-token`)

## MCP tools

`mcp_server.py` is a stdio bridge: it fetches the tool list from the running app and proxies every call to `POST /api/agent/call` with the token from `<DATA_DIR>/mcp-token`. It never opens the database. Env: `ECHO_URL`, `ECHO_TOKEN_FILE` (or `ECHO_TOKEN`).

| Tool | What it does |
| --- | --- |
| `clip_recent` | The most recently copied clips. Sensitive ones come back as `[oculto]`. |
| `clip_search` | Full-text search over the clipboard history. |
| `clip_get` | The full text of one clip (paginated); refuses sensitive clips outright. |
| `clip_set` | Put text on the clipboard and store it as a clip (write, idempotent by content). |
| `clip_copy` | Put an existing clip back on the clipboard (write; refuses sensitive unless `allow_sensitive`, and even then never returns the content). |
| `clip_pin` | Pin/unpin and set label/tags (write). |
| `clip_delete` | Soft-delete a clip (write, destructive; 24h undo window). |
| `clip_status` | Whether Echo is watching, counts, retention config. |
| `clip_capture` | Pause/resume watching (write). |

The shipped instructions tell the assistant: this is the user's own data, quote it only when asked; a sensitive clip is never returned, not even partially, and never ask the user to unhide one; `clip_set` changes what the user will paste next, so say what was put there; prefer `clip_search` with a time window over listing everything; never read the data folder or database directly.

## Tests

```bat
venv\Scripts\python -m pytest -q
```

Covers kind detection (URL/email/path/code/number/text table), sensitive detection (passwords by window title and by length, API key prefixes, JWT-like strings, Luhn-checked card numbers, IBAN checksum, and the negatives: a normal sentence, a plain 16-char word, a URL), dedupe bumping `times`, retention/cap/janitor with an injected clock, FTS with accents, pin/label/tags, soft delete + restore + purge, the fake backend driving the watcher end to end (push three contents, one a duplicate, → two clips, one with `times: 2`), pause/resume, the HTTP API, agent tools through `/api/agent/call` with the token (including the sensitive refusals), the request guard, the PWA endpoints, and a subprocess end-to-end test through the MCP stdio client. No test touches the real clipboard.

## License

MIT — Luissalet.
