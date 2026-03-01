from shared.clients.llm.LLMClientInterface import LLMClientInterface
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.helper.HelperConfig import HelperConfig
from server.models.requests import SearchRequest
from server.models.responses import SearchResponse, SearchResultItem


class QueryService:
    """Handles semantic search queries: embed -> scroll -> map results."""

    def __init__(
        self,
        helper_config: HelperConfig,
        rag_clients: list[RAGClientInterface],
        llm_client: LLMClientInterface,
    ) -> None:
        self.logging = helper_config.get_logger()
        self._rag_clients = rag_clients
        self._llm_client = llm_client

    ##########################################
    ############### CORE #####################
    ##########################################

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Embed a query, scroll the RAG backend, and return matching chunks.

        Phase III: uses do_scroll() with a payload filter on owner_id.
        Score is set to 0.0 as a placeholder until Phase IV vector similarity
        search is implemented.

        Args:
            request (SearchRequest): The search request with query, owner_id, and limit.

        Returns:
            SearchResponse: The matching document chunks with metadata.
        """
        self.logging.info(
            "QueryService.search: query='%s', owner_id=%d, limit=%d",
            request.query, request.owner_id, request.limit,
        )

        # embed the query text
        vectors = await self._llm_client.do_embed([request.query])
        query_vector = vectors[0]
        self.logging.debug("Query vector dimension: %d", len(query_vector))

        # use the first RAG client for Phase III (no multi-RAG routing yet)
        rag_client = self._rag_clients[0]

        # scroll with mandatory owner_id filter
        filters = {
            "must": [
                {"key": "owner_id", "match": {"value": str(request.owner_id)}},
            ]
        }
        scroll_result = await rag_client.do_scroll(
            filters=filters,
            with_payload=True,
            with_vector=False,
            limit=request.limit,
        )

        # map raw points to SearchResultItem
        items: list[SearchResultItem] = []
        for point in scroll_result.result:
            payload = point.get("payload") or {}
            item = SearchResultItem(
                dms_doc_id=str(payload.get("dms_doc_id", "")),
                title=str(payload.get("title", "")),
                chunk_text=payload.get("chunk_text"),
                score=0.0,
                created=payload.get("created"),
                category_name=payload.get("category_name"),
                type_name=payload.get("type_name"),
                label_names=payload.get("label_names") or [],
            )
            items.append(item)

        self.logging.info("QueryService.search: returning %d result(s).", len(items))
        return SearchResponse(
            query=request.query,
            results=items,
            total=len(items),
        )
