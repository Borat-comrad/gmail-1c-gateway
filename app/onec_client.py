import base64
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


def _error_message(status_code: int) -> str:
    messages = {
        401: "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u043b\u043e\u0433\u0438\u043d \u0438\u043b\u0438 \u043f\u0430\u0440\u043e\u043b\u044c 1\u0421",
        403: "\u041d\u0435\u0442 \u043f\u0440\u0430\u0432 \u0434\u043b\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0434\u0430\u043d\u043d\u044b\u043c 1\u0421",
        404: "\u041a\u043e\u0434 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0438\u043b\u0438 \u043f\u0443\u0442\u044c \u043a \u0441\u0435\u0440\u0432\u0438\u0441\u0443 1\u0421 \u043d\u0435\u0432\u0435\u0440\u043d\u044b\u0439",
        500: "\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0440\u0432\u0435\u0440\u0430 1\u0421",
    }
    return messages.get(
        status_code,
        f"\u0421\u0435\u0440\u0432\u0438\u0441 1\u0421 \u0432\u0435\u0440\u043d\u0443\u043b \u043e\u0448\u0438\u0431\u043a\u0443 {status_code}",
    )


def make_basic_auth_header(login: str, password: str) -> str:
    raw = f"{login}:{password}"
    raw_bytes = raw.encode("utf-8")
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"Basic {encoded}"


def make_onec_headers(login: str, password: str) -> dict[str, str]:
    return {
        "Authorization": make_basic_auth_header(login, password),
        "Accept": "application/json, text/plain, */*",
    }


async def fetch_onec_response(settings: Settings, code: str) -> httpx.Response:
    safe_code = quote(code, safe="")
    url = f"{settings.onec_base_url}/{safe_code}"

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        return await client.get(
            url,
            headers=make_onec_headers(settings.onec_login, settings.onec_password),
        )


async def fetch_price_history(settings: Settings, code: str) -> dict[str, Any]:
    try:
        response = await fetch_onec_response(settings=settings, code=code)
    except httpx.TimeoutException:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": "\u0422\u0430\u0439\u043c\u0430\u0443\u0442 \u043f\u0440\u0438 \u043e\u0431\u0440\u0430\u0449\u0435\u043d\u0438\u0438 \u043a \u0441\u0435\u0440\u0432\u0438\u0441\u0443 1\u0421",
            "raw": None,
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "code": code,
            "source_status": None,
            "error": f"\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043a \u0441\u0435\u0440\u0432\u0438\u0441\u0443 1\u0421: {exc.__class__.__name__}",
            "raw": None,
        }

    # Chrome extension shows 1C returns valid UTF-8 JSON, so the backend reads
    # UTF-8 directly and does not repair mojibake.
    try:
        decoded_text = response.content.decode("utf-8")
    except UnicodeDecodeError:
        decoded_text = response.text

    if response.status_code == 200:
        try:
            data = json.loads(decoded_text)
        except ValueError:
            data = None
            raw = decoded_text
        else:
            raw = None

        return {
            "ok": True,
            "code": code,
            "source_status": response.status_code,
            "data": data,
            "raw": raw,
        }

    return {
        "ok": False,
        "code": code,
        "source_status": response.status_code,
        "error": _error_message(response.status_code),
        "raw": decoded_text,
    }


async def fetch_price_history_debug_raw(settings: Settings, code: str) -> dict[str, Any]:
    try:
        response = await fetch_onec_response(settings=settings, code=code)
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

    content = response.content

    return {
        "ok": response.status_code == 200,
        "code": code,
        "source_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "apparent_encoding": getattr(response, "encoding", None),
        "first_200_bytes_hex": content[:200].hex(),
        "utf8_text_preview": content.decode("utf-8", errors="replace")[:500],
        "response_text_preview": response.text[:500],
        "cp1251_text_preview": content.decode("cp1251", errors="replace")[:500],
    }
