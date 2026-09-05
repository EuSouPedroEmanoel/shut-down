"""O que a v1.1 acrescentou: um painel só, editado no lugar, e o chat limpo.

Se algum destes testes cair, o bot volta a poluir a conversa — que é justamente
o problema que a versão veio resolver.
"""

import time

import pytest
from conftest import CHAT, DONO, OUTRO, PAINEL, fake_callback_update, fake_context, fake_message_update
from telegram.error import BadRequest

from shutdown_bot import bot, ui


@pytest.mark.asyncio
async def test_edita_o_painel_existente_em_vez_de_mandar_mensagem_nova():
    context = fake_context({DONO}, chat_data={bot.PANEL_KEY: PAINEL})

    await bot.mostrar_painel(context, CHAT, ui.painel_principal(DONO))

    assert len(context.bot.editadas) == 1
    assert context.bot.enviadas == []


@pytest.mark.asyncio
async def test_cria_o_painel_quando_ainda_nao_existe_e_guarda_o_id():
    context = fake_context({DONO}, chat_data={})

    await bot.mostrar_painel(context, CHAT, ui.painel_principal(DONO))

    assert len(context.bot.enviadas) == 1
    assert context.chat_data[bot.PANEL_KEY] == PAINEL + 1


@pytest.mark.asyncio
async def test_dois_toques_seguidos_nao_viram_erro():
    """O Telegram recusa editar para um texto idêntico; isso não é falha."""
    context = fake_context({DONO}, chat_data={bot.PANEL_KEY: PAINEL})
    context.bot.erro_ao_editar = BadRequest("Message is not modified: ...")

    await bot.mostrar_painel(context, CHAT, ui.painel_principal(DONO))

    assert context.bot.enviadas == []  # não recria o painel à toa
    assert context.chat_data[bot.PANEL_KEY] == PAINEL


@pytest.mark.asyncio
async def test_painel_apagado_a_mao_e_recriado():
    context = fake_context({DONO}, chat_data={bot.PANEL_KEY: PAINEL})
    context.bot.erro_ao_editar = BadRequest("Message to edit not found")

    await bot.mostrar_painel(context, CHAT, ui.painel_principal(DONO))

    assert len(context.bot.enviadas) == 1
    assert context.chat_data[bot.PANEL_KEY] == PAINEL + 1


@pytest.mark.asyncio
async def test_apaga_a_mensagem_de_quem_esta_na_allowlist():
    update = fake_message_update(texto="/status")
    await bot.apagar_do_usuario(update, fake_context({DONO}))
    update.effective_message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_nao_apaga_a_mensagem_de_estranho():
    """Apagar a tentativa de um estranho seria esconder prova; o log fica."""
    update = fake_message_update(user_id=OUTRO, texto="/desligar")
    await bot.apagar_do_usuario(update, fake_context({DONO}))
    update.effective_message.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_toque_em_painel_antigo_nao_agenda_e_some():
    """Depois de um restart pode sobrar painel duplicado; o velho não vale."""
    context = fake_context({DONO}, chat_data={bot.PANEL_KEY: PAINEL})
    update = fake_callback_update(
        f"c:off:0:{DONO}:{int(time.time())}", message_id=PAINEL - 7
    )

    await bot.on_callback(update, context)

    assert context.job_queue.jobs == []
    update.callback_query.message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_apos_reinicio_o_bot_adota_o_painel_clicado():
    """Sem isso, todo systemctl restart deixaria um painel órfão no chat."""
    context = fake_context({DONO}, chat_data={})  # memória perdida no restart
    update = fake_callback_update(f"m:{DONO}", message_id=42)

    await bot.on_callback(update, context)

    assert context.chat_data[bot.PANEL_KEY] == 42
    assert context.bot.enviadas == []  # adotou, não criou um segundo painel


@pytest.mark.asyncio
async def test_desligar_com_argumento_pergunta_so_aquele_tempo():
    """É o motivo de os comandos de texto continuarem existindo."""
    context = fake_context({DONO}, args=["1800"])
    await bot.cmd_desligar(fake_message_update(texto="/desligar 1800"), context)

    assert "em 30min" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_desligar_sem_argumento_oferece_a_grade_de_tempos():
    context = fake_context({DONO})
    await bot.cmd_desligar(fake_message_update(texto="/desligar"), context)

    assert "quando?" in context.bot.ultimo_texto


@pytest.mark.asyncio
async def test_atraso_invalido_nao_abre_confirmacao():
    context = fake_context({DONO}, args=["abacaxi"])
    await bot.cmd_desligar(fake_message_update(texto="/desligar abacaxi"), context)

    texto = context.bot.ultimo_texto
    assert "não é um número" in texto
    assert "Confirma" not in texto
