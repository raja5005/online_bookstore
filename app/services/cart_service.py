"""Shopping cart rules.

A cart does not reserve stock. The stock check here gives immediate feedback,
and is repeated under a row lock when an order is placed (Week 5).
"""
from sqlalchemy.orm import Session

from app.core.exceptions import BookNotFound, CartItemNotFound, CartNotFound, InsufficientStock
from app.models import Book, Cart, CartItem
from app.repositories.book_repository import BookRepository
from app.repositories.cart_repository import CartRepository


class CartService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.carts = CartRepository(session)
        self.books = BookRepository(session)

    def get_cart(self, user_id: int) -> Cart:
        cart = self.carts.get_with_details(user_id)
        if cart is None:
            raise CartNotFound()
        return cart

    def add_item(self, user_id: int, book_id: int, quantity: int) -> Cart:
        cart = self._locked_cart(user_id)
        book = self.books.get(book_id)
        if book is None or not book.is_active:
            raise BookNotFound()

        item = self.carts.lock_item(cart.id, book_id)
        new_quantity = quantity + (item.quantity if item else 0)
        self._check_stock(book, new_quantity)

        if item is None:
            self.session.add(CartItem(cart_id=cart.id, book_id=book_id, quantity=new_quantity))
        else:
            item.quantity = new_quantity
        return self._save(user_id)

    def update_item(self, user_id: int, book_id: int, quantity: int) -> Cart:
        cart = self._locked_cart(user_id)
        item = self._locked_item(cart, book_id)
        self._check_stock(self.books.get(book_id), quantity)
        item.quantity = quantity
        return self._save(user_id)

    def remove_item(self, user_id: int, book_id: int) -> Cart:
        cart = self._locked_cart(user_id)
        self.session.delete(self._locked_item(cart, book_id))
        return self._save(user_id)

    def _locked_cart(self, user_id: int) -> Cart:
        cart = self.carts.lock_cart(user_id)
        if cart is None:
            raise CartNotFound()
        return cart

    def _locked_item(self, cart: Cart, book_id: int) -> CartItem:
        item = self.carts.lock_item(cart.id, book_id)
        if item is None:
            raise CartItemNotFound()
        return item

    @staticmethod
    def _check_stock(book: Book, quantity: int) -> None:
        if quantity > book.stock:
            raise InsufficientStock(
                f'Only {book.stock} of "{book.title}" available. You asked for {quantity}.'
            )

    def _save(self, user_id: int) -> Cart:
        self.session.commit()
        self.session.expire_all()
        return self.get_cart(user_id)
