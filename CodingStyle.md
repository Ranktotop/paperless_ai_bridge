# CodingStyle.md – Python Coding Style Guide

This document describes my personal Python coding style.
It is project-agnostic and should be applied to all Python projects.

---

## Table of Contents

1. [Language](#1-language)
2. [Naming Conventions](#2-naming-conventions)
3. [Type Annotations](#3-type-annotations)
4. [Docstrings](#4-docstrings)
5. [Import Order](#5-import-order)
6. [Error Handling](#6-error-handling)
7. [Async / Await](#7-async--await)
8. [Configuration & Environment Variables](#8-configuration--environment-variables)
9. [Logging](#9-logging)
10. [FastAPI Patterns](#10-fastapi-patterns)
11. [Pydantic Models](#11-pydantic-models)
12. [Class Organisation](#12-class-organisation)
13. [Whitespace & Formatting](#13-whitespace--formatting)
14. [Project Architecture](#14-project-architecture)
15. [Miscellaneous](#15-miscellaneous)

---

## 1. Language

All code is written in **English**.

This includes:
- Function names, method names, variable names
- Class names, module names
- Comments, docstrings
- Log messages
- LLM prompts and system prompts embedded in code

`.env` keys are exempt from this rule.

---

## 2. Naming Conventions

### Classes
Use **PascalCase**.

```python
class HttpClient:
class AuthService:
class EmbedClientInterface:   # Abstract base classes get an "Interface" suffix
class EmbedClientOllama:      # Implementations are named after the backend
```

### Functions and Methods
Use **snake_case**.

```python
def get_engine_name() -> str:
def is_authenticated_header() -> bool:
async def do_embed() -> httpx.Response:
def _read_server_url() -> str:
```

### Method Prefix Conventions

| Prefix   | Meaning                                              |
|----------|------------------------------------------------------|
| `do_*`   | Async main action (network call, heavy operation)    |
| `get_*`  | Getter — reads and returns data                      |
| `is_*`   | Boolean check — returns `True` or `False`            |
| `_read_*`| Internal reader (private, reads config or state)     |

### Variables
Use **snake_case**.

```python
body_dict = {}
response_headers = {}
filter_conditions = []
helper_config = HelperConfig()
```

### Constants (module-level)
- Public constants: `SCREAMING_SNAKE_CASE`
- Private constants: `_SCREAMING_SNAKE_CASE` (leading underscore)

```python
DEFAULT_TIMEOUT = 30
_ANSI_RESET = "\033[0m"
_COLOR_MAP: dict[str, str] = {
    "cyan":  "\033[36m",
    "green": "\033[32m",
}
```

### Private vs. Public

| Visibility | Convention            | Example                    |
|------------|-----------------------|----------------------------|
| Public     | No prefix             | `do_request()`, `get_key()`|
| Private    | Single underscore `_` | `_read_url()`, `_client`   |

Never use double underscore (`__`) for name mangling unless explicitly required.

---

## 3. Type Annotations

### Union Syntax (PEP 604)
Always use the modern `|` syntax. Do **not** use `Optional[T]` or `Union[T, U]` in new code.

```python
# Correct
def get_value(key: str, default: str | None = None) -> str | None:

# Avoid
def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
```

### All Public Functions Must Be Annotated
Both parameters and return types.

```python
async def do_healthcheck(self) -> httpx.Response:
def extract_embeddings(self, response_data: dict) -> list[list[float]]:
async def boot(self) -> None:
```

### Generic Types
Always write out the element type.

```python
list[float]
list[list[float]]
dict[str, Any]
dict[str, str]
list[dict[str, Any]]
tuple[int, str]
```

### AsyncGenerator
Use explicit return type for lifespan functions.

```python
from typing import AsyncGenerator

async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ...
    yield
    ...
```

### Private Methods
Private methods should also be annotated — consistency matters.

```python
def _read_server_url(self) -> str | None:
```

---

## 4. Docstrings

### Format
Use triple **double** quotes (`"""`). The closing `"""` is always on its own line for
multi-line docstrings.

```python
def get_engine_name(self) -> str:
    """Returns the name of the backend engine (e.g. "ollama")."""

def do_embed(self, body: dict) -> httpx.Response:
    """Send an embedding request to the backend.

    Args:
        body (dict): The request payload to forward.

    Returns:
        httpx.Response: The raw response from the backend.

    Raises:
        Exception: If the HTTP client has not been initialised via boot().
        HTTPException: If the backend is unreachable (503).
    """
```

### Structure

| Section  | Label      | Format                                    | When to include        |
|----------|------------|-------------------------------------------|------------------------|
| Summary  | —          | Single sentence, ends with `.`            | Always                 |
| Args     | `Args:`    | `name (type): Description.`               | When params exist      |
| Returns  | `Returns:` | `type: Description.`                      | When not `None`        |
| Raises   | `Raises:`  | `ExceptionType: When this is raised.`     | When exceptions raised |

### Module-level Docstrings
Files with complex logic (services, clients, utilities) start with a module docstring.

```python
"""Payload enrichment service.

Write path: intercepts upsert requests to enrich document payloads
with structured metadata via sequential LLM calls (classify → extract).

Read path: classifies query intent and applies filters for listing
queries, falling back to semantic vector search for concept exploration.
"""
```

### Classes
All public classes get a docstring.

```python
class QueryClassification(BaseModel):
    """Structured output of the intent classification LLM call."""
```

---

## 5. Import Order

Follow the standard Python convention: **stdlib → third-party → local**.

```python
# 1. Standard library
import os
import json
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

# 2. Third-party
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

# 3. Local / project
from myapp.routers.MyRouter import my_router
from myapp.clients.MyClient import MyClient
from shared.helper.config_helper import HelperConfig
from shared.logging.logging_setup import setup_logging
```

### Rules
- **Never** use wildcard imports (`from module import *`)
- Always import specific names
- One blank line between the three import groups (optional but preferred)

---

## 6. Error Handling

### API Errors (FastAPI)
Use `HTTPException` with meaningful HTTP status codes.

```python
raise HTTPException(status_code=503, detail="Backend not reachable.")
raise HTTPException(status_code=401, detail="Invalid or missing authentication header.")
raise HTTPException(status_code=500, detail="API key not configured on server.")
```

### Parse / Validation Errors
Use `ValueError`.

```python
raise ValueError(f"Could not determine vector size for model '{model_name}'.")
raise ValueError("LLM response content is empty.")
```

### Startup / Configuration Errors
Use generic `Exception` — these are programmer errors, not user errors.

```python
raise Exception(f"Unsupported engine: '{engine}'. Valid values: ollama, openai.")
raise Exception("HTTP client not initialised. Call boot() before making requests.")
```

### Log Before Raising
For critical failures, log the error context before raising.

```python
if response.status_code >= 300:
    self.logging.error(
        "Request to %s failed with status %d: %s",
        kwargs["url"],
        response.status_code,
        response.text,
    )
    raise Exception(f"Request to {kwargs['url']} failed with status {response.status_code}.")
```

### Graceful Fallbacks
For non-critical failures, return `None` instead of crashing.

```python
try:
    result = await self.client.do_scroll(...)
    return result
except Exception as e:
    self.logging.warning("Scroll failed for %r: %s", collection, e)
    return None
```

### Warning vs. Error
- `logging.warning()` — operation failed but application continues normally
- `logging.error()` — significant failure, may degrade functionality

---

## 7. Async / Await

### Always Use Async HTTP Clients
Never make synchronous blocking network calls inside an async context.

```python
# Correct
import httpx

async def boot(self) -> None:
    self._client = httpx.AsyncClient(timeout=self.timeout)

# Avoid
import requests
response = requests.get(url)  # blocks the event loop
```

### Lifespan Management
Use `@asynccontextmanager` for app startup/shutdown logic. Do not use the deprecated
`@app.on_event("startup")` / `@app.on_event("shutdown")` decorators.

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- startup ---
    app.state.config = HelperConfig(logger=logging)
    app.state.client = MyClient(helper_config=app.state.config)
    await app.state.client.boot()

    yield  # application runs

    # --- shutdown ---
    await app.state.client.close()


app = FastAPI(lifespan=lifespan)
```

### Closing Async Clients
Use `aclose()`, not `close()`.

```python
async def close(self) -> None:
    """Close the HTTP client and release resources."""
    if self._client:
        await self._client.aclose()
        self._client = None
```

### Fire-and-Forget Background Tasks
Use `asyncio.create_task()` for tasks that should run independently.

```python
asyncio.create_task(self.enrichment_service.enrich_and_update(name, body_dict))
```

### Concurrent Execution
Use `asyncio.gather()` to run multiple coroutines concurrently.

```python
results = await asyncio.gather(
    *[self._process_item(item) for item in items]
)
```

### Concurrency Control
Use `asyncio.Semaphore` to limit parallel calls to external services.

```python
self._llm_semaphore = asyncio.Semaphore(1)

async with self._llm_semaphore:
    response = await self._call_llm(prompt)
```

### Guard Against Uninitialised Clients

```python
if self._client is None:
    raise Exception("HTTP client not initialised. Call boot() before making requests.")
```

---

## 8. Configuration & Environment Variables

### Central Config Class
All environment variable access goes through a single config class.
Never read `os.getenv()` directly in business logic.

```python
class HelperConfig:
    """Central configuration helper. Reads all settings from environment variables."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def get_string_val(self, key: str, default: str | None = None) -> str:
        """Read a string environment variable.

        Args:
            key (str): Environment variable name (case-insensitive).
            default (str | None): Fallback value if the variable is not set.

        Returns:
            str: The resolved value.

        Raises:
            ValueError: If the variable is not set and no default is provided.
        """
        key = key.upper()
        val = os.getenv(key) or None          # empty string → None
        if val is None and default is None:
            raise ValueError(f"Environment variable '{key}' is not set.")
        return val if val is not None else default

    def get_number_val(self, key: str, default: float | int | None = None) -> float | int:
        ...

    def get_bool_val(self, key: str, default: bool | None = None) -> bool:
        ...

    def get_logger(self) -> logging.Logger:
        return self._logger
```

### Usage in Components
The config object is passed in, never created internally.

```python
class MyService:
    def __init__(self, helper_config: HelperConfig) -> None:
        self.logging = helper_config.get_logger()
        self._base_url = helper_config.get_string_val("SERVICE_BASE_URL")
        self._timeout = helper_config.get_number_val("SERVICE_TIMEOUT", default=30)
```

### `.env.example` Structure
Grouped by service/concern, with a comment header per section.

```dotenv
# General
LOG_LEVEL=info
APP_API_KEY=your-secret-here

# Backend service
BACKEND_BASE_URL=http://localhost:8080
BACKEND_API_KEY=some-key

# Database
DB_HOST=localhost
DB_PORT=5432
DB_PASSWORD=your-db-password-here
```

### Rules
- Empty string is treated as "not set" (falls back to default)
- All keys are normalised to `UPPERCASE` internally
- No secrets are hardcoded — everything via `.env`
- Provide sensible defaults where possible; raise `ValueError` when a required variable is missing

---

## 9. Logging

### Setup
Use the standard `logging` module. Wrap the logger in a thin class to add
quality-of-life features (e.g. optional color output for the console).

```python
import logging
import logging.config

def setup_logging() -> logging.Logger:
    """Initialise and return the application logger."""
    logging.config.dictConfig(LOGGING_CONFIG)
    return logging.getLogger(__name__)
```

### Printf-Style Formatting
Always use `%`-style formatting in log calls — **never** f-strings.
This avoids eager string evaluation when the log level is suppressed.

```python
# Correct
self.logging.info("Processing request for collection %r", collection_name)
self.logging.error("Request to %s failed with status %d: %s", url, status, text)

# Avoid
self.logging.info(f"Processing request for collection {collection_name!r}")
```

### Log Level Conventions

| Level     | When to use                                               |
|-----------|-----------------------------------------------------------|
| `debug`   | Detailed internal traces; suppressed in production        |
| `info`    | Key events: startup, successful completion of operations  |
| `warning` | Non-fatal issues: fallbacks, cache misses, degraded mode  |
| `error`   | Real failures with context; operation did not succeed     |
| `critical`| Application-level failures requiring immediate attention  |

### Truncate Long Values in Logs
Slice strings to keep log output readable.

```python
self.logging.debug("LLM response preview: %r", content[:80])
self.logging.debug("Cache hit for query: %r", query_text[:60])
```

### Suppress Noisy Third-party Loggers
Set external loggers to `WARNING` or `ERROR` unless in debug mode.

```python
debug_mode = os.getenv("LOG_LEVEL", "info").lower() == "debug"
logging.getLogger("httpx").setLevel(logging.DEBUG if debug_mode else logging.WARNING)
logging.getLogger("some_noisy_library").setLevel(logging.ERROR)
```

### Optional Console Color Support
A thin logger wrapper can accept an optional `color=` keyword argument.
Colors are applied only in the console handler, not in file logs.

```python
self.logging.info("Service started successfully.", color="green")
self.logging.warning("Caching unavailable.", color="yellow")
self.logging.error("Backend unreachable.", color="red")
```

---

## 10. FastAPI Patterns

### Router-Based Organisation
Endpoints live in `APIRouter` instances, which are included in the main app.

```python
# routers/MyRouter.py
from fastapi import APIRouter, Depends, Request, Response

my_router = APIRouter()

@my_router.post("/api/resource", dependencies=[Depends(verify_auth)], tags=["My Service"])
async def create_resource(request: Request) -> Response:
    ...
```

```python
# main app
from myapp.routers.MyRouter import my_router
app.include_router(my_router)
```

### App State for Shared Resources
Store shared objects (config, clients, logger) on `app.state`.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.logging = setup_logging()
    app.state.config = HelperConfig(logger=app.state.logging)
    app.state.client = MyClient(helper_config=app.state.config)
    await app.state.client.boot()
    yield
    await app.state.client.close()
```

### Dependency Injection
Use `Depends()` for authentication and other shared concerns.

```python
@my_router.post("/api/resource", dependencies=[Depends(verify_auth)])
async def create_resource(request: Request) -> Response:
```

### Raw Request Body Handling
Read the raw body, then parse as JSON.

```python
body_bytes = await request.body()
body_dict = json.loads(body_bytes)
```

### Raw Response Forwarding (Proxy Pattern)
When acting as a proxy, forward the raw response with its original content type.

```python
return Response(
    content=response.content,
    status_code=response.status_code,
    headers=response_headers,
    media_type=response.headers.get("content-type", "application/json"),
)
```

### JSON Responses
Use `JSONResponse` when returning structured data.

```python
from fastapi.responses import JSONResponse

return JSONResponse(content={"status": "ok", "items": results})
```

### Multiple HTTP Methods on One Route
Use `api_route()` to handle multiple methods with one handler.

```python
@my_router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["Proxy"],
)
async def proxy(request: Request, path: str) -> Response:
```

### CORS Middleware
Always add CORS middleware; configure origins according to the deployment environment.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Startup Health Check
Verify connectivity to external services in `lifespan` before the app starts accepting
requests.

```python
await app.state.client.do_healthcheck()
```

### Endpoint Tags
Tag every endpoint for Swagger/OpenAPI documentation.

```python
tags=["My Service"]
```

---

## 11. Pydantic Models

### Base Class
All models inherit from `pydantic.BaseModel`.

```python
from pydantic import BaseModel

class SearchResult(BaseModel):
    """A single result returned from the search endpoint."""

    document_id: str
    filename: str
    score: float
    summary: str | None = None
```

### Field Rules
- All fields are explicitly type-annotated
- Optional fields: `field: str | None = None`
- Collection fields with empty default: `tags: list[str] = []`, `meta: dict[str, Any] = {}`
- Complex generic types are written out: `conditions: dict[str, list[str]] = {}`

### Docstrings
All model classes get a docstring describing their purpose.

```python
class QueryClassification(BaseModel):
    """Structured output of the intent classification LLM call."""

    mode: str
    doc_type: str | None = None
    conditions: dict[str, Any] = {}
```

### No Inner Config Classes
Do not add inner `class Config` unless a specific Pydantic feature (e.g. `from_attributes`)
is actually needed. Rely on Pydantic's defaults.

---

## 12. Class Organisation

### Constructor Pattern
The constructor accepts a config object and immediately stores the logger.

```python
class MyService:
    def __init__(self, helper_config: HelperConfig) -> None:
        self.logging = helper_config.get_logger()
        self._base_url = helper_config.get_string_val("SERVICE_BASE_URL")
        self._client: httpx.AsyncClient | None = None
```

### Method Grouping with Section Banners
Group methods by purpose and separate them with comment banners.

```python
##########################################
############### CHECKER ##################
##########################################

def is_connected(self) -> bool:
    ...

##########################################
################ GETTER ##################
##########################################

def get_engine_name(self) -> str:
    ...

##########################################
############### REQUESTS #################
##########################################

async def do_request(self, ...) -> httpx.Response:
    ...
```

Common section names: `CHECKER`, `GETTER`, `READER`, `REQUESTS`, `CORE REQUESTS`, `OTHER`.

### Abstract Base Classes
- Inherit from `ABC` and use `@abstractmethod`
- Interface classes end with the suffix `Interface`
- Concrete implementations are named after the backend/technology they wrap

```python
from abc import ABC, abstractmethod

class MyClientInterface(ABC):
    """Abstract base class for backend clients."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.logging = helper_config.get_logger()

    @abstractmethod
    def get_engine_name(self) -> str:
        """Returns the name of the backend engine."""
        pass

    @abstractmethod
    async def do_request(self, ...) -> httpx.Response:
        ...


class MyClientOllama(MyClientInterface):
    """Ollama implementation of MyClientInterface."""

    def get_engine_name(self) -> str:
        return "ollama"
```

### Private Attributes
Prefix with a single underscore.

```python
self._client: httpx.AsyncClient | None = None
self._semaphore = asyncio.Semaphore(1)
self._base_url: str = helper_config.get_string_val("BASE_URL")
```

---

## 13. Whitespace & Formatting

### Indentation
4 spaces. Never tabs.

### Blank Lines
- **2 blank lines** between top-level definitions (classes, module-level functions)
- **1 blank line** between methods inside a class
- **1 blank line** to separate logical blocks inside a function (where it aids readability)

### Line Length
Aim for **100–120 characters**. No hard limit, but avoid unnecessarily long lines.
Wrap function signatures and long expressions naturally.

```python
# Acceptable — fits the context
def get_scroll_payload(
    self,
    filters: list[dict],
    with_payload: bool | list | dict,
    with_vector: bool | list,
    limit: int | None = None,
) -> dict:
```

### Multiline Strings
For long strings (LLM prompts, SQL, HTML templates), use triple-quoted strings with
a backslash after the opening quotes to suppress the leading newline.

```python
system_prompt = f"""\
You are a document classifier.
Given the following document text, determine which type best describes it.

Available types:
{types_list}

Respond with a JSON object.
"""
```

### Unit Comments
Add inline comments when a number has a unit.

```python
self.ttl_seconds = 300         # seconds
self.max_retries = 3           # attempts
self.chunk_size = 1000         # characters
```

---

## 14. Project Architecture

### Layered Directory Structure

```
myproject/
├── server/
│   └── myservice/
│       ├── myservice_app.py     # FastAPI entry point
│       ├── clients/
│       │   ├── MyClientInterface.py
│       │   └── MyClientImpl.py
│       ├── routers/
│       │   └── MyRouter.py
│       └── services/
│           └── MyService.py
├── shared/
│   ├── clients/                 # Reusable I/O clients (cache, DB, …)
│   ├── dependencies/            # FastAPI Depends() utilities (auth, …)
│   ├── helper/                  # Config, utilities
│   ├── logging/                 # Logging setup
│   ├── models/                  # Pydantic models
│   └── schemas/                 # YAML/JSON schema loaders
└── config/
    └── my_schemas.yaml
```

### Layer Responsibilities

| Layer        | Responsibility                                         |
|--------------|--------------------------------------------------------|
| `clients/`   | I/O: HTTP calls, database access, cache reads/writes   |
| `routers/`   | Routing: parse request, delegate, return response      |
| `services/`  | Business logic: orchestrate clients, apply rules       |
| `models/`    | Data structures: Pydantic models, no logic             |
| `shared/`    | Cross-cutting concerns: config, logging, auth          |

### Abstract Client Pattern

Every external dependency (DMS, vector DB, cache, LLM, …) is accessed exclusively through an
**interface class** (`*Interface`, inherits from `ABC`). Business logic depends only on the
interface — never on a concrete implementation. This makes backends swappable without touching
any service or router code.

**Naming:**
- Interface: `<Domain>Interface` — e.g. `DMSInterface`, `VectorDBInterface`
- Concrete: `<Domain><Backend>` — e.g. `DMSPaperless`, `VectorDBQdrant`
- Never use generic suffixes like `Impl`, `Client`, or `Concrete`

**Structure rules:**
- The interface declares all public methods with full docstrings and type annotations.
- `boot()` and `close()` are always declared on the interface and placed in the
  `CORE REQUESTS` section of both the interface and the concrete class.
- Getter methods for config values (`get_base_url()`, `get_timeout()`, …) are declared on the
  interface so all implementations share the same config-key contract.
- Business logic (services, routers) receives the **interface type** in its constructor:

```python
# Correct — depends on the interface
class SyncService:
    def __init__(self, dms_client: DMSInterface, ...) -> None:

# Wrong — depends on a concrete class
class SyncService:
    def __init__(self, dms_client: DMSPaperless, ...) -> None:
```

**Class skeleton:**

```python
# DMSInterface.py
from abc import ABC, abstractmethod
from shared.helper.config_helper import HelperConfig

class DMSInterface(ABC):
    """Abstract base class for Document Management System clients."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()

    ##########################################
    ################ GETTER ##################
    ##########################################

    def get_base_url(self) -> str:
        """Return the DMS base URL from config."""
        return self.helper_config.get_string_val("DMS_BASE_URL")

    ##########################################
    ############### REQUESTS #################
    ##########################################

    @abstractmethod
    async def do_healthcheck(self) -> bool: ...

    ##########################################
    ############# CORE REQUESTS ##############
    ##########################################

    @abstractmethod
    async def boot(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


# DMSPaperless.py
class DMSPaperless(DMSInterface):
    """Paperless-ngx implementation of DMSInterface."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()
        self._client: httpx.AsyncClient | None = None

    # ... override all abstract methods
```

---

## 15. Miscellaneous

### JSON Handling
Use the standard `json` module directly.

```python
import json

body_dict = json.loads(body_bytes)
wrapped = json.dumps({"status": "ok", "data": result}).encode()
```

### Dictionary Merging
Use spread syntax for non-destructive merging.

```python
return {
    **base_payload,
    "doc_type": doc_type,
    "entities": entities,
    "_enriched": True,
}
```

Avoid `dict.update()` when you want to produce a new dict.

### List and Generator Comprehensions
Prefer comprehensions over explicit loops for data transformations.

```python
type_labels = "\n".join(f"- {tid}: {desc}" for tid, desc in schema.items())

processed = [transform(item) for item in raw_items if item is not None]

tasks = asyncio.gather(*[process(item) for item in items])
```

### None Guards
Always check for `None` before accessing attributes on optional objects.

```python
if self._client is None:
    raise Exception("Client not initialised. Call boot() first.")
```

### No Magic Numbers
Store all non-obvious numeric values in named variables with comments.

```python
# Avoid
await asyncio.sleep(5)

# Correct
RETRY_DELAY_SECONDS = 5
await asyncio.sleep(RETRY_DELAY_SECONDS)
```

### String Truncation in Debug Output
Slice strings when logging or displaying potentially large values.

```python
self.logging.debug("Query preview: %r", query_text[:80])
self.logging.debug("Response body snippet: %s", response_body[:200])
```

### No Unnecessary Abstractions
Do not create helpers, utilities, or base classes for one-off use.
Three similar lines of code is better than a premature abstraction.

### No Hardcoded Secrets
All credentials, API keys, URLs, and passwords come from environment variables.
The `.env` file is never committed to version control.
