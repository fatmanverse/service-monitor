# 服务详情、监控生命周期与直接启动实施计划

## Goal

实施已批准的服务详情、30 天历史保留、监控启停、手动探活结果与离线拉起、用户改密、Agent TLS 默认证书、根目录 `start.sh` 和管理界面二次优化。

## Architecture

- 复用 `Service`/`ServiceProbe`/`ProbeLog` 作为配置、状态和历史唯一源。
- 日志保留使用独立后端 owner，API、启动钩子和调度器共用同一截止规则。
- 前端保留哈希路由，将服务列表与详情拆分，共用服务操作和表单边界。
- TLS 证书生成是可重复调用的后端初始化能力；发布 `start.sh` 只编排目录、环境和兼容二进制。

## Tech Stack

- Python 3.9+、FastAPI、SQLAlchemy、APScheduler、cryptography、gRPC、PyInstaller。
- React 19、TypeScript 5.9、Vite 7、Lucide React、现有 CSS token 系统。
- POSIX `sh`、GitHub Actions、manylinux2014/manylinux_2_28。

## Baseline/Authority Refs

- `docs/aegis/specs/2026-08-05-service-console-lifecycle-design.md`
- `docs/aegis/specs/2026-08-03-service-monitor-design.md`
- `docs/aegis/specs/2026-08-04-agent-design.md`
- `docs/aegis/adr/2026-08-04-agent-execution-and-identity.md`
- 本会话中用户对独立详情、30 天物理删除和 `start.sh` 的批准。

## Compatibility Boundary

- 现有服务、探活项、资源组授权、Agent 身份和 30 天内日志保留。
- 已有服务的 `enabled` 值不重写；只改新建默认。
- 保留现有 `/services/{id}/probe`、`/restart` 和 Agent 命令路径，收紧行为不更换 URL。
- `install.sh` 继续负责 systemd 安装；根目录 `start.sh` 不写系统目录。
- Agent 仍使用 TLS gRPC，不改用 FastAPI 传输 Agent 协议。

## TDD Route

- Mode: off
- Decision: skipped
- Strict authority: not applicable
- Test posture: post-change regression
- Reason: 项目未要求严格 TDD；按风险比例在每个结构切片后增加回归测试。
- Verification: 后端定向 pytest、Agent 定向 pytest、前端 typecheck/build、Shell 检查、发布布局与总回归。

## Verification

```sh
timeout 60s backend/.venv/bin/pytest -q backend/tests/test_api.py backend/tests/test_agent_reports.py backend/tests/test_agent_grpc_integration.py backend/tests/test_packaging_layout.py
npm run typecheck --prefix frontend
npm run build --prefix frontend
shellcheck scripts/start.sh backend/packaging/start.sh backend/packaging/install.sh scripts/platform.sh
timeout 60s backend/.venv/bin/pytest -q backend/tests
timeout 60s agent/.venv/bin/pytest -q agent/tests
git diff --check
```

## Planning Checks

### Requirement Ready Check

- Requirement source refs: 已批准 Design Spec 和本会话用户确认。
- Goals and scope refs: Design Spec 的目标、不变量、API 边界与非目标。
- User / scenario refs: 管理员配置与拉起，普通用户查看与手动探活，Agent 节点严格 TLS 连接。
- Requirement item refs: 六项问题、离线后询问拉起、`start.sh`、独立详情和 30 天物理保留。
- Acceptance / verification criteria refs: Design Spec 验收标准。
- Open blocker questions: 无。
- Decision: ready

### Change Necessity

- User-visible need: 现有页面无详情路由、稳定结果、历史视图、自助改密、默认 TLS 和直接启动入口。
- No-change / non-code option: 文档或环境变量无法补齐路由、API 语义和数据保留。
- Why code change is necessary: 必须修改契约、调度、认证、UI 和发布布局。
- Minimum change boundary: 复用现有模型/路由/打包 owner，新增日志保留模块、详情页和发布启动脚本。
- Decision: code-change

### Existence Check

