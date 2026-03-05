from shared.clients.ocr.OCRClientInterface import OCRClientInterface
from shared.helper.HelperConfig import HelperConfig


class OCRClientManager:
    """Factory that instantiates a single OCR client from the ``OCR_ENGINE`` env var.

    The engine name is resolved via reflection:
    ``shared.clients.ocr.{engine_lower}.OCRClient{Engine}``
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        self._helper_config = helper_config
        self.logging = helper_config.get_logger()
        self._client: OCRClientInterface = self._initialize_client()

    def _get_engine_from_env(self) -> str:
        """Read and normalise the OCR engine name from ``OCR_ENGINE``.

        Returns:
            Engine name with first letter capitalised (e.g. ``"Docling"``).

        Raises:
            ValueError: If ``OCR_ENGINE`` is not set.
        """
        engine = self._helper_config.get_string_val("OCR_ENGINE")
        if not engine:
            raise ValueError("OCR_ENGINE is not set in configuration.")
        return engine.strip().lower().capitalize()

    def _initialize_client(self) -> OCRClientInterface:
        """Instantiate the OCR client for the configured engine.

        Returns:
            An ``OCRClientInterface`` instance.

        Raises:
            ValueError: If the engine module or class cannot be found.
        """
        engine = self._get_engine_from_env()
        class_name = "OCRClient%s" % engine
        try:
            module = __import__(
                "shared.clients.ocr.%s.%s" % (engine.lower(), class_name),
                fromlist=[class_name],
            )
            client_class = getattr(module, class_name)
            client_instance: OCRClientInterface = client_class(helper_config=self._helper_config)
            self.logging.debug("Instantiated OCR client for engine: %s", engine)
            return client_instance
        except (ImportError, AttributeError) as e:
            raise ValueError(
                "Unsupported OCR engine specified: '%s'. Error: %s" % (engine, e)
            )

    def get_client(self) -> OCRClientInterface:
        """Return the instantiated OCR client.

        Returns:
            The single ``OCRClientInterface`` instance.
        """
        return self._client
