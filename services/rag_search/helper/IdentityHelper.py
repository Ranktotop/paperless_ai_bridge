
from server.user_mapping.UserMappingService import UserMappingService
from shared.clients.dms.DMSClientInterface import DMSClientInterface
from dataclasses import dataclass

@dataclass
class IdentityMap:
    """Data class representing the mapping of a frontend user_id to a DMS owner_id for a specific engine."""
    dms_engine: str
    owner_id: str


class IdentityHelper:
    """Helper class for resolving frontend user identities to DMS owner identities across multiple engines."""

    def __init__(self, user_mapping_service: UserMappingService, dms_clients: list[DMSClientInterface], frontend: str, user_id: str):
        self._user_mapping_service = user_mapping_service
        self._dms_clients = dms_clients
        self._frontend = frontend
        self._user_id = user_id
        self._map = self._fetch_identities()

    #################################
    ############ GETTER #############
    #################################

    def get_identities(self) -> list[IdentityMap]:
        """Returns the list of IdentityMap instances representing the resolved identities for this user."""
        return self._map
    
    def has_mappings(self) -> bool:
        """Returns True if at least one mapping was found for this user across all engines."""
        return len(self._map) > 0

    #################################
    ############ READER #############
    #################################

    def _fetch_identities(self) -> list[IdentityMap]:
        """
        Resolves the frontend user_id to DMS owner_ids for every configured engine via UserMappingService.
        Returns a list of IdentityMap instances. Engines for which no mapping exists are excluded.

        Returns:
            List of IdentityMap instances for this user.
        """
        owner_identities: list[IdentityMap] = []
        #iterate all dms clients
        for dms_client in self._dms_clients:
            #get engine name
            engine_name = dms_client.get_engine_name()
            # get the owner_id in the dms which is mapped to the frontend user_id for this dms
            resolved = self._user_mapping_service.resolve(self._frontend, self._user_id, engine_name)
            if resolved is not None:
                owner_identities.append(IdentityMap(dms_engine=engine_name, owner_id=str(resolved)))
        return owner_identities