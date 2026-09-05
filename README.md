# shut-down

Desligue, reinicie, suspenda ou bloqueie o seu computador **enviando uma mensagem no Telegram** — de qualquer lugar, do celular, sem precisar estar na frente da máquina.

O chat tem **uma mensagem só** — um painel de botões que o bot atualiza no lugar. Nada de histórico de comandos se acumulando:

```
🤖 Controle de energia
🕗 atualizado 14:32:07

[ 🔴 Desligar  ] [ 🔄 Reiniciar ]
[ 😴 Suspender ] [ 🔒 Bloquear  ]
[        📊 Status           ]
```

Toca em `🔴 Desligar` e **essa mesma mensagem** vira a pergunta — `⚡ Agora`, `⏱ 1 min`, `⏱ 5 min`, `⏱ 30 min` ou `✖️ Voltar`. Escolheu, ela vira a contagem com um botão de cancelar.

Mudou de ideia? Toque em cancelar (ou envie `/cancelar`) e nada acontece.

---

## Índice

- [O que ele faz](#o-que-ele-faz)
- [Antes de começar](#antes-de-começar)
- [Instalação passo a passo](#instalação-passo-a-passo)
  - [Passo 1 · Baixar o projeto](#passo-1--baixar-o-projeto)
  - [Passo 2 · Criar o seu bot no Telegram](#passo-2--criar-o-seu-bot-no-telegram)
  - [Passo 3 · Guardar o token](#passo-3--guardar-o-token)
  - [Passo 4 · Descobrir o seu ID do Telegram](#passo-4--descobrir-o-seu-id-do-telegram)
  - [Passo 5 · Liberar o seu acesso](#passo-5--liberar-o-seu-acesso)
  - [Passo 6 · Testar sem risco](#passo-6--testar-sem-risco)
  - [Passo 7 · O teste do cancelamento](#passo-7--o-teste-do-cancelamento-não-pule-este)
  - [Passo 8 · Instalar de vez](#passo-8--instalar-de-vez)
  - [Passo 9 · A prova final](#passo-9--a-prova-final)
- [Comandos](#comandos)
- [Compatibilidade](#compatibilidade)
- [Como a segurança funciona](#como-a-segurança-funciona)
- [Solução de problemas](#solução-de-problemas)
- [Manutenção](#manutenção)
- [Desinstalar](#desinstalar)
- [Para desenvolvedores](#para-desenvolvedores)

---

## O que ele faz

Um bot de Telegram que controla a energia da máquina onde ele roda. Depois de instalado, ele sobe sozinho **junto com o computador, antes mesmo de você fazer login** — então funciona mesmo que a máquina esteja na tela de senha.

Três características que valem saber de antemão:

- **Só você consegue usar.** Uma lista de IDs autorizados barra todo mundo. Nem quem descobrir o nome do seu bot consegue nada.
- **Toda ação destrutiva pede confirmação** num botão, e o atraso configurável dá tempo de você se arrepender.
- **Nenhuma porta é aberta no seu computador.** O bot faz conexões *de saída* para o Telegram. Não há nada escutando, nada exposto à internet.
- **O chat não acumula.** As suas mensagens são apagadas depois de processadas e o bot edita sempre o mesmo painel, em vez de responder com mensagem nova.

> **O que ele não faz:** ligar a máquina de volta. Computador desligado não recebe mensagem. Para isso você precisaria de Wake-on-LAN, que é outro projeto.

---

## Antes de começar

Você vai precisar de:

| Item | Detalhe |
|---|---|
| **Linux com systemd** | Ubuntu, Debian, Fedora, Mint, Zorin, Pop!\_OS, Arch, Manjaro, openSUSE... praticamente qualquer distribuição moderna. Veja [Compatibilidade](#compatibilidade) |
| **Python 3.10 ou superior** | Confira com `python3 --version` |
| **Uma conta no Telegram** | No celular ou no computador, tanto faz |
| **Acesso ao `sudo`** | Só no passo da instalação final |

Não precisa saber programar. Todos os comandos abaixo são para copiar e colar.

---

## Instalação passo a passo

### Passo 1 · Baixar o projeto

Abra o terminal e rode:

```bash
git clone https://github.com/Daniel-Carrapeiro-Mendes/shut-down.git
cd shut-down
```

Se o `git` não estiver instalado: `sudo apt install -y git` (ou `sudo dnf install -y git` no Fedora).

Instale também o pacote que cria ambientes virtuais do Python — em várias distribuições ele não vem por padrão:

```bash
sudo apt install -y python3-venv     # Ubuntu, Debian, Mint, Zorin, Pop!_OS
```

<details>
<summary>Outras distribuições</summary>

```bash
sudo dnf install -y python3-virtualenv   # Fedora
sudo pacman -S --needed python           # Arch, Manjaro (já vem incluso)
sudo zypper install -y python3-venv      # openSUSE
```
</details>

---

### Passo 2 · Criar o seu bot no Telegram

O Telegram não deixa qualquer programa mandar mensagens — você precisa criar um "bot", que é uma conta especial controlada por código. Quem cria bots é outro bot, chamado BotFather.

**2.1** — Abra o Telegram e pesquise por **`@BotFather`**. Escolha o que tem o **selo azul de verificado** (existem imitações).

**2.2** — Abra a conversa, toque em **INICIAR** e envie:

```
/newbot
```

**2.3** — Ele pergunta o **nome de exibição**. É livre, é o que aparece no topo da conversa. Por exemplo:

```
Meu PC
```

**2.4** — Agora ele pede o **username**. Este tem duas regras: precisa **terminar em `bot`** e precisa ser único no mundo inteiro. Por exemplo:

```
maxypc_desligar_bot
```

> Se aparecer *"Sorry, this username is already taken"*, é porque alguém já usou. Invente outro — acrescente números, por exemplo.

**2.5** — Deu certo? Ele responde com uma mensagem contendo o seu **token**, parecido com isto:

```
8123456789:AA-COLE-AQUI-O-SEU-TOKEN
```

> ### ⚠️ O token é a senha do seu bot
>
> Quem tiver esse texto pode controlar o seu bot. **Nunca** poste em fórum, print, vídeo ou repositório público. Se vazar, volte ao BotFather e envie `/revoke` — o token antigo morre na hora e você recebe um novo.

Guarde também o **link do seu bot**: `t.me/` seguido do username que você escolheu. No exemplo acima seria `t.me/maxypc_desligar_bot`.

---

### Passo 3 · Guardar o token

De volta ao terminal, dentro da pasta do projeto:

```bash
cp .env.example .env
nano .env
```

O `nano` é um editor de texto simples que abre dentro do terminal. Você vai ver algo assim:

```
TELEGRAM_BOT_TOKEN=
ALLOWED_USER_IDS=
```

Cole o token logo depois do `=` da primeira linha. **Sem aspas, sem espaços** ao redor do sinal de igual. Deixe a segunda linha vazia por enquanto — vamos preenchê-la no Passo 5.

```
TELEGRAM_BOT_TOKEN=8123456789:AA-COLE-AQUI-O-SEU-TOKEN
ALLOWED_USER_IDS=
```

Para salvar e sair do nano: **`Ctrl+O`**, depois **`Enter`**, depois **`Ctrl+X`**.

> 📌 **Edite o `.env`, nunca o `.env.example`.** O `.env` é ignorado pelo git e jamais vai para o GitHub. O `.env.example` é apenas o modelo em branco, e ele **é** versionado — um token colado nele acabaria publicado.

---

### Passo 4 · Descobrir o seu ID do Telegram

O bot precisa saber quem é você. Todo usuário do Telegram tem um número de identificação, e o próprio bot te conta qual é o seu:

```bash
BOOTSTRAP=1 ./run.sh
```

Na primeira vez ele demora um pouco, porque baixa as dependências. Quando terminar, o terminal mostra:

```
MODO BOOTSTRAP: apenas /meuid está disponível.
bot iniciado, aguardando mensagens
```

Isso é proposital: **sem a lista de autorizados, o bot sobe sem nenhum comando de energia**. Só existe o comando que revela o seu ID.

Agora abra o link do seu bot no Telegram (`t.me/seu_bot`), toque em **INICIAR** e envie:

```
/meuid
```

Ele responde com um número, algo como `1234567890`. **Anote.**

Volte ao terminal e pare o bot com **`Ctrl+C`**.

---

### Passo 5 · Liberar o seu acesso

```bash
nano .env
```

Coloque o número que você anotou na segunda linha:

```
TELEGRAM_BOT_TOKEN=8123456789:AA-COLE-AQUI-O-SEU-TOKEN
ALLOWED_USER_IDS=1234567890
```

Salve (`Ctrl+O`, `Enter`, `Ctrl+X`).

> Quer liberar mais alguém? Separe por vírgula: `ALLOWED_USER_IDS=1234567890,9876543210`
>
> **Deixar essa linha vazia bloqueia todo mundo, inclusive você.** É o comportamento correto e proposital — na dúvida, o sistema nega. Nunca interprete vazio como "liberado para todos".

---

### Passo 6 · Testar sem risco

```bash
./run.sh
```

O terminal deve mostrar `autorizados: [1234567890]` e `bot iniciado, aguardando mensagens`. Agora, no Telegram, teste nesta ordem:

| Envie | O que deve acontecer |
|---|---|
| `/start` | Aparece o painel de botões — e a sua mensagem some sozinha |
| `/status` | Uptime, CPU, RAM e disco da máquina |
| `/bloquear` | ⚠️ **A tela trava de verdade** — tenha a sua senha em mãos |

Quer conferir se o `/status` está falando a verdade? Compare com `uptime -p` e `free -h` em outro terminal.

---

### Passo 7 · O teste do cancelamento (não pule este)

Este é o teste que prova que você pode confiar em todo o resto.

**7.1** — Envie:

```
/desligar 60
```

**7.2** — O bot responde `Confirma desligar em 60s?` com dois botões. Toque em **✅ Desligar**.

**7.3** — A mensagem muda para `⏳ Desligando em 60s. Envie /cancelar para abortar.`

**7.4** — Agora, **antes dos 60 segundos acabarem**, envie:

```
/cancelar
```

**7.5** — Ele responde `✅ Ação cancelada.` **Fique de olho no relógio e espere passar bem mais de um minuto.**

Se a máquina continuar ligada, o mecanismo de segurança funciona. Só depois disso vale testar um desligamento real:

```
/desligar 30
```

Confirme e deixe correr. Salve o que estiver aberto antes — desta vez ele vai desligar mesmo.

---

### Passo 8 · Instalar de vez

Até aqui o bot só rodava enquanto o terminal estivesse aberto. Vamos torná-lo permanente. Ligue a máquina de novo e rode:

```bash
cd ~/shut-down          # ou onde você tiver colocado a pasta
sudo ./deploy/install.sh
```

O script vai:

1. Pedir a sua senha do `sudo`
2. Copiar o projeto para `/opt/shutdown-bot`
3. Criar o ambiente Python lá dentro
4. **Perguntar o token e o seu ID novamente**

> Por que perguntar de novo? Porque em produção o segredo passa a morar em `/etc/shutdown-bot.env`, um arquivo que só o root consegue ler (permissão `600`), **fora da pasta do projeto**. Assim o token nunca fica perto de um repositório git.

5. Ativar o serviço para iniciar junto com o sistema

No fim ele mostra o status do serviço. Você quer ver **`active (running)`** em verde.

---

### Passo 9 · A prova final

```bash
sudo reboot
```

Quando a máquina voltar e aparecer a tela de login, **não faça login**. Pegue o celular e envie `/status` ao bot.

**Se ele responder, está tudo perfeito.** Isso prova que o serviço subiu antes de qualquer sessão de usuário — que é justamente o que permite ao bot desligar a máquina sem pedir senha de administrador.

---

## Comandos

O dia a dia é pelo painel. Os comandos de texto continuam valendo para o que o painel não oferece — principalmente um atraso fora dos quatro botões — e **a mensagem que você envia é apagada** logo depois de processada.

| Comando | O que faz |
|---|---|
| `/start` | Abre (ou traz de volta) o painel |
| `/status` | Uptime, CPU, RAM, disco (e bateria, em notebooks) |
| `/desligar [segundos]` | Desliga. Sem número, o painel pergunta quando |
| `/reiniciar [segundos]` | Reinicia |
| `/cancelar` | Aborta a ação agendada |
| `/suspender` | Suspende para a RAM (dorme) |
| `/bloquear` | Bloqueia a tela |
| `/meuid` | Mostra o seu ID do Telegram |
| `/ajuda` | Lista os comandos dentro do painel |

Desligar, reiniciar **e suspender** sempre pedem confirmação. Suspender está nessa lista porque é o único erro que o bot não consegue desfazer: máquina dormindo não recebe mais comando nenhum. Bloquear vai direto, porque você desfaz na própria máquina.

O atraso aceita de 0 segundos até 24 horas: `/desligar 3600` desliga daqui a uma hora.

> **Onde foi parar o histórico.** Como o chat é limpo, ele deixa de ser o registro do que você pediu. Esse registro passa a ser o log do serviço: `journalctl -u shutdown-bot -n 50`.

---

## Compatibilidade

### ✅ Funciona

Qualquer **Linux com systemd** — que é a esmagadora maioria hoje. O projeto foi desenvolvido e testado no **Zorin OS 18.1**, mas não há nada específico dele: as ações usam `systemctl` e `loginctl`, comandos padrão do systemd, iguais em toda distribuição que o adota.

Ubuntu · Debian · Linux Mint · Zorin OS · Pop!\_OS · Fedora · RHEL / Rocky / Alma · Arch · Manjaro · EndeavourOS · openSUSE · Elementary · Kali

Funciona tanto em desktop quanto em notebook (nesse caso, o `/status` mostra também a bateria). Serve igualmente para um servidor caseiro ou um Raspberry Pi rodando Raspberry Pi OS.

### ⚠️ Precisa de adaptação

**Linux sem systemd** — Alpine (OpenRC), Void (runit), Devuan, Gentoo com OpenRC. O código do bot funciona, mas duas coisas mudam: os comandos em [`power.py`](src/shutdown_bot/power.py) (`poweroff`, `reboot`, `loginctl` viram equivalentes do seu init) e o [arquivo de serviço](deploy/shutdown-bot.service), que precisa virar um script de init do seu sistema.

**Windows e macOS** — a biblioteca do Telegram e o `psutil` (do `/status`) são multiplataforma, então o esqueleto roda. O que não roda é a camada de energia. Seria preciso trocar as listas de comandos em [`power.py`](src/shutdown_bot/power.py):

| | Windows | macOS |
|---|---|---|
| Desligar | `shutdown /s /t 0` | `osascript -e 'tell app "System Events" to shut down'` |
| Reiniciar | `shutdown /r /t 0` | `osascript -e 'tell app "System Events" to restart'` |
| Suspender | `rundll32.exe powrprof.dll,SetSuspendState 0,1,0` | `pmset sleepnow` |
| Bloquear | `rundll32.exe user32.dll,LockWorkStation` | `pmset displaysleepnow` |

...e substituir o serviço systemd pelo Agendador de Tarefas (Windows) ou por um `launchd` plist (macOS). É trabalho de uma tarde, não uma reescrita — mas **não está implementado nem testado aqui**.

---

## Como a segurança funciona

O token dá acesso ao bot, e o bot desliga a máquina. Por isso existem duas barreiras **independentes**: mesmo que a primeira caia, a segunda segura.

**1 · Lista de autorizados.** Todo comando confere o ID de quem enviou contra `ALLOWED_USER_IDS`. Quem não está na lista recebe uma recusa, e a tentativa vai para o log com ID e username. Lista vazia **nega todo mundo** — na dúvida, o sistema fecha.

**2 · Token fora do repositório.** Em produção ele vive em `/etc/shutdown-bot.env`, dono `root`, permissão `600` — só o root lê. Em desenvolvimento, num `.env` que o `.gitignore` bloqueia.

**Extras que evitam acidentes:**

- Os botões de confirmação carregam o ID de quem pediu. Em um grupo, outra pessoa tocar no botão não funciona.
- A confirmação **expira em 60 segundos**, para que um botão antigo rolando no histórico não desligue a máquina por engano.
- Ao iniciar, o bot **descarta as mensagens acumuladas** enquanto esteve fora do ar. Um `/desligar` de três horas atrás não executa quando ele volta.
- Só uma ação pode estar agendada por vez, para o `/cancelar` nunca virar loteria.

---

## Solução de problemas

<details>
<summary><b>O bot não responde nada</b></summary>

Veja os logs:

```bash
journalctl -u shutdown-bot -n 50 --no-pager
```

As causas mais comuns: token digitado errado (confira se não sobrou espaço ou aspas) ou máquina sem internet.
</details>

<details>
<summary><b>"⛔ Você não tem permissão para usar este bot"</b></summary>

O seu ID não está na lista. Envie `/meuid` — esse comando funciona para qualquer um — e compare com o que está configurado:

```bash
sudo cat /etc/shutdown-bot.env     # se já instalou o serviço
cat .env                           # se ainda está em modo de teste
```

Corrija e reinicie: `sudo systemctl restart shutdown-bot`
</details>

<details>
<summary><b>Erro "Conflict: terminated by other getUpdates request"</b></summary>

**Dois processos do bot estão rodando ao mesmo tempo** com o mesmo token — quase sempre o serviço mais um `./run.sh` esquecido. O Telegram só permite um. Pare o serviço antes de testar manualmente:

```bash
sudo systemctl stop shutdown-bot
./run.sh
# quando terminar:
sudo systemctl start shutdown-bot
```
</details>

<details>
<summary><b>Editei o código e nada mudou</b></summary>

O serviço roda a cópia em `/opt/shutdown-bot`, não a sua pasta de trabalho. Depois de mexer no código:

```bash
sudo ./deploy/install.sh
```

O script é idempotente: atualiza o código e **preserva** o token já configurado.
</details>

<details>
<summary><b>"Interactive authentication required" ao desligar</b></summary>

Acontece se você rodar via `./run.sh` por SSH: o polkit só libera desligamento para sessões locais ativas. Não é bug — é exatamente o problema que a instalação como serviço resolve, já que lá o bot roda como root. Use o `install.sh`.
</details>

<details>
<summary><b>"ensurepip is not available" ao criar o ambiente</b></summary>

Falta o pacote de ambientes virtuais do Python:

```bash
sudo apt install -y python3-venv
```
</details>

---

## Manutenção

```bash
journalctl -u shutdown-bot -f       # acompanhar os logs ao vivo
systemctl status shutdown-bot       # está rodando?
sudo systemctl restart shutdown-bot # reiniciar
sudoedit /etc/shutdown-bot.env      # trocar o token ou a lista de autorizados
```

Sempre reinicie o serviço depois de editar a configuração.

### Mudar a pasta do projeto de lugar

Pode mover à vontade — **o serviço não é afetado**, porque ele roda a cópia em `/opt/shutdown-bot`. Depois de mover, recrie o ambiente virtual, já que o `pip` guarda o caminho antigo:

```bash
mv ~/shut-down ~/Documents/Projects/
cd ~/Documents/Projects/shut-down
rm -rf .venv && ./run.sh
```

O git continua funcionando normalmente: o endereço do repositório remoto não depende do caminho local.

---

## Desinstalar

```bash
sudo systemctl disable --now shutdown-bot
sudo rm /etc/systemd/system/shutdown-bot.service
sudo rm /etc/shutdown-bot.env
sudo rm -rf /opt/shutdown-bot
sudo systemctl daemon-reload
```

E, no Telegram, envie `/deletebot` ao BotFather para apagar o bot de vez.

---

## Para desenvolvedores

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

**60 testes**, todos sem rede e sem tocar na máquina de verdade.

### Estrutura

| Arquivo | Papel |
|---|---|
| [`config.py`](src/shutdown_bot/config.py) | Lê e valida o ambiente; a regra da lista de autorizados mora aqui |
| [`power.py`](src/shutdown_bot/power.py) | Chamadas ao `systemctl` e ao `loginctl` |
| [`status.py`](src/shutdown_bot/status.py) | Relatório do `/status` |
| [`ui.py`](src/shutdown_bot/ui.py) | Monta os textos e teclados de cada tela do painel |
| [`bot.py`](src/shutdown_bot/bot.py) | Comandos, painel, confirmação e agendamento |
| [`deploy/`](deploy/) | Serviço systemd e instalador |

O passo a passo de como as peças se conectam está em [`ARQUITETURA.md`](ARQUITETURA.md).

### Um detalhe que o código protege de propósito

O `poweroff` mata o processo do bot. Se a mensagem final fosse enviada *depois* da chamada, ela nunca chegaria — o processo já teria morrido. Por isso o aviso é enviado e **aguardado** antes de desligar, e existe um teste ([`test_confirmacao.py`](tests/test_confirmacao.py)) que trava essa ordem para que ninguém a inverta sem perceber.

### Stack

Python 3.10+ · [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 22 · [psutil](https://github.com/giampaolo/psutil) · systemd

---

## Licença

MIT — use, modifique e distribua à vontade.
