# 🤖 LIA - Assistente Virtual Interativa (Totem Meta Day)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)
![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20%7C%203.8%20Flash-orange?logo=google)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-38B2AC?logo=tailwind-css)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Optional-336791?logo=postgresql)

A **LIA** é uma assistente virtual interativa orientada por Inteligência Artificial (LLM multimodal), desenvolvida para totens interativos durante o evento **Meta Day**. A aplicação oferece suporte completo a conversações fluidas tanto por **texto** quanto por **voz**, permitindo que visitantes, alunos e professores explorem atrações, salas e informações do evento.

---

## 📸 Demonstração da Interface

| 🚀 Tela Inicial (Identificação) | 💬 Tela do Chat de Voz e Texto (LIA) |
|:---:|:---:|
| ![Tela Inicial de Boas-vindas](docs/screenshots/tela_inicial.png) | ![Tela de Chat da LIA](docs/screenshots/tela_chat.png) |


---

## ✨ Funcionalidades Principais

- 🎙️ **Interação por Voz (Speech-to-Text)**: Gravação direta no navegador com transcrição e entendimento de linguagem natural.
- 🔊 **Síntese de Voz Neural (Text-to-Speech)**: Respostas faladas de forma ultra-natural via **Edge-TTS** com a voz prioritária **`Thalita (Multilingual)`** (`pt-BR-ThalitaMultilingualNeural`), catálogo de vozes ativas (`Antonio` e `Francisca`) e fallbacks automáticos em cascata para **Gemini TTS** e **gTTS**.
- ⚡ **Respostas Instantâneas (FAQ & Áudios Gravados)**: Perguntas frequentes do evento possuem áudios pré-gravados em alta fidelidade para resposta com latência zero.
- 🎨 **Interface Moderna para Totens**: Layout responsivo com Tailwind CSS, avatar animado, partículas visuais interativas e integração com **VLibras** para acessibilidade.
- 🛡️ **Arquitetura Segura e Modular**: Separação rigorosa de rotas, serviços de IA, áudio, banco de dados e arquivos estáticos, sem expor arquivos confidenciais.
- 📊 **Histórico e Métricas (Opcional)**: Integração com PostgreSQL para registro de perfis e interações.

---

## 🏗️ Arquitetura e Fluxo de Dados

```mermaid
sequenceDiagram
    autonumber
    actor Visitante as 👤 Visitante (Totem)
    participant UI as 🖥️ Frontend (HTML/JS)
    participant Flask as 🌐 Backend Flask (src/routes.py)
    participant AudioSvc as 🎙️ Speech Service (STT/TTS)
    participant GeminiSvc as 🤖 Gemini Service (LLM)
    participant DB as 🗄️ PostgreSQL (Opcional)

    Visitante->>UI: Fala no microfone ou digita mensagem
    alt Interação por Voz
        UI->>Flask: POST /chat (audio_file)
        Flask->>AudioSvc: Transcreve áudio para texto
    else Interação por Texto
        UI->>Flask: POST /chat (JSON: message)
    end

    Flask->>GeminiSvc: Envia mensagem com histórico da sessão
    GeminiSvc-->>Flask: Retorna resposta em texto
    
    opt Síntese de Voz Ativada
        Flask->>AudioSvc: Gera áudio (Edge-TTS Thalita -> Gemini TTS -> gTTS)
        AudioSvc-->>Flask: Retorna áudio em Base64
    end

    opt Banco Conectado
        Flask->>DB: Salva interação e perfil em log
    end

    Flask-->>UI: Retorna JSON { reply, audioData }
    UI->>Visitante: Anima avatar, exibe texto e reproduz áudio
```

---

## 📁 Estrutura do Projeto

