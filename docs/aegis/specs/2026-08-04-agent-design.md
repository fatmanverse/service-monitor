# 主动注册 Agent 设计规格

## 状态

- 产品方向：用户已确认。
- 书面规格：待用户复核。
- ADR 信号：是；实现完成前需记录双执行模式、Agent 身份与离线自治边界。

## 目标

- 提供类似 monit 的节点 Agent，由远程节点主动连接监控中心。
- Agent 在节点本地执行进程、systemd、GET、POST 探活、嵌套健康规则和自动拉起。
- Agent 无需目标节点预装 Python，以 PyInstaller 单文件二进制和 systemd 服务部署。
- 保留现有 SSH 执行模式，Agent 与 SSH 共用主机、服务、探活项、健康规则、告警和权限模型。
- 支持约 200 个节点、1000 个服务，Agent 心跳默认 30 秒。

## 核心不变量

- `Host`、`Service`、`ServiceProbe` 和 `health_rule_json` 是唯一配置源，不创建 Agent 专属服务配置表。
- 每台主机只能选择一种执行模式：`ssh` 或 `agent`；不得自动回退或同时执行。
- 主机切换为 Agent 时永久清除 SSH 连接信息；切回 SSH 必须重新配置。
- 中心负责配置、权限、状态汇总和飞书告警；Agent 负责本地执行、离线自治和结果暂存。
- Agent 只能读取绑定主机的配置，只能上报绑定主机的结果。
- 节点密钥按 Agent 独立生成、可撤销、可轮换，不使用全局共享 Agent 密钥。
- 目标节点部署过程不依赖 Docker；Docker/QEMU 只允许用于 GitHub Actions 构建和兼容测试。

## 方案选择

采用双执行模式：现有主机增加 `execution_mode`，默认 `ssh`；审批 Agent 时可新建 Agent 主机或绑定已有主机并显式切换为 `agent`。

不采用以下方案：

- Agent 独立维护服务与规则：会产生重复配置和状态同步冲突。
- Agent 完全替换 SSH：无法平滑兼容未部署 Agent 的节点。
- Agent 定时、SSH 手动执行：同一服务存在双执行路径，无法保证幂等和状态顺序。

## 中心端数据模型

### 主机

- `hosts.execution_mode`：`ssh` 或 `agent`，旧数据迁移后统一为 `ssh`。
- Agent 新建主机使用 Agent 上报的主机名、运行用户和地址摘要，不创建 SSH 认证数据。
- Agent 绑定已有主机时保留服务、历史、资源组授权和告警关系，但永久清除 SSH 连接信息；切换后调度器不得再提交 SSH 服务任务。

### 服务启动用户

- `services.start_user`：可选 Linux 用户名；未选择或为空时不得调用任何用户切换工具，直接以当前执行用户运行原启动命令。
- Agent 模式使用参数化进程调用 `runuser --user <start_user> -- /bin/sh -lc <start_command>`，不得拼接用户名到 Shell 字符串。
- SSH 模式使用安全引用后的 `sudo -n -u <start_user> -- /bin/sh -lc <start_command>`；目标 SSH 用户必须具备对应无交互 sudo 权限。
- SSH 模式缺少 `sudo` 或权限时启动明确失败，不自动改用原 SSH 用户执行。
- Agent 执行前使用系统用户数据库验证 `start_user` 存在；不存在时明确失败并上报。
- `start_user` 只影响启动命令，不改变进程、systemd 或 HTTP 探活的执行身份。

### Agent

新增 `agents`：

- `id`、`agent_uuid`：稳定且唯一。
- `status`：`pending`、`approved`、`rejected`、`revoked`。
- `host_id`：审批后唯一绑定主机。
- `claim_token_hash`：首次申请和领取密钥使用。
- `secret_hash`：长期请求认证，只保存高熵密钥哈希。
- `pending_secret_encrypted`：审批后临时保存的可领取密钥；首次认证心跳成功后清除。
- `hostname`、`runtime_user`、`os_release`、`architecture`、`glibc_version`、`agent_version`。
- `last_seen_at`、`last_ip`、`config_revision`、`created_at`、`approved_at`、`revoked_at`。

### 命令

新增 `agent_commands`：

- `command_id`：全局唯一，作为 Agent 幂等键。
- `agent_id`、`service_id`、`command_type`：`probe_service` 或 `restart_service`。
- `status`：`pending`、`claimed`、`succeeded`、`failed`、`expired`。
- `payload_json`、`result_json`、`created_at`、`claimed_at`、`finished_at`、`expires_at`。
- 默认 5 分钟未领取则过期；同一 `command_id` 不得重复执行。

