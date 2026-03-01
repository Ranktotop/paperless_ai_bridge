# dms_ai_bridge

Intelligent middleware between Document Management Systems (e.g. Paperless-ngx) and AI
frontends (OpenWebUI, AnythingLLM) via semantic search.

---

## Project Goal

Users ask questions in natural language about their documents. The bridge indexes all
documents from a DMS into a vector database and answers search queries through a FastAPI
server. In Phase IV a LangChain ReAct agent takes over intent classification and result
synthesis.

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
FastAPI (POST /query)
  │── LLMClientInterface.do_embed()    ← embed query text
  │── RAGClientInterface.do_scroll()   ← filter by owner_id + vector
  └── LLMClientInterface.do_chat()     ← Phase IV synthesis
```

Additional DMS backends, RAG backends, and LLM providers can be added without touching
the core pipeline — new implementations satisfy the relevant interface and the factory
picks them up automatically.

---

## Implementation Phases

| Phase | Scope | Status |
|---|---|---|
| I | Shared infrastructure, DMS client, RAG client, SyncService | Complete |
| II | LLM client (embedding via Ollama) | Complete |
| III | FastAPI server — POST /webhook/document + POST /query (scroll-based) | Pending |
| IV | LangChain ReAct agent, vector similarity search, LLM synthesis | Pending |

---

## Generic Interfaces

All HTTP clients inherit from `ClientInterface`. The three domain interfaces extend it.

### `ClientInterface` (`shared/clients/ClientInterface.py`)

Base ABC for every HTTP client. Provides:
- `boot()` / `close()` — create and destroy `httpx.AsyncClient`
- `do_request(method, endpoint, **kwargs)` — authenticated HTTP call with timeout
- `do_healthcheck()` — GET to `_get_endpoint_healthcheck()`
- `get_config_val(raw_key)` — builds namespaced env key `{CLIENT_TYPE}_{ENGINE_NAME}_{KEY}`

Every subclass must implement:
`_get_engine_name()`, `_get_base_url()`, `_get_auth_header()`,
`_get_endpoint_healthcheck()`, `_get_required_config()`

---

### `DMSClientInterface` (`shared/clients/dms/DMSClientInterface.py`)

ABC for all Document Management System backends.

Key methods:
- `fill_cache()` — paginated fetch of all documents and metadata; builds
  `DocumentHighDetails` objects with fully resolved names
- `get_enriched_documents() -> list[DocumentHighDetails]`
- `get_documents()`, `get_correspondents()`, `get_tags()`, `get_owners()`,
  `get_document_types()` — cache accessors

`DocumentHighDetails` (canonical output model):
```
engine, id
correspondent_id, document_type_id, tag_ids, owner_id   ← raw IDs
correspondent, document_type, tags, owner                ← resolved names
title, content, created_date, mime_type, file_name
```

Current implementation: `DMSClientPaperless`
Factory: `DMSClientManager` — reads `DMS_ENGINES` from env

---

### `RAGClientInterface` (`shared/clients/rag/RAGClientInterface.py`)

ABC for all vector database backends.

Key methods:
- `do_upsert_points(points: list[dict])` — insert/replace with deterministic UUIDs
- `do_scroll(filters, limit, with_payload, with_vector) -> ScrollResult`
- `do_delete_points_by_filter(filters)`
- `do_existence_check() -> bool`
- `do_create_collection(vector_size: int, distance: str)`

`VectorPoint` payload schema (`shared/clients/rag/models/VectorPoint.py`):
```
dms_engine, dms_doc_id, chunk_index
title, owner_id*                     (* MANDATORY — never None)
created, chunk_text
label_ids, label_names               ← tags
category_id, category_name          ← correspondent
type_id, type_name                   ← document type
owner_username
```

Point IDs are deterministic:
`uuid.uuid5(uuid.NAMESPACE_OID, f"{engine}:{doc_id}:{chunk_index}")`

Current implementation: `RAGClientQdrant`
Factory: `RAGClientManager` — reads `RAG_ENGINES` from env

---

### `LLMClientInterface` (`shared/clients/llm/LLMClientInterface.py`)

Unified ABC for inference backends — covers both embedding and chat/completion because
providers like Ollama support both natively.

Embedding methods (concrete):
- `do_embed(texts: str | list[str]) -> list[list[float]]`
- `do_fetch_embedding_vector_size() -> tuple[int, str]` — (dimension, distance_metric)
- `do_fetch_models() -> httpx.Response`

Chat/completion methods (concrete):
- `do_chat(messages: list[dict]) -> str` — returns assistant reply text

Abstract hooks subclasses must implement:
```
# embedding
get_embed_payload(texts)           extract_embeddings_from_response(response)
extract_vector_size_from_model_info(model_info)
get_endpoint_embedding()           get_endpoint_model_details()
_get_endpoint_models()

