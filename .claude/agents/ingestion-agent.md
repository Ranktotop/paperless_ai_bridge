---
name: ingestion-agent
description: >
  Owns the document ingestion pipeline: services/doc_ingestion/ with
  IngestionService (orchestrator), Document (central document class combining
  path-template parsing, OCR via PyMuPDF + Vision LLM, LLM metadata extraction,
  and LLM tag extraction), DocumentConverter (LibreOffice PDF conversion helper),
  FileScanner (rglob + watchfiles). Also owns the DMSClientInterface write methods
  (do_upload_document, do_update_document, do_resolve_or_create_*) and their
  Paperless implementation. Invoke when: modifying the ingestion pipeline, changing
  OCR strategy, updating path template syntax, debugging document upload issues,
  or adding new DMS write capabilities.
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
model: claude-sonnet-4-6
---

# ingestion-agent

Owns the document ingestion pipeline subsystem.

## Owned Files

- `services/doc_ingestion/` (complete directory)
  - `IngestionService.py` — orchestrator
  - `doc_ingestion.py` — entry point
  - `helper/Document.py` — central document class
  - `helper/DocumentConverter.py` — LibreOffice PDF conversion helper
  - `helper/FileScanner.py` — file discovery (rglob + watchfiles)
- Abstract write methods in `shared/clients/dms/DMSClientInterface.py`
  (`do_upload_document`, `do_update_document`, `do_resolve_or_create_*`)
- `shared/clients/dms/paperless/DMSClientPaperless.py` (write method implementations)

## Key Classes

### `Document`

Central class representing a file to be ingested. Combines all per-document logic.

**Lifecycle:** `boot()` → use getters → `cleanup()`

`boot()` performs in order:
1. Creates a UUID-named working directory
2. Initialises `DocumentConverter` and converts the source file
3. Extracts text: direct read for `txt`/`md`; PyMuPDF per-page text with Vision LLM
   fallback for pages below `minimum_text_chars = 40`
4. Reads metadata: path template first, LLM fill-in second (path wins)
5. Extracts tags via LLM

**Path template** (`_path_template`): positional `{correspondent}`, `{document_type}`,
`{year}`, `{month}`, `{day}`, `{title}` segments map to directory parts relative to
`root_path`. `correspondent` is mandatory — raises `RuntimeError` if absent.

**LLM metadata** (`_read_meta_from_content`): JSON response; feeds existing DMS
document_types into the prompt to prefer existing values.

**LLM tags** (`_read_tags_from_content`): JSON array of strings, max 3 tags; feeds
existing DMS tag names into the prompt.

**Public getters:**
- `get_title() -> str`
- `get_metadata() -> DocMetadata`
- `get_tags() -> list[str]`
- `get_content() -> str`
- `get_date_string(pattern: str) -> str | None`

### `DocMetadata` (dataclass in `Document.py`)

Fields: `correspondent`, `document_type`, `year`, `month`, `day`, `title`, `filename`

### `DocumentConverter`

Wraps LibreOffice (`soffice`) for format conversion.

- Native formats (pdf, png, jpg, jpeg, txt, md): copied to working directory as-is
- Convertible formats (docx, doc, odt, xlsx, xls, ods, csv, pptx, ppt, odp, rtf):
  converted to PDF via `soffice --headless --convert-to pdf`
- Raises `RuntimeError` if LibreOffice is not in PATH

### `IngestionService`

`do_ingest_file(file_path, root_path) -> int | None` pipeline:
1. `fill_cache()` on DMS client
2. Instantiate and `boot()` a `Document`
3. Resolve/create correspondent, document_type, tags via DMS write methods
4. Upload original file bytes → `do_upload_document()` → `doc_id`
5. PATCH with full metadata → `do_update_document()`
6. `cleanup()` in a `finally` block (always)

## Key Rules

- `Document.cleanup()` MUST run in `finally` — never skip
- Path metadata takes precedence over LLM metadata (path wins)
- `correspondent` is mandatory in path metadata
- `LLM_MODEL_VISION` is required — raise `RuntimeError` at boot if not configured
- LibreOffice must be in PATH — raise `RuntimeError` at `DocumentConverter` init if absent
- Working directories use UUID-based names to avoid collisions
- Language for LLM text: `LANGUAGE` env var (default: `German`)
- Log always %-style, never f-strings

## Coordination

- `do_chat_vision()` on `LLMClientInterface` must be provided by embed-llm-agent
- DMS write methods (`do_upload_document`, `do_update_document`, `do_resolve_or_create_*`)
  must be implemented by dms-agent before `IngestionService` can upload
- `OCRClientInterface` and its implementations are owned by ocr-agent — do not modify
  them here; if OCR behaviour changes, coordinate with ocr-agent
