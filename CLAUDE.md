# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`paperless_ai_bridge` is an intelligent middleware service (**AI-Bridge**) that connects AI frontends (**OpenWebUI / AnythingLLM**) with the document management system **Paperless-ngx**. It enables employees to ask complex natural-language questions against their document inventory while enforcing strict access permissions and avoiding redundant OCR processing.

## Repository

- Remote: https://github.com/Ranktotop/paperless_ai_bridge.git
- Branch: `main`

---

## Architecture (High-Level)

Follows a **Decoupled-Agent Model**:

| Layer | Component | Role |
|---|---|---|
| **UI** | OpenWebUI | Chat interface & user authentication |
| **Orchestration** | LangChain (ReAct Agent) | Request analysis, filter injection, synthesis |
| **Inference** | Ollama / LiteLLM | Local LLM execution |
| **Storage** | Paperless-ngx | Source of documents, metadata, OCR text |
| **Storage** | Qdrant | Vector DB for semantic search with metadata filtering |

---

## Core Components

### A. Sync Engine (Background Worker)
- Reads **existing OCR text** from Paperless-ngx (no new OCR).
- Vectorizes text and stores chunks in Qdrant.
- Each vector chunk stores payload: `paperless_id`, `tag_ids`, `correspondent_id`, `document_type`, `owner_id`.
- Triggered by: nightly cron **or** Paperless webhook → AI-Bridge (incremental sync).

### B. LangChain Agent (Orchestrator)
Uses **ReAct pattern** (Reasoning and Acting):
1. **Intent Analysis** — LLM detects whether user needs metadata (tags) or full-text content.
2. **Self-Querying Retrieval** — Translates natural language into hard Qdrant metadata filters (e.g., `document_type == 'Rechnung' AND created_date >= '2026-02-19'`).
3. **Security Injection** — Forces `owner_id == current_user` on every Qdrant query (never bypassed).
4. **Synthesis** — Summarizes retrieved chunks; optionally returns Paperless document links as sources.

---

## Security Concept

Two-layer access control:
1. **Identity Mapping** — YAML/ENV config maps frontend user-IDs to Paperless API tokens/user-IDs.
2. **Isolated Retrieval** — Qdrant pre-filters by `owner_id`; users can never access another user's vectors regardless of semantic similarity.

---

## Tech Stack

| Concern | Technology |
|---|---|
| API server | FastAPI |
| Agent framework | LangChain |
| Vector DB | Qdrant |
| Task queue | Celery + Redis |
| LLM hosting | Ollama / vLLM (external) |
| Deployment | Docker Compose (later: Kubernetes) |
| Document source | Paperless-ngx REST API |

---

## Development Roadmap

| Phase | Focus | Deliverable |
|---|---|---|
| **I** | **Basic Sync** | Python script mirrors Paperless OCR text into Qdrant (incl. tags & owner_id). |
| **II** | **Secured Retrieval** | LangChain query with hard `owner_id` filter works end-to-end. |
| **III** | **Agentic Logic** | AI autonomously decides which tags/filters to apply (ReAct). |
| **IV** | **UI Integration** | OpenWebUI integration as "Function" or API tool. |
| **V** | **Scale-Out** | API + Worker separation with Celery task queue. |

---

## Key Conventions

- **No redundant OCR:** Always use Paperless-provided `content` field; never trigger new OCR.
- **owner_id is mandatory:** Every Qdrant upsert and query MUST include `owner_id`. This is a security invariant, not optional.
- **Metadata-first filtering:** Prefer hard metadata filters over pure semantic search to reduce hallucination risk on access-controlled data.
- **Stateless API layer:** The FastAPI container holds no user state; session context travels with each request.
- **Always write code in English** – this includes all function names, variable names,
  parameters, comments, docstrings, log messages, and LLM prompts. No German in code.
  (.env keys are exempt.)
- Docstrings for all public functions and classes
- Type annotations using PEP 604 union syntax (`str | None`)
- Configuration via `HelperConfig` (central config helper using `os.getenv`)
- Explicit error handling with meaningful HTTP status codes in FastAPI
- No synchronous blocking calls in async contexts (`httpx` always with `AsyncClient`)

## Coding Style
The full coding style guide is defined in [`CodingStyle.md`](CodingStyle.md).
**Always follow it.** It covers naming conventions, type annotations, docstrings,
import order, error handling, async patterns, logging, FastAPI patterns, Pydantic
models, class organisation, and more.

Key rules repeated here for quick reference:
- **Always write code in English** – function names, variables, comments, docstrings,
  log messages, LLM prompts. No German in code. (.env keys are exempt.)
- Docstrings for all public functions and classes
- Type annotations using PEP 604 union syntax (`str | None`)
- Configuration via `HelperConfig` (central config helper using `os.getenv`)
- Explicit error handling with meaningful HTTP status codes in FastAPI
- No synchronous blocking calls in async contexts (`httpx` always with `AsyncClient`)