# chat
get_chat_payload(messages)         extract_chat_response(response)
_get_endpoint_chat()
```

Instance attributes (set in `__init__`):
- `self.embed_model` — reads `LLM_MODEL_EMBEDDING`
- `self.embed_distance` — reads `LLM_DISTANCE` (default: `Cosine`)
- `self.embed_model_max_chars` — reads `LLM_MODEL_EMBEDDING_MAX_CHARS`
- `self.chat_model` — reads `LLM_MODEL_CHAT` (optional; falls back to `embed_model`)

Current implementation: `LLMClientOllama`
Factory: `LLMClientManager` — reads `LLM_ENGINE` from env

---

## Directory Structure

```
dms_ai_bridge/
├── .claude/
│   ├── agents/                          ← agent definitions (see Agent Responsibilities)
│   └── settings.json
├── CLAUDE.md                            ← this file
├── .env / .env.example
├── requirements.txt
├── start.sh
├── shared/
│   ├── clients/
│   │   ├── ClientInterface.py           ← base ABC (lifecycle, auth, do_request)
│   │   ├── dms/
│   │   │   ├── DMSClientInterface.py    ← DMS ABC
│   │   │   ├── DMSClientManager.py      ← factory (reflection-based)
│   │   │   ├── models/
│   │   │   │   ├── Document.py          ← DocumentBase/Details/HighDetails
│   │   │   │   ├── Correspondent.py
│   │   │   │   ├── Tag.py
│   │   │   │   ├── Owner.py
│   │   │   │   └── DocumentType.py
│   │   │   └── paperless/
│   │   │       ├── DMSClientPaperless.py
│   │   │       └── models.py
│   │   ├── llm/
│   │   │   ├── LLMClientInterface.py    ← unified ABC (embed + chat)
│   │   │   ├── LLMClientManager.py      ← factory (reflection-based)
│   │   │   └── ollama/
│   │   │       └── LLMClientOllama.py
│   │   └── rag/
│   │       ├── RAGClientInterface.py    ← RAG ABC
│   │       ├── RAGClientManager.py      ← factory (reflection-based)
│   │       ├── models/
│   │       │   ├── VectorPoint.py       ← upsert payload (owner_id mandatory)
│   │       │   └── Scroll.py            ← scroll result model
│   │       └── qdrant/
│   │           └── RAGClientQdrant.py
│   ├── helper/
│   │   └── HelperConfig.py              ← central env var reader
│   ├── logging/
│   │   └── logging_setup.py             ← setup_logging(), ColorLogger
│   └── models/
│       └── config.py                    ← EnvConfig Pydantic model
├── services/
│   └── dms_rag_sync/
│       ├── SyncService.py               ← DMS → embed → RAG orchestration
│       └── dms_rag_sync.py              ← entry point (python -m services.dms_rag_sync)
└── server/                              ← Phase III/IV — not yet created
    └── api/
        ├── api_app.py                   ← FastAPI entry point with lifespan
        ├── routers/
        │   ├── WebhookRouter.py         ← POST /webhook/document
        │   └── QueryRouter.py           ← POST /query
        ├── services/
        │   └── QueryService.py          ← embed + scroll + (Phase IV) chat
        ├── dependencies/
        │   └── auth.py                  ← X-API-Key verification
        └── models/
            ├── requests.py              ← WebhookRequest, SearchRequest
            └── responses.py             ← SearchResultItem, SearchResponse
