import base64
import json
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


def _build_onec_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": make_basic_auth_header(
            settings.onec_login,
            settings.onec_password,
        ),
        "Accept": "application/json, text/plain, */*",
    }


def _error_message(status_code: int) -> str:
    messages = {
        401: "Неверный логин или пароль 1С",
        403: "Нет прав для доступа к данным 1С",
        404: "Код не найден или путь к сервису 1С неверный",
        500: "Ошибка сервера 1С",
    }
    return messages.get(status_code, f"Сервис 1С вернул ошибку {status_code}")


def looks_broken_cyrillic(text: str) -> bool:
    markers = ("Ð", "Ñ", "Рџ", "Р°", "Рµ", "Рѕ", "Рё", "СЃ", "С‚", "СЂ", "�")
    return any(marker in text for marker in markers)


def has_cyrillic(text: str) -> bool:
    return any(
        "А" <= char <= "Я" or "а" <= char <= "я" or char in ("Ё", "ё")
        for char in text
    )


def fix_broken_cyrillic(text: str) -> str:
    if not looks_broken_cyrillic(text):
        return text

    attempts = (
        ("latin1", "strict", "strict"),
        ("cp1252", "strict", "strict"),
        ("latin1", "ignore", "ignore"),
    )

    for source_encoding, encode_errors, decode_errors in attempts:
        try:
            fixed = text.encode(source_encoding, errors=encode_errors).decode(
                "utf-8",
                errors=decode_errors,
            )
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if has_cyrillic(fixed) and "Ð" not in fixed and "Ñ" not in fixed:
            return fixed

    return text


def normalize_json_text(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            fix_broken_cyrillic(key) if isinstance(key, str) else key: normalize_json_text(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [normalize_json_text(item) for item in value]

    if isinstance(value, str):
        return fix_broken_cyrillic(value)

    return value


async def fetch_onec_response(settings: Settings, code: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        return await client.get(
            build_onec_url(settings, code),
            headers=_build_onec_headers(settings),
        )


async def fetch_price_history(settings: Settings, code: str) -> dict[str, Any]:
    try:
        response = await fetch_onec_response(settings, code)
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

    if response.status_code != 200:
        decoded_text = response.content.decode("utf-8", errors="replace")
        return {
            "ok": False,
            "code": code,
            "source_status": response.status_code,
            "error": _error_message(response.status_code),
            "raw": decoded_text,
        }

    try:
        decoded_text = response.content.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "ok": True,
            "code": code,
            "source_status": response.status_code,
            "data": None,
            "raw": response.content.decode("utf-8", errors="replace"),
        }

    try:
        parsed = json.loads(decoded_text)
    except ValueError:
        return {
            "ok": True,
            "code": code,
            "source_status": response.status_code,
            "data": None,
            "raw": decoded_text,
        }

    normalized = normalize_json_text(parsed)

    return {
        "ok": True,
        "code": code,
        "source_status": response.status_code,
        "data": normalized,
        "raw": None,
        "server_code_version": "clean_utf8_probe_1",
        "decoded_preview": decoded_text[:500],
        "parsed_keys": list(parsed.keys()) if isinstance(parsed, dict) else [],
        "parsed_keys_repr": [repr(key) for key in parsed.keys()]
        if isinstance(parsed, dict)
        else [],
        "normalized_keys": list(normalized.keys()) if isinstance(normalized, dict) else [],
        "normalized_keys_repr": [repr(key) for key in normalized.keys()]
        if isinstance(normalized, dict)
        else [],
    }


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
