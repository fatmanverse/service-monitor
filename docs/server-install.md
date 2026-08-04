# 服务监控 Server 发布

服务监控的前端不是单独的“前端二进制”：GitHub Actions 先执行 `npm run build` 生成静态资源，再将 `frontend/dist` 嵌入后端 PyInstaller 单文件。最终部署只需要一个 `service-monitor-server` 二进制，不需要 Node.js 或 Python。

发布 workflow 会构建：

- `service-monitor-server-linux-x86_64-glibc228`
- `service-monitor-server-linux-arm64-glibc228`

每个 tar 包包含后端二进制、SHA-256、systemd unit、环境变量模板和安装脚本。安装：

```bash
tar -xzf service-monitor-server-*.tar.gz
sudo ./install.sh service-monitor-server-linux-x86_64-glibc228
sudo editor /etc/service-monitor/service-monitor.env
sudo systemctl start service-monitor-backend
```

默认只启动 FastAPI 管理 API；如果要同时启动 Agent gRPC 控制面，配置 `AGENT_GRPC_ENABLED=true`，并提供 `AGENT_GRPC_CERT_FILE` 与 `AGENT_GRPC_KEY_FILE`。
