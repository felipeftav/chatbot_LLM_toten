"""Definição e registro das rotas HTTP da aplicação Flask."""

import base64
import json
import traceback
from flask import Flask, request, jsonify, render_template, send_from_directory
from src.config import STATIC_DIR, DEFAULT_TTS_VOICE
from src.database import log_interaction
from src.services.faq_service import EVENT_INFO
from src.services.gemini_service import (
    model,
    SYSTEM_INSTRUCTION,
    active_conversations,
    convo_lock,
    get_or_create_chat,
    reset_chat_session,
    trim_chat_history,
)
from src.services.speech_service import (
    transcrever_audio_base64,
    get_tts_audio_data,
)


def register_routes(app: Flask) -> None:
    """Registra todas as rotas no app Flask fornecido."""

    @app.route("/")
    def index():
        """Renderiza a página principal do chat."""
        return render_template("index.html")

    @app.route("/chat", methods=["POST"])
    def chat():
        """Rota principal para envio de mensagens via texto ou áudio."""
        bot_reply_text = ""
        audio_base64 = None
        tts_is_enabled = False
        user_message_to_log = None
        profile = {}
        session_id = None
        selected_voice = DEFAULT_TTS_VOICE

        try:
            # 1. Fluxo de entrada por ÁUDIO (multipart/form-data)
            if "audio_file" in request.files:
                audio_file = request.files["audio_file"]
                profile_str = request.form.get("profile", "{}")
                try:
                    profile = json.loads(profile_str)
                except json.JSONDecodeError:
                    profile = {}
                session_id = profile.get("sessionId")

                if not session_id:
                    return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

                convo = get_or_create_chat(session_id, profile)

                audio_data = audio_file.read()
                audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_data}]

                response = convo.send_message(["Responda ao que foi dito neste áudio.", audio_parts[0]])

                audio_base64_transcript = base64.b64encode(audio_data).decode("utf-8")
                texto = transcrever_audio_base64(audio_base64_transcript)

                user_message_to_log = f"[ÁUDIO ENVIADO]: {texto}"
                bot_reply_text = response.text
                tts_is_enabled = True
                selected_voice = request.form.get("voice", DEFAULT_TTS_VOICE)

            # 2. Fluxo de entrada por TEXTO ou PERGUNTA PRESET (JSON)
            elif request.is_json:
                data = request.json or {}
                tts_is_enabled = data.get("tts_enabled", False)
                selected_voice = data.get("voice", DEFAULT_TTS_VOICE)
                profile = data.get("profile", {})
                session_id = profile.get("sessionId")

                if not session_id:
                    return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

                convo = get_or_create_chat(session_id, profile)

                # Pergunta pré-programada (FAQ)
                if "preset_question" in data:
                    question = data["preset_question"]
                    user_message_to_log = f"[PRESET]: {question}"
                    info = EVENT_INFO.get(question)
                    if info:
                        bot_reply_text = info["text"]
                        if tts_is_enabled:
                            full_audio_path = STATIC_DIR / info["audio_path"]
                            if full_audio_path.exists():
                                try:
                                    with open(full_audio_path, "rb") as f:
                                        audio_base64 = base64.b64encode(f.read()).decode("utf-8")
                                except Exception as e:
                                    print(f"⚠️ Erro ao carregar áudio preset: {e}")
                                    audio_base64 = get_tts_audio_data(bot_reply_text, voice=selected_voice)
                            else:
                                audio_base64 = get_tts_audio_data(bot_reply_text, voice=selected_voice)
                    else:
                        convo.send_message(question)
                        bot_reply_text = convo.last.text

                # Pergunta digitada livremente
                elif "message" in data:
                    user_message = data["message"]
                    user_message_to_log = user_message
                    convo.send_message(user_message)
                    bot_reply_text = convo.last.text

            # 3. Podar histórico para manter janela deslizante e poupar tokens
            trim_chat_history(convo)

            # 4. Salvar no histórico de banco de dados (se ativo)
            if user_message_to_log:
                log_interaction(user_message_to_log, bot_reply_text, profile)

            # 5. Síntese de voz TTS quando ativado e sem áudio pré-gravado
            if audio_base64 is None and tts_is_enabled and bot_reply_text:
                audio_base64 = get_tts_audio_data(bot_reply_text, voice=selected_voice)

            return jsonify({
                "reply": bot_reply_text,
                "audioData": audio_base64,
                "presetQuestions": list(EVENT_INFO.keys()),
            })

        except Exception as e:
            print(f"❌ Erro no endpoint /chat: {e}")
            traceback.print_exc()
            return jsonify({"error": "Erro interno no servidor ao processar chat."}), 500

    @app.route("/suggest-topic", methods=["GET"])
    def suggest_topic():
        """Sugere um tópico curto e dinâmico para início de conversa."""
        try:
            prompt = (
                "Sugira uma pergunta curiosa, divertida e bem curta (máximo 10 palavras), "
                "como se fosse o visitante perguntando algo sobre o evento Meta Day."
            )
            response = model.generate_content(prompt)
            return jsonify({"topic": response.text.strip().strip('"')})
        except Exception as e:
            print(f"❌ Erro no /suggest-topic: {e}")
            return jsonify({"error": f"Erro ao sugerir tópico: {e}"}), 500

    @app.route("/summarize", methods=["POST"])
    def summarize():
        """Resume a conversa atual de uma sessão."""
        try:
            data = request.json or {}
            session_id = data.get("profile", {}).get("sessionId")

            if not session_id:
                return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

            convo = None
            with convo_lock:
                if session_id in active_conversations:
                    convo = active_conversations[session_id]

            if not convo or not convo.history:
                return jsonify({"summary": "Ainda não há histórico de conversa para resumir."})

            formatted = "\n".join(
                f"{'Usuário' if m.role == 'user' else 'LIA'}: {m.parts[0].text}"
                for m in convo.history
                if m.parts and hasattr(m.parts[0], "text")
            )
            prompt = f"Resuma a conversa em português, de forma breve e objetiva:\n\n{formatted}"
            response = model.generate_content(prompt)
            return jsonify({"summary": response.text})

        except Exception as e:
            print(f"❌ Erro no /summarize: {e}")
            return jsonify({"error": f"Erro ao resumir conversa: {e}"}), 500

    @app.route("/restart", methods=["POST"])
    def restart():
        """Reinicia a sessão de conversa."""
        try:
            data = request.json or {}
            session_id = data.get("profile", {}).get("sessionId")

            if not session_id:
                return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

            reset_chat_session(session_id)
            return jsonify({"status": "success", "message": f"Sessão {session_id} reiniciada."})

        except Exception as e:
            print(f"❌ Erro no /restart: {e}")
            return jsonify({"error": f"Erro ao reiniciar sessão: {e}"}), 500

    @app.route("/get-audio", methods=["POST"])
    def get_audio():
        """Sintetiza um texto específico em áudio sob demanda."""
        try:
            data = request.json or {}
            text_to_speak = data.get("text")

            if not text_to_speak:
                return jsonify({"error": "Nenhum texto fornecido."}), 400

            voice = data.get("voice", DEFAULT_TTS_VOICE)
            audio_base64 = get_tts_audio_data(text_to_speak, voice=voice)
            return jsonify({"audioData": audio_base64})

        except Exception as e:
            print(f"❌ Erro no /get-audio: {e}")
            return jsonify({"error": "Erro interno ao gerar áudio."}), 500
