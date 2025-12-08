# 🚌 Conectese Server - API Backend

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-green.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese Server** é a API backend do sistema de monitoramento de ônibus em tempo real para Recife. Desenvolvido com FastAPI, oferece endpoints REST para consulta de localização de ônibus e integração com WhatsApp através da Evolution API, permitindo que os cidadãos consultem informações sobre transporte público via chatbot inteligente.

### 🎯 Objetivo

Fornecer uma API robusta e escalável que permite:

- **Consulta de localização** de ônibus em tempo real
- **Integração com WhatsApp** via Evolution API para chatbot conversacional
- **Processamento de IA** para interpretação de mensagens e respostas inteligentes
- **Cálculo de ETA** (Estimated Time of Arrival) para pontos de parada
- **Webhook** para recebimento de mensagens do WhatsApp

## ✨ Funcionalidades

- 🔍 **API REST**: Endpoints para consulta de localização de ônibus
- 💬 **Webhook WhatsApp**: Recebimento e processamento de mensagens via Evolution API
- 🤖 **IA Conversacional**: Processamento de mensagens usando LangChain e Groq
- ⏰ **Cálculo de ETA**: Estimativa de tempo de chegada aos pontos
- 📍 **Busca por Linha/Ponto**: Consultas flexíveis por número de linha ou ponto de parada
- 🏗️ **Arquitetura em Camadas**: Separação clara de responsabilidades

## 🛠️ Tecnologias Utilizadas

- **Python 3.12+**: Linguagem de programação principal
- **FastAPI**: Framework web moderno e rápido para construção da API
- **LangChain**: Framework para desenvolvimento de aplicações com LLMs
- **Groq**: Provedor de IA para processamento de linguagem natural
- **Evolution API**: Integração com WhatsApp para comunicação via chatbot
- **Pydantic**: Validação de dados e configurações
- **Loguru**: Sistema de logging avançado
- **uv**: Gerenciador de pacotes Python moderno e rápido

## 📁 Estrutura do Projeto

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py              # Aplicação principal FastAPI
│   ├── core/
│   │   ├── config.py        # Configurações da aplicação
│   │   └── dependencies.py  # Injeção de dependências
│   ├── repositories/        # Camada de acesso a dados
│   ├── routers/             # Endpoints da API
│   │   ├── webhook.py       # Webhook do WhatsApp
│   │   └── bus_location.py # Endpoints de localização
│   ├── schemas/             # Modelos de dados (Pydantic)
│   │   └── location.py      # Schemas de localização
│   ├── services/            # Lógica de negócio
│   │   ├── ai_service.py    # Serviço de IA
│   │   ├── bus_location_service.py
│   │   ├── eta_service.py   # Cálculo de ETA
│   │   └── evolution_service.py # Integração Evolution API
│   ├── prompts/             # Prompts para IA
│   │   └── whatsapp_system_prompt.py
│   └── utils/               # Utilitários
│       └── extract_user_number.py
├── pyproject.toml           # Configuração do projeto e dependências
├── uv.lock                  # Lock file das dependências
├── .env.example            # Exemplo de variáveis de ambiente
└── README.md                # Este arquivo
```

### Arquitetura

O projeto segue uma arquitetura em camadas bem definida:

- **Routers**: Definem os endpoints da API REST e webhooks
- **Services**: Contêm a lógica de negócio e orquestração
- **Repositories**: Gerenciam o acesso e manipulação de dados
- **Schemas**: Modelos de validação e serialização de dados (Pydantic)
- **Core**: Configurações e dependências compartilhadas

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- Python 3.12 ou superior
- [uv](https://github.com/astral-sh/uv) (gerenciador de pacotes Python)
- Conta/configuração da Evolution API para WhatsApp
- Chave de API do Groq para processamento de IA
- Acesso à API de dados dos ônibus de Recife (quando disponível)

## 🚀 Instalação

1. **Navegue até o diretório do server**:

   ```bash
   cd server
   ```

2. **Instale as dependências usando uv**:

   ```bash
   uv sync
   ```

3. **Ative o ambiente virtual**:
   ```bash
   source .venv/bin/activate  # Linux/Mac
   # ou
   .venv\Scripts\activate      # Windows
   ```

## ⚙️ Configuração

Copie o arquivo `.env.example` para `.env` e configure as variáveis:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
# Evolution API Configuration
EVOLUTION_API_URL=your_evolution_api_url
EVOLUTION_API_KEY=your_evolution_api_key
INSTANCE_NAME=your_instance_name

# Groq AI Configuration
GROQ_API_KEY=your_groq_api_key

# Bus Data API (quando disponível)
BUS_API_URL=your_bus_api_url
BUS_API_KEY=your_bus_api_key

# Application Settings
DEBUG=True
LOG_LEVEL=INFO
```

## 💻 Uso

### Iniciar o servidor

```bash
uvicorn app.main:app --reload
```

O servidor estará disponível em `http://localhost:8000`

### Documentação da API

Acesse a documentação interativa da API em:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Endpoints Principais

- `POST /webhook`: Webhook para recebimento de mensagens do WhatsApp
- `GET /bus-location/{line_number}`: Consulta de localização por número de linha
- `GET /bus-location/point/{point_id}`: Consulta de localização por ponto de parada

## 🔧 Desenvolvimento

### Estrutura de Serviços

- **AI Service**: Processa mensagens usando LangChain e Groq
- **Bus Location Service**: Gerencia consultas de localização
- **ETA Service**: Calcula tempo estimado de chegada
- **Evolution Service**: Integra com a Evolution API do WhatsApp

### Adicionar Novos Endpoints

1. Crie o schema em `app/schemas/`
2. Implemente a lógica em `app/services/`
3. Crie o router em `app/routers/`
4. Registre o router em `app/main.py`

## 🧪 Testes

```bash
# Executar testes (quando implementados)
pytest
```

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão adicionadas em breve.

---

**Desenvolvido com ❤️ para melhorar a mobilidade urbana em Recife**
