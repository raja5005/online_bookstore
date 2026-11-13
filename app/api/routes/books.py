"""Public catalog endpoints."""
from fastapi import APIRouter

from app.api.deps import CategoryFilter, DbSession, PageNumber, PageSize, SearchTerm
from app.models import Book, Category
from app.schemas.book import BookOut, BookPage, CategoryOut
from app.services.book_service import BookService

router = APIRouter(prefix="/api", tags=["Catalog"])


@router.get("/books", response_model=BookPage)
def list_books(
    session: DbSession,
    search: SearchTerm = None,
    category_id: CategoryFilter = None,
    page: PageNumber = 1,
    page_size: PageSize = 12,
) -> dict:
    """List books for sale. Search matches title, author or ISBN."""
    return BookService(session).list_books(
        search=search, category_id=category_id, page=page, page_size=page_size
    )


@router.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, session: DbSession) -> Book:
    """Show one book's details and availability."""
    return BookService(session).get_for_sale(book_id)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(session: DbSession) -> list[Category]:
    return BookService(session).list_categories()
