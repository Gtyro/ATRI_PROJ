import json
import os
import shutil
import socket
import subprocess
from types import SimpleNamespace

import pytest

from scripts import manage_processes as manager
from scripts.restart_environment import detached_process_environment


class PrivateEnvironment(dict):
    def __repr__(self):
        return "<private test environment>"


def test_detached_restart_environment_drops_parent_ownership_markers():
    inherited = {
        "PATH": "/synthetic/bin",
        "ATRI_PAYLOAD_OWNER": "synthetic-payload-owner",
        "ATRI_SCREEN_OWNER": "synthetic-screen-owner",
        "ATRI_SCREEN_ROOT": "/synthetic/project",
    }

    detached = detached_process_environment(inherited)

    assert detached == {"PATH": "/synthetic/bin"}
    assert inherited["ATRI_PAYLOAD_OWNER"] == "synthetic-payload-owner"


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "ROOT", tmp_path)
    monkeypatch.setattr(manager, "STATE", tmp_path / "state")
    manager.STATE.mkdir()
    return tmp_path


def test_screen_names_are_matched_exactly(monkeypatch):
    output = "\t101.napcat\t(Detached)\n\t102.napcat_other\t(Detached)\n\t103.atri_bot\t(Detached)\n"
    monkeypatch.setattr(manager, "command", lambda *a, **kw: SimpleNamespace(
        stdout=output, stderr="", returncode=0))
    assert manager.sessions()["napcat"] == ["101.napcat"]


def test_screen_query_failure_is_not_treated_as_empty(monkeypatch):
    monkeypatch.setattr(manager, "command", lambda *a, **kw: SimpleNamespace(
        stdout="", stderr="permission error", returncode=1))
    with pytest.raises(manager.LifecycleError):
        manager.sessions()


def test_unmanaged_same_name_is_never_adopted_or_stopped(runtime, monkeypatch):
    monkeypatch.setattr(manager, "sessions", lambda: {"napcat": ["101.napcat"]})
    monkeypatch.setattr(manager, "command", lambda *a, **kw: pytest.fail("must not mutate"))
    with pytest.raises(manager.LifecycleError, match="同名非受管"):
        manager.dev()
    manager.stop_one("napcat")


def test_repeated_dev_does_not_start_another_screen(runtime, monkeypatch):
    for name in manager.SERVICES:
        manager.save_state(name, {"running": True})
    monkeypatch.setattr(manager, "sessions", lambda: {})
    monkeypatch.setattr(manager, "healthy", lambda *a: True)
    monkeypatch.setattr(manager, "preflight", lambda mode="dev": pytest.fail("already running"))
    monkeypatch.setattr(manager, "command", lambda *a, **kw: pytest.fail("duplicate start"))
    manager.dev()


def test_restart_bot_preserves_managed_mode_and_targets_only_bot(runtime, monkeypatch):
    manager.save_state("napcat", {"mode": "dev"})
    manager.save_state("atri_bot", {"mode": "dev"})
    calls = []
    monkeypatch.setattr(manager, "preflight", lambda mode: calls.append(("preflight", mode)))
    monkeypatch.setattr(manager, "stop_one", calls.append)
    monkeypatch.setattr(manager, "ensure", lambda mode: calls.append(("ensure", mode)))

    manager.restart_bot()

    assert calls == [("preflight", "dev"), "atri_bot", ("ensure", "dev")]


def test_napcat_normal_startup_order_is_allowed(runtime):
    config = runtime / "config"
    config.mkdir()
    account = "0" * 8  # Synthetic fixture; never an operational account.
    for name in ("napcat.json", f"napcat_{account}.json"):
        (config / name).write_text(json.dumps({"fileLog": False}))
    # NapCat's logger is constructed before the core applies fileLog=false.
    (runtime / "napcat.mjs").write_text("class LogWrapper { fileLogEnabled = true; }")
    manager.check_napcat_logging(runtime, account)


