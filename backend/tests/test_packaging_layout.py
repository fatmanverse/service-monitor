from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_packaging_files_exist():
    assert (ROOT / "packaging" / "build.sh").is_file()
    assert (ROOT / "packaging" / "service-monitor-backend.service").is_file()
    assert (ROOT / "packaging" / "entrypoint.py").is_file()


def test_frontend_bundle_is_resolved_from_pyinstaller_runtime(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.sys, "_MEIPASS", "/tmp/pyinstaller", raising=False)
    assert str(main.frontend_dist_path()).startswith("/tmp/pyinstaller")

