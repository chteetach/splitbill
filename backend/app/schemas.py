"""Request/response models. These validate shape and format only; business rules that need
the database (membership, sums against the amount) live in app.services."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
)

from app.money import format_money, parse_amount

# Input amount: must arrive as a string, positive, at most 2 decimal places.
MoneyIn = Annotated[Decimal, BeforeValidator(parse_amount)]
# Output amount: always serialised as a "0.00"-style string.
MoneyOut = Annotated[Decimal, PlainSerializer(format_money, return_type=str)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EqualSplitIn(StrictModel):
    type: Literal["equal"]
    members: list[Username] = Field(min_length=1)


class ExactSplitIn(StrictModel):
    type: Literal["exact"]
    shares: dict[Username, MoneyIn] = Field(min_length=1)


SplitIn = Annotated[EqualSplitIn | ExactSplitIn, Field(discriminator="type")]


class ExpenseCreate(StrictModel):
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    paid_by: Username
    amount: MoneyIn
    split: SplitIn


class UserOut(BaseModel):
    username: str


class GroupSummaryOut(BaseModel):
    id: int
    name: str


class GroupOut(GroupSummaryOut):
    members: list[str]


class ShareOut(BaseModel):
    user: str
    amount: MoneyOut


class ExpenseOut(BaseModel):
    id: int
    group_id: int
    description: str
    paid_by: str
    amount: MoneyOut
    split_type: Literal["equal", "exact"]
    shares: list[ShareOut]
    created_by: str
    created_at: datetime


class BalanceOut(BaseModel):
    user: str
    # Positive: the group owes this member. Negative: this member owes the group.
    balance: MoneyOut


class BalancesOut(BaseModel):
    group_id: int
    balances: list[BalanceOut]


class SettlementOut(BaseModel):
    from_user: str
    to_user: str
    amount: MoneyOut


class SettleUpOut(BaseModel):
    group_id: int
    payments: list[SettlementOut]


class PaymentCreate(StrictModel):
    from_user: Username
    to_user: Username
    amount: MoneyIn


class PaymentOut(BaseModel):
    id: int
    group_id: int
    from_user: str
    to_user: str
    amount: MoneyOut
    created_by: str
    created_at: datetime
