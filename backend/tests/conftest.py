import os

os.environ.setdefault("DB_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.services import search_service, vision_service


@pytest.fixture()
def db_session():
    from app.db import models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class VisionStub:
    def __init__(self):
        self.calls = []
        self.result = {
            "signal": "BUY", "confidence": 80.0, "entry": 1.1000, "stop_loss": 1.0950,
            "take_profit": 1.1100, "rr": 2.0, "rationale": "stub", "structure": {}, "provider": "gemini",
        }

    def __call__(self, image_base64, symbol, timeframe, extra_context=""):
        self.calls.append({"symbol": symbol, "timeframe": timeframe, "extra_context": extra_context})
        return dict(self.result)


@pytest.fixture()
def vision(monkeypatch):
    stub = VisionStub()
    monkeypatch.setattr(vision_service, "analyze_chart", stub)
    return stub


@pytest.fixture()
def search(monkeypatch):
    summary = search_service.SentimentSummary(
        symbol="EURUSD", sentiment="neutral", summary="calm", available=True
    )
    monkeypatch.setattr(search_service, "get_sentiment", lambda symbol, timeout=None: summary)
    return summary
