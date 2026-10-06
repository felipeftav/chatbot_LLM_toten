import sys
import asyncio
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import edge_tts
from src.config import STATIC_DIR, VOZES_TTS_VALIDAS, DEFAULT_TTS_VOICE
from src.services.faq_service import EVENT_INFO

# Vozes atualizadas e confirmadas como ativas pelo sistema
vozes_validas = {
    "Thalita (Multilingual)": "pt-BR-ThalitaMultilingualNeural",
    "Antonio": "pt-BR-AntonioNeural",
    "Francisca": "pt-BR-FranciscaNeural",
}
VOZ_PADRAO = DEFAULT_TTS_VOICE


async def generate_and_save_audio(text_to_speak: str, output_path: Path, voice: str = VOZ_PADRAO) -> bool:
    """Sintetiza o texto em áudio MP3 utilizando Edge-TTS e salva no disco."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"🎙️ Gerando áudio com '{voice}' para: '{output_path.name}'...")
        communicate = edge_tts.Communicate(text_to_speak, voice=voice)
        await communicate.save(str(output_path))
        print(f"✅ Salvo com sucesso: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Erro ao gerar áudio com Edge-TTS ({voice}): {e}")
        return False


async def main():
    print("--- 🎙️ Iniciando Geração de Áudios Pré-gravados com Edge-TTS ---")
    print(f"Voz prioritária configurada: {VOZ_PADRAO}")
    print(f"Vozes disponíveis no sistema: {list(vozes_validas.keys())}\n")

    total_files = len(EVENT_INFO)
    success_count = 0

    for question, info in EVENT_INFO.items():
        text = info["text"]
        rel_path = info["audio_path"]
        target_path = STATIC_DIR / rel_path

        if await generate_and_save_audio(text, target_path, voice=VOZ_PADRAO):
            success_count += 1

    print("\n--- Processo Concluído ---")
    print(f"Resumo: {success_count} de {total_files} arquivos gerados com sucesso.")


if __name__ == "__main__":
    asyncio.run(main())