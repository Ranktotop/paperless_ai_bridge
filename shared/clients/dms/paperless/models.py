"""Internal Pydantic models for Paperless-ngx API responses.

These models are only used inside DMSClientPaperless to parse raw JSON
responses from the Paperless-ngx REST API.  They are never imported by the
rest of the application — all external-facing types use DMSDocument.
"""

from pydantic import BaseModel


class _CorrespondentResponse(BaseModel):
    id: int
    name: str


class _DocumentTypeResponse(BaseModel):
    id: int
    name: str


class _TagResponse(BaseModel):
    id: int
    name: str
    is_inbox_tag: bool = False


class _OwnerResponse(BaseModel):
    id: int
    username: str
    first_name: str = ""
    last_name: str = ""
