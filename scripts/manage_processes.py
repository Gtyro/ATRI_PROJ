"""Linux screen lifecycle management; never adopt sessions by name alone."""

from __future__ import annotations

import fcntl
import json
import logging
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import subprocess
import sys
import time
import uuid

import psutil
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "logs" / "process-manager"
PYTHON = ROOT / ".venv" / "bin" / "python"
SCRIPT = Path(__file__).resolve()
SERVICES = ("napcat", "atri_bot")
MODES = {"dev", "start"}
CONFIG_ENVIRONMENTS = {"dev": "dev", "start": "prod"}
TIMEOUT = 45


class LifecycleError(RuntimeError):
    """Messages must contain no configuration values or application output."""


def command(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=10, **kwargs,
    )


def sessions() -> dict[str, list[str]]:
    result = command(["screen", "-ls"])
    found: dict[str, list[str]] = {}
    for session in re.findall(r"^\s+(\d+\.[^\s]+)\s+", result.stdout, re.M):
        name = session.split(".", 1)[1]
        found.setdefault(name, []).append(session)
    if result.returncode and "No Sockets found" not in result.stdout + result.stderr:
        raise LifecycleError("无法查询 screen 会话；未执行任何停止操作。")
    return found


def state_path(name: str) -> Path:
    return STATE / f"{name}.json"


def load_state(name: str) -> dict | None:
    try:
        value = json.loads(state_path(name).read_text())
        if not isinstance(value, dict):
            raise ValueError
        return value
    except FileNotFoundError:
        return None
    except (ValueError, OSError):
        raise LifecycleError(f"{name}: 归属记录不可读；拒绝接管或停止。") from None


def save_state(name: str, value: dict) -> None:
    temporary = STATE / f".{name}.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(value))
    temporary.replace(state_path(name))


def same_process(pid: int, created: float) -> bool:
    if not isinstance(pid, int) or not isinstance(created, (int, float)):
        return False
    try:
        proc = psutil.Process(pid)
        return proc.create_time() == created and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.Error, TypeError, ValueError):
        return False


def owned(name: str, record: dict, current: dict[str, list[str]]) -> bool:
    """Check recorded identity, PID reuse, working directory and private marker."""
    try:
        session = record["session"]
        pid = record["screen_pid"]
        if record["root"] != str(ROOT) or session != f"{pid}.{name}":
            return False
        if session not in current.get(name, []):
            return False
        if not same_process(pid, record["screen_created"]):
            return False
        proc = psutil.Process(pid)
        env = proc.environ()
        return (
            proc.name().lower() == "screen"
            and proc.cwd() == str(ROOT)
            and env.get("ATRI_SCREEN_OWNER") == record["owner"]
            and env.get("ATRI_SCREEN_ROOT") == str(ROOT)
        )
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


def napcat_source() -> tuple[Path, str]:
    qq = shutil.which("qq")
    if not qq:
        raise LifecycleError("缺少 qq；请由服务器运维恢复现有 QQ/NapCat 安装。")
    base = Path(qq).resolve().parent / "resources/app/app_launcher/napcat"
    candidates = [
        p for p in (base / "config").glob("onebot11_*.json")
        if re.fullmatch(r"onebot11_[0-9]+\.json", p.name)
    ]
    if len(candidates) != 1:
        raise LifecycleError("现有 NapCat 账号配置缺失或不唯一；拒绝猜测账号。")
    account = candidates[0].stem.removeprefix("onebot11_")
    if not (base / "config" / f"napcat_{account}.json").is_file():
        raise LifecycleError("现有 NapCat 账号配置未成对；拒绝猜测账号。")
    return base, account


def check_napcat_logging(base: Path, account: str) -> None:
    """Validate the deployed NapCat logging policy.

    NapCat creates its logger before the core reads account-scoped settings. The
    installed source then applies ``fileLog=false`` during core initialization;
    that ordering is the normal NapCat startup lifecycle, not a startup error.
    """
    try:
        for name in ("napcat.json", f"napcat_{account}.json"):
            config = json.loads((base / "config" / name).read_text())
            if config.get("fileLog") is not False:
                raise LifecycleError("NapCat 原始文件日志未关闭；为避免泄密，拒绝启动。")
    except (OSError, ValueError):
        raise LifecycleError("无法确认 NapCat 原始日志安全性；拒绝启动。") from None


