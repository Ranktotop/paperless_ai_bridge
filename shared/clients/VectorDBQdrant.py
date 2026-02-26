"""Qdrant implementation of VectorDBInterface.

Wraps the Qdrant REST API via httpx. Every scroll (search) call enforces
an owner_id filter as a security invariant — this cannot be bypassed.
Every upsert validates that owner_id is present in the payload before
the request is sent.
"""

import uuid

import httpx

# Fixed namespace for deterministic UUIDv5 point IDs.
# Changing this value would invalidate all existing point IDs in Qdrant.
_POINT_ID_NAMESPACE = uuid.UUID("6f4d3c2b-1a09-4e5f-8b7c-6d5e4f3a2b1c")

from shared.clients.VectorDBInterface import VectorDBInterface
from shared.helper.config_helper import HelperConfig


class VectorDBQdrant(VectorDBInterface):
    """Qdrant implementation of VectorDBInterface."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()
        self._client: httpx.AsyncClient | None = None

    ##########################################
    ################ GETTER ##################
    ##########################################

    def get_engine_name(self) -> str:
        """Return the engine name identifier.

        Returns:
            str: "qdrant"
        """
        return "qdrant"

    def get_auth_header(self) -> dict[str, str]:
        """Return the Qdrant API key header if configured.

        Returns:
            dict[str, str]: {"api-key": "<key>"} if a key is set, otherwise {}.
        """
        api_key = self._read_server_api_key()
        if api_key:
            return {"api-key": api_key}
        return {}

    def get_collection(self) -> str:
        """Return the target Qdrant collection name from config.

        Returns:
            str: Collection name (default: 'paperless_docs').
        """
        return self.helper_config.get_string_val("QDRANT_COLLECTION", default="paperless_docs")

    def get_vector_size(self) -> int:
        """Return the embedding vector dimension from config.

        Returns:
            int: Vector size (default: 768).
        """
        return int(self.helper_config.get_number_val("QDRANT_VECTOR_SIZE", default=768))

    def get_timeout(self) -> int:
        """Return the request timeout in seconds from config.

        Returns:
            int: Timeout in seconds (default: 30).
        """
        return int(self.helper_config.get_number_val("QDRANT_TIMEOUT", default=30))

    def _get_endpoint_collections(self) -> str:
        """Return the endpoint path for the collections list.

        Returns:
            str: "/collections"
        """
        return "/collections"

    def _get_endpoint_collection(self, collection: str) -> str:
        """Return the endpoint path for a specific collection.

        Args:
            collection (str): Collection name.

        Returns:
            str: "/collections/{collection}"
        """
        return f"/collections/{collection}"

    def _get_endpoint_upsert(self, collection: str) -> str:
        """Return the endpoint path for upserting points.

        Args:
            collection (str): Collection name.

        Returns:
            str: "/collections/{collection}/points"
        """
        return f"/collections/{collection}/points"

    def _get_endpoint_search(self, collection: str) -> str:
        """Return the endpoint path for vector similarity search.

        Args:
            collection (str): Collection name.

        Returns:
            str: "/collections/{collection}/points/search"
        """
        return f"/collections/{collection}/points/search"

    def _get_endpoint_delete(self, collection: str) -> str:
        """Return the endpoint path for deleting points by filter.

        Args:
            collection (str): Collection name.

        Returns:
            str: "/collections/{collection}/points/delete"
        """
        return f"/collections/{collection}/points/delete"

    ##########################################
    ################ READER ##################
    ##########################################

    def _read_server_url(self) -> str:
        """Read the Qdrant server URL from config.

        Returns:
            str: The configured Qdrant base URL.
        """
        return self.helper_config.get_string_val("QDRANT_BASE_URL")

    def _read_server_api_key(self) -> str | None:
        """Read the Qdrant API key from config.

        Returns:
            str | None: The API key, or None if not configured.
        """
        return self.helper_config.get_string_val("QDRANT_API_KEY", default=None)

    ##########################################
    ################# OTHER ##################
    ##########################################

    def extract_scroll_content(self, response_data: dict) -> list[dict]:
        """Extract search result points from a Qdrant search API response.

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            list[dict]: A list of point dicts from the 'result' key.
        """
        return response_data.get("result", [])

    ##########################################
    ############### REQUESTS #################
    ##########################################

    async def do_healthcheck(self) -> bool:
        """Verify that Qdrant is reachable by listing collections.

        Returns:
            bool: True if Qdrant responds with HTTP 200.

        Raises:
            Exception: If the client is not initialised or Qdrant is unreachable.
        """
        response = await self.do_request("GET", self._get_endpoint_collections())
        if response.status_code != 200:
            raise Exception(
                f"Qdrant health check failed with status {response.status_code}."
            )
        self.logging.info("Qdrant health check passed.")
        return True

    async def do_existence_check(self, collection: str) -> bool:
        """Check whether a Qdrant collection exists.

        Args:
            collection (str): The collection name to check.

        Returns:
            bool: True if the collection exists, False if it does not (404).

        Raises:
            Exception: If the client is not initialised or an unexpected status is returned.
        """
        response = await self.do_request("GET", self._get_endpoint_collection(collection))
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        raise Exception(
            f"Existence check for collection {collection!r} failed with status {response.status_code}."
        )

    async def do_create_collection(self, collection: str) -> None:
        """Create a Qdrant collection with cosine-distance vectors.

        Args:
            collection (str): The collection name to create.

        Raises:
            Exception: If the client is not initialised or creation fails.
        """
        body = {
            "vectors": {
                "size": self.get_vector_size(),
                "distance": "Cosine",
            }
        }
        response = await self.do_request(
            "PUT", self._get_endpoint_collection(collection), json=body
        )
        if response.status_code not in (200, 201):
            self.logging.error(
                "Failed to create collection %r: status %d", collection, response.status_code
            )
            raise Exception(
                f"Failed to create Qdrant collection {collection!r}: status {response.status_code}."
            )
        self.logging.info("Qdrant collection %r created.", collection)

    async def do_delete_by_document(self, paperless_id: int) -> None:
        """Delete all vector points belonging to a document.

        Args:
            paperless_id (int): The Paperless-ngx document ID whose points to remove.

        Raises:
            Exception: If the client is not initialised or the delete fails.
        """
        body = {
            "filter": {
                "must": [
                    {"key": "paperless_id", "match": {"value": paperless_id}}
                ]
            }
        }
        response = await self.do_request(
            "POST", self._get_endpoint_delete(self.get_collection()), json=body
        )
        if response.status_code not in (200, 201):
            self.logging.error(
                "Delete failed for paperless_id=%d: status %d",
                paperless_id,
                response.status_code,
            )
            raise Exception(
                f"Qdrant delete failed for paperless_id={paperless_id}: status {response.status_code}."
            )
        self.logging.debug("Deleted all points for paperless_id=%d.", paperless_id)

    async def do_upsert(self, vector: list[float], payload: dict) -> None:
        """Insert or update a single vector point in the collection.

        Args:
            vector (list[float]): The embedding vector.
            payload (dict): Metadata stored alongside the vector.
                            Must include 'owner_id' (security invariant).

        Raises:
            ValueError: If 'owner_id' is missing from the payload.
            Exception: If the client is not initialised or the upsert fails.
        """
        if "owner_id" not in payload:
            raise ValueError("Payload must include 'owner_id'. This is a security invariant.")

        point_id = str(
            uuid.uuid5(
                _POINT_ID_NAMESPACE,
                f"{payload['paperless_id']}:{payload['chunk_index']}",
            )
        )
        body = {
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            ]
        }
        response = await self.do_request(
            "PUT", self._get_endpoint_upsert(self.get_collection()), json=body
        )
        if response.status_code not in (200, 201):
            self.logging.error(
                "Upsert failed for paperless_id=%r: status %d",
                payload.get("paperless_id"),
                response.status_code,
            )
            raise Exception(f"Qdrant upsert failed with status {response.status_code}.")

    async def do_scroll(
        self,
        query_vector: list[float],
        owner_id: int,
        limit: int = 5,
        extra_filter: dict | None = None,
    ) -> list[dict]:
        """Search for similar vectors, always pre-filtered by owner_id.

        The owner_id filter is unconditionally injected and cannot be
        removed or overridden by callers.

        Args:
            query_vector (list[float]): The query embedding vector.
            owner_id (int): The requesting user's ID. Always enforced as a filter.
            limit (int): Maximum number of results to return.
            extra_filter (dict | None): Additional Qdrant filter conditions merged
                                        with the mandatory owner_id filter.

        Returns:
            list[dict]: Matching points with payload and score.

        Raises:
            Exception: If the client is not initialised or the search fails.
        """
        must_conditions: list[dict] = [
            {"key": "owner_id", "match": {"value": owner_id}}
        ]
        if extra_filter:
            must_conditions.append(extra_filter)

        body = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "filter": {"must": must_conditions},
        }
        response = await self.do_request(
            "POST", self._get_endpoint_search(self.get_collection()), json=body
        )
        if response.status_code != 200:
            self.logging.error(
                "Search failed for owner_id=%d: status %d", owner_id, response.status_code
            )
            raise Exception(f"Qdrant search failed with status {response.status_code}.")
        return self.extract_scroll_content(response.json())

    ##########################################
    ############# CORE REQUESTS ##############
    ##########################################

    async def boot(self) -> None:
        """Initialise the HTTP client with base URL and auth headers."""
        self._client = httpx.AsyncClient(
            base_url=self._read_server_url(),
            headers=self.get_auth_header(),
            timeout=self.get_timeout(),
        )
        self.logging.info(
            "VectorDBQdrant (%s) initialised for %r",
            self.get_engine_name(),
            self._read_server_url(),
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def do_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Send an HTTP request to Qdrant.

        Central dispatcher — all request methods call this.

        Args:
            method (str): HTTP method (e.g. "GET", "PUT", "POST").
            url (str): URL path (relative to base URL).
            **kwargs: Additional arguments forwarded to httpx (e.g. json=).

        Returns:
            httpx.Response: The raw HTTP response.

        Raises:
            Exception: If the client is not initialised.
        """
        if self._client is None:
            raise Exception("HTTP client not initialised. Call boot() before making requests.")
        return await self._client.request(method, url, **kwargs)
