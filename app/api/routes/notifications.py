"""Notification endpoints. Notifications are created by the Observer pattern."""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, PageNumber, PageSize
from app.models import Notification
from app.schemas.notification import MarkedRead, NotificationOut, NotificationPage
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications(
    session: DbSession,
    user: CurrentUser,
    unread_only: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> dict:
    """Your notifications, newest first, with the number still unread."""
    return NotificationService(session).list_notifications(user.id, unread_only, page, page_size)


@router.post("/read-all", response_model=MarkedRead)
def mark_all_read(session: DbSession, user: CurrentUser) -> dict:
    return {"marked": NotificationService(session).mark_all_read(user.id)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, session: DbSession, user: CurrentUser) -> Notification:
    return NotificationService(session).mark_read(user.id, notification_id)
