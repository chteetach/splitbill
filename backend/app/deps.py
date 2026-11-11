"""Request dependencies: who is calling, and which group they may access."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app import repositories as repo
from app.db import get_db
from app.errors import NotFound, Unauthenticated
from app.models import Group, User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, x_user: Annotated[str | None, Header()] = None) -> User:
    if not x_user or not x_user.strip():
        raise Unauthenticated("The X-User header is required")
    user = repo.get_user_by_username(db, x_user.strip())
    if user is None:
        raise Unauthenticated(f"Unknown user: {x_user.strip()}", code="unknown_user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_member_group(group_id: int, db: DbSession, user: CurrentUser) -> Group:
    """Load the group, answering 404 both when it does not exist and when the caller is not a
    member, so non-members cannot discover which group ids exist (see README)."""
    group = repo.get_group(db, group_id)
    if group is None or not repo.is_member(db, group_id, user.id):
        raise NotFound("Group not found", code="group_not_found")
    return group


MemberGroup = Annotated[Group, Depends(get_member_group)]
