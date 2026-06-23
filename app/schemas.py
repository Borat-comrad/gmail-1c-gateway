from typing import Any

from pydantic import BaseModel


class PriceHistoryRequest(BaseModel):
    code: str


class PriceHistorySuccessResponse(BaseModel):
    ok: bool
    code: str
    source_status: int
    data: Any | None = None
    raw: str | None = None


class PriceHistoryErrorResponse(BaseModel):
    ok: bool
    code: str
    source_status: int | None = None
    error: str
    raw: str | None = None
