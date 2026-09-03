import subprocess

import pytest

from shutdown_bot import power


@pytest.fixture
def chamadas(monkeypatch):
    """Captura os comandos em vez de executá-los de verdade."""
    registro = []

    def fake_run(command, **kwargs):
        registro.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return registro


@pytest.mark.parametrize(
    ("funcao", "esperado"),
    [
        (power.poweroff, ["systemctl", "poweroff"]),
        (power.reboot, ["systemctl", "reboot"]),
        (power.suspend, ["systemctl", "suspend"]),
        (power.lock_sessions, ["loginctl", "lock-sessions"]),
    ],
)
def test_cada_acao_invoca_o_comando_certo(chamadas, funcao, esperado):
    funcao()
    assert [c for c, _ in chamadas] == [esperado]


def test_acao_usa_check_e_timeout(chamadas):
    power.poweroff()
    _, kwargs = chamadas[0]
    assert kwargs["check"] is True
    assert kwargs["timeout"] == power.TIMEOUT_SECONDS


def test_falha_do_comando_vira_erro_legivel(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="Access denied")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(power.PowerActionError, match="Access denied"):
        power.poweroff()


def test_timeout_vira_erro_legivel(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, power.TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(power.PowerActionError, match="não respondeu"):
        power.poweroff()


def test_comando_inexistente_vira_erro_legivel(monkeypatch):
    def fake_run(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(power.PowerActionError, match="não encontrado"):
        power.lock_sessions()
