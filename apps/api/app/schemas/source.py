from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import OrmModel


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    url: HttpUrl
    source_type: str = "rss"
    tier: str = "T2"
    language: str = "en"
    category_hint: str | None = None
    crawl_interval_minutes: int = Field(default=60, ge=5)
    is_enabled: bool = True
    reliability_score: int = Field(default=80, ge=0, le=100)
    extra: dict[str, Any] = {}


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    url: HttpUrl | None = None
    source_type: str | None = None
    tier: str | None = None
    language: str | None = None
    category_hint: str | None = None
    crawl_interval_minutes: int | None = Field(default=None, ge=5)
    is_enabled: bool | None = None
    reliability_score: int | None = Field(default=None, ge=0, le=100)
    extra: dict[str, Any] | None = None


class SourceRead(SourceBase, OrmModel):
    id: str
    url: str
    created_at: datetime
    updated_at: datetime

