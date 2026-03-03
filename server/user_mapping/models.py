from pydantic import BaseModel


class UserMapping(BaseModel):
    """Parsed and validated representation of config/user_mapping.yml.

    Structure mirrors the YAML schema:
        users:
          "<frontend>":
            "<user_id>":
              <engine>: <owner_id>
    """

    users: dict[str, dict[str, dict[str, int]]]
