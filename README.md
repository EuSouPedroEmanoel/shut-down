# shut-down

Bot de Telegram para controlar a energia desta máquina remotamente: desligar,
reiniciar, suspender, bloquear a tela e consultar o status — por mensagem.

## Comandos

| Comando | O que faz |
|---|---|
| `/status` | Uptime, CPU, RAM e disco |
| `/desligar [segundos]` | Desliga após confirmação (padrão: 10s) |
| `/reiniciar [segundos]` | Reinicia após confirmação |
| `/cancelar` | Aborta a ação agendada |
| `/suspender` | Suspende para a RAM |
| `/bloquear` | Bloqueia a tela |
| `/meuid` | Mostra o seu ID do Telegram |

`/desligar` e `/reiniciar` sempre pedem confirmação por botão, e o atraso existe
para dar uma janela de arrependimento: `/cancelar` aborta enquanto o tempo corre.

## Segurança

Quem tem o token do bot tem o poder de desligar a máquina, então há duas
barreiras independentes:

1. **Allowlist obrigatória.** Só os IDs em `ALLOWED_USER_IDS` são atendidos.
   Uma allowlist vazia **nega todo mundo** — nunca significa "liberado para
   todos". Tentativas negadas vão para o log com ID e username.
2. **Token fora do repositório.** Em produção mora em `/etc/shutdown-bot.env`
   (`root:root`, modo `600`); em desenvolvimento, num `.env` local que o
   `.gitignore` cobre.

Os botões de confirmação carregam o ID de quem pediu e expiram em 60 segundos,
para que um botão antigo no histórico não desligue a máquina por engano.

## Instalação

### 1. Criar o bot

No Telegram, fale com o **@BotFather**, envie `/newbot`, escolha nome e username,
e guarde o token.

### 2. Descobrir o seu ID

```bash
cp .env.example .env      # preencha só TELEGRAM_BOT_TOKEN
BOOTSTRAP=1 ./run.sh      # sobe o bot só com /meuid
```

Envie `/meuid` ao bot, copie o número para `ALLOWED_USER_IDS` no `.env` e pare o
bot com `Ctrl+C`.

### 3. Testar em desenvolvimento

```bash
./run.sh
```

Roda como o seu usuário. `systemctl poweroff` passa pelo polkit e funciona
porque a sua sessão gráfica local está ativa — mas falharia via SSH, e é por
isso que a instalação de produção roda como root.

### 4. Instalar como serviço

```bash
sudo ./deploy/install.sh
```

O script copia o projeto para `/opt/shutdown-bot`, cria o ambiente virtual,
pergunta token e IDs, escreve `/etc/shutdown-bot.env` com modo `600` e habilita
o serviço. É idempotente: rodar de novo atualiza o código sem perder o token.

A partir daí o bot sobe no boot, **antes de você fazer login**, e roda como root
— então as ações de energia são chamadas diretas ao `systemctl`, sem polkit nem
`sudo` no caminho.

```bash
journalctl -u shutdown-bot -f      # logs ao vivo
systemctl restart shutdown-bot     # após editar a configuração
sudoedit /etc/shutdown-bot.env     # trocar token ou allowlist
```

## Desenvolvimento

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

**Pré-requisito:** `sudo apt install -y python3-venv` — o Python do sistema vem
sem `ensurepip`, e sem esse pacote o `python3 -m venv` falha.

### Estrutura

| Arquivo | Papel |
|---|---|
| [config.py](src/shutdown_bot/config.py) | Lê e valida o ambiente; a regra da allowlist mora aqui |
| [power.py](src/shutdown_bot/power.py) | Wrappers de `systemctl` / `loginctl` |
| [status.py](src/shutdown_bot/status.py) | Relatório do `/status` |
| [bot.py](src/shutdown_bot/bot.py) | Handlers, confirmação e agendamento |

Um detalhe de ordem que o código protege explicitamente: o `poweroff` mata o
processo do bot, então a mensagem final é enviada e aguardada **antes** de
invocar o comando — nunca depois, ou ela nunca chegaria.

## Limitações

- O bot usa polling, então precisa de internet de saída. Máquina offline não
  atende — e não há como desligá-la pelo Telegram.
- `Restart=always` cobre quedas de rede e reinícios, mas não a falta de energia.
