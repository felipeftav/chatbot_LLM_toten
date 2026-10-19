"""Serviços de voz: Reconhecimento de Fala (STT) e Síntese de Voz (TTS)."""

import io
import re
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


def limpar_texto_para_tts(texto: str) -> str:
    """
    Remove emojis, símbolos gráficos e formatações markdown do texto antes de enviá-lo
    para o sintetizador de voz (TTS), evitando que a assistente leia emojis ou diga 'asterisco'.
    Preserva a pontuação natural e a acentuação.
    """
    if not texto:
        return ""

    # Padrão Unicode para capturar emojis, símbolos gráficos e seletores
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Emojis suplementares (rostos, objetos, gestos)
        "\u2600-\u27BF"          # Símbolos diversos e Dingbats (✨, ☕, ⚡, etc.)
        "\u2300-\u23FF"          # Símbolos técnicos diversos (⏰, ⏳, etc.)
        "\u2B50\u2B55"          # Estrela, círculo
        "\uFE00-\uFE0F"          # Variation selectors
        "\u200D"                 # Zero Width Joiner
        "]+",
        flags=re.UNICODE,
    )
    # 1. Remove emojis e pictogramas
    texto_limpo = emoji_pattern.sub("", texto)

    # 2. Remove completamente asteriscos (ex: **negrito** ou *itálico* ou asterisco solto)
    # Evita que o TTS pronuncie a palavra 'asterisco'
    texto_limpo = texto_limpo.replace("*", "")

    # 3. Remove outros marcadores markdown que soam estranho em voz alta
    texto_limpo = re.sub(r"(^|\s)_+([^_]+)_+($|\s)", r"\1\2\3", texto_limpo)  # _itálico_
    texto_limpo = texto_limpo.replace("`", "")  # crases de código
    texto_limpo = texto_limpo.replace("~", "")  # tachado
    texto_limpo = re.sub(r"^#+\s*", "", texto_limpo, flags=re.MULTILINE)      # ### títulos

    # 4. Remove múltiplos espaços em branco residuais
    texto_limpo = re.sub(r"[ \t]+", " ", texto_limpo)

    # 5. Ajusta espaços antes de pontuação decorrentes das remoções (ex: "Olá !" -> "Olá!")
    texto_limpo = re.sub(r"\s+([,.:;!?])", r"\1", texto_limpo)

    return texto_limpo.strip()


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


def _executar_corrotina_com_timeout(coro, timeout_seg: float = 7.0) -> bytes:
    """
    Executa uma corrotina assíncrona em thread isolada com timeout rígido.
    Evita travamentos de workers do Gunicorn (CRITICAL WORKER TIMEOUT) no Render
    caso a conexão externa (ex: WebSocket do Edge-TTS) fique pendurada.
    """
    import concurrent.futures

    async def _com_timeout():
        return await asyncio.wait_for(coro, timeout=timeout_seg)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _com_timeout())
        return future.result(timeout=timeout_seg + 1.0)


def get_edge_tts_audio_data(text_to_speak: str, voice: str = DEFAULT_TTS_VOICE) -> str:
    """
    Sintetiza áudio utilizando Edge-TTS com voz neural (padrão: Thalita Multilingual).
    Retorna os dados do arquivo MP3 codificados em base64 com timeout protetor.
    """
    texto_limpo = limpar_texto_para_tts(text_to_speak)
    if not texto_limpo:
        return ""

    try:
        audio_bytes = _executar_corrotina_com_timeout(
            _synthesize_edge_tts_async(texto_limpo, voice),
            timeout_seg=7.0,
        )

        if not audio_bytes:
            raise ValueError("Edge-TTS retornou buffer de áudio vazio.")

        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Falha no Edge-TTS ({voice}): {e}")


def get_gemini_tts_audio_data(text_to_speak: str) -> str:
    """
    Chama a API de TTS do Gemini para sintetizar áudio natural.
    Tenta com chaves válidas e timeout seguro.
    """
    if not API_KEYS:
        raise RuntimeError("Nenhuma chave Gemini disponível.")

    texto_limpo = limpar_texto_para_tts(text_to_speak)
    if not texto_limpo:
        return ""

    payload = {
        "contents": [{"parts": [{"text": texto_limpo}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Aoede"}
                }
            },
        },
        "model": "gemini-3.8-flash-lite-tts",
    }
    headers = {"Content-Type": "application/json"}

    keys_to_try = random.sample(API_KEYS, min(2, len(API_KEYS)))

    for key in keys_to_try:
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-3.8-flash-lite-tts:generateContent?key={key}"
            )
            response = requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=6
            )

            if not response.ok:
                print(f"⚠️ Gemini TTS HTTP {response.status_code}: {response.text[:200]}")
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
            print(f"⚠️ Erro de rede na chamada Gemini TTS: {e}")

    raise RuntimeError("Todas as tentativas com Gemini TTS falharam.")


def get_gtts_audio_data(text_to_speak: str) -> str:
    """Fallback final de síntese de voz usando gTTS."""
    try:
        texto_limpo = limpar_texto_para_tts(text_to_speak)
        if not texto_limpo:
            return ""

        print("ℹ️ Usando gTTS como alternativa...")
        tts = gTTS(text=texto_limpo, lang="pt-br")
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
    texto_limpo = limpar_texto_para_tts(text_to_speak)
    if not texto_limpo:
        return ""

    try:
        return get_edge_tts_audio_data(texto_limpo, voice=voice)
    except Exception as e_edge:
        print(f"⚠️ Erro no Edge-TTS ({e_edge}). Tentando fallback com Gemini TTS...")

    try:
        return get_gemini_tts_audio_data(texto_limpo)
    except Exception as e_gemini:
        print(f"⚠️ Erro no Gemini TTS ({e_gemini}). Acionando fallback gTTS...")

    return get_gtts_audio_data(texto_limpo)

