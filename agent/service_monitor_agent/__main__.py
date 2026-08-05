import argparse
import logging

from .client import AgentAuthenticationError, AgentClient
from .config import load_config
from .runtime import AgentRuntime
from .storage import AgentStorage


DEFAULT_CONFIG_PATH = "/etc/service-monitor-agent/agent.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="服务监控 Agent")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        print("service-monitor-agent self-test ok")
        return 0
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    storage = AgentStorage(config.state_path)
    client = AgentClient(
        config.center_url,
        config.ca_file,
        tls_server_name=config.tls_server_name,
    )
    try:
        AgentRuntime(config, storage, client).run_forever()
    except AgentAuthenticationError:
        logging.exception("Agent 密钥已失效，停止运行")
        return 2
    except KeyboardInterrupt:
        return 0
    finally:
        storage.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
