from typing import List

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AlertConfig


def resolve_alert_configs(db: Session, alert_config_ids: List[int]) -> List[AlertConfig]:
    ids = sorted(set(alert_config_ids))
    configs = db.scalars(select(AlertConfig).where(AlertConfig.id.in_(ids))).all() if ids else []
    if len(configs) != len(ids):
        raise HTTPException(status_code=422, detail="包含不存在的告警配置")
    return sorted(configs, key=lambda config: config.name)
