"""POST /api/v1/analyze: memory -> vision -> search -> merged response + PENDING trade row."""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import OutcomeStatus, TradeLog
from app.services import memory_engine, search_service, vision_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    image_base64: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(min_length=1, max_length=16)


class TradeDetails(BaseModel):
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    rr: Optional[float] = None


class AnalyzeResponse(BaseModel):
    trade_id: int
    symbol: str
    timeframe: str
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    rr: Optional[float] = None
    trade: TradeDetails
    rationale: str = ""
    structure: dict = Field(default_factory=dict)
    sentiment: dict
    memory_insights: dict
    status: str = OutcomeStatus.PENDING.value


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    memory = memory_engine.build_memory_context(db, req.symbol, req.timeframe)

    try:
        vision = vision_service.analyze_chart(
            req.image_base64, req.symbol, req.timeframe, extra_context=memory.text
        )
    except vision_service.VisionConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except vision_service.VisionAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except vision_service.VisionValidationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except vision_service.VisionServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    confidence, adjustment = memory_engine.adjust_confidence(
        db, req.symbol, req.timeframe, vision["signal"], float(vision["confidence"])
    )

    sentiment = search_service.get_sentiment(req.symbol)
    sentiment_dict = sentiment.model_dump() if hasattr(sentiment, "model_dump") else dict(sentiment)

    trade = TradeLog(
        symbol=req.symbol,
        timeframe=req.timeframe,
        signal=vision["signal"],
        confidence=confidence,
        entry=vision.get("entry"),
        sl=vision.get("stop_loss"),
        tp=vision.get("take_profit"),
        rr=vision.get("rr"),
        outcome_status=OutcomeStatus.PENDING,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return AnalyzeResponse(
        trade_id=trade.id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        signal=vision["signal"],
        confidence=trade.confidence,
        entry=trade.entry,
        sl=trade.sl,
        tp=trade.tp,
        rr=trade.rr,
        trade=TradeDetails(entry=trade.entry, sl=trade.sl, tp=trade.tp, rr=trade.rr),
        rationale=vision.get("rationale", ""),
        structure=vision.get("structure", {}),
        sentiment=sentiment_dict,
        memory_insights={**memory.to_dict(), "confidence_adjustment": adjustment},
    )
