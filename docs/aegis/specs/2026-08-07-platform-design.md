# 一体化运维平台设计规格

## 状态

- 产品方向：用户已确认（内部自用、一体化、可集群、可无限扩展）。
- 书面规格：待用户复核。
- 项目性质：全新项目，不复用任何既有代码与数据。
- ADR 信号：是。任务调度模型、Agent 通道模型、堡垒机自研边界、拓扑数据来源四项需独立记录。

## 目标

建设一个内部自用的一体化运维平台，在单一实体模型与单一权限模型之上，覆盖约 80% 的日常运维工作。

- **一体化**：全平台只有一份资产定义、一套权限、一条审计流水。任何模块不得自建资产表或自建权限判定。
- **可集群**：所有控制面组件无状态化，可多副本部署，任一副本失效不影响整体可用性。
- **可扩展**：容量增长通过增加副本与分片解决，不通过修改架构解决。设计目标为 10000 节点、100000 服务实例。
- **可审计**：一切读写与执行动作可追溯到人、时间、目标、结果。

## 非目标

以下内容明确不在本平台范围内，避免范围蔓延：

- 不做多租户 SaaS。内部自用，单组织模型，不设租户隔离层。
- 不做日志检索平台。日志采集与检索交由既有 ELK / Loki，平台只做跳转与关联。
- 不自研时序数据库。指标存储采用 Prometheus 生态，平台只做接入、聚合查询与展示。
- 不做容器编排。Kubernetes 已解决该问题，平台以只读方式接入集群资产。
- 不做 Windows 图形会话代理（RDP）。首期仅支持 SSH 类文本会话。

## 80% 运维需求的范围定义

平台覆盖以下八个能力域。此清单即验收范围，不在清单内的需求一律走变更评审。

| 能力域 | 覆盖内容 | 交付阶段 |
| --- | --- | --- |
| 资产管理 | 主机、服务、资源组、标签、凭据托管、自动发现与对账 | 一 |
| 身份与权限 | 用户、角色、资源组授权、操作级权限、审批流 | 一 |
| 任务编排 | 即时命令、定时任务、批量作业、剧本编排、审批与阻断 | 一 |
| 审计 | 统一审计流水、会话录像索引、变更历史、不可篡改归档 | 一 |
| 服务监控 | 探活（进程/systemd/HTTP/TCP）、健康规则、自动恢复、告警路由 | 二 |
| 指标监控 | Prometheus 接入、统一查询、仪表盘嵌入、容量分析 | 二 |
| 交付流水线 | Git Webhook 触发、构建、部署、探活验证、自动回滚 | 三 |
| 访问控制 | SSH 会话代理、会话录像与回放、命令审计与阻断 | 三 |
| 拓扑 | 部署拓扑、依赖拓扑、故障影响面分析 | 四 |

## 核心不变量

违反任一条即为架构缺陷，不接受以配置开关或兼容分支绕过。

1. **单一资产源**：`assets` 及其子类型表是唯一资产定义。监控、CI、堡垒机、拓扑均以外键引用，不得复制资产属性。
2. **单一权限判定**：所有授权决策必须经由 `authorization` 模块的统一入口。任何路由不得自行拼接权限过滤条件。
3. **控制面无状态**：API 与调度副本不得在进程内存中保存跨请求的权威状态。进程内缓存只允许作为可重建的性能优化。
4. **任务恰好执行一次**：同一任务实例在任意时刻最多被一个执行者持有，通过数据库租约保证，不依赖调度副本间的协调。
5. **执行必留痕**：任何在远端产生副作用的动作，必须先落审计记录再执行，执行结果回填同一条记录。
6. **凭据不出库**：主机凭据、密钥、令牌以信封加密存储，只在执行节点内存中解密，不写入日志、不回显给前端、不进入任务参数。
7. **Agent 最小权限**：Agent 只能读取绑定资产的配置，只能上报绑定资产的结果，不能枚举平台其他资产。
8. **审计不可删除**：审计流水只追加。归档与清理由独立保留策略执行，且清理动作本身入审计。

## 总体架构

### 分层

