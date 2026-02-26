"""Paperless-ngx implementation of the DMS interface."""

import httpx

from shared.clients.DMSInterface import DMSInterface
from shared.helper.config_helper import HelperConfig
from shared.models.document import Document, PaperlessDocument, VectorPayload

PAGE_SIZE = 100  # documents per page


class DMSPaperless(DMSInterface):
    """Concrete HTTP client for the Paperless-ngx REST API."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()
        self._client: httpx.AsyncClient | None = None

    ##########################################
    ################ GETTER ##################
    ##########################################

    def get_base_url(self) -> str:
        """Return the Paperless-ngx base URL from config.

        Returns:
            str: The configured base URL.
        """
        return self.helper_config.get_string_val("PAPERLESS_BASE_URL")

    def get_api_token(self) -> str:
        """Return the Paperless-ngx API token from config.

        Returns:
            str: The configured API token.
        """
        return self.helper_config.get_string_val("PAPERLESS_API_TOKEN")

    def get_timeout(self) -> int:
        """Return the request timeout in seconds from config.

        Returns:
            int: Timeout in seconds (default: 30).
        """
        return int(self.helper_config.get_number_val("PAPERLESS_TIMEOUT", default=30))

    def _read_default_owner_id(self) -> int | None:
        """Read the fallback owner_id for documents without an assigned owner.

        Used when Paperless-ngx returns owner=null (e.g. admin-created documents
        or pre-user-management imports). Returns None if not configured, which
        causes ownerless documents to be skipped by SyncService.

        Returns:
            int | None: Configured fallback owner_id, or None if absent.
        """
        raw = self.helper_config.get_number_val("PAPERLESS_DEFAULT_OWNER_ID", default=None)
        return int(raw) if raw is not None else None

    ##########################################
    ############### REQUESTS #################
    ##########################################

    async def do_healthcheck(self) -> bool:
        """Verify that the Paperless-ngx API is reachable and the token is valid.

        Uses /api/documents/?page_size=1 — a real data endpoint that validates
        both connectivity and authentication without relying on redirects.

        Returns:
            bool: True if the API responds with HTTP 200.

        Raises:
            Exception: If the client is not initialised or the API returns an error.
        """
        if self._client is None:
            raise Exception("HTTP client not initialised. Call boot() before making requests.")
        response = await self._client.get("/api/documents/", params={"page_size": 1})
        if response.status_code != 200:
            raise Exception(
                f"Paperless-ngx health check failed with status {response.status_code}."
            )
        self.logging.info("Paperless-ngx health check passed.")
        return True

    async def get_documents_page(self, page: int = 1) -> dict:
        """Fetch a single paginated page of documents.

        Args:
            page (int): Page number to fetch (1-based).

        Returns:
            dict: Raw API response with 'results', 'next', and 'count'.

        Raises:
            Exception: If the client is not initialised or the request fails.
        """
        if self._client is None:
            raise Exception("HTTP client not initialised. Call boot() before making requests.")
        response = await self._client.get(
            "/api/documents/",
            params={"page": page, "page_size": PAGE_SIZE},
        )
        if response.status_code != 200:
            self.logging.error(
                "Failed to fetch documents page %d: status %d", page, response.status_code
            )
            raise Exception(
                f"Failed to fetch documents page {page}: status {response.status_code}."
            )
        return response.json()

    async def get_document(self, document_id: int) -> PaperlessDocument:
        """Fetch a single document by its ID.

        Args:
            document_id (int): The Paperless-ngx document ID.

        Returns:
            PaperlessDocument: The parsed document.

        Raises:
            Exception: If the client is not initialised or the document cannot be fetched.
        """
        if self._client is None:
            raise Exception("HTTP client not initialised. Call boot() before making requests.")
        response = await self._client.get(f"/api/documents/{document_id}/")
        if response.status_code != 200:
            self.logging.error(
                "Failed to fetch document %d: status %d", document_id, response.status_code
            )
            raise Exception(
                f"Failed to fetch document {document_id}: status {response.status_code}."
            )
        data = response.json()
        owner_id: int | None = data.get("owner")
        if owner_id is None:
            owner_id = self._read_default_owner_id()
            if owner_id is not None:
                self.logging.debug(
                    "Document %d has no owner — applying default owner_id=%d.",
                    data["id"],
                    owner_id,
                )
        return PaperlessDocument(
            id=data["id"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            tag_ids=data.get("tags", []),
            correspondent_id=data.get("correspondent"),
            document_type_id=data.get("document_type"),
            owner_id=owner_id,
            created=data.get("created"),
            added=data.get("added"),
        )

    def build_vector_payload(
        self, doc: Document, chunk_index: int, chunk_text: str
    ) -> dict:
        """Build the Qdrant payload dict for a single Paperless document chunk.

        Extracts Paperless-specific metadata (tag_ids, correspondent_id,
        document_type_id) and returns a VectorPayload-serialised dict.

        Args:
            doc (Document): The source document (must be a PaperlessDocument at runtime).
            chunk_index (int): Zero-based index of this chunk within the document.
            chunk_text (str): The raw text of this chunk.

        Returns:
            dict: Payload suitable for VectorDBInterface.do_upsert().

        Raises:
            AssertionError: If doc is not a PaperlessDocument instance.
        """
        assert isinstance(doc, PaperlessDocument), (
            f"DMSPaperless.build_vector_payload() requires a PaperlessDocument, "
            f"got {type(doc).__name__}"
        )
        return VectorPayload(
            paperless_id=doc.id,
            chunk_index=chunk_index,
            title=doc.title,
            tag_ids=doc.tag_ids,
            correspondent_id=doc.correspondent_id,
            document_type_id=doc.document_type_id,
            owner_id=doc.owner_id,
            created=doc.created,
            chunk_text=chunk_text,
        ).model_dump()

    ##########################################
    ############# CORE REQUESTS ##############
    ##########################################

    async def boot(self) -> None:
        """Initialise the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.get_base_url(),
            headers={
                "Authorization": f"Token {self.get_api_token()}",
                "Accept": "application/json; version=9",
            },
            timeout=self.get_timeout(),
            follow_redirects=True,
        )
        self.logging.info("DMSPaperless initialised for %r", self.get_base_url())

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
