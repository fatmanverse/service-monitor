import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from .database import Database
from .models import Host, Service
from .monitoring import MonitoringService


logger = logging.getLogger(__name__)


class MonitorScheduler:
    def __init__(self, database: Database, monitoring: MonitoringService, workers: int = 200):
        self.database = database
        self.monitoring = monitoring
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="monitor")

    def start(self) -> None:
        self.scheduler.add_job(
            self.run_due_checks,
            "interval",
            seconds=15,
            id="monitor-due-checks",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.executor.shutdown(wait=False)

    def run_due_checks(self) -> None:
        now = datetime.utcnow()
        with self.database.session_factory() as db:
            host_ids = db.scalars(
                select(Host.id).where(Host.enabled.is_(True), Host.next_check_at <= now).limit(200)
            ).all()
            service_ids = db.scalars(
                select(Service.id).where(Service.enabled.is_(True), Service.next_check_at <= now).limit(1000)
            ).all()
        futures = [self.executor.submit(self._check_host, host_id) for host_id in host_ids]
        futures.extend(self.executor.submit(self._check_service, service_id) for service_id in service_ids)
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                logger.exception("Scheduled monitor task failed")

    def _check_host(self, host_id: int) -> None:
        with self.database.session_factory() as db:
            host = db.get(Host, host_id)
            if host and host.enabled:
                self.monitoring.check_host(db, host)

    def _check_service(self, service_id: int) -> None:
        with self.database.session_factory() as db:
            service = db.scalar(
                        select(Service)
                        .options(
                            joinedload(Service.host),
                            selectinload(Service.probes),
                            selectinload(Service.alert_configs),
                        )
                .where(Service.id == service_id)
            )
            if service and service.enabled:
                self.monitoring.check_service(db, service)
