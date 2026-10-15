from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="FX Trading Helper")

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


# TODO: register analyze router (app.api.analyze) at /api/v1/analyze
# TODO: register trades router (app.api.trades) at /api/v1/trades
# TODO: register memory router (app.api.memory) at /api/v1/memory
