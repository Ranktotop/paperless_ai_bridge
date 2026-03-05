from shared.clients.ocr.OCRClientInterface import OCRClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig


class OCRClientDocling(OCRClientInterface):
    """OCR client backed by a self-hosted Docling server (v1.12.0+).

    Sends documents to ``POST /v1/convert/file`` as multipart/form-data and
    returns the ``document.md_content`` field from the response as Markdown.
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        # Read optional config before calling super().__init__ so the values
        # are available if validate_full_configuration() is triggered inside super.
        # We read them again after super().__init__ using get_config_val for
        # proper key namespacing; here we just need defaults set.
        super().__init__(helper_config=helper_config)

        self._base_url: str = self.get_config_val("BASE_URL", default=None, val_type="string")
        self._api_key: str = self.get_config_val("API_KEY", default="", val_type="string")

    ##########################################
    ################ GETTER ##################
    ##########################################

    def _get_engine_name(self) -> str:
        return "Docling"

    def _get_base_url(self) -> str:
        return self._base_url

    def _get_required_config(self) -> list[EnvConfig]:
        return [
            EnvConfig(env_key="BASE_URL", val_type="string", default=None),
        ]

    ################ AUTH ##################

    def _get_auth_header(self) -> dict:
        if self._api_key:
            return {"X-Api-Key": self._api_key}
        return {}

    ################ ENDPOINTS ##################

    def _get_endpoint_healthcheck(self) -> str:
        return "/health"

    def _get_endpoint_convert_pdf_to_markdown(self) -> str:
        return "/v1/convert/file"

    ##########################################
    ############# PAYLOAD HOOKS ##############
    ##########################################

    def _get_convert_pdf_to_markdown_payload(self, file_bytes: bytes, filename: str) -> list:
        """Build the Docling multipart request for PDF-to-Markdown conversion.

        All fields including the file are passed as a list of tuples so that
        httpx builds a MultipartStream (AsyncByteStream-compatible). Mixing
        a dict/list ``data`` argument with ``files`` produces an IteratorByteStream
        which the AsyncClient rejects.
        Non-file form fields use the (None, value) 3-tuple convention.

        Args:
            file_bytes: Raw bytes of the file to convert.
            filename:   Original filename including extension.

        Returns:
            list: Multipart tuples for the ``files`` argument of ``do_request``.
        """
        multipart: list[tuple[str, tuple]] = [
            ("files", (filename, file_bytes, "application/octet-stream")),
            ("to_formats", (None, "md")),
            ("from_formats", (None, "pdf")),
            ("do_ocr", (None, "true")),
            ("image_export_mode", (None, "placeholder")),
            ("pdf_backend", (None, "dlparse_v4"))
        ]
        return multipart

    ##########################################
    ############# HELPERS ####################
    ##########################################

    def _parse_convert_file_response(self, response: dict) -> str:
        """Extract Markdown content from a Docling ``ConvertDocumentResponse``.

        Args:
            response: Parsed JSON body from Docling.

        Returns:
            Markdown string from ``document.md_content``.

        Raises:
            RuntimeError: If status is not success/partial_success or content is empty.
        """
        status = response.get("status", "")
        if status not in ("success", "partial_success"):
            raise RuntimeError(
                "Docling conversion failed with status '%s'" % status
            )

        document = response.get("document") or {}
        md_content: str = document.get("md_content") or ""

        #remove image placeholder like <!-- image -->
        md_content = md_content.replace("<!-- image -->", "")

        #if image was between double new lines we remove four new lines in a row to avoid too many empty lines in the final markdown
        md_content = md_content.replace("\n\n\n\n", "\n\n")

        if not md_content.strip():
            raise RuntimeError(
                "Docling returned empty md_content (status='%s')" % status
            )
        


        return md_content
