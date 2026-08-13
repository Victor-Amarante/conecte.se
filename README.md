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
| 💬 | **Interface conversacional** | Agente LangGraph + OpenAI no WhatsApp, com memória de conversa por usuário |
| 🚏 | **Consulta por linha e ponto** | 390 linhas, ~700 sublinhas e **7.136 paradas** com geometria, buscáveis por código, nome ou destino |
| 📍 | **Paradas próximas** | Consulta espacial em PostGIS: dada a localização, retorna as paradas em ~2 ms |
| 🎯 | **Linhas prováveis** | Ranqueia as linhas que atendem o passageiro, por distância da parada, quantidade de paradas no raio e presença de terminal |
| 🗺️ | **Itinerários** | Sequência ordenada de paradas de cada linha |
| ⏰ | **Horário do próximo ônibus** | Via Google Routes API, com sentido da viagem |

### 🚧 O que ainda não existe

| | Funcionalidade | Situação |
|---|---|---|
| 🔍 | **Localização do ônibus em tempo real** | **Não implementado.** Não há fonte pública de posição de veículo (AVL) para a RMR |
| 📡 | **Monitoramento contínuo do veículo** | O endpoint `POST /location` existe e o agente prioriza GPS ao vivo quando há — mas **nada alimenta esse endpoint hoje** |
| 🔔 | **Notificações e alertas** | Não existe. O assistente é instruído a recusar quando pedem, em vez de prometer |

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
| **RUMO** (cópia local em PostGIS) | quais linhas, onde é a parada, itinerário | ~2 ms |
| **Google Routes API** | quando o próximo ônibus passa | ~400 ms |
| **Agente LangGraph** | decide o que consultar e como responder | — |

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
 Bot › Na parada em frente ao nº 4403 (Edf. Maria Dulce), a 166 m de você 📍

       1️⃣ 041 — SETÚBAL (OPCIONAL)
       2️⃣ 120 — ALTO DOIS CARNEIROS / SHOPPING RECIFE
       3️⃣ 023 — TI TANCREDO NEVES / TI AEROPORTO
       4️⃣ 011 — PIEDADE / DERBY
       5️⃣ 030 — TI RIO DOCE / BARRA DE JANGADA

       Qual delas você quer acompanhar?

Você › 4
 Bot › O 011 passa às 09:20, daqui a 2 minutos,
       sentido Piedade / Derby via Shopping Recife / Riomar 🚌
```

Quando o Google não consegue confirmar a linha escolhida, o assistente **não
inventa um horário** — diz que não confirmou e oferece as outras linhas da mesma
parada, que costuma ser o que resolve o problema do passageiro.

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic, Loguru |
| Dados | PostgreSQL 16 + PostGIS 3.4, SQLAlchemy 2.0 async, Alembic, GeoAlchemy2 |
| ETL | httpx, selectolax, pyproj, tenacity |
| IA | LangGraph, LangChain, OpenAI, langchain-mcp-adapters |
| WhatsApp | Evolution API v2.3.0 |
| Rotas | Google Routes API |
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
    ├── tests/       # 124 testes
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

Depois pareie o WhatsApp em `http://localhost:8080/manager`.

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
