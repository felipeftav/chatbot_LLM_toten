"""Configurações gerais e variáveis de ambiente do projeto."""

import sys
import os
import random
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Configuração de encoding para suporte seguro a emojis e UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Diretórios principais do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = PROJECT_ROOT / "static"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Carregar arquivo .env
load_dotenv(PROJECT_ROOT / ".env")

# Chaves Gemini (suporta múltiplas chaves separadas por vírgula)
API_KEYS = [
    key.strip()
    for key in os.getenv("GEMINI_API_KEYS", "").split(",")
    if key.strip()
]

# URL de banco de dados PostgreSQL (opcional)
DATABASE_URL = os.getenv("DATABASE_URL")

# Modelos do Google Gemini suportados (ordenados por prioridade/economia)
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",  # Prioritário: menor latência e maior economia
    "gemini-2.5-flash",       # Fallback 1: equilibrado
    "gemini-3.8-flash",       # Fallback 2: alta precisão
]

# Configurações de Voz (Edge-TTS)
VOZES_TTS_VALIDAS = {
    "Thalita (Multilingual)": "pt-BR-ThalitaMultilingualNeural",
    "Antonio": "pt-BR-AntonioNeural",
    "Francisca": "pt-BR-FranciscaNeural",
}
DEFAULT_TTS_VOICE = os.getenv("TTS_VOICE", "pt-BR-ThalitaMultilingualNeural")

# Configurações de retentativas
MAX_RETRIES = 3


def configure_genai_with_available_key() -> str:
    """Testa todas as chaves fornecidas e configura a primeira válida."""
    if not API_KEYS:
        raise ValueError("A variável GEMINI_API_KEYS não foi configurada no arquivo .env.")

    for key in API_KEYS:
        try:
            genai.configure(api_key=key)
            # Teste de validação com o modelo mais rápido e econômico
            test_model = genai.GenerativeModel("gemini-2.5-flash-lite")
            test_model.generate_content("teste")
            print(f"✅ Chave Gemini válida configurada: {key[:8]}...")
            return key
        except Exception as e:
            print(f"❌ Chave {key[:8]} inválida ou com limite atingido: {e}")

    raise RuntimeError("🚫 Nenhuma chave Gemini válida disponível.")
