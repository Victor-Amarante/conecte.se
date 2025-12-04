# 🚌 Conectese - Chatbot Inteligente para Monitoramento de Ônibus

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.122+-green.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese** é um chatbot inteligente desenvolvido para WhatsApp que permite aos cidadãos de Recife monitorar a localização dos ônibus em tempo real. O projeto visa resolver o problema de imprevisibilidade no transporte público, oferecendo aos usuários informações precisas sobre a localização dos veículos para que possam ajustar seu tempo de saída e ter maior previsibilidade em seus deslocamentos.

### 🎯 Objetivo

Facilitar o acesso à informação sobre a localização dos ônibus através de uma interface simples e acessível no WhatsApp, permitindo que os usuários:

- **Saibam onde está o ônibus** que estão esperando
- **Tenham monitoramento mais aproximado** da localização em tempo real
- **Ajustem seu tempo de saída** com base em informações precisas
- **Tenham maior previsibilidade** nos seus deslocamentos

## ✨ Funcionalidades

- 🔍 **Consulta de Localização**: Informação em tempo real sobre onde está o ônibus desejado
- 📍 **Monitoramento Aproximado**: Acompanhamento da posição do veículo
- ⏰ **Previsão de Chegada**: Estimativa de tempo para o ônibus chegar ao ponto
- 💬 **Interface Conversacional**: Interação natural via WhatsApp
- 🚏 **Consulta por Linha/Ponto**: Busca por número da linha ou ponto de parada

## 🛠️ Tecnologias Utilizadas

- **Python 3.12+**: Linguagem de programação principal
- **FastAPI**: Framework web moderno e rápido para construção da API
- **Evolution API**: Integração com WhatsApp para comunicação via chatbot
- **Arquitetura em Camadas**: Separação clara de responsabilidades (repositories, services, routers, schemas)

## 📁 Estrutura do Projeto

```
conectese/
├── app/
│   ├── __init__.py
│   ├── main.py              # Aplicação principal FastAPI
│   ├── repositories/        # Camada de acesso a dados
│   ├── routers/             # Endpoints da API
│   ├── schemas/             # Modelos de dados (Pydantic)
│   └── services/            # Lógica de negócio
├── pyproject.toml           # Configuração do projeto e dependências
├── uv.lock                  # Lock file das dependências
└── README.md                # Este arquivo
```

### Arquitetura

O projeto segue uma arquitetura em camadas bem definida:

- **Routers**: Definem os endpoints da API REST
- **Services**: Contêm a lógica de negócio e orquestração
- **Repositories**: Gerenciam o acesso e manipulação de dados
- **Schemas**: Modelos de validação e serialização de dados (Pydantic)

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- Python 3.12 ou superior
- [uv](https://github.com/astral-sh/uv) (gerenciador de pacotes Python)
- Conta/configuração da Evolution API para WhatsApp
- Acesso à API de dados dos ônibus de Recife (quando disponível)

## 🚀 Instalação

1. **Clone o repositório** (quando disponível):

   ```bash
   git clone <url-do-repositorio>
   cd conectese
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

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# Evolution API Configuration
EVOLUTION_API_URL=your_evolution_api_url
EVOLUTION_API_KEY=your_evolution_api_key
INSTANCE_NAME=your_instance_name

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

### Exemplo de Interação via WhatsApp

```
Usuário: Olá, onde está o ônibus da linha 123?

Bot: Olá! Vou verificar a localização do ônibus da linha 123 para você.
     O ônibus está atualmente na Rua X, próximo ao ponto Y.
     Tempo estimado de chegada ao seu ponto: 5 minutos.

Usuário: Qual a previsão de chegada no ponto Z?

Bot: O ônibus da linha 123 está a aproximadamente 2 km do ponto Z.
     Previsão de chegada: 8 minutos.
```

## 👥 Equipe

Este projeto está sendo desenvolvido por uma equipe do Centro de Informática da Universidade Federal de Pernambuco, comprometida em melhorar a mobilidade urbana em Recife através da tecnologia.

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão adicionadas em breve.

---

**Desenvolvido com ❤️ para melhorar a mobilidade urbana em Recife**
