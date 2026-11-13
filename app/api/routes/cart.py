"""Shopping cart endpoints, for customers only."""
from fastapi import APIRouter

from app.api.deps import CurrentCustomer, DbSession
from app.models import Cart
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.services.cart_service import CartService

router = APIRouter(prefix="/api/cart", tags=["Shopping cart"])


@router.get("", response_model=CartOut)
def view_cart(session: DbSession, customer: CurrentCustomer) -> Cart:
    """Show the cart with line totals and the grand total."""
    return CartService(session).get_cart(customer.id)


@router.post("/items", response_model=CartOut)
def add_item(data: CartItemAdd, session: DbSession, customer: CurrentCustomer) -> Cart:
    """Add a book. If it is already in the cart, the quantities are combined."""
    return CartService(session).add_item(customer.id, data.book_id, data.quantity)


@router.patch("/items/{book_id}", response_model=CartOut)
def update_item(
    book_id: int, data: CartItemUpdate, session: DbSession, customer: CurrentCustomer
) -> Cart:
    """Set the quantity of a book already in the cart."""
    return CartService(session).update_item(customer.id, book_id, data.quantity)


@router.delete("/items/{book_id}", response_model=CartOut)
def remove_item(book_id: int, session: DbSession, customer: CurrentCustomer) -> Cart:
    """Remove a book from the cart."""
    return CartService(session).remove_item(customer.id, book_id)
