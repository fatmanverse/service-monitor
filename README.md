# 服务监控

单机部署的服务监控管理系统，后端使用 FastAPI + SQLite，前端使用 React + TypeScript。

## 能力

- 主机管理：SSH 节点配置、手动探活、定时探活，可为节点多选飞书机器人并接收离线和恢复告警。
- 服务监测：进程、systemd 服务、HTTP GET、HTTP POST 探活，支持请求头、JSON 请求体、Basic/Bearer 认证。
- 服务详情：独立路由展示本次探活结果、各检查项状态和最近 30 天历史。
- 监控生命周期：新服务默认停止定时探活，管理员显式启用/停止；手动探活离线后可确认拉起并复检。
- 资源组：服务单资源组归属，用户按资源组授权可见范围。
- 组合健康规则：一个服务可配置多个探活项，并使用任意嵌套 `AND` / `OR` 在线规则。
- 故障恢复：服务掉线后通过 SSH 执行启动命令，并再次确认状态。
- 告警管理：维护多个飞书机器人，一个服务可多选通知目标，离线与恢复时同时发送。
- 节点故障静默：节点离线期间暂停其所有服务探活、自动拉起和服务告警，服务保留最后一次状态；节点恢复后自动继续。
- 用户管理：管理员分配用户可见服务，非管理员只能读取获授权服务，所有用户均可校验旧密码后自助改密。
- 资源组授权：一个服务只属于一个资源组，用户可授权多个资源组。
- 多探活在线规则：服务可配置多个进程/GET/POST 探活项，并通过任意嵌套 `AND` / `OR` 规则判断在线。
- 数据一致性：删除主机时由数据库级联删除其服务、授权与探活记录。

## 开发启动

环境要求：Python 3.9+、Node.js 20.19+ 或 22.12+。Conda 环境可通过以下命令安装 Node.js 20：

```bash
conda install -c conda-forge "nodejs>=20.19,<21"
```

CentOS 7 等旧版 Linux 不要使用 NVM 下载的官方 Node.js 20 二进制，该二进制要求 `glibc 2.28+`。应先执行 `nvm deactivate`，再使用 conda-forge 安装兼容旧系统 ABI 的 Node.js。

首次安装也可以直接执行：

```bash
sh scripts/setup.sh
```

首次安装会生成 `backend/.env`，其中包含随机 `APP_SECRET` 和初始管理员密码，文件权限为 `600`；重复安装不会覆盖。查看初始密码：

```bash
cat backend/.env
```

安装脚本默认使用全局 Python（macOS 优先使用 Homebrew Python），并优先寻找当前 Conda 环境或 `miniconda3/bin` 中的 Node.js，再使用腾讯云 HTTP PyPI 镜像。`greenlet` 固定使用二进制 wheel，不要求服务器安装 C++ 编译器。需要指定已有 Python、Node 或其他镜像时：

```bash
PYTHON_BIN=/path/to/python \
NODE_BIN=/path/to/node \
NPM_BIN=/path/to/npm \
PYPI_INDEX_URL=http://mirrors.cloud.tencent.com/pypi/simple/ \
PYPI_TRUSTED_HOST=mirrors.cloud.tencent.com \
sh scripts/setup.sh
```

后端：

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

单进程部署：

```bash
cd frontend
npm install
npm run build
cd ../backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端构建目录存在时，FastAPI 会直接托管 `frontend/dist`。

安装完成后可直接执行 `sh scripts/start.sh`，脚本会加载 `backend/.env`。命令行提供的同名环境变量优先级更高。

首次启动会创建管理员，默认账号为 `admin`，密码由安装脚本生成。`APP_SECRET` 用于 SSH 密码等敏感数据加密，投入使用后不要更换，否则历史密文将无法解密。

升级已有数据库时，启动会自动执行幂等迁移：旧服务会获得迁移资源组和探活项，旧用户直授权会转换为资源组授权，旧飞书配置会迁移为“默认飞书机器人”并关联原来启用告警的服务；旧表和旧列保留为迁移备份，不再参与运行时鉴权、探活或告警判断。

## 环境变量

- `DATABASE_URL`：默认 `sqlite:///./service_monitor.db`
- `APP_SECRET`：令牌签名及 SSH 密码加密密钥
- `INITIAL_ADMIN_USERNAME`：默认 `admin`
- `INITIAL_ADMIN_PASSWORD`：默认 `admin123`
- `ACCESS_TOKEN_MINUTES`：默认 `480`
- `SCHEDULER_ENABLED`：默认 `true`
- `MONITOR_WORKERS`：默认 `200`，限制并发 SSH/HTTP 探活数量；低配置机器可按资源下调
- `AGENT_GRPC_BIND`：Agent gRPC TLS 服务监听地址，默认 `[::]:50051`
- `AGENT_GRPC_CERT_DIR`：实例 CA 与 Server 证书目录，未显式配置证书时自动生成
- `AGENT_GRPC_TLS_SERVER_NAME`：生成证书的固定 TLS 身份，默认 `service-monitor-server`
- `AGENT_GRPC_CERT_FILE` / `AGENT_GRPC_KEY_FILE` / `AGENT_GRPC_CA_FILE`：可选的外部证书、私钥与公共 CA 路径

Agent 注册、领取、心跳、配置同步和结果上报使用独立的 gRPC 服务，不经过 FastAPI。管理后台仍使用 FastAPI 提供管理员审批、撤销、密钥轮换和命令查询。启动 gRPC 服务：

```bash
cd backend
python3 -m app.agent_grpc_server
```

Agent 的无 Python 部署、PyInstaller 构建、四套 glibc 产物和 systemd 安装见 [docs/agent-install.md](docs/agent-install.md)。推送 `v*` tag 或手动运行 `Build Service Monitor Agent` workflow 会构建并发布 GitHub Release 资产。

管理服务使用 `Build Service Monitor Server` workflow：先构建 React 静态资源，再将其嵌入后端 PyInstaller 二进制，发布 x86_64/ARM64 的 glibc 2.17/2.28 四套服务端包。每个包包含可在解压目录直接运行、自动生成随机密码的 `start.sh`，部署说明见 [docs/server-install.md](docs/server-install.md)。

## SSH 主机密钥

系统只信任运行账户 `known_hosts` 中已登记的 SSH 主机密钥，未知主机密钥会明确拒绝。首次接入节点前，可使用 `ssh-keyscan -H <主机地址> >> ~/.ssh/known_hosts` 登记并人工核对指纹。
