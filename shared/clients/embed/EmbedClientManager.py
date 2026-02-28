
from shared.helper.HelperConfig import HelperConfig
from shared.clients.embed.EmbedClientInterface import EmbedClientInterface

class EmbedClientManager:
    """
    Manager class to handle Embed client based on configuration.
    """

    def __init__(self, helper_config: HelperConfig):
        self.helper_config = helper_config
        self.logging = helper_config.get_logger()
        self.client = self._initialize_client()

    def _get_engine_from_env(self) -> str:
        """
        Reads the Embed engine from ENV configuration.

        Returns:
            str: The name of the Embed engine.

        Raises:
            ValueError: If no Embed engine is specified in the configuration or if the specified engine is invalid.
        """
        engine = self.helper_config.get_string_val("EMBED_ENGINE")
        if not engine:
            raise ValueError("No Embed engine specified in configuration.")
        
        #lowercase all and uppcercase first letter for better comparison and display
        engine = engine.strip().lower()
        engine = engine.capitalize()
        return engine

    def _initialize_client(self) -> EmbedClientInterface:
        """
        Initializes the Embed client based on the engine specified in the configuration.

        Returns:
            EmbedClientInterface: An instance of the Embed client that implements the EmbedClientInterface.

        Raises:
            ValueError: If no valid Embed clients could be instantiated from the specified engine.
        """
        #iterate engines and instanciate clients. If there is an unsupported engine, raise error
        client = None
        engine = self._get_engine_from_env()
        className = f"EmbedClient{engine}"
        # try to import the class from shared.clients.dms.{engine}
        try:
            module = __import__(
                f"shared.clients.embed.{engine.lower()}.{className}",
                fromlist=[className],
            )
            client_class = getattr(module, className)
            client_instance = client_class(helper_config=self.helper_config)
            client = client_instance
            self.logging.debug(f"Instantiated Embed client for engine: {engine}")
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Unsupported Embed engine specified: '{engine}'. Error: {e}")
            
        if not client:
            raise ValueError("No valid Embed clients could be instantiated from the specified engines.")
        return client

    def get_client(self) -> EmbedClientInterface:
        """
        Returns the instantiated Embed client.

        Returns:
            EmbedClientInterface: The Embed client instance.
        """
        return self.client