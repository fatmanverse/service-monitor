# ADR：任务调度采用数据库租约而非独立队列组件

## 状态

已接受。适用于新平台全部执行动作。

## 背景

平台一切远端执行（探活、命令、部署、发现、备份）统一抽象为任务。任务系统需要满足：

- 多个调度副本并发运行，同一任务恰好被一个执行者领取。
- 执行者宕机后，其持有的任务能被其他副本接管，不永久卡死。
- 任务状态与业务数据（资产状态、审计记录）的变更需要原子性。
- 支持延迟执行、优先级、重试、并发策略、幂等去重。
- 长任务（部署十分钟）不阻塞短任务（探活一秒）。

## 决策

以 PostgreSQL 为任务队列，用 `FOR UPDATE SKIP LOCKED` 实现无锁抢占，用租约（`lease_owner` + `lease_expires_at`）实现故障接管。

领取逻辑为单条原子 SQL：

```sql
UPDATE tasks SET
    status = 'leased',
    lease_owner = :worker_id,
    lease_expires_at = now() + :lease_ttl,
    attempt = attempt + 1
WHERE id IN (
    SELECT id FROM tasks
    WHERE status = 'pending'
      AND scheduled_at <= now()
      AND task_type = ANY(:subscribed_types)
    ORDER BY priority, scheduled_at
    LIMIT :batch
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

Worker 执行期间周期续租。独立的回收任务将租约过期的任务重置为 `pending`；`attempt` 超过 `max_attempts` 则置 `failed`。

按 `task_type` 分订阅实现队列隔离：部署 worker 与探活 worker 是不同进程组，互不影响。

## 备选方案与否决理由

**Celery + Redis/RabbitMQ。** 生态成熟、功能完备。否决原因是引入独立的消息持久化层后，任务状态存在两处——Broker 里的投递状态与数据库里的业务状态。二者无法在一个事务内更新，需要额外的对账机制处理「消息已确认但数据库未提交」等中间态。对于运维平台这种「执行必须留痕」的场景，这类不一致的排查成本很高。

**Redis Streams 自建队列。** 轻量、性能高。否决原因是 Redis 的持久化保证弱于 PostgreSQL，而任务丢失在本场景不可接受（丢失一次部署任务意味着发布静默失败）。此外仍然存在跨系统事务问题。

**Kubernetes Job / CronJob。** 天然分布式与故障恢复。否决原因是平台需要管理非容器化的传统主机，不能假设 Kubernetes 存在；且任务粒度过细（每秒上千次探活）不适合以 Pod 为执行单元。

**APScheduler 内存调度（旧项目方案）。** 否决原因明确：内存注册表在多副本下每个副本都会独立触发同一定时任务，导致重复执行。这是旧项目无法集群化的直接原因。

## 代价

**强依赖 PostgreSQL 且 SQLite 不再可用。** `SKIP LOCKED` 是 PostgreSQL 特性，SQLite 无对应能力。开发环境也必须使用 PostgreSQL，不能再用零配置的文件数据库。接受此代价，因为集群能力是硬需求。

**任务表是热表，需要运维关注。** 高频写入加频繁更新会产生表膨胀，需要分区、归档与 autovacuum 调优。相比之下专用队列组件在这方面是免维护的。缓解方式是终态任务及时归档到 `tasks_archive`，热表只保留活跃数据。

**轮询而非推送带来调度延迟。** 副本以固定间隔轮询，任务从到期到被领取存在延迟。通过缩短轮询间隔（1 秒）与 `LISTEN/NOTIFY` 唤醒（高优先级任务立即通知）控制在可接受范围。容量目标定为 P99 低于 5 秒。

**幂等性责任转移给任务实现。** 因为存在租约过期后重跑的可能，任务实现必须幂等。对于天然非幂等的动作（执行启动脚本），需要以执行令牌加目标状态检查防重。这是显式代价，必须在每个任务类型的实现中处理。

## 影响

- 所有执行动作必须建模为任务，不允许在请求处理中直接执行远端操作。
- Worker 必须实现续租与幂等，作为任务框架的强制契约。
- 数据库运维需覆盖任务表的分区管理与归档策略。
- 阶段一必须以三类特征差异明显的任务（探活、批量命令、资产发现）验证框架，避免抽象只适配单一场景。
