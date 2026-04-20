import os
from datetime import timedelta
from urllib.parse import quote_plus

class Config:
    # Configuracoes do Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-dev-renata-2024'

    # Configuracoes do SQL Server
    SQL_SERVER = os.environ.get('SQL_SERVER') or '127.0.0.1,1433'
    SQL_DATABASE = os.environ.get('SQL_DATABASE') or 'SistemaChamados'
    SQL_USER = os.environ.get('SQL_USER') or 'pi_grp1'
    SQL_PASSWORD = os.environ.get('SQL_PASSWORD') or 'C0c@C0l@'
    SQL_DRIVER = 'ODBC Driver 17 for SQL Server'

    # String de conexao (corrigida)
    SQLALCHEMY_DATABASE_URI = (
    f"mssql+pyodbc://{quote_plus(SQL_USER)}:{quote_plus(SQL_PASSWORD)}"
    f"@{SQL_SERVER}/{SQL_DATABASE}"
    f"?driver={quote_plus(SQL_DRIVER)}")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuracoes de sessao
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    #Configurações de e-mail
    # =========================
    # EMAIL (SMTP)
    # =========================
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'pigrp1.suporte@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'C0c@C0l@'
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    # Configuracoes de upload (futuro)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'uploads'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}