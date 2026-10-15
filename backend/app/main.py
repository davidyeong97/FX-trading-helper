from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze as analyze_api
from app.config import settings
from app.db.database import init_db

app = FastAPI(title="FX Trading Helper")
init_db()

origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Allow Chrome extension origins (chrome-extension://<id>) and localhost.
    allow_origin_regex=r"^(chrome-extension://.*|https?://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


from app.api import memory as memory_api  # noqa: E402
from app.api import trades as trades_api  # noqa: E402

app.include_router(analyze_api.router)
app.include_router(trades_api.router)
app.include_router(memory_api.router)
