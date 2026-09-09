from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.raw_record import SourceType


class RawRecordOut(BaseModel):
    """Shape of a single RawRecord as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: SourceType
    source_id: str
    raw_text: str
    source_created_at: Optional[datetime]
    ingested_at: datetime
    is_processed: str


class RawRecordList(BaseModel):
    """Paginated list response for /records."""

    total: int
    limit: int
    offset: int
    items: list[RawRecordOut]