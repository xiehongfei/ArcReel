#!/usr/bin/env python3
"""本地开发服务管理：启动 / 停止 / 重启 / 状态 / 日志 / 环境检查。

    ./scripts/dev.py help              # 全部命令与参数
    ./scripts/dev.py setup             # 首次准备：依赖、.env、数据库、git 钩子
    ./scripts/dev.py start             # 后台启动后端 + 前端
    ./scripts/dev.py status            # 运行状态、端口与访问地址
    ./scripts/dev.py logs -f backend   # 跟踪后端日志
    ./scripts/dev.py stop              # 停止全部服务

直接执行即可：脚本只用标准库，不需要 uv / 项目 venv，Python 3.9+ 就行（macOS 自带
/usr/bin/python3 可用）；它在哪个目录被调用都行，工作目录按脚本位置推导。

端口与 CONTRIBUTING.md「本地开发环境」一致：后端 1241、前端 5173。服务各自在独立进程组里
后台运行，PID 与启动时间记在 .dev/run/，日志追加在 .dev/logs/。仅支持 POSIX 进程组信号，
即 macOS / Linux / WSL2。退出码：0 成功，1 检查或操作失败，2 用法错误。
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / ".dev"
LOG_DIR = DEV_DIR / "logs"
RUN_DIR = DEV_DIR / "run"
PROG = "./scripts/dev.py"

START_TIMEOUT_DEFAULT = 60.0
STOP_GRACE_DEFAULT = 10.0
POLL_INTERVAL = 0.2
# 收尾超过这个秒数就提示一次，避免 stop 看起来像卡住
SLOW_STOP_NOTICE = 3.0


@dataclass(frozen=True)
class Service:
    """一个开发服务：命令、端口、就绪探测与状态文件位置。"""

    key: str
    cwd: Path
    argv: tuple[str, ...]
    port: int
    url: str
    probe_url: str
    markers: tuple[str, ...]
    requires: Path

    @property
    def command(self) -> str:
        return " ".join(self.argv)

    @property
    def log_path(self) -> Path:
        return LOG_DIR / f"{self.key}.log"

    @property
    def state_path(self) -> Path:
        return RUN_DIR / f"{self.key}.json"


@dataclass(frozen=True)
class ServiceState:
    """启动时记下的进程信息，供 status 与 stop 使用。"""

    pid: int
    pgid: int
    started_at: float
    command: str


BACKEND = Service(
    key="backend",
    cwd=ROOT,
    # --reload-dir 必须限定目录：不限定的话 watchfiles 会扫描 node_modules / .venv / .git
    # / .worktrees 等数十万个文件，单核 CPU 占用超过 50%。
    argv=(
        "uv",
        "run",
        "uvicorn",
        "server.app:app",
        "--reload",
        "--reload-dir",
        "server",
        "--reload-dir",
        "lib",
        "--port",
        "1241",
    ),
    port=1241,
    url="http://127.0.0.1:1241",
    probe_url="http://127.0.0.1:1241/health",
    markers=("uvicorn",),
    requires=ROOT / ".venv",
)

FRONTEND = Service(
    key="frontend",
    cwd=ROOT / "frontend",
    argv=("pnpm", "dev"),
    port=5173,
    url="http://localhost:5173",
    probe_url="http://127.0.0.1:5173/",
    markers=("vite", "pnpm"),
    requires=ROOT / "frontend" / "node_modules",
)

SERVICES: tuple[Service, ...] = (BACKEND, FRONTEND)
SERVICE_TARGETS = ("all", "backend", "frontend")


# ---------------------------------------------------------------- 状态文件


def write_state(path: Path, state: ServiceState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_state(path: Path) -> ServiceState | None:
    """读取状态文件；缺失、损坏或字段类型不符时返回 None。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    pid = raw.get("pid")
    pgid = raw.get("pgid")
    started_at = raw.get("started_at")
    command = raw.get("command")
    if (
        not isinstance(pid, int)
        or not isinstance(pgid, int)
        or not isinstance(started_at, (int, float))
        or not isinstance(command, str)
    ):
        return None
    return ServiceState(pid=pid, pgid=pgid, started_at=float(started_at), command=command)


