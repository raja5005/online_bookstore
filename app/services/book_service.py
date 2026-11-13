"""Catalog browsing and book administration."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import is_duplicate_entry
from app.core.exceptions import BookNotFound, CategoryNotFound, ConcurrentChange, DuplicateIsbn
from app.models import Book, BookAuthor, Category
from app.repositories.book_repository import BookRepository
from app.schemas.book import BookCreate, BookUpdate


class BookService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.books = BookRepository(session)

    def list_books(
        self,
        *,
        search: str | None,
        category_id: int | None,
        page: int,
        page_size: int,
        include_inactive: bool = False,
    ) -> dict:
        items, total = self.books.search(
            search=search,
            category_id=category_id,
            active_only=not include_inactive,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    def get_for_sale(self, book_id: int) -> Book:
        book = self.books.get(book_id)
        if book is None or not book.is_active:
            raise BookNotFound()
        return book

    def list_categories(self) -> list[Category]:
        return self.books.list_categories()

    def create_book(self, data: BookCreate) -> Book:
        self._require_category(data.category_id)
        book = Book(**data.model_dump(exclude={"authors"}))
        with self._translating_conflicts():
            self.books.add(book)
            self._set_authors(book, data.authors)
            self.session.commit()
        return self._reload(book.id)

    def update_book(self, book_id: int, data: BookUpdate) -> Book:
        book = self.books.get(book_id)
        if book is None:
            raise BookNotFound()

        changes = data.model_dump(exclude_unset=True)
        authors = changes.pop("authors", None)
        if "category_id" in changes:
            self._require_category(changes["category_id"])

        with self._translating_conflicts():
            for field, value in changes.items():
                setattr(book, field, value)
            if authors is not None:
                self._set_authors(book, authors)
            self.session.commit()
        return self._reload(book_id)

    def _require_category(self, category_id: int) -> None:
        if self.books.get_category(category_id) is None:
            raise CategoryNotFound()

    def _set_authors(self, book: Book, names: list[str]) -> None:
        # Names are resolved before removing duplicates because MySQL compares
        # names without regard to case or accents, so "JANE" finds "Jane".
        unique = {}
        for name in names:
            author = self.books.get_or_create_author(name)
            unique.setdefault(author.id, author)

        existing = {link.author_id: link for link in book.author_links}
        links = []
        for position, author in enumerate(unique.values(), start=1):
            link = existing.get(author.id) or BookAuthor(author=author)
            link.author_position = position
            links.append(link)
        book.author_links = links

    def _reload(self, book_id: int) -> Book:
        self.session.expire_all()
        return self.books.get(book_id)

    @contextmanager
    def _translating_conflicts(self) -> Iterator[None]:
        try:
            yield
        except IntegrityError as exc:
            self.session.rollback()
            if not is_duplicate_entry(exc):
                raise
            if "uq_books_isbn" in str(exc.orig):
                raise DuplicateIsbn() from exc
            raise ConcurrentChange() from exc