def preflight(mode: str = "dev") -> None:
    environment = CONFIG_ENVIRONMENTS.get(mode)
    if environment is None:
        raise LifecycleError("未知运行模式；未启动任何负载。")
    for executable in ("screen", "xvfb-run", "Xvfb", "xauth", "qq"):
        if not shutil.which(executable):
            raise LifecycleError(f"缺少运行依赖：{executable}。")
    if not PYTHON.is_file() or not (ROOT / "bot.py").is_file():
        raise LifecycleError("缺少项目 .venv/bin/python 或 bot.py。")
    if not (ROOT / f".env.{environment}").is_file():
        raise LifecycleError(f"缺少 .env.{environment}；拒绝使用默认配置启动。")
    base, account = napcat_source()
    check_napcat_logging(base, account)


def redact(text: str, values: set[str]) -> str:
    # Remove control sequences first so ANSI codes cannot split a secret.
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    text = re.sub(r"\b\d{5,}\b", "[REDACTED]", text)
    text = re.sub(r"(?:https?|wss?)://[^\s\"'<>]+", "[REDACTED-URL]", text)
    return re.sub(
        r"(?i)((?:token|password|secret|api_key|access_key|account|uin)\s*[=:]\s*)\S+",
        r"\1[REDACTED]", text,
    )


def sensitive_values() -> set[str]:
    values: set[str] = set()

    def collect(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                collect(value)
        elif isinstance(obj, list):
            for value in obj:
                collect(value)
        elif isinstance(obj, str) and len(obj) >= 4:
            values.add(obj)

    for name in (".env.dev", ".env.prod"):
        collect(dict(dotenv_values(ROOT / name)))
    base, account = napcat_source()
    values.add(account)
    for path in (base / "config").glob("*.json"):
        collect(json.loads(path.read_text()))
    # Existing private application config; values remain in memory only.
    import yaml
    for path in (ROOT / "data").rglob("*.yaml"):
        collect(yaml.safe_load(path.read_text()))
    for key, value in os.environ.items():
        if re.search(r"(?i)token|secret|password|api_key|account", key) and value:
            values.add(value)
    return values


def run_bot() -> None:
    values = sensitive_values()
    original = logging.Formatter.format

    def safe_format(self, record):
        return redact(original(self, record), values)

    logging.Formatter.format = safe_format
    from loguru import logger

    def patch_record(record):
        record["message"] = redact(record["message"], values)

    logger.configure(patcher=patch_record)
    sys.path.insert(0, str(ROOT))
    sys.argv = [str(ROOT / "bot.py")]
    runpy.run_path(str(ROOT / "bot.py"), run_name="__main__")


def payload_members(record: dict) -> list[psutil.Process]:
    if not isinstance(record.get("owner"), str) or record.get("root") != str(ROOT):
        return []
    found = []
    for proc in psutil.process_iter():
        try:
            env = proc.environ()
            if (env.get("ATRI_PAYLOAD_OWNER") == record["owner"]
                    and env.get("ATRI_SCREEN_ROOT") == str(ROOT)
                    and proc.status() != psutil.STATUS_ZOMBIE):
                found.append(proc)
        except (psutil.Error, ProcessLookupError):
            continue
    return found


def terminate_payload(record: dict) -> None:
    # Verify every member separately, including orphaned QQ/Xvfb descendants.
    members = payload_members(record)
    for proc in members:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(members, timeout=8)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=3)


def should_record(line: str, mode: str) -> bool:
    if mode == "dev":
        return True
    return bool(re.search(
        r"(?i)(error|warn|warning|fatal|critical|exception|traceback|failed|failure|"
        r"crash|退出|错误|警告|异常|失败|崩溃)",
        line,
    ))


