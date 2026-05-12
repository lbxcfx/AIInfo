from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class ApiMeta(BaseModel):
    request_id: str | None = None
    next_cursor: str | None = None


class ApiError(BaseModel):
    code: str
    message: str
    details: dict = {}


class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    meta: ApiMeta = ApiMeta()
    error: ApiError | None = None


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