```
┌─────────────────────────────────────────────────────────────┐
│  接入层    Nginx / LB      ── TLS 终止、路由、限流            │
├─────────────────────────────────────────────────────────────┤
│  控制平面  api-server      ── REST/WS，无状态，N 副本         │
│           scheduler       ── 任务派发，无状态，N 副本         │
│           worker          ── 任务执行，无状态，N 副本         │
├─────────────────────────────────────────────────────────────┤
│  接入网关  agent-gateway   ── gRPC 长连接，有状态，N 副本      │
│           session-gateway ── 交互会话代理，有状态，N 副本      │
├─────────────────────────────────────────────────────────────┤
│  数据平面  PostgreSQL      ── 权威状态、任务队列、审计         │
│           Redis           ── 连接路由、缓存、分布式锁          │
│           对象存储         ── 会话录像、构建产物、归档          │
│           VictoriaMetrics ── 时序指标                        │
├─────────────────────────────────────────────────────────────┤
│  执行平面  agent           ── 节点内执行，主动外连             │
└─────────────────────────────────────────────────────────────┘
```

### 组件职责

**api-server**：处理前端与 Webhook 请求，做权限判定与参数校验，写入任务与审计，不执行长任务。任何请求处理时间超过 2 秒即视为设计错误，应改为任务。

**scheduler**：扫描到期任务并置为可领取状态。多副本通过 `FOR UPDATE SKIP LOCKED` 竞争，无需选主。

**worker**：领取任务并执行。区分任务类别订阅不同队列，避免长任务饿死短任务。

**agent-gateway**：持有 Agent 的 gRPC 双向流。是有状态组件，但状态可重建——Agent 断线后自动重连到任意副本。连接归属写入 Redis，供其他副本路由。

**session-gateway**：代理交互式会话，转发 PTY 字节流并旁路录制。有状态且不可迁移——会话生命周期内必须固定在同一副本，通过粘性路由保证。

### 为什么把网关与 API 分开

Agent 长连接和交互会话都要求连接亲和性，而 API 要求可随意扩缩和滚动重启。混在一个进程里会导致：滚动发布时踢掉所有 Agent 连接和用户终端；网关的连接数压力影响 API 的响应延迟。分开后 API 可以按请求量扩缩、网关按连接数扩缩，发布节奏也可以不同。

## 数据模型

### 资产域

采用「统一资产表 + 类型扩展表」结构，使权限、审计、拓扑可以统一引用资产而不关心具体类型。

```
assets                      资产主表
  id                        主键
  asset_type                host | service | database | k8s_cluster | ...
  name                      同类型内唯一
  resource_group_id         归属资源组，可为空（未归组资产）
  status                    unknown | healthy | degraded | down | maintenance
  labels                    JSONB，自由标签，建 GIN 索引
  source                    manual | discovery | k8s | cloud_api
  external_id               外部系统标识，用于对账去重
  created_at / updated_at

hosts                       主机扩展
  asset_id                  主键，外键 → assets.id
  hostname / ip_addresses
  os_family / os_version / arch / libc_version
  cpu_cores / memory_mb
  execution_mode            agent | ssh
  credential_id             外键 → credentials.id，可为空
  agent_id                  外键 → agents.id，可为空

service_instances           服务实例扩展
  asset_id                  主键，外键 → assets.id
  host_asset_id             承载主机，外键 → assets.id
  service_definition_id     外键 → service_definitions.id
  port / process_pattern / systemd_unit
  deploy_path / version

service_definitions         服务定义（跨实例共享的配置）
  id / name / repo_url / build_config / deploy_config
  health_rule               JSONB，嵌套 AND/OR 规则树
  probe_specs               JSONB，探活项定义
```

关键设计：**服务定义与服务实例分离**。同一个服务部署在十台机器上时，探活规则、构建配置、部署脚本只写一份，实例只保存位置与版本差异。这是旧结构最需要修正的地方——把定义塞进实例会导致改一次配置要改十条记录，且无法保证一致。

### 身份与权限域

```
users                       id / username / display_name / email
                            password_hash / mfa_secret
                            is_active / token_version
roles                       id / name / description / is_builtin
permissions                 id / code            例：asset.read、task.execute、session.open
role_permissions            role_id / permission_id
user_roles                  user_id / role_id / scope_type / scope_id
```

