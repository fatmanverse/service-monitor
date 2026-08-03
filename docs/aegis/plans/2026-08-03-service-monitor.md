# 服务监控实施计划

## Goal

按已确认规格交付 React + FastAPI + SQLite 单机服务监控系统。

## Architecture

API、领域监测服务和调度器分层；手动与定时任务共享监测服务，数据库关系是级联删除和授权过滤的唯一事实来源。

## Tech Stack

Python 3.9、FastAPI、SQLAlchemy、APScheduler、Paramiko、HTTPX、React、TypeScript、Vite。

## Baseline/Authority Refs

- 用户在当前会话确认的部署、SSH、认证、飞书和容量要求。
- `docs/aegis/specs/2026-08-03-service-monitor-design.md`。

## Compatibility Boundary

空仓库无历史兼容边界；首版 API 以 `/api` 为统一前缀。

## Verification

依次执行后端 pytest、前端 TypeScript 检查、前端构建和 API 冒烟测试。

## Tasks

1. 用 API 测试固定认证、权限、最小周期和级联删除行为。
2. 实现数据库、模型、安全、路由和监测领域服务。
3. 实现 APScheduler 到期扫描和应用生命周期。
4. 实现四模块 React 管理端和登录流程。
5. 执行自动验证并审查差异、复杂度与未覆盖风险。

## 2026-08-03 资源组与多探活扩展

1. 新增资源组、用户资源组授权、服务探活项和在线规则模型。
2. 幂等迁移旧服务配置与 `user_services` 授权，保留旧表和旧列作为迁移备份。
3. 删除运行时服务直授权路径，权限查询统一由资源组推导。
4. 服务探活并发执行全部探活项，并由递归规则树计算在线状态。
5. 前端增加资源组页面，用户授权改为资源组，服务配置改为探活项与规则编辑器。

## Risks

- SQLite 写并发有限，因此调度任务串行执行并缩短事务持有时间。
- SSH 与外部 HTTP 的真实联通只能在用户目标网络中验证，自动测试覆盖其输入、状态转换和权限边界。