def supervise(name: str, owner: str, mode: str) -> int:
    if mode not in MODES:
        raise LifecycleError("未知运行模式；未启动任何负载。")
    os.chdir(ROOT)
    os.umask(0o077)
    screen = psutil.Process(os.getppid())
    if screen.name().lower() != "screen":
        raise LifecycleError("内部运行入口必须由 screen 调用。")
    record = {
        "root": str(ROOT), "owner": owner,
        "mode": mode,
        "session": f"{screen.pid}.{name}", "screen_pid": screen.pid,
        "screen_created": screen.create_time(), "supervisor_pid": os.getpid(),
        "supervisor_created": psutil.Process().create_time(),
    }
    save_state(name, record)
    proc = None

    def shutdown(_signum, _frame):
        terminate_payload(record)
        if proc is not None:
            proc.wait(timeout=3)
        raise SystemExit(0)

    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(sig, shutdown)
    values = sensitive_values()
    if name == "napcat":
        base, account = napcat_source()
        check_napcat_logging(base, account)
        args = ["xvfb-run", "-a", "qq", "--no-sandbox", "-q", account]
    else:
        args = [str(PYTHON), "-u", str(SCRIPT), "_bot"]
    with (STATE / f"{name}.log").open("a", buffering=1) as log:
        proc = subprocess.Popen(
            args, cwd=ROOT, start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "ATRI_PAYLOAD_OWNER": owner,
                "ENVIRONMENT": CONFIG_ENVIRONMENTS[mode],
            },
        )
        record.update(payload_pid=proc.pid, payload_created=psutil.Process(proc.pid).create_time())
        save_state(name, record)

        log.write(f"{name}: payload started\n")
        try:
            assert proc.stdout is not None
            for line in iter(proc.stdout.readline, b""):
                text = redact(line.decode("utf-8", errors="replace"), values)
                if should_record(text, mode):
                    log.write(text)
            code = proc.wait()
            log.write(f"{name}: payload exited (code={code})\n")
            return code
        finally:
            terminate_payload(record)


def healthy(name: str, record: dict, current: dict[str, list[str]]) -> bool:
    if not owned(name, record, current):
        return False
    try:
        if not same_process(record["supervisor_pid"], record["supervisor_created"]):
            return False
        if not same_process(record["payload_pid"], record["payload_created"]):
            return False
        payload = psutil.Process(record["payload_pid"])
        if payload.ppid() != record["supervisor_pid"]:
            return False
        if name == "napcat":
            return any(p.name().lower() == "qq" for p in [payload, *payload.children(recursive=True)])
        environment = CONFIG_ENVIRONMENTS.get(record.get("mode", "dev"), "dev")
        port = int(dotenv_values(ROOT / f".env.{environment}").get("PORT", "8080"))
        return any(
            c.status == psutil.CONN_LISTEN and c.laddr.port == port
            for c in payload.net_connections(kind="inet")
        )
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


