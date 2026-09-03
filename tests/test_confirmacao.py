"""O caminho crítico: confirmar, agendar, cancelar — e a ordem do desligamento.

É aqui que mora o risco do projeto. Um bug no cancelamento desliga a máquina
quando não devia; um bug na ordem do /desligar faz o aviso final nunca chegar.
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shutdown_bot import bot, power
from shutdown_bot.config import Config

DONO = 111
OUTRO = 999


class FakeJob:
    def __init__(self, callback, name, chat_id, data):
        self.callback = callback
        self.name = name
        self.chat_id = chat_id
        self.data = data
        self.removido = False

    def schedule_removal(self):
        self.removido = True


class FakeJobQueue:
    """Fila que registra agendamentos em vez de executá-los."""

    def __init__(self):
        self.jobs: list[FakeJob] = []

    def run_once(self, callback, when, name, chat_id, data):
        self.jobs.append(FakeJob(callback, name, chat_id, data))
        self.agendado_para = when

    def get_jobs_by_name(self, name):
        return [j for j in self.jobs if j.name == name and not j.removido]


def fake_callback_update(data: str, user_id: int = DONO):
    query = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(chat_id=555),
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="dono"),
        effective_message=None,
        callback_query=query,
    )


def fake_context(job_queue=None):
    config = Config(token="t", allowed_user_ids=frozenset({DONO, OUTRO}))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"config": config}),
        job_queue=job_queue if job_queue is not None else FakeJobQueue(),
        args=[],
    )


def token_confirmacao(acao="off", delay=60, dono=DONO, idade=0):
    return f"c:{acao}:{delay}:{dono}:{int(time.time()) - idade}"


@pytest.mark.asyncio
async def test_confirmacao_agenda_o_desligamento():
    update = fake_callback_update(token_confirmacao(delay=60))
    context = fake_context()

    await bot.on_callback(update, context)

    assert len(context.job_queue.jobs) == 1
    assert context.job_queue.jobs[0].data == {"acao": "off"}
    assert context.job_queue.agendado_para == 60
    assert "60s" in update.callback_query.edit_message_text.await_args.args[0]


@pytest.mark.asyncio
async def test_cancelar_remove_o_job_agendado():
    """O teste mais importante: depois do /cancelar, nada pode executar."""
    context = fake_context()
    await bot.on_callback(fake_callback_update(token_confirmacao()), context)
    assert context.job_queue.get_jobs_by_name(bot.JOB_NAME)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=DONO, username="dono"),
        effective_message=SimpleNamespace(text="/cancelar", reply_text=AsyncMock()),
        callback_query=None,
    )
    await bot.cmd_cancelar(update, context)

    assert context.job_queue.get_jobs_by_name(bot.JOB_NAME) == []
    assert "cancelada" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_cancelar_sem_nada_agendado_avisa():
    context = fake_context()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=DONO, username="dono"),
        effective_message=SimpleNamespace(text="/cancelar", reply_text=AsyncMock()),
        callback_query=None,
    )
    await bot.cmd_cancelar(update, context)
    assert "nada agendado" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_botao_de_outra_pessoa_nao_agenda():
    """Em grupo, o botão pertence a quem digitou o comando."""
    update = fake_callback_update(token_confirmacao(dono=DONO), user_id=OUTRO)
    context = fake_context()

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []
    update.callback_query.answer.assert_awaited_once()
    assert update.callback_query.answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_confirmacao_expirada_nao_agenda():
    idade = bot.CONFIRMATION_TTL_SECONDS + 5
    update = fake_callback_update(token_confirmacao(idade=idade))
    context = fake_context()

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []
    assert "expirada" in update.callback_query.edit_message_text.await_args.args[0]


@pytest.mark.asyncio
async def test_nova_confirmacao_substitui_a_anterior():
    """Só uma ação pendente por vez — senão o /cancelar viraria loteria."""
    context = fake_context()
    await bot.on_callback(fake_callback_update(token_confirmacao(delay=60)), context)
    primeiro = context.job_queue.jobs[0]

    await bot.on_callback(fake_callback_update(token_confirmacao(delay=30)), context)

    assert primeiro.removido is True
    assert len(context.job_queue.get_jobs_by_name(bot.JOB_NAME)) == 1


@pytest.mark.asyncio
async def test_usuario_nao_autorizado_nao_agenda():
    update = fake_callback_update(token_confirmacao(dono=42), user_id=42)
    context = fake_context()

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []


@pytest.mark.asyncio
async def test_aviso_e_enviado_antes_do_poweroff(monkeypatch):
    """O poweroff mata o processo: se a ordem inverter, o aviso nunca chega."""
    ordem = []

    async def fake_send(chat_id, texto):
        ordem.append(("mensagem", texto))

    monkeypatch.setattr(power, "poweroff", lambda: ordem.append(("poweroff", None)))
    monkeypatch.setattr(
        bot, "ACOES", {**bot.ACOES, "off": ("Desligar", "Desligando", power.poweroff)}
    )

    job = FakeJob(bot._executar_acao, bot.JOB_NAME, 555, {"acao": "off"})
    context = SimpleNamespace(job=job, bot=SimpleNamespace(send_message=fake_send))

    await bot._executar_acao(context)

    assert [passo for passo, _ in ordem] == ["mensagem", "poweroff"]
    assert "Desligando agora" in ordem[0][1]


@pytest.mark.asyncio
async def test_falha_do_poweroff_e_reportada(monkeypatch):
    enviadas = []

    async def fake_send(chat_id, texto):
        enviadas.append(texto)

    def falha():
        raise power.PowerActionError("systemctl poweroff falhou: Access denied")

    monkeypatch.setattr(bot, "ACOES", {"off": ("Desligar", "Desligando", falha)})

    job = FakeJob(bot._executar_acao, bot.JOB_NAME, 555, {"acao": "off"})
    context = SimpleNamespace(job=job, bot=SimpleNamespace(send_message=fake_send))

    await bot._executar_acao(context)

    assert len(enviadas) == 2
    assert "Access denied" in enviadas[1]
