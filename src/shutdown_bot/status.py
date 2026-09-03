"""Resumo do estado da máquina para o comando /status."""

from __future__ import annotations

import socket
import time

import psutil


def format_duration(seconds: float) -> str:
    """Formata uma duração em ``2d 3h 14m`` — omitindo as unidades zeradas."""
    total = int(seconds)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def format_bytes(value: float) -> str:
    """Converte bytes para a maior unidade binária legível."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"  # inalcançável, mantém o type checker feliz


def collect() -> str:
    """Monta o relatório de status. Linhas indisponíveis são simplesmente omitidas."""
    uptime = time.time() - psutil.boot_time()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    lines = [
        f"🖥 <b>{socket.gethostname()}</b>",
        f"⏱ Ligado há {format_duration(uptime)}",
        f"⚙️ CPU: {psutil.cpu_percent(interval=0.5):.0f}%",
        f"🧠 RAM: {format_bytes(memory.used)} / {format_bytes(memory.total)}"
        f" ({memory.percent:.0f}%)",
        f"💾 Disco /: {format_bytes(disk.used)} / {format_bytes(disk.total)}"
        f" ({disk.percent:.0f}%)",
    ]

    # Esta máquina é um desktop sem bateria, mas o código roda em outros lugares.
    battery = getattr(psutil, "sensors_battery", lambda: None)()
    if battery is not None:
        plug = "🔌 na tomada" if battery.power_plugged else "🔋 na bateria"
        lines.append(f"{plug} — {battery.percent:.0f}%")

    return "\n".join(lines)
