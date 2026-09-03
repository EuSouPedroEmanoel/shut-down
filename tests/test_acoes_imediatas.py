"""Ordem e tratamento de erro em /suspender e /bloquear."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shutdown_bot import bot, power
from shutdown_bot.config import Config

DONO = 111


def fake_update():
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=DONO, username="dono"),
        effective_message=SimpleNamespace(text="/cmd", reply_text=AsyncMock()),
        callback_query=None,
    )


def fake_context():
    config = Config(token="t", allowed_user_ids=frozenset({DONO}))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"config": config}), args=[]
    )


@pytest.mark.asyncio
async def test_suspender_avisa_antes_de_executar(monkeypatch):
    """A suspensão corta a conexão: o aviso precisa sair primeiro."""
    ordem = []
    monkeypatch.setattr(power, "suspend", lambda: ordem.append("suspend"))

    update = fake_update()
    update.effective_message.reply_text = AsyncMock(
        side_effect=lambda *a, **k: ordem.append("mensagem")
    )

    await bot.cmd_suspender(update, fake_context())

    assert ordem == ["mensagem", "suspend"]


@pytest.mark.asyncio
async def test_bloquear_confirma_depois_de_executar(monkeypatch):
    """Bloquear não derruba a conexão, então a confirmação é sobre o fato."""
    ordem = []
    monkeypatch.setattr(power, "lock_sessions", lambda: ordem.append("lock"))

    update = fake_update()
    update.effective_message.reply_text = AsyncMock(
        side_effect=lambda *a, **k: ordem.append("mensagem")
    )

    await bot.cmd_bloquear(update, fake_context())

    assert ordem == ["lock", "mensagem"]


@pytest.mark.asyncio
async def test_bloquear_reporta_falha_em_vez_de_sucesso(monkeypatch):
    def falha():
        raise power.PowerActionError("loginctl lock-sessions falhou: sem sessão")

    monkeypatch.setattr(power, "lock_sessions", falha)

    update = fake_update()
    await bot.cmd_bloquear(update, fake_context())

    respostas = [c.args[0] for c in update.effective_message.reply_text.await_args_list]
    assert len(respostas) == 1
    assert "sem sessão" in respostas[0]
    assert "bloqueada" not in respostas[0]