### 结果去重

新增 `agent_report_receipts`，以 Agent 生成的 `report_id` 唯一去重。每个 Agent 同时维护持久化单调递增 `report_sequence`，中心以序号判断新旧，不能使用客户端时间或随机 ID 决定覆盖顺序。中心收到重复报告时返回成功但不重复写日志、改变状态或发送告警；回执可按保留周期清理。

## 注册与审批

1. Agent 首次启动生成随机 `agent_uuid` 和至少 256 位 `claim_token`，保存到权限 `0600` 的本地配置。
2. Agent 通过 TLS gRPC 提交注册申请和主机环境摘要；中心只保存 `claim_token` 哈希。
3. 管理员在“Agent 管理”中拒绝申请，或批准并选择“新建主机/绑定已有主机”。
4. 批准时中心生成至少 256 位独立 Agent 密钥，保存长期哈希及由 `APP_SECRET` 加密的临时领取副本。
5. Agent 使用 `agent_uuid + claim_token` 轮询领取密钥；网络中断时可重复领取同一临时副本。
6. Agent 使用新密钥完成首次认证心跳后，中心清除 `pending_secret_encrypted` 和 `claim_token_hash`。
7. 撤销后所有 Agent API 立即拒绝；重新接入必须重新申请或由管理员显式轮换密钥。

注册接口必须限制请求体大小，并按来源 IP 与 `agent_uuid` 限速；重复申请更新同一待审批记录，不创建无限重复记录。

## 认证与 gRPC TLS

- Agent gRPC metadata 使用 `x-agent-id` 和 `authorization: Bearer <agent-secret>`。
- 密钥比较使用恒定时间比较，高熵密钥使用带 `APP_SECRET` 的 HMAC-SHA256 哈希保存。
- 默认使用系统 CA 严格校验监控中心证书。
- 支持配置自定义 `ca_file`，用于内网自签 CA。
- 不提供关闭 TLS 证书校验的选项。
- Agent gRPC 认证与管理员/用户 FastAPI JWT API 分离，不复用用户登录令牌。
- FastAPI 只提供管理员审批、撤销、轮换和命令状态查询，不承载 Agent 注册、心跳、配置和报告协议。

## 同步协议

- Agent 默认每 30 秒发起一次 gRPC 心跳；所有连接均由 Agent 主动建立。
- 心跳携带 Agent 版本、主机摘要、当前配置版本和结果队列摘要。
- 中心响应包含最新配置版本、配置变更和待执行命令。
- 配置使用单调递增 `config_revision`；Agent 只接受更高版本，并以事务方式替换本地缓存。
- 探活结果完成后尽快批量上报，不必等待下一次心跳。
- 中心超过 90 秒未收到心跳，将 Agent 主机判定为离线并触发节点告警；恢复心跳时触发恢复告警。

首期使用 Agent 主动发起的 gRPC unary RPC，不使用 server streaming，也不建立中心到节点的入站连接。

### gRPC 契约

- `AgentControl.Enroll`：提交或刷新待审批申请。
- `AgentControl.Claim`：使用 `agent_uuid + claim_token` 领取审批后的密钥。
- `AgentControl.Heartbeat`：认证心跳并返回配置版本与待执行命令摘要。
- `AgentControl.GetConfig`：按版本获取绑定主机的完整配置。
- `AgentControl.Report`：批量幂等上报探活、自动拉起和命令结果。
- `GET /api/agents`、`POST /api/agents/{id}/approve`、`POST /api/agents/{id}/reject`、`POST /api/agents/{id}/revoke`、`POST /api/agents/{id}/rotate-secret`：管理员管理接口。
- `GET /api/agent-commands/{command_id}`：管理员或有服务可见权限的用户查询其已创建命令状态。

protobuf 唯一源为 `protocol/agent.proto`。请求和响应必须携带 `protocol_version`；不支持的主版本返回 `FAILED_PRECONDITION`，不做静默兼容。

## Agent 本地执行

