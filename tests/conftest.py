"""Dublês compartilhados pelos testes.

O painel fala com o Telegram por ``context.bot.edit_message_text`` e
``context.bot.send_message``, e guarda estado em ``context.chat_data``. Montar
isso à mão em cada arquivo daria quatro cópias da mesma classe, então mora aqui.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from shutdown_bot.config import Config

DONO = 111
OUTRO = 999
CHAT = 555
PAINEL = 1000


class FakeBot:
    """Registra as chamadas em vez de falar com o Telegram.

    ``ordem`` guarda a sequência de tudo que passou por aqui, que é como os
    testes provam que o aviso saiu *antes* do desligamento.
    """

    def __init__(self, ordem=None):
        self.ordem = ordem if ordem is not None else []
        self.enviadas: list[str] = []
        self.editadas: list[str] = []
        self.erro_ao_editar: Exception | None = None
        self._proximo_id = PAINEL

    async def send_message(self, chat_id, text=None, **kwargs):
        texto = text if text is not None else ""
        self.enviadas.append(texto)
        self.ordem.append(("mensagem", texto))
        self._proximo_id += 1
        return SimpleNamespace(message_id=self._proximo_id)

    async def edit_message_text(self, text=None, **kwargs):
        if self.erro_ao_editar is not None:
            erro, self.erro_ao_editar = self.erro_ao_editar, None
            raise erro
        texto = text if text is not None else ""
        self.editadas.append(texto)
        self.ordem.append(("mensagem", texto))

    @property
    def ultimo_texto(self) -> str:
        """O que está escrito no painel agora, tendo ele sido criado ou editado."""
        todos = self.editadas + self.enviadas
        return (self.ordem[-1][1] if self.ordem else "") or (todos[-1] if todos else "")


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
        self.agendado_para = None

    def run_once(self, callback, when, name, chat_id, data):
        self.jobs.append(FakeJob(callback, name, chat_id, data))
        self.agendado_para = when

    def get_jobs_by_name(self, name):
        return [j for j in self.jobs if j.name == name and not j.removido]


def fake_context(allowed=(DONO,), *, job_queue=None, chat_data=None, bot=None, args=None):
    config = Config(token="t", allowed_user_ids=frozenset(allowed))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"config": config}),
        bot=bot if bot is not None else FakeBot(),
        chat_data=chat_data if chat_data is not None else {},
        job_queue=job_queue if job_queue is not None else FakeJobQueue(),
        args=args or [],
    )


def fake_message_update(user_id=DONO, texto="/cmd"):
    """Update de uma mensagem digitada por você."""
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="dono"),
        effective_chat=SimpleNamespace(id=CHAT),
        effective_message=SimpleNamespace(
            text=texto, reply_text=AsyncMock(), delete=AsyncMock()
        ),
        callback_query=None,
    )


def fake_callback_update(data: str, user_id=DONO, message_id=PAINEL):
    """Update de um toque em botão. ``message_id`` diz em qual painel se tocou."""
    query = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        message=SimpleNamespace(
            chat_id=CHAT, message_id=message_id, delete=AsyncMock()
        ),
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="dono"),
        effective_chat=SimpleNamespace(id=CHAT),
        effective_message=None,
        callback_query=query,
    )
