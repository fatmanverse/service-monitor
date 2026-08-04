import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload, selectinload

from .database import Database
from .models import Agent, Host, Service
from .monitoring import MonitoringService, ProbeResult


logger = logging.getLogger(__name__)


class MonitorScheduler:
    def __init__(
        self,
        database: Database,
        monitoring: MonitoringService,
        workers: int = 200,
        agent_offline_seconds: int = 90,
    ):
        self.database = database
        self.monitoring = monitoring
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="monitor")
        self.agent_offline_seconds = agent_offline_seconds

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
        self._mark_offline_agents(now)
        with self.database.session_factory() as db:
            host_ids = db.scalars(
                select(Host.id)
                .where(
                    Host.enabled.is_(True),
                    Host.execution_mode == "ssh",
                    Host.next_check_at <= now,
                )
                .limit(200)
            ).all()
        self._wait_for(
            [self.executor.submit(self._check_host, host_id) for host_id in host_ids]
        )

        with self.database.session_factory() as db:
            service_ids = db.scalars(
                select(Service.id)
                .join(Host, Host.id == Service.host_id)
                .where(
                    Service.enabled.is_(True),
                    Service.next_check_at <= now,
                    Host.execution_mode == "ssh",
                    Host.status != "offline",
                )
                .limit(1000)
            ).all()
        self._wait_for(
            [self.executor.submit(self._check_service, service_id) for service_id in service_ids]
        )

    @staticmethod
    def _wait_for(futures) -> None:
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

    def _mark_offline_agents(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.agent_offline_seconds)
        with self.database.session_factory() as db:
            agents = db.scalars(
                select(Agent)
                .join(Host, Host.id == Agent.host_id)
                .options(
                    joinedload(Agent.host).selectinload(Host.alert_configs)
                )
                .where(
                    Agent.status == "approved",
                    Host.status != "offline",
                    or_(
                        Agent.last_seen_at < cutoff,
                        and_(
                            Agent.last_seen_at.is_(None),
                            Agent.approved_at < cutoff,
                        ),
                    ),
                )
            ).unique().all()
            alerts = []
            for agent in agents:
                previous_status = agent.host.status
                agent.host.status = "offline"
                agent.host.last_checked_at = now
                agent.host.last_error = "Agent 心跳超时"
                active = [config for config in agent.host.alert_configs if config.enabled]
                if active:
                    alerts.append((active, agent.host, previous_status))
            db.commit()
            for configs, host, previous_status in alerts:
                self.monitoring._send_host_status_alert(
                    configs,
                    host,
                    previous_status,
                    ProbeResult(False, "Agent 心跳超时"),
                )

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