权限模型是**「角色定义能做什么，授权范围定义能对谁做」**的二维结构。`user_roles.scope_type` 取 `global` 或 `resource_group`，`scope_id` 指向具体资源组。同一用户可以在 A 组是管理员、在 B 组是只读。

判定入口统一为 `authorization.can(user, permission_code, asset)`，内部展开为一次 SQL：从 `user_roles` 出发，匹配权限码，再校验资产是否落在授权范围内。资产未归组时回退到 `asset_grants` 逐个授权表。

### 任务域

任务是平台一切执行动作的统一抽象——探活、部署、命令、备份都是任务。

```
task_definitions             可复用的任务模板
  id / name / task_type / spec(JSONB) / timeout_seconds
  schedule_cron              为空表示仅手动或事件触发
  concurrency_policy         allow | forbid | replace
  approval_policy            none | single | dual

tasks                        任务实例
  id                         主键
  definition_id              可为空（临时任务）
  task_type                  probe | command | deploy | discovery | backup
  target_asset_id            执行目标
  status                     pending | queued | leased | running
                             | succeeded | failed | cancelled | timeout
  priority                   小值优先
  idempotency_key            唯一索引，防重复提交
  scheduled_at               到期时间
  lease_owner                持有者副本标识
  lease_expires_at           租约到期，用于故障接管
  attempt / max_attempts
  spec                       JSONB，执行参数（不含明文凭据）
  result                     JSONB，结构化结果
  audit_id                   外键 → audit_events.id
  created_by / created_at / started_at / finished_at

task_logs                    执行日志分片
  id / task_id / seq / stream(stdout|stderr) / chunk / created_at
```

`tasks` 表是热表，需要按 `scheduled_at` 与 `status` 建复合索引，并按月分区。终态任务归档到 `tasks_archive` 后从热表删除。

### 监控域

```
probe_results                探活结果（热数据，短保留）
  id / asset_id / probe_key / success / message
  response_ms / checked_at
health_transitions           状态跃迁（长保留，用于 SLA 与告警去重）
  id / asset_id / from_status / to_status / reason / occurred_at
alert_rules                  id / name / target_selector(JSONB)
                             condition / severity / for_duration
alert_channels               id / name / channel_type / config(加密)
alert_routes                 rule_id / channel_id / 生效时段 / 升级策略
alert_events                 id / rule_id / asset_id / status(firing|resolved)
                             fingerprint / started_at / resolved_at
```

`probe_results` 是全平台写入量最大的表。10000 节点、每节点 10 个探活项、60 秒间隔，意味着每秒约 1700 行写入。这张表必须按天分区、保留 7 天，聚合结果写入时序库。原始明细不用于长期查询。

### 审计域

```
audit_events
  id                        主键
  actor_type                user | system | agent | webhook
  actor_id / actor_name     冗余名称，避免用户删除后无法追溯
  action                    动词化编码，例：asset.update、session.open
  target_type / target_id / target_name
  resource_group_id         用于按组检索
  request_id                贯穿一次请求的全链路标识
  source_ip / user_agent
  before / after            JSONB，变更前后快照（敏感字段脱敏）
  result                    success | failure | denied
  error_message
  occurred_at

session_recordings
  id / session_id / asset_id / user_id
  storage_uri               对象存储位置
  duration_ms / bytes / sha256
  command_count / started_at / ended_at
```

审计写入采用**先写后行**：任何有副作用的操作先插入 `audit_events` 拿到 id，再执行，最后回填 `result`。这样即使执行过程中进程崩溃，也留下「尝试过」的痕迹。

### 交付域

```
repositories                 id / provider / repo_url
                             webhook_secret(加密) / default_branch
pipelines                    id / name / repository_id
                             trigger_config(JSONB) / stages(JSONB)
pipeline_runs                id / pipeline_id / commit_sha / ref
                             trigger_type / triggered_by
                             status / started_at / finished_at
deployments                  id / pipeline_run_id / target_asset_id
                             version / status
                             verification_result / rollback_of
artifacts                    id / pipeline_run_id / storage_uri / sha256
```

