import base64
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


def _error_message(status_code: int) -> str:
    messages = {
        401: "Неверный логин или пароль 1С",
        403: "Нет прав для доступа к данным 1С",
        404: "Код не найден или путь к сервису 1С неверный",
        500: "Ошибка сервера 1С",
    }
    return messages.get(status_code, f"Сервис 1С вернул ошибку {status_code}")


def make_basic_auth_header(login: str, password: str) -> str:
    raw = f"{login}:{password}"
    raw_bytes = raw.encode("utf-8")
    encoded = base64.b64encode(raw_bytes).decode("ascii")
    return f"Basic {encoded}"


async def fetch_price_history(settings: Settings, code: str) -> dict[str, Any]:
    safe_code = quote(code, safe="")
    url = f"{settings.onec_base_url}/{safe_code}"

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": make_basic_auth_header(
                        settings.onec_login,
                        settings.onec_password,
                    ),
                    "Accept": "application/json, text/plain, */*",
                },
            )
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
