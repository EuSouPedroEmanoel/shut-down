"""Ponto de entrada: ``python -m shutdown_bot``."""

from __future__ import annotations

import logging
import sys

from .bot import build_application
from .config import ConfigError, is_bootstrap, load_config

log = logging.getLogger("shutdown_bot")


def main() -> int:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        level=logging.INFO,
    )
    # A httpx loga cada requisição de polling; em INFO isso enterra o resto.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # O scheduler já tem logs próprios, mas o bot registra jobs com nome e ação.
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)

    bootstrap = is_bootstrap()
    try:
        config = load_config(require_allowlist=not bootstrap)
    except ConfigError as exc:
        log.error("%s", exc)
        return 1

    if bootstrap:
        log.warning(
            "MODO BOOTSTRAP: apenas /meuid está disponível. "
            "Preencha ALLOWED_USER_IDS e reinicie sem BOOTSTRAP=1."
        )
    else:
        log.info("autorizados: %s", sorted(config.allowed_user_ids))

    app = build_application(config, bootstrap=bootstrap)
    log.info("bot iniciado, aguardando mensagens")
    # drop_pending_updates evita executar comandos acumulados enquanto o bot
    # esteve fora do ar — incluindo um /desligar de horas atrás.
    app.run_polling(drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
