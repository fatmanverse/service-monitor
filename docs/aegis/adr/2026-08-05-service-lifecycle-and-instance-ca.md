# ADR: 服务监控生命周期与实例 CA

## 状态

已接受。

## 背景

原服务页将定时监控、手动探活和启动服务混合，新服务会立即进入调度，且历史日志无物理保留边界。Agent gRPC 支持自定义 CA，但 Server 发布不产生实例证书，导致默认接入无可用信任链。

## 决策

- `Service.enabled` 只表示是否参与定时调度，不限制手动探活、详情和历史查询。
- 新服务默认 `enabled=false`；旧服务的现有值不迁移。false 转 true 时将 `next_check_at` 设为当前时间。
- 手动 `/probe` 不执行自动拉起。只有管理员看到本次离线结果并确认后，才调用 `/restart` 启动并复检。
- `ProbeLog` 是 SSH/Agent、手动/定时结果的唯一历史源。统一保留 owner 查询最近 30 天，Server 启动和每日调度物理删除更旧记录。
- 每个 Server 实例在未显式配置外部证书时生成独有 CA 和 Server 证书。发布包不包含任何 CA 私钥。
- 自生成 Server 证书使用 `service-monitor-server` 固定 SAN。Agent 导入公共 CA 并通过 `tls_server_name` 严格验证，允许网络连接地址是内网 IP。
- 根目录 `start.sh` 只负责发布二进制的平台校验、当前目录初始化和前台运行；`install.sh` 继续负责 systemd 安装。

## 后果

- 监控启停不会启动或停止业务进程，界面必须使用不同文案和动作。
- 30 天前日志在升级后首次启动时可被永久删除，不提供内置导出或归档。
- CA 私钥是实例本地持久数据，不得丢失、共享到其他实例或上传到 GitHub Release。
- 部署外部证书时可继续使用证书自身域名，不必设置 `tls_server_name`，但不允许关闭校验。
