"""Ollama implementation of EmbedInterface.

Calls the Ollama /api/embed endpoint to generate text embeddings and
/v1/chat/completions for LLM completions.  Supports optional API key
authentication for secured Ollama deployments.
"""

from shared.clients.EmbedInterface import EmbedInterface
from shared.helper.config_helper import HelperConfig


class EmbedClientOllama(EmbedInterface):
    """Ollama implementation of EmbedInterface."""

    def __init__(self, helper_config: HelperConfig) -> None:
        super().__init__(helper_config)
        self.timeout = float(self.helper_config.get_number_val("EMBED_TIMEOUT", default=60))

    ##########################################
    ################ GETTER ##################
    ##########################################

    def get_engine_name(self) -> str:
        """Return the engine name identifier.

        Returns:
            str: "ollama"
        """
        return "ollama"

    def get_auth_header_key_name(self) -> str:
        """Return the header key used for authentication.

        Returns:
            str: "Authorization"
        """
        return "Authorization"

    def get_auth_header(self, api_key_override: str | None = None) -> dict[str, str]:
        """Return the Bearer token header if an API key is configured.

        Args:
            api_key_override (str | None): Use this key instead of the configured one.

        Returns:
            dict[str, str]: {"Authorization": "Bearer <key>"} or {} if no key is set.
        """
        key = api_key_override if api_key_override is not None else self._read_server_api_key()
        if key:
            return {"Authorization": f"Bearer {key}"}
        return {}

    def get_request_headers_to_strip(self) -> list[str]:
        """Return header names to strip before forwarding embedding requests.

        Returns:
            list[str]: Headers to remove (lowercase).
        """
        return ["authorization", "host"]

    def get_response_headers_to_strip(self) -> list[str]:
        """Return header names to strip from Ollama responses.

        Returns:
            list[str]: Headers to remove (lowercase).
        """
        return ["transfer-encoding", "connection"]

    def _get_endpoint_healthcheck(self) -> str:
        """Return the Ollama health-check endpoint path.

        Returns:
            str: "" (root path returns 200 OK on Ollama)
        """
        return ""

    def _get_endpoint_models(self) -> str:
        """Return the Ollama model list endpoint path.

        Returns:
            str: "/api/tags"
        """
        return "/api/tags"

    def get_endpoint_embedding(self) -> str:
        """Return the Ollama embedding endpoint path.

        Returns:
            str: "/api/embed"
        """
        return "/api/embed"

    def get_endpoint_completion(self) -> str:
        """Return the Ollama chat completion endpoint path.

        Returns:
            str: "/v1/chat/completions"
        """
        return "/v1/chat/completions"

    def get_endpoint_model_details(self) -> str:
        """Return the Ollama model-details endpoint path.

        Returns:
            str: "/api/show"
        """
        return "/api/show"

    def get_completion_payload(
        self, system_prompt: str, prompt: str, temperature: float
    ) -> dict:
        """Build the OpenAI-compatible chat completion request body for Ollama.

        Args:
            system_prompt (str): The system instruction for the LLM.
            prompt (str): The user prompt.
            temperature (float): Sampling temperature.

        Returns:
            dict: JSON-serialisable request body.
        """
        return {
            "model": self._read_llm_model_name(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }

    ##########################################
    ################ READER ##################
    ##########################################

    def _read_server_url(self) -> str:
        """Read the Ollama server URL from config.

        Returns:
            str: The configured Ollama base URL.
        """
        return self.helper_config.get_string_val("EMBED_BASE_URL", default="http://localhost:11434")

    def _read_server_api_key(self) -> str | None:
        """Read the Ollama API key from config.

        Returns:
            str | None: The API key, or None if not configured.
        """
        return self.helper_config.get_string_val("EMBED_API_KEY", default=None)

    def _read_llm_max_context_chars(self) -> int:
        """Read the maximum LLM context length in characters from config.

        Returns:
            int: Max characters (default: 8000).
        """
        return int(self.helper_config.get_number_val("LLM_CONTEXT_MAX_CHARS", default=8000))

    def _read_llm_model_name(self) -> str:
        """Read the LLM model name from config.

        Returns:
            str: Model identifier (default: "llama3.2").
        """
        return self.helper_config.get_string_val("LLM_MODEL", default="llama3.2")

    def _read_embedding_model_name(self) -> str:
        """Read the embedding model name from config.

        Returns:
            str: Embedding model identifier (default: "nomic-embed-text").
        """
        return self.helper_config.get_string_val("EMBED_MODEL", default="nomic-embed-text")

    ##########################################
    ################# OTHER ##################
    ##########################################

    def extract_completion_content(self, raw_response: dict) -> str:
        """Extract the assistant message text from an Ollama completion response.

        Args:
            raw_response (dict): The parsed JSON response from /v1/chat/completions.

        Returns:
            str: The assistant's reply text.

        Raises:
            ValueError: If the response format is invalid or content is missing.
        """
        try:
            content = raw_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ValueError(
                f"Unexpected Ollama completion response format: {list(raw_response.keys())}"
            ) from exc
        if not content:
            raise ValueError("Ollama completion response contains empty content.")
        return content

    def extract_vector_size_from_model_info(self, model_info: dict) -> int:
        """Extract the embedding dimension from an Ollama /api/show response.

        Searches the model details dict recursively for the key
        "embedding_length".

        Args:
            model_info (dict): The parsed JSON response from /api/show.

        Returns:
            int: The embedding vector dimension.

        Raises:
            ValueError: If the dimension cannot be found in the response.
        """
        def _find(obj: object, key: str) -> int | None:
            if isinstance(obj, dict):
                if key in obj:
                    return int(obj[key])
                for v in obj.values():
                    result = _find(v, key)
                    if result is not None:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = _find(item, key)
                    if result is not None:
                        return result
            return None

        size = _find(model_info, "embedding_length")
        if size is None:
            raise ValueError(
                "Could not determine embedding vector size from Ollama model info. "
                f"Response keys: {list(model_info.keys())}"
            )
        return size

    def extract_embeddings_from_response(self, response_data: dict) -> list[list[float]]:
        """Extract embedding vectors from an Ollama /api/embed response.

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            list[list[float]]: Embedding vectors in input order.

        Raises:
            ValueError: If the response does not contain valid embeddings.
        """
        embeddings = response_data.get("embeddings")
        if not embeddings or not embeddings[0]:
            raise ValueError(
                "Ollama response does not contain valid embeddings. "
                f"Response keys: {list(response_data.keys())}"
            )
        return embeddings

    def _build_embed_body(self, text: str) -> dict:
        """Build the Ollama embedding request body.

        Args:
            text (str): The text to embed.

        Returns:
            dict: {"model": "...", "input": "<text>"}
        """
        return {
            "model": self._read_embedding_model_name(),
            "input": text,
        }