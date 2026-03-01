# dms_ai_bridge

Intelligent middleware between [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)
and AI frontends such as [Open WebUI](https://github.com/open-webui/open-webui) or
[AnythingLLM](https://github.com/Mintplex-Labs/anything-llm).

The bridge indexes all Paperless-ngx documents into a [Qdrant](https://qdrant.tech/) vector
database using [Ollama](https://ollama.com/) embeddings. A FastAPI server exposes a semantic
search endpoint and a webhook listener so the index stays in sync whenever Paperless-ngx adds
or updates a document.

---

## Architecture

```
Paperless-ngx ──► SyncService ──► EmbedClientOllama ──► Ollama
                       │
                       ▼
                   VectorDBQdrant ──► Qdrant
                       ▲
         Webhook ──────┤
         (POST /webhook/document)
                       │
         Query ────────┘
         (POST /query)
```

Interface hierarchy (generic → concrete):

```
DMSInterface ──► DMSPaperless
VectorDBInterface ──► VectorDBQdrant
EmbedInterface ──► EmbedClientOllama
```

---

## Implementation Status

### Phase I — Infrastructure (complete)
- FastAPI server with lifespan startup/shutdown
- `DMSInterface` (ABC) + `DMSPaperless` — Paperless-ngx REST client (API v9, `follow_redirects`)
- `VectorDBInterface` (ABC) + `VectorDBQdrant` — Qdrant REST client via httpx
- Qdrant collection auto-creation on startup
- `SyncService` — full sync (all pages) + incremental sync (single document)
- Text chunking with configurable size and overlap (default: 1 000 chars / 100 char overlap)
- `POST /webhook/document` — fire-and-forget incremental sync triggered by Paperless-ngx
- API key authentication (`X-API-Key` header) on all endpoints
- `HelperConfig` — all configuration via environment variables (never `os.getenv()` in business logic)
- Pydantic models: `Document` (generic base), `PaperlessDocument` (concrete subclass),
  `VectorPayload`, `SearchRequest`, `SearchResponse`
- `owner_id` enforced as a security invariant on every Qdrant upsert and every search filter
- One-shot sync runner: `python -m sync.sync_runner`

### Phase II — Embedding Client (complete)
- `EmbedInterface` (ABC) — template-method pattern; `do_request()`, `boot()`, `close()`,
  `embed_text()` are concrete on the interface
- `EmbedClientOllama` — implements all abstract methods for the Ollama `/api/embed` endpoint;
  supports optional Bearer-token auth, batch-aware `extract_embeddings_from_response()`,
  LLM completion endpoint (`/v1/chat/completions`), and model-info endpoint (`/api/show`)
- `SyncService._embed()` delegates to `embed_client.embed_text()` — full pipeline live

### Phase III — Query Service (complete)
- `QueryService.do_query()` — embeds the query via `EmbedClientOllama`, calls
  `VectorDBQdrant.do_scroll()` with a mandatory `owner_id` filter, returns a ranked
  `SearchResponse` with `chunk_text` for each hit
- `chunk_text` stored in every Qdrant payload during sync so results are self-contained
- `QueryService` wired into the FastAPI lifespan alongside `SyncService`
- `POST /query` returns `200 OK` with `SearchResponse` JSON

### Phase IV — Agentic Logic (pending)
- LangChain ReAct agent with multi-step reasoning
- Intent classification: metadata query vs. full-text search
- Self-querying metadata filter translation (e.g. `document_type == 'Rechnung'`)
- Result synthesis with LLM summarisation and Paperless source links

---

## Project Structure

```
dms_ai_bridge/
├── server/
│   └── api/
│       ├── api_app.py                   # FastAPI entry point (lifespan pattern)
│       ├── routers/
│       │   ├── WebhookRouter.py         # POST /webhook/document
│       │   └── QueryRouter.py           # POST /query
│       └── services/
│           └── QueryService.py          # Embed → scroll → SearchResponse
├── sync/
│   ├── sync_runner.py                   # python -m sync.sync_runner
│   └── services/
│       └── SyncService.py               # Full + incremental sync pipeline
├── shared/
│   ├── clients/
│   │   ├── DMSInterface.py              # ABC — document management system
│   │   ├── DMSPaperless.py              # Paperless-ngx implementation
│   │   ├── VectorDBInterface.py         # ABC — vector database
│   │   ├── VectorDBQdrant.py            # Qdrant implementation
│   │   ├── EmbedInterface.py            # ABC — embedding / LLM backend
│   │   └── EmbedClientOllama.py         # Ollama implementation
│   ├── dependencies/
│   │   └── auth.py                      # X-API-Key verification
│   ├── helper/
│   │   └── config_helper.py             # HelperConfig — env var reader
│   ├── logging/
│   │   └── logging_setup.py             # setup_logging()
│   └── models/
│       ├── document.py                  # Document (generic), PaperlessDocument, VectorPayload
│       └── search.py                    # SearchRequest, SearchResultItem, SearchResponse
├── .docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values.

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `info` | Logging level (`debug`, `info`, `warning`, `error`) |
| `APP_API_KEY` | — | Secret key required in `X-API-Key` header for all API calls |
| `PAPERLESS_BASE_URL` | `http://paperless:8000` | Paperless-ngx base URL |
| `PAPERLESS_API_TOKEN` | — | Paperless-ngx API token |
| `PAPERLESS_TIMEOUT` | `30` | HTTP timeout in seconds |
| `QDRANT_BASE_URL` | `http://qdrant:6333` | Qdrant REST API base URL |
| `QDRANT_COLLECTION` | `paperless_docs` | Qdrant collection name |
| `QDRANT_TIMEOUT` | `30` | HTTP timeout in seconds |
| `QDRANT_API_KEY` | — | Qdrant API key (optional) |
| `EMBED_BASE_URL` | `http://ollama:11434` | Ollama base URL |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model name |
| `EMBED_TIMEOUT` | `60` | Embedding request timeout in seconds |
| `EMBED_API_KEY` | — | Ollama Bearer token (optional) |
| `LLM_MODEL` | `llama3.2` | LLM model name (Phase IV) |
| `LLM_CONTEXT_MAX_CHARS` | `8000` | Max characters passed to LLM (Phase IV) |
| `EMBEDDING_DISTANCE` | `Cosine` | Qdrant distance metric (`Cosine`, `Dot`, `Euclid`) |

---

## Running

### With Docker Compose

```bash
cp .env.example .env
# edit .env with your settings
docker compose -f .docker/docker-compose.yml up -d
```

### Locally (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the API server
python -m uvicorn server.api.api_app:app --reload

# Run a one-shot full sync
python -m sync.sync_runner
```

---

## Testing the Sync Pipeline

### Prerequisites

All three external services must be reachable before running the sync:

| Service | What to check |
|---|---|
| **Paperless-ngx** | API token valid: `curl -H "Authorization: Token <token>" <PAPERLESS_BASE_URL>/api/documents/?page_size=1` |
| **Ollama** | Model available: `ollama list` — must show `nomic-embed-text` (or your `EMBED_MODEL`) |
| **Qdrant** | Reachable: `curl <QDRANT_BASE_URL>/healthz` |

Pull the embedding model if not yet present:

```bash
ollama pull nomic-embed-text
```

Start Qdrant locally if not using Docker Compose:

```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

### Run the full sync

```bash
# From the project root with .venv active
source .venv/bin/activate
python -m sync.sync_runner
```

Expected log output:

```
INFO  Starting full sync...
INFO  Fetching page 1 from Paperless-ngx...
INFO  Qdrant collection 'paperless_docs' already exists.
DEBUG Syncing document 42 ('Invoice ACME 2024'): 3 chunk(s).
...
INFO  Full sync complete. Documents synced: 17
```

### Verify the index in Qdrant

```bash
# Count indexed points
curl http://localhost:6333/collections/paperless_docs

# Inspect the first few points
curl -X POST http://localhost:6333/collections/paperless_docs/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 3, "with_payload": true, "with_vector": false}'
```

Each point's `payload` should contain `paperless_id`, `owner_id`, `title`, `chunk_text`, and the Paperless metadata fields.

### Test the query endpoint

With the API server running (`python -m uvicorn server.api.api_app:app --reload`):

```bash
curl -X POST http://localhost:8000/query \
  -H "X-API-Key: <APP_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Rechnung letztes Jahr", "owner_id": 1, "limit": 3}'
```

Expected response:

```json
{
  "query": "Rechnung letztes Jahr",
  "results": [
    {
      "paperless_id": 42,
      "title": "Invoice ACME 2024",
      "score": 0.87,
      "chunk_text": "..."
    }
  ],
  "total": 3
}
```

### Test incremental sync via webhook

```bash
curl -X POST http://localhost:8000/webhook/document \
  -H "X-API-Key: <APP_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"document_id": 42}'
```

Expected response: `{"status": "accepted", "document_id": 42}` — the sync runs in the background.

---

## API Endpoints

All endpoints require the `X-API-Key` header.

### `POST /webhook/document`

Called by Paperless-ngx after a document is added or updated.
Triggers an incremental sync as a background task and returns immediately.

**Request body**
```json
{ "document_id": 42 }
```

**Response**
```json
{ "status": "accepted", "document_id": 42 }
```

**Paperless-ngx webhook configuration**\
In the Paperless-ngx admin, use the built-in workflow triggers to `POST` to
`http://<bridge-host>:8080/webhook/document` with the body
`{"document_id": {{ document.pk }}}` and the `X-API-Key` header.

### `POST /query`

Natural language search against the Qdrant vector index.

**Request body**
```json
{ "query": "Invoice from ACME 2024", "owner_id": 1, "limit": 5 }
```

**Response**
```json
{
  "query": "Invoice from ACME 2024",
  "results": [
    { "paperless_id": 42, "title": "Invoice ACME", "score": 0.91, "chunk_text": "..." }
  ],
  "total": 1
}
```

---

## Security

- Every request to `/webhook/document` and `/query` must carry the `X-API-Key` header
  matching `APP_API_KEY`.
- `owner_id` is enforced unconditionally on every Qdrant upsert **and** every search
  filter — users can only retrieve vectors that belong to their Paperless-ngx user ID.
