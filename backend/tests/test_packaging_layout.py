from pathlib import Path
import hashlib
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_backend_packaging_files_exist():
    assert (ROOT / "packaging" / "build.sh").is_file()
    assert (ROOT / "packaging" / "start.sh").is_file()
    assert (ROOT / "packaging" / "service-monitor-backend.service").is_file()
    assert (ROOT / "packaging" / "entrypoint.py").is_file()


def test_frontend_bundle_is_resolved_from_pyinstaller_runtime(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.sys, "_MEIPASS", "/tmp/pyinstaller", raising=False)
    assert str(main.frontend_dist_path()).startswith("/tmp/pyinstaller")


def test_release_start_script_initializes_once_and_reuses_credentials(tmp_path):
    release = tmp_path / "release"
    fake_bin = tmp_path / "fake-bin"
    release.mkdir()
    fake_bin.mkdir()
    shutil.copy2(ROOT / "packaging" / "start.sh", release / "start.sh")
    shutil.copy2(ROOT.parent / "scripts" / "platform.sh", release / "platform.sh")
    artifact = release / "service-monitor-server-linux-x86_64-glibc217"
    artifact.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = --self-test ]; then exit 0; fi\n"
        "printf '%s\\n' \"$PORT|$DATABASE_URL|$AGENT_GRPC_CERT_DIR\" > started.env\n"
    )
    artifact.chmod(0o755)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_name(f"{artifact.name}.sha256").write_text(
        f"{digest}  {artifact.name}\n"
    )
    (fake_bin / "uname").write_text("#!/bin/sh\nprintf 'x86_64\\n'\n")
    (fake_bin / "getconf").write_text("#!/bin/sh\nprintf 'glibc 2.17\\n'\n")
    (fake_bin / "uname").chmod(0o755)
    (fake_bin / "getconf").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}

    first = subprocess.run(
        ["sh", str(release / "start.sh")],
        cwd=release,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    assert "管理员密码:" in first.stdout
    config = release / ".service-monitor.env"
    assert config.stat().st_mode & 0o777 == 0o600
    first_config = config.read_text()
    assert (release / "started.env").read_text().strip() == (
        "8000|sqlite:///./data/service_monitor.db|./certs"
    )

    second = subprocess.run(
        ["sh", str(release / "start.sh")],
        cwd=release,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert "管理员密码:" not in second.stdout
    assert config.read_text() == first_config