### 拓扑域

```
asset_relations
  id
  source_asset_id / target_asset_id
  relation_type              runs_on | depends_on | deploys_to
                             | load_balances | replicates
  discovery_method           manual | deployment | connection_probe | trace
  confidence                 0-100，自动发现的可信度
  last_seen_at               自动发现关系的续期时间
  UNIQUE(source, target, relation_type)
```

`last_seen_at` 是防腐烂的关键：自动发现的关系若超过阈值未被再次观测，降低置信度并最终标记失效，而不是永久留在图上。手工关系不受此约束。

## 关键机制

### 任务调度与抢占

调度不选主，所有 scheduler 副本对称竞争。领取任务的单条 SQL：

```sql
UPDATE tasks SET
    status = 'leased',
    lease_owner = :worker_id,
    lease_expires_at = now() + :lease_ttl,
    attempt = attempt + 1
WHERE id IN (
    SELECT id FROM tasks
    WHERE status = 'pending' AND scheduled_at <= now()
    ORDER BY priority, scheduled_at
    LIMIT :batch
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

`SKIP LOCKED` 让并发副本各自拿到不同的行，无需分布式锁。租约到期后由回收任务将 `leased`/`running` 且 `lease_expires_at < now()` 的任务重置为 `pending`，实现执行者宕机后的自动接管。`attempt` 超过 `max_attempts` 则置为 `failed`，避免无限重试。

Worker 在执行期间需周期性续租，长任务不会因超时被重复派发。

### Agent 双通道模型

Agent 与平台之间存在两类交互，必须走不同通道：

**控制通道（durable）**：配置下发、结果上报、异步命令。走数据库队列，Agent 通过 gRPC 流接收通知，断线期间任务留在队列，重连后继续。可靠性优先。

**实时通道（ephemeral）**：交互式终端、实时日志跟随。走 gRPC 双向流，不持久化。连接断开即会话结束。延迟优先。

Agent 连接到任意 gateway 副本后，在 Redis 写入 `agent:{uuid} -> gateway:{node_id}`，带 TTL 并周期续期。当 API 副本需要向某 Agent 推送实时消息时，查 Redis 得到归属副本，通过 Redis Pub/Sub 投递到该副本，由它写入对应的流。

这个设计的取舍是：实时通道依赖 Redis 可用性，Redis 故障时交互会话不可用，但异步任务不受影响——因为它们走数据库队列。核心运维能力（配置、探活、部署）在 Redis 故障时仍可工作。

### 交互式会话代理

会话建立流程：

1. 用户请求打开会话，api-server 校验 `session.open` 权限与目标资产授权。
2. 若目标要求审批，创建审批任务并返回等待状态。
3. 校验通过后写入 `audit_events`（`session.open`，result 暂空），生成一次性会话票据存入 Redis（TTL 30 秒）。
4. 前端用票据连接 session-gateway 的 WebSocket，gateway 校验票据后建立到目标的连接。
5. 目标为 Agent 模式时，gateway 通过实时通道向 Agent 请求 PTY；SSH 模式时 gateway 直连并从凭据服务取密钥。
6. 全程字节流旁路写入录像缓冲，按块上传对象存储。
7. 命令边界由 PTY 输入流解析提取，写入 `session_commands` 供检索与阻断。

阻断机制在 gateway 侧同步执行：命令提交前匹配黑名单规则，命中则拒绝并记审计。规则缓存在 gateway 本地，通过 Redis Pub/Sub 失效通知，避免每条命令查库。

### 凭据管理

三层密钥结构，避免单一主密钥泄露导致全量凭据暴露：

- **主密钥（KEK）**：来自环境变量或 KMS，不落盘。
- **数据密钥（DEK）**：每条凭据独立生成，用 KEK 加密后与密文同行存储。
- **密文**：用 DEK 加密的凭据内容。

解密只发生在 worker 与 gateway 的内存中。api-server 永远不解密凭据——它只传递 `credential_id`。凭据轮换时生成新 DEK 重新加密，旧版本保留一个周期供回滚。

## 功能模块设计

### 资产管理

资产来源分三类：手工录入、Agent 自注册、外部系统同步（云 API、Kubernetes、CMDB）。三类来源统一进入对账流程：按 `source` + `external_id` 判定是新增、更新还是失联。

自动发现的资产默认进入「待确认」状态，不自动纳入监控与授权，需人工确认归组。这避免了发现流程的误报直接产生告警噪音。

失联资产不自动删除，转为 `maintenance` 状态并保留 30 天，防止网络抖动导致资产与其历史数据一起消失。

### 服务监控

探活执行在 Agent 本地完成，平台只下发规则与接收结果。这与「平台主动去探测」的模型相比，节省了 N×M 的网络连接，且节点离线时 Agent 可以本地自治判断并暂存结果。

健康规则是嵌套的 AND/OR 表达式树，叶子节点是探活项。规则求值在 Agent 与平台两侧都实现，Agent 侧用于本地自治与快速自愈，平台侧用于权威判定与告警。两侧使用同一份规则定义与同一套测试向量，避免行为分叉。

自动恢复动作是任务，不是探活的副作用：探活判定离线后创建 `command` 类型任务执行恢复脚本，再创建一次性 `probe` 任务复检。这样恢复动作天然获得审计、并发控制、审批与重试能力。

### 告警

告警链路为：状态跃迁 → 规则匹配 → 指纹去重 → 抑制判定 → 路由分发 → 升级。

去重指纹由规则 id + 资产 id + 关键标签组成，同指纹的持续故障只发一次首告与一次恢复告。抑制规则支持依赖抑制——数据库宕机时抑制其上层应用的告警，依据来自拓扑域的 `depends_on` 关系。

告警通知本身也是任务，失败可重试，且发送记录入审计。

### 交付流水线

Webhook 端点是**未认证的公网入口**，必须做三件事：验签（GitHub `X-Hub-Signature-256` / GitLab token）、重放防护（记录 delivery id 去重）、限流。验签失败直接丢弃并记审计，不返回详细原因。

流水线阶段固定为：`拉取 → 构建 → 产物归档 → 部署 → 验证 → 完成/回滚`。验证阶段复用监控域的探活能力——部署后创建一次性探活任务，失败则触发回滚。这是平台一体化的核心价值：CI 知道服务的健康定义，监控知道刚发生了变更。

同一服务的部署严格串行，通过 `concurrency_policy = forbid` 加服务级咨询锁实现。回滚是一次指向历史版本的正向部署，不是逆操作，因此同样留完整审计。

### 拓扑

关系数据来源按可信度排序：

1. **部署关系**（高置信度）：来自 `deployments`，天然准确且自动更新。
2. **承载关系**（确定）：来自 `service_instances.host_asset_id`。
3. **手工声明**（中置信度）：人工补充的依赖，不自动过期。
4. **连接观测**（低置信度）：Agent 采集 TCP 连接反查对端资产，需要 `last_seen_at` 续期。

首期只做前两类——它们零成本且不会腐烂。连接观测放到最后，因为它引入持续的采集开销与误报处理成本。

故障影响面分析基于 `depends_on` 反向遍历：给定故障资产，输出受影响的上游服务集合，用于告警抑制与故障通告。

## 横向扩展设计

### 无状态化改造要点

控制面不得持有跨请求状态。具体到几个容易出错的地方：

- 并发控制不用进程内锁，改用数据库咨询锁（`pg_advisory_xact_lock`）或 `tasks` 表的 `concurrency_policy`。进程内锁在多副本下完全失效。
- 定时任务不用进程内调度器的内存注册表，改为数据库驱动——`task_definitions.schedule_cron` 计算下次到期时间写入 `tasks.scheduled_at`。
- 证书与密钥不存本地文件系统，改为数据库或对象存储。否则每个副本各自签发一套 CA，Agent 无法跨副本验证。
- WebSocket 会话不假设后续请求落在同一副本，除交互会话外都通过 Redis 共享状态。

### 分片与容量

| 数据 | 增长驱动 | 策略 |
| --- | --- | --- |
| `probe_results` | 节点数 × 探活项 × 频率 | 按天分区，保留 7 天，聚合入时序库 |
| `tasks` | 任务量 | 按月分区，终态归档后删除 |
| `task_logs` | 任务量 × 日志量 | 大块日志转对象存储，库内只留摘要 |
| `audit_events` | 操作量 | 按月分区，冷分区转只读并归档 |
| 会话录像 | 会话时长 | 直接落对象存储，库内只存索引 |
| 时序指标 | 节点数 × 指标数 | VictoriaMetrics 集群模式水平扩展 |

数据库首期单实例加只读副本即可支撑目标容量；若写入成为瓶颈，按 `resource_group_id` 做逻辑分片，因为跨组查询在权限模型下本就少见。

### 容量目标与验证方式

设计目标不通过推算宣告，必须压测验证：

- 10000 个 Agent 同时在线，gateway 副本数与连接分布符合预期。
- 每秒 2000 条探活结果写入，数据库 P99 写延迟低于 50ms。
- 1000 个并发任务执行，调度延迟（到期至开始执行）P99 低于 5 秒。
- 100 个并发交互会话，输入到回显延迟 P99 低于 200ms。

## 安全设计

### 攻击面与对策

平台掌握所有节点的执行权限，被攻破等同于全部服务器失陷。安全设计不是可选项。

| 攻击面 | 对策 |
| --- | --- |
| Webhook 公网入口 | 强制验签、重放防护、限流、失败不回显原因 |
| 会话代理 | 一次性票据、票据与用户/资产绑定、TTL 30 秒 |
| 命令注入 | 参数化执行，不拼接 Shell 字符串；用户名等标识符走白名单校验 |
| 凭据泄露 | 信封加密、api-server 不解密、日志与响应脱敏 |
| Agent 冒充 | 每 Agent 独立证书、可撤销、可轮换，不用共享密钥 |
| 越权访问 | 统一权限入口、默认拒绝、资产未授权时返回 404 而非 403 |
| 审计篡改 | 审计表只追加、归档校验哈希链 |
| 提权执行 | 危险命令黑名单、双人审批、生产环境操作强制审批 |

### 自研堡垒机的风险声明

需要明确记录：自研会话代理的安全风险显著高于自研监控。监控失效的后果是漏报，会话代理失效的后果是攻击者获得全部节点的控制权。

已知成熟替代方案为 Teleport 与 JumpServer，二者经过大量攻防检验。选择自研的前提是接受以下责任：PTY 转发的边界情况处理、录像完整性保证、命令解析绕过（管道、编码、交互式子 shell）的防护、以及持续的安全维护。

本设计的折中是：**分阶段自研，先做低风险子集**。首期只做「经 Agent 执行的受控命令 + 完整审计」，不做完整的 PTY 交互代理；PTY 代理放在第三阶段，届时可重新评估是否改为集成。这样早期就能获得审计能力，而把高风险部分推迟到有充分测试条件时再做。

## 平台自身可观测性

平台自己必须被监控，否则故障时无从下手。

- 所有服务暴露 Prometheus 指标：请求量与延迟、任务队列深度与滞留时长、Agent 在线数、租约回收次数、数据库连接池使用率。
- 结构化日志，字段包含 `request_id`，与审计流水的 `request_id` 对齐，可从审计事件直接跳到相关日志。
- 关键链路埋点：任务从创建到完成的各阶段耗时，用于定位调度延迟来源。
- 平台自身的告警不走平台自己的告警链路，避免自举依赖——单独配置一条外部通道。

## 技术选型

| 组件 | 选型 | 理由 |
| --- | --- | --- |
| 后端框架 | Python 3.12 + FastAPI | 延续既有技术栈；异步支持与 gRPC 生态成熟 |
| ORM | SQLAlchemy 2.x | 已有经验；支持 `SKIP LOCKED` 等原生 SQL 逃逸 |
| 迁移 | Alembic | 手写迁移在多副本与多环境下不可维护 |
| 数据库 | PostgreSQL 16 | 需要 `SKIP LOCKED`、JSONB、分区、咨询锁；SQLite 不支持并发写 |
| 缓存与路由 | Redis 7 | 连接归属、Pub/Sub、票据、分布式锁 |
| 时序 | VictoriaMetrics | 兼容 Prometheus 协议，集群模式水平扩展成本低 |
| 对象存储 | MinIO / S3 | 录像、产物、归档 |
| Agent 通信 | gRPC 双向流 + mTLS | 主动外连穿透 NAT；双向流支撑实时通道 |
| Agent 打包 | PyInstaller 单文件 | 目标节点无需预装 Python |
| 前端 | React 19 + TypeScript | 延续既有技术栈 |
| 前端状态 | TanStack Query + Zustand | 大量服务端状态需要缓存与失效管理，手写会失控 |
| 前端路由 | React Router | 多模块平台需要嵌套路由与代码分割 |
| 前端样式 | Tailwind CSS | 组件数量将达数百，需要统一约束 |
| 前端图表 | ECharts | 拓扑图与时序图需求，社区方案成熟 |

### 与旧项目的选型差异

三处必须改变，否则无法达成集群目标：

- **SQLite → PostgreSQL**：SQLite 单写者模型无法支撑多副本写入，且不支持 `SKIP LOCKED`，任务抢占无从实现。
- **手写迁移 → Alembic**：手写迁移无版本图、无回滚、无法处理多人并行开发的分支合并。
- **进程内调度 → 数据库驱动调度**：APScheduler 的内存注册表在多副本下会导致每个副本都执行同一定时任务。

## 分阶段交付

每阶段结束时平台必须可用，不接受「地基阶段无可用功能」。

**阶段一：地基与资产**（可用形态：资产台账 + 批量命令执行 + 完整审计）

资产模型、权限模型、任务框架、审计框架、Agent 注册与控制通道、资产管理界面、即时命令与批量作业。此阶段验证核心抽象是否成立——如果任务框架无法优雅承载「批量命令」，后续所有模块都会走偏。

**阶段二：监控与告警**（可用形态：完整的服务监控替代品）

探活规则、健康规则引擎、状态跃迁、自动恢复、告警规则与路由、Prometheus 接入、监控仪表盘。

**阶段三：交付与访问**（可用形态：提交代码到上线的完整链路 + 受控访问）

Git Webhook、流水线引擎、构建与部署、部署后验证与回滚；会话代理、录像与回放、命令审计。

**阶段四：拓扑与分析**（可用形态：故障影响面分析）

部署与承载拓扑、拓扑可视化、依赖抑制、影响面分析、容量分析。

## 验收标准

功能验收按阶段清单逐项确认。此外以下横向标准适用于每个阶段：

1. **集群验收**：任意组件杀掉一个副本，进行中的操作不丢失，新请求正常处理。
2. **恰好一次验收**：构造调度副本竞争与 worker 宕机场景，确认任务不重复执行、不丢失。
3. **权限验收**：为每个权限码构造越权尝试，确认全部被拒绝且入审计。
4. **审计完整性验收**：随机抽取 20 个写操作，确认均可从审计流水还原「谁在何时对什么做了什么，结果如何」。
5. **迁移验收**：全部迁移可在空库与存量库上重复执行，且可回滚一个版本。
6. **压测验收**：达成容量目标章节的四项指标。
7. **测试覆盖**：核心模块（权限、任务、健康规则、凭据）单元测试覆盖率不低于 80%。

## 风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 范围过大导致长期无可交付 | 项目停在半成品 | 分四阶段，每阶段独立可用；阶段内再切垂直切片 |
| 自研会话代理存在安全缺陷 | 全节点失陷 | 分阶段自研，先做低风险子集；第三阶段前重新评估是否改为集成 |
| 资产模型抽象错误 | 全模块返工 | 阶段一用批量作业与监控两个真实场景验证抽象 |
| 任务框架无法承载多样负载 | 各模块自建执行路径，一体化失败 | 阶段一即引入三类差异较大的任务验证 |
| PostgreSQL 成为写入瓶颈 | 容量触顶 | 明细数据分区加短保留；预留按资源组分片方案 |
| Redis 故障影响面不清 | 故障时误判 | 明确划分依赖：实时通道依赖 Redis，异步链路不依赖 |
| 与既有 Prometheus / K8s 数据割裂 | 沦为又一个孤岛 | 统一实体模型强制外部资产也走 `assets` 表与对账流程 |
