from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shutdown_bot import bot
from shutdown_bot.config import DEFAULT_DELAY_SECONDS, MAX_DELAY_SECONDS, Config


def fake_update(user_id: int):
    """Update mínimo: só o que o decorator @restrito realmente toca."""
    mensagem = SimpleNamespace(text="/desligar", reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="alguem"),
        effective_message=mensagem,
        callback_query=None,
    )


def fake_context(allowed: set[int]):
    config = Config(token="t", allowed_user_ids=frozenset(allowed))
    return SimpleNamespace(
        application=SimpleNamespace(bot_data={"config": config}), args=[]
    )


@pytest.mark.asyncio
async def test_restrito_deixa_passar_quem_esta_na_allowlist():
    chamado = False

    @bot.restrito
    async def handler(update, context):
        nonlocal chamado
        chamado = True

    await handler(fake_update(111), fake_context({111}))
    assert chamado is True


@pytest.mark.asyncio
async def test_restrito_bloqueia_quem_nao_esta_na_allowlist():
    chamado = False

    @bot.restrito
    async def handler(update, context):
        nonlocal chamado
        chamado = True

    update = fake_update(999)
    await handler(update, fake_context({111}))

    assert chamado is False
    update.effective_message.reply_text.assert_awaited_once()
    assert "permissão" in update.effective_message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_restrito_bloqueia_com_allowlist_vazia():
    """Cinto e suspensório: mesmo sem allowlist, nada passa."""
    chamado = False

    @bot.restrito
    async def handler(update, context):
        nonlocal chamado
        chamado = True

    await handler(fake_update(111), fake_context(set()))
    assert chamado is False


def test_parse_delay_sem_argumento_usa_o_padrao():
    assert bot._parse_delay([]) == DEFAULT_DELAY_SECONDS


def test_parse_delay_aceita_numero():
    assert bot._parse_delay(["60"]) == 60
    assert bot._parse_delay(["0"]) == 0


@pytest.mark.parametrize("arg", ["abc", "-1", str(MAX_DELAY_SECONDS + 1)])
def test_parse_delay_rejeita_valores_invalidos(arg):
    with pytest.raises(ValueError):
        bot._parse_delay([arg])
