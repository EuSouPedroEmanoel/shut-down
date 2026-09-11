"""Ações de energia da máquina.

O serviço roda como root (unit systemd de sistema), então ``systemctl`` e
``loginctl`` são chamados diretamente — sem ``sudo`` e sem polkit no caminho.
Rodando em modo desenvolvimento como usuário comum, o polkit autoriza porque a
sessão gráfica local está ativa.
"""

from __future__ import annotations

import logging
import os
import subprocess

from . import executor_client

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10

POWEROFF = ["systemctl", "poweroff"]
REBOOT = ["systemctl", "reboot"]
SUSPEND = ["systemctl", "suspend"]
LOCK = ["loginctl", "lock-sessions"]


class PowerActionError(RuntimeError):
    """A ação de energia falhou — mensagem já pronta para exibir ao usuário."""


def run_action(command: list[str]) -> None:
    """Executa uma ação de energia, traduzindo falhas em ``PowerActionError``."""
    if os.path.exists(executor_client.SOCKET_PATH):
        action = {
            tuple(POWEROFF): "poweroff",
            tuple(REBOOT): "reboot",
            tuple(SUSPEND): "suspend",
            tuple(LOCK): "lock",
        }.get(tuple(command))
        if action is not None:
            try:
                executor_client.execute(action)
                return
            except executor_client.ExecutorError as exc:
                raise PowerActionError(str(exc)) from exc
    log.info("executando ação de energia: %s", " ".join(command))
    try:
        subprocess.run(
            command,
            check=True,
            timeout=TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PowerActionError(f"comando não encontrado: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PowerActionError(
            f"{' '.join(command)} não respondeu em {TIMEOUT_SECONDS}s"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"código {exc.returncode}"
        raise PowerActionError(f"{' '.join(command)} falhou: {detail}") from exc


def poweroff() -> None:
    run_action(POWEROFF)


def reboot() -> None:
    run_action(REBOOT)


def suspend() -> None:
    run_action(SUSPEND)


def lock_sessions() -> None:
    run_action(LOCK)
