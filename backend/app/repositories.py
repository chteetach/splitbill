"""Data access. Functions here run queries and nothing else: no HTTP, no business rules."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseShare, Group, GroupMember, Payment, User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def list_users(db: Session) -> Sequence[User]:
    return db.scalars(select(User).order_by(User.username)).all()


def get_group(db: Session, group_id: int) -> Group | None:
    return db.get(Group, group_id)


def list_groups_for_user(db: Session, user_id: int) -> Sequence[Group]:
    return db.scalars(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user_id)
        .order_by(Group.id)
    ).all()


def is_member(db: Session, group_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
        )
        > 0
    )


def insert_expense_if_new(db: Session, values: dict) -> int | None:
    """Insert an expense row unless one with the same (group_id, idempotency_key) exists.

    Uses INSERT ... ON CONFLICT DO NOTHING, so two concurrent requests with the same key
    are serialised by the unique index: the second blocks until the first commits and then
    inserts nothing. Returns the new id, or None when the key was already taken.
    """
    stmt = (
        insert(Expense)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_expenses_group_idempotency_key")
        .returning(Expense.id)
    )
    return db.scalar(stmt)


def add_shares(db: Session, expense_id: int, shares: list[tuple[int, Decimal]]) -> None:
    db.add_all(
        ExpenseShare(expense_id=expense_id, user_id=user_id, amount=amount, position=i)
        for i, (user_id, amount) in enumerate(shares)
    )


def get_expense(db: Session, group_id: int, expense_id: int) -> Expense | None:
    return db.scalar(select(Expense).where(Expense.group_id == group_id, Expense.id == expense_id))


def get_expense_by_idempotency_key(db: Session, group_id: int, key: str) -> Expense | None:
    return db.scalar(
        select(Expense).where(Expense.group_id == group_id, Expense.idempotency_key == key)
    )


def list_active_expenses(db: Session, group_id: int) -> Sequence[Expense]:
    return db.scalars(
        select(Expense)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    ).all()


def mark_expense_deleted(db: Session, expense: Expense, when: datetime) -> None:
    expense.deleted_at = when


def paid_totals(db: Session, group_id: int) -> dict[int, Decimal]:
    """Sum of active expenses paid by each user."""
    rows = db.execute(
        select(Expense.paid_by_id, func.sum(Expense.amount))
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by_id)
    ).all()
    return {user_id: total for user_id, total in rows}


def share_totals(db: Session, group_id: int) -> dict[int, Decimal]:
    """Sum of each user's shares across active expenses."""
    rows = db.execute(
        select(ExpenseShare.user_id, func.sum(ExpenseShare.amount))
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(ExpenseShare.user_id)
    ).all()
    return {user_id: total for user_id, total in rows}


def add_payment(db: Session, payment: Payment) -> Payment:
    db.add(payment)
    db.flush()
    return payment


def list_payments(db: Session, group_id: int) -> Sequence[Payment]:
    return db.scalars(
        select(Payment)
        .where(Payment.group_id == group_id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    ).all()


def payment_totals(db: Session, group_id: int) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(total sent by each user, total received by each user) in repayments."""
    sent = db.execute(
        select(Payment.from_user_id, func.sum(Payment.amount))
        .where(Payment.group_id == group_id)
        .group_by(Payment.from_user_id)
    ).all()
    received = db.execute(
        select(Payment.to_user_id, func.sum(Payment.amount))
        .where(Payment.group_id == group_id)
        .group_by(Payment.to_user_id)
    ).all()
    return dict(sent), dict(received)
