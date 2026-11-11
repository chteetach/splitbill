from fastapi import APIRouter

from app import repositories as repo
from app.deps import DbSession
from app.schemas import UserOut

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: DbSession) -> list[UserOut]:
    """List users so a client can offer a user picker (there is no real authentication)."""
    return [UserOut(username=u.username) for u in repo.list_users(db)]