def test_napcat_logging_policy_still_requires_filelog_disabled(runtime):
    config = runtime / "config"
    config.mkdir()
    account = "0" * 8
    for name in ("napcat.json", f"napcat_{account}.json"):
        (config / name).write_text(json.dumps({"fileLog": False}))
    (config / f"napcat_{account}.json").write_text(json.dumps({"fileLog": True}))
    with pytest.raises(manager.LifecycleError, match="原始文件日志"):
        manager.check_napcat_logging(runtime, account)


def test_redaction_removes_values_ansi_accounts_and_url_credentials():
    synthetic = "fixture-sensitive-value"
    text = f"{synthetic[:8]}\x1b[31m{synthetic[8:]} token=fixture-token https://local/?token=x " + "0" * 8
    result = manager.redact(text, {synthetic})
    assert synthetic not in result
    assert "fixture-token" not in result
    assert "https://" not in result
    assert "0" * 8 not in result


def test_dev_keeps_diagnostic_lines_while_start_filters_them():
    assert manager.should_record("INFO connected to OneBot", "dev")
    assert not manager.should_record("INFO connected to OneBot", "start")
    assert manager.should_record("WARNING reconnecting", "start")
    assert manager.should_record("ERROR connection failed", "start")


def test_sensitive_values_reads_only_selected_environment(runtime, monkeypatch):
    (runtime / ".env.dev").write_text("DEV_SECRET=dev-only-value\n")
    (runtime / ".env.prod").write_text("PROD_SECRET=prod-only-value\n")
    monkeypatch.setattr(manager, "napcat_source", lambda: (runtime, "00000000"))
    (runtime / "config").mkdir()
    for name in ("napcat.json", "napcat_00000000.json"):
        (runtime / "config" / name).write_text("{}")

    values = manager.sensitive_values("dev")

    assert "dev-only-value" in values
    assert "prod-only-value" not in values


def test_preflight_rejects_unreadable_selected_environment(runtime, monkeypatch):
    env_path = runtime / ".env.dev"
    env_path.write_text("OPENAI_API_KEY=secret\n")
    (runtime / ".venv/bin").mkdir(parents=True)
    python_path = runtime / ".venv/bin/python"
    python_path.touch()
    (runtime / "bot.py").touch()
    monkeypatch.setattr(manager, "PYTHON", python_path)
    monkeypatch.setattr(manager.shutil, "which", lambda _: "/fixture/bin/dependency")
    monkeypatch.setattr(manager, "napcat_source", lambda: pytest.fail("must stop at env validation"))
    original_open = manager.Path.open

    def reject_selected_env(path, *args, **kwargs):
        if path == env_path:
            raise PermissionError
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(manager.Path, "open", reject_selected_env)

    with pytest.raises(manager.LifecycleError, match="无法读取 .env.dev"):
        manager.preflight("dev")


def test_mode_is_recorded_and_is_not_an_alias():
    assert manager.MODES == {"dev", "start"}
    assert manager.CONFIG_ENVIRONMENTS == {"dev": "dev", "start": "prod"}


def test_pid_reuse_fails_ownership_check(runtime, monkeypatch):
    record = {"root": str(runtime), "session": "101.napcat", "screen_pid": 101,
              "screen_created": 1.0, "owner": "fixture-owner"}
    monkeypatch.setattr(manager, "same_process", lambda *a: False)
    assert not manager.owned("napcat", record, {"napcat": ["101.napcat"]})


def test_missing_pid_is_not_current_process():
    assert not manager.same_process(None, None)


def test_stale_state_cleanup_preserves_unrelated_session(runtime, monkeypatch):
    manager.save_state("napcat", {"root": str(runtime), "screen_pid": 101,
                                 "screen_created": 1.0, "session": "101.napcat"})
    monkeypatch.setattr(manager, "sessions", lambda: {"napcat": ["102.napcat"]})
    monkeypatch.setattr(manager, "same_process", lambda *a: False)
    monkeypatch.setattr(manager, "command", lambda *a, **kw: pytest.fail("must not mutate"))
    manager.stop_one("napcat")
    assert not manager.state_path("napcat").exists()


