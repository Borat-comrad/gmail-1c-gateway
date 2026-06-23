import json
import logging
from email.message import Message
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


def _error_message(status_code: int) -> str:
    messages = {
        401: "Неверный логин или пароль 1С",
        403: "Нет прав для доступа к данным 1С",
        404: "Код не найден или путь к сервису 1С неверный",
        500: "Ошибка сервера 1С",
    }
    return messages.get(status_code, f"Сервис 1С вернул ошибку {status_code}")


def _charset_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None

    message = Message()
    message["content-type"] = content_type
    return message.get_param("charset", header="content-type")


def is_mojibake(text: str) -> bool:
    return has_bad_mojibake(text)


def has_cyrillic(text: str) -> bool:
    return any(
        "\u0410" <= char <= "\u042f"
        or "\u0430" <= char <= "\u044f"
        or char in ("\u0401", "\u0451")
        for char in text
    )


def has_bad_mojibake(text: str) -> bool:
    markers = ("\u00d0", "\u00d1", "\u0420\u045f", "\u0421\u0403", "\u0421\u201a")
    return any(marker in text for marker in markers)


def repair_mojibake(text: str) -> str | None:
    for source_encoding in ("latin1", "cp1251"):
        try:
            repaired = text.encode(source_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if not is_mojibake(repaired):
            return repaired

    return None


def repair_text_value(value: str) -> str:
    attempts = []

    if "\u00d0" in value or "\u00d1" in value:
        attempts.extend(("latin1", "cp1252"))

    if "\u0420" in value or "\u0421" in value:
        attempts.append("cp1251")

    for source_encoding in dict.fromkeys(attempts):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if has_cyrillic(repaired) and not has_bad_mojibake(repaired):
            return repaired

    return value


def repair_json_mojibake(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            repair_text_value(key) if isinstance(key, str) else key: repair_json_mojibake(val)
            for key, val in value.items()
        }

    if isinstance(value, list):
        return [repair_json_mojibake(item) for item in value]

    if isinstance(value, str):
        return repair_text_value(value)

    return value


def decode_response_body(content: bytes, content_type: str | None) -> str:
    # 1C may return Russian data in a legacy encoding.
    encodings = []
    for encoding in (
        "utf-8",
        "cp1251",
        "windows-1251",
        _charset_from_content_type(content_type),
    ):
        if encoding and encoding not in encodings:
            encodings.append(encoding)

    decoded_candidates = []

    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

        if not is_mojibake(decoded):
            return decoded

        decoded_candidates.append(decoded)

    for decoded in decoded_candidates:
        repaired = repair_mojibake(decoded)
        if repaired is not None:
            return repaired

    return content.decode("utf-8", errors="replace")


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

    content_type = response.headers.get("content-type")
    decoded_text = decode_response_body(response.content, content_type)

    if response.status_code == 200:
        try:
            parsed = json.loads(decoded_text)
        except ValueError:
            data = None
            raw = repair_text_value(decoded_text)
        else:
            repaired = repair_json_mojibake(parsed)
            data = repaired
            raw = None
            logger.warning(
                "1C decoded response diagnostics: content_type=%r decoded_preview=%r parsed_preview=%r",
                content_type,
                decoded_text[:300],
                json.dumps(repaired, ensure_ascii=False)[:300],
            )

        result = {
            "ok": True,
            "code": code,
            "source_status": response.status_code,
            "data": data,
            "raw": raw,
        }
        if isinstance(data, dict):
            result["debug_repaired_keys"] = list(data.keys())

        return result

    return {
        "ok": False,
        "code": code,
        "source_status": response.status_code,
        "error": _error_message(response.status_code),
        "raw": repair_text_value(decoded_text),
    }
