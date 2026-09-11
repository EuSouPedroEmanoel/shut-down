"""Handlers do Telegram e montagem da aplicação.

O bot não conversa: ele mantém **um** painel no chat e edita essa mesma mensagem
a cada toque. Toda mensagem sua é apagada depois de processada, então a conversa
tem sempre uma mensagem só — a ideia é que pareça um controle remoto, não um
histórico de comandos.
"""

from __future__ import annotations

import asyncio
import functools
import html
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import power, status, ui
from .config import DEFAULT_DELAY_SECONDS, MAX_DELAY_SECONDS, Config

log = logging.getLogger(__name__)

# Nome único do job agendado: só uma ação de energia pode estar pendente por vez,
# e é isso que permite ao /cancelar abortar sem manter estado global.
JOB_NAME = "acao-agendada"

# Uma confirmação pendente vira inválida depois disso, para que um botão antigo
# rolando no histórico da conversa não desligue a máquina por engano.
CONFIRMATION_TTL_SECONDS = 60

# Onde o id da mensagem-painel fica guardado dentro do chat_data.
PANEL_KEY = "panel_id"

AJUDA = (
    "🤖 <b>Controle de energia</b>\n\n"
    "O painel faz tudo por botão. Os comandos abaixo continuam valendo, e a "
    "mensagem some sozinha depois de enviada:\n\n"
    "/start — abre o painel\n"
    "/status — estado da máquina\n"
    "/desligar [segundos] — desliga\n"
    "/reiniciar [segundos] — reinicia\n"
    "/cancelar — aborta a ação agendada\n"
    "/suspender — suspende para a RAM\n"
    "/bloquear — bloqueia a tela\n"
    "/meuid — mostra o seu ID do Telegram"
)

# ação -> (rótulo, verbo no gerúndio, função que executa)
ACOES: dict[str, tuple[str, str, Callable[[], None]]] = {
    "off": ("Desligar", "Desligando", power.poweroff),
    "reb": ("Reiniciar", "Reiniciando", power.reboot),
}

# Ações que acontecem na hora, sem agendamento nem /cancelar.
IMEDIATAS: dict[str, Callable[[], None]] = {
    "sus": power.suspend,
    "lock": power.lock_sessions,
}

# Suspender entra na lista de confirmação porque é o único erro que o bot não
# consegue desfazer: máquina suspensa não recebe mais comando nenhum.
CONFIRMA = ("off", "reb", "sus")

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def restrito(func: Handler) -> Handler:
    """Bloqueia o handler para quem não está na allowlist.

    A configuração é lida de ``application.bot_data["config"]`` para que os
    testes possam injetar uma allowlist sem tocar no ambiente.
    """

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        config: Config = context.application.bot_data["config"]
        user = update.effective_user
        if not config.is_allowed(user.id if user else None):
            log.warning(
                "acesso negado: id=%s username=%s texto=%r",
                getattr(user, "id", None),
                getattr(user, "username", None),
                getattr(update.effective_message, "text", None),
            )
            await _responder(update, "⛔ Você não tem permissão para usar este bot.")
            return
        await func(update, context)

    return wrapper


async def _responder(update: Update, texto: str, **kwargs: Any) -> None:
    """Resposta fora do painel — só para quem não tem painel nenhum.

    Quem não está na allowlist não ganha painel, e o /meuid é justamente o
    comando de antes de existir allowlist.
    """
    if update.callback_query is not None:
        await update.callback_query.edit_message_text(
            texto, parse_mode=ParseMode.HTML, **kwargs
        )
    elif update.effective_message is not None:
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.HTML, **kwargs
        )


def _parse_delay(args: list[str]) -> int:
    """Interpreta o argumento de atraso, em segundos."""
    if not args:
        return DEFAULT_DELAY_SECONDS
    try:
        delay = int(args[0])
    except ValueError:
        raise ValueError(f"{args[0]!r} não é um número de segundos.") from None
    if delay < 0:
        raise ValueError("O atraso não pode ser negativo.")
    if delay > MAX_DELAY_SECONDS:
        raise ValueError(f"O atraso máximo é {MAX_DELAY_SECONDS}s (24h).")
    return delay


# --------------------------------------------------------------------------- #
# O painel
# --------------------------------------------------------------------------- #


async def _apagar(message: Any) -> None:
    """Apaga uma mensagem sem deixar a falha derrubar o handler.

    Apagar pode falhar por motivos banais (mensagem já apagada à mão, mais velha
    que as 48h que a API permite) e nenhum deles justifica perder o comando.
    """
    try:
        await message.delete()
    except TelegramError as exc:
        log.debug("não consegui apagar a mensagem: %s", exc)


