#!/usr/bin/env bash
# Modo desenvolvimento: roda o bot como o seu usuário, lendo o .env local.
# Para produção, use deploy/install.sh (serviço systemd rodando como root).
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
    echo "Criando o ambiente virtual..."
    python3 -m venv .venv || {
        echo "Falhou. Instale o venv primeiro: sudo apt install -y python3-venv" >&2
        exit 1
    }
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

if [[ ! -f .env ]]; then
    echo "Nenhum .env encontrado. Copie o .env.example e preencha o token." >&2
    exit 1
fi

PYTHONPATH=src exec .venv/bin/python -m shutdown_bot