- Proposed new surface: `probe_log_retention.py`、`ServiceDetailPage.tsx`、`backend/packaging/start.sh`。
- Existing owner / reuse candidate: `scheduler.py`、`ServicesPage.tsx`、`scripts/start.sh`。
- Why existing surface is insufficient: 调度器不应所有数据保留规则；列表页已过载；源码启动脚本与发布二进制边界不同。
- Creation proof: 三个新文件分别建立唯一规则所有者、独立 URL 页面和发布运行入口。
- Entropy / retirement impact: 删除列表页旧结果通知/直接启动逻辑和被替代的无引用样式。
- Decision: add-with-proof

### Architecture Integrity Lens

- Invariant: 一个日志源、一个保留规则、一个监控启停语义、一个 Agent TLS 信任链。
- Canonical owner / contract: `ProbeLog`、日志保留模块、`Service.enabled`、Server 实例 CA。
- Responsibility overlap: 必须移除 `/probe` 中的自动拉起与列表页中的“启动”混合语义。
- Higher-level simplification: SSH 和 Agent 手动结果转换为同一前端模型。
- Retirement / falsifier: 如仍存在前端自行截断历史、第二个日志表或探活自动执行启动命令，则架构审查不通过。
- Verdict: proceed

### Plan-Time Complexity Check

- Target files: `ServicesPage.tsx` 当前同时承担列表、表单和操作；`ui.css`/`layout.css`/`features.css` 总计超过 1700 行。
- Existing size / shape signals: 页面和样式已有明显职责压力。
- Owner fit: 列表保留列表/表单，详情和账号使用独立页/组件，新样式使用独立 `service-detail.css`。
- Add-in-place risk: 在 `ServicesPage.tsx` 和现有全局样式继续增长会引入状态耦合和选择器冲突。
- Better file boundary: `ServiceDetailPage.tsx`、`AccountPage.tsx`、`features/services/serviceActions.ts`、`styles/service-detail.css`。
- Recommendation: add owner file

### Plan Pressure Test

- Owner / contract / retirement: 已明确日志、监控、TLS 和发布入口 owner，并要求删除旧混合路径。
- Architecture integrity / higher-level path: 复用现有模型和 API，不新增重复业务实体。
- Verification scope: 覆盖后端、Agent、前端、Shell 和 GitHub Actions 布局。
- Task executability: 任务按后端契约、安全、发布、前端、清理和验收顺序执行。
- Pressure result: proceed

## Execution Readiness View

- Intent Lock: 实施已批准 Design Spec，不扩展历史导出、SSO、守护运行或无 TLS Agent。
- Scope Fence: 仅服务生命周期/详情、历史、改密、TLS、直接启动、UI 优化与死代码删除。
- Baseline Lock: 不破坏现有 Agent/SSH 双执行模式和资源组权限。
- Approved Behavior: 服务卡进详情；30 天物理保留；新服务默认停止；离线后询问拉起；自助改密；实例 CA；根目录 `start.sh`。
- Owner / Contract Constraints: 各业务规则只有一个后端 owner；前端不弥补后端保留/权限缺口。
- Compatibility Boundary: 旧数据和 API URL 保留，旧服务启停值不改。
- Retirement Boundary: 删除列表页旧启动动作、顶部探活结果通知、无引用前端代码和被替代样式。
- Task Batches: 后端服务/历史；认证；TLS/发布；前端路由/详情；全局优化/清理；验收。
- Test Obligations: 每个契约变更有定向回归，最后运行总回归和构建。
- Review Gates: 每个任务后检查 diff、隐式回退、重复规则和权限扩大。
- Drift / Rewind Rules: 如需新数据表、改 Agent 传输协议或变更 30 天语义，停止并返回规格。
- Evidence Required Before Completion: 测试/构建/Shell/布局结果、diff 审查和无未跟踪必要代码。
- Advisory Boundary: method-pack execution guidance only; not GateDecision, PolicySnapshot, or completion authority.

## Tasks

### Task 1: 固定服务生命周期和 30 天历史契约

**Files**

- Create: `backend/app/probe_log_retention.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/services.py`
- Modify: `backend/app/scheduler.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/monitoring.py`
- Modify: `backend/app/agent_reports.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_agent_reports.py`

