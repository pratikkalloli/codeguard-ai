"""Docker-backed local runner for isolated Python snippets.

This is a learning/development sandbox, not a production security boundary.
It runs no container until the configured Python image is already present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any


PYTHON_IMAGE = "python:3.12-slim"
MAX_CODE_BYTES = 128 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 3
MAX_TIMEOUT_SECONDS = 10
MAX_TEST_CASES = 10
CONTAINER_STARTUP_GRACE_SECONDS = 15
MAX_SUPERVISOR_OUTPUT_BYTES = 512 * 1024
RESULT_MARKER = "__CODEGUARD_METRICS__"

_SUPERVISOR_TEMPLATE = r'''import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

_source_length = int(os.environ["CODEGUARD_SOURCE_LENGTH"])
_source = sys.stdin.buffer.read(_source_length).decode("utf-8")
_captured = {"stdout": bytearray(), "stderr": bytearray()}
_lock = threading.Lock()
_output_size = 0
_output_limit = threading.Event()
_limit = __OUTPUT_LIMIT__

def _drain(name, stream):
    global _output_size
    while True:
        _chunk = stream.read(4096)
        if not _chunk:
            return
        with _lock:
            _remaining = max(0, _limit - _output_size)
            if _remaining:
                _accepted = _chunk[:_remaining]
                _captured[name].extend(_accepted)
                _output_size += len(_accepted)
            if len(_chunk) > _remaining:
                _output_limit.set()

_timed_out = False
_returncode = 1
_script_path = None
_start_ns = time.perf_counter_ns()
try:
    with tempfile.TemporaryDirectory(prefix="codeguard-", dir="/tmp") as _temp:
        _script_path = os.path.join(_temp, "submitted.py")
        Path(_script_path).write_text(_source, encoding="utf-8")
        _child = subprocess.Popen(
            [sys.executable, "-I", _script_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        _out_thread = threading.Thread(target=_drain, args=("stdout", _child.stdout), daemon=True)
        _err_thread = threading.Thread(target=_drain, args=("stderr", _child.stderr), daemon=True)
        _out_thread.start()
        _err_thread.start()
        _deadline = time.monotonic() + __TIMEOUT__
        while _child.poll() is None:
            if _output_limit.is_set():
                try:
                    os.killpg(_child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            if time.monotonic() >= _deadline:
                _timed_out = True
                try:
                    os.killpg(_child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.005)
        _returncode = _child.wait()
        _out_thread.join(timeout=2)
        _err_thread.join(timeout=2)
        _process_ns = time.perf_counter_ns() - _start_ns
        try:
            _memory_peak = int(Path("/sys/fs/cgroup/memory.peak").read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            _memory_peak = None
        _payload = {
            "process_wall_ns": _process_ns,
            "returncode": _returncode,
            "timed_out": _timed_out,
            "output_limit_exceeded": _output_limit.is_set(),
            "stdout": bytes(_captured["stdout"]).decode("utf-8", errors="replace"),
            "stderr": bytes(_captured["stderr"]).decode("utf-8", errors="replace"),
            "memory_peak_bytes": _memory_peak,
        }
        sys.stdout.write("__CODEGUARD_METRICS__" + json.dumps(_payload, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        if _timed_out:
            sys.exit(124)
        if _output_limit.is_set():
            sys.exit(125)
        sys.exit(0 if _returncode == 0 else 1)
except Exception as _error:
    sys.stderr.write(type(_error).__name__ + ": " + str(_error) + "\n")
    raise
'''


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_seconds: float = 0.0
    engine_check_seconds: float | None = None
    code_execution_seconds: float | None = None
    image_readiness_seconds: float | None = None
    container_startup_seconds: float | None = None
    container_startup_measurement_type: str = "Unavailable"
    docker_run_seconds: float | None = None
    docker_overhead_estimate_seconds: float | None = None
    docker_overhead_measurement_type: str = "Unavailable"
    memory_peak_bytes: int | None = None
    code_time_measurement_type: str = "Unavailable"
    memory_measurement_type: str = "Unavailable"


@dataclass(frozen=True)
class FunctionTestResult:
    test_name: str
    status: str
    expected_output: str
    inputs_json: str = ""
    actual_output: str = ""
    error_message: str = ""
    duration_seconds: float = 0.0
    code_execution_seconds: float | None = None
    memory_peak_bytes: int | None = None
    code_time_measurement_type: str = "Unavailable"
    memory_measurement_type: str = "Unavailable"


def _find_docker() -> str | None:
    executable = shutil.which("docker")
    if executable:
        return executable
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
    ]
    return next((str(path) for path in candidates if path.is_file()), None)


def _docker_environment(docker: str) -> dict[str, str]:
    """Make Docker Desktop's per-user credential helpers discoverable."""
    environment = os.environ.copy()
    docker_folder = str(Path(docker).resolve().parent)
    path_entries = environment.get("PATH", "").split(os.pathsep)
    if docker_folder.lower() not in {entry.lower() for entry in path_entries}:
        environment["PATH"] = docker_folder + os.pathsep + environment.get("PATH", "")
    return environment


