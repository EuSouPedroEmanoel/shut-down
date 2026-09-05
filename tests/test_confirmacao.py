"""O caminho crítico: confirmar, agendar, cancelar — e a ordem do desligamento.

É aqui que mora o risco do projeto. Um bug no cancelamento desliga a máquina
quando não devia; um bug na ordem do /desligar faz o aviso final nunca chegar.
"""

import time
from types import SimpleNamespace

import pytest
from conftest import (
    CHAT,
    DONO,
    OUTRO,
    FakeBot,
    FakeJob,
    fake_callback_update,
    fake_context,
    fake_message_update,
)

from shutdown_bot import bot, power


def token_confirmacao(acao="off", delay=60, dono=DONO, idade=0):
    return f"c:{acao}:{delay}:{dono}:{int(time.time()) - idade}"


@pytest.mark.asyncio
async def test_confirmacao_agenda_o_desligamento():
    update = fake_callback_update(token_confirmacao(delay=60))
    context = fake_context({DONO, OUTRO})

    await bot.on_callback(update, context)

    assert len(context.job_queue.jobs) == 1
    assert context.job_queue.jobs[0].data["acao"] == "off"
    assert context.job_queue.agendado_para == 60
    assert "em 1min" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_cancelar_remove_o_job_agendado():
    """O teste mais importante: depois do /cancelar, nada pode executar."""
    context = fake_context({DONO, OUTRO})
    await bot.on_callback(fake_callback_update(token_confirmacao()), context)
    assert context.job_queue.get_jobs_by_name(bot.JOB_NAME)

    await bot.cmd_cancelar(fake_message_update(texto="/cancelar"), context)

    assert context.job_queue.get_jobs_by_name(bot.JOB_NAME) == []
    assert "cancelada" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_botao_cancelar_do_painel_tambem_remove_o_job():
    """A janela de desistência do painel tem de valer tanto quanto o comando."""
    context = fake_context({DONO, OUTRO})
    await bot.on_callback(fake_callback_update(token_confirmacao()), context)

    await bot.on_callback(fake_callback_update(f"x:{DONO}"), context)

    assert context.job_queue.get_jobs_by_name(bot.JOB_NAME) == []
    assert "Cancelado" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_cancelar_sem_nada_agendado_avisa():
    context = fake_context({DONO})
    await bot.cmd_cancelar(fake_message_update(texto="/cancelar"), context)
    assert "nada agendado" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_botao_de_outra_pessoa_nao_agenda():
    """Em grupo, o botão pertence a quem abriu a tela."""
    update = fake_callback_update(token_confirmacao(dono=DONO), user_id=OUTRO)
    context = fake_context({DONO, OUTRO})

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []
    update.callback_query.answer.assert_awaited_once()
    assert update.callback_query.answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_confirmacao_expirada_nao_agenda():
    idade = bot.CONFIRMATION_TTL_SECONDS + 5
    update = fake_callback_update(token_confirmacao(idade=idade))
    context = fake_context({DONO})

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []
    assert "expirada" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_nova_confirmacao_substitui_a_anterior():
    """Só uma ação pendente por vez — senão o /cancelar viraria loteria."""
    context = fake_context({DONO})
    await bot.on_callback(fake_callback_update(token_confirmacao(delay=60)), context)
    primeiro = context.job_queue.jobs[0]

    await bot.on_callback(fake_callback_update(token_confirmacao(delay=30)), context)

    assert primeiro.removido is True
    assert len(context.job_queue.get_jobs_by_name(bot.JOB_NAME)) == 1


@pytest.mark.asyncio
async def test_usuario_nao_autorizado_nao_agenda():
    update = fake_callback_update(token_confirmacao(dono=42), user_id=42)
    context = fake_context({DONO})

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []


def contexto_de_job(acao="off", ordem=None):
    """Contexto como a JobQueue monta: tem job, bot e chat_data, mas não update."""
    job = FakeJob(bot._executar_acao, bot.JOB_NAME, CHAT, {"acao": acao, "user_id": DONO})
    return SimpleNamespace(job=job, bot=FakeBot(ordem), chat_data={})


@pytest.mark.asyncio
async def test_aviso_e_enviado_antes_do_poweroff(monkeypatch):
    """O poweroff mata o processo: se a ordem inverter, o aviso nunca chega."""
    ordem = []
    monkeypatch.setattr(
        bot,
        "ACOES",
        {**bot.ACOES, "off": ("Desligar", "Desligando", lambda: ordem.append(("poweroff", None)))},
    )

    context = contexto_de_job(ordem=ordem)
    await bot._executar_acao(context)

    assert [passo for passo, _ in ordem] == ["mensagem", "poweroff"]
    assert "Desligando agora" in ordem[0][1]


@pytest.mark.asyncio
async def test_falha_do_poweroff_e_reportada(monkeypatch):
    def falha():
        raise power.PowerActionError("systemctl poweroff falhou: Access denied")

    monkeypatch.setattr(bot, "ACOES", {"off": ("Desligar", "Desligando", falha)})

    context = contexto_de_job()
    await bot._executar_acao(context)

    assert len(context.bot.ordem) == 2
    assert "Access denied" in context.bot.ordem[1][1]
