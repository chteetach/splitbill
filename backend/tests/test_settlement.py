from decimal import Decimal

from fastapi.testclient import TestClient

from app.services import settle_up
from tests.helpers import as_user, balances_of, equal_expense


def d(value: str) -> Decimal:
    return Decimal(value)


def test_settle_up_matches_the_brief_example(client: TestClient) -> None:
    client.post(
        "/groups/1/expenses",
        json=equal_expense("1000.00", ["alice", "bob", "carol"]),
        headers=as_user("alice"),
    )
    res = client.get("/groups/1/settle-up", headers=as_user("bob"))
    assert res.status_code == 200
    assert res.json()["payments"] == [
        {"from_user": "bob", "to_user": "alice", "amount": "333.33"},
        {"from_user": "carol", "to_user": "alice", "amount": "333.33"},
    ]


def test_settle_up_is_empty_when_everyone_is_even(client: TestClient) -> None:
    assert client.get("/groups/2/settle-up", headers=as_user("dan")).json()["payments"] == []


def test_settle_up_brings_every_balance_to_zero() -> None:
    balances = [("a", d("50.00")), ("b", d("30.00")), ("c", d("-45.00")), ("d", d("-35.00"))]
    payments = settle_up(balances)
    net = dict(balances)
    for payer, payee, amount in payments:
        net[payer] += amount
        net[payee] -= amount
    assert all(v == 0 for v in net.values())
    assert len(payments) <= len(balances) - 1


def test_settle_up_uses_one_payment_per_matching_pair() -> None:
    balances = [("a", d("10.00")), ("b", d("-10.00")), ("c", d("25.00")), ("d", d("-25.00"))]
    assert settle_up(balances) == [("d", "c", d("25.00")), ("b", "a", d("10.00"))]


def test_repayment_updates_balances(client: TestClient) -> None:
    client.post(
        "/groups/1/expenses",
        json=equal_expense("1000.00", ["alice", "bob", "carol"]),
        headers=as_user("alice"),
    )
    res = client.post(
        "/groups/1/payments",
        json={"from_user": "bob", "to_user": "alice", "amount": "333.33"},
        headers=as_user("bob"),
    )
    assert res.status_code == 201, res.text
    assert res.json()["amount"] == "333.33"

    balances = balances_of(client.get("/groups/1/balances", headers=as_user("alice")).json())
    assert balances == {"alice": "333.33", "bob": "0.00", "carol": "-333.33"}
    assert client.get("/groups/1/settle-up", headers=as_user("alice")).json()["payments"] == [
        {"from_user": "carol", "to_user": "alice", "amount": "333.33"}
    ]
    listed = client.get("/groups/1/payments", headers=as_user("carol")).json()
    assert [(p["from_user"], p["to_user"]) for p in listed] == [("bob", "alice")]


def test_repayment_validation(client: TestClient) -> None:
    def pay(body: dict, user: str = "bob", group: int = 1) -> tuple[int, str]:
        res = client.post(f"/groups/{group}/payments", json=body, headers=as_user(user))
        return res.status_code, res.json()["error"]["code"]

    assert pay({"from_user": "bob", "to_user": "bob", "amount": "1.00"}) == (422, "same_user")
    assert pay({"from_user": "bob", "to_user": "dan", "amount": "1.00"}) == (
        422,
        "not_group_member",
    )
    assert pay({"from_user": "bob", "to_user": "alice", "amount": "1.001"}) == (
        422,
        "validation_error",
    )
    assert pay({"from_user": "bob", "to_user": "dan", "amount": "1.00"}, user="alice", group=2) == (
        404,
        "group_not_found",
    )
