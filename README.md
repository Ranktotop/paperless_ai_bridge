# dms_ai_bridge

Intelligent middleware between Document Management Systems (e.g.
[Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx)) and AI frontends such as
[Open WebUI](https://github.com/open-webui/open-webui) or
[AnythingLLM](https://github.com/Mintplex-Labs/anything-llm).

The bridge indexes all documents from a DMS into a [Qdrant](https://qdrant.tech/) vector
database using [Ollama](https://ollama.com/) embeddings. A FastAPI server (Phase III) will
expose a semantic search endpoint and a webhook listener so the index stays in sync whenever
a document is added or updated.

---

## Architecture

```
DMS (Paperless-ngx)
  │
  ▼
DMSClientInterface ──► fill_cache() ──► DocumentHighDetails[]
  │
  ▼
SyncService ──► chunk() ──► LLMClientInterface.do_embed() ──► vectors[]
  │                                          │
  ▼                                          ▼
RAGClientInterface.do_upsert_points()   Ollama /api/embed
  │
  ▼
Qdrant (vector store, owner_id-filtered)
  ▲
  │
FastAPI (POST /query)           ← Phase III
  │── LLMClientInterface.do_embed()
  │── RAGClientInterface.do_scroll()
  └── LLMClientInterface.do_chat()    ← Phase IV
```

Interface hierarchy (generic → concrete):

```
ClientInterface
  ├── DMSClientInterface  ──► DMSClientPaperless
  ├── RAGClientInterface  ──► RAGClientQdrant
  └── LLMClientInterface  ──► LLMClientOllama
```

Additional DMS backends, RAG backends, and LLM providers can be added without touching the
core pipeline — new implementations satisfy the relevant interface and the factory picks them
up automatically via reflection.

---

## Implementation Status

| Phase | Scope | Status |
|---|---|---|
| I | Shared infrastructure, DMS client, RAG client, SyncService | Complete |
| II | LLM client — embedding + chat via Ollama | Complete |
| III | FastAPI server — `POST /webhook/document` + `POST /query` | Pending |
| IV | LangChain ReAct agent, vector similarity search, LLM synthesis | Pending |

### Phase I — Infrastructure (complete)

- `ClientInterface` — base ABC for all HTTP clients (`boot`/`close`/`do_request`/`do_healthcheck`)
- `DMSClientInterface` (ABC) + `DMSClientPaperless` — Paperless-ngx REST client
  - `fill_cache()` — paginated fetch of all documents with fully resolved metadata
  - `DocumentHighDetails` — canonical output model with resolved correspondent, tags, type, owner
- `RAGClientInterface` (ABC) + `RAGClientQdrant` — Qdrant REST client via httpx
  - Deterministic point IDs (`uuid5(engine:doc_id:chunk_index)`)
  - `do_upsert_points()`, `do_scroll()`, `do_delete_points_by_filter()`, `do_create_collection()`
- `SyncService` — full sync (all documents) + incremental sync (single document)
  - Text chunking: character-level, `CHUNK_SIZE=1000`, `CHUNK_OVERLAP=100`
  - `asyncio.Semaphore(DOC_CONCURRENCY=5)` — bounded concurrency
  - Upsert batches of 100 — Qdrant-safe payload sizes
  - Orphan cleanup after full sync
- `HelperConfig` — all configuration via environment variables, never `os.getenv()` in business logic
- `owner_id` enforced as a security invariant on every Qdrant upsert and every search filter

### Phase II — LLM Client (complete)

- `LLMClientInterface` (ABC) — unified interface for embedding and chat/completion
  - `do_embed(texts)` → `list[list[float]]` — always returns a list, even for a single string
  - `do_fetch_embedding_vector_size()` → `(dimension, distance_metric)`
  - `do_chat(messages)` → `str` — OpenAI-format message dicts
- `LLMClientOllama` — implements all abstract hooks for Ollama
  - Embedding: `POST /api/embed`
  - Chat: `POST /api/chat` with `"stream": False`
  - Vector size discovery via `POST /api/show`
  - Optional Bearer-token auth

### Phase III — FastAPI Server (pending)

- `POST /webhook/document` — fire-and-forget incremental sync via `BackgroundTasks`
- `POST /query` — embed query → `do_scroll()` with `owner_id` filter → `SearchResponse`
- `X-API-Key` authentication on all endpoints

### Phase IV — Agentic Logic (pending)

- LangChain ReAct agent with multi-step reasoning
- Intent classification: metadata query vs. full-text search
- Result synthesis with LLM summarisation and DMS source links

---

## Project Structure

```
dms_ai_bridge/
├── CLAUDE.md                            # Architecture reference and coding conventions
├── .env / .env.example
├── requirements.txt
├── start.sh                             # Uvicorn launcher (Phase III)
├── shared/
│   ├── clients/
│   │   ├── ClientInterface.py           # Base ABC (lifecycle, auth, do_request)
│   │   ├── dms/
│   │   │   ├── DMSClientInterface.py    # DMS ABC
│   │   │   ├── DMSClientManager.py      # Factory (reflection-based)
│   │   │   ├── models/                  # Document, Correspondent, Tag, Owner, DocumentType
│   │   │   └── paperless/
│   │   │       └── DMSClientPaperless.py
│   │   ├── llm/
│   │   │   ├── LLMClientInterface.py    # Unified ABC (embed + chat)
│   │   │   ├── LLMClientManager.py      # Factory (reflection-based)
│   │   │   └── ollama/
│   │   │       └── LLMClientOllama.py
│   │   └── rag/
│   │       ├── RAGClientInterface.py    # RAG ABC
│   │       ├── RAGClientManager.py      # Factory (reflection-based)
│   │       ├── models/                  # VectorPoint, Scroll
│   │       └── qdrant/
│   │           └── RAGClientQdrant.py
│   ├── helper/
│   │   └── HelperConfig.py              # Central env var reader
│   ├── logging/
│   │   └── logging_setup.py             # setup_logging(), ColorLogger
│   └── models/
│       └── config.py                    # EnvConfig Pydantic model
├── services/
│   └── dms_rag_sync/
│       ├── SyncService.py               # DMS → embed → RAG orchestration
│       └── dms_rag_sync.py              # Entry point (python -m services.dms_rag_sync.dms_rag_sync)
└── server/                              # Phase III/IV — not yet created
    └── api/
        ├── api_app.py
        ├── routers/
        │   ├── WebhookRouter.py         # POST /webhook/document
        │   └── QueryRouter.py           # POST /query
        ├── services/
        │   └── QueryService.py
        ├── dependencies/
        │   └── auth.py                  # X-API-Key verification
        └── models/
            ├── requests.py
            └── responses.py
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values.

### General

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `info` | Logging level (`debug`, `info`, `warning`, `error`) |
| `APP_API_KEY` | — | Secret key required in `X-API-Key` header (Phase III) |

### DMS

| Variable | Default | Description |
|---|---|---|
| `DMS_ENGINES` | — | Comma-separated list of DMS backends, e.g. `[paperless]` |
| `DMS_TIMEOUT` | `30` | HTTP timeout in seconds |
| `DMS_PAPERLESS_BASE_URL` | — | Paperless-ngx base URL |
| `DMS_PAPERLESS_API_KEY` | — | Paperless-ngx API token |

### RAG (Qdrant)

| Variable | Default | Description |
|---|---|---|
| `RAG_ENGINES` | — | Comma-separated list of RAG backends, e.g. `[qdrant]` |
| `RAG_TIMEOUT` | `30` | HTTP timeout in seconds |
| `RAG_QDRANT_BASE_URL` | — | Qdrant REST API base URL |
| `RAG_QDRANT_COLLECTION` | — | Qdrant collection name |
| `RAG_QDRANT_API_KEY` | — | Qdrant API key (optional) |

### LLM (Ollama)

| Variable | Default | Description |
|---|---|---|
| `LLM_ENGINE` | — | LLM backend, e.g. `ollama` |
| `LLM_TIMEOUT` | `60` | HTTP timeout in seconds |
| `LLM_OLLAMA_BASE_URL` | — | Ollama base URL |
| `LLM_OLLAMA_API_KEY` | — | Ollama Bearer token (optional) |
| `LLM_MODEL_EMBEDDING` | — | Embedding model name (e.g. `nomic-embed-text`) |
| `LLM_MODEL_EMBEDDING_MAX_CHARS` | — | Max characters per chunk passed to the embedding model |
| `LLM_MODEL_CHAT` | — | Chat model name (e.g. `llama3.2`); optional, falls back to `LLM_MODEL_EMBEDDING` |
| `LLM_DISTANCE` | `Cosine` | Qdrant distance metric (`Cosine`, `Dot`, `Euclid`) |

---

## Running

### Full sync (one-shot)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in .env

python -m services.dms_rag_sync.dms_rag_sync
```

Expected log output:

```
INFO  Starting full sync...
INFO  Fetching documents from Paperless-ngx...
DEBUG Syncing document 42 ('Invoice ACME 2024'): 3 chunk(s).
...
INFO  Full sync complete.
```

### API server (Phase III — pending)

```bash
# Once Phase III is implemented:
bash start.sh
# or directly:
uvicorn server.api.api_app:app --host 0.0.0.0 --port 8080
```

### With Docker Compose

```bash
cp .env.example .env
# edit .env with your settings
docker compose -f .docker/docker-compose.yml up -d
```

---

## Verifying the Index

After a successful sync, inspect the Qdrant collection directly:

```bash
# Count indexed points
curl http://localhost:6333/collections/<RAG_QDRANT_COLLECTION>

# Inspect the first few points
curl -X POST http://localhost:6333/collections/<RAG_QDRANT_COLLECTION>/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 3, "with_payload": true, "with_vector": false}'
```

Each point's payload contains `dms_doc_id`, `owner_id`, `title`, `chunk_text`, and the
resolved metadata fields (`correspondent`, `tags`, `category`, etc.).

---

## API Endpoints (Phase III — pending)

All endpoints require the `X-API-Key` header matching `APP_API_KEY`.

### `POST /webhook/document`

Called by Paperless-ngx after a document is added or updated.
Triggers an incremental sync as a background task and returns immediately.

**Request**
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

**Request**
```json
{ "query": "Invoice from ACME 2024", "owner_id": 1, "limit": 5 }
```

**Response**
```json
{
  "query": "Invoice from ACME 2024",
  "results": [
    { "dms_doc_id": 42, "title": "Invoice ACME", "score": 0.91, "chunk_text": "..." }
  ],
  "total": 1
}
```

---

## Security

- Every request to `/webhook/document` and `/query` must carry the `X-API-Key` header
  matching `APP_API_KEY`.
- `owner_id` is enforced unconditionally on every Qdrant upsert **and** every search
  filter — users can only retrieve vectors that belong to their own DMS user ID.
- Documents without `owner_id` are skipped at sync time — no silent writes to Qdrant.
