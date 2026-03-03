from shared.clients.cache.CacheClientInterface import CacheClientInterface
from shared.helper.HelperConfig import HelperConfig


class CacheClientManager:
    """Manager class to instantiate the configured cache client."""

    def __init__(self, helper_config: HelperConfig) -> None:
        self.helper_config = helper_config
        self.logging = helper_config.get_logger()
        self.client = self._initialize_client()

    def _get_engine_from_env(self) -> str:
        """Read the cache engine name from env configuration.

        Returns:
            str: Capitalised engine name (e.g. "Redis").

        Raises:
            ValueError: If CACHE_ENGINE is not set or empty.
        """
        engine = self.helper_config.get_string_val("CACHE_ENGINE")
        if not engine:
            raise ValueError("No cache engine specified in configuration (CACHE_ENGINE).")
        return engine.strip().lower().capitalize()

    def _initialize_client(self) -> CacheClientInterface:
        """Instantiate the cache client for the configured engine.

        Returns:
            CacheClientInterface: The instantiated client.

        Raises:
            ValueError: If the engine is unsupported or cannot be imported.
        """
        engine = self._get_engine_from_env()
        class_name = f"CacheClient{engine}"
        try:
            module = __import__(
                f"shared.clients.cache.{engine.lower()}.{class_name}",
                fromlist=[class_name],
            )
            client_class = getattr(module, class_name)
            client = client_class(helper_config=self.helper_config)
            self.logging.debug("Instantiated cache client for engine: %s", engine)
            return client
        except (ImportError, AttributeError) as e:
            raise ValueError("Unsupported cache engine '%s'. Error: %s" % (engine, e))

    def get_client(self) -> CacheClientInterface:
        """Return the instantiated cache client."""
        return self.client
