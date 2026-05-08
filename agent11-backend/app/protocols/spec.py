from __future__ import annotations

from pydantic import BaseModel, Field


class ProtocolFieldSpec(BaseModel):
    name: str
    offset: int = Field(ge=0, description="Byte offset from start")
    length: int = Field(ge=1, description="Number of bytes")
    type: str = Field(description="uint|int|hex|ascii")
    endian: str = Field(default="big", description="big|little")
    scale: float = 1.0
    unit: str | None = None


class ProtocolSpec(BaseModel):
    protocol_id: str
    version: str = "1.0.0"
    description: str | None = None
    fields: list[ProtocolFieldSpec]

