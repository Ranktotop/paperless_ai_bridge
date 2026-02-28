"""Query service — orchestrates semantic search against the Qdrant vector index.

Phase II: embed query text → Qdrant scroll with owner_id filter → return ranked results.
Phase III (future): add LangChain ReAct agent with intent classification and
  self-querying metadata filter translation.
"""

from shared.clients.EmbedInterface import EmbedInterface
from shared.clients.VectorDBInterface import VectorDBInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.search import SearchRequest, SearchResponse, SearchResultItem


class QueryService:
    """Orchestrates embedding, vector retrieval, and result assembly for document search."""

    def __init__(
        self,
        helper_config: HelperConfig,
        qdrant_client: VectorDBInterface,
        embed_client: EmbedInterface,
    ) -> None:
        self.logging = helper_config.get_logger()
        self._qdrant = qdrant_client
        self._embed = embed_client

    ##########################################
    ################ CORE ####################
    ##########################################

    async def do_query(self, request: SearchRequest) -> SearchResponse:
        """Execute a natural language query against the user's document index.

        Embeds the query text, searches Qdrant with a mandatory owner_id filter,
        and returns the ranked matching document chunks.

        Args:
            request (SearchRequest): The incoming query with text, owner_id, and limit.

        Returns:
            SearchResponse: Ranked list of matching document chunks.
        """
        self.logging.info(
            "Executing query — owner_id=%d query=%r limit=%d",
            request.owner_id,
            request.query[:80],
            request.limit,
        )

        vector = await self._embed.embed_text(request.query)
        hits = await self._qdrant.do_scroll(
            query_vector=vector,
            owner_id=request.owner_id,
            limit=request.limit,
        )
        items = self._build_result_items(hits)

        self.logging.info(
            "Query complete — owner_id=%d results=%d",
            request.owner_id,
            len(items),
        )
        return SearchResponse(query=request.query, results=items, total=len(items))

    ##########################################
    ############### HELPERS ##################
    ##########################################

    def _build_result_items(self, qdrant_hits: list[dict]) -> list[SearchResultItem]:
        """Convert raw Qdrant search hits into SearchResultItem models.

        Args:
            qdrant_hits (list[dict]): Raw result points from Qdrant.

        Returns:
            list[SearchResultItem]: Structured result items.
        """
        items: list[SearchResultItem] = []
        for hit in qdrant_hits:
            payload = hit.get("payload", {})
            items.append(
                SearchResultItem(
                    paperless_id=payload.get("paperless_id", 0),
                    title=payload.get("title", ""),
                    score=hit.get("score", 0.0),
                    chunk_text=payload.get("chunk_text"),
                )
            )
        return items
