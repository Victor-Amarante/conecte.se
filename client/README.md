# 🚌 Conectese Client - Interface Web de Monitoramento

![React](https://img.shields.io/badge/React-19.2-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue.svg)
![Vite](https://img.shields.io/badge/Vite-7.2-purple.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-4.1-38bdf8.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese Client** é a interface web do sistema de monitoramento de ônibus em tempo real para Recife. Desenvolvido com React e TypeScript, oferece uma experiência moderna e intuitiva para que os cidadãos possam acompanhar a localização dos ônibus em tempo real, ajustar seu tempo de saída e ter maior previsibilidade em seus deslocamentos.

### 🎯 Objetivo

Fornecer uma interface web acessível e moderna que permite aos usuários:

- **Visualizar a localização** dos ônibus em tempo real
- **Monitorar o trajeto** do veículo desejado
- **Ajustar o tempo de saída** com base em informações precisas
- **Ter maior previsibilidade** nos deslocamentos
- **Acessar informações** de forma rápida e intuitiva

## ✨ Funcionalidades

- 📍 **Rastreamento em Tempo Real**: Visualização da localização atual do ônibus
- 🗺️ **Mapa Interativo**: Visualização geográfica do trajeto e posição
- ⏰ **Previsão de Chegada**: Exibição do tempo estimado de chegada
- 🔍 **Busca por Linha**: Consulta rápida por número da linha
- 📱 **Design Responsivo**: Interface adaptada para desktop e mobile
- 🎨 **UI Moderna**: Interface limpa e intuitiva com TailwindCSS

## 🛠️ Tecnologias Utilizadas

- **React 19.2**: Biblioteca JavaScript para construção de interfaces
- **TypeScript**: Superset do JavaScript com tipagem estática
- **Vite 7.2**: Build tool moderna e rápida
- **TailwindCSS 4.1**: Framework CSS utility-first
- **Lucide React**: Biblioteca de ícones moderna
- **React Hooks**: Gerenciamento de estado e efeitos colaterais

## 📁 Estrutura do Projeto

```
client/
├── public/                  # Arquivos estáticos
├── src/
│   ├── components/          # Componentes React reutilizáveis
│   │   ├── GpsButton.tsx    # Botão de geolocalização
│   │   └── InfoRow.tsx      # Linha de informação
│   ├── pages/               # Páginas da aplicação
│   │   └── TrackerPage.tsx  # Página principal de rastreamento
│   ├── hooks/               # Custom hooks
│   │   └── useGeoLocation.ts # Hook de geolocalização
│   ├── services/            # Serviços e APIs
│   │   └── api.ts           # Cliente HTTP
│   ├── enums/               # Enumerações TypeScript
│   │   └── StatusEnum.ts    # Status do sistema
│   ├── assets/              # Recursos estáticos
│   ├── App.tsx              # Componente raiz
│   ├── main.tsx             # Ponto de entrada
│   └── index.css            # Estilos globais
├── package.json             # Dependências e scripts
├── vite.config.ts           # Configuração do Vite
├── tsconfig.json            # Configuração do TypeScript
└── README.md                # Este arquivo
```

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- Node.js 18+ ou superior
- npm, yarn ou pnpm (gerenciador de pacotes)
- Acesso à API backend do Conectese (server)

## 🚀 Instalação

1. **Navegue até o diretório do client**:

   ```bash
   cd client
   ```

2. **Instale as dependências**:

   ```bash
   npm install
   # ou
   yarn install
   # ou
   pnpm install
   ```

## ⚙️ Configuração

Crie um arquivo `.env` na raiz do diretório `client` com as seguintes variáveis:

```env
# API Backend URL
VITE_API_URL=http://localhost:8000
```

## 💻 Uso

### Modo de Desenvolvimento

```bash
npm run dev
# ou
yarn dev
# ou
pnpm dev
```

A aplicação estará disponível em `http://localhost:5173` (ou outra porta se 5173 estiver ocupada)

### Build para Produção

```bash
npm run build
# ou
yarn build
# ou
pnpm build
```

Os arquivos de produção serão gerados na pasta `dist/`

### Preview da Build

```bash
npm run preview
# ou
yarn preview
# ou
pnpm preview
```

### Linting

```bash
npm run lint
# ou
yarn lint
# ou
pnpm lint
```

## 🎨 Componentes Principais

### TrackerPage

Página principal que exibe o rastreamento do ônibus com mapa e informações em tempo real.

### GpsButton

Componente que permite ao usuário compartilhar sua localização para cálculos de ETA mais precisos.

### InfoRow

Componente reutilizável para exibir informações formatadas em linhas.

### useGeoLocation

Hook customizado para gerenciar a geolocalização do usuário.

## 🔧 Desenvolvimento

### Adicionar Novos Componentes

1. Crie o componente em `src/components/`
2. Exporte o componente
3. Importe e use onde necessário

### Adicionar Novas Páginas

1. Crie a página em `src/pages/`
2. Configure a rota (quando implementado sistema de rotas)
3. Importe e use no `App.tsx`

### Estilização

O projeto utiliza TailwindCSS para estilização. Consulte a [documentação oficial](https://tailwindcss.com/docs) para mais informações.

## 📱 Responsividade

A interface é totalmente responsiva e funciona bem em:

- 📱 Dispositivos móveis (smartphones)
- 📱 Tablets
- 💻 Desktops

## 🧪 Testes

```bash
# Executar testes (quando implementados)
npm test
```

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão adicionadas em breve.

---

**Desenvolvido com ❤️ para melhorar a mobilidade urbana em Recife**
