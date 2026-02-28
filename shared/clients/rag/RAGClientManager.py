
from shared.helper.HelperConfig import HelperConfig
from shared.clients.rag.RAGClientInterface import RAGClientInterface

class RAGClientManager:
    """
    Manager class to handle multiple RAG clients based on configuration.
    """

    def __init__(self, helper_config: HelperConfig):
        self.helper_config = helper_config
        self.logging = helper_config.get_logger()
        self.clients = self._initialize_clients()

    def _get_engines_from_env(self) -> list[str]:
        """
        Reads the list of RAG engines from ENV configuration.

        Returns:
            list[str]: A list of RAG engine names.

        Raises:
            ValueError: If no RAG engines are specified in the configuration or if the specified engines are invalid.
        """
        engines = self.helper_config.get_list_val("RAG_ENGINES")
        if not engines:
            raise ValueError("No RAG engines specified in configuration.")
        
        #lowercase all and uppcercase first letter for better comparison and display
        engines = [engine.strip().lower() for engine in engines]
        engines = [engine.capitalize() for engine in engines]
        return engines

    def _initialize_clients(self) -> list[RAGClientInterface]:
        """
        Initializes RAG clients based on the engines specified in the configuration.

        Returns:
            list[RAGClientInterface]: A list of instances of RAG clients that implement the RAGClientInterface.

        Raises:
            ValueError: If no valid RAG clients could be instantiated from the specified engines.
        """
        #iterate engines and instanciate clients. If there is an unsupported engine, raise error
        clients = []
        for engine in self._get_engines_from_env():
            className = f"RAGClient{engine}"
            # try to import the class from shared.clients.rag.{engine}
            try:
                module = __import__(
                    f"shared.clients.rag.{engine.lower()}.{className}",
                    fromlist=[className],
                )
                client_class = getattr(module, className)
                client_instance = client_class(helper_config=self.helper_config)
                clients.append(client_instance)
                self.logging.debug(f"Instantiated RAG client for engine: {engine}")
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Unsupported RAG engine specified: '{engine}'. Error: {e}")
        if not clients:
            raise ValueError("No valid RAG clients could be instantiated from the specified engines.")
        return clients

    def get_clients(self) -> list[RAGClientInterface]:
        """
        Returns the list of instantiated RAG clients.

        Returns:
            list[RAGClientInterface]: The list of RAG client instances.
        """
        return self.clients