**Why**

为详情页提供完整、可分页且物理受限的历史，并把监控启停与手动拉起分开。

**Change Necessity**

现有日志 API 固定 100 条且无时间边界，`/probe` 会根据管理员身份触发自动拉起。最小边界是日志 owner、service schema/router、monitoring 返回值和调度调用点。

**Impact/Compatibility**

- `Service.enabled` 模型和创建 schema 默认改为 `false`，不迁移已有行。
- 日志 API 返回分页对象，同步修改唯一前端消费者。
- `/probe` 始终 `allow_restart=False`；`/restart` 保留管理员限制。

**Verification**

```sh
timeout 60s backend/.venv/bin/pytest -q backend/tests/test_api.py backend/tests/test_agent_reports.py
```

**Steps**

1. 在 `probe_log_retention.py` 定义 30 天常量、UTC cutoff、分页查询和批量删除函数。
2. 为日志分页增加 cursor/item schema，为手动结果增加探活项结果 schema。
3. 将监测层的各项结果映射到 API 返回，确保日志仍只写一次。
4. 改造 service logs API 和 `/probe` 拉起语义，启停时更新 `next_check_at`。
5. 在 Server 启动时清理一次，在 APScheduler 注册每日任务，共用同一删除函数。
6. 添加新建默认停止、启停、日志时间边界/游标/物理删除、手动探活不拉起的回归。

### Task 2: 实施用户自助改密和会话失效

**Files**

- Modify: `backend/app/models.py`
- Modify: `backend/app/migrations.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/security.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_api.py`

**Why**

普通用户当前无可访问的改密入口，且成功改密后旧 JWT 必须失效。

**Change Necessity**

管理员用户更新接口不校验旧密码，不能复用为自助路径。最小边界是 auth router/schema 和用户 token version。

**Impact/Compatibility**

为用户增加默认 token version 的幂等迁移，现有用户可继续登录；改密后所有旧 token 失效。

**Verification**

```sh
timeout 60s backend/.venv/bin/pytest -q backend/tests/test_api.py -k password
```

**Steps**

1. 增加 `token_version` 字段和幂等 SQLite 迁移，JWT 签发/解析校验该版本。
2. 增加当前密码、新密码、确认密码 schema 和 `PUT /api/auth/password`。
3. 校验旧密码、新密码差异与确认值，成功后更新哈希并递增 token version。
4. 添加成功、错误旧密码、确认不一致和旧 token 失效测试。

### Task 3: 生成 Server 实例 TLS 证书并提供公共 CA

**Files**

- Create: `backend/app/tls_certificates.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/agent_grpc_server.py`
- Modify: `backend/app/routers/agents.py`
- Modify: `backend/app/main.py`
- Modify: `agent/service_monitor_agent/config.py`
- Modify: `agent/service_monitor_agent/client.py`
- Modify: `backend/tests/test_agent_grpc_integration.py`
- Modify: `backend/tests/test_agent_enrollment.py`
- Modify: `agent/tests/test_client.py`

**Why**

新 Server 目录当前没有默认 Agent 信任链，启用 gRPC 时会因缺失证书失败。

**Change Necessity**

配置文档无法为每个实例创建唯一 CA。最小边界是证书生成 owner、gRPC Server 读取、Agent TLS identity 配置和管理员 CA 下载。

**Impact/Compatibility**

显式配置的证书路径仍优先；仅当使用默认实例目录时生成文件。Agent 继续严格校验 TLS。

**Verification**

```sh
timeout 60s backend/.venv/bin/pytest -q backend/tests/test_agent_grpc_integration.py backend/tests/test_agent_enrollment.py
timeout 60s agent/.venv/bin/pytest -q agent/tests/test_client.py
```

**Steps**

1. 使用 `cryptography.x509` 实现幂等 CA/Server 证书生成，固定 TLS 身份为 `service-monitor-server`。
2. 在配置中增加 CA 文件和 TLS server name，启动时解析显式路径或实例默认路径。
3. 为 Agent channel 配置 gRPC authority override，保持 CA 校验不可关闭。
4. 增加管理员公共 CA 下载接口，只返回证书而非私钥。
5. 测试首次/重复生成、文件权限、正确 CA/identity 连接和错误 CA/identity 拒绝。

