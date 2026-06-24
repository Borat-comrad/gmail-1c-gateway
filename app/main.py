from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.onec_client import fetch_price_history, fetch_price_history_debug_raw
from app.schemas import PriceHistoryRequest


app = FastAPI(title="gmail-1c-gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/v1/price-history")
async def price_history(payload: PriceHistoryRequest) -> dict:
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code must not be empty")

    settings = get_settings()
    return await fetch_price_history(settings=settings, code=code)


# Temporary endpoint for comparing the raw 1C response bytes/text previews.
@app.post("/api/v1/price-history-debug-raw")
async def price_history_debug_raw(payload: PriceHistoryRequest) -> dict:
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code must not be empty")

    settings = get_settings()
    return await fetch_price_history_debug_raw(settings=settings, code=code)
