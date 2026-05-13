from datetime import datetime
from typing import Any

from app.schemas.common import OrmModel
from app.schemas.item import ItemRead


class WechatDraftRead(OrmModel):
    id: str
    item_id: str
    draft_type: str
    title: str
    digest: str
    markdown: str
    image_plan: dict[str, Any]
    style_notes: dict[str, Any]
    submission_status: str
    submit_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    item: ItemRead | None = None