### Task 4: 提供发布根目录 `start.sh`

**Files**

- Create: `backend/packaging/start.sh`
- Modify: `scripts/platform.sh`
- Modify: `.github/workflows/server-build.yml`
- Modify: `backend/tests/test_packaging_layout.py`
- Modify: `docs/server-install.md`

**Why**

用户需要在解压目录中无 root、无 systemd 直接启动，并首次获得随机管理员密码。

**Change Necessity**

现有 `scripts/start.sh` 需要 Python 和手工 `.env`，`install.sh` 需要 root。最小边界是发布启动脚本、bundle 组装和布局测试。

**Impact/Compatibility**

不更改 `install.sh` 使用方式。发布包仍按单平台产物打包，`start.sh` 选择同目录的兼容二进制。

**Verification**

```sh
shellcheck backend/packaging/start.sh scripts/platform.sh
timeout 60s backend/.venv/bin/pytest -q backend/tests/test_packaging_layout.py
```

**Steps**

1. 实现平台检测和同目录二进制选择，不兼容时明确退出。
2. 首次创建 `data`/`certs`/`.service-monitor.env`，使用 `umask 077` 和系统安全随机源生成密钥/密码。
3. 配置 SQLite、TLS 路径、gRPC 启用和 HTTP 端口，首次打印凭据，再次运行不重置。
4. 使用 `exec env ... "$binary"` 前台启动，保留 `Ctrl+C` 信号语义。
5. 在 GitHub Actions 每个 Server bundle 中加入脚本，添加首次/再次初始化布局测试和文档。

### Task 5: 实施前端路由、服务详情和手动结果流

**Files**

- Create: `frontend/src/pages/ServiceDetailPage.tsx`
- Create: `frontend/src/features/services/serviceActions.ts`
- Create: `frontend/src/styles/service-detail.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app/navigation.ts`
- Modify: `frontend/src/hooks/useHashRoute.ts`
- Modify: `frontend/src/pages/ServicesPage.tsx`
- Modify: `frontend/src/features/services/serviceForm.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles/index.css`

**Why**

服务操作和历史需要稳定 URL 与持久结果面板，而不是列表页顶部通知。

**Change Necessity**

现有路由只识别一级 section，`ServicesPage` 混合列表、表单、探活和启动。最小边界是路由解析、独立详情页、共用 Agent 命令终态转换和 API/types。

**Impact/Compatibility**

`#/services` 仍是服务列表；新增 `#/services/{id}`。普通用户保留查看/手动探活，管理员才看到启停/编辑/删除/拉起。

**Verification**

```sh
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

**Steps**

1. 定义可识别 section 和 service ID 的 typed route，使 `AppShell` 导航高亮仍映射到 services。
2. 扩展 API/types 支持单服务、日志游标、各项探活结果、启停和 Agent 命令终态。
3. 抽取统一手动 action helper，SSH 结果直接归一，Agent 命令轮询后归一。
4. 实现详情页状态摘要、操作区、探活项、本次结果和 30 天历史分页。
5. 离线结果后仅在管理员+有启动命令时打开确认弹窗，确认后拉起并用复检结果更新面板/历史。
6. 将服务卡整体设为可导航，删除列表页中旧“启动”动作和探活结果 Notice。
7. 将新建表单 `enabled` 默认改为 false，编辑时仍忠实载入现有值。

### Task 6: 实施个人账号、CA 下载和管理界面二次优化

**Files**

- Create: `frontend/src/pages/AccountPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/app/navigation.ts`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/pages/AgentsPage.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/base.css`
- Modify: `frontend/src/styles/layout.css`
- Modify: `frontend/src/styles/ui.css`
- Modify: `frontend/src/styles/features.css`
- Modify: `frontend/src/styles/service-detail.css`

**Why**

用户需要可访问的改密入口和 CA 下载，且现有侧边栏/首页/状态层级仍需深度优化。

