import os
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests
import json
import traceback

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do Gemini (Conversa) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não foi configurada. Crie um arquivo .env e adicione a chave.")

genai.configure(api_key=GEMINI_API_KEY)

# --- ATUALIZAÇÃO DO MODELO ---
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config={
        "temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048
    },
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ],
)
convo = model.start_chat(history=[])


# --- Lógica para o Text-to-Speech do Gemini ---
TTS_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GEMINI_API_KEY}"

def get_tts_audio_data(text_to_speak):
    """Chama a API de TTS do Gemini para converter texto em áudio."""
    payload = {
        "contents": [{"parts": [{"text": f"Fale de forma natural e clara, como uma assistente prestativa: {text_to_speak}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Aoede"}
                }
            }
        },
        "model": "gemini-2.5-flash-preview-tts"
    }
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(TTS_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0]
        audio_data = part.get('inlineData', {}).get('data')
        return audio_data
    except Exception as e:
        print(f"ERRO ao chamar ou processar a API de TTS: {e}")
        return None

# --- Configuração do Flask ---
app = Flask(__name__)
CORS(app)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        bot_reply_text = ""
        
        if 'audio_file' in request.files:
            audio_file = request.files['audio_file']
            audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_file.read()}]
            prompt = "Você é um assistente virtual. Ouça este áudio e responda de forma concisa e amigável."
            response = convo.send_message([prompt, audio_parts[0]])
            bot_reply_text = response.text

        elif request.is_json:
            user_message = request.json.get('message')
            user_message = f'Você é um assistente virtual. Responda seguinte texto de forma concisa e amigável: {user_message}'
            if not user_message:
                return jsonify({"error": "Nenhuma mensagem de texto fornecida."}), 400
            
            convo.send_message(user_message)
            bot_reply_text = convo.last.text
        else:
            return jsonify({"error": "Formato de requisição inválido."}), 400

        audio_base64 = get_tts_audio_data(bot_reply_text)

        return jsonify({
            "reply": bot_reply_text,
            "audioData": audio_base64
        })

    except Exception as e:
        print(f"Ocorreu um erro inesperado no endpoint /chat: {e}")
        traceback.print_exc()
        return jsonify({"error": "Ocorreu um erro interno no servidor."}), 500

# --- ✨ NOVA ROTA: SUGERIR TÓPICO ---
@app.route('/suggest-topic', methods=['GET'])
def suggest_topic():
    try:
        prompt = "Sugira um tópico de conversa interessante e divertido, em uma única frase curta e direta para um usuário iniciar um bate-papo."
        response = model.generate_content(prompt)
        return jsonify({"topic": response.text.strip()})
    except Exception as e:
        print(f"Ocorreu um erro no endpoint /suggest-topic: {e}")
        return jsonify({"error": "Não foi possível sugerir um tópico."}), 500

# --- ✨ NOVA ROTA: RESUMIR CONVERSA ---
@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        if not convo.history:
            return jsonify({"summary": "Ainda não há histórico de conversa para resumir."})

        formatted_history = ""
        for message in convo.history:
            if not message.parts or not hasattr(message.parts[0], 'text'):
                continue
            
            role = "Usuário" if message.role == "user" else "Assistente"
            text = message.parts[0].text
            if text:
                 formatted_history += f"{role}: {text}\n"

        if not formatted_history.strip():
             return jsonify({"summary": "O histórico de conversa ainda não contém texto."})

        prompt = f"Resuma a seguinte conversa em português, em um único parágrafo curto e objetivo:\n\n---\n{formatted_history}\n---"
        
        response = model.generate_content(prompt)
        
        return jsonify({"summary": response.text})
    except Exception as e:
        print(f"Ocorreu um erro no endpoint /summarize: {e}")
        traceback.print_exc()
        return jsonify({"error": "Não foi possível resumir a conversa."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
