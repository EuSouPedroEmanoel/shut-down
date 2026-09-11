"""Cliente do executor privilegiado via socket Unix."""

from __future__ import annotations

import json
import os
import socket

SOCKET_PATH = os.environ.get("SHUTDOWN_EXECUTOR_SOCKET", "/run/shutdown-bot/executor.sock")


class ExecutorError(RuntimeError):
    """Falha ao comunicar com o executor."""


def execute(action: str) -> None:
    """Solicita uma ação nomeada ao executor local."""
    payload = (json.dumps({"action": action}) + "\n").encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(10)
            client.connect(SOCKET_PATH)
            client.sendall(payload)
            response = client.makefile("rb").readline()
    except OSError as exc:
        raise ExecutorError(f"não foi possível conectar ao executor: {exc}") from exc

    try:
        data = json.loads(response)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ExecutorError("resposta inválida do executor") from exc
    if not data.get("ok"):
        raise ExecutorError(data.get("error", "executor recusou a ação"))
