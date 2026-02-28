from shared.clients.embed.EmbedClientInterface import EmbedClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig


class EmbedClientOllama(EmbedClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)
        self._base_url = self.get_config_val("BASE_URL", default=None, val_type="string")
        self._api_key = self.get_config_val("API_KEY", default="", val_type="string")

    ##########################################
    ################ GETTER ##################
    ##########################################

    ################ GENERAL ##################
    def _get_engine_name(self) -> str:
        return "Ollama"

    ################ CONFIG ##################
    def _get_required_config(self) -> list[EnvConfig]:
        return [
            EnvConfig(env_key="BASE_URL", val_type="string", default=None),
            EnvConfig(env_key="API_KEY", val_type="string", default="")
        ]
    
    ################ AUTH ##################    
    def _get_auth_header(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        else:
            return {}

    ################ ENDPOINTS ##################
    def _get_base_url(self) -> str:
        return self._base_url

    def _get_endpoint_healthcheck(self) -> str:
        # root on ollama
        return ""

    def _get_endpoint_models(self) -> str:
        # ollama uses /api/tags for model listing
        return "/api/tags"

    def get_endpoint_embedding(self) -> str:
        # ollama uses /api/embed for embedding requests
        return "/api/embed"

    def get_endpoint_model_details(self) -> str:
        # ollama uses /api/show for model details, with model name in body
        return "/api/show"

    ################ PAYLOAD BUILDER ##################
    def get_embed_payload(self, texts: list[str]) -> dict:
        """Build the Ollama embedding request body.

        Args:
            texts (list[str]): The texts to embed.

        Returns:
            dict: {"model": "...", "input": [...]}
        """
        return {"model": self.embed_model, "input": texts}

    ##########################################
    ################# OTHER ##################
    ##########################################

    def extract_vector_size_from_model_info(self, model_info: dict) -> int:
        model_info: dict = model_info.get("model_info", {})
        for key, value in model_info.items():
            if key.endswith(".embedding_length"):
                return int(value)
        raise ValueError(f"Could not determine embedding vector size for model {self.embed_model}")

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