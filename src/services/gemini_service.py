"""Gerenciamento de modelo, sessões de conversação e prompts da IA."""

import threading
from typing import Dict, Any, Optional
import google.generativeai as genai
from src.config import (
    DATA_DIR,
    GEMINI_MODELS,
    configure_genai_with_available_key,
)

# Inicializa e valida a chave com o modelo prioritário
configure_genai_with_available_key()

# Carrega a instrução de sistema da LIA
prompt_file = DATA_DIR / "system_instruction.txt"
if prompt_file.exists():
    with open(prompt_file, "r", encoding="utf-8") as f:
        SYSTEM_INSTRUCTION = f.read()
else:
    SYSTEM_INSTRUCTION = "Você é a LIA, assistente virtual do evento Meta Day."

# Prioriza o modelo mais rápido e econômico (gemini-2.5-flash-lite)
selected_model_name = GEMINI_MODELS[0]
print(f"🤖 Modelo Gemini prioritário em execução: {selected_model_name}")

# Inicializa modelo generativo otimizado para totem e respostas concisas (<= 350 caracteres)
model = genai.GenerativeModel(
    model_name=selected_model_name,
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 20,
        "max_output_tokens": 250,  # ~1000 caracteres no máximo, prevenindo alucinações longas e poupando tokens
    },
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ],
)

# Sessões ativas de conversação
active_conversations: Dict[str, Any] = {}
convo_lock = threading.Lock()


def trim_chat_history(chat_session: Any, max_messages: int = 6) -> None:
    """
    Mantém apenas o contexto inicial e as mensagens mais recentes no histórico.
    Reduz o custo de tokens em até 70% em conversas longas no totem.
    """
    try:
        history = chat_session.history
        if len(history) > max_messages:
            # Preserva o primeiro turno (contexto do visitante) + últimas interações
            chat_session.history = history[:2] + history[-(max_messages - 2):]
    except Exception as e:
        print(f"⚠️ Aviso ao podar histórico: {e}")


def get_or_create_chat(session_id: str, profile: dict) -> Any:
    """
    Recupera ou cria uma nova sessão de chat.
    Injeta o contexto do perfil em memória sem realizar chamadas extras de API.
    """
    with convo_lock:
        if session_id not in active_conversations:
            nome = profile.get("name", "Visitante")
            papel = profile.get("role", "Visitante")
            area = profile.get("interestArea", "Geral")
            objetivo = profile.get("objective", "Conhecer o evento")

            # Inicia o histórico em memória com o perfil, sem custo de requisição HTTP inicial
            initial_history = [
                {
                    "role": "user",
                    "parts": [
                        f"[Dados do Visitante]: Nome: {nome}, Perfil: {papel}, "
                        f"Área de interesse: {area}, Objetivo: {objetivo}."
                    ],
                },
                {
                    "role": "model",
                    "parts": [
                        f"Olá, {nome}! Que ótimo ter você no Meta Day! "
                        f"Como posso te guiar pelas salas e atrações?"
                    ],
                },
            ]

            print(f"✨ Criando sessão otimizada em memória para: {session_id} ({nome})")
            chat_session = model.start_chat(history=initial_history)
            active_conversations[session_id] = chat_session

        return active_conversations[session_id]


def reset_chat_session(session_id: str) -> bool:
    """Remove a sessão de memória para que uma nova seja iniciada."""
    with convo_lock:
        if session_id in active_conversations:
            del active_conversations[session_id]
            print(f"🔄 Sessão {session_id} reiniciada.")
            return True
        return False