```

---

## Agent Responsibilities

Six specialised agents own distinct subsystems. Invoke the correct agent for any task
touching that subsystem. Agents that own interfaces must coordinate before changing
public method signatures.

### `infra-agent` — Shared Infrastructure
**Model:** `claude-opus-4-6`

**Owns:**
- `shared/helper/HelperConfig.py` — central env var reader
- `shared/logging/logging_setup.py` — `setup_logging()`, `ColorLogger`, `CustomFormatter`
- `shared/models/config.py` — `EnvConfig` Pydantic model
- `shared/clients/ClientInterface.py` — base ABC for all HTTP clients
- `.docker/Dockerfile`, `.docker/docker-compose.yml`
- `requirements.txt`, `start.sh`

**Invoke when:**
changing `HelperConfig` public API, adding logging features, modifying the base HTTP
client lifecycle (`boot`/`close`/`do_request`), updating Python dependencies, or
adjusting Docker configuration.

**Critical:** all other agents depend on this agent's outputs. Treat every change as
potentially breaking for the whole team. Never remove or rename public methods on
`HelperConfig` or `ClientInterface` without updating all subclasses in the same commit.

---

### `dms-agent` — DMS Client Subsystem
**Model:** `claude-sonnet-4-6`

**Owns:**
- `shared/clients/dms/DMSClientInterface.py`
- `shared/clients/dms/DMSClientManager.py`
- `shared/clients/dms/models/` (Document, Correspondent, Tag, Owner, DocumentType)
- `shared/clients/dms/paperless/DMSClientPaperless.py`
- `shared/clients/dms/paperless/models.py`

**Invoke when:**
adding a new DMS backend, modifying how documents are fetched or cached, changing
DMS data models, debugging Paperless-ngx API issues, or adding new metadata fields
to `DocumentHighDetails`.

**Key rules:**
- `fill_cache()` must resolve ALL foreign keys before building `DocumentHighDetails` —
  never leave names as `None` when an ID is set
- Never trigger OCR — only read the `content` field Paperless already provides
- If a DMS endpoint is unavailable during cache fill, log WARNING and continue; do not abort
- Model hierarchy `DocumentBase → DocumentDetails → DocumentHighDetails` must not be flattened
- Adding `DocumentHighDetails` fields requires coordination with sync-agent and rag-agent

---

### `rag-agent` — RAG / Vector DB Subsystem
**Model:** `claude-sonnet-4-6`

**Owns:**
- `shared/clients/rag/RAGClientInterface.py`
- `shared/clients/rag/RAGClientManager.py`
- `shared/clients/rag/models/VectorPoint.py`
- `shared/clients/rag/models/Scroll.py`
- `shared/clients/rag/qdrant/RAGClientQdrant.py`

**Invoke when:**
adding a new vector DB backend, modifying upsert or search behaviour, changing the
`VectorPoint` payload schema, debugging Qdrant issues, or adding new filter capabilities
to `do_scroll()`.

**Key rules:**
- **Security invariant (non-negotiable):** every upsert must have `owner_id` set; every
  user-facing scroll must filter by `owner_id`. Raise `ValueError` on upsert if `owner_id`
  is `None`.
- Point IDs must be deterministic (`uuid5`) — never use random UUIDs
- `VectorPoint` field names are a stable contract read by api-agent from raw Qdrant
  payload dicts — coordinate with sync-agent and api-agent before any field rename

---

### `embed-llm-agent` — LLM / Embedding Client Subsystem
**Model:** `claude-sonnet-4-6`

**Owns:**
- `shared/clients/llm/LLMClientInterface.py`
- `shared/clients/llm/LLMClientManager.py`
- `shared/clients/llm/ollama/LLMClientOllama.py`

**Invoke when:**
adding a new LLM/embedding provider, changing how texts are embedded or chat messages
are sent, debugging embedding or chat API responses, adjusting model configuration
(distance metric, vector size discovery, chat model), or implementing a new provider.

**Key rules:**
- `do_embed()` always returns `list[list[float]]` — even for a single string; callers
  access `result[0]` for the first vector
- Batch splitting is the caller's responsibility — `do_embed()` sends the full list as
  one request
- `do_chat()` messages use the OpenAI format (`role`/`content` dicts)
- `get_chat_payload()` implementations must set `"stream": False`
- Changing `do_fetch_embedding_vector_size()` tuple order: notify sync-agent and api-agent
- Changing `do_chat()` return type: notify api-agent

**Adding a new provider:**
1. Create `shared/clients/llm/{engine_lower}/LLMClient{Engine}.py`
2. Inherit `LLMClientInterface`, implement all abstract hooks (both embedding and chat)
3. Set `LLM_ENGINE={Engine}` in env — factory loads via reflection

---

### `sync-agent` — DMS-to-RAG Sync Pipeline
**Model:** `claude-sonnet-4-6`

**Owns:**
- `services/dms_rag_sync/SyncService.py`
- `services/dms_rag_sync/dms_rag_sync.py`

**Invoke when:**
changing chunking strategy or constants, tuning batch sizes or concurrency, fixing
sync bugs, modifying `do_incremental_sync()`, or adjusting orphan cleanup logic.

**Key rules:**
- `do_incremental_sync(document_id: int) -> None` is the public API contract with
  api-agent's `WebhookRouter` — never change this signature without notifying api-agent
- Skip documents without `owner_id` (security gate — no silent writes)
- Chunking: character-level only (`CHUNK_SIZE=1000`, `CHUNK_OVERLAP=100`), no tokenisation
- Concurrency: always `asyncio.Semaphore(DOC_CONCURRENCY=5)` — never unbounded `gather()`
- Upsert in batches of `UPSERT_BATCH_SIZE=100` — Qdrant rejects oversized payloads
- After full sync: scroll RAG for all `dms_engine` vectors, delete any whose `dms_doc_id`
  is absent from the current DMS document set (orphan cleanup)

---

### `api-agent` — FastAPI Server (Phase III/IV)
**Model:** `claude-opus-4-6`

**Owns:** (all files pending — must be created)
- `server/api/api_app.py` — FastAPI entry point with lifespan
- `server/api/routers/WebhookRouter.py` — `POST /webhook/document`
- `server/api/routers/QueryRouter.py` — `POST /query`
- `server/api/services/QueryService.py` — embed → scroll → `SearchResponse`
- `server/api/dependencies/auth.py` — `X-API-Key` verification
- `server/api/models/requests.py` — `WebhookRequest`, `SearchRequest`
- `server/api/models/responses.py` — `SearchResultItem`, `SearchResponse`

**Invoke when:**
creating the FastAPI app, adding routes, building `QueryService`, integrating LangChain
for Phase IV, or implementing auth middleware.

**Key rules:**
- All route handlers: `async def`
- Clients accessed only via `request.app.state.*` — never instantiate in handlers
- `owner_id` is mandatory on `SearchRequest` — enforced at Pydantic model level
- Use `BackgroundTasks` for the webhook — never `asyncio.create_task()` in route handlers
- Every subdirectory under `server/api/` needs `__init__.py` for uvicorn module resolution
- Phase III: `POST /query` uses `do_scroll()` with payload filter, `score=0.0` placeholder
- Phase IV: use `WebSearch` to look up current `create_react_agent` API before implementing

**API contracts:**
```
POST /webhook/document
  Request:  {"document_id": 42}
  Response: {"status": "accepted", "document_id": 42}
  Action:   background_tasks.add_task(sync_service.do_incremental_sync, document_id)