async def mostrar_painel(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, tela: tuple[str, Any]
) -> None:
    """Edita o painel existente. Só cria mensagem nova se não houver painel.

    Este é o coração da v1.1: enquanto esta função editar em vez de enviar, o
    chat continua com uma mensagem só.
    """
    texto, teclado = tela
    panel_id = context.chat_data.get(PANEL_KEY) if context.chat_data else None

    if panel_id is not None:
        try:
            await context.bot.edit_message_text(
                texto,
                chat_id=chat_id,
                message_id=panel_id,
                parse_mode=ParseMode.HTML,
                reply_markup=teclado,
            )
            return
        except BadRequest as exc:
            if "not modified" in str(exc).lower():
                # Dois toques dentro do mesmo segundo: o painel já está certo.
                return
            # Painel apagado à mão ou velho demais para editar: recria abaixo.
            log.info("painel %s não pôde ser editado (%s); recriando", panel_id, exc)
            context.chat_data.pop(PANEL_KEY, None)

    msg = await context.bot.send_message(
        chat_id, texto, parse_mode=ParseMode.HTML, reply_markup=teclado
    )
    if context.chat_data is not None:
        context.chat_data[PANEL_KEY] = msg.message_id


async def _painel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    aviso: str | None = None,
) -> None:
    """Atalho para voltar à tela inicial, opcionalmente com um aviso no topo."""
    await mostrar_painel(context, chat_id, ui.painel_principal(user_id, aviso))


def _alvo(update: Update) -> tuple[int, int] | None:
    """Extrai ``(chat_id, user_id)`` do update, ou ``None`` se faltar algum."""
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return None
    return chat.id, user.id


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #


async def cmd_meuid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Único comando aberto: é como você descobre o seu ID na primeira execução."""
    user = update.effective_user
    if user is None:
        return
    log.info("/meuid consultado por id=%s username=%s", user.id, user.username)
    await _responder(
        update,
        f"Seu ID do Telegram é <code>{user.id}</code>\n\n"
        "Coloque-o em <code>ALLOWED_USER_IDS</code> para liberar os comandos.",
    )


@restrito
async def cmd_painel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alvo = _alvo(update)
    if alvo:
        await _painel(context, *alvo)


@restrito
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alvo = _alvo(update)
    if alvo:
        await mostrar_painel(context, alvo[0], ui.tela_ajuda(AJUDA, alvo[1]))


@restrito
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alvo = _alvo(update)
    if alvo:
        await _mostrar_status(context, *alvo)


async def _mostrar_status(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int
) -> None:
    log.info("/status consultado por id=%s", user_id)
    # collect() faz uma amostragem de CPU de 0,5s; fora da thread do event loop.
    relatorio = await asyncio.to_thread(status.collect)
    await mostrar_painel(context, chat_id, ui.tela_status(relatorio, user_id))


@restrito
async def cmd_desligar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _pedir_confirmacao(update, context, "off")


@restrito
async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _pedir_confirmacao(update, context, "reb")


@restrito
async def cmd_suspender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _pedir_confirmacao(update, context, "sus")


@restrito
async def cmd_bloquear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alvo = _alvo(update)
    if alvo:
        await _executar_imediata(context, alvo[0], alvo[1], "lock")


@restrito
async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    alvo = _alvo(update)
    if alvo is None:
        return
    if _cancelar_jobs(context):
        log.info("ação cancelada por id=%s", alvo[1])
        await _painel(context, *alvo, aviso="✅ Ação cancelada.")
    else:
        await _painel(context, *alvo, aviso="ℹ️ Não havia nada agendado.")


async def _pedir_confirmacao(
    update: Update, context: ContextTypes.DEFAULT_TYPE, acao: str
) -> None:
    """Comando de texto: cai na mesma tela de confirmação que o botão abriria.

    Sem argumento, oferece a grade de tempos. Com ``/desligar 1800``, pergunta
    apenas sobre aqueles 1800s — que é o motivo de os comandos continuarem
    existindo depois do painel.
    """
    alvo = _alvo(update)
    if alvo is None:
        return
    chat_id, user_id = alvo

    delay: int | None = None
    if context.args:
        try:
            delay = _parse_delay(list(context.args))
        except ValueError as exc:
            await _painel(context, chat_id, user_id, f"⚠️ {html.escape(str(exc))}")
            return

    await mostrar_painel(context, chat_id, ui.tela_confirmacao(acao, user_id, delay))


def _cancelar_jobs(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove os jobs pendentes. Devolve ``True`` se havia algum."""
    jobs = context.job_queue.get_jobs_by_name(JOB_NAME) if context.job_queue else ()
    for job in jobs:
        log.info("job removido: nome=%s id=%s", JOB_NAME, getattr(job, "id", "desconhecido"))
        job.schedule_removal()
    return bool(jobs)


