import json
from abc import abstractmethod

from shared.clients.ClientInterface import ClientInterface
from shared.helper.HelperConfig import HelperConfig

# Key namespace constants — use these in all callers, never hardcode key strings
KEY_FILTER_OPTIONS = "filter_options"


class CacheClientInterface(ClientInterface):
    """ABC for all cache backends.

    Subclasses that do not use HTTP (e.g. Redis) must override boot(), close(),
    and do_healthcheck() to manage their own connection lifecycle and health
    probe instead of relying on httpx.AsyncClient.
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        super().__init__(helper_config=helper_config)

    ##########################################
    ################ GETTER ##################
    ##########################################

    def _get_client_type(self) -> str:
        return "cache"

    ##########################################
    ############# REQUESTS ###################
    ##########################################

    @abstractmethod
    async def do_get(self, key: str) -> str | None:
        """Retrieve a cached string value by key.

        Returns:
            The stored value, or None on a cache miss.
        """
        pass

    @abstractmethod
    async def do_set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Store a string value under key.

        Args:
            key: Cache key.
            value: String value to store.
            ttl_seconds: Time-to-live in seconds. None means use the backend
                         default TTL (CACHE_{ENGINE}_DEFAULT_TTL_SECONDS).
        """
        pass

    @abstractmethod
    async def do_delete(self, key: str) -> None:
        """Remove a single key from the cache."""
        pass

    @abstractmethod
    async def do_delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching a glob pattern.

        Example:
            await client.do_delete_pattern("filter_options:*")
        """
        pass

    @abstractmethod
    async def do_exists(self, key: str) -> bool:
        """Return True if the key exists in the cache."""
        pass

    ##########################################
    ############### CORE #####################
    ##########################################

    async def do_get_json(self, key: str) -> dict | list | None:
        """Retrieve and deserialise a JSON-encoded value.

        Returns:
            Parsed dict or list on hit, None on miss or JSON decode error.
        """
        raw = await self.do_get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.logging.warning(
                "CacheClientInterface.do_get_json: JSON decode failed for key '%s'", key
            )
            return None

    async def do_set_json(
        self,
        key: str,
        value: dict | list,
        ttl_seconds: int | None = None,
    ) -> None:
        """Serialise value as JSON and store it under key.

        Args:
            key: Cache key.
            value: Dict or list to serialise and store.
            ttl_seconds: Optional TTL override; see do_set() for semantics.
        """
        await self.do_set(key, json.dumps(value), ttl_seconds=ttl_seconds)
