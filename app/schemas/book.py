"""Request and response shapes for the catalog."""
import re
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

MAX_STOCK = 1_000_000


def _normalize_isbn(value: object) -> object:
    if not isinstance(value, str):
        return value
    isbn = re.sub(r"[\s-]", "", value)
    if not re.fullmatch(r"[0-9]{13}", isbn):
        raise ValueError("ISBN must contain exactly 13 digits.")
    return isbn


Isbn = Annotated[str, BeforeValidator(_normalize_isbn)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
# Free books are not allowed: every order must have something to pay.
Price = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Stock = Annotated[int, Field(ge=0, le=MAX_STOCK)]
CoverUrl = Annotated[str, StringConstraints(max_length=500, pattern=r"^https?://\S+$")]
CategoryId = Annotated[int, Field(ge=1)]
AuthorName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
AuthorNames = Annotated[list[AuthorName], Field(min_length=1, max_length=20)]


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    isbn: str
    title: str
    description: str | None
    price: Decimal
    stock: int
    in_stock: bool
    is_active: bool
    cover_url: str | None
    category: CategoryOut
    authors: list[str]


class BookPage(BaseModel):
    items: list[BookOut]
    total: int
    page: int
    page_size: int
    pages: int


class BookCreate(BaseModel):
    isbn: Isbn
    title: Title
    description: Optional[Description] = None
    price: Price
    stock: Stock = 0
    category_id: CategoryId
    cover_url: Optional[CoverUrl] = None
    authors: AuthorNames


class BookUpdate(BaseModel):
    """Only the fields sent are changed. Set is_active to false to withdraw a book."""

    isbn: Optional[Isbn] = None
    title: Optional[Title] = None
    description: Optional[Description] = None
    price: Optional[Price] = None
    stock: Optional[Stock] = None
    category_id: Optional[CategoryId] = None
    cover_url: Optional[CoverUrl] = None
    authors: Optional[AuthorNames] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def reject_null_for_required_columns(self) -> "BookUpdate":
        for field in self.model_fields_set - {"description", "cover_url"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self
