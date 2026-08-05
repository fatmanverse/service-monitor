# 服务控制台生命周期工作意图

## Requested Outcome

完成已批准的服务详情、30 天历史、监控启停、手动探活/拉起、改密、Agent TLS、根目录 `start.sh`、界面优化和死代码清理。

## Scope And Non-Goals

- Scope: `docs/aegis/plans/2026-08-05-service-console-lifecycle.md` 中的 7 个任务。
- Non-goals: 历史导出、SSO、Agent 明文协议、`start.sh` 守护运行、新 UI 框架。
- Stop: 全部验收证据完成，或发现需要超出已批准规格的契约变更。

## BaselineReadSetHint

- `docs/aegis/specs/2026-08-05-service-console-lifecycle-design.md`
- `docs/aegis/plans/2026-08-05-service-console-lifecycle.md`
- `docs/aegis/specs/2026-08-03-service-monitor-design.md`
- `docs/aegis/specs/2026-08-04-agent-design.md`
- `docs/aegis/adr/2026-08-04-agent-execution-and-identity.md`

## BaselineUsageDraft

- Required baseline refs: 上述 5 个文件。
- Acknowledged before plan refs: 全部。
- Cited in plan refs: 全部。
- Missing refs: 无。
- Decision: continue

## ImpactStatementDraft

- Backend: service/log/auth/TLS/scheduler/config/packaging owners.
- Frontend: hash route/service detail/account/agents/layout/styles.
- Distribution: GitHub Actions server bundle and direct-run script.
- Compatibility: preserve old service enabled values, old data, API URLs, SSH/Agent execution boundary and strict TLS.

## Execution Readiness View

- Intent Lock: 只实施已批准规格。
- Scope Fence: 详情、历史、启停、探活/拉起、改密、TLS、`start.sh`、UI/清理。
- Baseline Lock: 不更换数据模型或 Agent 协议 owner。
- Compatibility Boundary: 旧数据与 URL 保留，旧 enabled 值不改。
- Retirement Boundary: 移除旧混合启动/结果路径和静态证明的死代码。
- Test Obligations: 定向测试 -> type/build -> packaging/shell -> full regressions.
- Advisory Boundary: method-pack execution guidance only; not completion authority.

