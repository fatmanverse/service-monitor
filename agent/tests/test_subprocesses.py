from service_monitor_agent import subprocesses


BUNDLE_PATH = "/tmp/_MEI123456"


def test_environment_is_untouched_outside_a_bundle(monkeypatch):
    monkeypatch.delattr(subprocesses.sys, "_MEIPASS", raising=False)
    environ = {"LD_LIBRARY_PATH": "/opt/operator/lib", "PATH": "/usr/bin"}

    assert subprocesses.system_environment(environ) == environ


def test_bootloader_original_library_path_is_restored(monkeypatch):
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    environ = {
        "LD_LIBRARY_PATH": f"{BUNDLE_PATH}:/opt/operator/lib",
        "LD_LIBRARY_PATH_ORIG": "/opt/operator/lib",
        "PATH": "/usr/bin",
    }

    env = subprocesses.system_environment(environ)

    assert env["LD_LIBRARY_PATH"] == "/opt/operator/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env
    assert env["PATH"] == "/usr/bin"


def test_injected_library_path_is_dropped_when_there_was_no_original(monkeypatch):
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    environ = {"LD_LIBRARY_PATH": BUNDLE_PATH, "PATH": "/usr/bin"}

    env = subprocesses.system_environment(environ)

    assert "LD_LIBRARY_PATH" not in env
    assert env["PATH"] == "/usr/bin"


def test_empty_original_is_treated_as_absent(monkeypatch):
    """The bootloader writes an empty string when the caller had no value set."""
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    environ = {"LD_LIBRARY_PATH": BUNDLE_PATH, "LD_LIBRARY_PATH_ORIG": ""}

    env = subprocesses.system_environment(environ)

    assert "LD_LIBRARY_PATH" not in env
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_source_mapping_is_not_mutated(monkeypatch):
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    environ = {"LD_LIBRARY_PATH": BUNDLE_PATH, "LD_LIBRARY_PATH_ORIG": "/opt/lib"}

    subprocesses.system_environment(environ)

    assert environ["LD_LIBRARY_PATH"] == BUNDLE_PATH
    assert environ["LD_LIBRARY_PATH_ORIG"] == "/opt/lib"


def test_run_passes_the_cleaned_environment(monkeypatch):
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", f"{BUNDLE_PATH}:/opt/operator/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/opt/operator/lib")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")

    monkeypatch.setattr(subprocesses.subprocess, "run", fake_run)
    subprocesses.run(["systemctl", "is-active", "nginx"], check=False)

    assert captured["argv"] == ["systemctl", "is-active", "nginx"]
    assert captured["env"]["LD_LIBRARY_PATH"] == "/opt/operator/lib"


def test_run_respects_an_explicit_environment(monkeypatch):
    monkeypatch.setattr(subprocesses.sys, "_MEIPASS", BUNDLE_PATH, raising=False)
    captured = {}

    def fake_run(argv, **kwargs):
        captured["env"] = kwargs.get("env")

    monkeypatch.setattr(subprocesses.subprocess, "run", fake_run)
    subprocesses.run(["true"], env={"LD_LIBRARY_PATH": "/caller/choice"})

    assert captured["env"] == {"LD_LIBRARY_PATH": "/caller/choice"}
