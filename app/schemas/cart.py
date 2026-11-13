"""Request and response shapes for the shopping cart."""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.book import BookOut

Quantity = Annotated[int, Field(gt=0, le=999)]


class CartItemAdd(BaseModel):
    book_id: Annotated[int, Field(ge=1)]
    quantity: Quantity = 1


class CartItemUpdate(BaseModel):
    quantity: Quantity


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book: BookOut
    quantity: int
    line_total: Decimal
    available: bool


class CartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CartItemOut]
    item_count: int
    total: Decimal
    can_checkout: bool
