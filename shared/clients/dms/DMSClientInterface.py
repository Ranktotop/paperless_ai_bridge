from abc import abstractmethod
from shared.helper.HelperConfig import HelperConfig
from shared.clients.ClientInterface import ClientInterface
from shared.clients.dms.models.Document import DocumentBase, DocumentDetails, DocumentsListResponse, DocumentHighDetails
from shared.clients.dms.models.Correspondent import CorrespondentBase, CorrespondentDetails, CorrespondentsListResponse
from shared.clients.dms.models.Tag import TagBase, TagDetails, TagsListResponse
from shared.clients.dms.models.Owner import OwnerBase, OwnerDetails, OwnersListResponse
from shared.clients.dms.models.DocumentType import DocumentTypeBase, DocumentTypeDetails, DocumentTypesListResponse
from typing import Callable, TypeVar
T = TypeVar("T")

class DMSClientInterface(ClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)

        # cache 
        self._cache_documents: dict[str, DocumentDetails] | None = None
        self._cache_correspondents: dict[str, CorrespondentDetails] | None = None
        self._cache_tags: dict[str, TagDetails] | None = None
        self._cache_owners: dict[str, OwnerDetails] | None = None
        self._cache_document_types: dict[str, DocumentTypeDetails] | None = None
        self._cache_enriched_documents: dict[str, DocumentHighDetails] | None = None

    ##########################################
    ############### CHECKER ##################
    ##########################################

    ##########################################
    ################ GETTER ##################
    ##########################################

    ################ GENERAL ##################
    def _get_client_type(self) -> str:
        """
        Returns the type of the client. E.g. "rag"
        """
        return "dms"
    
    def get_enriched_documents(self) -> list[DocumentHighDetails]:
        """
        Returns the enriched document details cache, which contains all the information needed for the LLM prompt in one place. This is filled during the fill_cache() method.

        Returns:
            list[DocumentHighDetails]: A list of enriched document details.

        """
        if self._cache_enriched_documents is None:
            raise Exception("Enriched document cache is not filled yet. Please call fill_cache() first.")
        return list(self._cache_enriched_documents.values())

    ################ ENDPOINTS ##################
    @abstractmethod
    def _get_endpoint_documents(self, page:int = 1, page_size:int=100) -> str:
        """
        Returns the endpoint path for document listing requests.
        
        Args:
            page (int): The page number for paginated document listing.
            page_size (int): The number of documents per page for paginated document listing.

        Returns:
            str: The endpoint path for document listing requests (e.g. "/api/documents")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_correspondents(self, page:int = 1, page_size:int=100) -> str:
        """
        Returns the endpoint path for correspondent requests.
        
        Args:
            page (int): The page number for paginated correspondent listing.
            page_size (int): The number of correspondents per page for paginated correspondent listing.

        Returns:
            str: The endpoint path for correspondent requests (e.g. "/api/correspondents")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_tags(self, page:int = 1, page_size:int=100) -> str:
        """
        Returns the endpoint path for tag requests.
        
        Args:
            page (int): The page number for paginated tag listing.
            page_size (int): The number of tags per page for paginated tag listing.

        Returns:
            str: The endpoint path for tag requests (e.g. "/api/tags")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_owners(self, page:int = 1, page_size:int=100) -> str:
        """
        Returns the endpoint path for owner requests.
        
        Args:
            page (int): The page number for paginated owner listing.
            page_size (int): The number of owners per page for paginated owner listing.

        Returns:
            str: The endpoint path for owner requests (e.g. "/api/owners")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_document_types(self, page:int = 1, page_size:int=100) -> str:
        """
        Returns the endpoint path for document type requests.
        
        Args:
            page (int): The page number for paginated document type listing.
            page_size (int): The number of document types per page for paginated document type listing.

        Returns:
            str: The endpoint path for document type requests (e.g. "/api/document_types")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_document_details(self, document_id: str) -> str:
        """
        Returns the endpoint path for document details requests.
        
        Args:
            document_id (str): The ID of the document.

        Returns:
            str: The endpoint path for document details requests (e.g. "/api/documents/{id}")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_correspondent_details(self, correspondent_id: str) -> str:
        """
        Returns the endpoint path for correspondent details requests.
        
        Args:
            correspondent_id (str): The ID of the correspondent.

        Returns:
            str: The endpoint path for correspondent details requests (e.g. "/api/correspondents/{id}")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_tag_details(self, tag_id: str) -> str:
        """
        Returns the endpoint path for tag details requests.
        
        Args:
            tag_id (str): The ID of the tag.

        Returns:
            str: The endpoint path for tag details requests (e.g. "/api/tags/{id}")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_owner_details(self, owner_id: str) -> str:
        """
        Returns the endpoint path for owner details requests.
        
        Args:
            owner_id (str): The ID of the owner.

        Returns:
            str: The endpoint path for owner details requests (e.g. "/api/owners/{id}")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_document_type_details(self, document_type_id: str) -> str:
        """
        Returns the endpoint path for document type details requests.
        
        Args:
            document_type_id (str): The ID of the document type.

        Returns:
            str: The endpoint path for document type details requests (e.g. "/api/document_types/{id}")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    ##########################################
    ############### REQUESTS #################
    ##########################################
    
    ############# LISTING REQUESTS ##############
    async def do_fetch_documents(self) -> list[DocumentBase]:
        """
        Fetches all documents from dms backend

        Returns:
            list[DocumentBase]: A list of documents fetched from the backend.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        documents = []
        page = 1
        page_size = 300
        while True:
            resp = await self.do_request(method="GET", endpoint=self._get_endpoint_documents(page=page, page_size=page_size))
            documents_list_response = self._parse_endpoint_documents(resp.json(), requested_page_size=page_size)
            documents.extend(documents_list_response.documents)
            self.logging.info("Fetched documents page %d of %d from %s, total documents so far: %d of %d", page, documents_list_response.lastPage, self._get_engine_name(), len(documents), documents_list_response.overallCount)
            page = documents_list_response.nextPage
            if not page:
                break            
        return documents
    
    async def do_fetch_correspondents(self) -> list[CorrespondentBase]:
        """
        Fetches all correspondents from dms backend

        Returns:
            list[CorrespondentBase]: A list of correspondents fetched from the backend.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        correspondents = []
        page = 1
        page_size = 300
        while True:
            resp = await self.do_request(method="GET", endpoint=self._get_endpoint_correspondents(page=page, page_size=page_size))
            correspondents_list_response = self._parse_endpoint_correspondents(resp.json(), requested_page_size=page_size)
            correspondents.extend(correspondents_list_response.correspondents)
            self.logging.info("Fetched correspondents page %d of %d from %s, total correspondents so far: %d of %d", page, correspondents_list_response.lastPage, self._get_engine_name(), len(correspondents), correspondents_list_response.overallCount)
            page = correspondents_list_response.nextPage
            if not page:
                break            
        return correspondents
    
    async def do_fetch_owners(self) -> list[OwnerBase]:
        """
        Fetches all owners from dms backend

        Returns:
            list[OwnerBase]: A list of owners fetched from the backend.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        owners = []
        page = 1
        page_size = 300
        while True:
            resp = await self.do_request(method="GET", endpoint=self._get_endpoint_owners(page=page, page_size=page_size))
            owners_list_response = self._parse_endpoint_owners(resp.json(), requested_page_size=page_size)
            owners.extend(owners_list_response.owners)
            self.logging.info("Fetched owners page %d of %d from %s, total owners so far: %d of %d", page, owners_list_response.lastPage, self._get_engine_name(), len(owners), owners_list_response.overallCount)
            page = owners_list_response.nextPage
            if not page:
                break            
        return owners
    
    async def do_fetch_tags(self) -> list[TagBase]:
        """
        Fetches all tags from dms backend

        Returns:
            list[TagBase]: A list of tags fetched from the backend.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        tags = []
        page = 1
        page_size = 300
        while True:
            resp = await self.do_request(method="GET", endpoint=self._get_endpoint_tags(page=page, page_size=page_size))
            tags_list_response = self._parse_endpoint_tags(resp.json(), requested_page_size=page_size)
            tags.extend(tags_list_response.tags)
            self.logging.info("Fetched tags page %d of %d from %s, total tags so far: %d of %d", page, tags_list_response.lastPage, self._get_engine_name(), len(tags), tags_list_response.overallCount)
            page = tags_list_response.nextPage
            if not page:
                break            
        return tags
    
    async def do_fetch_document_types(self) -> list[DocumentTypeBase]:
        """
        Fetches all document types from dms backend

        Returns:
            list[DocumentTypeBase]: A list of document types fetched from the backend.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        document_types = []
        page = 1
        page_size = 300
        while True:
            resp = await self.do_request(method="GET", endpoint=self._get_endpoint_document_types(page=page, page_size=page_size))
            document_types_list_response = self._parse_endpoint_document_types(resp.json(), requested_page_size=page_size)
            document_types.extend(document_types_list_response.types)
            self.logging.info("Fetched document types page %d of %d from %s, total document types so far: %d of %d", page, document_types_list_response.lastPage, self._get_engine_name(), len(document_types), document_types_list_response.overallCount)
            page = document_types_list_response.nextPage
            if not page:
                break            
        return document_types
    
    
    ############# GET REQUESTS ##############
    async def do_fetch_document_details(self, document_id: str) -> DocumentDetails:
        """
        Fetches a document from dms backend

        Args:
            document_id (str): The ID of the document to fetch.

        Returns:
            DocumentDetails: The details of the fetched document.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_document_details(document_id))
        document_details = self._parse_endpoint_document(resp.json())
        return document_details
    
    async def do_fetch_correspondent_details(self, correspondent_id: str) -> CorrespondentDetails:
        """
        Fetches a correspondent from dms backend

        Args:
            correspondent_id (str): The ID of the correspondent to fetch.

        Returns:
            CorrespondentDetails: The details of the fetched correspondent.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_correspondent_details(correspondent_id))
        correspondent_details = self._parse_endpoint_correspondent(resp.json())
        return correspondent_details
    
    async def do_fetch_owner_details(self, owner_id: str) -> OwnerDetails:
        """
        Fetches an owner from dms backend

        Args:
            owner_id (str): The ID of the owner to fetch.

        Returns:
            OwnerDetails: The details of the fetched owner.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_owner_details(owner_id))
        owner_details = self._parse_endpoint_owner(resp.json())
        return owner_details
    
    async def do_fetch_tag_details(self, tag_id: str) -> TagDetails:
        """
        Fetches a tag from dms backend

        Args:
            tag_id (str): The ID of the tag to fetch.

        Returns:
            TagDetails: The details of the fetched tag.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_tag_details(tag_id))
        tag_details = self._parse_endpoint_tag(resp.json())
        return tag_details
    
    async def do_fetch_document_type_details(self, document_type_id: str) -> DocumentTypeDetails:
        """
        Fetches a document type from dms backend

        Args:
            document_type_id (str): The ID of the document type to fetch.

        Returns:
            DocumentTypeDetails: The details of the fetched document type.
        Raises:
            Exception: If the response format is invalid or the content cannot be extracted.
            NotImplementedError: If the method is not implemented in a subclass.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_document_type_details(document_type_id))
        document_type_details = self._parse_endpoint_document_type(resp.json())
        return document_type_details

    ##########################################
    ########### RESPONSE PARSER ##############
    ##########################################

    ############### LIST RESPONSES ###############
    @abstractmethod
    def _parse_endpoint_documents(self, response: dict, requested_page_size:int|None = None) -> DocumentsListResponse:
        """
        Parses the response from the document listing endpoint and returns a list of documents with their metadata.

        Args:
            response (dict): The raw response from the document listing endpoint.
            requested_page_size (int | None): The page size that was requested for this document listing. This is used to calculate the last page number in the pagination info. If None, the last page number will be calculated by amount of returned results.
        Returns:
            DocumentsListResponse: The parsed response containing a list of documents and pagination information.
        """
        pass

    @abstractmethod
    def _parse_endpoint_correspondents(self, response: dict, requested_page_size:int|None = None) -> CorrespondentsListResponse:
        """
        Parses the response from the correspondent listing endpoint and returns a list of correspondents with their metadata.

        Args:
            response (dict): The raw response from the correspondent listing endpoint.
            requested_page_size (int | None): The page size that was requested for this correspondent listing. This is used to calculate the last page number in the pagination info. If None, the last page number will be calculated by amount of returned results.
        Returns:
            CorrespondentsListResponse: The parsed response containing a list of correspondents and pagination information.
        """
        pass

    @abstractmethod
    def _parse_endpoint_owners(self, response: dict, requested_page_size:int|None = None) -> OwnersListResponse:
        """
        Parses the response from the owner listing endpoint and returns a list of owners with their metadata.

        Args:
            response (dict): The raw response from the owner listing endpoint.
            requested_page_size (int | None): The page size that was requested for this owner listing. This is used to calculate the last page number in the pagination info. If None, the last page number will be calculated by amount of returned results.
        Returns:
            OwnersListResponse: The parsed response containing a list of owners and pagination information.
        """
        pass

    @abstractmethod
    def _parse_endpoint_tags(self, response: dict, requested_page_size:int|None = None) -> TagsListResponse:
        """
        Parses the response from the tag listing endpoint and returns a list of tags with their metadata.

        Args:
            response (dict): The raw response from the tag listing endpoint.
            requested_page_size (int | None): The page size that was requested for this tag listing. This is used to calculate the last page number in the pagination info. If None, the last page number will be calculated by amount of returned results.
        Returns:
            TagsListResponse: The parsed response containing a list of tags and pagination information.
        """
        pass

    @abstractmethod
    def _parse_endpoint_document_types(self, response: dict, requested_page_size:int|None = None) -> DocumentTypesListResponse:
        """
        Parses the response from the document type listing endpoint and returns a list of document types with their metadata.

        Args:
            response (dict): The raw response from the document type listing endpoint.
            requested_page_size (int | None): The page size that was requested for this document type listing. This is used to calculate the last page number in the pagination info. If None, the last page number will be calculated by amount of returned results.
        Returns:
            DocumentTypesListResponse: The parsed response containing a list of document types and pagination information.
        """
        pass

    ############ GET RESPONSES ##############
    @abstractmethod
    def _parse_endpoint_document(self, response: dict) -> DocumentDetails:
        """
        Parses a raw document dict from the backend API into a DocumentDetails object.

        Args:
            response (dict): The raw document data as returned by the backend API.
        Returns:
            DocumentDetails: The parsed document object.
        Raises:
            Exception: If required fields are missing or the data format is invalid.
        """
        pass

    @abstractmethod
    def _parse_endpoint_correspondent(self, response: dict) -> CorrespondentDetails:
        """
        Parses a raw correspondent dict from the backend API into a CorrespondentDetails object.

        Args:
            response (dict): The raw correspondent data as returned by the backend API.
        Returns:
            CorrespondentDetails: The parsed correspondent object.
        Raises:
            Exception: If required fields are missing or the data format is invalid.
        """
        pass

    @abstractmethod
    def _parse_endpoint_owner(self, response: dict) -> OwnerDetails:
        """
        Parses a raw owner dict from the backend API into a OwnerDetails object.

        Args:
            response (dict): The raw owner data as returned by the backend API.
        Returns:
            OwnerDetails: The parsed owner object.
        Raises:
            Exception: If required fields are missing or the data format is invalid.
        """
        pass

    @abstractmethod
    def _parse_endpoint_tag(self, response: dict) -> TagDetails:
        """
        Parses a raw tag dict from the backend API into a TagDetails object.

        Args:
            response (dict): The raw tag data as returned by the backend API.
        Returns:
            TagDetails: The parsed tag object.
        Raises:
            Exception: If required fields are missing or the data format is invalid.
        """
        pass

    @abstractmethod
    def _parse_endpoint_document_type(self, response: dict) -> DocumentTypeDetails:
        """
        Parses a raw document type dict from the backend API into a DocumentTypeDetails object.

        Args:
            response (dict): The raw document type data as returned by the backend API.
        Returns:
            DocumentTypeDetails: The parsed document type object.
        Raises:
            Exception: If required fields are missing or the data format is invalid.
        """
        pass

    ##########################################
    ################# CACHE ##################
    ##########################################

    async def fill_cache(self, force_refresh: bool = False) -> None:
        """
        Fill the internal cache with any reference data needed for document resolution (e.g. correspondent and tag names).
        This is called once at startup before the sync to avoid redundant requests during document processing.

        Args:
            force_refresh (bool): If True, forces a cache refresh even if data is already present. This can be used to ensure the cache is up to date if there are changes in the backend after the initial fill.
        """
        await self.get_document_types(force=force_refresh)
        await self.get_owners(force=force_refresh)
        await self.get_tags(force=force_refresh)
        await self.get_correspondents(force=force_refresh)
        await self.get_documents(force=force_refresh)

        # check if enrichment is needed
        if self._cache_enriched_documents is not None and not force_refresh:
            return
        
        # now build the enriched document cache with all the details needed for the LLM prompt in one place
        enriched_documents: dict[str, DocumentHighDetails] = {}
        for document_id, document_details in self._cache_documents.items():
            correspondent = None
            owner = None
            tags = []
            document_type = None

            if document_details.correspondent_id and self._cache_correspondents and document_details.correspondent_id in self._cache_correspondents:
                correspondent = self._cache_correspondents[document_details.correspondent_id]
            if document_details.owner_id and self._cache_owners and document_details.owner_id in self._cache_owners:
                owner = self._cache_owners[document_details.owner_id]
            if document_details.tag_ids and self._cache_tags:
                for tag_id in document_details.tag_ids:
                    if tag_id in self._cache_tags:
                        tags.append(self._cache_tags[tag_id])
            if document_details.document_type_id and self._cache_document_types and document_details.document_type_id in self._cache_document_types:
                document_type = self._cache_document_types[document_details.document_type_id]

            enriched_document = DocumentHighDetails(
                **document_details.model_dump(),
                correspondent=correspondent,
                owner=owner,
                tags=tags,
                document_type=document_type
            )
            enriched_documents[document_id] = enriched_document

        self._cache_enriched_documents = enriched_documents

    async def get_documents(self, force: bool = False) -> dict[str, DocumentDetails]:
        """
        Fill the cache with document-related reference data if needed.
        
        Args:
            force (bool): If True, forces a cache refresh even if data is already present.

        Returns:
            dict[str, DocumentDetails]: A dictionary of documents indexed by their ID.

        Raises:
            Exception: If fetching data from the backend fails.
        """
        # if documents exists in cache, skip
        if self._cache_documents is not None and not force:
            return self._cache_documents
        
        #fetch documents via api
        documents = await self.do_fetch_documents()

        # iterate documents and fetch details for each document which is only a DocumentBase object
        detailed_documents: list[DocumentDetails] = []
        for document in documents:
            if not isinstance(document, DocumentDetails):
                detailed_document = await self.do_fetch_document_details(str(document.id))
                detailed_documents.append(detailed_document)
            else:
                detailed_documents.append(document)

        self._cache_documents = {document.id: document for document in detailed_documents}
        return self._cache_documents


    async def get_correspondents(self, force: bool = False) -> dict[str, CorrespondentDetails]:
        """
        Fill the cache with correspondent-related reference data if needed.
        
        Args:
            force (bool): If True, forces a cache refresh even if data is already present.

        Returns:
            dict[str, CorrespondentDetails]: A dictionary of correspondents indexed by their ID.

        Raises:
            Exception: If fetching data from the backend fails.
        """
        # if correspondents exists in cache, skip
        if self._cache_correspondents is not None and not force:
            return self._cache_correspondents
        
        #fetch correspondents via api
        correspondents = await self.do_fetch_correspondents()

        # iterate correspondents and fetch details for each correspondent which is only a CorrespondentBase object
        detailed_correspondents: list[CorrespondentDetails] = []
        for correspondent in correspondents:
            if not isinstance(correspondent, CorrespondentDetails):
                detailed_correspondent = await self.do_fetch_correspondent_details(str(correspondent.id))
                detailed_correspondents.append(detailed_correspondent)
            else:
                detailed_correspondents.append(correspondent)

        self._cache_correspondents = {correspondent.id: correspondent for correspondent in detailed_correspondents}
        return self._cache_correspondents
    
    async def get_owners(self, force: bool = False) -> dict[str, OwnerDetails]:
        """
        Fill the cache with owner-related reference data if needed.
        
        Args:
            force (bool): If True, forces a cache refresh even if data is already present.

        Returns:
            dict[str, OwnerDetails]: A dictionary of owners indexed by their ID.

        Raises:
            Exception: If fetching data from the backend fails.
        """
        # if owners exists in cache, skip
        if self._cache_owners is not None and not force:
            return self._cache_owners
        
        #fetch owners via api
        owners = await self.do_fetch_owners()

        # iterate owners and fetch details for each owner which is only a OwnerBase object
        detailed_owners: list[OwnerDetails] = []
        for owner in owners:
            if not isinstance(owner, OwnerDetails):
                detailed_owner = await self.do_fetch_owner_details(str(owner.id))
                detailed_owners.append(detailed_owner)
            else:
                detailed_owners.append(owner)
        
        self._cache_owners = {owner.id: owner for owner in detailed_owners}
        return self._cache_owners
    
    async def get_tags(self, force: bool = False) -> dict[str, TagDetails]:
        """
        Fill the cache with tag-related reference data if needed.
        
        Args:
            force (bool): If True, forces a cache refresh even if data is already present.

        Returns:
            dict[str, TagDetails]: A dictionary of tags indexed by their ID.

        Raises:
            Exception: If fetching data from the backend fails.
        """
        # if tags exists in cache, skip
        if self._cache_tags is not None and not force:
            return self._cache_tags
        
        #fetch tags via api
        tags = await self.do_fetch_tags()

        # iterate tags and fetch details for each tag which is only a TagBase object
        detailed_tags: list[TagDetails] = []
        for tag in tags:
            if not isinstance(tag, TagDetails):
                detailed_tag = await self.do_fetch_tag_details(str(tag.id))
                detailed_tags.append(detailed_tag)
            else:
                detailed_tags.append(tag)

        self._cache_tags = {tag.id: tag for tag in detailed_tags}
        return self._cache_tags
    
    async def get_document_types(self, force: bool = False) -> dict[str, DocumentTypeDetails]:
        """
        Fill the cache with document type-related reference data if needed.
        
        Args:
            force (bool): If True, forces a cache refresh even if data is already present.

        Returns:
            dict[str, DocumentTypeDetails]: A dictionary of document types indexed by their ID.

        Raises:
            Exception: If fetching data from the backend fails.
        """
        # if document types exists in cache, skip
        if self._cache_document_types is not None and not force:
            return self._cache_document_types
        
        #fetch document types via api
        document_types = await self.do_fetch_document_types()

        # iterate document types and fetch details for each document type which is only a DocumentTypeBase object
        detailed_document_types: list[DocumentTypeDetails] = []
        for doc_type in document_types:
            if not isinstance(doc_type, DocumentTypeDetails):
                detailed_doc_type = await self.do_fetch_document_type_details(str(doc_type.id))
                detailed_document_types.append(detailed_doc_type)
            else:
                detailed_document_types.append(doc_type)

        self._cache_document_types = {doc_type.id: doc_type for doc_type in detailed_document_types}
        return self._cache_document_types