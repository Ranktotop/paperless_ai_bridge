
from shared.clients.cache.CacheClientInterface import KEY_FILTER_OPTIONS
from shared.clients.cache.CacheClientInterface import CacheClientInterface
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.helper.HelperConfig import HelperConfig
import asyncio

from dataclasses import dataclass, field

@dataclass
class RagResponse:
    dms_engine: str
    owner_id: str
    cache_key:str
    correspondents: list[str] = field(default_factory=list)
    document_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

class CacheHelper:
    def __init__(self, cache_client: CacheClientInterface, rag_clients: list[RAGClientInterface], config: HelperConfig):
        self._cache_client = cache_client
        self._config = config
        self._rag_clients = rag_clients
        self.logging = config.get_logger()
        self._rag_data:dict[str, dict[str, RagResponse]] = {} # [engine][owner_id] -> RagResponse

    ##########################################
    ################# GETTER #################
    ##########################################

    async def get_data(self, dms_engine: str, owner_id: str, force_live: bool = False) -> RagResponse:
        data:RagResponse|None = None
        source = "unknown"
        # fetch from cache primary if not forced live
        cache_result = await self._fetch_from_cache(dms_engine, owner_id) if not force_live else None
        if cache_result is not None:
            source = "cached"
            data = cache_result
        # fetch from rags secondary
        else:        
            source = "live"
            data = await self._fetch_from_rags(dms_engine, owner_id)

        #error gate
        if data is None:
            raise Exception(f"Failed to fetch data for engine {dms_engine} and owner_id {owner_id} from both cache and RAG backends.")
        #convert RagResponse data to dict (with copy) and log the count of each filter value for better readability
        dict_data = data.__dict__.copy()
        dict_data["correspondents"] = len(dict_data["correspondents"])
        dict_data["document_types"] = len(dict_data["document_types"])
        dict_data["tags"] = len(dict_data["tags"])
        self.logging.debug(f"Fetched {source} data for engine {dms_engine} and owner_id {owner_id}:\n{dict_data}")

        # return the original data object
        return data

    ##########################################
    ################# CACHE ##################
    ##########################################

    def _create_cache_key(self, *values) -> str:
        """
        Returns a cache key for the provided values.

        Args:
            values: Variable length argument list of strings to be included in the cache key after the namespace.

        Returns:
            str: Cache key for filter options corresponding to the provided values.
        """
        #dynamically create cache keys based on the number of values provided
        base_key = KEY_FILTER_OPTIONS
        for value in values:
            base_key += f":{value}"
        return base_key
    
    async def _fetch_from_cache(self, dms_engine:str, owner_id:str) -> RagResponse|None:
        """
        Fetches a value from the cache based on the provided filter values.

        Args:
            dms_engine: The DMS engine name. E.g. paperless, filestash, etc.
            owner_id: The owner ID.
        Returns:
            RagResponse|None: The value corresponding to the provided filter values fetched from cache. Returns None if cache miss occurs.
        """        
        # make sure engine is lc
        dms_engine = dms_engine.lower()
        key = self._create_cache_key(dms_engine, owner_id)
        cache_result = await self._cache_client.do_get_json(key)
        if cache_result is None:
            return None
        result = RagResponse(
            dms_engine=dms_engine,
            owner_id=owner_id,
            cache_key=key,
            correspondents=cache_result.get("correspondents", []),
            document_types=cache_result.get("document_types", []),
            tags=cache_result.get("tags", []))
        self.logging.debug(f"Fetching from cache with key: {key}, result: {result}")
        return result
    
    async def _fetch_from_rags(self, dms_engine:str, owner_id:str) -> RagResponse:
        """
        Fetches all documents for given dms_engine and owner_id from RAG backends, extracts distinct filter values, and returns them as a merged RagResponse object. 
        The result is also written to cache for future requests.

        Args:
            dms_engine: The DMS engine name. E.g. paperless, filestash, etc.
            owner_id: The owner ID.

        Returns:
            RagResponse: The values corresponding to the provided filter values fetched from RAG backend.
        """
        # make sure engine is lc
        dms_engine = dms_engine.lower()
        #if already fetched for this owner_id, return from memory cache
        if dms_engine in self._rag_data and owner_id in self._rag_data[dms_engine]:
            self.logging.debug(f"Fetching data for engine {dms_engine} and owner_id {owner_id} from memory cache.")
            return self._rag_data[dms_engine][owner_id]
        
        #define the scroll task for rag client      
        self.logging.debug(f"Fetching data for engine {dms_engine} and owner_id {owner_id} from RAG backend.")
        #define the scroll tasks as coroutines for all rag clients
        scroll_tasks = [
            rag_client.do_fetch_points(
                filters=[
                    {"key": "dms_engine", "match": {"value": dms_engine}},
                    {"key": "owner_id", "match": {"value": owner_id}},
                ],
                include_fields=["category_name", "type_name", "label_names"],
                with_vector=False,
            )
            for rag_client in self._rag_clients
        ]
        #execute all scroll tasks in parallel and gather results
        scroll_responses = await asyncio.gather(*scroll_tasks, return_exceptions=True)

        #Prepare empty response object to collect results from all rag clients for this dms engine and owner_id.
        result = RagResponse(
            dms_engine=dms_engine,
            owner_id=owner_id,
            cache_key=self._create_cache_key(dms_engine, owner_id),
            correspondents=set(),
            document_types=set(),
            tags=set())
        
        #iterate results from all rag clients
        has_errors = False
        for idx, points in enumerate(scroll_responses):

            #get the corresponding rag client
            rag_client = self._rag_clients[idx]

            #if result is exception, log warning and continue with next result
            if isinstance(points, Exception):
                self.logging.warning(f"Error occured while fetching data from RAG client [{rag_client.get_engine_name()}]: {points}", color="yellow")
                has_errors = True
                continue
            
            for point in points:
                if point.category_name:
                    result.correspondents.add(point.category_name)
                if point.type_name:
                    result.document_types.add(point.type_name)
                for label in point.label_names:
                    if label:
                        result.tags.add(label)

        #sort the sets and convert to lists for better readability
        result.correspondents = sorted(result.correspondents)
        result.document_types = sorted(result.document_types)
        result.tags = sorted(result.tags)
        
        #upsert to cache if not error occured during fetching from rags
        if not has_errors:                
            try:
                cache_data = {
                    "correspondents": result.correspondents,
                    "document_types": result.document_types,
                    "tags": result.tags}                
                await self._cache_client.do_set_json(result.cache_key, cache_data)
            except Exception as exc:
                self.logging.warning(f"Error occured while writing rag data to cache with key {result.cache_key}: {exc}", color="yellow")

        # save results to memory cache
        if not dms_engine in self._rag_data:
            self._rag_data[dms_engine] = {}
        self._rag_data[dms_engine][owner_id] = result
        return result