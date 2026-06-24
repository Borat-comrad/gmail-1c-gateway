import base64
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


def make_basic_auth_header(login: str, password: str) -> str:
    raw = f"{login}:{password}"
    raw_bytes = raw.encode("utf-8")
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"Basic {encoded}"


def build_onec_url(settings: Settings, code: str) -> str:
    safe_code = quote(code, safe="")
    return f"{settings.onec_base_url}/{safe_code}"


def build_onec_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": make_basic_auth_header(
            settings.onec_login,
            settings.onec_password,
        ),
        "Accept": "application/json, text/plain, */*",
    }


def onec_error_message(status_code: int) -> str:
    messages = {
        401: "Неверный логин или пароль 1С",
        403: "Нет прав для доступа к данным 1С",
        404: "Код не найден или путь к сервису 1С неверный",
        500: "Ошибка сервера 1С",
    }
    return messages.get(status_code, f"Сервис 1С вернул ошибку {status_code}")


async def fetch_onec_response(settings: Settings, code: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        return await client.get(
            build_onec_url(settings, code),
            headers=build_onec_headers(settings),
        )


async def fetch_price_history_debug_raw(settings: Settings, code: str) -> dict[str, Any]:
    try:
        response = await fetch_onec_response(settings, code)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": "Timeout while requesting 1C service",
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": f"Connection error while requesting 1C service: {exc.__class__.__name__}",
        }

    return {
        "ok": response.status_code == 200,
        "code": code,
        "source_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "apparent_encoding": getattr(response, "encoding", None),
        "first_200_bytes_hex": response.content[:200].hex(),
        "utf8_text_preview": response.content.decode("utf-8", errors="replace")[:500],
    }