POST /query
  Request:  {"query": "...", "owner_id": 1, "limit": 5}
  Response: {"query": "...", "results": [...], "total": N}
```

---

## Coding Conventions

### Interface-first
New backends are ALWAYS created by implementing the relevant interface. Never create
direct dependencies between concrete implementations.

### Constructors
```python
def __init__(self, helper_config: HelperConfig) -> None:
    super().__init__(helper_config)        # required for ClientInterface subclasses
    self.logging = helper_config.get_logger()
```

### Method prefixes
| Prefix | Meaning |
|---|---|
| `do_*` | async action with side effects (I/O, state change) |
| `get_*` | pure getter — no I/O, no side effects |
| `is_*` | boolean check |
| `_read_*` | private reader |

### Class section banners (in this order)
```python
##########################################
############# LIFECYCLE ##################
##########################################

##########################################
############# CHECKER ####################
##########################################

##########################################
############## GETTER ####################
##########################################

##########################################
############# REQUESTS ###################
##########################################

##########################################
############### CORE #####################
##########################################

##########################################
############# HELPERS ####################
##########################################
```

### Logging — always %-style, never f-strings
```python
# correct
self.logging.info("Syncing document %d ('%s'): %d chunk(s)", doc_id, title, n)

# WRONG
self.logging.info(f"Syncing document {doc_id}")
```

### Type annotations
PEP 604 union syntax: `str | None` — never `Optional[str]`

### Configuration keys
Pattern: `{CLIENT_TYPE}_{ENGINE_NAME}_{SETTING}`

```
DMS_PAPERLESS_BASE_URL     DMS_PAPERLESS_API_KEY
RAG_QDRANT_BASE_URL        RAG_QDRANT_COLLECTION
LLM_OLLAMA_BASE_URL        LLM_OLLAMA_API_KEY
LLM_MODEL_EMBEDDING        LLM_MODEL_CHAT         LLM_DISTANCE
```

Never call `os.getenv()` directly in business logic — always use `HelperConfig`.

### Async
No `requests`, no synchronous I/O. Exclusively `httpx.AsyncClient` for all HTTP calls.

### Security invariant
`owner_id` MUST be present in every Qdrant upsert payload and every search filter.
Documents without `owner_id` are skipped at sync time — no silent writes.

### Language
All code, variable names, comments, docstrings, and log messages: **English**.

---

## Agent Selection Guide

| Trigger | Agent |
|---|---|
| `HelperConfig`, `ClientInterface`, logging, Docker, `requirements.txt` | `infra-agent` |
| Paperless API, `DMSClientInterface`, `DocumentHighDetails`, DMS models | `dms-agent` |
| Qdrant, `RAGClientInterface`, `VectorPoint`, scroll filters | `rag-agent` |
| Ollama, `LLMClientInterface`, embedding, chat, new LLM provider | `embed-llm-agent` |
| Chunking, sync pipeline, `SyncService`, orphan cleanup | `sync-agent` |
| FastAPI routes, `QueryService`, webhook, auth, Phase III/IV server | `api-agent` |

**Cross-cutting changes** (e.g. adding a field to `VectorPoint`, changing a `ClientInterface`
abstract method) require coordinating the relevant agents before merging — see each agent's
"Coordination points" section in `.claude/agents/`.
