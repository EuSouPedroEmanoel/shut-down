"""Leitura e validação da configuração vinda do ambiente.

Em produção as variáveis chegam pelo ``EnvironmentFile=`` do systemd. Em
desenvolvimento, um arquivo ``.env`` na raiz do projeto é lido como fallback —
variáveis já presentes no ambiente sempre têm prioridade sobre o arquivo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# raiz do projeto: .../src/shutdown_bot/config.py -> .../
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DELAY_SECONDS = 10
MAX_DELAY_SECONDS = 24 * 60 * 60  # 24h


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida — impede o bot de iniciar."""


@dataclass(frozen=True)
class Config:
    token: str
    allowed_user_ids: frozenset[int]

    def is_allowed(self, user_id: int | None) -> bool:
        """Autoriza um usuário.

        Uma allowlist vazia nega todo mundo: é a política segura por padrão, e
        nunca deve ser interpretada como "liberado para todos".
        """
        if user_id is None:
            return False
        return user_id in self.allowed_user_ids


def load_dotenv(path: Path | None = None) -> None:
    """Carrega um ``.env`` simples (``CHAVE=valor``) no ambiente do processo.

    Não sobrescreve variáveis já definidas e ignora linhas em branco e
    comentários. Silenciosamente não faz nada se o arquivo não existir.
    """
    env_path = path or (PROJECT_ROOT / ".env")
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_user_ids(raw: str) -> frozenset[int]:
    """Converte ``"123, 456"`` em ``{123, 456}``, ignorando entradas vazias."""
    ids = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ids.add(int(chunk))
        except ValueError:
            raise ConfigError(
                f"ALLOWED_USER_IDS contém um valor que não é numérico: {chunk!r}"
            ) from None
    return frozenset(ids)


def load_config(
    env: dict[str, str] | None = None, *, require_allowlist: bool = True
) -> Config:
    """Monta a configuração, falhando cedo e com mensagem acionável.

    ``require_allowlist=False`` é usado apenas no modo bootstrap, em que o bot
    sobe sem allowlist para que ``/meuid`` revele o seu ID do Telegram.
    """
    if env is None:
        load_dotenv()
        env = dict(os.environ)

    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN não definido. Crie um bot com o @BotFather "
            "(/newbot) e coloque o token no .env (dev) ou em "
            "/etc/shutdown-bot.env (produção)."
        )

    allowed = parse_user_ids(env.get("ALLOWED_USER_IDS", ""))
    if not allowed and require_allowlist:
        raise ConfigError(
            "ALLOWED_USER_IDS está vazio, o que negaria todos os comandos. "
            "Inicie o bot com BOOTSTRAP=1 e envie /meuid para descobrir o seu "
            "ID, depois preencha ALLOWED_USER_IDS."
        )

    return Config(token=token, allowed_user_ids=allowed)


def is_bootstrap() -> bool:
    """Modo de descoberta de ID: sobe o bot só com ``/meuid`` disponível."""
    return os.environ.get("BOOTSTRAP", "").strip().lower() in {"1", "true", "yes"}
