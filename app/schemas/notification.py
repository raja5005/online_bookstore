"""Response shapes for notifications."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    message: str
    order_id: int | None
    is_read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
    page: int
    page_size: int
    pages: int


class MarkedRead(BaseModel):
    marked: int
