"""Serviços de voz: Reconhecimento de Fala (STT) e Síntese de Voz (TTS)."""

import io
import json
import random
import base64
import asyncio
import requests
import edge_tts
from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr
from src.config import API_KEYS, MAX_RETRIES, DEFAULT_TTS_VOICE, VOZES_TTS_VALIDAS


def transcrever_audio_base64(audio_base64: str) -> str:
    """
    Decodifica o áudio em base64 recebido pelo frontend,
    converte para WAV via pydub e transcreve para texto usando Google SpeechRecognition.
    """
    try:
        if not audio_base64:
            raise ValueError("O áudio recebido está vazio.")

        audio_bytes = base64.b64decode(audio_base64)
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))

        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            texto = recognizer.recognize_google(audio_data, language="pt-BR")

        return texto

    except Exception as e:
        print(f"⚠️ Erro na transcrição do áudio: {e}")
        return "[Falha na transcrição]"


async def _synthesize_edge_tts_async(text: str, voice: str) -> bytes:
    """Função assíncrona interna para sintetizar áudio via edge_tts Communicate stream."""
    communicate = edge_tts.Communicate(text, voice=voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def get_edge_tts_audio_data(text_to_speak: str, voice: str = DEFAULT_TTS_VOICE) -> str:
    """
    Sintetiza áudio utilizando Edge-TTS com voz neural (padrão: Thalita Multilingual).
    Retorna os dados do arquivo MP3 codificados em base64.
    """
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                audio_bytes = executor.submit(
                    asyncio.run, _synthesize_edge_tts_async(text_to_speak, voice)
                ).result()
        else:
            audio_bytes = loop.run_until_complete(
                _synthesize_edge_tts_async(text_to_speak, voice)
            )

        if not audio_bytes:
            raise ValueError("Edge-TTS retornou buffer de áudio vazio.")

        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Falha no Edge-TTS ({voice}): {e}")


def get_gemini_tts_audio_data(text_to_speak: str) -> str:
    """
    Chama a API de TTS do Gemini para sintetizar áudio natural.
    Tenta até MAX_RETRIES com chaves válidas.
    """
    if not API_KEYS:
        raise RuntimeError("Nenhuma chave Gemini disponível.")

    payload = {
        "contents": [{"parts": [{"text": f"Fale de forma natural e clara: {text_to_speak}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Aoede"}
                }
            },
        },
        "model": "gemini-2.5-flash-tts",
    }
    headers = {"Content-Type": "application/json"}

    keys_to_try = random.sample(API_KEYS, min(3, len(API_KEYS)))

    for key in keys_to_try:
        for _ in range(MAX_RETRIES):
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.5-flash-preview-tts:generateContent?key={key}"
                )
                response = requests.post(
                    url, headers=headers, data=json.dumps(payload), timeout=25
                )

                if not response.ok:
                    print(f"⚠️ Gemini TTS HTTP {response.status_code}: {response.text[:200]}")
                    if response.status_code in (402, 403, 429):
                        break  # Tentar próxima chave
                    continue

                result = response.json()
                candidates = result.get("candidates", [])
                if not candidates:
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline_data = part.get("inlineData")
                    if inline_data and "data" in inline_data:
                        return inline_data["data"]

            except requests.RequestException as e:
                print(f"⚠️ Erro de rede na chamada TTS: {e}")

    raise RuntimeError("Todas as tentativas com Gemini TTS falharam.")


def get_gtts_audio_data(text_to_speak: str) -> str:
    """Fallback final de síntese de voz usando gTTS."""
    try:
        print("ℹ️ Usando gTTS como alternativa...")
        tts = gTTS(text=text_to_speak, lang="pt-br")
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"❌ ERRO ao gerar TTS com gTTS: {e}")
        return ""


def get_tts_audio_data(text_to_speak: str, voice: str = DEFAULT_TTS_VOICE) -> str:
    """
    Função principal de TTS com fallback em cascata:
    1. Edge-TTS (voz prioritária: pt-BR-ThalitaMultilingualNeural)
    2. Fallback 1: Gemini TTS
    3. Fallback 2: gTTS
    """
    try:
        return get_edge_tts_audio_data(text_to_speak, voice=voice)
    except Exception as e_edge:
        print(f"⚠️ Erro no Edge-TTS ({e_edge}). Tentando fallback com Gemini TTS...")

    try:
        return get_gemini_tts_audio_data(text_to_speak)
    except Exception as e_gemini:
        print(f"⚠️ Erro no Gemini TTS ({e_gemini}). Acionando fallback gTTS...")

    return get_gtts_audio_data(text_to_speak)

