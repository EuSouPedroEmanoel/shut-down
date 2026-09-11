"""Interface de linha de comando para controlar a máquina local."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import power, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shutdown-bot",
        description="Consulta o status e controla a energia desta máquina.",
        epilog=(
            "Comandos úteis:\n"
            "  shutdown-bot status               consultar o status local\n"
            "  shutdown-bot logs                 acompanhar os logs\n"
            "  shutdown-bot service restart      reiniciar o serviço\n"
            "  shutdown-bot config               trocar token ou allowlist"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="mostra o status da máquina")

    service = subparsers.add_parser("service", help="controla os serviços do bot")
    service.add_argument(
        "action", choices=("status", "start", "stop", "restart"), help="ação"
    )
    subparsers.add_parser("logs", help="acompanha os logs do bot")
    subparsers.add_parser("config", help="edita a configuração protegida")

    for name, help_text in (
        ("poweroff", "desliga a máquina"),
        ("reboot", "reinicia a máquina"),
        ("suspend", "suspende a máquina"),
        ("lock", "bloqueia as sessões"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "--yes",
            action="store_true",
            help="confirma a ação sem perguntar",
        )

    return parser


def _action_for(command: str):
    return {
        "poweroff": power.poweroff,
        "reboot": power.reboot,
        "suspend": power.suspend,
        "lock": power.lock_sessions,
    }[command]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "status":
        # O status usado no Telegram contém tags HTML; no terminal, removê-las
        # deixa a saída legível sem duplicar a lógica de coleta.
        print(status.collect().replace("<b>", "").replace("</b>", ""))
        return 0

    if args.command == "service":
        try:
            return subprocess.call(["sudo", "systemctl", args.action, "shutdown-bot"])
        except KeyboardInterrupt:
            print("\nAção interrompida.")
            return 130
    if args.command == "logs":
        try:
            return subprocess.call(["journalctl", "-u", "shutdown-bot", "-f"])
        except KeyboardInterrupt:
            print("\nAcompanhamento encerrado.")
            return 0
    if args.command == "config":
        try:
            env = os.environ.copy()
            editor = shutil.which("vi") or shutil.which("nano")
            if editor is not None:
                env["SUDO_EDITOR"] = editor
            return subprocess.call(["sudoedit", "/etc/shutdown-bot.env"], env=env)
        except KeyboardInterrupt:
            print("\nEdição interrompida.")
            return 130

    action = _action_for(args.command)
    if not args.yes:
        answer = input(f"Confirma a ação '{args.command}'? [s/N] ").strip().lower()
        if answer not in {"s", "sim", "y", "yes"}:
            print("Ação cancelada.")
            return 0

    try:
        action()
    except power.PowerActionError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print(f"Ação '{args.command}' enviada com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
