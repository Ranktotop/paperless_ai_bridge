"""Abstract interface for Document Management System (DMS) clients."""

from abc import ABC, abstractmethod

from shared.helper.config_helper import HelperConfig
from shared.models.document import Document


class DMSInterface(ABC):
    """Abstract base class defining the contract for DMS API clients.

    Implementations connect to a specific DMS backend (e.g. Paperless-ngx).
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()

    ##########################################
    ############### REQUESTS #################
    ##########################################

    @abstractmethod
    async def do_healthcheck(self) -> bool:
        """Verify that the DMS API is reachable.

        Returns:
            bool: True if the API responds successfully.

        Raises:
            Exception: If the client is not initialised or the API is unreachable.
        """
        pass

    @abstractmethod
    async def get_documents_page(self, page: int = 1) -> dict:
        """Fetch a single paginated page of documents.

        Args:
            page (int): Page number to fetch (1-based).

        Returns:
            dict: Raw API response with 'results', 'next', and 'count'.
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: int) -> Document:
        """Fetch a single document by its ID.

        Args:
            document_id (int): The DMS document ID.

        Returns:
            Document: The parsed document.
        """
        pass

    @abstractmethod
    def build_vector_payload(
        self, doc: Document, chunk_index: int, chunk_text: str
    ) -> dict:
        """Build the vector store payload dict for a single document chunk.

        Encapsulates all backend-specific metadata extraction so callers
        (e.g. SyncService) remain decoupled from concrete DMS models.
        The returned dict must include 'owner_id' (security invariant).

        Args:
            doc (Document): The source document.
            chunk_index (int): Zero-based index of this chunk within the document.
            chunk_text (str): The raw text of this chunk.

        Returns:
            dict: Payload suitable for VectorDBInterface.do_upsert().
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
