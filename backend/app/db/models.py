import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OutcomeStatus(str, enum.Enum):
    PENDING = "PENDING"
    WIN = "WIN"
    LOSS = "LOSS"
    INVALID = "INVALID"


class TradeLog(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    signal: Mapped[str] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_status: Mapped[OutcomeStatus] = mapped_column(
        Enum(OutcomeStatus), default=OutcomeStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    lessons: Mapped[list["LessonLog"]] = relationship(
        back_populates="trade", cascade="all, delete-orphan"
    )


class LessonLog(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), index=True)
    post_mortem_reason: Mapped[str] = mapped_column(Text, default="")
    mistake_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    trade: Mapped[TradeLog] = relationship(back_populates="lessons")
