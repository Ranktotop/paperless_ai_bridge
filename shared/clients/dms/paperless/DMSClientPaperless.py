from shared.clients.dms.DMSClientInterface import DMSClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig
from shared.clients.dms.models.Document import DocumentsListResponse, DocumentDetails
from shared.clients.dms.models.Correspondent import CorrespondentsListResponse, CorrespondentDetails
from shared.clients.dms.models.Tag import TagsListResponse, TagDetails
from shared.clients.dms.models.Owner import OwnersListResponse, OwnerDetails
from shared.clients.dms.models.DocumentType import DocumentTypesListResponse, DocumentTypeDetails
from datetime import datetime
from urllib.parse import urlparse, parse_qs


class DMSClientPaperless(DMSClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)
        self._base_url = self.get_config_val("BASE_URL", default=None, val_type="string")
        self._api_key = self.get_config_val("API_KEY", default="", val_type="string")

    ##########################################
    ################ GETTER ##################
    ##########################################

    ################ GENERAL ##################
    def _get_engine_name(self) -> str:
        return "Paperless"
    
    ################ CONFIG ##################
    def _get_required_config(self) -> list[EnvConfig]:
        return [
            EnvConfig(env_key="BASE_URL", val_type="string", default=None),
            EnvConfig(env_key="API_KEY", val_type="string", default="")
        ]
    
    ################ AUTH ##################
    def _get_auth_header(self) -> dict:
        if self._api_key:
            return {"Authorization": f"Token {self._api_key}"}
        else:
            return {}
    
    ################ ENDPOINTS ##################    
    def _get_base_url(self) -> str:
        return self._base_url
    
    def _get_endpoint_healthcheck(self) -> str:
        return "/api/documents/"
    
    def _get_endpoint_documents(self, page:int = 1, page_size:int=100) -> str:
        plain_url = f"/api/documents/"
        separator = "?"
        if page:
            plain_url += f"{separator}page={page}"
            separator = "&"
        if page_size:
            plain_url += f"{separator}page_size={page_size}"
        return plain_url
    
    def _get_endpoint_correspondents(self, page:int = 1, page_size:int=100) -> str:
        plain_url = f"/api/correspondents/"
        separator = "?"
        if page:
            plain_url += f"{separator}page={page}"
            separator = "&"
        if page_size:
            plain_url += f"{separator}page_size={page_size}"
        return plain_url

    def _get_endpoint_tags(self, page:int = 1, page_size:int=100) -> str:
        plain_url = f"/api/tags/"
        separator = "?"
        if page:
            plain_url += f"{separator}page={page}"
            separator = "&"
        if page_size:
            plain_url += f"{separator}page_size={page_size}"
        return plain_url
    
    def _get_endpoint_owners(self, page:int = 1, page_size:int=100) -> str:
        plain_url = f"/api/users/"
        separator = "?"
        if page:
            plain_url += f"{separator}page={page}"
            separator = "&"
        if page_size:
            plain_url += f"{separator}page_size={page_size}"
        return plain_url
    
    def _get_endpoint_document_types(self, page:int = 1, page_size:int=100) -> str:
        plain_url = f"/api/document_types/"
        separator = "?"
        if page:
            plain_url += f"{separator}page={page}"
            separator = "&"
        if page_size:
            plain_url += f"{separator}page_size={page_size}"
        return plain_url
    
    def _get_endpoint_document_details(self, document_id: str) -> str:
        return f"/api/documents/{document_id}/"
    
    def _get_endpoint_correspondent_details(self, correspondent_id: str) -> str:
        return f"/api/correspondents/{correspondent_id}/"
    
    def _get_endpoint_tag_details(self, tag_id: str) -> str:
        return f"/api/tags/{tag_id}/"
    
    def _get_endpoint_owner_details(self, owner_id: str) -> str:
        return f"/api/users/{owner_id}/"
    
    def _get_endpoint_document_type_details(self, document_type_id: str) -> str:
        return f"/api/document_types/{document_type_id}/"
    
    
    ##########################################
    ########### RESPONSE PARSER ##############
    ##########################################

    ############### LIST RESPONSES ###############
    def _parse_endpoint_documents(self, response: dict, requested_page_size:int|None = None) -> DocumentsListResponse:
        meta = self._parse_listing_meta(response)
        
        # since paperless sends details in the list, we can parse them directly into DocumentDetails objects
        docs = []
        for item in response.get("results", []):
            doc = self._parse_endpoint_document(item)
            docs.append(doc)

        # return answer
        pageLen = len(docs) if not requested_page_size else requested_page_size
        return DocumentsListResponse(
            engine=self._get_engine_name(),
            documents=docs,
            currentPage=meta["current_page"],
            nextPage=meta["next_page"],
            previousPage=meta["previous_page"],
            overallCount=meta["overall_results_count"],
            pageLength=pageLen,
            lastPage= meta["overall_results_count"] // pageLen + (1 if meta["overall_results_count"] % pageLen > 0 else 0) if meta["overall_results_count"] and pageLen else None
        )
    
    def _parse_endpoint_correspondents(self, response: dict, requested_page_size:int|None = None) -> CorrespondentsListResponse:
        meta = self._parse_listing_meta(response)
        
        # since paperless sends details in the list, we can parse them directly into CorrespondentDetails objects
        correspondents = []
        for item in response.get("results", []):
            correspondent = self._parse_endpoint_correspondent(item)
            correspondents.append(correspondent)

        # return answer
        pageLen = len(correspondents) if not requested_page_size else requested_page_size
        return CorrespondentsListResponse(
            engine=self._get_engine_name(),
            correspondents=correspondents,
            currentPage=meta["current_page"],
            nextPage=meta["next_page"],
            previousPage=meta["previous_page"],
            overallCount=meta["overall_results_count"],
            pageLength=pageLen,
            lastPage= meta["overall_results_count"] // pageLen + (1 if meta["overall_results_count"] % pageLen > 0 else 0) if meta["overall_results_count"] and pageLen else None
        )
    
    def _parse_endpoint_owners(self, response: dict, requested_page_size:int|None = None) -> OwnersListResponse:
        meta = self._parse_listing_meta(response)
        
        # since paperless sends details in the list, we can parse them directly into OwnerDetails objects
        owners = []
        for item in response.get("results", []):
            owner = self._parse_endpoint_owner(item)
            owners.append(owner)

        # return answer
        pageLen = len(owners) if not requested_page_size else requested_page_size
        return OwnersListResponse(
            engine=self._get_engine_name(),
            owners=owners,
            currentPage=meta["current_page"],
            nextPage=meta["next_page"],
            previousPage=meta["previous_page"],
            overallCount=meta["overall_results_count"],
            pageLength=pageLen,
            lastPage= meta["overall_results_count"] // pageLen + (1 if meta["overall_results_count"] % pageLen > 0 else 0) if meta["overall_results_count"] and pageLen else None
        )
        
    
    def _parse_endpoint_tags(self, response: dict, requested_page_size:int|None = None) -> TagsListResponse:
        meta = self._parse_listing_meta(response)
        
        # since paperless sends details in the list, we can parse them directly into TagDetails objects
        tags = []
        for item in response.get("results", []):
            tag = self._parse_endpoint_tag(item)
            tags.append(tag)

        # return answer
        pageLen = len(tags) if not requested_page_size else requested_page_size
        return TagsListResponse(
            engine=self._get_engine_name(),
            tags=tags,
            currentPage=meta["current_page"],
            nextPage=meta["next_page"],
            previousPage=meta["previous_page"],
            overallCount=meta["overall_results_count"],
            pageLength=pageLen,
            lastPage= meta["overall_results_count"] // pageLen + (1 if meta["overall_results_count"] % pageLen > 0 else 0) if meta["overall_results_count"] and pageLen else None
        )
    
    def _parse_endpoint_document_types(self, response: dict, requested_page_size:int|None = None) -> DocumentTypesListResponse:
        meta = self._parse_listing_meta(response)
        
        # since paperless sends details in the list, we can parse them directly into DocumentTypeDetails objects
        types = []
        for item in response.get("results", []):
            doc_type = self._parse_endpoint_document_type(item)
            types.append(doc_type)

        # return answer
        pageLen = len(types) if not requested_page_size else requested_page_size
        return DocumentTypesListResponse(
            engine=self._get_engine_name(),
            types=types,
            currentPage=meta["current_page"],
            nextPage=meta["next_page"],
            previousPage=meta["previous_page"],
            overallCount=meta["overall_results_count"],
            pageLength=pageLen,
            lastPage= meta["overall_results_count"] // pageLen + (1 if meta["overall_results_count"] % pageLen > 0 else 0) if meta["overall_results_count"] and pageLen else None
        )
    
    def _parse_listing_meta(self, listing_response:dict) -> dict:
        """
        Parse the metadata from a listing response, including pagination details.

        Args:
            listing_response (dict): The raw response from the DMS listing endpoint.

        Returns:
            dict: A dictionary containing pagination metadata such as current_page, next_page, previous_page, and overall_results_count.
        """
        next_url = listing_response.get("next")
        overall_results_count = listing_response.get("count")
        next_page: int | None = None
        if next_url:
            params = parse_qs(urlparse(next_url).query)
            page_values = params.get("page", [])
            if page_values and page_values[0].isdigit():
                next_page = int(page_values[0])
        current_page = next_page - 1 if next_page else 1
        previous_page = current_page - 1 if current_page > 1 else None

        return {
            "current_page": current_page,
            "next_page": next_page,
            "previous_page": previous_page,
            "overall_results_count": overall_results_count
        }
        
    
    ############### GET RESPONSES ###############
    def _parse_endpoint_document(self, response: dict) -> DocumentDetails:
        return DocumentDetails(
                #base
                engine=self._get_engine_name(),
                id=response.get("id"),

                #details
                correspondent_id=response.get("correspondent"),
                document_type_id=response.get("document_type"),
                title=response.get("title"),
                content=response.get("content"),
                tag_ids=response.get("tags", []),
                created_date=datetime.fromisoformat(response.get("created_date")) if response.get("created_date") else None,                
                owner_id=response.get("owner"),
                mime_type=response.get("mime_type"),
                file_name=response.get("original_file_name")
            )
    
    def _parse_endpoint_correspondent(self, response: dict) -> CorrespondentDetails:
        return CorrespondentDetails(
                #base
                engine=self._get_engine_name(),
                id=response.get("id"),

                #details
                name=response.get("name"),
                slug=response.get("slug"),               
                owner_id=response.get("owner"),
                documents=response.get("documents_count")
            )
    
    def _parse_endpoint_owner(self, response: dict) -> OwnerDetails:
        return OwnerDetails(
                #base
                engine=self._get_engine_name(),
                id=response.get("id"),

                #details
                username=response.get("username"),
                email=response.get("email"),
                firstname=response.get("first_name"),
                lastname=response.get("last_name")
            )
    
    def _parse_endpoint_tag(self, response: dict) -> TagDetails:
        return TagDetails(
                #base
                engine=self._get_engine_name(),
                id=response.get("id"),

                #details
                name=response.get("name"),
                slug=response.get("slug"),               
                owner_id=response.get("owner"),
                documents=response.get("documents_count")
            )
    
    def _parse_endpoint_document_type(self, response: dict) -> DocumentTypeDetails:
        return DocumentTypeDetails(
                #base
                engine=self._get_engine_name(),
                id=response.get("id"),

                #details
                name=response.get("name"),
                slug=response.get("slug"),               
                owner_id=response.get("owner"),
                documents=response.get("documents_count")
            )