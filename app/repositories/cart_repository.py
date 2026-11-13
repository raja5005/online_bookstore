"""Database queries for shopping carts."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import BookAuthor, Book, Cart, CartItem


class CartRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_with_details(self, user_id: int) -> Cart | None:
        book = selectinload(Cart.items).selectinload(CartItem.book)
        return self.session.scalar(
            select(Cart)
            .options(
                book.selectinload(Book.category),
                book.selectinload(Book.author_links).selectinload(BookAuthor.author),
            )
            .where(Cart.user_id == user_id)
        )

    # The two queries below lock their rows until the transaction ends, so
    # simultaneous changes to one cart happen one at a time. Both must be
    # locking reads: a request has already read the user by this point, and in
    # MySQL's default isolation level an ordinary read would keep returning
    # data from before the lock was obtained.

    def lock_cart(self, user_id: int) -> Cart | None:
        return self.session.scalar(
            select(Cart).where(Cart.user_id == user_id).with_for_update()
        )

    def lock_items(self, cart_id: int) -> list[CartItem]:
        return list(
            self.session.scalars(
                select(CartItem)
                .where(CartItem.cart_id == cart_id)
                .order_by(CartItem.id)
                .with_for_update()
            )
        )

    def lock_item(self, cart_id: int, book_id: int) -> CartItem | None:
        return self.session.scalar(
            select(CartItem)
            .where(CartItem.cart_id == cart_id, CartItem.book_id == book_id)
            .with_for_update()
        )
