# Multi-Alert Reflection

- Canonical owner: `AlertConfig` plus `ServiceAlertConfig` now own all runtime alert routing.
- Compatibility: the old single-row `alert_configs` record and `Service.alert_enabled` column are retained only for one-time migration and are not read by monitoring.
- Failure handling: delivery attempts run for every enabled associated robot; failures are aggregated rather than short-circuiting later targets.
- Residual risk: API integration tests and a real old SQLite migration still require the installed SQLAlchemy/FastAPI environment.