# --------------------------------------------------------------------------- #
# Limpeza do chat
# --------------------------------------------------------------------------- #


async def apagar_do_usuario(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Apaga a mensagem que você mandou, depois de ela já ter sido processada.

    Roda no grupo 1, ou seja, depois dos handlers de comando: quando a mensagem
    some, o painel já foi redesenhado. Mensagem de quem não está na allowlist
    fica onde está — o log registra a tentativa, e apagar seria esconder prova.
    """
    config: Config = context.application.bot_data["config"]
    user = update.effective_user
    if not config.is_allowed(user.id if user else None):
        return
    if update.effective_message is not None:
        await _apagar(update.effective_message)


# --------------------------------------------------------------------------- #
# Botões
# --------------------------------------------------------------------------- #


def _dono_do_botao(partes: list[str]) -> str | None:
    """Diz de quem é o botão.

    O id do dono é sempre o último campo, menos no ``c:`` — que mantém de
    propósito o formato da v1.0, com o carimbo de criação no fim.
    """
    if not partes or len(partes) < 2:
        return None
    if partes[0] == "c":
        return partes[3] if len(partes) == 5 else None
    return partes[-1]


def _e_o_painel_atual(context: ContextTypes.DEFAULT_TYPE, message: Any) -> bool:
    """Confere se o clique veio do painel vigente.

    O ``chat_data`` vive em memória: depois de um ``systemctl restart`` o bot não
    sabe mais qual mensagem era o painel. Nesse caso ele adota a mensagem clicada
    em vez de criar uma segunda — sem isso, todo reinício deixaria um painel
    órfão com botões vivos no chat.
    """
    panel_id = context.chat_data.get(PANEL_KEY)
    if panel_id is None:
        context.chat_data[PANEL_KEY] = message.message_id
        return True
    return panel_id == message.message_id


@restrito
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.message is None:
        return

    # Um callback só pode ser respondido uma vez, então cada saída abaixo chama
    # query.answer() exatamente uma vez — com alerta quando há o que explicar.
    partes = (query.data or "").split(":")

    # O id de quem pediu vai embutido no botão: em um grupo, outra pessoa pode
    # clicar, e aqui se confere que quem clicou é quem abriu a tela.
    if _dono_do_botao(partes) != str(user.id):
        await query.answer("Este botão não é seu.", show_alert=True)
        return

    if not _e_o_painel_atual(context, query.message):
        await query.answer("Painel antigo — use o painel de baixo.")
        await _apagar(query.message)
        return

    await query.answer()

    chat_id = query.message.chat_id
    prefixo = partes[0]

    if prefixo == "m":
        await _painel(context, chat_id, user.id)
    elif prefixo == "s":
        await _mostrar_status(context, chat_id, user.id)
    elif prefixo == "q":
        await _abrir_confirmacao(context, chat_id, user.id, partes[1])
    elif prefixo == "a":
        await _executar_imediata(context, chat_id, user.id, partes[1])
    elif prefixo == "x":
        _cancelar_jobs(context)
        await _painel(context, chat_id, user.id, "✖️ Cancelado.")
    elif prefixo == "c":
        await _agendar(context, chat_id, user.id, partes)
    else:
        await _painel(context, chat_id, user.id, "⚠️ Botão inválido.")


async def _abrir_confirmacao(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, acao: str
) -> None:
    if acao not in CONFIRMA:
        await _painel(context, chat_id, user_id, "⚠️ Ação desconhecida.")
        return
    # Suspender não agenda nada, então não faz sentido oferecer atraso.
    delay = 0 if acao == "sus" else None
    await mostrar_painel(context, chat_id, ui.tela_confirmacao(acao, user_id, delay))


async def _agendar(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, partes: list[str]
) -> None:
    """Trata o ``c:`` — o botão que realmente compromete a máquina."""
    if len(partes) != 5:
        await _painel(context, chat_id, user_id, "⚠️ Botão inválido.")
        return

    acao, delay_raw, _, criado_em = partes[1], partes[2], partes[3], partes[4]

    if acao == "sus":
        await _executar_imediata(context, chat_id, user_id, "sus")
        return

    if acao not in ACOES:
        await _painel(context, chat_id, user_id, "⚠️ Ação desconhecida.")
        return

    if time.time() - int(criado_em) > CONFIRMATION_TTL_SECONDS:
        await _painel(
            context, chat_id, user_id, "⏰ Confirmação expirada. Peça de novo."
        )
        return

    delay = int(delay_raw)
    rotulo = ACOES[acao][0]

    _cancelar_jobs(context)  # uma ação pendente por vez
    context.job_queue.run_once(
        _executar_acao,
        when=delay,
        name=JOB_NAME,
        chat_id=chat_id,
        data={"acao": acao, "user_id": user_id},
    )
    log.info("%s agendado para daqui a %ss por id=%s", rotulo, delay, user_id)
    await mostrar_painel(context, chat_id, ui.tela_agendado(acao, delay, user_id))


async def _executar_imediata(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, acao: str
) -> None:
    """Suspender e bloquear: acontecem agora, sem passar pela fila de jobs."""
    executar = IMEDIATAS.get(acao)
    if executar is None:
        await _painel(context, chat_id, user_id, "⚠️ Ação desconhecida.")
        return

    if acao == "sus":
        # Suspender corta a conexão no meio da chamada, então o painel precisa
        # estar atualizado ANTES: uma edição não entregue deixaria a tela
        # mentindo sobre o estado da máquina.
        log.info("suspendendo a pedido de id=%s", user_id)
        await _painel(context, chat_id, user_id, "😴 Suspendendo...")
        try:
            await asyncio.to_thread(executar)
        except power.PowerActionError as exc:
            await _painel(context, chat_id, user_id, f"❌ {html.escape(str(exc))}")
        return

    # Bloquear não derruba a conexão, então dá para confirmar o fato consumado,
    # em vez de anunciar um sucesso que ainda não aconteceu.
    try:
        await asyncio.to_thread(executar)
    except power.PowerActionError as exc:
        await _painel(context, chat_id, user_id, f"❌ {html.escape(str(exc))}")
        return
    log.info("tela bloqueada a pedido de id=%s", user_id)
    await _painel(
        context, chat_id, user_id, f"🔒 Tela bloqueada · {time.strftime('%H:%M')}"
    )


async def _executar_acao(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job que dispara a ação de energia agendada.

    A ordem aqui é o detalhe que mais importa no projeto: o ``poweroff`` mata
    este processo, então o aviso final tem de ser enviado e aguardado *antes*
    da chamada — nunca depois, ou ele nunca chega.
    """
    job = context.job
    acao = job.data["acao"]
    user_id = job.data.get("user_id", 0)
    _, gerundio, executar = ACOES[acao]

    log.info(
        "job iniciado: nome=%s id=%s ação=%s",
        JOB_NAME,
        getattr(job, "id", "desconhecido"),
        acao,
    )
    await _painel(context, job.chat_id, user_id, f"⚡ {gerundio} agora...")
    try:
        await asyncio.to_thread(executar)
    except power.PowerActionError as exc:
        log.error("falha na ação %s: %s", acao, exc)
        await _painel(context, job.chat_id, user_id, f"❌ {html.escape(str(exc))}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("erro ao processar update", exc_info=context.error)


# --------------------------------------------------------------------------- #
# Montagem
# --------------------------------------------------------------------------- #


def build_application(config: Config, *, bootstrap: bool = False) -> Application:
    """Monta a ``Application`` com os handlers apropriados ao modo.

    No modo bootstrap só ``/meuid`` é registrado — não há allowlist ainda, e
    nenhum comando de energia deve existir enquanto não houver.
    """
    app = Application.builder().token(config.token).build()
    app.bot_data["config"] = config

    app.add_handler(CommandHandler("meuid", cmd_meuid))

    if bootstrap:
        # Sem allowlist, a única coisa útil que o bot pode fazer é revelar o ID.
        app.add_handler(CommandHandler(["start", "ajuda", "help"], cmd_meuid))
    else:
        app.add_handler(CommandHandler("start", cmd_painel))
        app.add_handler(CommandHandler(["ajuda", "help"], cmd_ajuda))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("desligar", cmd_desligar))
        app.add_handler(CommandHandler("reiniciar", cmd_reiniciar))
        app.add_handler(CommandHandler("cancelar", cmd_cancelar))
        app.add_handler(CommandHandler("suspender", cmd_suspender))
        app.add_handler(CommandHandler("bloquear", cmd_bloquear))
        app.add_handler(CallbackQueryHandler(on_callback))
        # Grupo 1 roda depois de tudo acima: quando a sua mensagem some, o
        # painel já foi redesenhado. Só em chat privado — em grupo o bot não
        # mexe em mensagem de ninguém.
        app.add_handler(
            MessageHandler(filters.ChatType.PRIVATE, apagar_do_usuario), group=1
        )

    app.add_error_handler(on_error)
    return app