def test_alive_unverified_record_is_retained(runtime, monkeypatch):
    manager.save_state("napcat", {"screen_pid": 101, "screen_created": 1.0})
    monkeypatch.setattr(manager, "sessions", lambda: {})
    monkeypatch.setattr(manager, "same_process", lambda *a: True)
    with pytest.raises(manager.LifecycleError, match="归属验证失败"):
        manager.stop_one("napcat")
    assert manager.state_path("napcat").exists()


def test_preflight_failure_creates_no_session(runtime, monkeypatch):
    monkeypatch.setattr(manager, "sessions", lambda: {})

    def reject(mode="dev"):
        raise manager.LifecycleError("fixture safety rejection")

    monkeypatch.setattr(manager, "preflight", reject)
    monkeypatch.setattr(manager, "command", lambda *a, **kw: pytest.fail("must not start"))
    with pytest.raises(manager.LifecycleError, match="safety rejection"):
        manager.dev()
    assert not list(manager.STATE.glob("*.json"))


def test_failed_second_launch_rolls_back_only_new_session(runtime, monkeypatch):
    monkeypatch.setattr(manager, "sessions", lambda: {})
    monkeypatch.setattr(manager, "preflight", lambda mode="dev": None)
    stopped = []

    def launch(args, **kwargs):
        name = args[args.index("-dmS") + 1]
        if name == "napcat":
            manager.save_state(name, {"payload_pid": 101})
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(manager, "command", launch)
    monkeypatch.setattr(manager, "stop_one", stopped.append)
    with pytest.raises(manager.LifecycleError, match="screen 启动失败"):
        manager.dev()
    assert stopped == ["napcat"]


def test_multiple_existing_accounts_are_rejected(runtime, monkeypatch):
    qq = runtime / "qq"
    qq.touch()
    config = runtime / "resources/app/app_launcher/napcat/config"
    config.mkdir(parents=True)
    for digit in ("0", "1"):
        (config / f"onebot11_{digit * 8}.json").write_text("{}")
    monkeypatch.setattr(manager.shutil, "which", lambda _: str(qq))
    with pytest.raises(manager.LifecycleError, match="不唯一"):
        manager.napcat_source()


@pytest.fixture
def isolated_screen(tmp_path):
    """Real screen, private socket directory, synthetic QQ/bot payloads."""
    if not shutil.which("screen"):
        pytest.skip("screen is not installed")
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(manager.SCRIPT, scripts / "manage_processes.py")
    venv = root / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").symlink_to(manager.PYTHON)
    (venv / "lib").symlink_to(manager.ROOT / ".venv/lib")
    shutil.copyfile(manager.ROOT / ".venv/pyvenv.cfg", venv / "pyvenv.cfg")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    (root / ".env.dev").write_text(f"PORT={port}\nLOG_LEVEL=DEBUG\n")
    (root / ".env.prod").write_text(f"PORT={port}\nLOG_LEVEL=INFO\n")
    (root / "bot.py").write_text(
        "import socket, time\n"
        "from dotenv import dotenv_values\n"
        "import os\n"
        "sock = socket.socket()\n"
        "env = os.environ.get('ENVIRONMENT', 'dev')\n"
        "sock.bind(('127.0.0.1', int(dotenv_values('.env.' + env)['PORT'])))\n"
        "sock.listen()\n"
        "while True: time.sleep(1)\n"
    )
    fakebin = root / "bin"
    fakebin.mkdir()
    qq = fakebin / "qq"
    qq.write_text(
        f"#!{venv / 'bin/python'}\n"
        "import ctypes, subprocess, time\n"
        "from pathlib import Path\n"
        "ctypes.CDLL(None).prctl(15, b'qq', 0, 0, 0)\n"
        "child = subprocess.Popen(['sleep', '300'])\n"
        "Path('child.pid').write_text(str(child.pid))\n"
        "while True: time.sleep(1)\n"
    )
    qq.chmod(0o700)
    xvfb = fakebin / "xvfb-run"
    xvfb.write_text('#!/bin/bash\nshift\nexec "$@"\n')
    xvfb.chmod(0o700)
    base = fakebin / "resources/app/app_launcher/napcat"
    (base / "config").mkdir(parents=True)
    account = "0" * 8
    for name in ("napcat.json", f"napcat_{account}.json", f"onebot11_{account}.json"):
        (base / "config" / name).write_text(json.dumps({"fileLog": False}))
    (base / "napcat.mjs").write_text(
        "class LogWrapper { fileLogEnabled = false; constructor() {"
        " const file = { silent: !this.fileLogEnabled }; } }"
    )
    screen_dir = tmp_path / "screens"
    screen_dir.mkdir(mode=0o700)
    env = PrivateEnvironment({**os.environ, "SCREENDIR": str(screen_dir),
                              "PATH": f"{fakebin}:{os.environ['PATH']}"})
    prefix = [str(venv / "bin/python"), str(scripts / "manage_processes.py")]

    def execute(action):
        return subprocess.run(prefix + [action], cwd=root, env=env,
                              capture_output=True, text=True, timeout=65)

    def query():
        return subprocess.run(["screen", "-ls"], cwd=root, env=env,
                              capture_output=True, text=True, timeout=10).stdout

    yield root, env, execute, query
    # Exact fixture identities only, in a socket directory created by this test.
    execute("stop")
    for line in query().splitlines():
        parts = line.split()
        if parts and parts[0].split(".", 1)[0].isdigit():
            subprocess.run(["screen", "-S", parts[0], "-X", "quit"], cwd=root,
                           env=env, capture_output=True, timeout=10)


