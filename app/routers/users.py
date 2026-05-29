from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin, require_super
from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_super)):
    return db.query(User).order_by(User.last_name).all()


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/{user_id}/role")
def set_role(user_id: int, role: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    try:
        target.role = UserRole(role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {role}")
    db.commit()
    return {"ok": True}


@router.put("/{user_id}/deactivate", status_code=204)
def deactivate_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    target.is_active = False
    db.commit()
