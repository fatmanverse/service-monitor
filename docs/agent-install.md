# Agent 安装与发布

Agent 以 PyInstaller 单文件运行，不要求目标节点安装 Python。GitHub Actions 在 tag（`v*`）或手动触发时构建四个 Linux 产物：

- `service-monitor-agent-linux-x86_64-glibc217`
- `service-monitor-agent-linux-x86_64-glibc228`
- `service-monitor-agent-linux-arm64-glibc217`
- `service-monitor-agent-linux-arm64-glibc228`

每个 release bundle 包含 Agent 二进制、SHA-256 文件、安装/卸载脚本和 systemd unit。glibc 2.17 构建使用 `manylinux2014`，glibc 2.28 构建使用 `manylinux_2_28`；ARM64 使用原生 ARM runner，兼容性 workflow 另外使用 QEMU 检查 ARM 镜像。

## 安装

先在管理端“Agent 接入”页下载当前 Server 的公共 CA，然后解压目标节点对应的 tar 包并执行：

```bash
sudo CA_FILE="$PWD/service-monitor-ca.crt" ./install.sh
sudo editor /etc/service-monitor-agent/agent.toml
sudo systemctl start service-monitor-agent
sudo systemctl status service-monitor-agent
```

安装器根据 `uname -m` 和 `getconf GNU_LIBC_VERSION` 选择产物。glibc 低于 2.17、musl、未知 libc 和不支持的架构会明确失败。重复安装不会覆盖 `agent.toml` 或 `/var/lib/service-monitor-agent/agent.db`。

新安装会将 CA 复制到 `/etc/service-monitor-agent/ca.crt`，并写入固定的 Server TLS 身份。只需将 `center_url` 改为实际内网 IP 或域名：

```toml
center_url = "grpcs://monitor.example:50051"
ca_file = "/etc/service-monitor-agent/ca.crt"
tls_server_name = "service-monitor-server"
heartbeat_interval = 30
state_path = "/var/lib/service-monitor-agent/agent.db"
```

通过 IP 连接时，`tls_server_name` 仍验证 Server 证书的 SAN，不会关闭 TLS 校验。外部公共 CA 签发的证书可不传 `CA_FILE`，并按证书域名配置 `center_url`。

首次运行会在状态库中生成 Agent 身份和 claim token。权限应保持为 root 可读，Agent 通过 gRPC 向中心申请审批；管理员批准后 Agent 自动领取独立密钥。

## 卸载

默认卸载只移除二进制和 systemd unit，保留配置与身份：

```bash
sudo ./uninstall.sh
```

只有明确传入 `--purge` 才会删除 `/etc/service-monitor-agent` 和 `/var/lib/service-monitor-agent`。

## 本地构建

在 manylinux 容器内运行构建脚本，并设置固定产物名称：

```bash
ARTIFACT_NAME=service-monitor-agent-linux-x86_64-glibc228 \
  OUTPUT_DIR="$PWD/dist/agent" \
  docker run --rm --platform linux/amd64 \
    -e ARTIFACT_NAME -e OUTPUT_DIR=/workspace/dist/agent \
    -v "$PWD:/workspace" -w /workspace \
    quay.io/pypa/manylinux_2_28_x86_64 \
    sh agent/packaging/build.sh
```

构建完成后，二进制会执行 `--self-test`，并生成同名 `.sha256` 文件。
