from abc import abstractmethod

from shared.clients.ClientInterface import ClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig


class OCRClientInterface(ClientInterface):
    """Abstract base class for all OCR client backends.

    Concrete subclasses implement document-to-text conversion via an external
    OCR service (e.g. Docling).  The single public action method is
    ``do_convert_pdf_to_markdown``, which uploads raw file bytes and returns extracted
    Markdown text.
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        super().__init__(helper_config=helper_config)
        # OCR conversion is slow; use 300 s as default unless OCR_TIMEOUT is set explicitly.
        # super().__init__() already read OCR_TIMEOUT with default=30 — override it here.
        self.timeout = helper_config.get_number_val("OCR_TIMEOUT", default=300.0)

    ##########################################
    ################ GETTER ##################
    ##########################################

    def _get_client_type(self) -> str:
        return "ocr"

    @abstractmethod
    def _get_engine_name(self) -> str:
        pass

    @abstractmethod
    def _get_base_url(self) -> str:
        pass

    @abstractmethod
    def _get_auth_header(self) -> dict:
        pass

    @abstractmethod
    def _get_endpoint_healthcheck(self) -> str:
        pass

    @abstractmethod
    def _get_endpoint_convert_pdf_to_markdown(self) -> str:
        """Returns the endpoint path for the PDF-to-Markdown conversion request."""
        pass

    @abstractmethod
    def _get_required_config(self) -> list[EnvConfig]:
        pass

    ##########################################
    ############# PAYLOAD HOOKS ##############
    ##########################################

    @abstractmethod
    def _get_convert_pdf_to_markdown_payload(self, file_bytes: bytes, filename: str) -> dict | list:
        """Build the multipart files argument for the PDF-to-Markdown conversion request.

        Args:
            file_bytes: Raw content of the file to convert.
            filename:   Original filename including extension.

        Returns:
            The value to pass as the ``files`` argument to ``do_request``.
        """
        pass

    ##########################################
    ############# HELPERS ####################
    ##########################################

    @abstractmethod
    def _parse_convert_file_response(self, response: dict) -> str:
        """Extract the Markdown text from the raw JSON response.

        Args:
            response: Parsed JSON body returned by the OCR service.

        Returns:
            Extracted Markdown string.

        Raises:
            RuntimeError: If the response indicates failure or contains no content.
        """
        pass

    ##########################################
    ############# REQUESTS ###################
    ##########################################

    async def do_convert_pdf_to_markdown(self, file_bytes: bytes, filename: str) -> str:
        """Upload *file_bytes* to the OCR service and return the extracted Markdown.

        Args:
            file_bytes: Raw content of the file to convert.
            filename:   Original filename including extension (used as the
                        multipart field name so the service can infer format).

        Returns:
            Extracted Markdown string.

        Raises:
            RuntimeError: If the HTTP request fails or the response contains no content.
        """
        try:
            files = self._get_convert_pdf_to_markdown_payload(file_bytes, filename)
            response = await self.do_request(
                method="POST",
                endpoint=self._get_endpoint_convert_pdf_to_markdown(),
                files=files,
            )

            if response.status_code >= 300:
                raise RuntimeError(
                    "OCR service returned status %d for file '%s': %s"
                    % (response.status_code, filename, response.text)
                )

            return self._parse_convert_file_response(response.json())
        except Exception as e:
            self.logging.error(
                "Error during OCR conversion of file '%s': %s", filename, str(e)
            )
            raise e
