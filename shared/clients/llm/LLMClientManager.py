from shared.helper.HelperConfig import HelperConfig
from shared.clients.llm.LLMClientInterface import LLMClientInterface


class LLMClientManager:
    """Manager class to instantiate the configured LLM client."""

    def __init__(self, helper_config: HelperConfig):
        self.helper_config = helper_config
        self.logging = helper_config.get_logger()
        self.client = self._initialize_client()

    def _get_engine_from_env(self) -> str:
        """Read the LLM engine name from env configuration.

        Returns:
            str: Capitalised engine name (e.g. "Ollama").

        Raises:
            ValueError: If LLM_ENGINE is not set or empty.
        """
        engine = self.helper_config.get_string_val("LLM_ENGINE")
        if not engine:
            raise ValueError("No LLM engine specified in configuration (LLM_ENGINE).")
        return engine.strip().lower().capitalize()

    def _initialize_client(self) -> LLMClientInterface:
        """Instantiate the LLM client for the configured engine.

        Returns:
            LLMClientInterface: The instantiated client.

        Raises:
            ValueError: If the engine is unsupported or cannot be imported.
        """
        engine = self._get_engine_from_env()
        class_name = f"LLMClient{engine}"
        try:
            module = __import__(
                f"shared.clients.llm.{engine.lower()}.{class_name}",
                fromlist=[class_name],
            )
            client_class = getattr(module, class_name)
            client = client_class(helper_config=self.helper_config)
            self.logging.debug("Instantiated LLM client for engine: %s", engine)
            return client
        except (ImportError, AttributeError) as e:
            raise ValueError("Unsupported LLM engine '%s'. Error: %s" % (engine, e))

    def get_client(self) -> LLMClientInterface:
        """Return the instantiated LLM client."""
        return self.client
