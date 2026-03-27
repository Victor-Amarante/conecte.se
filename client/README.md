# 🚌 Conectese Client - Interface Web de Rastreamento GPS

![React](https://img.shields.io/badge/React-19.2-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue.svg)
![Vite](https://img.shields.io/badge/Vite-7.2-purple.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-4.1-38bdf8.svg)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow.svg)

## 📋 Sobre o Projeto

O **Conectese Client** é a interface web do sistema de monitoramento de ônibus em tempo real para Recife. Desenvolvido com React e TypeScript, oferece uma experiência moderna e intuitiva para rastreamento GPS e envio de localização do ônibus para o backend, permitindo que o sistema calcule ETAs precisos e forneça informações em tempo real via WhatsApp.

### 🎯 Objetivo

Fornecer uma interface web acessível e moderna que permite:

- **Rastrear a localização GPS** do ônibus em tempo real
- **Enviar automaticamente** a localização para o backend
- **Visualizar informações** de coordenadas, precisão e status
- **Integrar com o backend** para cálculo de ETA e comunicação via WhatsApp

## ✨ Funcionalidades

- 📍 **Rastreamento GPS em Tempo Real**: Captura contínua da localização usando a API Geolocation do navegador
- 🔄 **Envio Automático**: Envia a localização para o backend a cada intervalo configurável
- 📊 **Visualização de Dados**: Exibe latitude, longitude, precisão e status do rastreamento
- 🎨 **UI Moderna**: Interface limpa e intuitiva com TailwindCSS e design responsivo
- 🔘 **Controle de Rastreamento**: Botão para iniciar/parar o rastreamento GPS
- ⚡ **Status em Tempo Real**: Indicadores visuais do estado do rastreamento (IDLE, TRACKING, ERROR)

## 🛠️ Tecnologias Utilizadas

- **React 19.2**: Biblioteca JavaScript para construção de interfaces
- **TypeScript 5.9**: Superset do JavaScript com tipagem estática
- **Vite 7.2**: Build tool moderna e rápida
- **TailwindCSS 4.1**: Framework CSS utility-first
- **Lucide React**: Biblioteca de ícones moderna
- **React Hooks**: Gerenciamento de estado e efeitos colaterais
- **Geolocation API**: API nativa do navegador para rastreamento GPS

## 📁 Estrutura do Projeto

```
client/
├── public/                  # Arquivos estáticos
├── src/
│   ├── components/          # Componentes React reutilizáveis
│   │   ├── GpsButton.tsx    # Botão de controle de rastreamento GPS
│   │   └── InfoRow.tsx      # Componente para exibir informações em linhas
│   ├── pages/               # Páginas da aplicação
│   │   └── TrackerPage.tsx  # Página principal de rastreamento
│   ├── hooks/               # Custom hooks
│   │   └── useGeoLocation.ts # Hook para gerenciar geolocalização e envio
│   ├── services/            # Serviços e APIs
│   │   └── api.ts           # Cliente HTTP para comunicação com backend
│   ├── enums/               # Enumerações TypeScript
│   │   └── StatusEnum.ts    # Status do sistema (IDLE, TRACKING, ERROR)
│   ├── assets/              # Recursos estáticos
│   ├── App.tsx              # Componente raiz
│   ├── main.tsx             # Ponto de entrada
│   └── index.css            # Estilos globais
├── package.json             # Dependências e scripts
├── vite.config.ts           # Configuração do Vite
├── tsconfig.json            # Configuração do TypeScript
└── README.md                # Este arquivo
```

## 🔄 Fluxo de Funcionamento

1. **Usuário inicia o rastreamento** através do botão GPS
2. **Hook `useGeoLocation`** solicita permissão de geolocalização
3. **Navegador captura** a localização GPS periodicamente
4. **Localização é enviada** automaticamente para o backend via `POST /location`
5. **Backend processa** a localização e calcula ETA quando necessário
6. **Informações são exibidas** na interface em tempo real

### Integração com Backend

O client se comunica com o backend através do endpoint:

```
POST http://localhost:8000/location
Content-Type: application/json

{
  "latitude": -8.04887728646683,
  "longitude": -34.95138771773008,
  "accuracy": 10.5,
  "timestamp": 1234567890
}
```

## 📦 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- Node.js 18+ ou superior
- npm, yarn ou pnpm (gerenciador de pacotes)
- Backend do Conectese rodando (consulte [server/README.md](../server/README.md))

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

**Nota**: O valor padrão é `http://localhost:8000` se a variável não for definida.

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

### Como Usar

1. **Acesse a aplicação** no navegador
2. **Clique no botão GPS** para iniciar o rastreamento
3. **Permita o acesso** à localização quando solicitado pelo navegador
4. **Acompanhe as informações** de latitude, longitude e precisão
5. **A localização será enviada** automaticamente para o backend a cada intervalo configurado

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

Página principal que exibe o rastreamento GPS com informações em tempo real. Gerencia o estado do rastreamento e exibe os dados de localização.

**Características:**

- Interface responsiva com design moderno
- Exibição de latitude, longitude e precisão
- Tratamento de erros de geolocalização
- Indicadores visuais de status

### GpsButton

Componente que permite ao usuário iniciar/parar o rastreamento GPS. Exibe diferentes estados visuais baseados no status atual.

**Estados:**

- **IDLE**: Rastreamento inativo
- **TRACKING**: Rastreamento ativo
- **ERROR**: Erro na geolocalização

### InfoRow

Componente reutilizável para exibir informações formatadas em linhas (label: valor).

### useGeoLocation

Hook customizado para gerenciar a geolocalização do usuário e envio automático para o backend.

**Funcionalidades:**

- Solicita permissão de geolocalização
- Captura localização GPS periodicamente
- Envia localização para o backend automaticamente
- Gerencia estados de rastreamento e erros
- Configurável com intervalo de atualização

**Uso:**

```typescript
const { data, isTracking, toggleTracking } = useGeoLocation(3000); // 3000ms = 3s
```

**Retorno:**

- `data`: Objeto com latitude, longitude, accuracy, error
- `isTracking`: Boolean indicando se está rastreando
- `toggleTracking`: Função para iniciar/parar rastreamento

## 🔧 Desenvolvimento

### Adicionar Novos Componentes

1. Crie o componente em `src/components/`
2. Exporte o componente
3. Importe e use onde necessário

### Adicionar Novas Páginas

1. Crie a página em `src/pages/`
2. Importe e use no `App.tsx`

### Estilização

O projeto utiliza TailwindCSS para estilização. Consulte a [documentação oficial](https://tailwindcss.com/docs) para mais informações.

### Configuração do Intervalo de Rastreamento

O intervalo padrão de envio de localização pode ser configurado no hook `useGeoLocation`:

```typescript
// Enviar localização a cada 3 segundos
const { data, isTracking, toggleTracking } = useGeoLocation(3000);

// Enviar localização a cada 5 segundos
const { data, isTracking, toggleTracking } = useGeoLocation(5000);
```

## 📱 Responsividade

A interface é totalmente responsiva e funciona bem em:

- 📱 Dispositivos móveis (smartphones)
- 📱 Tablets
- 💻 Desktops

## 🔒 Permissões Necessárias

A aplicação requer permissão de **geolocalização** do navegador. Certifique-se de:

- Permitir o acesso quando solicitado
- Verificar as configurações de privacidade do navegador
- Usar HTTPS em produção (geolocalização requer contexto seguro)

## 🐛 Troubleshooting

### Geolocalização não funciona

- Verifique se o navegador suporta a API Geolocation
- Certifique-se de que a permissão foi concedida
- Em desenvolvimento local, use `http://localhost` (alguns navegadores podem bloquear)
- Em produção, use HTTPS

### Erro ao enviar localização

- Verifique se o backend está rodando
- Confirme que `VITE_API_URL` está configurado corretamente
- Verifique o console do navegador para erros de rede

## 🧪 Testes

```bash
# Executar testes (quando implementados)
npm test
```

## 📝 Licença

Este projeto está em desenvolvimento. Informações sobre licença serão adicionadas em breve.

---

**Desenvolvido com ❤️ para melhorar a mobilidade urbana em Recife**
