from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.memory_engine import aggregate_stats

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("/stats")
def memory_stats(limit: int = Query(10, ge=1, le=100), db: Session = Depends(get_db)):
    return aggregate_stats(db, recent_lessons=limit)
