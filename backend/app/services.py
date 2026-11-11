"""Business rules: share allocation, membership, idempotency, deletion and balances."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app import repositories as repo
from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.models import Expense, Group, User
from app.money import ZERO, allocate_equal
from app.schemas import EqualSplitIn, ExactSplitIn, ExpenseCreate


@dataclass(frozen=True)
class CreateResult:
    expense: Expense
    created: bool  # False when an earlier request with the same Idempotency-Key is replayed


def compute_shares(
    amount: Decimal, split: EqualSplitIn | ExactSplitIn
) -> list[tuple[str, Decimal]]:
    """Return (username, share) pairs in the order the members were listed.

    Guarantees the shares sum to `amount` exactly, or raises ValidationFailed.
    """
    if isinstance(split, EqualSplitIn):
        duplicates = sorted({m for m in split.members if split.members.count(m) > 1})
        if duplicates:
            raise ValidationFailed(
                f"Members are listed more than once: {', '.join(duplicates)}",
                code="duplicate_members",
            )
        return list(zip(split.members, allocate_equal(amount, len(split.members)), strict=True))

    shares = list(split.shares.items())
    total = sum((share for _, share in shares), ZERO)
    if total != amount:
        raise ValidationFailed(
            f"The shares add up to {total} but the amount is {amount}",
            code="shares_mismatch",
            details={"amount": str(amount), "shares_total": str(total)},
        )
    return shares


def _fingerprint(user: User, payload: ExpenseCreate) -> str:
    canonical = json.dumps(
        {"user": user.username, "request": payload.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_expense(
    db: Session,
    group: Group,
    user: User,
    payload: ExpenseCreate,
    idempotency_key: str | None,
) -> CreateResult:
    fingerprint = _fingerprint(user, payload) if idempotency_key else None
    if idempotency_key:
        # Fast path for a plain retry; the INSERT below still handles the concurrent case.
        existing = repo.get_expense_by_idempotency_key(db, group.id, idempotency_key)
        if existing:
            return _replay(existing, fingerprint)

    members = {m.username: m for m in group.members}
    shares = compute_shares(payload.amount, payload.split)
    outsiders = [name for name in [payload.paid_by, *(n for n, _ in shares)] if name not in members]
    if outsiders:
        unique = list(dict.fromkeys(outsiders))
        raise ValidationFailed(
            f"Not a member of this group: {', '.join(unique)}",
            code="not_group_member",
            details={"users": unique},
        )

    expense_id = repo.insert_expense_if_new(
        db,
        {
            "group_id": group.id,
            "description": payload.description,
            "paid_by_id": members[payload.paid_by].id,
            "amount": payload.amount,
            "split_type": payload.split.type,
            "created_by_id": user.id,
            "idempotency_key": idempotency_key,
            "request_fingerprint": fingerprint,
        },
    )
    if expense_id is None:
        # A concurrent request with the same key committed first; return its expense.
        db.rollback()
        existing = repo.get_expense_by_idempotency_key(db, group.id, idempotency_key or "")
        if existing is None:  # pragma: no cover - only if that expense was hard-deleted
            raise Conflict("Idempotency-Key conflict, please retry", code="idempotency_conflict")
        return _replay(existing, fingerprint)

    repo.add_shares(db, expense_id, [(members[name].id, share) for name, share in shares])
    db.commit()
    expense = repo.get_expense(db, group.id, expense_id)
    assert expense is not None
    return CreateResult(expense=expense, created=True)


def _replay(existing: Expense, fingerprint: str | None) -> CreateResult:
    if existing.request_fingerprint != fingerprint:
        raise Conflict(
            "This Idempotency-Key was already used for a different request",
            code="idempotency_key_reused",
        )
    return CreateResult(expense=existing, created=False)


def delete_expense(db: Session, group: Group, user: User, expense_id: int) -> None:
    expense = repo.get_expense(db, group.id, expense_id)
    if expense is None or expense.deleted_at is not None:
        raise NotFound("Expense not found", code="expense_not_found")
    if expense.paid_by_id != user.id:
        raise Forbidden("Only the payer can delete this expense", code="not_payer")
    repo.mark_expense_deleted(db, expense, datetime.now(UTC))
    db.commit()


def group_balances(db: Session, group: Group) -> list[tuple[str, Decimal]]:
    """Net balance per member: paid minus owed. Positive means the member is owed money."""
    paid = repo.paid_totals(db, group.id)
    owed = repo.share_totals(db, group.id)
    balances = [(m.username, paid.get(m.id, ZERO) - owed.get(m.id, ZERO)) for m in group.members]
    # Every expense's shares sum to its amount, so this can only fail if the data is corrupt.
    if sum((b for _, b in balances), ZERO) != ZERO:
        raise RuntimeError(f"Balances for group {group.id} do not sum to zero")
    return balances