def clear_state(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


# ---------------------------------------------------------------- 进程与端口


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def reap_children() -> None:
    """回收本进程已结束的子进程；restart 在同一进程里 stop 时靠它避免把僵尸进程当存活。"""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def wait_process_exit(pid: int, timeout: float) -> bool:
    """等待进程退出；超时返回 False。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        reap_children()
        if not process_alive(pid):
            return True
        time.sleep(POLL_INTERVAL)
    reap_children()
    return not process_alive(pid)


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def wait_port_closed(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not port_open(port):
            return True
        time.sleep(POLL_INTERVAL)
    return not port_open(port)


def port_listener_pid(port: int) -> int | None:
    """端口上的监听进程 PID；lsof 缺失或未命中时返回 None。"""
    lsof = shutil.which("lsof")
    if lsof is None:
        return None
    result = subprocess.run(
        [lsof, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    for token in result.stdout.split():
        if token.isdigit():
            return int(token)
    return None


def http_ready(url: str, timeout: float = 1.0) -> bool:
    """URL 是否已有 HTTP 响应；连接失败才算未就绪，非 5xx 的响应都说明服务已在监听。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


def process_command(pid: int) -> str | None:
    ps = shutil.which("ps")
    if ps is None:
        return None
    result = subprocess.run([ps, "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=False)
    command = result.stdout.strip()
    return command or None


def command_matches(pid: int, markers: Sequence[str]) -> bool:
    """命令行里出现任一标记词即算匹配；读不到命令行时（ps 缺失）不拦。"""
    command = process_command(pid)
    return True if command is None else any(marker in command for marker in markers)


def group_members(pgid: int) -> list[int]:
    """进程组里仍然存活的 PID；ps 缺失时返回空列表。"""
    ps = shutil.which("ps")
    if ps is None:
        return []
    result = subprocess.run([ps, "-o", "pid=", "-g", str(pgid)], capture_output=True, text=True, check=False)
    return [int(token) for token in result.stdout.split() if token.isdigit()]


def capture_output(argv: Sequence[str]) -> str | None:
    """命令的首行输出版本号；命令缺失或输出为空时返回 None。"""
    if shutil.which(argv[0]) is None:
        return None
    result = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    text = result.stdout.strip() or result.stderr.strip()
    return text.splitlines()[0] if text else None


def enable_line_buffering() -> None:
    """管道与 CI 日志里 Python 默认块缓冲，启动进度会等到进程结束才可见。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(line_buffering=True)


def enable_default_sigpipe() -> None:
    """下游提前关闭管道（如 `help | head`）时按 Unix 惯例终止，而不是抛 BrokenPipeError。"""
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


# ---------------------------------------------------------------- 展示工具


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    days, remain = divmod(total, 86400)
    hours, remain = divmod(remain, 3600)
    minutes, secs = divmod(remain, 60)
    if days:
        return f"{days}d{hours}h"
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def tail_lines(handle: BinaryIO, count: int) -> list[str]:
    """句柄内容的末尾 count 行；读完句柄停在 EOF。"""
    return [line.decode("utf-8", "replace").rstrip("\r\n") for line in collections.deque(handle, maxlen=max(count, 0))]


def read_new_lines(handle: BinaryIO) -> Iterator[bytes]:
    """从当前位置读出所有完整行；末尾没写完的半行留到下次。"""
    while True:
        position = handle.tell()
        line = handle.readline()
        if not line:
            return
        if not line.endswith(b"\n"):
            handle.seek(position)
            return
        yield line


# ---------------------------------------------------------------- 命令实现


def resolve_services(target: str) -> tuple[Service, ...]:
    """把命令行的服务名解析成服务列表；all 即全部服务。"""
    if target == "all":
        return SERVICES
    for service in SERVICES:
        if service.key == target:
            return (service,)
    raise ValueError(f"未知服务: {target}")


def ensure_env_file() -> None:
    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if env_file.exists() or not example.exists():
        return
    shutil.copyfile(example, env_file)
    print("[准备] 由 .env.example 生成 .env（AUTH_PASSWORD 留空，首次启动自动生成）")


def start_banner(service: Service) -> bytes:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return f"\n===== {stamp} 启动 {service.command} =====\n".encode()


def print_tail(service: Service, count: int, indent: str = "") -> None:
    if not service.log_path.exists():
        return
    with service.log_path.open("rb") as handle:
        for line in tail_lines(handle, count):
            print(f"{indent}{line}")


def wait_ready(service: Service, process: subprocess.Popen[bytes], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        returncode = process.poll()
        if returncode is not None:
            print(f"[失败] {service.key} 启动即退出（退出码 {returncode}），日志末尾：")
            print_tail(service, 20, indent="       ")
            clear_state(service.state_path)
            return False
        if http_ready(service.probe_url):
            print(f"[就绪] {service.key}: {service.url}（pid {process.pid}）")
            return True
        time.sleep(POLL_INTERVAL)
    print(f"[警告] {service.key} 在 {timeout:.0f}s 内未就绪，进程仍在运行")
    print(f"       用 logs -f {service.key} 查看进度")
    return False


def start_service(service: Service, timeout: float) -> bool:
    state = read_state(service.state_path)
    if state is not None and process_alive(state.pid):
        print(f"[跳过] {service.key} 已在运行（pid {state.pid}）")
        return True
    if state is not None:
        print(f"[清理] {service.key}: 状态文件对应的进程已不存在")
        clear_state(service.state_path)
    if shutil.which(service.argv[0]) is None:
        print(f"[失败] {service.key}: 未找到命令 {service.argv[0]}，见 CONTRIBUTING.md「本地开发环境」")
        return False
    if not service.requires.exists():
        print(f"[失败] {service.key}: 缺少 {relative(service.requires)}")
        print(f"       先运行: {PROG} setup")
        return False
    if port_open(service.port):
        owner = port_listener_pid(service.port)
        holder = f"pid {owner}" if owner is not None else "未知进程"
        print(f"[失败] {service.key}: 端口 {service.port} 已被占用（{holder}）")
        print(f"       确认占用者后停止它，或用 stop {service.key} 清理本脚本启动的实例")
        return False
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with service.log_path.open("ab") as log_file:
        log_file.write(start_banner(service))
        log_file.flush()
        process = subprocess.Popen(
            list(service.argv),
            cwd=service.cwd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    write_state(
        service.state_path,
        ServiceState(pid=process.pid, pgid=process.pid, started_at=time.time(), command=service.command),
    )
    print(f"[启动] {service.key}: pid {process.pid}，命令 {service.command}")
    print(f"       日志 {relative(service.log_path)}")
    if timeout <= 0:
        return True
    return wait_ready(service, process, timeout)


def stop_service(service: Service, grace: float, *, force: bool) -> bool:
    state = read_state(service.state_path)
    if state is None:
        if port_open(service.port):
            owner = port_listener_pid(service.port)
            holder = f"pid {owner}" if owner is not None else "未知进程"
            print(f"[注意] {service.key} 不是本脚本启动的，但端口 {service.port} 被 {holder} 占用")
        else:
            print(f"[跳过] {service.key} 未在运行")
        return True
    if not process_alive(state.pid):
        clear_state(service.state_path)
        print(f"[清理] {service.key}: 进程已不存在，清除残留状态")
        return True
    if not force and not command_matches(state.pid, service.markers):
        actual = process_command(state.pid) or "（无法读取命令）"
        print(f"[失败] {service.key}: pid {state.pid} 的命令与记录不符，拒绝停止")
        print(f"       实际命令: {actual}")
        print("       确认是该服务后加 --force 重试")
        return False
    print(f"[停止] {service.key}: 发送 SIGTERM（pid {state.pid}）")
    with contextlib.suppress(ProcessLookupError):
        os.killpg(state.pgid, signal.SIGTERM)
    started = time.monotonic()
    announced = False
    while process_alive(state.pid) and time.monotonic() - started < grace:
        if not announced and time.monotonic() - started > SLOW_STOP_NOTICE:
            print(f"[等待] {service.key}: 仍在收尾，最多再等 {grace - SLOW_STOP_NOTICE:.0f}s")
            announced = True
        time.sleep(POLL_INTERVAL)
    reap_children()
    if process_alive(state.pid):
        survivors = "、".join(str(pid) for pid in group_members(state.pgid)) or "读不到进程列表"
        print(f"[超时] {service.key}: {grace:.0f}s 内未退出，发送 SIGKILL（残留 pid {survivors}）")
    with contextlib.suppress(ProcessLookupError):
        os.killpg(state.pgid, signal.SIGKILL)
    wait_process_exit(state.pid, 5.0)
    clear_state(service.state_path)
    if not wait_port_closed(service.port, 5.0):
        print(f"[注意] {service.key}: 端口 {service.port} 仍被占用，可能有残留进程")
        return False
    print(f"[完成] {service.key} 已停止")
    return True


def cmd_setup() -> int:
    ensure_env_file()
    steps: tuple[tuple[str, tuple[str, ...], Path], ...] = (
        ("同步后端依赖", ("uv", "sync"), ROOT),
        ("安装前端依赖", ("pnpm", "install"), ROOT / "frontend"),
        ("初始化数据库", ("uv", "run", "alembic", "upgrade", "head"), ROOT),
        ("安装 git 钩子", ("uv", "run", "pre-commit", "install"), ROOT),
    )
    for title, argv, cwd in steps:
        print(f"[setup] {title}: {' '.join(argv)}")
        result = subprocess.run(list(argv), cwd=cwd, check=False)
        if result.returncode != 0:
            print(f"[失败] {title} 退出码 {result.returncode}，修复后重跑 setup")
            return result.returncode if result.returncode > 0 else 1
    print(f"[完成] 环境就绪，启动: {PROG} start")
    return 0


def cmd_start(target: str, timeout: float) -> int:
    ensure_env_file()
    services = resolve_services(target)
    failed = [service.key for service in services if not start_service(service, timeout)]
    if failed:
        print(f"\n[失败] 未完成启动: {', '.join(failed)}")
        print(f"       查看日志: {PROG} logs -f")
        return 1
    print(f"\n[完成] 已启动: {', '.join(service.key for service in services)}")
    for service in services:
        print(f"       {service.key}: {service.url}")
    print(f"       查看状态: {PROG} status")
    print(f"       查看日志: {PROG} logs -f")
    print(f"       停止服务: {PROG} stop")
    return 0


def cmd_stop(target: str, grace: float, *, force: bool) -> int:
    services = resolve_services(target)
    failed = [service.key for service in reversed(services) if not stop_service(service, grace, force=force)]
    if failed:
        print(f"\n[失败] 未停止: {', '.join(failed)}")
        return 1
    return 0


def cmd_restart(target: str, timeout: float, *, force: bool) -> int:
    services = resolve_services(target)
    failed = [
        service.key for service in reversed(services) if not stop_service(service, STOP_GRACE_DEFAULT, force=force)
    ]
    if failed:
        print(f"\n[失败] 未停止: {', '.join(failed)}，已放弃重启")
        return 1
    return cmd_start(target, timeout)


def cmd_status() -> int:
    print(f"工作区 {ROOT}")
    running = 0
    for service in SERVICES:
        state = read_state(service.state_path)
        if state is not None and process_alive(state.pid):
            running += 1
            uptime = format_duration(time.time() - state.started_at)
            health = "就绪" if http_ready(service.probe_url) else "端口未响应"
            print(
                f"{service.key:<9}运行中  pid {state.pid}  端口 {service.port}  {service.url}  已运行 {uptime}  {health}"
            )
            continue
        detail = ""
        if port_open(service.port):
            owner = port_listener_pid(service.port)
            holder = f"，pid {owner}" if owner is not None else ""
            detail = f"（端口 {service.port} 被其他进程占用{holder}）"
        elif state is not None:
            detail = f"（残留状态文件 {relative(service.state_path)}，下次 start / stop 清理）"
        print(f"{service.key:<9}已停止  端口 {service.port}{detail}")
    print(f"\n日志目录 {relative(LOG_DIR)}    状态目录 {relative(RUN_DIR)}")
    print(f"查看日志: {PROG} logs -f")
    return 0 if running == len(SERVICES) else 1


def follow_logs(services: Sequence[Service], lines: int) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handles: dict[str, BinaryIO] = {}
    try:
        for service in services:
            service.log_path.touch(exist_ok=True)
            handle = service.log_path.open("rb")
            handles[service.key] = handle
            for line in tail_lines(handle, lines):
                print(f"[{service.key}] {line}", flush=True)
        print(f"[dev] 跟踪日志中（{', '.join(service.key for service in services)}），Ctrl-C 退出", flush=True)
        while True:
            wrote = False
            for service in services:
                for raw in read_new_lines(handles[service.key]):
                    print(f"[{service.key}] {raw.decode('utf-8', 'replace').rstrip()}", flush=True)
                    wrote = True
            time.sleep(0.1 if wrote else 0.3)
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        for handle in handles.values():
            handle.close()


def cmd_logs(target: str, lines: int, *, follow: bool) -> int:
    services = resolve_services(target)
    if follow:
        return follow_logs(services, lines)
    for index, service in enumerate(services):
        if index:
            print()
        print(f"===== {service.key}  {relative(service.log_path)} =====")
        if not service.log_path.exists():
            print("（尚无日志，服务未启动过）")
            continue
        with service.log_path.open("rb") as handle:
            content = tail_lines(handle, lines)
        if not content:
            print("（日志为空）")
        for line in content:
            print(line)
    return 0


def node_version_ok(version: str) -> bool:
    """Node.js 版本是否满足 CONTRIBUTING.md 的 24.12.0 下限；解析不出时放行。"""
    parts = version.strip().lstrip("v").split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1])
    except (IndexError, ValueError):
        return True
    return (major, minor) >= (24, 12)


def cmd_doctor() -> int:
    print(f"工作区 {ROOT}")
    problems: list[str] = []
    for name in ("uv", "node", "pnpm"):
        path = shutil.which(name)
        if path is None:
            problems.append(f"未找到 {name}，见 CONTRIBUTING.md「本地开发环境」")
            print(f"[缺少] {name}")
            continue
        print(f"[ok]   {name}: {capture_output((name, '--version')) or '版本未知'}  ({path})")
    node_version = capture_output(("node", "--version"))
    if node_version is not None and not node_version_ok(node_version):
        problems.append(f"Node.js {node_version} 低于要求的 24.12.0")
        print(f"[版本] Node.js {node_version} 低于 CONTRIBUTING.md 要求的 24.12.0")
    for label, path, hint in (
        (".env", ROOT / ".env", "start / setup 会由 .env.example 自动生成"),
        (".venv", ROOT / ".venv", "先运行 setup（uv sync）"),
        ("frontend/node_modules", ROOT / "frontend" / "node_modules", "先运行 setup（pnpm install）"),
    ):
        if path.exists():
            print(f"[ok]   {label} 存在")
        elif label == ".env":
            print(f"[注意] {label} 不存在：{hint}")
        else:
            problems.append(f"{label} 不存在：{hint}")
            print(f"[缺少] {label}：{hint}")
    for service in SERVICES:
        state = read_state(service.state_path)
        occupied = port_open(service.port)
        owner = port_listener_pid(service.port) if occupied else None
        if state is not None and process_alive(state.pid):
            print(f"[ok]   端口 {service.port}: 本项目 {service.key} 正在服务（pid {state.pid}）")
        elif owner is not None:
            problems.append(f"端口 {service.port} 被占用（pid {owner}）")
            print(f"[冲突] 端口 {service.port}: 被 pid {owner} 占用")
        elif occupied:
            problems.append(f"端口 {service.port} 被占用")
            print(f"[冲突] 端口 {service.port}: 已被占用")
        else:
            print(f"[ok]   端口 {service.port}: 空闲")
    if problems:
        print("\n发现的问题:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"\n环境检查通过，启动: {PROG} start")
    return 0


# ---------------------------------------------------------------- 命令行


def add_target(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=SERVICE_TARGETS,
        metavar="服务",
        help="backend / frontend / all（默认 all）",
    )


def add_help_argument(parser: argparse.ArgumentParser) -> None:
    """注册中文的 -h；调用方的 add_help 须为 False。"""
    parser.add_argument("-h", "--help", action="help", help="显示本帮助并退出")


def localize_group_titles(parser: argparse.ArgumentParser) -> None:
    """把 argparse 固定的英文分组标题换成中文；没有公开接口，只能改这两个属性。"""
    parser._positionals.title = "参数"
    parser._optionals.title = "选项"


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    parser = argparse.ArgumentParser(
        prog="scripts/dev.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    add_help_argument(parser)
    localize_group_titles(parser)
    subparsers = parser.add_subparsers(dest="command", metavar="命令")
    commands: dict[str, argparse.ArgumentParser] = {}

    def add_command(name: str, help_text: str) -> argparse.ArgumentParser:
        command = subparsers.add_parser(name, help=help_text, add_help=False)
        add_help_argument(command)
        localize_group_titles(command)
        return command

    commands["setup"] = add_command("setup", "首次准备：依赖、.env、数据库、git 钩子，可重复执行")

    commands["start"] = start = add_command("start", "启动服务（后台运行，日志落 .dev/logs/）")
    add_target(start)
    start.add_argument(
        "--timeout",
        type=float,
        default=START_TIMEOUT_DEFAULT,
        metavar="秒",
        help="等待就绪的最长秒数（默认 60；0 表示发完命令即返回）",
    )

    commands["stop"] = stop = add_command("stop", "停止服务")
    add_target(stop)
    stop.add_argument(
        "--timeout",
        type=float,
        default=STOP_GRACE_DEFAULT,
        metavar="秒",
        help="SIGTERM 宽限秒数，超时后 SIGKILL（默认 10）",
    )
    stop.add_argument("--force", action="store_true", help="跳过进程身份校验，强制停止")

    commands["restart"] = restart = add_command("restart", "重启服务（先 stop 再 start）")
    add_target(restart)
    restart.add_argument(
        "--timeout",
        type=float,
        default=START_TIMEOUT_DEFAULT,
        metavar="秒",
        help="重启后等待就绪的最长秒数（默认 60）",
    )
    restart.add_argument("--force", action="store_true", help="停止阶段跳过进程身份校验")

    commands["status"] = add_command("status", "查看运行状态、端口与访问地址")

    commands["logs"] = logs = add_command("logs", "查看日志（默认显示末尾 80 行）")
    add_target(logs)
    logs.add_argument("-f", "--follow", action="store_true", help="持续输出新日志，Ctrl-C 退出")
    logs.add_argument("-n", "--lines", type=int, default=80, metavar="行数", help="显示末尾多少行（默认 80）")

    commands["doctor"] = add_command("doctor", "检查本机依赖、配置与端口占用")
    commands["help"] = add_command("help", "显示全部命令与参数")
    return parser, commands


def print_all_help(parser: argparse.ArgumentParser, commands: dict[str, argparse.ArgumentParser]) -> None:
    parser.print_help()
    for command in commands.values():
        print()
        command.print_help()


def main(argv: list[str] | None = None) -> int:
    if os.name != "posix":
        print("本脚本依赖 POSIX 进程组信号，请在 macOS / Linux / WSL2 下运行。")
        return 2
    enable_default_sigpipe()
    enable_line_buffering()
    parser, commands = build_parser()
    args = parser.parse_args(argv)
    command: str | None = args.command
    if command == "help":
        print_all_help(parser, commands)
        return 0
    if command is None:
        parser.print_help()
        return 1
    if command == "setup":
        return cmd_setup()
    if command == "start":
        return cmd_start(args.target, args.timeout)
    if command == "stop":
        return cmd_stop(args.target, args.timeout, force=args.force)
    if command == "restart":
        return cmd_restart(args.target, args.timeout, force=args.force)
    if command == "status":
        return cmd_status()
    if command == "logs":
        return cmd_logs(args.target, args.lines, follow=args.follow)
    if command == "doctor":
        return cmd_doctor()
    raise AssertionError(f"未处理的命令: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
