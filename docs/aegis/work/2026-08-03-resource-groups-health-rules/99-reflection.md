# Reflection

- Repair track: authentication secret reuse is validated and persisted by the same invariant, `existing.auth_type == incoming.auth_type`; switching Basic/Bearer now requires a new secret. Explicitly supplied health rules are always validated, including falsey JSON objects.
- Retirement track: legacy `user_services` and legacy single-probe service columns are retained only for data migration and SQLite compatibility, and are excluded from runtime authorization and monitoring.
- Architecture review: resource-group authorization remains the single runtime permission source; the health-rule module remains the single validation and evaluation source.
- Complexity: no maintained file crossed 800 lines; the largest touched backend owner is 292 lines. No new fallback, adapter, or duplicate rule owner was introduced.
- Residual risk: dependency-backed API tests, exact frontend toolchain build, and an actual old-database migration still require an installed runtime environment.
