from shared.helper.HelperConfig import HelperConfig
from shared.clients.rag.RAGClientInterface import RAGClientInterface
from shared.models.config import EnvConfig


class RAGClientQdrant(RAGClientInterface):
    def __init__(self, helper_config: HelperConfig):
        super().__init__(helper_config=helper_config)
        self._base_url = self.get_config_val("BASE_URL", default=None, val_type="string")
        self._api_key = self.get_config_val("API_KEY", default="", val_type="string")
        self._collection_name = self.get_config_val("COLLECTION", default=None, val_type="string")

    ##########################################
    ################ GETTER ##################
    ##########################################

    ################ GENERAL ##################
    def _get_engine_name(self) -> str:
        return "Qdrant"

    ################ CONFIG ##################
    def _get_required_config(self) -> list[EnvConfig]:
        return [
            EnvConfig(env_key="BASE_URL", val_type="string", default=None),
            EnvConfig(env_key="API_KEY", val_type="string", default=""),
            EnvConfig(env_key="COLLECTION", val_type="string", default=None)
        ]

    ################ AUTH ##################
    def _get_auth_header(self) -> dict:
        if self._api_key:
            return {"api-key": f"{self._api_key}"}
        else:
            return {}

    ################ ENDPOINTS ##################
    def _get_base_url(self) -> str:
        return self._base_url

    def _get_endpoint_healthcheck(self) -> str:
        return "/healthz"

    def _get_endpoint_scroll(self) -> str:
        return f"/collections/{self._collection_name}/points/scroll"

    def _get_endpoint_points(self) -> str:
        return f"/collections/{self._collection_name}/points"

    def _get_endpoint_delete_points(self) -> str:
        return f"/collections/{self._collection_name}/points/delete"

    def _get_endpoint_check_collection_existence(self) -> str:
        return f"/collections/{self._collection_name}/exists"

    def _get_endpoint_create_collection(self) -> str:
        return f"/collections/{self._collection_name}"

    def _get_endpoint_count(self) -> str:
        return f"/collections/{self._collection_name}/points/count"

    ##########################################
    ########### PAYLOAD BUILDER ##############
    ##########################################

    def get_scroll_payload(self, filters: list[dict], with_payload: bool | list | dict, with_vector: bool | list, limit: int | None = None, offset: str | None = None) -> dict:
        payload = {
            "filter": {"must": filters},
            "limit": limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if offset is not None:
            payload["offset"] = offset
        return payload

    def get_count_payload(self, filters: list[dict]) -> dict:
        return {"filter": {"must": filters}, "exact": True}

    def get_delete_payload(self, filter: dict) -> dict:
        return {"filter": filter}

    ##########################################
    ########### RESPONSE PARSER ##############
    ##########################################

    def extract_scroll_content(self, raw_response: dict) -> dict:
        result = raw_response.get("result", {})
        return {
            "result": result.get("points", []),
            "status": raw_response.get("status", "ok"),
            "time": raw_response.get("time", 0),
        }

    def extract_next_page_offset(self, raw_response: dict) -> str | None:
        return raw_response.get("result", {}).get("next_page_offset")