**Change Necessity**

现有导航没有普通用户账号入口，Agent 页没有 CA 下载，布局选中容器尺寸和主页信息密度不符合已批准参考结构。

**Impact/Compatibility**

保留现有视觉 token 名称和 Lucide 图标，不引入新 UI 框架、渐变、玻璃效果或任意魔法尺寸。

**Verification**

```sh
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

**Steps**

1. 增加普通/管理员都可访问的账号入口和改密表单，成功后调用登出。
2. 在 Agent 页加入公共 CA 下载命令和 TLS server name 配置提示，使用浏览器下载而非把证书内容塞入 UI。
3. 优化侧边栏展开/折叠宽度、选中区、顶栏和移动端导航，确保文字不截断。
4. 将服务列表首屏重组为状态统计+紧凑工具栏+可扫描卡片，保持安静的管理工具风格。
5. 统一加载、空、错误、操作中和禁用状态，复用现有 Button/Badge/Modal/Toolbar。

### Task 7: 删除无用前端路径并完成发布验收

**Files**

- Delete: 本轮替代后经 `rg`/TypeScript/CSS 审核确认无引用的前端文件和样式块。
- Modify: `backend/tests/test_packaging_layout.py`
- Modify: `README.md`
- Modify: `docs/server-install.md`
- Create: `docs/aegis/adr/2026-08-05-service-lifecycle-and-instance-ca.md`
- Modify: `docs/aegis/INDEX.md`

**Why**

用户明确要求删除不再使用的前端代码，且发布前必须证明所有改动可构建、可测试、可打包。

**Change Necessity**

只添加新页面会保留旧结果/启动路径和死样式。最小边界是删除有静态证据的无引用代码，同步文档与 ADR。

**Impact/Compatibility**

只删除零引用或已被新 owner 完全取代的内部路径；不删除公开 API、数据列或发布脚本兼容入口。

**Verification**

```sh
timeout 60s backend/.venv/bin/pytest -q backend/tests
timeout 60s agent/.venv/bin/pytest -q agent/tests
npm run typecheck --prefix frontend
npm run build --prefix frontend
shellcheck scripts/start.sh backend/packaging/start.sh backend/packaging/install.sh scripts/platform.sh
git diff --check
git status --short
```

**Steps**

1. 使用 TypeScript 构建、`rg` 引用扫描和 CSS selector 对照识别死代码，逐项删除并立即重跑 typecheck。
2. 更新 README/安装文档，区分 `start.sh` 直接运行和 `install.sh` systemd 安装。
3. 记录 `Service.enabled` 调度语义、30 天日志 owner 和实例 CA 私钥所有权 ADR。
4. 按验证顺序运行后端定向、前端类型/构建、Shell/布局、Agent 和后端总回归。
5. 审查最终 diff，检查重复规则、隐式回退、吞错、死代码、未说明行为变更和安全回归。

## Risks

- Agent 命令结果当前只保存摘要，探活项结果需要与 Agent report schema 实际数据对齐，不能前端伪造细节。
- token version 迁移必须兼容旧 SQLite，不能依赖全新建库。
- `start.sh` 的随机源和平台选择必须在 CentOS 7 可用，不依赖 Bash 或新 coreutils 选项。
- 根目录环境文件中包含管理员初始密码；初始化后可保留用于重启，必须 `0600` 且不在重复启动时打印。

## Retirement

- 删除 `ServicesPage` 中手动探活结果 Notice 和直接“启动”按钮。
- 删除任何前端 30 天截断或第二历史源。
- 删除被新详情页/账号页完全取代且经静态证据证明无引用的组件、hook 和 CSS selector。
- 保留现有 `scripts/start.sh`，因其仍是源码开发入口；保留 `install.sh`，因其仍是 systemd 安装入口。

## Execution Route

- Decision: inline
- Evidence: 用户要求直接实施，当前工作树可用，且后端契约、前端类型与发布布局需由单一协调者保持顺序一致。
- Fallback: 任一合同发现需要超出已批准规格时停止实施并回到设计。
- User confirmation required: no