```text
chatbot_LLM_toten/
├── data/                               # Dados, planilhas e prompts do sistema
│   ├── system_instruction.txt          # Diretrizes e personalidade da LIA
│   └── Base para a IA - MetaDay.xlsx   # Planilha de apoio de informações
│
├── docs/                               # Documentação e mídias visuais
│   └── screenshots/                    # Capturas de tela para o README
│
├── scripts/                            # Scripts utilitários de manutenção
│   ├── convert_images.py               # Otimização de imagens para WebP
│   └── create_audio.py                 # Gerador de áudios pré-gravados
│
├── src/                                # Código-fonte modular do Backend
│   ├── config.py                       # Configurações de ambiente, chaves e caminhos
│   ├── database.py                     # Pool de conexões e logging no PostgreSQL
│   ├── routes.py                       # Endpoints HTTP da API Flask
│   └── services/
│       ├── faq_service.py              # Catálogo de perguntas frequentes e áudios
│       ├── gemini_service.py           # Gestão de modelos e histórico de chat
│       └── speech_service.py           # STT (reconhecimento) e TTS (síntese)
│
├── static/                             # Arquivos estáticos servidos com segurança
│   ├── audio/respostas_pre_gravadas/   # Áudios pré-gravados em MP3
│   ├── css/styles.css                  # Estilos customizados e animações
│   ├── images/                         # Avatares, QR Codes e favicons
│   └── js/main.js                      # Lógica de interface, áudio e animação
│
├── templates/                          # Templates HTML
│   └── index.html                      # Interface principal do chat
│
├── .env.example                        # Modelo de variáveis de ambiente
├── .gitignore                          # Regras completas de exclusão do Git
├── app.py                              # Ponto de entrada enxuto do servidor
├── Procfile                            # Configuração de inicialização (Gunicorn)
├── requirements.txt                    # Dependências Python
└── README.md                           # Documentação oficial
```

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos
- **Python 3.10 ou superior** instalado.
- Chave de API do **Google Gemini** (gratuita em [Google AI Studio](https://aistudio.google.com/apikey)).

### 2. Passo a Passo de Instalação

#### No Windows (PowerShell):
```powershell
# 1. Clone ou acesse a pasta do projeto
cd c:\Dev\Faculdade\chatbot_LLM_toten

# 2. Crie o ambiente virtual
python -m venv venv

# 3. Ative o ambiente virtual
.\venv\Scripts\Activate.ps1

# Se houver erro de permissão no PowerShell, execute antes:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Instale as dependências
pip install -r requirements.txt
```

#### No Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 3. Configurar as Variáveis de Ambiente (`.env`)

Crie um arquivo `.env` na raiz do projeto baseado no `.env.example`:

```env
# Sua chave de API do Gemini (ou múltiplas chaves separadas por vírgula para balanceamento)
GEMINI_API_KEYS="AIzaSy...SUA_CHAVE_AQUI"

# (Opcional) URL de conexão do PostgreSQL (Render, Supabase, Neon, etc.)
# DATABASE_URL="postgresql://usuario:senha@host:5432/database"
```

> [!NOTE]
> Se a variável `DATABASE_URL` não for informada, o sistema iniciará normalmente em modo autônomo, sem salvar logs no PostgreSQL.

---

### 4. Iniciar o Servidor

Com o ambiente virtual ativado:

```powershell
python app.py
```

Você verá a saída de confirmação no terminal:
```text
✅ Chave Gemini válida configurada: AIzaSy...
🤖 Modelo Gemini selecionado: gemini-2.5-flash-lite
 * Running on http://127.0.0.1:5000
```

Abra no navegador:
👉 **[http://localhost:5000](http://localhost:5000)**

*(Permita o acesso ao microfone no navegador quando solicitado).*

---

## 🔌 Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Renderiza a interface do totem (`index.html`). |
| `POST` | `/chat` | Envia mensagem por texto ou gravação de voz (`audio_file`). |
| `POST` | `/get-audio` | Converte um texto específico em áudio (TTS sob demanda). |
| `GET` | `/suggest-topic`| Gera sugestão dinâmica de tópico para puxar conversa. |
| `POST` | `/summarize` | Gera resumo do histórico da conversa atual. |
| `POST` | `/restart` | Reinicia a sessão de conversação do usuário. |

---

## 🛠️ Scripts Utilitários

Na pasta `scripts/`, você encontra utilitários auxiliares:

- **`scripts/create_audio.py`**:
  Gera previamente os áudios das perguntas frequentes em formato MP3 usando **Edge-TTS** (com a voz `pt-BR-ThalitaMultilingualNeural`) e salva em `static/audio/respostas_pre_gravadas/`.
  ```powershell
  python scripts/create_audio.py
  ```

- **`scripts/convert_images.py`**:
  Converte imagens para o formato `.webp` com compressão otimizada para carregamento rápido no totem.
  ```powershell
  python scripts/convert_images.py
  ```

---

## 🩺 Solução de Problemas (Troubleshooting)

- **Erro `404 This model is no longer available`**:
  Os modelos antigos `gemini-2.0-flash` foram descontinuados pelo Google. O projeto está configurado para utilizar `gemini-2.5-flash`, `gemini-2.5-flash-lite` ou `gemini-3.8-flash`.
- **Erro de caracteres especiais / Unicode no Windows**:
  O arquivo `src/config.py` já força a codificação de saída do terminal para `UTF-8` automaticamente.
- **O microfone não grava**:
  Certifique-se de acessar via `http://localhost:5000` (ou HTTPS em produção) e autorizar o microfone nas permissões do navegador.

---

## 👥 Equipe do Projeto

Projeto desenvolvido para o **Meta Day** pelos alunos do 2º semestre de **Ciência de Dados para Negócios**:
- Felipe Tavares
- Thiago Teles
- Paulo Futagawa
- Thais Nakazone
- Riquelme Nichiyama

*Orientação: Profs. Rômulo Maia e Nathane de Castro.*
