from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import LessonLog, OutcomeStatus, TradeLog

router = APIRouter(prefix="/api/v1/trades", tags=["trades"])


class TradeCreate(BaseModel):
    symbol: str
    timeframe: str
    signal: str
    confidence: float = 0.0
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    rr: float | None = None


class OutcomeUpdate(BaseModel):
    outcome_status: OutcomeStatus
    post_mortem_reason: str | None = None
    mistake_category: str | None = Field(default=None, max_length=64)


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    timeframe: str
    signal: str
    confidence: float
    entry: float | None
    sl: float | None
    tp: float | None
    rr: float | None
    outcome_status: OutcomeStatus
    created_at: datetime


@router.post("", response_model=TradeOut, status_code=201)
def create_trade(body: TradeCreate, db: Session = Depends(get_db)):
    trade = TradeLog(**body.model_dump())
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@router.get("", response_model=list[TradeOut])
def list_trades(
    symbol: str | None = None,
    timeframe: str | None = None,
    outcome_status: OutcomeStatus | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = select(TradeLog).order_by(TradeLog.created_at.desc(), TradeLog.id.desc())
    if symbol:
        q = q.where(TradeLog.symbol == symbol)
    if timeframe:
        q = q.where(TradeLog.timeframe == timeframe)
    if outcome_status:
        q = q.where(TradeLog.outcome_status == outcome_status)
    return db.execute(q.limit(limit)).scalars().all()


@router.patch("/{trade_id}/outcome", response_model=TradeOut)
@router.post("/{trade_id}/outcome", response_model=TradeOut, include_in_schema=False)
def set_outcome(trade_id: int, body: OutcomeUpdate, db: Session = Depends(get_db)):
    trade = db.get(TradeLog, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    trade.outcome_status = body.outcome_status
    if body.post_mortem_reason or body.mistake_category:
        db.add(
            LessonLog(
                trade_id=trade.id,
                post_mortem_reason=body.post_mortem_reason or "",
                mistake_category=body.mistake_category,
            )
        )
    db.commit()
    db.refresh(trade)
    return trade
