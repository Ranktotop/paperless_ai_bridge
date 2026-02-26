"""Abstract interface for embedding model clients.

Every embedding backend (Ollama, LiteLLM, OpenAI-compatible, …) is accessed
exclusively through this interface. Concrete implementations handle the specific
API protocol for their backend.

The central do_request() is a concrete template method on this interface —
it handles URL assembly, auth headers, and error logging uniformly.
Subclasses only implement the abstract configuration and extraction methods.
"""

from abc import ABC, abstractmethod

import httpx

from shared.helper.config_helper import HelperConfig


class EmbedInterface(ABC):
    """Abstract base class for embedding model clients."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = self.helper_config.get_logger()
        self.timeout: float = 60.0          # seconds; override in subclass via config
        self._client: httpx.AsyncClient | None = None

    ##########################################
    ############### CHECKER ##################
    ##########################################

    def is_authenticated_header(
        self, header: dict, api_key_override: str | None = None
    ) -> bool:
        """Validate a request header against the expected auth header.

        Args:
            header (dict): The header dict to validate.
            api_key_override (str | None): API key to check against instead of
                                           the configured backend key.

        Returns:
            bool: True if the header matches the expected auth, or if no auth
                  is configured.
        """
        expected = self.get_auth_header(api_key_override=api_key_override)
        if not expected:
            return True
        for key, value in expected.items():
            if key not in header or header.get(key) != value:
                return False
        return True

    ##########################################
    ################ GETTER ##################
    ##########################################

    @abstractmethod
    def get_engine_name(self) -> str:
        """Return the name of the embedding engine (e.g. "ollama").

        Returns:
            str: Engine identifier string.
        """
        pass

    @abstractmethod
    def get_auth_header_key_name(self) -> str:
        """Return the header key used for authentication (e.g. "Authorization").

        Returns:
            str: The header key name.
        """
        pass

    @abstractmethod
    def get_auth_header(self, api_key_override: str | None = None) -> dict[str, str]:
        """Return the authentication header dict for API requests.

        Args:
            api_key_override (str | None): Use this key instead of the configured one.

        Returns:
            dict[str, str]: Header key-value pair, or empty dict if unauthenticated.
        """
        pass

    @abstractmethod
    def get_request_headers_to_strip(self) -> list[str]:
        """Return header names to strip before forwarding requests to the backend.

        Returns:
            list[str]: Header names (lowercase) to strip.
        """
        pass

    @abstractmethod
    def get_response_headers_to_strip(self) -> list[str]:
        """Return header names to strip from backend responses before forwarding.

        Returns:
            list[str]: Header names (lowercase) to strip.
        """
        pass

    @abstractmethod
    def _get_endpoint_healthcheck(self) -> str:
        """Return the endpoint path for health-check requests.

        Returns:
            str: URL path (e.g. "" for root, or "/health").
        """
        pass

    @abstractmethod
    def _get_endpoint_models(self) -> str:
        """Return the endpoint path for listing available models.

        Returns:
            str: URL path (e.g. "/api/tags").
        """
        pass

    @abstractmethod
    def get_endpoint_embedding(self) -> str:
        """Return the endpoint path for embedding requests.

        Returns:
            str: URL path (e.g. "/api/embed").
        """
        pass

    @abstractmethod
    def get_endpoint_completion(self) -> str:
        """Return the endpoint path for chat completion requests.

        Returns:
            str: URL path (e.g. "/v1/chat/completions").
        """
        pass

    @abstractmethod
    def get_endpoint_model_details(self) -> str:
        """Return the endpoint path for fetching model details.

        Returns:
            str: URL path (e.g. "/api/show").
        """
        pass

    @abstractmethod
    def get_completion_payload(
        self, system_prompt: str, prompt: str, temperature: float
    ) -> dict:
        """Build the request body for a chat completion call.

        Args:
            system_prompt (str): The system instruction for the LLM.
            prompt (str): The user prompt.
            temperature (float): Sampling temperature.

        Returns:
            dict: JSON-serialisable request body.
        """
        pass

    def get_embedding_distance(self) -> str:
        """Return the distance metric for creating a Qdrant collection.

        Reads EMBEDDING_DISTANCE from config; defaults to "Cosine".

        Returns:
            str: Distance metric accepted by Qdrant (e.g. "Cosine", "Dot", "Euclid").
        """
        return self.helper_config.get_string_val("EMBEDDING_DISTANCE", default="Cosine")

    ##########################################
    ################ READER ##################
    ##########################################

    @abstractmethod
    def _read_server_url(self) -> str:
        """Read the embedding server base URL from config.

        Returns:
            str: The server base URL.
        """
        pass

    @abstractmethod
    def _read_server_api_key(self) -> str | None:
        """Read the embedding server API key from config.

        Returns:
            str | None: The API key, or None if not configured.
        """
        pass

    @abstractmethod
    def _read_llm_max_context_chars(self) -> int:
        """Read the maximum context length in characters for the LLM.

        Returns:
            int: Maximum number of characters to pass to the LLM.
        """
        pass

    @abstractmethod
    def _read_llm_model_name(self) -> str:
        """Read the LLM model name from config.

        Returns:
            str: Model identifier (e.g. "llama3.2").
        """
        pass

    @abstractmethod
    def _read_embedding_model_name(self) -> str:
        """Read the embedding model name from config.

        Returns:
            str: Embedding model identifier (e.g. "nomic-embed-text").
        """
        pass

    ##########################################
    ################# OTHER ##################
    ##########################################

    @abstractmethod
    def extract_completion_content(self, raw_response: dict) -> str:
        """Extract the text content from a raw LLM completion response.

        Args:
            raw_response (dict): The parsed JSON response from the completion endpoint.

        Returns:
            str: The assistant's reply text.

        Raises:
            ValueError: If the response format is invalid or content is empty.
        """
        pass

    @abstractmethod
    def extract_vector_size_from_model_info(self, model_info: dict) -> int:
        """Extract the embedding vector dimension from a model-details response.

        Args:
            model_info (dict): The parsed JSON response from the model-details endpoint.

        Returns:
            int: The embedding vector dimension.

        Raises:
            ValueError: If the dimension cannot be determined from the response.
        """
        pass

    @abstractmethod
    def extract_embeddings_from_response(self, response_data: dict) -> list[list[float]]:
        """Extract embedding vectors from a raw embedding API response.

        Response format differs by backend:
        - Ollama /api/embed:  {"embeddings": [[…], […]]}  — already ordered
        - OpenAI /v1/embeddings: {"data": [{"embedding": […], "index": 0}]} — needs sorting

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            list[list[float]]: Embedding vectors in the same order as the input texts.

        Raises:
            Exception: If the response format is invalid.
        """
        pass

    @abstractmethod
    def _build_embed_body(self, text: str) -> dict:
        """Build the request body for a single-text embedding request.

        Args:
            text (str): The text to embed.

        Returns:
            dict: JSON-serialisable request body (backend-specific format).
        """
        pass

    ##########################################
    ############### REQUESTS #################
    ##########################################

    async def do_healthcheck(self) -> httpx.Response:
        """Check whether the embedding backend is reachable.

        Returns:
            httpx.Response: The response from the health-check endpoint.
        """
        return await self.do_request(method="GET", endpoint=self._get_endpoint_healthcheck())

    async def do_fetch_models(self) -> httpx.Response:
        """Fetch the list of available models from the backend.

        Returns:
            httpx.Response: The response containing the model list.
        """
        return await self.do_request(method="GET", endpoint=self._get_endpoint_models())

    async def do_fetch_embedding_vector_size(self) -> tuple[int, str]:
        """Fetch the output vector dimension and distance metric for the embedding model.

        Returns:
            tuple[int, str]: (vector_dimension, distance_metric).

        Raises:
            Exception: If the backend cannot be reached or the dimension cannot be
                determined.
        """
        response = await self.do_request(
            method="POST",
            endpoint=self.get_endpoint_model_details(),
            json={"name": self._read_embedding_model_name()},
            raise_on_error=True,
        )
        vector_size = self.extract_vector_size_from_model_info(response.json())
        return vector_size, self.get_embedding_distance()

    async def do_embed(self, body_dict: dict) -> httpx.Response:
        """Send an embedding request with the given body to the backend.

        Args:
            body_dict (dict): The request body (backend-specific format).

        Returns:
            httpx.Response: The raw response from the embedding endpoint.
        """
        return await self.do_request(
            method="POST", endpoint=self.get_endpoint_embedding(), json=body_dict
        )

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text.

        High-level convenience method used by SyncService and QueryService.
        Builds the backend-specific body, calls do_embed(), and extracts the
        first vector from the response.

        Args:
            text (str): The text to embed.

        Returns:
            list[float]: The embedding vector.

        Raises:
            Exception: If the embedding request fails.
            ValueError: If the response does not contain a valid embedding.
        """
        body = self._build_embed_body(text)
        response = await self.do_embed(body)
        if response.status_code != 200:
            self.logging.error(
                "Embedding request failed: status %d, body: %s",
                response.status_code,
                response.text[:200],
            )
            raise Exception(
                f"Embedding request failed with status {response.status_code}."
            )
        return self.extract_embeddings_from_response(response.json())[0]

    ##########################################
    ############# CORE REQUESTS ##############
    ##########################################

    async def boot(self) -> None:
        """Initialise the HTTP client."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self.logging.info(
            "%s (%s) initialised for %r",
            self.__class__.__name__,
            self.get_engine_name(),
            self._read_server_url(),
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def do_request(
        self,
        method: str = "GET",
        endpoint: str = "",
        content: bytes | None = None,
        data: dict | None = None,
        files: dict | None = None,
        json: dict | None = None,
        params: dict | None = None,
        additional_headers: dict | None = None,
        raise_on_error: bool = False,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send an HTTP request to the embedding backend.

        Central template method — builds the full URL, injects auth headers, and
        logs errors. All REQUESTS methods call this.

        Args:
            method (str): HTTP method (e.g. "GET", "POST").
            endpoint (str): URL path (leading slash optional).
            content (bytes | None): Raw bytes body.
            data (dict | None): Form-encoded body.
            files (dict | None): Multipart file upload.
            json (dict | None): JSON-serialisable body.
            params (dict | None): URL query parameters.
            additional_headers (dict | None): Extra headers that override the defaults.
            raise_on_error (bool): Raise Exception on non-2xx status.
            timeout (float | None): Override the default timeout for this request.

        Returns:
            httpx.Response: The raw HTTP response.

        Raises:
            Exception: If the client is not initialised or raise_on_error is True
                       and the response status is >= 300.
        """
        if self._client is None:
            raise Exception("HTTP client not initialised. Call boot() before making requests.")

        # Normalise endpoint path
        normalised = "/" + endpoint.strip().lstrip("/") if endpoint.strip() else ""
        url = f"{self._read_server_url().rstrip('/')}{normalised}"

        headers: dict[str, str] = {}
        headers.update(self.get_auth_header())
        if additional_headers:
            headers.update(additional_headers)

        kwargs: dict = {
            "headers": headers,
            "timeout": timeout if timeout is not None else self.timeout,
            "params": params,
        }
        # Attach exactly one body argument
        if content is not None:
            kwargs["content"] = content
        elif data is not None:
            kwargs["data"] = data
        elif files is not None:
            kwargs["files"] = files
        elif json is not None:
            kwargs["json"] = json

        response = await self._client.request(method, url, **kwargs)

        if raise_on_error and response.status_code >= 300:
            self.logging.error(
                "Request to %s failed with status %d: %s",
                url,
                response.status_code,
                response.text[:300],
            )
            raise Exception(
                f"Request to {url} failed with status {response.status_code}."
            )

        return response