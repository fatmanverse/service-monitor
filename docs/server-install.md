# 服务监控 Server 发布

服务监控的前端不是单独的“前端二进制”：GitHub Actions 先执行 `npm run build` 生成静态资源，再将 `frontend/dist` 嵌入后端 PyInstaller 单文件。最终部署只需要一个 `service-monitor-server` 二进制，不需要 Node.js 或 Python。

发布 workflow 会构建：

- `service-monitor-server-linux-x86_64-glibc217`
- `service-monitor-server-linux-x86_64-glibc228`
- `service-monitor-server-linux-arm64-glibc217`
- `service-monitor-server-linux-arm64-glibc228`

每个 tar 包包含后端二进制、SHA-256、`start.sh`、systemd unit、环境变量模板和安装脚本。

不安装 systemd，直接在解压目录前台运行：

```bash
tar -xzf service-monitor-server-*.tar.gz
./start.sh
```

`start.sh` 会校验平台、SHA-256 和二进制自检，首次创建 `data/`、`certs/` 和权限 `0600` 的 `.service-monitor.env`，然后打印随机管理员密码。再次运行复用原配置和密码。使用 `Ctrl+C` 停止，可通过 `PORT=9000 ./start.sh` 覆盖 HTTP 端口。

需要 systemd 守护和开机自启时使用安装脚本：

```bash
tar -xzf service-monitor-server-*.tar.gz
sudo ./install.sh service-monitor-server-linux-x86_64-glibc217
sudo editor /etc/service-monitor/service-monitor.env
sudo systemctl start service-monitor-backend
```

安装器会校验主机 CPU 架构、glibc 版本和二进制 `--self-test`，不匹配时不会替换已安装的 Server。`uname -m` 输出 `x86_64` 时选择 `x86_64` 产物，输出 `aarch64` 时选择 `arm64` 产物。

新配置默认同时启动 Agent TLS gRPC 控制面，并在 `AGENT_GRPC_CERT_DIR` 生成当前实例独有 CA 和 Server 证书。已有外部证书的部署可继续显式配置 `AGENT_GRPC_CERT_FILE`、`AGENT_GRPC_KEY_FILE` 和可选 `AGENT_GRPC_CA_FILE`。
