"""Central configuration helper for the paperless AI bridge."""

import logging
import os


class HelperConfig:
    """Central configuration helper. Reads all settings from environment variables."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def get_string_val(self, key: str, default: str | None = None) -> str:
        """Read a string environment variable.

        Args:
            key (str): Environment variable name (case-insensitive).
            default (str | None): Fallback value if the variable is not set.

        Returns:
            str: The resolved value.

        Raises:
            ValueError: If the variable is not set and no default is provided.
        """
        key = key.upper()
        val = os.getenv(key) or None  # empty string → None
        if val is None and default is None:
            raise ValueError(f"Environment variable '{key}' is not set.")
        return val if val is not None else default

    def get_number_val(self, key: str, default: float | int | None = None) -> float | int:
        """Read a numeric environment variable.

        Args:
            key (str): Environment variable name (case-insensitive).
            default (float | int | None): Fallback value if the variable is not set.

        Returns:
            float | int: The resolved numeric value.

        Raises:
            ValueError: If the variable is not set and no default is provided.
            ValueError: If the value cannot be parsed as a number.
        """
        key = key.upper()
        raw = os.getenv(key) or None
        if raw is None:
            if default is None:
                raise ValueError(f"Environment variable '{key}' is not set.")
            return default
        try:
            return int(raw) if "." not in raw else float(raw)
        except ValueError:
            raise ValueError(f"Environment variable '{key}' is not a valid number: '{raw}'.")

    def get_bool_val(self, key: str, default: bool | None = None) -> bool:
        """Read a boolean environment variable.

        Args:
            key (str): Environment variable name (case-insensitive).
            default (bool | None): Fallback value if the variable is not set.

        Returns:
            bool: The resolved boolean value.

        Raises:
            ValueError: If the variable is not set and no default is provided.
        """
        key = key.upper()
        raw = os.getenv(key) or None
        if raw is None:
            if default is None:
                raise ValueError(f"Environment variable '{key}' is not set.")
            return default
        return raw.lower() in ("true", "1", "yes")

    def get_logger(self) -> logging.Logger:
        """Return the application logger.

        Returns:
            logging.Logger: The configured logger instance.
        """
        return self._logger
