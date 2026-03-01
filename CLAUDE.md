# paperless_ai_bridge

Intelligente Middleware zwischen DMS-Systemen (z. B. Paperless-ngx) und KI-Frontends
(OpenWebUI, AnythingLLM) über semantische Suche.

## Ziel

Nutzer stellen Fragen in natürlicher Sprache zu ihren Dokumenten. Die Bridge indexiert alle
Dokumente eines DMS in eine Vektordatenbank (RAG) und beantwortet Suchanfragen mit einem
FastAPI-Server. Langfristig übernimmt ein LangChain-ReAct-Agent die Intent-Klassifikation
und Ergebnis-Synthese.

---

## Architektur

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
  │── LLMClientInterface.do_embed()    ← query text
  │── RAGClientInterface.do_scroll()   ← owner_id filter + vector
  └── LLMClientInterface.do_chat()     ← Phase IV synthesis
```

Weitere DMS, RAG-Backends und LLM-Provider können ohne Änderung am Core hinzugefügt werden.

---

## Generische Interfaces

### `ClientInterface` (`shared/clients/ClientInterface.py`)
Basis-ABC für alle HTTP-Clients. Lifecycle (`boot()` / `close()`), `do_request()`,
`do_healthcheck()`, Config-Helper (`get_config_val()`).
Alle anderen Interfaces erben von dieser Klasse.

### `DMSClientInterface` (`shared/clients/dms/DMSClientInterface.py`)
ABC für alle DMS-Backends. Definiert:
- Pagination über alle Ressourcentypen (Dokumente, Korrespondenten, Tags, Besitzer, Typen)
- Mehrschichtiges Caching (raw + enriched)
- `fill_cache()` → befüllt alle Caches und baut `DocumentHighDetails`-Objekte
- `get_enriched_documents()` → vollständig aufgelöste Dokument-Objekte mit Namen

Concrete Implementations: `DMSClientPaperless`
Factory: `DMSClientManager` (liest `DMS_ENGINES` aus Umgebungsvariablen)

### `RAGClientInterface` (`shared/clients/rag/RAGClientInterface.py`)
ABC für alle Vektordatenbank-Backends. Definiert:
- `do_upsert_points(points)` — Vektoren mit Payloads einfügen/aktualisieren
- `do_scroll(filters, limit, with_payload, with_vector)` — gefilterte Suche
- `do_delete_points_by_filter(filters)` — Löschen nach Filter
- `do_existence_check()` / `do_create_collection(vector_size, distance)`

Concrete Implementations: `RAGClientQdrant`
Factory: `RAGClientManager` (liest `RAG_ENGINES`)

### `LLMClientInterface` (`shared/clients/llm/LLMClientInterface.py`)
Unified ABC für Embedding- und Chat/Completion-Backends. Definiert:
- `do_embed(text_or_list)` → `list[list[float]]`
- `do_fetch_embedding_vector_size()` → `(int, str)` — Dimension und Distanzmetrik
- `do_fetch_models()` → verfügbare Modelle
- `do_chat(messages)` → Antwort-String

Concrete Implementations: `LLMClientOllama`
Factory: `LLMClientManager` (liest `LLM_ENGINE`)


---

## Verzeichnisstruktur

```
paperless_ai_bridge/
├── .claude/
│   ├── agents/                          ← Agenten-Definitionen (diese Dateien)
│   └── settings.json
├── CLAUDE.md                            ← Diese Datei
├── .env / .env.example
├── README.md
├── requirements.txt
├── start.sh
├── shared/
│   ├── clients/
│   │   ├── ClientInterface.py           ← Basis-ABC (HTTP lifecycle, auth, do_request)
│   │   ├── dms/
│   │   │   ├── DMSClientInterface.py    ← DMS-ABC
│   │   │   ├── DMSClientManager.py      ← Factory
│   │   │   ├── models/                  ← Document, Correspondent, Tag, Owner, DocumentType
│   │   │   └── paperless/
│   │   │       └── DMSClientPaperless.py
│   │   ├── llm/
│   │   │   ├── LLMClientInterface.py    ← Unified ABC (embed + chat)
│   │   │   ├── LLMClientManager.py      ← Factory
│   │   │   └── ollama/
│   │   │       └── LLMClientOllama.py
│   │   └── rag/
│   │       ├── RAGClientInterface.py    ← RAG-ABC
│   │       ├── RAGClientManager.py      ← Factory
│   │       ├── models/
│   │       │   ├── VectorPoint.py       ← Payload-Modell (owner_id Pflicht)
│   │       │   └── Scroll.py
│   │       └── qdrant/
│   │           └── RAGClientQdrant.py
│   ├── helper/
│   │   └── HelperConfig.py              ← Zentraler Env-Var-Reader
│   ├── logging/
│   │   └── logging_setup.py             ← setup_logging(), ColorLogger
│   └── models/
│       └── config.py                    ← EnvConfig Pydantic-Modell
├── services/
│   └── dms_rag_sync/
│       ├── SyncService.py               ← Orchestrierung: DMS → embed → RAG
│       └── dms_rag_sync.py              ← Einstiegspunkt
└── server/                              ← Phase III/IV — noch nicht erstellt
    └── api/
        ├── api_app.py
        ├── routers/
        │   ├── WebhookRouter.py
        │   └── QueryRouter.py
        ├── services/
        │   └── QueryService.py
        ├── dependencies/
        │   └── auth.py
        └── models/
            ├── requests.py
            └── responses.py
