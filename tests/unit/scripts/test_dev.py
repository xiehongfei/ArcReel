import io
import os
import shutil
import subprocess
import sys

import pytest

from scripts.dev import (
    BACKEND,
    FRONTEND,
    SERVICES,
    ServiceState,
    clear_state,
    command_matches,
    format_duration,
    node_version_ok,
    process_alive,
    read_new_lines,
    read_state,
    resolve_services,
    tail_lines,
    write_state,
)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (59.9, "59s"),
        (60, "1m00s"),
        (3599, "59m59s"),
        (3600, "1h00m"),
        (86399, "23h59m"),
        (86400, "1d0h"),
        (90061, "1d1h"),
        (-5, "0s"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_resolve_services():
    assert resolve_services("all") == SERVICES
    assert resolve_services("backend") == (BACKEND,)
    assert resolve_services("frontend") == (FRONTEND,)


def test_resolve_services_rejects_unknown_target():
    with pytest.raises(ValueError, match="未知服务"):
        resolve_services("worker")


def test_state_round_trip(tmp_path):
    path = tmp_path / "run" / "backend.json"
    state = ServiceState(pid=1234, pgid=1234, started_at=1700000000.5, command="uv run uvicorn server.app:app")
    write_state(path, state)
    assert read_state(path) == state


def test_read_state_missing_file(tmp_path):
    assert read_state(tmp_path / "absent.json") is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        '{"pid": "1234", "pgid": 1234, "started_at": 1.0, "command": "x"}',
        '{"pid": 1234, "pgid": 1234, "command": "x"}',
        '{"pid": 1234, "pgid": 1234, "started_at": 1.0}',
    ],
)
def test_read_state_rejects_bad_payload(tmp_path, payload):
    path = tmp_path / "state.json"
    path.write_text(payload, encoding="utf-8")
    assert read_state(path) is None


def test_clear_state_is_idempotent(tmp_path):
    path = tmp_path / "state.json"
    write_state(path, ServiceState(pid=1, pgid=1, started_at=0.0, command="x"))
    clear_state(path)
    clear_state(path)
    assert not path.exists()


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (2, ["b", "c"]),
        (10, ["a", "b", "c"]),
        (0, []),
        (-1, []),
    ],
)
def test_tail_lines(count, expected):
    assert tail_lines(io.BytesIO(b"a\nb\nc\n"), count) == expected


def test_tail_lines_replaces_invalid_utf8():
    assert tail_lines(io.BytesIO(b"\xff\n"), 1) == ["\ufffd"]


def test_read_new_lines_waits_for_complete_line():
    handle = io.BytesIO(b"done\npartial")
    assert list(read_new_lines(handle)) == [b"done\n"]
    handle.seek(0, io.SEEK_END)
    handle.write(b" line\n")
    handle.seek(len(b"done\n"))
    assert list(read_new_lines(handle)) == [b"partial line\n"]


def test_process_alive_sees_own_process():
    assert process_alive(os.getpid())


def test_process_alive_is_false_after_exit():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    assert not process_alive(process.pid)


def test_command_matches_uses_process_command_line():
    if shutil.which("ps") is None:
        pytest.skip("环境里没有 ps，命令身份校验按放行处理")
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert command_matches(process.pid, ("python",))
        assert not command_matches(process.pid, ("uvicorn",))
    finally:
        process.terminate()
        process.wait()


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("v24.12.0", True),
        ("v24.11.9", False),
        ("v25.0.0", True),
        ("v22.14.0", False),
        ("unknown", True),
    ],
)
def test_node_version_ok(version, expected):
    assert node_version_ok(version) is expected
