import os
import uvicorn
from init_sprint1_db import init_db

if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization warning or deferred: {e}")

    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on 0.0.0.0:{port}...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
