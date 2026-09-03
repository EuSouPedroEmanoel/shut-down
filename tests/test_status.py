from types import SimpleNamespace

import psutil
import pytest

from shutdown_bot import status


@pytest.mark.parametrize(
    ("segundos", "esperado"),
    [
        (0, "0m"),
        (90, "1m"),
        (3600, "1h 0m"),
        (86400 * 2 + 3600 * 3 + 60 * 14, "2d 3h 14m"),
    ],
)
def test_format_duration(segundos, esperado):
    assert status.format_duration(segundos) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(512, "512.0 B"), (2048, "2.0 KiB"), (3 * 1024**3, "3.0 GiB")],
)
def test_format_bytes(valor, esperado):
    assert status.format_bytes(valor) == esperado


@pytest.fixture
def psutil_falso(monkeypatch):
    """Substitui o psutil por números fixos, para o relatório ser determinístico."""
    monkeypatch.setattr(psutil, "boot_time", lambda: 0.0)
    monkeypatch.setattr(status.time, "time", lambda: 3600.0)
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 12.0)
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(used=4 * 1024**3, total=16 * 1024**3, percent=25.0),
    )
    monkeypatch.setattr(
        psutil,
        "disk_usage",
        lambda path: SimpleNamespace(used=100 * 1024**3, total=500 * 1024**3, percent=20.0),
    )


def test_collect_monta_o_relatorio(psutil_falso, monkeypatch):
    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)
    relatorio = status.collect()
    assert "Ligado há 1h 0m" in relatorio
    assert "CPU: 12%" in relatorio
    assert "RAM: 4.0 GiB / 16.0 GiB (25%)" in relatorio
    assert "Disco /: 100.0 GiB / 500.0 GiB (20%)" in relatorio


def test_collect_omite_bateria_quando_nao_ha(psutil_falso, monkeypatch):
    """Esta máquina é um desktop sem bateria — a linha simplesmente não aparece."""
    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)
    assert "🔋" not in status.collect()
    assert "🔌" not in status.collect()


def test_collect_inclui_bateria_quando_ha(psutil_falso, monkeypatch):
    monkeypatch.setattr(
        psutil,
        "sensors_battery",
        lambda: SimpleNamespace(percent=87.0, power_plugged=False),
    )
    assert "🔋 na bateria — 87%" in status.collect()
