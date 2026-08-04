# Intent

## Requested Outcome

交付可主动注册、管理员审批、独立密钥认证、本地自治监测和多 ABI 二进制发布的 Linux Agent，同时保留未切换主机的 SSH 模式。

## Scope

- 中心 Agent 模型、迁移、协议、审批、同步、报告与命令。
- Agent Python/PyInstaller/systemd 实现。
- Agent 管理前端、服务启动用户与异步命令状态。
- x86_64/ARM64、glibc 2.17/2.28 和 Ubuntu/Debian/CentOS/Rocky 验证。

## Non-Goals

- Windows、macOS、Alpine/musl、WebSocket、中心入站连接、Agent 自动升级和多中心高可用。

## Baseline Read Set

- `docs/aegis/specs/2026-08-04-agent-design.md`
- `docs/aegis/plans/2026-08-04-agent.md`
- `docs/aegis/specs/2026-08-03-service-monitor-design.md`
- `docs/aegis/specs/2026-08-03-multi-feishu-alerts.md`

## Baseline Usage

- Required refs: all refs above.
- Acknowledged before execution: all refs above.
- Missing refs: none.
- Decision: continue.

## Impact Statement

- Persistence: new Agent/command/report tables; hosts table compatibility migration.
- Security: new per-Agent credentials and irreversible SSH field clearing on explicit switch.
- Runtime: strict SSH/Agent single execution mode.
- Distribution: four Linux binary artifacts and systemd packaging.

