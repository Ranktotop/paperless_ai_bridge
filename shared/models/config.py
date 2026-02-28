from pydantic import BaseModel


class EnvConfig(BaseModel):
    """
    Represents a single configuration parameter required for a env setting.

    Attributes:
        env_key (str): The key/name of the environment variable to read.
        val_type (str): The expected type of the environment variable's value. Supported types are "string", "int", "bool", and "list".
        default (str | int | bool | list | None): An optional default value if the environment variable is not set. If None, the variable is required and an error will be raised if it is not set.
    """

    # Core configuration parameters
    # Core identity
    env_key: str
    val_type: str
    default: str | int | bool | list | None = None