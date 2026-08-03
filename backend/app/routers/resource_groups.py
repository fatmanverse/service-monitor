from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..dependencies import get_db, require_admin
from ..models import ResourceGroup, Service, User, UserResourceGroup
from ..schemas import ResourceGroupCreate, ResourceGroupOutput, ResourceGroupUpdate


router = APIRouter(prefix="/resource-groups", tags=["资源组"])


def group_output(db: Session, group: ResourceGroup) -> ResourceGroupOutput:
    service_count = db.scalar(select(func.count(Service.id)).where(Service.resource_group_id == group.id)) or 0
    user_count = db.scalar(
        select(func.count(UserResourceGroup.user_id)).where(UserResourceGroup.resource_group_id == group.id)
    ) or 0
    return ResourceGroupOutput(
        id=group.id,
        name=group.name,
        description=group.description,
        service_count=service_count,
        user_count=user_count,
        created_at=group.created_at,
    )


@router.get("", response_model=List[ResourceGroupOutput])
def list_groups(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return [group_output(db, group) for group in db.scalars(select(ResourceGroup).order_by(ResourceGroup.name)).all()]


@router.post("", response_model=ResourceGroupOutput, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: ResourceGroupCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    group = ResourceGroup(name=payload.name, description=payload.description)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="资源组名称已存在")
    db.refresh(group)
    return group_output(db, group)


@router.put("/{group_id}", response_model=ResourceGroupOutput)
def update_group(
    group_id: int,
    payload: ResourceGroupUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    group = db.get(ResourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="资源组不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="资源组名称已存在")
    db.refresh(group)
    return group_output(db, group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    group = db.get(ResourceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="资源组不存在")
    if db.scalar(select(Service.id).where(Service.resource_group_id == group_id).limit(1)):
        raise HTTPException(status_code=409, detail="资源组仍包含服务，不能删除")
    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
