
from shared.helper.HelperConfig import HelperConfig
from shared.clients.dms.DMSClientInterface import DMSClientInterface

class DMSClientManager:
    """
    Manager class to handle multiple DMS clients based on configuration.
    """

    def __init__(self, helper_config: HelperConfig):
        self.helper_config = helper_config
        self.logging = helper_config.get_logger()
        self.clients = self._initialize_clients()

    def _get_engines_from_env(self) -> list[str]:
        """
        Reads the list of DMS engines from ENV configuration.

        Returns:
            list[str]: A list of DMS engine names.

        Raises:
            ValueError: If no DMS engines are specified in the configuration or if the specified engines are invalid.
        """
        engines = self.helper_config.get_list_val("DMS_ENGINES")
        if not engines:
            raise ValueError("No DMS engines specified in configuration.")
        
        #lowercase all and uppcercase first letter for better comparison and display
        engines = [engine.strip().lower() for engine in engines]
        engines = [engine.capitalize() for engine in engines]
        return engines

    def _initialize_clients(self) -> list[DMSClientInterface]:
        """
        Initializes DMS clients based on the engines specified in the configuration.

        Returns:
            list[DMSClientInterface]: A list of instances of DMS clients that implement the DMSClientInterface.

        Raises:
            ValueError: If no valid DMS clients could be instantiated from the specified engines.
        """
        #iterate engines and instanciate clients. If there is an unsupported engine, raise error
        clients = []
        for engine in self._get_engines_from_env():
            className = f"DMSClient{engine}"
            # try to import the class from shared.clients.dms.{engine}
            try:
                module = __import__(
                    f"shared.clients.dms.{engine.lower()}.{className}",
                    fromlist=[className],
                )
                client_class = getattr(module, className)
                client_instance = client_class(helper_config=self.helper_config)
                clients.append(client_instance)
                self.logging.debug(f"Instantiated DMS client for engine: {engine}")
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Unsupported DMS engine specified: '{engine}'. Error: {e}")
        if not clients:
            raise ValueError("No valid DMS clients could be instantiated from the specified engines.")
        return clients

    def get_clients(self) -> list[DMSClientInterface]:
        """
        Returns the list of instantiated DMS clients.

        Returns:
            list[DMSClientInterface]: The list of DMS client instances.
        """
        return self.clients