"""Create the initial administrator explicitly from a trusted terminal."""
import argparse
import getpass
from app.database import get_session_local
from app.core.security import get_password_hash
from app.schemas.user import UserCreate
from app.models.user import User

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("New administrator password: ")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match.")
    data = UserCreate(email=args.email, full_name=args.name, password=password)
    with get_session_local()() as db:
        if db.query(User).filter_by(email=str(data.email).lower()).first():
            raise SystemExit("Email already exists; refusing to change an existing account.")
        db.add(User(email=str(data.email).lower(), full_name=data.full_name, hashed_password=get_password_hash(password), role_id="ADMIN_SAAS", is_active=True))
        db.commit()
    print("Administrator created. No other accounts were modified.")

if __name__ == "__main__":
    main()