```

---

## Allgemeine Coding-Konventionen

### Interface-first
Neue Backends werden IMMER durch Implementierung des zugehörigen Interface erstellt.
Niemals direkte Abhängigkeiten zwischen konkreten Implementierungen.

### Klassenkonstruktoren
```python
def __init__(self, helper_config: HelperConfig) -> None:
    super().__init__(helper_config)       # für Unterklassen von ClientInterface
    self.logging = helper_config.get_logger()
```

### Methoden-Präfixe
- `do_*` — asynchrone Aktion (Seiteneffekte, I/O)
- `get_*` — Getter (kein I/O, kein Seiteneffekt)
- `is_*` — Boolean-Prüfung
- `_read_*` — privater Reader

### Klassen-Sektionen (in dieser Reihenfolge)
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

### Logging
IMMER %-Style — niemals f-Strings in Log-Aufrufen:
```python
self.logging.info("Syncing document %s ('%s'): %d chunk(s)", doc_id, title, n)  # richtig
self.logging.info(f"Syncing document {doc_id}")  # FALSCH
```

### Type-Annotations
PEP 604: `str | None`, niemals `Optional[str]`

### Konfigurationsschlüssel
Muster: `{CLIENT_TYPE}_{ENGINE_NAME}_{SETTING}`
Beispiele: `DMS_PAPERLESS_BASE_URL`, `RAG_QDRANT_COLLECTION`, `LLM_OLLAMA_BASE_URL`
Niemals `os.getenv()` direkt — immer über `HelperConfig`.

### Async
Kein `requests`, kein synchrones I/O. Ausschließlich `httpx.AsyncClient` für HTTP-Aufrufe.

### Sicherheits-Invariante
`owner_id` MUSS in jedem Qdrant-Upsert-Payload und jedem Such-Filter vorhanden sein.
Dokumente ohne `owner_id` werden beim Sync übersprungen (kein Silent-Write).

### Sprache
Sämtlicher Code, Variablennamen, Kommentare, Docstrings und Log-Nachrichten: **Englisch**.

---

## Agent-Zuständigkeiten

| Agent | Bereich | Status |
|---|---|---|
| `infra-agent` | `shared/helper/`, `shared/logging/`, `shared/models/`, `shared/clients/ClientInterface.py`, Docker | Pflege (Existing) |
| `dms-agent` | `shared/clients/dms/` | Pflege + Erweiterung |
| `rag-agent` | `shared/clients/rag/` | Pflege + Erweiterung |
| `embed-llm-agent` | `shared/clients/llm/` | Pflege + Erweiterung |
| `sync-agent` | `services/dms_rag_sync/` | Pflege |
| `api-agent` | `server/api/` | Neu erstellen (Phase III/IV) |
