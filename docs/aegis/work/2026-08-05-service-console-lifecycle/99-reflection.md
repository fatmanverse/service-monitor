# 服务控制台生命周期实施反思

## Outcome

- 服务卡进入独立详情，详情集中展示本次结果、探活项和 30 天历史。
- 新服务默认停止定时探活，启用时立即进入可调度状态。
- 手动离线结果后才询问管理员是否拉起，后端 `/probe` 不再自动执行启动命令。
- 用户可校验旧密码后改密，token version 使旧 JWT 在后端失效。
- Server 可生成实例 CA/Server 证书，Agent 支持导入 CA 并校验固定 TLS 身份。
- Server 发布包根目录 `start.sh` 能在当前目录生成随机密码和配置后前台运行。

## Architecture Review

1. Ownership integrity: `ProbeLog`/retention owner、`Service.enabled`、token version 和实例 CA 均只有一个 canonical owner。
2. Module boundaries: Agent 协议仍是 TLS gRPC，FastAPI 只提供管理和 CA 下载。
3. Contract changes: 日志 API 改为游标分页，探活返回扩展探活项，前后端同步更新。
4. Cascade proliferation: 没有新增日志表、token 黑名单、前端历史截断或 TLS 回退。
5. Dependency direction: UI 消费后端权限/保留结果，调度器调用保留 owner，不反向复制规则。
6. Retirement completeness: 列表旧启动/探活结果路径和暗色主题 owner 已删除，其余前端文件均有引用。
7. Entropy flow: 新增 owner 都对应独立契约，列表页职责减少，没有隐式 fallback。

## Residual Risk

- 未按用户指示运行浏览器视觉验证；已使用 TypeScript 和 Vite 生产构建作静态证据。
- Python 3.13 测试环境对 `datetime.utcnow()` 产生弃用警告，属现有全局时间模型，本轮没有混合 timezone-aware 值以避免 SQLite 兼容变更。
