from abc import abstractmethod

import httpx
from typing import Tuple
from shared.clients.ClientInterface import ClientInterface

from shared.helper.HelperConfig import HelperConfig

class EmbedClientInterface(ClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)

        # model and embedding config
        self.embed_distance = helper_config.get_string_val(f"{self.get_client_type().upper()}_DISTANCE", default="Cosine")
        self.embed_model = helper_config.get_string_val(f"{self.get_client_type().upper()}_MODEL", default=None)
        self.embed_model_max_chars = helper_config.get_number_val(f"{self.get_client_type().upper()}_MODEL_MAX_CHARS", default=None)

    ##########################################
    ############### CHECKER ##################
    ##########################################

    ##########################################
    ################ GETTER ##################
    ##########################################

    ################ GENERAL ##################
    def _get_client_type(self) -> str:
        """
        Returns the type of the client. E.g. "rag"
        """
        return "embed"
    
    ################ ENDPOINTS ##################
    @abstractmethod
    def _get_endpoint_models(self) -> str:
        """
        Returns the endpoint path for model listing requests.

        Returns:
            str: The endpoint path for model listing requests (e.g. "/api/tags")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def get_endpoint_embedding(self) -> str:
        """
        Returns the endpoint path for embedding requests.

        Returns:
            str: The endpoint path for embedding requests (e.g. "/api/embed")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def get_endpoint_model_details(self) -> str:
        """
        Returns the endpoint path for model details requests.

        Returns:
            str: The endpoint path for model details requests (e.g. "/api/show")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    ################ PAYLOAD BUILDER ##################
    @abstractmethod
    def get_embed_payload(self, texts: list[str]) -> dict:
        """Build the backend-specific request body for an embedding request.

        Args:
            texts (list[str]): The texts to embed.

        Returns:
            dict: JSON-serialisable request body (e.g. {"model": "...", "input": [...]}).

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    ##########################################
    ################# OTHER ##################
    ##########################################

    @abstractmethod
    def extract_vector_size_from_model_info(self, model_info: dict) -> int:
        """
        Extracts the embedding vector size from the model information response.

        Args:
            model_info (dict): The raw response from the model details endpoint.
        Returns:
            int: The dimension of the embedding vectors produced by the model.
        Raises:
            Exception: If the response format is invalid or the vector size cannot be determined.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def extract_embeddings_from_response(self, response_data: dict) -> list[list[float]]:
        """Extract embedding vectors from a raw embedding API response.

        Response format differs by backend:
        - Ollama /api/embed: {"embeddings": [[...], [...]]}  — already ordered
        - OpenAI-compatible: {"data": [{"embedding": [...], "index": 0}]} — needs sorting

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            list[list[float]]: Embedding vectors in the same order as the input texts.

        Raises:
            ValueError: If the response format is invalid or embeddings are empty.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    ##########################################
    ############### REQUESTS #################
    ##########################################

    async def do_fetch_models(self) -> httpx.Response:
        """Fetch the list of available embedding models from the backend.

        Returns:
            httpx.Response: The response containing the model list.
        """
        return await self.do_request(method="GET", endpoint=self._get_endpoint_models())

    async def do_fetch_embedding_vector_size(self) -> Tuple[int, str]:
        """
        Fetch the output vector dimension and distance metric of the configured embedding model.

        Returns:
            Tuple[int, str]: The number of dimensions produced by the embedding model and the distance metric.

        Raises:
            Exception: If the backend cannot be reached or the dimension cannot be
                determined from the response.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        response = await self.do_request(
            method="POST",
            json={"name": self.embed_model},
            endpoint=self.get_endpoint_model_details(),
            raise_on_error=True,
        )
        vector_size = self.extract_vector_size_from_model_info(model_info=response.json())
        return vector_size, self.embed_distance

    async def do_embed(self, texts: list[str] | str) -> list[list[float]]:
        """Send an embedding request and return the extracted vectors.

        Normalises the input to a list, builds the backend-specific payload via
        get_embed_payload(), sends the request, validates the status, and extracts
        the vectors via extract_embeddings_from_response().

        Args:
            texts (list[str] | str): One or more texts to embed.

        Returns:
            list[list[float]]: Embedding vectors in the same order as the inputs.

        Raises:
            Exception: If the HTTP request fails (status != 200).
            ValueError: If the response does not contain valid embeddings.
        """
        texts = [texts] if isinstance(texts, str) else texts
        body = self.get_embed_payload(texts)
        response = await self.do_request(method="POST", endpoint=self.get_endpoint_embedding(), json=body)
        if response.status_code != 200:
            self.logging.error(
                "Embedding request failed: status %d, body: %s",
                response.status_code,
                response.text[:200],
            )
            raise Exception("Embedding request failed with status %d." % response.status_code)
        return self.extract_embeddings_from_response(response.json())