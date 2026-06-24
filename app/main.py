import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.onec_client import (
    fetch_onec_response,
    fetch_price_history_debug_raw,
    onec_error_message,
)
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
async def price_history(payload: PriceHistoryRequest) -> Response | dict:
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code must not be empty")

    settings = get_settings()
    try:
        response = await fetch_onec_response(settings=settings, code=code)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": "Таймаут при обращении к сервису 1С",
            "raw": None,
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": f"Ошибка подключения к сервису 1С: {exc.__class__.__name__}",
            "raw": None,
        }

    if response.status_code == 200:
        return Response(
            content=response.content,
            media_type="application/json; charset=utf-8",
            status_code=200,
        )

    return {
        "ok": False,
        "code": code,
        "source_status": response.status_code,
        "error": onec_error_message(response.status_code),
        "raw": response.content.decode("utf-8", errors="replace"),
    }


# Temporary endpoint for comparing the raw 1C response bytes/text previews.
@app.post("/api/v1/price-history-debug-raw")
async def price_history_debug_raw(payload: PriceHistoryRequest) -> dict:
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code must not be empty")

    settings = get_settings()
    return await fetch_price_history_debug_raw(settings=settings, code=code)
