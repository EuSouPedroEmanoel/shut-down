import pytest

from shutdown_bot.config import Config, ConfigError, load_config, parse_user_ids


def test_allowlist_vazia_nega_todo_mundo():
    """A regra de segurança central: vazio nunca significa 'liberado'."""
    config = Config(token="t", allowed_user_ids=frozenset())
    assert config.is_allowed(123) is False
    assert config.is_allowed(None) is False


def test_allowlist_autoriza_apenas_quem_esta_nela():
    config = Config(token="t", allowed_user_ids=frozenset({111, 222}))
    assert config.is_allowed(111) is True
    assert config.is_allowed(333) is False


def test_parse_user_ids_aceita_espacos_e_separadores():
    assert parse_user_ids(" 111, 222 ;333 ") == frozenset({111, 222, 333})


def test_parse_user_ids_ignora_entradas_vazias():
    assert parse_user_ids(",, ,") == frozenset()


def test_parse_user_ids_rejeita_valor_nao_numerico():
    with pytest.raises(ConfigError, match="não é numérico"):
        parse_user_ids("111,abc")


def test_load_config_exige_token():
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_config({"ALLOWED_USER_IDS": "1"})


def test_load_config_exige_allowlist():
    with pytest.raises(ConfigError, match="ALLOWED_USER_IDS"):
        load_config({"TELEGRAM_BOT_TOKEN": "t"})


def test_load_config_dispensa_allowlist_no_bootstrap():
    config = load_config({"TELEGRAM_BOT_TOKEN": "t"}, require_allowlist=False)
    assert config.allowed_user_ids == frozenset()
    # ...mas continua negando tudo, que é o comportamento esperado no bootstrap.
    assert config.is_allowed(1) is False
