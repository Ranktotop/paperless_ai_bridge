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
        return val.strip() if val is not None else default

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
    
    def get_list_val(self, key: str, default: list[str] | None = None, separator: str = ",", element_type: type = str) -> list[str]:
        """Read a list environment variable, splitting by a separator.

        Args:
            key (str): Environment variable name (case-insensitive).
            default (list[str] | None): Fallback value if the variable is not set.
            separator (str): The delimiter to split the string into a list.
            element_type (type): The type to which each element should be cast.

        Returns:
            list: The resolved list of elements.

        Raises:
            ValueError: If the variable is not set and no default is provided.
        """        
        # Read raw value
        raw_val = self.get_string_val(key=key, default=None)
        if raw_val is None:
            if default is None:
                raise ValueError(f"Environment variable '{key}' is not set.")
            return default
        # make sure string is set in the following syntax: "[elem1,elem2,...]"
        if not raw_val.startswith("[") or not raw_val.endswith("]"):
            raise ValueError(f"Environment variable '{key}' must be in the format '[elem1{separator}elem2{separator}...]'. Got: '{raw_val}'")
        # remove surrounding brackets and split by separator and remove empty/whitespace-only elements
        raw_val = raw_val[1:-1] 
        elements = [v.strip() for v in raw_val.split(separator) if v.strip()]
        #if empty list, return empty list
        if not elements:
            return []

        # Try to cast each element to the specified type. Raise error if impossible to cast.
        try:
            return [element_type(elem) for elem in elements]
        except ValueError as e:
            raise ValueError(f"Environment variable '{key}' contains invalid elements: {e}. Expected format: '[elem1{separator}elem2{separator}...]'. Type set to {element_type.__name__}. Got: '{raw_val}'")

    def get_logger(self) -> logging.Logger:
        """Return the application logger.

        Returns:
            logging.Logger: The configured logger instance.
        """
        return self._logger
