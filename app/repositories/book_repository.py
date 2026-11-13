"""Database queries for the catalog."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Author, Book, BookAuthor, Category

# Loading these up front avoids one extra query per book on a list page.
BOOK_DETAILS = (
    selectinload(Book.category),
    selectinload(Book.author_links).selectinload(BookAuthor.author),
)


class BookRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, book_id: int) -> Book | None:
        return self.session.scalar(
            select(Book).options(*BOOK_DETAILS).where(Book.id == book_id)
        )

    def search(
        self,
        *,
        search: str | None,
        category_id: int | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Book], int]:
        conditions = self._conditions(search, category_id, active_only)
        total = self.session.scalar(select(func.count()).select_from(Book).where(*conditions))
        books = self.session.scalars(
            select(Book)
            .options(*BOOK_DETAILS)
            .where(*conditions)
            .order_by(Book.title, Book.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(books), total

    @staticmethod
    def _conditions(search: str | None, category_id: int | None, active_only: bool) -> list:
        conditions = []
        if active_only:
            conditions.append(Book.is_active.is_(True))
        if category_id is not None:
            conditions.append(Book.category_id == category_id)

        term = (search or "").strip()
        if term:
            # autoescape treats % and _ as ordinary characters, not wildcards.
            matches = [
                Book.title.contains(term, autoescape=True),
                Book.author_links.any(
                    BookAuthor.author.has(Author.name.contains(term, autoescape=True))
                ),
            ]
            isbn_term = term.replace("-", "")
            if isbn_term:
                matches.append(Book.isbn.contains(isbn_term, autoescape=True))
            conditions.append(or_(*matches))
        return conditions

    def lock_many(self, book_ids: list[int]) -> dict[int, Book]:
        """Lock books for a stock change. Locking in id order prevents deadlocks."""
        books = self.session.scalars(
            select(Book).where(Book.id.in_(book_ids)).order_by(Book.id).with_for_update()
        )
        return {book.id: book for book in books}

    def list_categories(self) -> list[Category]:
        return list(self.session.scalars(select(Category).order_by(Category.name)))

    def get_category(self, category_id: int) -> Category | None:
        return self.session.get(Category, category_id)

    def get_or_create_author(self, name: str) -> Author:
        author = self.session.scalar(select(Author).where(Author.name == name))
        if author is None:
            author = Author(name=name)
            self.session.add(author)
            self.session.flush()
        return author

    def add(self, book: Book) -> None:
        self.session.add(book)
