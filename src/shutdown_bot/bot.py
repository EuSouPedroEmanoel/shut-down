"""Handlers do Telegram e montagem da aplicação."""

from __future__ import annotations

import asyncio
import functools
import html
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from . import power, status
from .config import DEFAULT_DELAY_SECONDS, MAX_DELAY_SECONDS, Config

log = logging.getLogger(__name__)

# Nome único do job agendado: só uma ação de energia pode estar pendente por vez,
# e é isso que permite ao /cancelar abortar sem manter estado global.
JOB_NAME = "acao-agendada"

# Uma confirmação pendente vira inválida depois disso, para que um botão antigo
# rolando no histórico da conversa não desligue a máquina por engano.
CONFIRMATION_TTL_SECONDS = 60

AJUDA = (
    "🤖 <b>Controle de energia</b>\n\n"
    "/status — estado da máquina\n"
    "/desligar [segundos] — desliga (padrão: "
    f"{DEFAULT_DELAY_SECONDS}s)\n"
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
    """Responde tanto a uma mensagem quanto ao clique em um botão."""
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
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _responder(update, AJUDA)


@restrito
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # collect() faz uma amostragem de CPU de 0,5s; fora da thread do event loop.
    relatorio = await asyncio.to_thread(status.collect)
    await _responder(update, relatorio)


@restrito
async def cmd_suspender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Suspender corta a conexão do bot no meio da chamada, então o aviso vai
    # antes: uma mensagem não entregue pareceria falha para o usuário.
    await _responder(update, "😴 Suspendendo...")
    await _executar_ou_reportar(update, power.suspend)


@restrito
async def cmd_bloquear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Bloquear a tela não derruba a conexão, então dá para confirmar de verdade,
    # depois do fato — em vez de anunciar um sucesso que ainda não aconteceu.
    if await _executar_ou_reportar(update, power.lock_sessions):
        await _responder(update, "🔒 Tela bloqueada.")


async def _executar_ou_reportar(update: Update, acao: Callable[[], None]) -> bool:
    """Roda a ação fora do event loop. Devolve ``False`` se falhou (já reportado)."""
    try:
        await asyncio.to_thread(acao)
    except power.PowerActionError as exc:
        await _responder(update, f"❌ {html.escape(str(exc))}")
        return False
    return True


@restrito
async def cmd_desligar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _pedir_confirmacao(update, context, "off")


@restrito
async def cmd_reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _pedir_confirmacao(update, context, "reb")


async def _pedir_confirmacao(
    update: Update, context: ContextTypes.DEFAULT_TYPE, acao: str
) -> None:
    rotulo = ACOES[acao][0]
    user = update.effective_user
    if user is None:
        return

    try:
        delay = _parse_delay(context.args or [])
    except ValueError as exc:
        await _responder(update, f"⚠️ {html.escape(str(exc))}")
        return

    # O ID de quem pediu vai embutido no botão: em um grupo, outra pessoa pode
    # clicar, e o callback confere que quem clicou é quem pediu.
    token = f"c:{acao}:{delay}:{user.id}:{int(time.time())}"
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"✅ {rotulo}", callback_data=token),
                InlineKeyboardButton("✖️ Cancelar", callback_data=f"x:{user.id}"),
            ]
        ]
    )
    await update.effective_message.reply_text(
        f"Confirma <b>{rotulo.lower()}</b> em {delay}s?",
        parse_mode=ParseMode.HTML,
        reply_markup=teclado,
    )


@restrito
async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _cancelar_jobs(context):
        await _responder(update, "✅ Ação cancelada.")
    else:
        await _responder(update, "ℹ️ Não havia nada agendado.")


def _cancelar_jobs(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove os jobs pendentes. Devolve ``True`` se havia algum."""
    jobs = context.job_queue.get_jobs_by_name(JOB_NAME) if context.job_queue else ()
    for job in jobs:
        job.schedule_removal()
    return bool(jobs)


# --------------------------------------------------------------------------- #
# Confirmação por botão
# --------------------------------------------------------------------------- #


@restrito
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return

    # Um callback só pode ser respondido uma vez, então cada saída abaixo chama
    # query.answer() exatamente uma vez — com alerta quando há o que explicar.
    partes = (query.data or "").split(":")

    if partes[0] == "x":
        if len(partes) == 2 and partes[1] != str(user.id):
            await query.answer("Este botão não é seu.", show_alert=True)
            return
        await query.answer()
        _cancelar_jobs(context)
        await _responder(update, "✖️ Cancelado.")
        return

    if partes[0] != "c" or len(partes) != 5:
        await query.answer()
        await _responder(update, "⚠️ Botão inválido.")
        return

    acao, delay_raw, dono, criado_em = partes[1], partes[2], partes[3], partes[4]

    if dono != str(user.id):
        await query.answer("Este botão não é seu.", show_alert=True)
        return

    await query.answer()

    if acao not in ACOES:
        await _responder(update, "⚠️ Ação desconhecida.")
        return

    if time.time() - int(criado_em) > CONFIRMATION_TTL_SECONDS:
        await _responder(update, "⏰ Confirmação expirada. Envie o comando de novo.")
        return

    delay = int(delay_raw)
    rotulo, gerundio, _ = ACOES[acao]

    _cancelar_jobs(context)  # uma ação pendente por vez
    context.job_queue.run_once(
        _executar_acao,
        when=delay,
        name=JOB_NAME,
        chat_id=query.message.chat_id,
        data={"acao": acao},
    )
    log.info("%s agendado para daqui a %ss por id=%s", rotulo, delay, user.id)

    if delay:
        await _responder(
            update, f"⏳ {gerundio} em {delay}s. Envie /cancelar para abortar."
        )
    else:
        await _responder(update, f"⏳ {gerundio}...")


async def _executar_acao(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job que dispara a ação de energia agendada.

    A ordem aqui é o detalhe que mais importa no projeto: o ``poweroff`` mata
    este processo, então o aviso final tem de ser enviado e aguardado *antes*
    da chamada — nunca depois, ou ele nunca chega.
    """
    job = context.job
    acao = job.data["acao"]
    _, gerundio, executar = ACOES[acao]

    await context.bot.send_message(job.chat_id, f"⚡ {gerundio} agora...")
    try:
        await asyncio.to_thread(executar)
    except power.PowerActionError as exc:
        log.error("falha na ação %s: %s", acao, exc)
        await context.bot.send_message(job.chat_id, f"❌ {html.escape(str(exc))}")


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
        app.add_handler(CommandHandler(["start", "ajuda", "help"], cmd_ajuda))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("desligar", cmd_desligar))
        app.add_handler(CommandHandler("reiniciar", cmd_reiniciar))
        app.add_handler(CommandHandler("cancelar", cmd_cancelar))
        app.add_handler(CommandHandler("suspender", cmd_suspender))
        app.add_handler(CommandHandler("bloquear", cmd_bloquear))
        app.add_handler(CallbackQueryHandler(on_callback))

    app.add_error_handler(on_error)
    return app
