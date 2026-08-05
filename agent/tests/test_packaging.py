import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT.parent / "scripts" / "platform.sh"
PYINSTALLER_RUNTIME = ROOT.parent / "scripts" / "pyinstaller-runtime.sh"


def select(product, architecture, libc):
    result = subprocess.run(
        [
            "sh",
            "-c",
            f'. "{PLATFORM}"; select_artifact_for "$1" "$2" "$3"',
            "sh",
            product,
            architecture,
            libc,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_selects_exact_architecture_and_oldest_compatible_glibc():
    assert select("agent", "x86_64", "2.17") == "service-monitor-agent-linux-x86_64-glibc217"
    assert select("server", "aarch64", "2.28") == "service-monitor-server-linux-arm64-glibc228"


def test_selects_glibc228_for_newer_glibc():
    assert select("agent", "amd64", "2.34") == "service-monitor-agent-linux-x86_64-glibc228"


def test_rejects_unsupported_architecture_and_libc():
    for architecture, libc in (("mips64", "2.34"), ("x86_64", "1.99"), ("x86_64", "musl-1.2.4")):
        result = subprocess.run(
            ["sh", "-c", f'. "{PLATFORM}"; select_artifact "$1" "$2"', "sh", architecture, libc],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


def compatible(product, artifact, architecture, libc):
    return subprocess.run(
        [
            "sh",
            "-c",
            f'. "{PLATFORM}"; artifact_is_compatible "$1" "$2" "$3" "$4"',
            "sh",
            product,
            artifact,
            architecture,
            libc,
        ],
        capture_output=True,
        text=True,
    )


def test_accepts_older_glibc_baseline_on_newer_host():
    result = compatible("server", "service-monitor-server-linux-x86_64-glibc217", "x86_64", "2.34")
    assert result.returncode == 0


def test_rejects_wrong_architecture_or_newer_glibc_baseline():
    wrong_arch = compatible("server", "service-monitor-server-linux-arm64-glibc217", "x86_64", "2.34")
    assert wrong_arch.returncode != 0
    assert "架构" in wrong_arch.stderr

    newer_glibc = compatible("server", "service-monitor-server-linux-x86_64-glibc228", "x86_64", "2.17")
    assert newer_glibc.returncode != 0
    assert "glibc" in newer_glibc.stderr


def test_finds_required_pyinstaller_runtime_library(tmp_path):
    library = tmp_path / "libcrypt.so.2"
    library.touch()
    result = subprocess.run(
        ["sh", "-c", f'. "{PYINSTALLER_RUNTIME}"; find_runtime_library libcrypt.so.2'],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "RUNTIME_LIBRARY_DIRS": str(tmp_path)},
    )
    assert result.stdout.strip() == str(library)


def test_rejects_missing_pyinstaller_runtime_library(tmp_path):
    result = subprocess.run(
        ["sh", "-c", f'. "{PYINSTALLER_RUNTIME}"; find_runtime_library libcrypt.so.2'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "RUNTIME_LIBRARY_DIRS": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "libcrypt.so.2" in result.stderr
