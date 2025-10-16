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


SYSTEM_INSTRUCTION = """
Você é LIA, a assistente virtual oficial do evento Metaday.
Sua missão é ajudar os participantes com informações sobre o evento de forma amigável, clara e entusiasmada.
- Seja sempre prestativa e positiva.
- Responda de forma concisa e direta.
- Seu foco principal são as informações sobre o Metaday. Se não souber uma resposta, diga que vai procurar a informação com a organização.
- Não invente informações.
"""

# --- ATUALIZAÇÃO DO MODELO ---
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION,
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

# --- ✨ DICIONÁRIO DE PERGUNTAS E RESPOSTAS PRÉ-PROGRAMADAS ---
EVENT_INFO = {
    "Qual a programação?": "A programação do evento é a seguinte: Abertura às 9h, palestra sobre IA às 10h, e workshop de desenvolvimento às 14h. O encerramento será às 18h.",
    "Onde é o evento?": "O evento será realizado no Centro de Convenções da cidade, localizado na Avenida Principal, número 123.",
    "Como me inscrevo?": "As inscrições podem ser feitas diretamente no site oficial do evento. Procure pelo link na nossa página principal ou fale com um de nossos organizadores.",
    "Qual o valor?": "A entrada para o evento é gratuita, basta se inscrever online!",
}

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
        tts_is_enabled = False # Default para False
        
        if 'audio_file' in request.files:
            audio_file = request.files['audio_file']
            audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_file.read()}]
            prompt = "Responda ao que foi dito neste áudio."
            response = convo.send_message([prompt, audio_parts[0]])
            bot_reply_text = response.text
            tts_is_enabled = True # Assumimos que o usuário quer resposta em áudio se enviou áudio

        elif request.is_json:
            data = request.json
            tts_is_enabled = data.get('tts_enabled', False) # Pega o estado do TTS da requisição
            
            # --- ✨ LÓGICA PARA PERGUNTAS PRÉ-PROGRAMADAS ---
            if 'preset_question' in data:
                question = data.get('preset_question')
                bot_reply_text = EVENT_INFO.get(question, "Desculpe, não tenho uma resposta para essa pergunta pré-definida.")
            
            # --- Lógica original para mensagem de texto ---
            elif 'message' in data:
                user_message = data.get('message')
                if not user_message:
                    return jsonify({"error": "Nenhuma mensagem de texto fornecida."}), 400
                
                convo.send_message(user_message)
                bot_reply_text = convo.last.text
            else:
                return jsonify({"error": "Nenhuma mensagem de texto ou pergunta pré-definida fornecida."}), 400
        else:
            return jsonify({"error": "Formato de requisição inválido."}), 400

        audio_base64 = None # Inicia como None
        if tts_is_enabled and bot_reply_text:
            audio_base64 = get_tts_audio_data(bot_reply_text)

        # ✨ CORREÇÃO: Sempre retorna a lista de perguntas pré-definidas
        return jsonify({
            "reply": bot_reply_text,
            "audioData": audio_base64,
            "presetQuestions": list(EVENT_INFO.keys())
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
    
# --- ✨ NOVA ROTA: REINICIAR CONVERSA ---
@app.route('/restart', methods=['POST'])
def restart():
    try:
        # Limpa o histórico da conversa no objeto 'convo'
        convo.history.clear()
        return jsonify({"status": "success", "message": "Conversa reiniciada."})
    except Exception as e:
        print(f"Ocorreu um erro no endpoint /restart: {e}")
        traceback.print_exc()
        return jsonify({"error": "Não foi possível reiniciar a conversa."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
