from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import RawRecordList, RawRecordOut
from app.models.raw_record import RawRecord, SourceType

router = APIRouter(prefix="/records", tags=["records"])


@router.get("", response_model=RawRecordList)
def list_records(
    db: Session = Depends(get_db),
    source: Optional[SourceType] = Query(
        default=None, description="Filter by source, e.g. REDDIT"
    ),
    is_processed: Optional[str] = Query(
        default=None, description="Filter by processing status, e.g. 'pending'"
    ),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    List raw records with basic filtering and pagination.
    Ordered newest-first by ingested_at.
    """
    stmt = select(RawRecord)
    count_stmt = select(func.count()).select_from(RawRecord)

    if source is not None:
        stmt = stmt.where(RawRecord.source == source)
        count_stmt = count_stmt.where(RawRecord.source == source)

    if is_processed is not None:
        stmt = stmt.where(RawRecord.is_processed == is_processed)
        count_stmt = count_stmt.where(RawRecord.is_processed == is_processed)

    total = db.scalar(count_stmt)

    stmt = stmt.order_by(RawRecord.ingested_at.desc()).limit(limit).offset(offset)
    items = db.scalars(stmt).all()

    return RawRecordList(total=total, limit=limit, offset=offset, items=items)


@router.get("/{record_id}", response_model=RawRecordOut)
def get_record(record_id: UUID, db: Session = Depends(get_db)):
    """Fetch a single raw record by its UUID."""
    record = db.get(RawRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record