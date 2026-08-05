import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from .models import ProbeLog


PROBE_LOG_RETENTION_DAYS = 30


@dataclass
class ProbeLogPage:
    items: List[ProbeLog]
    next_cursor: Optional[str]


def probe_log_cutoff(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.utcnow()) - timedelta(days=PROBE_LOG_RETENTION_DAYS)


def _encode_cursor(log: ProbeLog) -> str:
    payload = json.dumps(
        {"checked_at": log.checked_at.isoformat(), "id": log.id},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        return datetime.fromisoformat(payload["checked_at"]), int(payload["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("无效的历史记录游标") from exc


def list_probe_logs(
    db: Session,
    service_id: int,
    limit: int,
    cursor: Optional[str] = None,
    now: Optional[datetime] = None,
) -> ProbeLogPage:
    query = select(ProbeLog).where(
        ProbeLog.service_id == service_id,
        ProbeLog.checked_at >= probe_log_cutoff(now),
    )
    if cursor:
        checked_at, log_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                ProbeLog.checked_at < checked_at,
                and_(ProbeLog.checked_at == checked_at, ProbeLog.id < log_id),
            )
        )
    logs = db.scalars(
        query.order_by(ProbeLog.checked_at.desc(), ProbeLog.id.desc()).limit(limit + 1)
    ).all()
    has_more = len(logs) > limit
    items = logs[:limit]
    next_cursor = _encode_cursor(items[-1]) if has_more and items else None
    return ProbeLogPage(items=items, next_cursor=next_cursor)


def purge_expired_probe_logs(
    db: Session,
    now: Optional[datetime] = None,
) -> int:
    result = db.execute(
        delete(ProbeLog).where(ProbeLog.checked_at < probe_log_cutoff(now))
    )
    db.commit()
    return result.rowcount or 0
