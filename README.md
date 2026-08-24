# 🚌 Conectese — Assistente de Transporte Público no WhatsApp

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-green.svg)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-1.0-orange.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese** é um assistente conversacional no WhatsApp para quem usa ônibus
na Região Metropolitana do Recife. O passageiro manda a localização, o sistema
mostra quais linhas atendem aquele ponto, ele escolhe uma e descobre quando o
próximo passa — tudo em linguagem natural, sem instalar aplicativo nenhum.

### 🎯 Objetivo de longo prazo

Reduzir a imprevisibilidade do transporte público, permitindo que o passageiro:

- Saiba onde está o ônibus que está esperando
- Acompanhe a posição do veículo em tempo real
- Ajuste seu tempo de saída com base em informação precisa
- Tenha maior previsibilidade nos deslocamentos

> ⚠️ **Este é o destino, não o estado atual.** A seção abaixo separa o que já
> funciona do que ainda não existe. Ver a [tabela de funcionalidades](#-funcionalidades).

## ✨ Funcionalidades

### ✅ O que já funciona

| | Funcionalidade | Detalhe |
|---|---|---|
| 🧭 | **Planejamento de viagem** | O passageiro diz **para onde vai** e recebe qual ônibus pegar, em que parada embarcar, o horário e as baldeações |
| 🔁 | **Replanejamento** | "E agora, quanto tempo falta?" recalcula a **mesma** viagem — o destino fica guardado na sessão |
| 🚶 | **Trajeto curto** | Quando dá para ir a pé, informa a caminhada **e** oferece o ônibus, calculado nos nossos itinerários |
| 💬 | **Interface conversacional** | Agente LangGraph + OpenAI no WhatsApp, com memória de conversa por usuário |
| 🚏 | **Consulta por linha e ponto** | 390 linhas, ~700 sublinhas e **7.136 paradas** com geometria, buscáveis por código, nome ou destino |
| 📍 | **Paradas próximas** | Consulta espacial em PostGIS: dada a localização, retorna as paradas em ~2 ms |
| 🎯 | **Linhas prováveis** | Ranqueia as linhas que atendem o passageiro, por distância da parada, quantidade de paradas no raio e presença de terminal |
| 🗺️ | **Itinerários** | Sequência ordenada de paradas de cada linha |
| ⏰ | **Horários do ponto** | Próximas passagens na parada mais próxima, de todas as linhas |
| 💬 | **Formatação nativa** | O Markdown do modelo é convertido antes do envio — o passageiro não vê asteriscos na tela |

### 🚧 O que ainda não existe

| | Funcionalidade | Situação |
|---|---|---|
| 🔍 | **Localização do ônibus em tempo real** | **Não implementado.** Não há fonte pública de posição de veículo (AVL) para a RMR |
| 📡 | **Monitoramento contínuo do veículo** | O endpoint `POST /location` existe e o agente prioriza GPS ao vivo quando há — mas **nada alimenta esse endpoint hoje** |
| 🔔 | **Notificações e alertas** | Não existe. O assistente é instruído a recusar quando pedem, em vez de prometer |
| 🆔 | **Resposta a contato novo mascarado** | O WhatsApp às vezes entrega só um identificador (LID), sem o telefone. Sem número, não há para onde responder — hoje o descarte ao menos aparece no log |

### ⚠️ Uma distinção que importa

Quando o passageiro pergunta *"onde está o ônibus?"*, o Conectese responde
*"o próximo está previsto para 10:02"*. **São perguntas diferentes.**

Os horários vêm da **tabela programada** que o Grande Recife publica ao Google —
não de rastreamento. Se o veículo estiver atrasado, o sistema não sabe. Por isso
o assistente diz "previsto para", nunca "está chegando".

## 🏗️ Como funciona

Três fontes se combinam, e o encaixe entre as duas primeiras é o que torna o
projeto viável sem infraestrutura de rastreamento própria:

| Fonte | Responde | Latência |
|---|---|---|
| **RUMO** (cópia local em PostGIS) | quais linhas, onde é a parada, itinerário, e **como o passageiro reconhece a parada na rua** | ~2 ms |
| **Google Routes API** | qual linha leva de A a B, quando passa, onde baldear | ~400 ms |
| **Google Geocoding API** | transforma "Shopping Recife" em coordenada | ~200 ms |
| **Agente LangGraph** | decide o que consultar e como responder | — |

O Google devolve a parada por endereço — *"Av. Prof. Artur de Sá, 577"*. A base
do RUMO tem a referência que se reconhece na rua — *"EM FRENTE AO Nº4403 (EDF.
MARIA DULCE)"*. Cada embarque é enriquecido com a parada equivalente do nosso
banco, porque saber a linha sem saber onde esperar não resolve.

