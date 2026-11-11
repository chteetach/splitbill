import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import repositories
from app.db import get_engine
from app.main import app
from tests.helpers import as_user, equal_expense


def expense_count() -> int:
    with get_engine().connect() as conn:
        return conn.scalar(text("SELECT COUNT(*) FROM expenses"))


def test_repeated_idempotency_key_creates_one_expense(client: TestClient) -> None:
    body = equal_expense("1000.00", ["alice", "bob", "carol"])
    headers = as_user("alice", "7f3c2a10-dinner-0001")

    first = client.post("/groups/1/expenses", json=body, headers=headers)
    second = client.post("/groups/1/expenses", json=body, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json() == first.json()
    assert expense_count() == 1


def test_equivalent_amount_formatting_counts_as_the_same_request(client: TestClient) -> None:
    headers = as_user("alice", "same-amount")
    first = client.post(
        "/groups/1/expenses", json=equal_expense("1000", ["alice", "bob"]), headers=headers
    )
    second = client.post(
        "/groups/1/expenses", json=equal_expense("1000.00", ["alice", "bob"]), headers=headers
    )
    assert (first.status_code, second.status_code) == (201, 200)
    assert expense_count() == 1


def test_key_reused_for_a_different_request_is_rejected(client: TestClient) -> None:
    headers = as_user("alice", "reused-key")
    client.post("/groups/1/expenses", json=equal_expense("10.00", ["alice"]), headers=headers)
    res = client.post("/groups/1/expenses", json=equal_expense("20.00", ["alice"]), headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "idempotency_key_reused"
    assert expense_count() == 1


def test_same_key_in_another_group_is_independent(client: TestClient) -> None:
    key = "shared-key"
    a = client.post(
        "/groups/1/expenses",
        json=equal_expense("10.00", ["bob"], paid_by="bob"),
        headers=as_user("bob", key),
    )
    b = client.post(
        "/groups/2/expenses",
        json=equal_expense("10.00", ["bob"], paid_by="bob"),
        headers=as_user("bob", key),
    )
    assert (a.status_code, b.status_code) == (201, 201)
    assert expense_count() == 2


def test_failed_request_does_not_consume_the_key(client: TestClient) -> None:
    headers = as_user("alice", "retry-after-fix")
    bad = client.post(
        "/groups/1/expenses",
        json={**equal_expense("10.00", ["alice"]), "amount": "10.001"},
        headers=headers,
    )
    assert bad.status_code == 422
    good = client.post(
        "/groups/1/expenses", json=equal_expense("10.00", ["alice"]), headers=headers
    )
    assert good.status_code == 201


def wait_for_lock_waiter(timeout: float = 5.0) -> None:
    """Block until some other connection is waiting on a row/index lock."""
    deadline = time.monotonic() + timeout
    with get_engine().connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.scalar(
                text(
                    "SELECT COUNT(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                )
            )
            if waiting:
                return
            time.sleep(0.02)
    raise AssertionError("second request never blocked on the first one's insert")


def test_concurrent_requests_with_same_key_create_one_expense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force a real race: request A inserts its row and pauses before committing, so request B
    cannot see it, misses the fast-path lookup and reaches the INSERT while A's transaction is
    still open. B must wait for A and then return A's expense instead of creating a second."""
    body = equal_expense("300.00", ["alice", "bob", "carol"])
    headers = as_user("alice", "concurrent-0001")
    a_inserted, release_a = threading.Event(), threading.Event()
    real_add_shares = repositories.add_shares

    def add_shares_then_pause(*args, **kwargs):  # type: ignore[no-untyped-def]
        real_add_shares(*args, **kwargs)
        if not a_inserted.is_set():
            a_inserted.set()
            assert release_a.wait(timeout=10)

    monkeypatch.setattr(repositories, "add_shares", add_shares_then_pause)

    def submit() -> tuple[int, int]:
        with TestClient(app) as c:
            res = c.post("/groups/1/expenses", json=body, headers=headers)
            return res.status_code, res.json()["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(submit)
        assert a_inserted.wait(timeout=10)
        second = pool.submit(submit)
        wait_for_lock_waiter()
        release_a.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    assert [status for status, _ in results] == [201, 200]
    assert results[0][1] == results[1][1]
    assert expense_count() == 1
