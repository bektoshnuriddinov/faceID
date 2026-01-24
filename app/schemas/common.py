from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID

class PersonResponse(BaseModel):
    status: Literal["ok", "error"] = Field(
        ...,
        description="Operation result status"
    )
    message: str = Field(
        ...,
        description="Human-readable result message"
    )
    person_id: Optional[UUID] = Field(
        None,
        description="Created person ID (only if status=ok)"
    )