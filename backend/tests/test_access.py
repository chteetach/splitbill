import pytest
from fastapi.testclient import TestClient

from tests.helpers import as_user, equal_expense


def test_groups_list_only_contains_the_users_groups(client: TestClient) -> None:
    def names(user: str) -> list[str]:
        return [g["name"] for g in client.get("/groups", headers=as_user(user)).json()]

    assert names("alice") == ["Chiang Mai trip"]
    assert names("bob") == ["Chiang Mai trip", "Office lunch"]
    assert names("dan") == ["Office lunch"]


def test_group_detail_lists_members(client: TestClient) -> None:
    res = client.get("/groups/1", headers=as_user("carol"))
    assert res.status_code == 200
    assert res.json() == {"id": 1, "name": "Chiang Mai trip", "members": ["alice", "bob", "carol"]}


@pytest.mark.parametrize("path", ["/groups/2", "/groups/2/expenses", "/groups/2/balances"])
def test_alice_cannot_read_group_2(client: TestClient, path: str) -> None:
    res = client.get(path, headers=as_user("alice"))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "group_not_found"


def test_alice_cannot_write_group_2(client: TestClient) -> None:
    res = client.post(
        "/groups/2/expenses",
        json=equal_expense("50.00", ["bob", "dan"], paid_by="bob"),
        headers=as_user("alice"),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "group_not_found"
    assert client.get("/groups/2/expenses", headers=as_user("bob")).json() == []


def test_alice_cannot_delete_in_group_2(client: TestClient) -> None:
    created = client.post(
        "/groups/2/expenses",
        json=equal_expense("50.00", ["bob", "dan"], paid_by="bob"),
        headers=as_user("bob"),
    ).json()
    res = client.delete(f"/groups/2/expenses/{created['id']}", headers=as_user("alice"))
    assert res.status_code == 404
    assert len(client.get("/groups/2/expenses", headers=as_user("bob")).json()) == 1


def test_non_member_and_missing_group_are_indistinguishable(client: TestClient) -> None:
    hidden = client.get("/groups/2", headers=as_user("alice"))
    missing = client.get("/groups/999", headers=as_user("alice"))
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


def test_expense_ids_are_scoped_to_the_group(client: TestClient) -> None:
    created = client.post(
        "/groups/2/expenses",
        json=equal_expense("50.00", ["bob", "dan"], paid_by="bob"),
        headers=as_user("bob"),
    ).json()
    # bob is in group 1 too, but the expense belongs to group 2.
    res = client.delete(f"/groups/1/expenses/{created['id']}", headers=as_user("bob"))
    assert res.status_code == 404


def test_missing_or_unknown_user_is_unauthenticated(client: TestClient) -> None:
    assert client.get("/groups").status_code == 401
    res = client.get("/groups", headers=as_user("mallory"))
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unknown_user"