def test_real_screen_lifecycle_preserves_foreign_session(isolated_screen):
    root, env, execute, query = isolated_screen
    subprocess.run(["screen", "-dmS", "unrelated", "sleep", "300"], cwd=root,
                   env=env, capture_output=True, check=True, timeout=10)
    result = execute("dev")
    assert result.returncode == 0, result.stdout + result.stderr
    state = root / "logs/process-manager"
    before = {name: (state / f"{name}.json").read_text() for name in manager.SERVICES}
    assert ".napcat\t" in query() and ".atri_bot\t" in query()
    assert execute("status").returncode == 0
    assert execute("dev").returncode == 0
    assert before == {name: (state / f"{name}.json").read_text() for name in manager.SERVICES}
    assert execute("start").returncode == 0
    assert all(
        json.loads((state / f"{name}.json").read_text())["mode"] == "start"
        for name in manager.SERVICES
    )
    napcat_screen = json.loads((state / "napcat.json").read_text())["screen_pid"]
    old_bot_screen = json.loads((state / "atri_bot.json").read_text())["screen_pid"]
    restarted = execute("restart_bot")
    assert restarted.returncode == 0, restarted.stdout + restarted.stderr
    assert json.loads((state / "napcat.json").read_text())["screen_pid"] == napcat_screen
    assert json.loads((state / "atri_bot.json").read_text())["screen_pid"] != old_bot_screen
    assert execute("status").returncode == 0
    child_pid = int((root / "child.pid").read_text())
    child_created = manager.psutil.Process(child_pid).create_time()
    assert execute("stop").returncode == 0
    assert not manager.same_process(child_pid, child_created)
    assert not list(state.glob("*.json"))
    remaining = query()
    assert ".napcat\t" not in remaining and ".atri_bot\t" not in remaining
    assert ".unrelated\t" in remaining
    assert execute("stop").returncode == 0
    assert (state.stat().st_mode & 0o777) == 0o700
    assert ((state / "napcat.log").stat().st_mode & 0o777) == 0o600


def test_real_unmanaged_collision_is_preserved(isolated_screen):
    root, env, execute, query = isolated_screen
    subprocess.run(["screen", "-dmS", "napcat", "sleep", "300"], cwd=root,
                   env=env, capture_output=True, check=True, timeout=10)
    result = execute("dev")
    assert result.returncode != 0
    assert "同名非受管" in result.stderr
    assert execute("stop").returncode == 0
    assert ".napcat\t" in query()
    assert ".atri_bot\t" not in query()
