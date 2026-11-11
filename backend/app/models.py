from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# NUMERIC(12,2): up to 9,999,999,999.99 THB, stored exactly.
Money = Numeric(12, 2, asdecimal=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    members: Mapped[list[User]] = relationship(
        secondary="group_members", order_by="User.username", lazy="selectin"
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint("split_type IN ('equal', 'exact')", name="ck_expenses_split_type"),
        # Scopes Idempotency-Key per group; NULL keys never conflict.
        UniqueConstraint("group_id", "idempotency_key", name="uq_expenses_group_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    split_type: Mapped[str] = mapped_column(String(10))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    # SHA-256 of the canonical request, used to detect a key reused for a different request.
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))

    paid_by: Mapped[User] = relationship(foreign_keys=[paid_by_id], lazy="joined")
    shares: Mapped[list["ExpenseShare"]] = relationship(
        order_by="ExpenseShare.position", lazy="selectin"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_expense_shares_amount_nonneg"),)

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    # Order the members were listed in the request (drives remainder allocation).
    position: Mapped[int] = mapped_column(Integer)

    user: Mapped[User] = relationship(lazy="joined")
