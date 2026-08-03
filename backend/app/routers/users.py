from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import get_db, require_admin
from ..models import ResourceGroup, User, UserResourceGroup
from ..schemas import ResourceGroupGrantInput, ResourceGroupOutput, UserCreate, UserSummary, UserUpdate
from ..security import hash_password
from .resource_groups import group_output


router = APIRouter(prefix="/users", tags=["用户"])


@router.get("", response_model=List[UserSummary])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    user = User(username=payload.username, password_hash=hash_password(payload.password), is_admin=payload.is_admin, is_active=payload.is_active)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在")
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserSummary)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("password", None)
    if user.id == admin.id and values.get("is_active") is False:
        raise HTTPException(status_code=400, detail="不能停用当前登录用户")
    if user.id == admin.id and values.get("is_admin") is False:
        raise HTTPException(status_code=400, detail="不能取消当前登录用户的管理员权限")
    for key, value in values.items():
        setattr(user, key, value)
    if password:
        user.password_hash = hash_password(password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_id}/resource-groups", response_model=List[ResourceGroupOutput])
def get_user_groups(user_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    groups = db.scalars(select(ResourceGroup).join(UserResourceGroup).where(UserResourceGroup.user_id == user_id).order_by(ResourceGroup.name)).all()
    return [group_output(db, group) for group in groups]


@router.put("/{user_id}/resource-groups", response_model=List[ResourceGroupOutput])
def set_user_groups(
    user_id: int,
    payload: ResourceGroupGrantInput,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    group_ids = sorted(set(payload.resource_group_ids))
    groups = db.scalars(select(ResourceGroup).where(ResourceGroup.id.in_(group_ids))).all() if group_ids else []
    if len(groups) != len(group_ids):
        raise HTTPException(status_code=400, detail="包含不存在的资源组")
    db.execute(delete(UserResourceGroup).where(UserResourceGroup.user_id == user_id))
    db.add_all([UserResourceGroup(user_id=user_id, resource_group_id=group_id) for group_id in group_ids])
    db.commit()
    return [group_output(db, group) for group in sorted(groups, key=lambda item: item.name)]
