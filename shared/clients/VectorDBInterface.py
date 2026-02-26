"""Abstract interface for vector database clients.

Every external vector DB dependency is accessed exclusively through this
interface. Concrete implementations connect to a specific backend (e.g. Qdrant).
The owner_id security invariant — enforced on every upsert and scroll — is
declared in this interface's docstrings and must be upheld by all implementations.
"""

from abc import ABC, abstractmethod

import httpx

from shared.helper.config_helper import HelperConfig


class VectorDBInterface(ABC):
    """Abstract base class for vector database clients."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()

    ##########################################
    ############### CHECKER ##################
    ##########################################

    def is_authenticated_header(self) -> bool:
        """Return True if an API key is configured for the vector DB.

        Returns:
            bool: True if an API key is present, False otherwise.
        """
        return bool(self._read_server_api_key())

    ##########################################
    ################ GETTER ##################
    ##########################################

    @abstractmethod
    def get_engine_name(self) -> str:
        """Return the name of the vector DB engine (e.g. "qdrant").

        Returns:
            str: Engine identifier string.
        """
        pass

    @abstractmethod
    def get_auth_header(self) -> dict[str, str]:
        """Return the authentication header dict for API requests.

        Returns:
            dict[str, str]: Header key-value pair, or empty dict if unauthenticated.
        """
        pass

    @abstractmethod
    def get_collection(self) -> str:
        """Return the target collection name from config.

        Returns:
            str: Collection name.
        """
        pass

    @abstractmethod
    def get_vector_size(self) -> int:
        """Return the embedding vector dimension from config.

        Returns:
            int: Vector size (e.g. 768, 1536).
        """
        pass

    @abstractmethod
    def get_timeout(self) -> int:
        """Return the request timeout in seconds from config.

        Returns:
            int: Timeout in seconds.
        """
        pass

    @abstractmethod
    def _get_endpoint_collections(self) -> str:
        """Return the endpoint path for listing or managing collections.

        Returns:
            str: URL path (e.g. "/collections").
        """
        pass

    @abstractmethod
    def _get_endpoint_collection(self, collection: str) -> str:
        """Return the endpoint path for a specific collection.

        Args:
            collection (str): Collection name.

        Returns:
            str: URL path (e.g. "/collections/my_col").
        """
        pass

    @abstractmethod
    def _get_endpoint_upsert(self, collection: str) -> str:
        """Return the endpoint path for upserting points.

        Args:
            collection (str): Collection name.

        Returns:
            str: URL path for the upsert operation.
        """
        pass

    @abstractmethod
    def _get_endpoint_search(self, collection: str) -> str:
        """Return the endpoint path for vector similarity search.

        Args:
            collection (str): Collection name.

        Returns:
            str: URL path for the search operation.
        """
        pass

    @abstractmethod
    def _get_endpoint_delete(self, collection: str) -> str:
        """Return the endpoint path for deleting points by filter.

        Args:
            collection (str): Collection name.

        Returns:
            str: URL path for the delete operation.
        """
        pass

    ##########################################
    ################ READER ##################
    ##########################################

    @abstractmethod
    def _read_server_url(self) -> str:
        """Read the vector DB server URL from config.

        Returns:
            str: The server base URL.
        """
        pass

    @abstractmethod
    def _read_server_api_key(self) -> str | None:
        """Read the vector DB API key from config.

        Returns:
            str | None: The API key, or None if not configured.
        """
        pass

    ##########################################
    ################# OTHER ##################
    ##########################################

    @abstractmethod
    def extract_scroll_content(self, response_data: dict) -> list[dict]:
        """Extract result items from a raw search/scroll API response.

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            list[dict]: A list of result point dicts.
        """
        pass

    ##########################################
    ############### REQUESTS #################
    ##########################################

    @abstractmethod
    async def do_healthcheck(self) -> bool:
        """Verify that the vector DB is reachable.

        Returns:
            bool: True if the service responds successfully.

        Raises:
            Exception: If the client is not initialised or the service is unreachable.
        """
        pass

    @abstractmethod
    async def do_existence_check(self, collection: str) -> bool:
        """Check whether a named collection exists.

        Args:
            collection (str): The collection name to check.

        Returns:
            bool: True if the collection exists, False otherwise.

        Raises:
            Exception: If the client is not initialised or an unexpected error occurs.
        """
        pass

    @abstractmethod
    async def do_create_collection(self, collection: str) -> None:
        """Create a new collection with the configured vector size.

        Args:
            collection (str): The collection name to create.

        Raises:
            Exception: If the client is not initialised or creation fails.
        """
        pass

    @abstractmethod
    async def do_delete_by_document(self, paperless_id: int) -> None:
        """Delete all vector points belonging to a document.

        Must be called before re-syncing a document to prevent stale chunks
        (e.g. from an owner change or shorter content after an edit).

        Args:
            paperless_id (int): The Paperless-ngx document ID whose points to remove.

        Raises:
            Exception: If the client is not initialised or the delete fails.
        """
        pass

    @abstractmethod
    async def do_upsert(self, vector: list[float], payload: dict) -> None:
        """Insert or update a single vector point in the collection.

        The payload MUST include 'owner_id' — this is a security invariant.

        Args:
            vector (list[float]): The embedding vector.
            payload (dict): Metadata stored alongside the vector.
                            Must include 'owner_id'.

        Raises:
            ValueError: If 'owner_id' is missing from the payload.
            Exception: If the client is not initialised or the upsert fails.
        """
        pass

    @abstractmethod
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
            extra_filter (dict | None): Additional filter conditions merged
                                        with the mandatory owner_id filter.

        Returns:
            list[dict]: Matching points with payload and score.

        Raises:
            Exception: If the client is not initialised or the search fails.
        """
        pass

    ##########################################
    ############# CORE REQUESTS ##############
    ##########################################

    @abstractmethod
    async def boot(self) -> None:
        """Initialise the HTTP client."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        pass

    @abstractmethod
    async def do_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Send an HTTP request to the vector DB.

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
        pass
