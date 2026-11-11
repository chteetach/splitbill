from fastapi import APIRouter

from app import repositories as repo
from app import services
from app.deps import CurrentUser, DbSession, MemberGroup
from app.schemas import BalanceOut, BalancesOut, GroupOut, GroupSummaryOut

router = APIRouter(tags=["groups"])


@router.get("/groups", response_model=list[GroupSummaryOut])
def list_groups(db: DbSession, user: CurrentUser) -> list[GroupSummaryOut]:
    return [GroupSummaryOut(id=g.id, name=g.name) for g in repo.list_groups_for_user(db, user.id)]


@router.get("/groups/{group_id}", response_model=GroupOut)
def get_group(group: MemberGroup) -> GroupOut:
    return GroupOut(id=group.id, name=group.name, members=[m.username for m in group.members])


@router.get("/groups/{group_id}/balances", response_model=BalancesOut)
def get_balances(db: DbSession, group: MemberGroup) -> BalancesOut:
    return BalancesOut(
        group_id=group.id,
        balances=[
            BalanceOut(user=name, balance=b) for name, b in services.group_balances(db, group)
        ],
    )