def _simple_result(status: str, message: str, started: float) -> ExecutionResult:
    return ExecutionResult(
        status=status,
        stderr=message,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def _json_values_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without treating booleans as integers."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_values_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    return left == right


def _container_id(cid_file: Path) -> str | None:
    try:
        value = cid_file.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None
    return value if re.fullmatch(r"[0-9a-f]{12,64}", value) else None


def _stop_container(docker: str, cid_file: Path, process: subprocess.Popen[bytes]) -> None:
    container_id = _container_id(cid_file)
    if container_id:
        try:
            subprocess.run(
                [docker, "kill", container_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_docker_environment(docker),
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass


def _container_startup_and_remove(
    docker: str, cid_file: Path, requested_at: datetime
) -> float | None:
    """Read the engine's container start timestamp, then remove the stopped container."""
    container_id = _container_id(cid_file)
    if not container_id:
        return None
    startup_seconds: float | None = None
    try:
        inspected = subprocess.run(
            [docker, "inspect", "--format", "{{.State.StartedAt}}", container_id],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=_docker_environment(docker),
            timeout=5,
            check=False,
        )
        if inspected.returncode == 0:
            stamp = inspected.stdout.strip()
            if stamp and not stamp.startswith("0001-"):
                started_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                startup_seconds = (started_at - requested_at).total_seconds()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        startup_seconds = None
    finally:
        try:
            subprocess.run(
                [docker, "rm", "-f", container_id],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_docker_environment(docker),
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return startup_seconds


def run_python(
    code: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    *,
    docker_executable: str | None = None,
) -> ExecutionResult:
    """Run source via stdin inside a tightly restricted Docker container.

    No project files, user folders, or host volumes are mounted. The container
    has no network, a read-only root filesystem, a non-root UID, dropped Linux
    capabilities, and bounded CPU, memory, process count, temporary storage,
    wall time, and captured output. An in-container supervisor times a child
    Python process, separately from Docker setup. This reduces risk but does not
    guarantee safety against container-runtime or kernel vulnerabilities.
    """
    started = time.monotonic()
    if not isinstance(code, str) or not code.strip():
        return _simple_result("Security blocked", "No Python code was supplied.", started)
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return _simple_result("Security blocked", "Code exceeds the 128 KiB input limit.", started)
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        return _simple_result("Security blocked", f"Timeout must be an integer from 1 to {MAX_TIMEOUT_SECONDS} seconds.", started)

    docker = docker_executable or _find_docker()
    if not docker:
        return _simple_result("Execution error", "Docker CLI was not found. Install Docker Desktop and restart the terminal.", started)
    docker_env = _docker_environment(docker)

    engine_started = time.monotonic()
    try:
        engine = subprocess.run(
            [docker, "info", "--format", "{{.OSType}}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=docker_env,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return _simple_result("Execution error", f"Could not connect to Docker: {error}", started)
    engine_check_seconds = time.monotonic() - engine_started
    if engine.returncode != 0 or engine.stdout.strip() != "linux":
        detail = engine.stderr.strip() or "Docker is not using a running Linux container engine."
        return _simple_result("Execution error", detail, started)

    image_check_started = time.monotonic()
    try:
        image = subprocess.run(
            [docker, "image", "inspect", PYTHON_IMAGE, "--format", "{{.Id}}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env=docker_env,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return _simple_result("Execution error", f"Could not inspect the Python image: {error}", started)
    image_readiness_seconds = time.monotonic() - image_check_started
    if image.returncode != 0:
        return _simple_result(
            "Execution error",
            f"Required image {PYTHON_IMAGE} is not downloaded. In PowerShell, run: docker pull {PYTHON_IMAGE}",
            started,
        )

    with tempfile.TemporaryDirectory(prefix="codeguard-") as temp_folder:
        cid_file = Path(temp_folder) / "container-id.txt"
        command = [
            docker,
            "run",
            "--pull=never",
            "--interactive",
            "--cidfile",
            str(cid_file),
            "--network=none",
            "--read-only",
            "--user=65534:65534",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--pids-limit=32",
            "--memory=128m",
            "--memory-swap=128m",
            "--cpus=0.5",
            "--ulimit=cpu=2:2",
            "--ulimit=fsize=1048576:1048576",
            "--ulimit=nofile=64:64",
            "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
            "--workdir=/tmp",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--env=PYTHONUNBUFFERED=1",
            f"--env=CODEGUARD_SOURCE_LENGTH={len(code.encode('utf-8'))}",
            PYTHON_IMAGE,
            "python",
            "-I",
            "-c",
            _SUPERVISOR_TEMPLATE.replace("__TIMEOUT__", repr(timeout_seconds)).replace(
                "__OUTPUT_LIMIT__", repr(MAX_OUTPUT_BYTES)
            ),
        ]
        docker_requested_at = datetime.now(timezone.utc)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=docker_env,
            )
        except OSError as error:
            return _simple_result("Execution error", f"Could not start Docker: {error}", started)
        docker_run_started = time.monotonic()

        output = {"stdout": bytearray(), "stderr": bytearray()}
        output_lock = threading.Lock()
        output_limit_exceeded = threading.Event()
        output_size = 0

        def drain(name: str, stream: Any) -> None:
            nonlocal output_size
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                with output_lock:
                    remaining = max(0, MAX_SUPERVISOR_OUTPUT_BYTES - output_size)
                    if remaining:
                        accepted = chunk[:remaining]
                        output[name].extend(accepted)
                        output_size += len(accepted)
                    if len(chunk) > remaining:
                        output_limit_exceeded.set()

        stdout_thread = threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True)
        stderr_thread = threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        try:
            process.stdin.write(code.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            try:
                process.stdin.close()
            except OSError:
                pass

        deadline = docker_run_started + timeout_seconds + CONTAINER_STARTUP_GRACE_SECONDS
        runner_timeout = False
        try:
            while process.poll() is None:
                if output_limit_exceeded.is_set():
                    _stop_container(docker, cid_file, process)
                    break
                if time.monotonic() >= deadline:
                    runner_timeout = True
                    _stop_container(docker, cid_file, process)
                    break
                time.sleep(0.025)
            if process.poll() is None:
                _stop_container(docker, cid_file, process)
            process.wait(timeout=4)
        except (OSError, subprocess.TimeoutExpired) as error:
            _stop_container(docker, cid_file, process)
            _container_startup_and_remove(docker, cid_file, docker_requested_at)
            return _simple_result("Execution error", f"Docker execution failed: {error}", started)
        finally:
            stdout_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

        stdout = output["stdout"].decode("utf-8", errors="replace")
        stderr = output["stderr"].decode("utf-8", errors="replace")
        docker_run_seconds = round(time.monotonic() - docker_run_started, 6)
        container_startup_seconds = _container_startup_and_remove(
            docker, cid_file, docker_requested_at
        )
        finished_at = time.monotonic()
        duration = round(finished_at - started, 6)
        if (
            container_startup_seconds is not None
            and not (0.001 <= container_startup_seconds <= CONTAINER_STARTUP_GRACE_SECONDS)
        ):
            container_startup_seconds = None
        startup_type = (
            "Docker engine StartedAt timestamp compared with Windows host clock; approximate"
            if container_startup_seconds is not None
            else "Unavailable: Docker Desktop engine/host timestamp was missing or unsynchronized"
        )
        if runner_timeout:
            status = "Timeout" if container_startup_seconds is not None else "Execution error"
            detail = "Container exceeded the outer startup/execution safety deadline."
            return ExecutionResult(
                status,
                stderr=detail,
                exit_code=process.returncode,
                duration_seconds=duration,
                engine_check_seconds=round(engine_check_seconds, 6),
                image_readiness_seconds=round(image_readiness_seconds, 6),
                container_startup_seconds=(
                    round(container_startup_seconds, 6) if container_startup_seconds is not None else None
                ),
                container_startup_measurement_type=startup_type,
                docker_run_seconds=docker_run_seconds,
                docker_overhead_estimate_seconds=round(docker_run_seconds, 6),
                docker_overhead_measurement_type="Approximate docker run lifetime; includes container startup and teardown; process time unavailable",
            )
        if output_limit_exceeded.is_set():
            return ExecutionResult("Security blocked", stderr="Runner protocol exceeded its output limit.", exit_code=process.returncode, duration_seconds=duration)

        metrics_line = next((line for line in stdout.splitlines() if line.startswith(RESULT_MARKER)), None)
        if metrics_line is None:
            detail = stderr.strip() or f"Docker runner exited with code {process.returncode} before returning measurements."
            return ExecutionResult("Execution error", stderr=detail, exit_code=process.returncode, duration_seconds=duration)
        try:
            metrics = json.loads(metrics_line[len(RESULT_MARKER):])
        except (json.JSONDecodeError, TypeError) as error:
            return ExecutionResult("Execution error", stderr=f"Could not parse runner measurements: {error}", exit_code=process.returncode, duration_seconds=duration)

        code_stdout = metrics.get("stdout", "")
        code_stderr = metrics.get("stderr", "")
        code_execution_seconds = max(0.0, float(metrics.get("process_wall_ns", 0)) / 1_000_000_000)
        overhead = (
            max(0.0, docker_run_seconds - code_execution_seconds)
        )
        overhead_type = (
            "Approximate remaining docker run time after subtracting in-container process wall time; includes supervisor and teardown"
        )
        if container_startup_seconds is None:
            overhead_type += "; container startup is included because its independent timestamp was unavailable"
        else:
            overhead = max(0.0, overhead - container_startup_seconds)
            overhead_type += "; container startup estimate is also subtracted"
        memory_peak_bytes = metrics.get("memory_peak_bytes")
        if not isinstance(memory_peak_bytes, int) or memory_peak_bytes < 0:
            memory_peak_bytes = None
        memory_type = (
            "Linux cgroup v2 memory.peak; whole container high-water mark, including Python runtime and sandbox overhead"
            if memory_peak_bytes is not None
            else "Unavailable: cgroup v2 memory.peak could not be read inside this container"
        )
        if metrics.get("timed_out"):
            status = "Timeout"
        elif metrics.get("output_limit_exceeded"):
            status = "Security blocked"
            code_stderr = "Output exceeded the 64 KiB combined limit; the container was stopped."
        else:
            status = "Passed" if metrics.get("returncode") == 0 else "Failed"
        code_measurement = (
            "In-container child-process wall time measured with time.perf_counter_ns; includes Python interpreter startup and exit, excludes Docker/image startup"
        )
        return ExecutionResult(
            status,
            stdout=code_stdout,
            stderr=code_stderr or stderr.strip(),
            exit_code=metrics.get("returncode"),
            duration_seconds=duration,
            engine_check_seconds=round(engine_check_seconds, 6),
            code_execution_seconds=round(code_execution_seconds, 6),
            image_readiness_seconds=round(image_readiness_seconds, 6),
            container_startup_seconds=(round(container_startup_seconds, 6) if container_startup_seconds is not None else None),
            container_startup_measurement_type=startup_type,
            docker_run_seconds=docker_run_seconds,
            docker_overhead_estimate_seconds=round(overhead, 6) if overhead is not None else None,
            docker_overhead_measurement_type=overhead_type,
            memory_peak_bytes=memory_peak_bytes,
            code_time_measurement_type=code_measurement,
            memory_measurement_type=memory_type,
        )


def run_function_tests(
    code: str,
    function_name: str,
    cases: list[dict[str, Any]],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[FunctionTestResult]:
    """Call a named function with JSON positional-argument cases in Docker."""
    if not re.fullmatch(r"[A-Za-z_]\w*", function_name or ""):
        return [FunctionTestResult("Setup", "security_blocked", "", error_message="Use a simple Python function name (letters, numbers, underscores).")]
    if not cases:
        return [FunctionTestResult("Setup", "execution_error", "", error_message="Add at least one test case.")]
    if len(cases) > MAX_TEST_CASES:
        return [FunctionTestResult("Setup", "security_blocked", "", error_message=f"At most {MAX_TEST_CASES} test cases are allowed per run.")]

    results: list[FunctionTestResult] = []
    for index, case in enumerate(cases, start=1):
        arguments = case.get("inputs")
        expected = case.get("expected")
        if not isinstance(arguments, list):
            results.append(FunctionTestResult(f"Test {index}", "execution_error", json.dumps(expected), error_message="Inputs must be a JSON array of positional arguments."))
            continue

        try:
            arguments_json = json.dumps(arguments, ensure_ascii=True, allow_nan=False)
            expected_text = json.dumps(expected, ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError) as error:
            results.append(FunctionTestResult(f"Test {index}", "execution_error", "", error_message=f"Test inputs and expected outputs must be standard JSON values: {error}"))
            continue
        function_literal = repr(function_name)
        harness = f"""
import contextlib as _cg_contextlib
import io as _cg_io
import json as _cg_json
_cg_function = globals().get({function_literal})
if not callable(_cg_function):
    raise NameError("Function {function_name} was not defined")
_cg_arguments = _cg_json.loads({arguments_json!r})
_cg_capture = _cg_io.StringIO()
with _cg_contextlib.redirect_stdout(_cg_capture):
    _cg_value = _cg_function(*_cg_arguments)
print("__CODEGUARD_RESULT__" + _cg_json.dumps(_cg_value, ensure_ascii=True, allow_nan=False))
"""
        result = run_python(code + "\n" + harness, timeout_seconds)
        actual_text = ""
        error_message = result.stderr.strip()
        status = result.status.lower().replace(" ", "_")
        if result.status == "Passed":
            marker = "__CODEGUARD_RESULT__"
            result_lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
            if not result_lines:
                status = "execution_error"
                error_message = "The function runner did not return a JSON value. Ensure the function returns a JSON-serializable value."
            else:
                try:
                    actual_value = json.loads(result_lines[-1][len(marker):])
                    actual_text = json.dumps(actual_value, ensure_ascii=True, allow_nan=False)
                    status = "passed" if _json_values_equal(actual_value, expected) else "failed"
                    error_message = "" if status == "passed" else "Returned value did not match the expected JSON value."
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    status = "execution_error"
                    error_message = f"Could not parse the function result as JSON: {error}"
        results.append(
            FunctionTestResult(
                test_name=f"Test {index}",
                status=status,
                expected_output=expected_text,
                inputs_json=arguments_json,
                actual_output=actual_text,
                error_message=error_message,
                duration_seconds=result.duration_seconds,
                code_execution_seconds=result.code_execution_seconds,
                memory_peak_bytes=result.memory_peak_bytes,
                code_time_measurement_type=result.code_time_measurement_type,
                memory_measurement_type=result.memory_measurement_type,
            )
        )
    return results
