"""Application errors. A handler in app/main.py turns these into HTTP responses."""


class AppError(Exception):
    status_code = 400
    detail = "The request could not be processed."
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class EmailAlreadyRegistered(AppError):
    status_code = 409
    detail = "An account with this email already exists."


class WeakPassword(AppError):
    status_code = 422
    detail = "The password does not meet the requirements."


class InvalidCredentials(AppError):
    status_code = 401
    detail = "Incorrect email or password."
    headers = {"WWW-Authenticate": "Bearer"}


class InvalidToken(AppError):
    status_code = 401
    detail = "The access token is invalid or has expired."
    headers = {"WWW-Authenticate": "Bearer"}


class PermissionDenied(AppError):
    status_code = 403
    detail = "You do not have permission to do this."


class BookNotFound(AppError):
    status_code = 404
    detail = "This book could not be found."


class CategoryNotFound(AppError):
    status_code = 404
    detail = "This category could not be found."


class CartNotFound(AppError):
    status_code = 404
    detail = "This account does not have a cart."


class CartItemNotFound(AppError):
    status_code = 404
    detail = "This book is not in your cart."


class DuplicateIsbn(AppError):
    status_code = 409
    detail = "A book with this ISBN already exists."


class InsufficientStock(AppError):
    status_code = 409
    detail = "There is not enough stock for that quantity."


class OrderNotFound(AppError):
    status_code = 404
    detail = "This order could not be found."


class EmptyCart(AppError):
    status_code = 409
    detail = "Your cart is empty."


class BookUnavailable(AppError):
    status_code = 409
    detail = "A book in your cart is no longer for sale."


class InvalidOrderTransition(AppError):
    status_code = 409
    detail = "This order cannot be changed that way."


class OrderNotPayable(AppError):
    status_code = 409
    detail = "This order is not waiting for payment."


class NotificationNotFound(AppError):
    status_code = 404
    detail = "This notification could not be found."


class ConcurrentChange(AppError):
    status_code = 409
    detail = "Another change happened at the same time. Please try again."
