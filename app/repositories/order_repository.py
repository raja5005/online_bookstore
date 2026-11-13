"""Database queries for orders.

Customer queries always filter by the customer's id, so a customer can only
ever reach their own orders. Admin queries can reach any order.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Book, BookAuthor, Order, OrderItem, OrderStatus

ORDER_DETAILS = (
    selectinload(Order.items)
    .selectinload(OrderItem.book)
    .selectinload(Book.author_links)
    .selectinload(BookAuthor.author),
    selectinload(Order.payments),
    selectinload(Order.history),
    selectinload(Order.customer),
)


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Customer queries -------------------------------------------------

    def get_for_customer(self, order_id: int, user_id: int) -> Order | None:
        return self.session.scalar(
            select(Order)
            .options(*ORDER_DETAILS)
            .where(Order.id == order_id, Order.user_id == user_id)
        )

    def lock_for_customer(self, order_id: int, user_id: int) -> Order | None:
        return self.session.scalar(
            select(Order).where(Order.id == order_id, Order.user_id == user_id).with_for_update()
        )

    def list_for_customer(self, user_id: int, limit: int, offset: int) -> tuple[list[Order], int]:
        return self._page([Order.user_id == user_id], limit, offset)

    # --- Admin queries ----------------------------------------------------

    def get(self, order_id: int) -> Order | None:
        return self.session.scalar(select(Order).options(*ORDER_DETAILS).where(Order.id == order_id))

    def lock(self, order_id: int) -> Order | None:
        return self.session.scalar(select(Order).where(Order.id == order_id).with_for_update())

    def list_all(self, status: OrderStatus | None, limit: int, offset: int) -> tuple[list[Order], int]:
        conditions = [Order.status == status] if status else []
        return self._page(conditions, limit, offset)

    # ----------------------------------------------------------------------

    def _page(self, conditions: list, limit: int, offset: int) -> tuple[list[Order], int]:
        total = self.session.scalar(select(func.count()).select_from(Order).where(*conditions))
        orders = self.session.scalars(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.customer))
            .where(*conditions)
            .order_by(Order.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(orders), total

    def add(self, order: Order) -> None:
        self.session.add(order)
