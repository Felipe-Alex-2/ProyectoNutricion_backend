"""Start an isolated local API, or create its first administrator."""
import os
from pathlib import Path
import secrets
import sys

from dotenv import load_dotenv


def configure_local():
    root = Path(__file__).resolve().parent
    os.chdir(root)
    env_path = root / ".env.local"
    if not env_path.exists():
        env_path.write_text(
            "ENVIRONMENT=development\n"
            "DATABASE_URL=sqlite:///./nutricion_local.db\n"
            f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
            f"BACKUP_ENCRYPTION_KEY={secrets.token_urlsafe(48)}\n"
            "FRONTEND_URL=http://localhost:4200\n"
            "CORS_ORIGINS=http://localhost:4200,http://127.0.0.1:4200\n"
            "BACKUP_DIR=backups/local\n",
            encoding="utf-8",
        )
    # Override any Railway configuration inherited by this terminal.
    load_dotenv(env_path, override=True)
    from sqlalchemy.engine import make_url
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "sqlite" and url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("run_local.py only accepts a local database in .env.local.")
    if os.environ.get("ENVIRONMENT") != "development":
        raise SystemExit("Set ENVIRONMENT=development in .env.local.")


if __name__ == "__main__":
    configure_local()
    from prepare_db import prepare_database
    prepare_database()
    if len(sys.argv) > 1 and sys.argv[1] == "create-admin":
        sys.argv.pop(1)
        from create_admin import main
        main()
    else:
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
