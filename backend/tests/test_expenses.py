from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import as_user, balances_of, equal_expense, exact_expense


def test_equal_split_of_100_among_three_and_balances_sum_to_zero(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=equal_expense("100.00", ["alice", "bob", "carol"]),
        headers=as_user("alice"),
    )
    assert res.status_code == 201, res.text
    assert [(s["user"], s["amount"]) for s in res.json()["shares"]] == [
        ("alice", "33.34"),
        ("bob", "33.33"),
        ("carol", "33.33"),
    ]

    balances = balances_of(client.get("/groups/1/balances", headers=as_user("alice")).json())
    assert balances == {"alice": "66.66", "bob": "-33.33", "carol": "-33.33"}
    assert sum(Decimal(b) for b in balances.values()) == Decimal("0.00")


def test_brief_example_dinner_of_1000(client: TestClient) -> None:
    client.post(
        "/groups/1/expenses",
        json=equal_expense("1000.00", ["alice", "bob", "carol"]),
        headers=as_user("alice", "7f3c2a10-dinner-0001"),
    )
    balances = balances_of(client.get("/groups/1/balances", headers=as_user("bob")).json())
    assert balances == {"alice": "666.66", "bob": "-333.33", "carol": "-333.33"}


def test_remainder_follows_listed_order_not_alphabetical(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=equal_expense("100.00", ["carol", "bob", "alice"]),
        headers=as_user("alice"),
    )
    assert [(s["user"], s["amount"]) for s in res.json()["shares"]] == [
        ("carol", "33.34"),
        ("bob", "33.33"),
        ("alice", "33.33"),
    ]


def test_exact_split_is_recorded(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=exact_expense("1000.00", {"alice": "500.00", "bob": "300.00", "carol": "200.00"}),
        headers=as_user("alice"),
    )
    assert res.status_code == 201, res.text
    balances = balances_of(client.get("/groups/1/balances", headers=as_user("alice")).json())
    assert balances == {"alice": "500.00", "bob": "-300.00", "carol": "-200.00"}


def test_exact_split_not_summing_to_amount_is_rejected(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=exact_expense("1000.00", {"alice": "500.00", "bob": "300.00", "carol": "199.99"}),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "shares_mismatch"
    assert "999.99" in error["message"] and "1000.00" in error["message"]
    assert client.get("/groups/1/expenses", headers=as_user("alice")).json() == []


def test_amount_with_three_decimal_places_is_rejected(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=equal_expense("10.005", ["alice", "bob"]),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    assert "2 decimal places" in error["message"]
    assert error["details"][0]["field"] == "amount"


def test_exact_share_with_three_decimal_places_is_rejected(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=exact_expense("10.00", {"alice": "5.005", "bob": "4.995"}),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    assert "2 decimal places" in res.json()["error"]["message"]


def test_zero_negative_and_numeric_amounts_are_rejected(client: TestClient) -> None:
    for amount in ["0.00", "-5.00", 100.0, 100]:
        body = equal_expense("1.00", ["alice"])
        body["amount"] = amount
        res = client.post("/groups/1/expenses", json=body, headers=as_user("alice"))
        assert res.status_code == 422, amount


def test_payer_must_be_group_member(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=equal_expense("90.00", ["alice", "bob"], paid_by="dan"),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_group_member"
    assert res.json()["error"]["details"] == {"users": ["dan"]}


def test_split_members_must_be_group_members(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=exact_expense("90.00", {"alice": "45.00", "dan": "45.00"}),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "not_group_member"


def test_duplicate_members_in_equal_split_are_rejected(client: TestClient) -> None:
    res = client.post(
        "/groups/1/expenses",
        json=equal_expense("90.00", ["alice", "bob", "alice"]),
        headers=as_user("alice"),
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "duplicate_members"


def test_expenses_are_listed_newest_first(client: TestClient) -> None:
    for description in ["first", "second", "third"]:
        client.post(
            "/groups/1/expenses",
            json=equal_expense("30.00", ["alice", "bob"], description=description),
            headers=as_user("alice"),
        )
    listed = client.get("/groups/1/expenses", headers=as_user("carol")).json()
    assert [e["description"] for e in listed] == ["third", "second", "first"]


def test_only_the_payer_can_delete_an_expense(client: TestClient) -> None:
    created = client.post(
        "/groups/1/expenses",
        json=equal_expense("90.00", ["alice", "bob", "carol"], paid_by="bob"),
        headers=as_user("alice"),
    ).json()
    url = f"/groups/1/expenses/{created['id']}"

    # alice recorded it but bob paid, so alice may not delete it.
    res = client.delete(url, headers=as_user("alice"))
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "not_payer"
    assert len(client.get("/groups/1/expenses", headers=as_user("alice")).json()) == 1

    assert client.delete(url, headers=as_user("bob")).status_code == 204


def test_deleted_expense_is_hidden_and_excluded_from_balances(client: TestClient) -> None:
    keep = client.post(
        "/groups/1/expenses",
        json=equal_expense("30.00", ["alice", "bob", "carol"]),
        headers=as_user("alice"),
    ).json()
    drop = client.post(
        "/groups/1/expenses",
        json=equal_expense("300.00", ["alice", "bob", "carol"], paid_by="bob"),
        headers=as_user("bob"),
    ).json()

    assert (
        client.delete(f"/groups/1/expenses/{drop['id']}", headers=as_user("bob")).status_code == 204
    )

    listed = client.get("/groups/1/expenses", headers=as_user("alice")).json()
    assert [e["id"] for e in listed] == [keep["id"]]
    balances = balances_of(client.get("/groups/1/balances", headers=as_user("alice")).json())
    assert balances == {"alice": "20.00", "bob": "-10.00", "carol": "-10.00"}

    # Deleting again: the expense no longer exists from the API's point of view.
    again = client.delete(f"/groups/1/expenses/{drop['id']}", headers=as_user("bob"))
    assert again.status_code == 404


def test_soft_delete_keeps_the_row(client: TestClient) -> None:
    from sqlalchemy import text

    from app.db import get_engine

    created = client.post(
        "/groups/2/expenses",
        json=equal_expense("50.00", ["bob", "dan"], paid_by="dan"),
        headers=as_user("dan"),
    ).json()
    client.delete(f"/groups/2/expenses/{created['id']}", headers=as_user("dan"))
    with get_engine().connect() as conn:
        deleted_at = conn.scalar(
            text("SELECT deleted_at FROM expenses WHERE id = :id"), {"id": created["id"]}
        )
    assert deleted_at is not None


def test_expenses_cannot_be_edited(client: TestClient) -> None:
    for method in ("put", "patch"):
        res = getattr(client, method)("/groups/1/expenses/1", json={}, headers=as_user("alice"))
        assert res.status_code == 405
        assert res.json()["error"]["code"] == "method_not_allowed"
