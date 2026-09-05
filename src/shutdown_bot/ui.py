"""Telas do painel: montam texto e teclado, sem falar com o Telegram.

Está separado de ``bot.py`` para que o que cada tela mostra possa ser testado
sem simular a API do Telegram: aqui só entram dados e saem strings e teclados.
"""

from __future__ import annotations

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

Tela = tuple[str, InlineKeyboardMarkup]

TITULO = "🤖 <b>Controle de energia</b>"

# Atrasos oferecidos na confirmação de desligar/reiniciar. Cobrem o uso real
# ("deixa terminar o download e desliga") sem obrigar a digitar um comando.
ATRASOS: tuple[tuple[int, str], ...] = (
    (0, "⚡ Agora"),
    (60, "⏱ 1 min"),
    (300, "⏱ 5 min"),
    (1800, "⏱ 30 min"),
)

# ação -> (emoji, rótulo). O emoji só existe para dar contraste no teclado.
ROTULOS: dict[str, tuple[str, str]] = {
    "off": ("🔴", "Desligar"),
    "reb": ("🔄", "Reiniciar"),
    "sus": ("😴", "Suspender"),
    "lock": ("🔒", "Bloquear"),
}


def rotulo(acao: str) -> str:
    """Nome legível da ação, sem emoji — para usar no meio de uma frase."""
    return ROTULOS[acao][1]


def formatar_atraso(segundos: int) -> str:
    """``0`` vira ``agora``; múltiplos de minuto viram ``5min``; o resto, ``45s``."""
    if segundos == 0:
        return "agora"
    if segundos >= 60 and segundos % 60 == 0:
        return f"{segundos // 60}min"
    return f"{segundos}s"


def em_frase(segundos: int) -> str:
    """Mesma coisa que ``formatar_atraso``, mas encaixável numa frase.

    Sem isso sai "Confirma desligar 30min?" — falta a preposição, e "em agora"
    não existe, então o zero é o caso especial.
    """
    return "agora" if segundos == 0 else f"em {formatar_atraso(segundos)}"


def _carimbo() -> str:
    """Rodapé com a hora da última atualização.

    Não é enfeite: o Telegram recusa um editMessageText cujo texto seja idêntico
    ao que já está na tela. Sem o carimbo, tocar duas vezes no mesmo botão com a
    máquina no mesmo estado devolveria BadRequest em vez de atualizar.
    """
    return f"\n\n🕗 <i>atualizado {time.strftime('%H:%M:%S')}</i>"


def _voltar(user_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton("✖️ Voltar", callback_data=f"m:{user_id}")


def painel_principal(user_id: int, aviso: str | None = None) -> Tela:
    """A tela inicial — é ela que fica no chat quando nada está acontecendo.

    ``aviso`` é o resultado da última ação ("🔒 Tela bloqueada"), que aparece
    logo abaixo do título e some na próxima vez que o painel é redesenhado.
    """
    linhas = [TITULO]
    if aviso:
        linhas.append(f"\n{aviso}")

    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔴 Desligar", callback_data=f"q:off:{user_id}"),
                InlineKeyboardButton("🔄 Reiniciar", callback_data=f"q:reb:{user_id}"),
            ],
            [
                InlineKeyboardButton("😴 Suspender", callback_data=f"q:sus:{user_id}"),
                InlineKeyboardButton("🔒 Bloquear", callback_data=f"a:lock:{user_id}"),
            ],
            [InlineKeyboardButton("📊 Status", callback_data=f"s:{user_id}")],
        ]
    )
    return "\n".join(linhas) + _carimbo(), teclado


def tela_ajuda(texto: str, user_id: int) -> Tela:
    """Lista os comandos de texto, que continuam valendo ao lado do painel."""
    return texto + _carimbo(), InlineKeyboardMarkup([[_voltar(user_id)]])


def tela_status(relatorio: str, user_id: int) -> Tela:
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("♻️ Atualizar", callback_data=f"s:{user_id}"),
                _voltar(user_id),
            ]
        ]
    )
    return relatorio + _carimbo(), teclado


def tela_confirmacao(
    acao: str, user_id: int, delay: int | None = None, criado_em: int | None = None
) -> Tela:
    """Pergunta antes de executar.

    Com ``delay=None`` (toque no painel) oferece a grade de tempos. Com um
    ``delay`` explícito (veio de ``/desligar 1800``) vira um sim/não sobre
    aquele tempo, preservando o que o comando de texto sempre fez.
    """
    emoji, nome = ROTULOS[acao]
    agora = int(time.time()) if criado_em is None else criado_em

    if delay is None and acao in ("off", "reb"):
        texto = f"{emoji} <b>{nome}</b> a máquina — quando?"
        botoes = [
            InlineKeyboardButton(
                etiqueta, callback_data=f"c:{acao}:{segundos}:{user_id}:{agora}"
            )
            for segundos, etiqueta in ATRASOS
        ]
        # duas por linha: quatro botões em fila ficam ilegíveis no celular
        linhas = [botoes[0:2], botoes[2:4], [_voltar(user_id)]]
        return texto + _carimbo(), InlineKeyboardMarkup(linhas)

    segundos = 0 if delay is None else delay
    texto = f"{emoji} Confirma <b>{nome.lower()}</b> {em_frase(segundos)}?"
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ {nome}",
                    callback_data=f"c:{acao}:{segundos}:{user_id}:{agora}",
                ),
                _voltar(user_id),
            ]
        ]
    )
    return texto + _carimbo(), teclado


def tela_agendado(acao: str, delay: int, user_id: int) -> Tela:
    """Mostrada entre a confirmação e a execução — é a janela para desistir."""
    emoji, nome = ROTULOS[acao]
    texto = f"{emoji} <b>{nome}</b> {em_frase(delay)}."
    if delay:
        texto += "\nToque em cancelar para abortar."
    teclado = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖️ Cancelar", callback_data=f"x:{user_id}")]]
    )
    return texto + _carimbo(), teclado
