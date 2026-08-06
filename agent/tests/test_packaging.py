import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT.parent / "scripts" / "platform.sh"
PYINSTALLER_RUNTIME = ROOT.parent / "scripts" / "pyinstaller-runtime.sh"
INSTALLER = ROOT / "packaging" / "install.sh"


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


def linked_libcrypt(tmp_path, soname):
    tmp_path.mkdir(parents=True)
    library = tmp_path / soname
    library.touch()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ldd = fake_bin / "ldd"
    ldd.write_text(
        "#!/bin/sh\n"
        f"printf 'libcrypt.so.{soname.rsplit('.', 1)[1]} => {library} (0x0000)\\n'\n"
    )
    ldd.chmod(0o755)
    binary = tmp_path / "libpython3.9.so.1.0"
    binary.touch()
    return subprocess.run(
        ["sh", "-c", f'. "{PYINSTALLER_RUNTIME}"; find_linked_libcrypt "$1"', "sh", str(binary)],
        capture_output=True,
        text=True,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
    )


def test_detects_the_libcrypt_soname_linked_by_libpython(tmp_path):
    libcrypt1 = linked_libcrypt(tmp_path / "one", "libcrypt.so.1")
    libcrypt2 = linked_libcrypt(tmp_path / "two", "libcrypt.so.2")

    assert libcrypt1.returncode == 0
    assert libcrypt1.stdout.strip().endswith("libcrypt.so.1")
    assert libcrypt2.returncode == 0
    assert libcrypt2.stdout.strip().endswith("libcrypt.so.2")


def test_collects_libcrypt_from_python_extension_modules(tmp_path):
    library = tmp_path / "libcrypt.so.1"
    library.touch()
    libpython = tmp_path / "libpython3.9.so.1.0"
    libpython.touch()
    dynload = tmp_path / "lib-dynload"
    dynload.mkdir()
    crypt_extension = dynload / "_crypt.cpython-39-x86_64-linux-gnu.so"
    crypt_extension.touch()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    ldd = fake_bin / "ldd"
    ldd.write_text(
        "#!/bin/sh\n"
        f"case \"$1\" in *_crypt*.so) printf 'libcrypt.so.1 => {library} (0x0000)\\n' ;; esac\n"
    )
    ldd.chmod(0o755)

    result = subprocess.run(
        [
            "sh",
            "-c",
            f'. "{PYINSTALLER_RUNTIME}"; find_python_libcrypt_dependencies "$1" "$2"',
            "sh",
            str(libpython),
            str(dynload),
        ],
        capture_output=True,
        text=True,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == str(library)


def test_build_scripts_use_linked_libcrypt_instead_of_artifact_name():
    server_build = (ROOT.parent / "backend" / "packaging" / "build.sh").read_text()
    agent_build = (ROOT / "packaging" / "build.sh").read_text()

    assert "find_python_libcrypt_dependencies" in server_build
    assert "find_python_libcrypt_dependencies" in agent_build
    assert "libcrypt_bundle_required" not in server_build
    assert "libcrypt_bundle_required" not in agent_build
    assert "/opt/service-monitor-python/lib" not in server_build
    assert "/opt/service-monitor-python/lib" not in agent_build


def test_rejects_missing_pyinstaller_runtime_library(tmp_path):
    result = subprocess.run(
        ["sh", "-c", f'. "{PYINSTALLER_RUNTIME}"; find_runtime_library libcrypt.so.2'],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "RUNTIME_LIBRARY_DIRS": str(tmp_path)},
    )
    assert result.returncode != 0
    assert "libcrypt.so.2" in result.stderr


def test_agent_ca_is_validated_before_installed_files_are_replaced():
    script = INSTALLER.read_text()

    assert script.index('Agent 公共 CA 文件不存在') < script.index(
        'install -m 0755 "$binary" "$BIN_PATH"'
    )
