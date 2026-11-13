"""Create the first administrator from the command line.

Run from the project folder: python -m scripts.create_admin

Public sign-up can only create customers, and only an admin can create another
admin through the API, so the first admin has to be created here.
"""
import getpass
import sys

from app.core.database import DatabaseManager
from app.core.exceptions import AppError
from app.models import UserRole
from app.services.auth_service import AuthService


def main() -> int:
    email = input("Admin email: ")
    full_name = input("Full name: ")
    password = getpass.getpass("Password (at least 12 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords do not match.", file=sys.stderr)
        return 1

    with DatabaseManager().new_session() as session:
        try:
            admin = AuthService(session).register(UserRole.ADMIN, email, password, full_name)
        except AppError as exc:
            print(exc.detail, file=sys.stderr)
            return 1
    print(f"Created admin {admin.email} with id {admin.id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
