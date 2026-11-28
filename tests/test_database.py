from database import normalize_database_url


def test_postgres_scheme_uses_installed_psycopg3_driver():
    assert normalize_database_url("postgres://user:pass@host:5432/ruta") == "postgresql+psycopg://user:pass@host:5432/ruta"


def test_postgresql_scheme_uses_installed_psycopg3_driver():
    assert normalize_database_url("postgresql://user:pass@host:5432/ruta?sslmode=require") == "postgresql+psycopg://user:pass@host:5432/ruta?sslmode=require"


def test_existing_psycopg_and_sqlite_urls_are_preserved():
    assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("sqlite:///./app.db") == "sqlite:///./app.db"
