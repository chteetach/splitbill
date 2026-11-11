from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app import repositories as repo
from app import services
from app.deps import CurrentUser, DbSession, MemberGroup
from app.errors import ValidationFailed
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseOut, ShareOut

router = APIRouter(tags=["expenses"])


def to_expense_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        description=expense.description,
        paid_by=expense.paid_by.username,
        amount=expense.amount,
        split_type=expense.split_type,
        shares=[ShareOut(user=s.user.username, amount=s.amount) for s in expense.shares],
        created_by=expense.created_by.username,
        created_at=expense.created_at,
    )


@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replay of an earlier request with the same Idempotency-Key"}},
)
def create_expense(
    payload: ExpenseCreate,
    response: Response,
    db: DbSession,
    user: CurrentUser,
    group: MemberGroup,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> ExpenseOut:
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not 1 <= len(idempotency_key) <= 255:
            raise ValidationFailed("Idempotency-Key must be 1 to 255 characters")
    result = services.create_expense(db, group, user, payload, idempotency_key)
    if not result.created:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    return to_expense_out(result.expense)


@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseOut])
def list_expenses(db: DbSession, group: MemberGroup) -> list[ExpenseOut]:
    return [to_expense_out(e) for e in repo.list_active_expenses(db, group.id)]


@router.delete("/groups/{group_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: DbSession, user: CurrentUser, group: MemberGroup) -> None:
    services.delete_expense(db, group, user, expense_id)
