"""Test setup: every run rebuilds the TEST_DATABASE_URL schema through the real Alembic
migrations (so the seed data under test is exactly what production gets), and each test starts
with no expenses."""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.exit(
        "TEST_DATABASE_URL is not set. Start PostgreSQL (docker compose up -d db) and export "
        "TEST_DATABASE_URL, or run the suite with: docker compose run --rm backend-tests",
        returncode=2,
    )
# The app reads DATABASE_URL at first use; point it at the test database before importing it.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    config = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    # configparser treats % as interpolation, so escape it in URL-encoded passwords.
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def clean_expenses() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE expense_shares, expenses RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