Os dados da rede vêm do portal [RUMO](https://virtual.granderecife.pe.gov.br/rumo/)
do Grande Recife, extraídos por um pipeline de ETL próprio e carregados em
Postgres/PostGIS. **Os códigos de linha coincidem entre RUMO e Google** (`2462`,
`011`, ...), o que permite cruzar as duas fontes sem tradução.

## 💬 Exemplo real de interação

Transcrição de uma conversa de teste, na Av. Boa Viagem:

```
Você › Oi, boa noite!
 Bot › Boa noite! Me manda sua localização pelo clipe 📎 do WhatsApp
       que eu te digo quais ônibus passam aí.

Você › [envia a localização]
 Bot › Recebi 📍 Posso te ajudar de dois jeitos:
       • Me diz *para onde você quer ir* e eu digo qual ônibus pegar e onde
       • Ou, se preferir, eu listo *todos os ônibus que passam aí*

       O que você prefere?

Você › quero ir pro Marco Zero
 Bot › Você pode pegar o 195, 062 ou 061 na parada a 25 m da Rua
       Ernesto de Paula Santos, em frente ao nº 4387 📍

       - O 195 passa às 12:33, daqui a 15 min, sentido Recife - Porto de Galinhas 🚌
       - O 062 passa às 12:34, daqui a 16 min, sentido Jardim Piedade 🚌
       - O 061 passa às 12:35, daqui a 17 min, sentido Piedade / Conde da Boa Vista 🚌

       Todas chegam ao Marco Zero em cerca de 46 minutos, sem baldeação.
```

### Os dois fluxos

O assistente **sempre oferece os dois caminhos** ao receber a localização, e
nenhum é escondido:

| Fluxo | Quando serve | O que responde |
|---|---|---|
| **Por destino** | "quero ir pro Marco Zero" | Qual linha pegar, onde embarcar, horário e baldeações |
| **Por ponto** | "quais ônibus passam aqui?" | Todas as linhas da parada mais próxima |

Perguntar o destino é o que torna a resposta útil — uma parada costuma ser
servida por muitas linhas indo para lados opostos, e listar todas transferiria
ao passageiro justamente o trabalho que o assistente deveria fazer. Mas quem só
quer conhecer as linhas do ponto tem uma pergunta legítima, e continua atendido.

> As mensagens saem com a formatação do WhatsApp (`*negrito*`, um asterisco só).
> O modelo escreve Markdown por hábito, então a conversão acontece no código,
> logo antes do envio — no prompt ela se perdia em respostas longas e chegou a
> sair `**360**` para um passageiro real.

### Destino perto: ônibus continua sendo oferecido

Quando o destino está a poucas centenas de metros, o Google não sugere ônibus —
manda caminhar. O assistente informa isso, **mas nunca para por aí**:

```
Fica pertinho — dá pra ir a pé em uns 16 min 🚶
Mas se preferir ônibus, pega o 041 na parada em frente ao nº 523, a 168 m 🚌
```

Quem pediu ônibus pode ter motivo para não querer andar: bagagem, criança no
colo, chuva, sol forte, dificuldade de locomoção. Nesse caso a linha direta é
calculada nos **nossos próprios itinerários**, comparando a ordem das paradas
para nunca sugerir a linha certa no sentido errado.

Quando não há linha direta, o trajeto vem com a baldeação explicada — onde
descer e o que pegar depois.

### Uma única fonte de horários

Perguntar de novo ("e agora?", "quanto tempo falta?") **replaneja a mesma
viagem**, com o destino guardado na sessão. Isso não é detalhe interno: é o que
mantém as respostas coerentes entre si.

Numa conversa real o assistente disse que a linha passaria em 24 minutos e, no
turno seguinte, que não conseguia confirmar o horário dela — o passageiro
perguntou, com razão, qual das duas estava certa. A causa era haver **duas**
ferramentas respondendo "quando passa", cada uma escolhendo uma parada
diferente: uma pela proximidade do passageiro, outra pelo trajeto até o
destino. Hoje existe uma só.

### A primeira mensagem de um contato novo

Nos primeiros testes era preciso **enviar tudo duas vezes**. O motivo: o
WhatsApp identifica quem envia por um LID — um identificador mascarado, não um
telefone — e manda o número real num campo à parte, que na primeira mensagem de
um contato novo costuma vir vazio. Sem número, não há para onde responder, e a
mensagem é descartada.

Isso ainda acontece, e não há solução enquanto o número não chega. O que mudou
foi a visibilidade: o descarte era **completamente silencioso** — respondia
"ok" à Evolution e não escrevia nada no log —, então uma classe inteira de
mensagens perdidas só apareceu porque um usuário reclamou. Agora aparece como
aviso.

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic, Loguru |
| Dados | PostgreSQL 16 + PostGIS 3.4, SQLAlchemy 2.0 async, Alembic, GeoAlchemy2 |
| ETL | httpx, selectolax, pyproj, tenacity |
| IA | LangGraph, LangChain, OpenAI, langchain-mcp-adapters |
| WhatsApp | Evolution API v2.3.0 |
| Rotas | Google Routes API, Google Geocoding API |
| Infra | Docker Compose, uv |

## 📁 Estrutura

```
conectese/
└── server/          # API FastAPI, ETL, agente conversacional
    ├── app/
    │   ├── agent/   # grafo LangGraph, ferramentas, MCP
    │   ├── etl/     # pipeline de dados do RUMO
    │   ├── db/      # modelos e sessões
    │   ├── routers/ # webhook, transit, bus_location
    │   └── services/
    ├── alembic/     # migrations
    ├── scripts/     # chat local, sem WhatsApp
    ├── tests/       # 169 testes
    └── docker-compose.yaml
```

Documentação detalhada do backend em **[server/README.md](server/README.md)** —
inclui o mapeamento completo da API não documentada do RUMO.

## 🚀 Começando

```bash
cd server
cp .env.example .env      # preencha OPENAI_API_KEY e GOOGLE_MAPS_API_KEY
docker compose up -d --build
docker compose exec api python -m app.etl.cli sync   # carrega a rede, ~2 min
```

Depois pareie o WhatsApp em `http://localhost:8080/manager`. Se o QR code não
aparecer, a `CONFIG_SESSION_PHONE_VERSION` está desatualizada — a falha é
silenciosa e está explicada em [server/README.md](server/README.md).

Para conversar com o agente **sem WhatsApp**:

```bash
docker compose exec api python scripts/chat.py
```

Os passos completos, incluindo o modo de desenvolvimento com hot reload, estão
em [server/README.md](server/README.md).

## 🗺️ Próximos passos

1. **Buscar uma fonte de posição em tempo real (AVL).** É o que falta para o
   objetivo principal. Caminhos possíveis: parceria com a Cittamobi, que opera o
   tempo real do Recife; solicitação do feed ao Grande Recife via Lei de Acesso
   à Informação; ou um rastreador colaborativo próprio.
2. **Rastreador colaborativo.** O servidor já está pronto para receber: o
   endpoint `POST /location` aceita posição com `codigo_linha`, e o agente
   prioriza GPS ao vivo sobre horário programado. Falta o app que alimenta —
   havia um protótipo em React, removido por ora.
3. **Melhorias conversacionais.** Notificações quando houver tempo real, consulta
   de itinerário completo, integração com metrô e BRT.

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão
adicionadas em breve.

---

**Desenvolvido para melhorar a mobilidade urbana em Recife**