def stop_one(name: str) -> None:
    record = load_state(name)
    if record is None:
        print(f"{name}: 无受管记录，未停止任何同名会话。")
        return
    current = sessions()
    if not owned(name, record, current):
        # Keep records for orphan recovery instead of losing their identities.
        alive = any(
            same_process(record.get(f"{role}_pid"), record.get(f"{role}_created"))
            for role in ("screen", "supervisor", "payload")
        )
        if alive or payload_members(record):
            raise LifecycleError(f"{name}: 归属验证失败且记录中的进程仍存在；未发送信号。")
        state_path(name).unlink()
        print(f"{name}: 已清理失效记录；同名非受管会话未受影响。")
        return
    pid = record["supervisor_pid"]
    if not same_process(pid, record["supervisor_created"]):
        raise LifecycleError(f"{name}: supervisor 归属不可确认；未发送信号。")
    supervisor = psutil.Process(pid)
    if supervisor.ppid() != record["screen_pid"] or supervisor.cwd() != str(ROOT):
        raise LifecycleError(f"{name}: supervisor 归属不匹配；未发送信号。")
    supervisor.send_signal(signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not any(
            same_process(record.get(f"{role}_pid"), record.get(f"{role}_created"))
            for role in ("screen", "supervisor", "payload")
        ) and not payload_members(record) and record["session"] not in sessions().get(name, []):
            state_path(name).unlink()
            print(f"{name}: 受管会话和进程已停止并验证。")
            return
        time.sleep(0.2)
    raise LifecycleError(f"{name}: 停止尚未完成，保留归属记录；未操作其他会话。")


def ensure(mode: str) -> None:
    if mode not in MODES:
        raise LifecycleError("未知运行模式；支持 dev、start、stop、status。")
    current = sessions()
    records = {name: load_state(name) for name in SERVICES}
    for name, record in records.items():
        if current.get(name) and (record is None or not owned(name, record, current)):
            raise LifecycleError(f"{name}: 存在同名非受管会话；拒绝接管或创建重复会话。")
        if len(current.get(name, [])) > 1:
            raise LifecycleError(f"{name}: 存在重复会话；拒绝自动处理。")
    all_healthy = all(healthy(name, records[name] or {}, current) for name in SERVICES)
    # Records written before mode-aware startup have no ``mode`` field.  If
    # their ownership and health are otherwise verified, treat them as the
    # original development-mode records instead of needlessly restarting them.
    same_mode = all(
        records[name]
        and records[name].get("mode", "dev") == mode
        for name in SERVICES
    )
    if all_healthy and same_mode:
        print(f"napcat / atri_bot: {mode} 模式已运行，未创建重复会话。")
        return
    preflight(mode)  # Validate both services before creating either session.
    mode_switch = any(record and record.get("mode") != mode for record in records.values())
    for name, record in records.items():
        if record and (mode_switch or not healthy(name, record, current)):
            stop_one(name)
            records[name] = None
    started: list[str] = []
    try:
        for name, record in records.items():
            if record:
                continue
            owner = uuid.uuid4().hex
            result = command(
                ["screen", "-c", "/dev/null", "-dmS", name,
                 str(PYTHON), "-u", str(SCRIPT), "_run", name, owner, mode],
                env={
                    **os.environ,
                    "ATRI_SCREEN_OWNER": owner,
                    "ATRI_SCREEN_ROOT": str(ROOT),
                    "ENVIRONMENT": CONFIG_ENVIRONMENTS[mode],
                },
            )
            if result.returncode:
                raise LifecycleError(f"{name}: screen 启动失败；未输出原始错误。")
            started.append(name)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and "payload_pid" not in (load_state(name) or {}):
                time.sleep(0.1)
            if "payload_pid" not in (load_state(name) or {}):
                raise LifecycleError(f"{name}: 未生成归属记录，启动失败。")
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            current = sessions()
            if all(healthy(n, load_state(n) or {}, current) for n in SERVICES):
                time.sleep(2)
                if all(healthy(n, load_state(n) or {}, sessions()) for n in SERVICES):
                    print(f"napcat / atri_bot: {mode} 模式的 screen 与负载存活，bot 已监听现有配置端口。")
                    return
            if any(not same_process((load_state(n) or {}).get("payload_pid"),
                                    (load_state(n) or {}).get("payload_created")) for n in started):
                raise LifecycleError("受管负载在启动期间退出；请检查脱敏日志。")
            time.sleep(0.3)
        raise LifecycleError("等待受管负载/机器人监听超时；请检查脱敏日志。")
    except (LifecycleError, OSError, subprocess.SubprocessError):
        for name in reversed(started):
            try:
                stop_one(name)
            except LifecycleError:
                print(f"{name}: 回滚未完成，保留归属记录供 stop 重试。")
        raise


def dev() -> None:
    """Start (or reconcile) the verbose development profile."""
    ensure("dev")


def start() -> None:
    """Start (or reconcile) the production profile."""
    ensure("start")


def main() -> int:
    os.chdir(ROOT)
    os.umask(0o077)
    if len(sys.argv) < 2:
        raise LifecycleError("缺少入口；支持 dev、start、stop、status。")
    action = sys.argv[1]
    if action == "_bot":
        run_bot()
        return 0
    if action == "_run" and len(sys.argv) == 5 and sys.argv[2] in SERVICES:
        return supervise(sys.argv[2], sys.argv[3], sys.argv[4])
    if action not in {"dev", "start", "stop", "status"}:
        raise LifecycleError("未知入口；支持 dev、start、stop、status。")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    with (STATE / "manager.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action in MODES:
            ensure(action)
        elif action == "stop":
            errors = []
            for name in reversed(SERVICES):
                try:
                    stop_one(name)
                except LifecycleError as exc:
                    errors.append(str(exc))
            if errors:
                raise LifecycleError("\n".join(errors))
        else:
            current = sessions()
            ok = True
            for name in SERVICES:
                running = healthy(name, load_state(name) or {}, current)
                print(f"{name}: {'受管且存活' if running else '未就绪或非受管'}")
                ok = ok and running
            return 0 if ok else 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LifecycleError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("进程管理操作失败；未输出可能包含配置值的原始错误。", file=sys.stderr)
        raise SystemExit(1)
