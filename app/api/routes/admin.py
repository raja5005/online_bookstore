"""Endpoints restricted to administrators."""
from fastapi import APIRouter, status

from app.api.deps import (
    CategoryFilter,
    CurrentAdmin,
    DbSession,
    PageNumber,
    PageSize,
    SearchTerm,
)
from app.models import Book, Order, OrderStatus, User, UserRole
from app.schemas.book import BookCreate, BookOut, BookPage, BookUpdate
from app.schemas.order import AdminOrderOut, AdminOrderPage
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import AuthService
from app.services.book_service import BookService
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/admin", tags=["Administration"])


@router.post("/admins", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_admin(data: UserCreate, session: DbSession, _: CurrentAdmin) -> User:
    """Create another administrator. Admin passwords need at least 12 characters."""
    return AuthService(session).register(UserRole.ADMIN, data.email, data.password, data.full_name)


@router.get("/books", response_model=BookPage)
def list_all_books(
    session: DbSession,
    _: CurrentAdmin,
    search: SearchTerm = None,
    category_id: CategoryFilter = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> dict:
    """List every book, including those withdrawn from sale."""
    return BookService(session).list_books(
        search=search,
        category_id=category_id,
        page=page,
        page_size=page_size,
        include_inactive=True,
    )


@router.post("/books", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def add_book(data: BookCreate, session: DbSession, _: CurrentAdmin) -> Book:
    """Add a new book. Authors that don't exist yet are created automatically."""
    return BookService(session).create_book(data)


@router.patch("/books/{book_id}", response_model=BookOut)
def update_book(book_id: int, data: BookUpdate, session: DbSession, _: CurrentAdmin) -> Book:
    """Change a book's details, price or stock. Set is_active to withdraw or restore it."""
    return BookService(session).update_book(book_id, data)


@router.get("/orders", response_model=AdminOrderPage)
def list_all_orders(
    session: DbSession,
    _: CurrentAdmin,
    status: OrderStatus | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
) -> dict:
    """List every customer's orders, newest first, optionally filtered by status."""
    return OrderService(session).list_all_orders(status, page, page_size)


@router.get("/orders/{order_id}", response_model=AdminOrderOut)
def get_any_order(order_id: int, session: DbSession, _: CurrentAdmin) -> Order:
    return OrderService(session).get_any_order(order_id)


@router.post("/orders/{order_id}/ship", response_model=AdminOrderOut)
def ship_order(order_id: int, session: DbSession, admin: CurrentAdmin) -> Order:
    """Mark a paid order as shipped."""
    return OrderService(session).ship(admin.id, order_id)


@router.post("/orders/{order_id}/deliver", response_model=AdminOrderOut)
def deliver_order(order_id: int, session: DbSession, admin: CurrentAdmin) -> Order:
    """Mark a shipped order as delivered."""
    return OrderService(session).deliver(admin.id, order_id)


@router.post("/orders/{order_id}/cancel", response_model=AdminOrderOut)
def cancel_any_order(order_id: int, session: DbSession, admin: CurrentAdmin) -> Order:
    """Cancel an order that has not shipped. Stock is restored and any payment refunded."""
    return OrderService(session).cancel_as_admin(admin.id, order_id)
