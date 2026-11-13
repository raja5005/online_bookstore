"""Reading notifications and marking them as read. Users only reach their own."""
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import NotificationNotFound
from app.models import Notification


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_notifications(self, user_id: int, unread_only: bool, page: int, page_size: int) -> dict:
        mine = Notification.user_id == user_id
        conditions = [mine, Notification.is_read.is_(False)] if unread_only else [mine]
        total = self.session.scalar(select(func.count()).select_from(Notification).where(*conditions))
        unread = self.session.scalar(
            select(func.count()).select_from(Notification).where(mine, Notification.is_read.is_(False))
        )
        items = self.session.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        return {
            "items": items,
            "total": total,
            "unread": unread,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    def mark_read(self, user_id: int, notification_id: int) -> Notification:
        notification = self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        if notification is None:
            raise NotificationNotFound()
        notification.is_read = True
        self.session.commit()
        return notification

    def mark_all_read(self, user_id: int) -> int:
        result = self.session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        self.session.commit()
        return result.rowcount
