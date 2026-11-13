"""Application entry point. Run with: uvicorn app.main:app --reload"""
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, books, cart, notifications, orders, users
from app.core.config import PROJECT_ROOT
from app.core.database import DatabaseManager
from app.core.exceptions import AppError

app = FastAPI(
    title="Online Bookstore API",
    description="Capstone project: browse books, manage a cart, order and pay.",
    version="0.7.0",
)


@app.exception_handler(AppError)
def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(books.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(notifications.router)
app.include_router(admin.router)


@app.get("/health", tags=["System"])
def health() -> JSONResponse:
    """Report whether the API can reach the database."""
    if DatabaseManager().is_available():
        return JSONResponse({"status": "ok", "database": "connected"})
    return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)


class FrontendFiles(StaticFiles):
    """Makes browsers check for newer files, so an update shows on a normal refresh."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Must stay last: anything not matched above is served from the frontend folder.
app.mount("/", FrontendFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
