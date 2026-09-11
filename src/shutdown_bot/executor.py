"""Executor privilegiado: aceita somente ações de energia conhecidas."""

from __future__ import annotations

import json
import logging
import os
import socket
import sys

from . import power

log = logging.getLogger("shutdown_executor")
SOCKET_PATH = os.environ.get("SHUTDOWN_EXECUTOR_SOCKET", "/run/shutdown-bot/executor.sock")
ALLOWED_ACTIONS = {
    "poweroff": power.poweroff,
    "reboot": power.reboot,
    "suspend": power.suspend,
    "lock": power.lock_sessions,
}


def serve() -> int:
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o750, exist_ok=True)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o660)
        server.listen(8)
        log.info("executor aguardando em %s", SOCKET_PATH)
        while True:
            connection, _ = server.accept()
            with connection:
                try:
                    request = json.loads(connection.makefile("rb").readline())
                    action = request.get("action")
                    if action not in ALLOWED_ACTIONS:
                        raise ValueError("ação não permitida")
                    log.info("executando ação: %s", action)
                    ALLOWED_ACTIONS[action]()
                    result = {"ok": True}
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    result = {"ok": False, "error": str(exc)}
                except power.PowerActionError as exc:
                    result = {"ok": False, "error": str(exc)}
                connection.sendall((json.dumps(result) + "\n").encode())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(serve())
