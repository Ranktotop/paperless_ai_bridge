"""User identity mapping between AI frontends and DMS backends.

Loads config/user_mapping.yml once at startup and resolves external
frontend user IDs to DMS-internal owner IDs (and vice versa).
"""

import os

import yaml

from server.user_mapping.models import UserMapping


class UserMappingService:
    """Resolves AI frontend user IDs to DMS owner IDs.

    Loaded once at startup from the file at USER_MAPPING_FILE
    (default: config/user_mapping.yml) and stored in app.state.

    The YAML schema is:
        users:
          "<frontend>":        # e.g. "openwebui", "anythingllm"
            "<user_id>":       # frontend user ID as string
              <engine>: <int>  # DMS engine name: owner_id
    """

    def __init__(self, mapping_file: str | None = None) -> None:
        path = mapping_file or os.getenv("USER_MAPPING_FILE", "config/user_mapping.yml")
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        self._mapping = UserMapping.model_validate(raw)

    ##########################################
    ############### CORE #####################
    ##########################################

    def resolve(self, frontend: str, user_id: str, engine: str) -> int | None:
        """Return the DMS owner_id for a given frontend user.

        Args:
            frontend: AI system identifier (e.g. "openwebui", "anythingllm").
            user_id:  Frontend-internal user ID as string.
            engine:   DMS engine name (e.g. "paperless").

        Returns:
            DMS owner_id (int) if a mapping exists, None otherwise.
        """
        frontend_map = self._mapping.users.get(frontend)
        if frontend_map is None:
            return None
        user_map = frontend_map.get(user_id)
        if user_map is None:
            return None
        return user_map.get(engine)

    def reverse_resolve(self, owner_id: int, engine: str) -> list[tuple[str, str]]:
        """Return all (frontend, user_id) pairs that map to the given owner.

        Used by SyncService for webhook cache invalidation — when a document's
        owner changes, all frontend caches for that owner must be flushed.

        Args:
            owner_id: DMS-internal owner ID.
            engine:   DMS engine name (e.g. "paperless").

        Returns:
            List of (frontend, user_id) tuples. Empty list if no match.
        """
        results: list[tuple[str, str]] = []
        for frontend, user_map in self._mapping.users.items():
            for user_id, engine_map in user_map.items():
                if engine_map.get(engine) == owner_id:
                    results.append((frontend, user_id))
        return results