- Agent 使用本地 SQLite 保存已批准身份、配置缓存、结果 outbox、持久化 `report_sequence` 和已执行命令 ID。
- 状态库权限为 `0600`；HTTP Basic/Bearer 等配置密钥使用由 Agent 密钥派生的本地加密密钥保存，不以明文落盘。
- 进程探活扫描 `/proc/*/cmdline`，语义与现有 `pgrep -f` 一致。
- `systemctl status <unit>` 和 `systemctl is-active <unit>` 配置统一执行 `systemctl is-active --quiet -- <unit>`，仅退出码 0 在线。
- GET/POST 支持 Headers、JSON Body、Basic、Bearer、期望状态码和超时。
- 健康规则复用中心相同的递归 AND/OR 求值与验证规则。
- 自动拉起仅执行管理员配置的 `start_command`，执行后立即复检。
- 仅设置 `start_user` 时，自动拉起和手动启动才切换到该用户后执行；未设置时保持当前用户。
- Agent 进程由 systemd 守护；默认以 root 运行以支持进程查看和服务拉起，部署文档必须说明权限风险。

## 中心断线与补报

- Agent 无法连接中心时继续使用最后一次完整配置执行探活和自动拉起。
- 本地 outbox 默认保留最近 10000 条结果或 7 天，先达到上限者生效；超限删除最旧已完成记录并写本地错误日志。
- 连接恢复后按 `report_sequence` 补报，发生时间只用于展示。
- 历史补报写入探活日志，但不逐条重放飞书告警；中心只根据每个服务最新补报状态与中心已知状态发送至多一次状态变化告警，并标注“延迟上报”。
- 中心断线期间 Agent 无法发送飞书告警，这是明确限制，不在 Agent 内复制告警配置。

## 手动命令

- 前端手动探活和启动在 Agent 模式下创建命令，不同步等待 Agent 完成。
- 页面展示等待、执行中、成功、失败和超时状态，并轮询命令结果。
- Agent 领取命令后先在本地记录 `command_id`，再执行；重领同一命令返回已有结果。
- `restart_service` 执行启动命令并复检；节点离线或 Agent 被撤销时中心拒绝创建新命令。
- SSH 模式继续使用现有同步手动接口，API 输出需明确区分即时结果与排队命令。

## 调度与告警

- 中心调度器只为 `execution_mode=ssh` 的主机创建 SSH 主机和服务任务。
- Agent 主机状态只由认证心跳超时决定，不发起 SSH 探活。
- Agent 服务状态只由 Agent 报告更新；重复 `report_id` 或较小 `report_sequence` 不得覆盖更新状态。
- Agent 主机离线时沿用现有行为：其服务保留最后状态，中心静默服务告警。
- Agent 恢复后，中心处理最新状态；只有真实状态变化才发送服务告警。

## 管理界面

- 新增“Agent 管理”导航，仅管理员可见。
- 待审批列表显示主机名、系统、架构、glibc、Agent 版本、申请时间和来源地址。
- 审批时选择新建主机或绑定已有主机；绑定操作必须二次确认执行模式切换及 SSH 连接信息永久清除。
- 已批准列表显示绑定主机、在线状态、最后心跳、配置版本，并提供撤销和密钥轮换。
- 主机管理显示执行模式；Agent 主机隐藏无效的 SSH 认证编辑项。
- 服务页面的手动操作在 Agent 模式下展示异步命令状态。

## Agent 文件布局

- 二进制：`/usr/local/bin/service-monitor-agent`
- 配置：`/etc/service-monitor-agent/agent.toml`，权限 `0600`
- 状态库：`/var/lib/service-monitor-agent/agent.db`
- 日志：默认写入 journald
- systemd unit：`/etc/systemd/system/service-monitor-agent.service`

安装脚本必须幂等，不覆盖已有 Agent 身份和密钥；卸载默认保留配置与状态库，清除身份必须使用显式参数。

## 构建与发布

GitHub Actions 必须发布以下四个独立产物：

- `service-monitor-agent-linux-x86_64-glibc217`
- `service-monitor-agent-linux-x86_64-glibc228`
- `service-monitor-agent-linux-arm64-glibc217`
- `service-monitor-agent-linux-arm64-glibc228`

构建要求：

- glibc 2.17 使用 `manylinux2014` 构建环境。
- glibc 2.28 使用 `manylinux_2_28` 构建环境。
- glibc 2.34 及更高版本使用 glibc 2.28 产物，并必须在 Rocky Linux 9、Ubuntu 22.04/24.04 和 Debian 12 中验证。
- ARM64 优先使用原生 GitHub Runner；不可用时使用 QEMU 构建并进行架构验证。
- 发布包包含 SHA-256 校验文件、安装脚本和 systemd unit。
- 安装脚本使用 `uname -m` 与 `getconf GNU_LIBC_VERSION` 选择最高兼容产物。
- glibc 低于 2.17、未知 libc 或 musl/Alpine 必须明确拒绝，不静默选择错误包。

