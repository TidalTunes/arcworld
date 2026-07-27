"""Process isolation for generated world-model and plan code."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import threading
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

_WORKER = r"""
import copy
import json
import sys

try:
    import resource
    memory = 2 * 1024 * 1024 * 1024
    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        if hasattr(resource, name):
            try:
                resource.setrlimit(getattr(resource, name), (memory, memory))
            except (OSError, ValueError):
                pass
    if hasattr(resource, "RLIMIT_FSIZE"):
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    if hasattr(resource, "RLIMIT_NOFILE"):
        resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    if hasattr(resource, "RLIMIT_CPU"):
        resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
except ImportError:
    pass

SAFE = {
    "Exception": Exception,
    "ValueError": ValueError,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "deepcopy": copy.deepcopy,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

class PlanAPI:
    def action(self, name):
        upper = str(name).upper()
        if not upper.startswith("ACTION"):
            raise ValueError("unknown action")
        action_id = int(upper[6:])
        if action_id < 1 or action_id > 7:
            raise ValueError("action id must be in 1..7")
        return {"id": action_id}

    def click(self, x, y):
        x, y = int(x), int(y)
        if not (0 <= x <= 63 and 0 <= y <= 63):
            raise ValueError("click coordinates must be in 0..63")
        return {"id": 6, "x": x, "y": y}

    def reset(self):
        return {"id": 0}

    def repeat(self, action, count):
        count = int(count)
        if not 0 <= count <= 256:
            raise ValueError("repeat count must be in 0..256")
        return [copy.deepcopy(action) for _ in range(count)]

    def sequence(self, *parts):
        result = []
        for part in parts:
            if isinstance(part, dict):
                result.append(part)
            else:
                result.extend(part)
        return result

code = None

def namespace():
    value = {"__builtins__": SAFE}
    exec(code, value)
    return value

def respond(value):
    try:
        encoded = json.dumps({"ok": True, "value": value}, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        encoded = json.dumps(
            {"ok": False, "error": "non-JSON result: " + str(error)},
            separators=(",", ":"),
        )
    sys.stdout.write(encoded + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    try:
        request = json.loads(line)
        operation = request["op"]
        if operation == "load":
            code = compile(request["source"], "<isolated-generated-code>", "exec")
            respond(True)
            continue
        if code is None:
            raise RuntimeError("source is not loaded")
        scope = namespace()
        if operation == "call":
            result = scope[request["name"]](*request.get("args", []))
            respond(result)
        elif operation == "plan":
            result = scope["build_plan"](PlanAPI(), request["context"])
            if not isinstance(result, (list, tuple)):
                raise TypeError("build_plan must return a list or tuple")
            respond(list(result))
        else:
            raise ValueError("unknown operation")
    except BaseException as error:
        sys.stdout.write(
            json.dumps(
                {"ok": False, "error": type(error).__name__ + ": " + str(error)},
                separators=(",", ":"),
            )
            + "\n"
        )
        sys.stdout.flush()
"""


class SandboxError(RuntimeError):
    """Generated code failed or violated the process contract."""


class SandboxTimeout(SandboxError):
    """Generated code exceeded its per-call wall-clock budget."""


@dataclass(slots=True)
class GeneratedProcess:
    source: str
    timeout_seconds: float = 2.0
    _process: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def call(self, name: str, *args: Any) -> Any:
        return self._request({"op": "call", "name": name, "args": args})

    def build_plan(self, context: Mapping[str, Any]) -> list[dict[str, Any]]:
        value = self._request({"op": "plan", "context": dict(context)})
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise SandboxError("build_plan returned invalid action data")
        return value

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=0.5)

    def _request(self, request: Mapping[str, Any]) -> Any:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._start()
            return self._exchange(request)

    def _start(self) -> None:
        self.close()
        self._process = subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", _WORKER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            start_new_session=True,
            env={"PATH": os.environ.get("PATH", "")},
        )
        self._exchange({"op": "load", "source": self.source})

    def _exchange(self, request: Mapping[str, Any]) -> Any:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise SandboxError("generated-code worker is unavailable")
        try:
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            self.close()
            raise SandboxError("generated-code worker stopped unexpectedly") from error

        selector = selectors.DefaultSelector()
        try:
            selector.register(process.stdout, selectors.EVENT_READ)
            ready = selector.select(self.timeout_seconds)
        finally:
            selector.close()
        if not ready:
            self.close()
            raise SandboxTimeout(f"generated code exceeded {self.timeout_seconds:.3f} seconds")
        line = process.stdout.readline()
        if not line:
            self.close()
            raise SandboxError("generated-code worker returned no result")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as error:
            self.close()
            raise SandboxError("generated-code worker returned malformed JSON") from error
        if response.get("ok") is not True:
            raise SandboxError(str(response.get("error", "generated code failed")))
        return response.get("value")

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()
