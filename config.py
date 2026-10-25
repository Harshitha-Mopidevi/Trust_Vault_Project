import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-before-deployment")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'trustvault.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "txt", "xls", "xlsx", "csv", "ppt", "pptx",
        "png", "jpg", "jpeg", "gif", "webp", "bmp",
    }

    # Optional ONLYOFFICE Docs integration for read-only Office document viewing.
    # Values are read from .env after load_dotenv() is called in run.py.
    ONLYOFFICE_DOCUMENT_SERVER = os.getenv("ONLYOFFICE_DOCUMENT_SERVER", "").strip()
    ONLYOFFICE_PUBLIC_URL = os.getenv("ONLYOFFICE_PUBLIC_URL", "").strip()
    ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "").strip()
