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


async def fetch_price_history(settings: Settings, code: str) -> dict[str, Any]:
    safe_code = quote(code, safe="")
    url = f"{settings.onec_base_url}/{safe_code}"

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(
                url,
                auth=(settings.onec_login, settings.onec_password),
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

    raw = response.text or None

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            data = None
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
        "raw": raw,
    }
