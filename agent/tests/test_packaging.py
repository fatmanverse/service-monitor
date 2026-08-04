import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "packaging" / "platform.sh"


def select(architecture, libc):
    result = subprocess.run(
        ["sh", "-c", f'. "{PLATFORM}"; select_artifact "$1" "$2"', "sh", architecture, libc],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_selects_exact_architecture_and_oldest_compatible_glibc():
    assert select("x86_64", "2.17") == "service-monitor-agent-linux-x86_64-glibc217"
    assert select("aarch64", "2.28") == "service-monitor-agent-linux-arm64-glibc228"


def test_selects_glibc228_for_newer_glibc():
    assert select("amd64", "2.34") == "service-monitor-agent-linux-x86_64-glibc228"


def test_rejects_unsupported_architecture_and_libc():
    for architecture, libc in (("mips64", "2.34"), ("x86_64", "1.99"), ("x86_64", "musl-1.2.4")):
        result = subprocess.run(
            ["sh", "-c", f'. "{PLATFORM}"; select_artifact "$1" "$2"', "sh", architecture, libc],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

