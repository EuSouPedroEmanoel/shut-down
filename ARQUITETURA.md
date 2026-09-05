# Arquitetura

Bot de Telegram que controla a energia da máquina onde ele roda. Versão 1.1.0.

## Arquivos, na ordem em que executam

| Arquivo | O que faz | Quem chama |
|---|---|---|
| [`run.sh`](run.sh) | Modo desenvolvimento: garante a `.venv`, exige o `.env` e sobe o bot com `PYTHONPATH=src` | Você, no terminal |
| [`deploy/install.sh`](deploy/install.sh) | Copia o projeto para `/opt/shutdown-bot`, pergunta token e IDs, grava `/etc/shutdown-bot.env` com permissão `600` e liga o serviço | Você, uma vez só |
| [`deploy/shutdown-bot.service`](deploy/shutdown-bot.service) | Unit do systemd que sobe o bot como root junto com a máquina, antes de qualquer login | systemd, no boot |
| [`src/shutdown_bot/__main__.py`](src/shutdown_bot/__main__.py) | Configura o log, carrega a config, decide entre modo normal e bootstrap e inicia o polling | `python -m shutdown_bot` |
| [`src/shutdown_bot/config.py`](src/shutdown_bot/config.py) | Lê o ambiente (com o `.env` como reserva) e valida token e lista de autorizados; a regra de quem pode usar o bot mora aqui | `__main__.py` na partida, e o decorator `restrito` a cada mensagem |
| [`src/shutdown_bot/bot.py`](src/shutdown_bot/bot.py) | Registra os handlers, mantém o painel único, valida os botões e agenda as ações | `__main__.py` monta; a biblioteca chama a cada update |
| [`src/shutdown_bot/ui.py`](src/shutdown_bot/ui.py) | Monta o texto e o teclado de cada tela do painel, sem tocar na rede | `bot.py`, antes de cada edição do painel |
| [`src/shutdown_bot/status.py`](src/shutdown_bot/status.py) | Lê uptime, CPU, RAM, disco e bateria com o psutil e devolve o relatório já formatado | `bot.py`, na tela de status |
| [`src/shutdown_bot/power.py`](src/shutdown_bot/power.py) | Executa `systemctl` e `loginctl` por `subprocess`, traduzindo qualquer falha em `PowerActionError` | `bot.py`, dentro de uma thread separada |
| [`tests/conftest.py`](tests/conftest.py) | Dublês compartilhados: um `bot` falso que registra chamadas em vez de falar com o Telegram, e uma fila de jobs que não executa nada | pytest, automaticamente |
| [`.env.example`](.env.example) | Modelo com os nomes das variáveis e **sem** os valores; o `.env` de verdade nunca entra no git | Você, ao copiar |

## Como as peças se conectam

Você toca em `🔴 Desligar` no painel. O Telegram entrega um update ao polling, e a
biblioteca chama `on_callback` em `bot.py`. Antes de qualquer coisa, o decorator
`restrito` pergunta ao `config.py` se o seu ID está na lista — se não estiver, para
aí. Passando, `on_callback` confere duas coisas: se o botão é seu (o seu ID vai
embutido no `callback_data`) e se o toque veio do painel vigente, e não de uma
mensagem antiga esquecida no chat.

Só então o `ui.py` monta a tela de confirmação, e `mostrar_painel` **edita** a mesma
mensagem de sempre — é essa edição, em vez de uma resposta nova, que mantém o chat
com uma mensagem só. Você escolhe `⏱ 5 min`; o callback `c:` valida o prazo de 60
segundos do botão e registra um job único na fila da biblioteca, chamado
`acao-agendada`. Enquanto ele não dispara, cancelar é só removê-lo da fila.

Cinco minutos depois o job acorda em `_executar_acao`, edita o painel para o aviso
final, **aguarda essa edição chegar** e só aí chama `power.poweroff()`, que roda
`systemctl poweroff` numa thread separada para não travar o event loop. Em paralelo
a tudo isso, um handler no grupo 1 apaga a mensagem que você digitou, sempre depois
de os handlers de comando já terem redesenhado o painel.

## Decisões

**Um painel editado, em vez de mensagens novas.** É a mudança que define a 1.1. O
bot guarda o id da mensagem-painel e chama `editMessageText` nela a cada interação.
Responder com mensagem nova é o padrão da maioria dos bots e foi o que sujou o chat
na 1.0.

**Um carimbo de hora no rodapé de toda tela.** O Telegram recusa uma edição cujo
texto seja idêntico ao que já está na tela. Sem o carimbo, tocar duas vezes no mesmo
botão com a máquina no mesmo estado devolveria erro em vez de atualizar. O código
ainda trata esse erro, mas o carimbo faz com que ele quase nunca aconteça.

**Nada de persistência em disco para o id do painel.** A biblioteca oferece
`PicklePersistence`, mas ela gravaria o `bot_data` inteiro — e é lá que mora o
`Config`, **com o token dentro**. Segredo em arquivo é exatamente o que o `.env`
existe para evitar. Em vez disso, quando o bot reinicia e não sabe mais qual era o
painel, ele adota a mensagem em que você tocar. O efeito prático é o mesmo, sem
gravar nada.

**A limpeza do chat roda no grupo 1.** A biblioteca executa os grupos de handlers em
ordem. Comandos ficam no grupo 0 e a limpeza no grupo 1, então a sua mensagem só
desaparece depois de o painel já estar desenhado. E ela nunca apaga mensagem de quem
não está na lista de autorizados: isso seria apagar a prova de uma tentativa de
acesso, que o log precisa registrar.

**O aviso vai antes do desligamento, nunca depois.** O `poweroff` mata o processo do
bot. Uma mensagem enviada depois da chamada nunca chegaria. Há um teste em
[`tests/test_confirmacao.py`](tests/test_confirmacao.py) que trava essa ordem para que
ninguém a inverta sem perceber. A mesma lógica vale para suspender, que corta a
conexão no meio da chamada.

**`ui.py` separado de `bot.py`.** As telas viraram funções que só recebem dados e
devolvem texto e teclado. Isso permite testar o que cada tela mostra sem simular a
API do Telegram, e evita que o `bot.py` — que já cuida de permissão, agendamento e
limpeza — vire um arquivo de 500 linhas.

**`subprocess` com lista de argumentos, nunca `shell=True`.** Os comandos são listas
fixas (`["systemctl", "poweroff"]`), sem interpolar nada vindo do Telegram. Mesmo que
alguém passasse pela lista de autorizados, não há string de shell onde injetar.

**Sem `sudo` em lugar nenhum.** Em produção o serviço já roda como root pelo systemd;
em desenvolvimento, o polkit autoriza pela sessão local ativa. Pedir senha derrotaria
o propósito de controlar a máquina remotamente.

**`python-telegram-bot` em vez de chamar a API na mão.** Ela traz o polling, a fila de
jobs agendados (que é o que faz o atraso e o cancelamento funcionarem) e os teclados
de botão prontos. Sem ela, seria preciso escrever loop de long polling, repetição em
caso de falha e um agendador — três coisas fáceis de errar num bot que desliga
computador.

**Polling, não webhook.** Webhook exigiria abrir uma porta e ter certificado. Polling
faz só conexões de saída, então nada fica exposto na sua máquina.
