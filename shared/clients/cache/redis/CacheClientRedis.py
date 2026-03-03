import redis.asyncio as aioredis

from shared.clients.cache.CacheClientInterface import CacheClientInterface
from shared.helper.HelperConfig import HelperConfig
from shared.models.config import EnvConfig
import httpx


class CacheClientRedis(CacheClientInterface):
    """Redis implementation of CacheClientInterface.

    Uses redis.asyncio instead of httpx.AsyncClient — boot() and close()
    manage the Redis connection rather than an HTTP session.
    """

    def __init__(self, helper_config: HelperConfig) -> None:
        super().__init__(helper_config=helper_config)
        self._base_url: str = self.get_config_val("BASE_URL", default=None, val_type="string")
        self._password: str = self.get_config_val("PASSWORD", default="", val_type="string")
        self._db: int = int(self.get_config_val("DB", default=0, val_type="number"))
        self._default_ttl: int = int(
            self.get_config_val("DEFAULT_TTL_SECONDS", default=86400, val_type="number")
        )
        self._redis: aioredis.Redis | None = None

    ##########################################
    ################ GETTER ##################
    ##########################################

    def _get_engine_name(self) -> str:
        return "Redis"

    def _get_required_config(self) -> list[EnvConfig]:
        return [
            EnvConfig(env_key="BASE_URL", val_type="string", default=None),
            EnvConfig(env_key="PASSWORD", val_type="string", default=""),
            EnvConfig(env_key="DB", val_type="number", default=0),
            EnvConfig(env_key="DEFAULT_TTL_SECONDS", val_type="number", default=86400),
        ]

    def _get_auth_header(self) -> dict:
        # Redis does not use HTTP auth headers
        return {}

    def _get_base_url(self) -> str:
        return self._base_url

    def _get_endpoint_healthcheck(self) -> str:
        # Not used — do_healthcheck() is overridden to issue a Redis PING
        return "/"

    ##########################################
    ############# LIFECYCLE ##################
    ##########################################

    async def boot(self) -> None:
        """Establish the Redis connection. Does not create an httpx.AsyncClient."""
        self._redis = aioredis.from_url(
            self._base_url,
            db=self._db,
            decode_responses=True,
            password=self._password or None,
        )

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    ##########################################
    ############# CHECKER ####################
    ##########################################

    # override the HTTP-based do_healthcheck() from ClientInterface because Redis uses a native PING command rather than an HTTP request
    # we check the boolean response from ping() and return a dummy httpx.Response-like object for consistency with the expected return type
    async def do_healthcheck(self) -> httpx.Response:
        """Ping Redis to verify connectivity.

        Overrides the HTTP-based do_healthcheck() from ClientInterface because
        Redis uses a native PING command rather than an HTTP request.

        Returns:
            True if Redis responds to PING.

        Raises:
            Exception: If boot() has not been called.
        """
        self._assert_connected()
        result = await self._redis.ping()  # type: ignore[union-attr]
        response = httpx.Response(status_code=200 if result else 500)
        return response

    ##########################################
    ############# REQUESTS ###################
    ##########################################

    async def do_get(self, key: str) -> str | None:
        """Retrieve a string value by key; returns None on miss."""
        self._assert_connected()
        return await self._redis.get(key)  # type: ignore[union-attr]

    async def do_set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Store a string value under key with an optional TTL.

        Args:
            key: Cache key.
            value: String value to store.
            ttl_seconds: TTL override; None uses self._default_ttl.
                         0 or negative means no expiry.
        """
        self._assert_connected()
        effective_ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        if effective_ttl and effective_ttl > 0:
            await self._redis.setex(key, effective_ttl, value)  # type: ignore[union-attr]
        else:
            await self._redis.set(key, value)  # type: ignore[union-attr]

    async def do_delete(self, key: str) -> None:
        """Remove a single key from Redis."""
        self._assert_connected()
        await self._redis.delete(key)  # type: ignore[union-attr]

    async def do_delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching a glob pattern using SCAN (safe for large keyspaces).

        Args:
            pattern: Glob pattern, e.g. "filter_options:*".
        """
        self._assert_connected()
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await self._redis.scan(  # type: ignore[union-attr]
                cursor=cursor, match=pattern, count=100
            )
            if keys:
                await self._redis.delete(*keys)  # type: ignore[union-attr]
                deleted += len(keys)
            if cursor == 0:
                break
        self.logging.debug(
            "CacheClientRedis.do_delete_pattern: deleted %d key(s) matching '%s'",
            deleted, pattern,
        )

    async def do_exists(self, key: str) -> bool:
        """Return True if the key exists in Redis."""
        self._assert_connected()
        return bool(await self._redis.exists(key))  # type: ignore[union-attr]

    ##########################################
    ############# HELPERS ####################
    ##########################################

    def _assert_connected(self) -> None:
        """Raise if boot() has not been called."""
        if self._redis is None:
            raise Exception("Redis client not initialized. Call boot() first.")
