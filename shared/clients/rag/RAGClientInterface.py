from abc import abstractmethod
from typing import Any

import httpx
from shared.clients.rag.models.Scroll import ScrollResult
from shared.clients.ClientInterface import ClientInterface
import json

from shared.helper.HelperConfig import HelperConfig


class RAGClientInterface(ClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)

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
        return "rag"

    ################ ENDPOINTS ##################
    @abstractmethod
    def _get_endpoint_scroll(self) -> str:
        """
        Returns the endpoint path for scroll requests.

        Returns:
            str: The endpoint path for scroll requests (e.g. "/scroll")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_points(self) -> str:
        """
        Returns the endpoint path for points upsert requests.

        Returns:
            str: The endpoint path for points requests (e.g. "/points")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_delete_points(self) -> str:
        """
        Returns the endpoint path for deleting points by filter.

        Returns:
            str: The endpoint path (e.g. "/collections/my_col/points/delete")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_check_collection_existence(self) -> str:
        """
        Returns the endpoint path for collection existence check requests.

        Returns:
            str: The endpoint path for collection existence check requests (e.g. "/existence_check")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def _get_endpoint_create_collection(self) -> str:
        """
        Returns the endpoint path for create collection requests.

        Returns:
            str: The endpoint path for create collection requests (e.g. "/create_collection")

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def get_scroll_payload(self, filters: list[dict], with_payload: bool | list | dict, with_vector: bool | list, limit: int | None = None) -> dict:
        """
        Returns the payload template for scroll requests to the RAG backend.

        Args:
            filters (list[dict]): The filters to apply to the scroll request.
            with_payload (bool | list | dict): Whether to include the payload in the scroll request, or which payload fields to include.
            with_vector (bool | list): Whether to include the vector in the scroll request, or which vector fields to include.
            limit (int | None): The maximum number of results to return.

        Returns:
            dict: The payload for the scroll request.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def get_delete_payload(self, filter: dict) -> dict:
        """
        Builds the backend-specific request payload for a filter-based delete.

        Args:
            filter (dict): The filter that identifies which points to delete.

        Returns:
            dict: The payload for the delete request.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def extract_scroll_content(self, raw_response: dict) -> dict:
        """
        Extracts the relevant content from a raw scroll response.

        Args:
            raw_response (dict): The raw JSON response from the scroll endpoint.

        Returns:
            dict: A dict with keys "result", "status", "time".

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    ##########################################
    ############### REQUESTS #################
    ##########################################

    async def do_existence_check(self) -> bool:
        """Check if a collection exists in the rag backend.

        Returns:
            bool: True if the collection exists, False otherwise.
        """
        resp = await self.do_request(method="GET", endpoint=self._get_endpoint_check_collection_existence())
        return resp.json().get("result", {}).get("exists")

    async def do_create_collection(self, vector_size: int = 768, distance: str = "Cosine") -> httpx.Response:
        """Create a collection in the rag backend.

        Args:
            vector_size (int): The size of the vectors in the collection.
            distance (str): The distance metric for the vectors.

        Returns:
            httpx.Response: The response from the create collection request.
        """
        return await self.do_request(
            method="PUT",
            json={
                "vectors": {
                    "size": vector_size,
                    "distance": distance}},
            endpoint=self._get_endpoint_create_collection())

    async def do_upsert_points(self, points: list[dict[str, Any]]) -> httpx.Response:
        """Upsert points into the rag backend collection.
        Inserts new points or replaces existing ones if a point with the same ID already exists.

        Args:
            points (list[dict[str, Any]]): The list of points to upsert.

        Returns:
            httpx.Response: The response from the upsert request.
        """
        return await self.do_request(
            method="PUT",
            content=json.dumps({"points": points}),
            endpoint=self._get_endpoint_points(),
            additional_headers={"Content-Type": "application/json"})

    async def do_delete_points_by_filter(self, filter: dict) -> None:
        """Deletes all points matching the given filter from the RAG backend.
        Used when a DMS document is updated (delete old chunks) or deleted entirely.

        Args:
            filter (dict): The filter that identifies which points to delete.
                           Must always include owner_id to enforce access isolation.
        """
        await self.do_request(
            method="POST",
            content=json.dumps(self.get_delete_payload(filter)),
            endpoint=self._get_endpoint_delete_points(),
            additional_headers={"Content-Type": "application/json"},
            raise_on_error=True,
        )

    async def do_scroll(self, filters: dict, with_payload: bool | list | dict, with_vector: bool | list, limit: int | None = None) -> ScrollResult:
        """Scroll through a collection in the rag backend.

        Args:
            filters (dict): The filters to apply to the scroll request.
            with_payload (bool | list | dict): Whether to include the payload in the scroll request, or which payload fields to include.
            with_vector (bool | list): Whether to include the vector in the scroll request.
            limit (int | None): The maximum number of results to return.

        Returns:
            ScrollResult: The result from the scroll request.
        """
        resp = await self.do_request(
            method="POST",
            content=json.dumps(self.get_scroll_payload(filters, with_payload, with_vector, limit)),
            endpoint=self._get_endpoint_scroll(),
            additional_headers={"Content-Type": "application/json"},
            raise_on_error=True
            )
        scroll_content = self.extract_scroll_content(raw_response=resp.json())
        return ScrollResult(
                result=scroll_content.get("result", []),
                status=scroll_content.get("status", "ok"),
                time=scroll_content.get("time", 0),
            )
