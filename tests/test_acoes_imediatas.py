"""Ordem e tratamento de erro em suspender e bloquear."""

import time

import pytest
from conftest import DONO, fake_callback_update, fake_context, fake_message_update

from shutdown_bot import bot, power


@pytest.mark.asyncio
async def test_suspender_so_pergunta_antes_de_executar(monkeypatch):
    """Suspender é o erro que o bot não desfaz: máquina dormindo não recebe ordem."""
    executou = []
    monkeypatch.setattr(power, "suspend", lambda: executou.append("suspend"))
    monkeypatch.setattr(bot, "IMEDIATAS", {**bot.IMEDIATAS, "sus": power.suspend})

    context = fake_context({DONO})
    await bot.cmd_suspender(fake_message_update(texto="/suspender"), context)

    assert executou == []
    assert "Confirma" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_suspender_avisa_antes_de_executar(monkeypatch):
    """A suspensão corta a conexão: o painel precisa estar atualizado primeiro."""
    ordem = []
    monkeypatch.setattr(
        bot, "IMEDIATAS", {**bot.IMEDIATAS, "sus": lambda: ordem.append(("suspend", None))}
    )

    context = fake_context({DONO})
    context.bot.ordem = ordem
    update = fake_callback_update(f"c:sus:0:{DONO}:{int(time.time())}")

    await bot.on_callback(update, context)

    assert [passo for passo, _ in ordem] == ["mensagem", "suspend"]
    assert "Suspendendo" in ordem[0][1]
    assert context.job_queue.jobs == []  # suspender não agenda nada


@pytest.mark.asyncio
async def test_bloquear_confirma_depois_de_executar(monkeypatch):
    """Bloquear não derruba a conexão, então a confirmação é sobre o fato."""
    ordem = []
    monkeypatch.setattr(
        bot, "IMEDIATAS", {**bot.IMEDIATAS, "lock": lambda: ordem.append(("lock", None))}
    )

    context = fake_context({DONO})
    context.bot.ordem = ordem
    await bot.cmd_bloquear(fake_message_update(texto="/bloquear"), context)

    assert [passo for passo, _ in ordem] == ["lock", "mensagem"]
    assert "bloqueada" in ordem[1][1]


@pytest.mark.asyncio
async def test_bloquear_reporta_falha_em_vez_de_sucesso(monkeypatch):
    def falha():
        raise power.PowerActionError("loginctl lock-sessions falhou: sem sessão")

    monkeypatch.setattr(bot, "IMEDIATAS", {**bot.IMEDIATAS, "lock": falha})

    context = fake_context({DONO})
    await bot.cmd_bloquear(fake_message_update(texto="/bloquear"), context)

    assert "sem sessão" in context.bot.ultimo_texto
    assert "bloqueada" not in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_bloquear_pelo_painel_nao_pede_confirmacao(monkeypatch):
    """Bloquear é reversível na própria máquina: pedir confirmação só atrapalha."""
    executou = []
    monkeypatch.setattr(
        bot, "IMEDIATAS", {**bot.IMEDIATAS, "lock": lambda: executou.append("lock")}
    )

    context = fake_context({DONO})
    await bot.on_callback(fake_callback_update(f"a:lock:{DONO}"), context)

    assert executou == ["lock"]
