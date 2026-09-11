#!/usr/bin/env bash
# Instala o bot como servico systemd de sistema. Idempotente: pode rodar de novo
# para atualizar o codigo sem perder o token ja configurado.
#
#   sudo ./deploy/install.sh
set -euo pipefail

DEST=/opt/shutdown-bot
ENV_FILE=/etc/shutdown-bot.env
UNIT=/etc/systemd/system/shutdown-bot.service
EXECUTOR_UNIT=/etc/systemd/system/shutdown-executor.service
SRC="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Rode com sudo: sudo $0" >&2
    exit 1
fi

if ! python3 -c "import ensurepip" 2>/dev/null; then
    echo "Instalando python3-venv (necessario para criar o ambiente virtual)..."
    apt-get install -y python3-venv
fi

echo "==> Copiando o projeto para $DEST"
mkdir -p "$DEST"
# O .venv fica de fora: e recriado no destino, com os caminhos certos.
# O .env local tambem: em producao o segredo mora em $ENV_FILE.
tar -C "$SRC" --exclude=.venv --exclude=.env --exclude=.git \
    --exclude=__pycache__ --exclude=.pytest_cache -cf - . | tar -C "$DEST" -xf -

echo "==> Preparando o ambiente virtual"
[[ -d "$DEST/.venv" ]] || python3 -m venv "$DEST/.venv"
"$DEST/.venv/bin/pip" install --quiet --upgrade pip
"$DEST/.venv/bin/pip" install --quiet -r "$DEST/requirements.txt"

if [[ -f "$ENV_FILE" ]]; then
    echo "==> $ENV_FILE ja existe, mantendo a configuracao atual"
else
    echo "==> Configuracao"
    read -rp "Token do bot (@BotFather): " TOKEN
    read -rp "Seu(s) ID(s) do Telegram, separados por virgula: " IDS
    if [[ -z "$TOKEN" ]]; then
        echo "Token vazio; abortando." >&2
        exit 1
    fi
    # umask antes do redirecionamento: o arquivo nunca chega a existir legivel.
    ( umask 077; cat > "$ENV_FILE" <<EOF
TELEGRAM_BOT_TOKEN=$TOKEN
ALLOWED_USER_IDS=$IDS
EOF
    )
    chown root:root "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

echo "==> Instalando o servico"
install -m 644 "$SRC/deploy/shutdown-bot.service" "$UNIT"
install -m 644 "$SRC/deploy/shutdown-executor.service" "$EXECUTOR_UNIT"
install -m 755 "$DEST/bin/shutdown-bot" /usr/local/bin/shutdown-bot
if command -v fish >/dev/null 2>&1; then
    install -Dm 644 "$DEST/completions/shutdown-bot.fish" \
        /usr/share/fish/vendor_completions.d/shutdown-bot.fish
fi
if command -v bash >/dev/null 2>&1; then
    install -Dm 644 "$DEST/completions/shutdown-bot.bash" \
        /usr/share/bash-completion/completions/shutdown-bot
fi
if command -v zsh >/dev/null 2>&1; then
    install -Dm 644 "$DEST/completions/_shutdown-bot" \
        /usr/share/zsh/site-functions/_shutdown-bot
fi
systemctl daemon-reload
systemctl enable --now shutdown-executor.service
systemctl enable shutdown-bot.service
# restart, e nao "enable --now": com o servico ja rodando, o --now nao faz nada
# e o processo continuaria com o codigo antigo carregado na memoria. Como este
# script tambem serve para atualizar, ele precisa recarregar o codigo sempre.
systemctl restart shutdown-bot.service
sleep 2
systemctl --no-pager --lines=0 status shutdown-bot.service || true

cat <<'EOF'

Pronto. Comandos uteis:
  shutdown-bot status               # consultar o status local
  shutdown-bot logs                 # acompanhar os logs
  shutdown-bot service restart      # reiniciar o servico
  shutdown-bot config               # trocar token ou allowlist
EOF
