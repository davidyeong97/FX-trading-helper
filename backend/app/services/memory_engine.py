"""Memory engine: turns past trades/post-mortems into a prompt-enrichment block."""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LessonLog, OutcomeStatus, TradeLog

MAX_LESSONS = 5
_RESOLVED = (OutcomeStatus.WIN, OutcomeStatus.LOSS)


@dataclass
class MemoryContext:
    symbol: str
    timeframe: str
    wins: int = 0
    losses: int = 0
    win_rate: float | None = None
    lessons: list[dict] = field(default_factory=list)
    mistake_counts: dict[str, int] = field(default_factory=dict)
    text: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "mistake_counts": self.mistake_counts,
            "lessons": self.lessons,
        }


def _win_rate(db: Session, symbol: str, timeframe: str) -> tuple[int, int]:
    rows = db.execute(
        select(TradeLog.outcome_status).where(
            TradeLog.symbol == symbol,
            TradeLog.timeframe == timeframe,
            TradeLog.outcome_status.in_(_RESOLVED),
        )
    ).scalars().all()
    wins = sum(1 for r in rows if r == OutcomeStatus.WIN)
    return wins, len(rows) - wins


def _ranked_lessons(db: Session, symbol: str, timeframe: str, limit: int) -> list[tuple[LessonLog, TradeLog]]:
    """Lessons for same symbol (any timeframe) ranked: exact setup first, then recency."""
    rows = db.execute(
        select(LessonLog, TradeLog)
        .join(TradeLog, LessonLog.trade_id == TradeLog.id)
        .where(TradeLog.symbol == symbol)
        .order_by(LessonLog.created_at.desc(), LessonLog.id.desc())
    ).all()
    pairs = [(le, tr) for le, tr in rows]
    # stable sort keeps recency order within each relevance tier
    pairs.sort(key=lambda p: 0 if p[1].timeframe == timeframe else 1)
    return pairs[:limit]


def build_memory_context(db: Session, symbol: str, timeframe: str, limit: int = MAX_LESSONS) -> MemoryContext:
    ctx = MemoryContext(symbol=symbol, timeframe=timeframe)
    ctx.wins, ctx.losses = _win_rate(db, symbol, timeframe)
    total = ctx.wins + ctx.losses
    if total:
        ctx.win_rate = ctx.wins / total

    for lesson, trade in _ranked_lessons(db, symbol, timeframe, limit):
        cat = lesson.mistake_category or "uncategorized"
        ctx.mistake_counts[cat] = ctx.mistake_counts.get(cat, 0) + 1
        ctx.lessons.append(
            {
                "trade_id": trade.id,
                "timeframe": trade.timeframe,
                "signal": trade.signal,
                "outcome": trade.outcome_status.value,
                "mistake_category": cat,
                "reason": lesson.post_mortem_reason,
            }
        )

    ctx.text = _format(ctx)
    return ctx


def _format(ctx: MemoryContext) -> str:
    if ctx.win_rate is None and not ctx.lessons:
        return ""
    lines = [f"TRADER MEMORY for {ctx.symbol} {ctx.timeframe} (learn from past results):"]
    if ctx.win_rate is not None:
        lines.append(
            f"- Win rate on this setup: {ctx.win_rate:.0%} ({ctx.wins}W/{ctx.losses}L)."
        )
        if ctx.win_rate < 0.5:
            lines.append("- Past performance is poor here; lower confidence unless the setup is clearly strong.")
    if ctx.lessons:
        lines.append("- Past mistakes:")
        for l in ctx.lessons:
            reason = (l["reason"] or "no details").strip()
            lines.append(f"  * [{l['mistake_category']}] ({l['timeframe']}, {l['signal']}, {l['outcome']}) {reason}")
    return "\n".join(lines)


def enrich_prompt(system_prompt: str, memory_text: str) -> str:
    """Prepend memory context to the vision system prompt (no-op when empty)."""
    return f"{memory_text}\n\n{system_prompt}" if memory_text else system_prompt


def aggregate_stats(db: Session, recent_lessons: int = 10) -> dict:
    """Win rate overall and grouped by symbol/timeframe, plus most recent lessons."""
    rows = db.execute(
        select(TradeLog.symbol, TradeLog.timeframe, TradeLog.outcome_status).where(
            TradeLog.outcome_status.in_(_RESOLVED)
        )
    ).all()
    groups: dict[tuple[str, str], list[int]] = {}
    for symbol, tf, status in rows:
        g = groups.setdefault((symbol, tf), [0, 0])
        g[0 if status == OutcomeStatus.WIN else 1] += 1

    def _entry(wins: int, losses: int) -> dict:
        total = wins + losses
        return {"wins": wins, "losses": losses, "total": total,
                "win_rate": wins / total if total else None}

    by_group = [
        {"symbol": s, "timeframe": tf, **_entry(w, l)}
        for (s, tf), (w, l) in sorted(groups.items())
    ]
    tw = sum(g[0] for g in groups.values())
    tl = sum(g[1] for g in groups.values())

    lessons = db.execute(
        select(LessonLog, TradeLog)
        .join(TradeLog, LessonLog.trade_id == TradeLog.id)
        .order_by(LessonLog.created_at.desc(), LessonLog.id.desc())
        .limit(recent_lessons)
    ).all()
    return {
        "overall": _entry(tw, tl),
        "by_symbol_timeframe": by_group,
        "recent_lessons": [
            {
                "id": le.id,
                "trade_id": tr.id,
                "symbol": tr.symbol,
                "timeframe": tr.timeframe,
                "outcome": tr.outcome_status.value,
                "mistake_category": le.mistake_category,
                "reason": le.post_mortem_reason,
                "created_at": le.created_at.isoformat(),
            }
            for le, tr in lessons
        ],
    }