兼容验证矩阵：

- CentOS 7。
- Rocky Linux 8、9。
- Ubuntu 20.04、22.04、24.04。
- Debian 11、12。
- x86_64 与 ARM64 均需执行二进制自检、注册、领取密钥、心跳、配置同步、进程/HTTP 探活、命令幂等和安装脚本检查。
- Ubuntu 必须额外验证 systemd unit，可安装、启动、重启和读取 journald 日志。

## 数据迁移与兼容

- 安装升级迁移只为 `hosts.execution_mode` 增加默认值 `ssh`，迁移本身不删除或重写现有 SSH 密文；只有管理员确认切换具体主机时才清除。
- SQLite 迁移使 `hosts.port` 可空，并为 `services` 增加可空 `start_user`；表重建必须在事务中保留主键、外键关系、索引和所有已有行。
- 新表通过幂等迁移创建，旧 SQLite 数据保留。
- 绑定已有主机切换为 Agent 时执行以下不可逆字段变更：`password_encrypted = NULL`、`private_key_path = NULL`、`port = NULL`、`auth_type = "agent"`，原 SSH `username` 替换为 Agent 实际运行用户。
- 切换不删除主机名称、主机标识、服务、探活记录、资源组授权或告警关系。
- 从 Agent 切回 SSH 必须由管理员显式操作，并重新填写 SSH 地址、端口、用户名和认证配置。
- 不提供运行时自动 SSH 回退。

### 数据删除声明

- 删除分类：`persistent-state`。
- 已确认目标：绑定已有主机切换为 Agent 时的 SSH 密码密文、私钥路径、端口及原 SSH 用户信息。
- 新唯一执行所有者：绑定后的 Agent。
- 保留行为：服务配置、状态历史、资源组授权、告警关系和主机身份不变。
- 用户确认：已于 2026-08-04 明确确认上述字段永久清除。
- 回滚边界：切换后不从应用数据库恢复 SSH 信息；需要切回时由管理员重新录入。

## 验收标准

- 未认证 Agent 可提交待审批申请，但不能读取配置或创建结果。
- 审批后 Agent 可重复领取密钥直至首次认证成功，之后 `claim_token` 失效。
- 撤销密钥后心跳、同步、结果和命令接口全部拒绝。
- 新建和绑定两种审批路径都能正确生成 Agent 主机关系。
- 绑定已有主机后 SSH 连接字段按确认范围永久清除，其他业务关系和历史保持不变。
- Agent 只收到绑定主机的服务、探活项、规则和所需认证密钥。
- 服务可选配置 `start_user`；已设置时 SSH 和 Agent 模式均以指定用户执行，缺少用户或权限时明确失败；未设置时验证不会调用 `sudo` 或 `runuser`。
- Agent 在中心断线期间继续探活和自动拉起，恢复后幂等补报且不产生告警风暴。
- 手动探活和启动命令可从等待流转到终态，重复领取不重复执行。
- Agent 模式不会触发任何 SSH 调度；SSH 模式行为保持不变。
- 心跳超时和恢复触发现有节点告警，离线期间服务告警静默。
- 四个发布产物均生成并带校验和，Ubuntu、Debian、CentOS/Rocky 矩阵通过。
- 后端目标测试、Agent 单元/集成测试、前端类型检查和构建全部通过。

## 非目标

- 不支持 Windows、macOS 或 Alpine/musl Agent。
- 不支持中心主动连接 Agent、WebSocket 或 Agent 入站监听端口。
- 不在首期提供 Agent 自动升级；升级由安装脚本或配置管理工具执行。
- 不在 Agent 内发送飞书告警或维护第二套用户权限。
- 不提供任意远程 Shell；命令队列只允许已定义命令类型和已有服务启动命令。
- 不提供多中心、高可用或跨中心 Agent 漫游。

## 复杂度预算

- 后端新增独立 Agent 路由、认证、同步与命令模块，不继续扩大现有 `monitoring.py`。
- Agent 执行器独立于 FastAPI，但健康规则必须复用或由同一组契约测试保证一致。
- 前端 Agent 管理独立页面，主机与服务页面只增加执行模式相关分支。
- 预计现有核心文件不应超过 800 行；任何跨越必须在实施计划中安排拆分。
