import json

from shared.clients.llm.LLMClientInterface import LLMClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig


class LLMClientOllama(LLMClientInterface):
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
            EnvConfig(env_key="API_KEY", val_type="string", default=""),
        ]

    ################ AUTH ##################
    def _get_auth_header(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    ################ ENDPOINTS ##################
    def _get_base_url(self) -> str:
        return self._base_url

    def _get_endpoint_healthcheck(self) -> str:
        return ""

    def _get_endpoint_models(self) -> str:
        return "/api/tags"

    def get_endpoint_embedding(self) -> str:
        return "/api/embed"

    def get_endpoint_model_details(self) -> str:
        return "/api/show"

    def _get_endpoint_chat(self) -> str:
        return "/api/chat"

    ################ PAYLOAD BUILDER ##################
    def get_embed_payload(self, texts: list[str]) -> dict:
        """Build the Ollama embedding request body.

        Args:
            texts (list[str]): The texts to embed.

        Returns:
            dict: {"model": "...", "input": [...]}
        """
        return {"model": self.embed_model, "input": texts}

    def get_chat_payload(self, messages: list[dict]) -> dict:
        """Build the Ollama chat request body.

        Uses chat_model if configured, falls back to embed_model.

        Args:
            messages (list[dict]): OpenAI-format messages.

        Returns:
            dict: {"model": "...", "messages": [...], "stream": False}
        """
        model = self.chat_model or self.embed_model
        return {"model": model, "messages": messages, "stream": False}

    ################ PAYLOAD BUILDER ##################
    def get_model_details_payload(self) -> dict:
        return {"name": self.embed_model}

    ##########################################
    ########### RESPONSE PARSER ##############
    ##########################################

    def _parse_endpoint_model_details(self, model_info: dict) -> int:
        info: dict = model_info.get("model_info", {})
        for key, value in info.items():
            if key.endswith(".embedding_length"):
                return int(value)
        raise ValueError("Could not determine embedding vector size for model '%s'" % self.embed_model)

    def _parse_endpoint_embedding(self, response_data: dict) -> list[list[float]]:
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
                "Response keys: %s" % list(response_data.keys())
            )
        return embeddings

    def _is_default_chat_response(self, response_data: dict) -> bool:
        """Return True if message.content is a non-empty string."""
        content = response_data.get("message", {}).get("content")
        return bool(content)

    def _is_tool_call_response(self, response_data: dict) -> bool:
        """Return True if message.tool_calls is present and non-empty."""
        tool_calls = response_data.get("message", {}).get("tool_calls")
        return bool(tool_calls)

    def _parse_endpoint_chat(self, response_data: dict) -> str:
        """Extract the assistant reply text from an Ollama /api/chat response.

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            str: The assistant reply text.

        Raises:
            ValueError: If the response does not contain a valid message.
        """
        message = response_data.get("message", {})
        content = message.get("content")
        if content is None:
            raise ValueError(
                "Ollama chat response does not contain a valid message. "
                "Response keys: %s" % list(response_data.keys())
            )
        return content

    def _parse_tool_call_response(self, response_data: dict) -> str:
        """Convert an Ollama native tool call response to ReAct-format text.

        Ollama tool call responses have no content but carry a tool_calls list
        and an optional thinking field. This method synthesises the ReAct lines
        that the agent loop expects:

            Thought: <thinking text>   (omitted when empty)
            Action: <tool_name>
            Action Input: <arguments as JSON>

        Args:
            response_data (dict): The parsed JSON response body.

        Returns:
            str: ReAct-formatted assistant text.
        """
        message = response_data.get("message", {})
        tool_call = message.get("tool_calls", [{}])[0]
        fn = tool_call.get("function", {})
        tool_name = fn.get("name", "")
        arguments = fn.get("arguments", {})

        parts = []
        thinking = message.get("thinking", "")
        if thinking:
            parts.append("Thought: %s" % thinking)
        parts.append("Action: %s" % tool_name)
        parts.append("Action Input: %s" % json.dumps(arguments, ensure_ascii=False))
        return "\n".join(parts)
