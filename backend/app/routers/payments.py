from fastapi import APIRouter, status

from app import repositories as repo
from app import services
from app.deps import CurrentUser, DbSession, MemberGroup
from app.models import Payment
from app.schemas import PaymentCreate, PaymentOut

router = APIRouter(tags=["payments"])


def to_payment_out(payment: Payment) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        group_id=payment.group_id,
        from_user=payment.from_user.username,
        to_user=payment.to_user.username,
        amount=payment.amount,
        created_by=payment.created_by.username,
        created_at=payment.created_at,
    )


@router.post(
    "/groups/{group_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: PaymentCreate, db: DbSession, user: CurrentUser, group: MemberGroup
) -> PaymentOut:
    payment = services.record_payment(
        db, group, user, payload.from_user, payload.to_user, payload.amount
    )
    return to_payment_out(payment)


@router.get("/groups/{group_id}/payments", response_model=list[PaymentOut])
def list_payments(db: DbSession, group: MemberGroup) -> list[PaymentOut]:
    return [to_payment_out(p) for p in repo.list_payments(db, group.id)]
