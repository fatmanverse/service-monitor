from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import get_current_user, get_db
from ..models import User
from ..schemas import CurrentUserOutput, LoginInput, TokenOutput
from ..security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenOutput)
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenOutput(access_token=create_access_token(user.id, request.app.state.settings))


@router.get("/me", response_model=CurrentUserOutput)
def me(current_user: User = Depends(get_current_user)):
    return current_user

