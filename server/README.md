# 🚌 Conectese Server — API Backend

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-green.svg)
![PostGIS](https://img.shields.io/badge/PostGIS-3.4-blue.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese Server** é a API backend do assistente de transporte público da
Região Metropolitana do Recife. O passageiro conversa pelo WhatsApp, envia sua
localização, escolhe entre as linhas que passam por ali e acompanha quanto
tempo falta para o ônibus chegar.

O sistema é construído sobre três fundações:

1. **Uma cópia local da rede de transporte** — 390 linhas, ~700 sublinhas e
   7.136 paradas com geometria, extraídas do portal
   [RUMO](https://virtual.granderecife.pe.gov.br/rumo/) do Grande Recife e
   carregadas em Postgres/PostGIS. Responde *quais* linhas atendem o usuário e
   *onde* ficam as paradas.
2. **O Google Maps** para os horários. Responde *quando* o ônibus passa.
3. **Um agente LangGraph** com ferramentas sobre os dois, que decide o que
   consultar em vez de seguir um roteiro fixo.

### Por que duas fontes

O encaixe entre elas é o que faz o produto funcionar sem infraestrutura de
rastreamento própria:

| | RUMO (local) | Google Maps |
|---|---|---|
| Responde | quais linhas, onde é a parada, itinerário | quando o ônibus passa |
| Latência | ~2 ms (PostGIS) | ~400 ms (rede) |
| Custo | zero | por requisição |

**Os códigos de linha coincidem nas duas fontes** — o Google identifica a
agência como "Grande Recife Consórcio de Transporte" e usa os mesmos códigos
(`2462`, `1927`, ...) que o RUMO. É isso que permite cruzá-las sem tradução.

A alternativa seria depender de GPS embarcado em cada veículo, que não existe
como fonte pública. O endpoint `POST /location` continua disponível para quem
tiver rastreamento próprio: quando há posição ao vivo de uma linha, ela tem
prioridade sobre o horário programado, por ser mais precisa.

## ✨ Funcionalidades

- 🧭 **Planejamento de viagem**: origem → destino pela Routes API, com linha,
  parada de embarque, horário e baldeações; o destino fica guardado na sessão,
  então "e agora?" replaneja a **mesma** viagem
- 🚶 **Trajeto curto**: quando o Google manda caminhar, a linha direta é
  calculada nos nossos itinerários e oferecida junto
- 🗺️ **Rede de transporte completa**: paradas, linhas, sublinhas, itinerários e
  traçados, com consultas espaciais em PostGIS
- 🎯 **Linhas prováveis por localização**: dada a posição do passageiro, ranqueia
  as linhas que ele provavelmente quer
- 🤖 **Agente conversacional**: LangGraph + OpenAI, com ferramentas e memória de
  conversa persistida por número de WhatsApp
- 🔌 **Ferramentas via MCP**: capacidades externas acopláveis sem alterar o grafo
- 📍 **Localização pelo WhatsApp**: aceita `locationMessage` e `liveLocationMessage`
- 💬 **Formatação nativa do WhatsApp**: o Markdown do modelo é convertido no
  envio, para o passageiro não ver asteriscos na tela
- ⏰ **ETA a partir de GPS ao vivo**: Google Routes API, com fallback Haversine —
  usado quando há rastreamento próprio alimentando `POST /location`
- 🔄 **ETL idempotente**: sincronização do RUMO com snapshots brutos e auditoria

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic, Loguru |
| Dados | PostgreSQL 16 + PostGIS 3.4, SQLAlchemy 2.0 (async), Alembic, GeoAlchemy2 |
| ETL | httpx, selectolax, pyproj, tenacity |
| IA | LangGraph, LangChain, OpenAI, langchain-mcp-adapters |
| WhatsApp | Evolution API v2.3.0 |
| Rotas | Google Routes API |
| Pacotes | uv |

## 📁 Estrutura

```
server/
├── app/
│   ├── main.py                  # Aplicação FastAPI
│   ├── dependencies.py          # Wiring dos serviços
│   ├── agent/                   # Agente conversacional
│   │   ├── graph.py             #   StateGraph + checkpointer Postgres
│   │   ├── tools.py             #   Ferramentas sobre a rede de transporte
│   │   ├── context.py           #   Contexto do turno (usuário, localização)
│   │   ├── state.py             #   AgentState
│   │   └── mcp.py               #   Carregamento opcional de tools MCP
│   ├── etl/                     # Pipeline de dados do RUMO
│   │   ├── rumo_client.py       #   Cliente HTTP (JSON + HTML)
│   │   ├── parsers.py           #   Parse do catálogo de linhas
│   │   ├── transform.py         #   UTM 25S → WGS84, normalização
│   │   ├── load.py              #   Upserts idempotentes
│   │   ├── pipeline.py          #   Orquestração
│   │   └── cli.py               #   `python -m app.etl.cli`
│   ├── db/
│   │   ├── models.py            # Modelos SQLAlchemy
│   │   └── session.py           # Engine e sessões async
│   ├── routers/                 # webhook, bus_location, transit
│   ├── schemas/                 # Modelos Pydantic
│   ├── services/
│   │   ├── journey_service.py   #   Planejamento origem → destino
│   │   ├── geocoding_service.py #   Destino escrito → coordenada
│   │   ├── transit_service.py   #   Consultas espaciais (PostGIS)
│   │   ├── departure_service.py #   Próximas partidas numa parada
│   │   ├── session_service.py   #   Localização e destino por usuário
│   │   ├── eta_service.py       #   ETA a partir de GPS ao vivo
│   │   ├── registry.py          #   Instâncias únicas dos serviços
│   │   └── ...                  #   evolution, bus_location, webhook
│   ├── prompts/                 # Prompt de sistema do agente
│   └── utils/
│       ├── whatsapp_format.py   #   Markdown do modelo → formatação do WhatsApp
│       └── extract_user_number.py
├── alembic/                     # Migrations (0001 → 0003)
├── scripts/chat.py              # Chat local, sem WhatsApp
├── tests/                       # 169 testes (fixtures reais do RUMO)
├── docker-compose.yaml
└── pyproject.toml
```

## 📦 Pré-requisitos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Docker (para Postgres/PostGIS, Evolution API e Redis)
- Chave da OpenAI (para o agente)
- Chave do Google Maps com **duas APIs habilitadas**:
  - **Routes API** — qual linha leva de A a B, horários e baldeações
  - **Geocoding API** — transforma o destino escrito ("Shopping Recife") em
    coordenada

  Sem a Routes API o ETA cai para uma estimativa em linha reta; sem a Geocoding
  o planejamento de viagem não funciona, porque não há como resolver o destino.

## 🚀 Instalação

```bash
cd server
uv sync
cp .env.example .env   # e preencha as chaves
```

Variáveis essenciais em `.env`:

```env
AUTHENTICATION_API_KEY=...      # Evolution API
EVO_BASE_URL=...
EVO_INSTANCE_NAME=...
CONFIG_SESSION_PHONE_VERSION=2.3000.1043857760   # sem isso o QR code não gera
CONECTESE_DATABASE_URL=postgresql+asyncpg://conectese:conectese@localhost:5434/conectese
OPENAI_API_KEY=...
GOOGLE_MAPS_API_KEY=...         # Routes API + Geocoding API
```

## 🚀 Subir tudo de uma vez

```bash
cd server
cp .env.example .env    # preencha OPENAI_API_KEY e GOOGLE_MAPS_API_KEY
docker compose up -d --build
```

Isso sobe seis serviços: a API do Conectese, o Postgres/PostGIS da aplicação, a
Evolution API, o Postgres dela, o Redis e o pgAdmin. A API **aplica as
migrations sozinha** na subida, então um banco novo já nasce com o schema.

Depois, duas coisas que o compose não faz por você:

**1. Carregar os dados do RUMO** (uma vez, ~2 min):

```bash
docker compose exec api python -m app.etl.cli sync
```

**2. Parear o número do WhatsApp.** Abra `http://localhost:8080/manager`, entre
com a `AUTHENTICATION_API_KEY` do seu `.env`, crie uma instância com o nome de
`EVO_INSTANCE_NAME` e leia o QR code pelo WhatsApp.

> ⚠️ **Se o QR code não aparecer, é a versão do WhatsApp Web.** O Baileys anuncia
> a versão definida em `CONFIG_SESSION_PHONE_VERSION`; quando ela envelhece, o
> WhatsApp recusa a sessão e a instância entra em loop de reconexão **sem
> registrar erro nenhum** — a tela fica em branco e nada no log explica. A versão
> atual está em
> [`baileys-version.json`](https://raw.githubusercontent.com/WhiskeySockets/Baileys/master/src/Defaults/baileys-version.json).

Ou pela API:

```bash
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: $AUTHENTICATION_API_KEY" -H 'Content-Type: application/json' \
  -d '{"instanceName":"'"$EVO_INSTANCE_NAME"'","integration":"WHATSAPP-BAILEYS","qrcode":true}'
```

O webhook já vem configurado: a Evolution entrega em `http://api:8000/webhook`,
pelo nome do serviço na rede do Docker. Isso importa — de dentro do container,
`localhost` seria a própria Evolution, não a API.

| Serviço | Porta | Para quê |
|---|---|---|
| API do Conectese | 8000 | `/docs`, `/transit/*`, `/webhook` |
| Evolution API | 8080 | `/manager` para parear o número |
| PostGIS da aplicação | 5434 | dados de transporte e conversas |
| Postgres da Evolution | 5433 | interno da Evolution |
| pgAdmin | 4000 | inspeção visual do banco |

### Desenvolvimento sem container

O container não recarrega ao salvar arquivo. Para iterar no código, suba só a
infraestrutura e rode a API no host:

```bash
docker compose up -d conectese-db evolution-api redis postgres
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Nesse modo o `.env` vale como está (`localhost:5434`, `localhost:8080`), mas a
Evolution precisa alcançar a API no host — troque o webhook para
`http://host.docker.internal:8000/webhook`.

## 🗄️ Banco de dados

O banco da aplicação é **separado** do Postgres da Evolution API (que fica na
porta 5433). O da aplicação usa PostGIS na porta **5434**:

```bash
docker compose up -d conectese-db
uv run alembic upgrade head
```

> **Nota (Apple Silicon)**: `postgis/postgis` não publica imagem arm64, então o
> container roda sob emulação. Funciona normalmente; apenas é mais lento em
> desenvolvimento local.

## 🔄 Carregar os dados do RUMO

```bash
# Sincronização completa (~1.600 requests, 5–8 min)
uv run python -m app.etl.cli sync

# Subconjunto rápido, para desenvolvimento
uv run python -m app.etl.cli sync --lines 001,011,191

# Sem os traçados — bem mais rápido, mantém paradas e itinerários
uv run python -m app.etl.cli sync --skip-shapes

# Reaplicar transformações a partir do último snapshot, sem tocar no RUMO
uv run python -m app.etl.cli reprocess

# Conferir nosso índice contra a fonte, para uma parada
uv run python -m app.etl.cli validate --stop 190126
```

Cada execução grava os payloads brutos em `data/raw/<timestamp>/` e registra o
resultado na tabela `etl_runs`. As cargas são **upserts**: uma execução que
falha no meio nunca destrói os dados bons da anterior.

> ⚠️ **O RUMO limita clientes agressivos.** Uma sincronização completa são
> ~1.600 requests; algumas seguidas fazem o portal recusar conexões por um
> tempo. Por isso o cliente espaça as chamadas (`RUMO_REQUEST_DELAY_SECONDS`) e
> existe o `reprocess`: mudanças nas regras de transformação se aplicam ao
> snapshot salvo em segundos, sem nova coleta.

### Sobre a fonte de dados

O portal RUMO expõe uma API JSON pública, porém **não documentada e não
versionada**. Os pontos que mais importam:

| Endpoint | Observação |
|---|---|
| `GET /rumo/` | HTML; `#sel_linha` traz as 390 linhas |
| `GET /rumo/?codigo-linha=<cod>` | HTML; `#rutas-select` traz as sublinhas |
| `GET /rumo/json_mapa_paradas` | 7.136 paradas numa única chamada |
| `GET /rumo/json_paradas_linha/` | Itinerário ordenado — **exige barra final** |
| `GET /rumo/json_shape/` | Traçado — **exige barra final** |
| `GET /rumo/json_modal_paradas` | Índice parada→linhas (usado só para validação) |

- Coordenadas vêm em **UTM zona 25S (EPSG:32725)**, convertidas para WGS84 no ETL.
- `nodo` é a chave de junção entre o inventário de paradas e os itinerários.
- Em `json_modal_paradas`, os campos `latitude`/`longitude` são na verdade
  easting/northing — os nomes estão errados na origem.

## 💻 Uso

```bash
uv run uvicorn app.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`.

### Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/webhook` | Webhook da Evolution API |
| `POST` | `/location` | Recebe a posição GPS de um veículo |
| `GET` | `/location/tracked` | Linhas com sinal GPS recente |
| `GET` | `/transit/lines/probable` | **Linhas prováveis para uma localização** |
| `GET` | `/transit/stops/nearby` | Paradas mais próximas |
| `GET` | `/transit/lines/search` | Busca de linhas por código ou nome |
| `GET` | `/transit/lines/{codigo}/itinerary` | Itinerário de uma linha |
| `GET` | `/transit/stops/{stop_id}/lines` | Linhas que atendem uma parada |
| `GET` | `/health` | Health check |

Exemplo:

```bash
curl "localhost:8000/transit/lines/probable?lat=-8.0488&lon=-34.9513"
```

Omitindo `radius_m`, a busca amplia o raio automaticamente (300 m → 2,5 km) até
encontrar linhas, o que evita resposta vazia em áreas de baixa densidade.

## 🤖 O agente

O fluxo conversacional é um `StateGraph` no padrão agente-com-ferramentas: o
modelo responde ou pede ferramentas, o `ToolNode` executa, e o controle volta ao
modelo. O histórico é persistido pelo `AsyncPostgresSaver` usando o número do
WhatsApp como `thread_id` — é isso que permite ao passageiro enviar a
localização numa mensagem e escolher a linha na seguinte.

Ferramentas disponíveis: **`plan_trip`**, `find_probable_lines`,
`find_nearby_stops`, `list_lines_at_stop`, `search_lines`, `get_line_itinerary`,
`select_line`, `get_stop_departures`.

### Uma única fonte de horários

`plan_trip` é a **única** ferramenta que responde "quando passa". Quando o
passageiro pergunta de novo ("e agora?", "quanto tempo falta?"), ela é chamada
sem o argumento `destino` e replaneja a mesma viagem — o destino fica guardado
em `user_sessions`.

Isso corrige um problema observado em conversa real: existiam duas ferramentas
respondendo à mesma pergunta, e como escolhiam paradas diferentes (uma pela
proximidade do passageiro, outra pelo trajeto até o destino), davam horários
diferentes para o mesmo ônibus. O passageiro percebeu e perguntou qual estava
certo.

`get_stop_departures` cobre o outro caso — quem não tem destino e só quer saber
o movimento do ponto. Ela reporta **todas** as linhas que saem daquela parada e
nunca afirma nada sobre uma linha específica, porque a Routes API não permite
consultar uma linha isolada.

### Acoplar ferramentas via MCP

Crie `server/mcp_servers.json`:

```json
{
  "servers": {
    "clima": { "transport": "stdio", "command": "uvx", "args": ["mcp-weather"] }
  }
}
```

As ferramentas são carregadas na inicialização do agente. Falhas aqui **não são
fatais**: o agente segue com as ferramentas nativas.

## 📱 A camada do WhatsApp

Duas particularidades do canal que já custaram bugs visíveis ao passageiro.

### Formatação: WhatsApp não é Markdown

Negrito no WhatsApp é `*assim*`, com **um** asterisco. O modelo escreve Markdown
por hábito, e numa conversa real a mensagem chegou como `**360**`, com os
asteriscos à mostra.

O prompt pede a sintaxe certa, mas isso não basta: numa resposta longa a
instrução se perde. Por isso a conversão acontece **no código**, em
`utils/whatsapp_format.py`, aplicada por `EvolutionApiService.send_text_message`
logo antes do envio — negrito, títulos `#` e espaços de fim de linha. É a última
coisa que roda, então nenhuma resposta escapa.

### Mensagens descartadas ficam no log

O WhatsApp identifica quem envia por um **LID** (`148271481798877@lid`), que não
é um telefone. O número real vem em `senderPn` — e na primeira mensagem de um
contato novo esse campo costuma vir **vazio**, porque o WhatsApp ainda não
resolveu o número. Sem ele não há para onde responder, e a mensagem é
descartada; a segunda tentativa funciona.

Esse é o motivo de, nos primeiros testes, ser preciso enviar tudo duas vezes.

O descarte em si continua — não há como responder a quem não tem número —, mas
ele deixou de ser invisível. O `webhook_ignored_handler` respondia `200
{"status":"ignored"}` **sem logar nada**: para a Evolution, sucesso; para nós,
silêncio. Hoje mensagem de passageiro descartada sai como `WARNING`, enquanto
grupo e eco do próprio bot ficam em `debug`, que é ruído esperado.

```
WARNING | Mensagem do usuário DESCARTADA: masked user (LID) - cannot respond
```

## 💬 Conversar com o agente sem WhatsApp

```bash
uv run python scripts/chat.py
```

Abre um chat no terminal. O script monta payloads no mesmo formato da Evolution
e os entrega ao `WebhookService` real — só o envio da resposta é substituído por
um `print`. Ou seja, exercita o caminho de produção inteiro (parsing, sessão,
agente, ferramentas), sem precisar de instância de WhatsApp.

```
você › oi
🤖 Me manda sua localização pelo clipe 📎 ...

você › /loc                      # Cidade Universitária por padrão
🤖 Recebi 📍 Posso te ajudar de dois jeitos:
   • Me diz para onde você quer ir e eu digo qual ônibus pegar e onde
   • Ou, se preferir, eu listo todos os ônibus que passam aí

você › quero ir pro Marco Zero
🤖 Pega o 062 na parada a 25 m da Rua Ernesto de Paula Santos 📍
   Passa às 12:35, daqui a 8 min · chega por volta das 12:56 🚌
   ferramentas: plan_trip

você › e agora, quanto tempo falta?
🤖 ...
   ferramentas: plan_trip          # replaneja a MESMA viagem
```

Comandos: `/loc [lat lon]`, `/reset`, `/sair`.

O tempo de chegada funciona sem preparo nenhum — vem dos horários do Google.
Se você tiver rastreamento próprio, poste a posição e ela passa a ter
prioridade sobre o horário programado:

```bash
curl -X POST localhost:8000/location -H 'Content-Type: application/json' \
  -d '{"latitude":-8.03,"longitude":-34.92,"codigo_linha":"2462"}'
```

Quando há posição ao vivo da linha recomendada, o `plan_trip` acrescenta um
bloco `gps_ao_vivo` à primeira opção, com a distância real do veículo. Sem
rastreador, a resposta usa apenas o horário programado.

## 🧪 Testes

```bash
uv run pytest                      # tudo
uv run pytest -m "not integration" # só unitários, dispensa banco
```

Os testes de parsing e conversão usam fixtures capturadas do RUMO real, de modo
que uma mudança de layout na origem quebra o teste em vez de corromper o banco.
Os de integração pulam sozinhos quando o banco está fora ou vazio.

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão
adicionadas em breve.

---

**Desenvolvido com ❤️ para melhorar a mobilidade urbana em Recife**
