import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "chave-secreta-dev-renata-2024"

    SQL_SERVER = os.environ.get("SQL_SERVER") or "127.0.0.1,1433"
    SQL_DATABASE = os.environ.get("SQL_DATABASE") or "SistemaChamados"
    SQL_USER = os.environ.get("SQL_USER") or "pi_grp1"
    SQL_PASSWORD = os.environ.get("SQL_PASSWORD") or "C0c@C0l@"
    SQL_DRIVER = os.environ.get("SQL_DRIVER") or "ODBC Driver 17 for SQL Server"

    SQLALCHEMY_DATABASE_URI = (
        f"mssql+pyodbc://{quote_plus(SQL_USER)}:{quote_plus(SQL_PASSWORD)}"
        f"@{SQL_SERVER}/{SQL_DATABASE}"
        f"?driver={quote_plus(SQL_DRIVER)}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # EMAIL (SMTP generico)
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "smtp.office365.com"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = _as_bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _as_bool(os.environ.get("MAIL_USE_SSL"), False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or ""
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or ""
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MAIL_TIMEOUT = int(os.environ.get("MAIL_TIMEOUT") or 20)

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = "uploads"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
