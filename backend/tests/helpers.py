def equal_expense(
    amount: str, members: list[str], paid_by: str = "alice", description: str = "Test expense"
) -> dict:
    return {
        "description": description,
        "paid_by": paid_by,
        "amount": amount,
        "split": {"type": "equal", "members": members},
    }


def exact_expense(amount: str, shares: dict[str, str], paid_by: str = "alice") -> dict:
    return {
        "description": "Test expense",
        "paid_by": paid_by,
        "amount": amount,
        "split": {"type": "exact", "shares": shares},
    }


def as_user(user: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"X-User": user}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def balances_of(response_json: dict) -> dict[str, str]:
    return {b["user"]: b["balance"] for b in response_json["balances"]}
