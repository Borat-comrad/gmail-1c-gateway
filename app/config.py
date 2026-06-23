from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    onec_base_url: str
    onec_login: str
    onec_password: str
    request_timeout_seconds: float


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Environment variable {name} is required")
    return value.strip()


def _timeout_seconds() -> float:
    value = _required_env("REQUEST_TIMEOUT_SECONDS")
    try:
        timeout = float(value)
    except ValueError as exc:
        raise RuntimeError("REQUEST_TIMEOUT_SECONDS must be a number") from exc

    if timeout <= 0:
        raise RuntimeError("REQUEST_TIMEOUT_SECONDS must be greater than 0")
    return timeout


@lru_cache
def get_settings() -> Settings:
    return Settings(
        onec_base_url=_required_env("ONEC_BASE_URL").rstrip("/"),
        onec_login=_required_env("ONEC_LOGIN"),
        onec_password=_required_env("ONEC_PASSWORD"),
        request_timeout_seconds=_timeout_seconds(),
    )
