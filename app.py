# Imports built-in
import os
import io
import json
import random
import threading
import traceback
from datetime import datetime
import time

# Imports de terceiros
import requests
import base64
import pytz
from gtts import gTTS
from flask import Flask, request, jsonify, render_template, make_response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
import psycopg2
from psycopg2 import pool
from pydub import AudioSegment
import speech_recognition as sr


# ============================================================
# 🔧 CONFIGURAÇÕES INICIAIS
# ============================================================

active_conversations = {}
convo_lock = threading.Lock() # Para segurança em threads


# Carrega as variáveis do arquivo .env
load_dotenv()

# Lê todas as chaves de API listadas em GEMINI_API_KEYS (separadas por vírgula)
API_KEYS = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]

if not API_KEYS:
    raise ValueError("A variável GEMINI_API_KEYS não foi configurada no arquivo .env.")

# Testa todas as chaves e configura a primeira válida
def configure_genai_with_available_key():
    for key in API_KEYS:
        try:
            genai.configure(api_key=key)
            # Teste rápido para ver se a chave funciona
            test_model = genai.GenerativeModel("gemini-2.0-flash")
            test_model.generate_content("teste")
            print(f"✅ Chave válida configurada: {key[:8]}...")
            return True
        except Exception as e:
            print(f"❌ Chave {key[:8]} inválida ou com limite: {e}")
    raise RuntimeError("🚫 Nenhuma chave Gemini válida disponível.")

# Chama a função antes de criar o modelo LIA
configure_genai_with_available_key()


# ============================================================
# 🔗 CONEXÃO COM O BANCO DE DADOS
# ============================================================

# O Render irá popular esta variável com a URL Interna do seu lia-db
DATABASE_URL = os.getenv("DATABASE_URL") 

db_pool = None

if DATABASE_URL:
    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            sslmode='require'
        )
        # Teste rápido
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        print(f"✅ Conexão com pool estabelecida! PostgreSQL: {cursor.fetchone()[0]}")
        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        print(f"❌ Erro ao criar pool de conexões: {e}")
        db_pool = None
else:
    print("⚠️ DATABASE_URL não encontrada. O aplicativo não terá acesso ao banco de dados.")


def log_message(sender, message_text, profile_data={}):
    """Insere uma mensagem no banco usando pool de conexões."""
    if not db_pool:
        print("⚠️ Banco de dados não disponível. Mensagem não foi salva.")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_log (
                    id SERIAL PRIMARY KEY,
                    sender VARCHAR(10) NOT NULL,
                    message TEXT NOT NULL,
                    user_name VARCHAR(100),
                    role VARCHAR(50),
                    interest_area VARCHAR(100),
                    objective VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE,
                    created_at_sp_str VARCHAR(25)
                );
            """)
            sp_tz = pytz.timezone("America/Sao_Paulo")
            timestamp_sp = datetime.now(sp_tz)
            timestamp_sp_str = timestamp_sp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO chat_log 
                    (sender, message, user_name, role, interest_area, objective, created_at, created_at_sp_str) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                sender,
                message_text,
                profile_data.get('name', ''),
                profile_data.get('role', ''),
                profile_data.get('interestArea', ''),
                profile_data.get('objective', ''),
                timestamp_sp,
                timestamp_sp_str
            ))

        conn.commit()
        print(f"💾 Mensagem de {sender} salva no BD com timestamp SP como string!")

    except Exception as e:
        print(f"❌ Erro ao salvar mensagem: {e}")
        conn.rollback()
    finally:
        db_pool.putconn(conn)


def log_interaction(user_message, bot_reply, profile_data={}):
    """Salva a interação completa usando pool de conexões."""
    if not db_pool:
        print("⚠️ Banco de dados não disponível. Interação não foi salva.")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_interactions (
                    id SERIAL PRIMARY KEY,
                    user_message TEXT,
                    bot_reply TEXT,
                    user_name VARCHAR(100),
                    role VARCHAR(50),
                    interest_area VARCHAR(100),
                    objective VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE,
                    created_at_sp_str VARCHAR(25)
                );
            """)
            sp_tz = pytz.timezone("America/Sao_Paulo")
            timestamp_sp = datetime.now(sp_tz)
            timestamp_sp_str = timestamp_sp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                INSERT INTO chat_interactions 
                    (user_message, bot_reply, user_name, role, interest_area, objective, created_at, created_at_sp_str)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                user_message,
                bot_reply,
                profile_data.get('name', ''),
                profile_data.get('role', ''),
                profile_data.get('interestArea', ''),
                profile_data.get('objective', ''),
                timestamp_sp,
                timestamp_sp_str
            ))
        conn.commit()
        print("💾 Interação (usuário + bot) salva com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao salvar interação: {e}")
        conn.rollback()
    finally:
        db_pool.putconn(conn)


# ============================================================
# 🤖 CONFIGURAÇÃO DO MODELO LIA (Assistente Virtual)
# ============================================================

BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "system_instruction.txt")

with open(file_path, "r", encoding="utf-8") as f:
    SYSTEM_INSTRUCTION = f.read()

# ============================================================
# 📚 RESPOSTAS PRÉ-PROGRAMADAS
# ============================================================

EVENT_INFO = {
    "Onde posso ver os projetos de Ciência de Dados para Negócios?": {
        "text": "Os projetos de Ciência de Dados para Negócios (CDN) estão no 3º andar, sala 307! Lá você confere soluções inovadoras criadas pelos alunos e conhece a LIA, a assistente virtual oficial do evento! 🤖💡",
        "audio_path": "respostas_pre_gravadas/projetos_cdn.mp3"
    },
    "E os trabalhos de Marketing, onde estão?": {
        "text": "Os projetos de Marketing estão no 2º andar, nas salas 202, 203, 206, 208, 209 e 210, além da área do ping pong. São trabalhos cheios de criatividade e comunicação — vale a pena conferir! 🎯✨",
        "audio_path": "respostas_pre_gravadas/projetos_mkt.mp3"
    },
    "Onde encontro os projetos de GNI?": {
        "text": "Os trabalhos de GNI estão distribuídos pelo térreo, 2º e 3º andares. No térreo, a Feira de Empreendedores; no 2º, projetos acadêmicos; e no 3º, LAB Sebrae e projetos especiais. 💼🚀",
        "audio_path": "respostas_pre_gravadas/projetos_gni.mp3"
    },
    "Onde encontro comidas e doces?": {
        "text": "No térreo, área de alimentação! Você encontra Tati Nasi Confeitaria, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom e Cantina das Bentas. Prove delícias e apoie os empreendedores! 🍔🍰🍦",
        "audio_path": "respostas_pre_gravadas/empresas_alimentacao.mp3"
    },
    "Quais empresas estão no evento?": {
        "text": "No térreo, várias empresas e parceiros: Tati Nasi Confeitaria, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom, Cantina das Bentas, Dans Brechó, Anainá Moda Sustentável e outras. Produtos, serviços e ideias incríveis! 🌟🍔🍰",
        "audio_path": "respostas_pre_gravadas/empresas_expondo.mp3"
    },
    "O que é a LIA?": {
        "text": "Sou eu! 😄 Fui criada pelos alunos do 2º semestre de Ciência de Dados para Negócios, sob orientação dos profs. Rômulo Maia e Nathane de Castro. Minha missão é ajudar sua visita e fornecer informações do evento de forma prática e divertida! 🤖💙",
        "audio_path": "respostas_pre_gravadas/o_que_e_lia.mp3"
    }
}


# Lista de modelos possíveis para o chat
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# Escolhe um modelo aleatório a cada inicialização
selected_model = random.choice(GEMINI_MODELS)
print(f"🤖 Modelo selecionado para esta sessão: {selected_model}")

# Cria o modelo Gemini configurado com as instruções da LIA
model = genai.GenerativeModel(
    model_name=selected_model,
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048
    },
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ],
)

# Inicia o histórico de conversa
convo = model.start_chat(history=[])

# ============================================================
# 🔊 FUNÇÕES DE CONVERSÃO DE TEXTO EM ÁUDIO (TTS) COM RETRY
# ============================================================

# Variáveis globais para o rodízio de chaves de forma segura
current_key_index = 0
key_lock = threading.Lock()

MAX_RETRIES = 3  # Tentativas por chave
BACKOFF_BASE = 2  # Segundos base para backoff exponencial


def get_gemini_tts_audio_data(text_to_speak):
    """
    Gera áudio com a API Gemini usando rodízio de chaves, retry por chave e fallback gTTS.
    """
    global current_key_index
    
    payload = {
        "contents": [{"parts": [{"text": f"Fale de forma natural e clara: {text_to_speak}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}
        },
        "model": "gemini-2.5-flash-tts"
    }
    headers = {'Content-Type': 'application/json'}

    with key_lock:
        start_index = current_key_index

    for i in range(len(API_KEYS)):
        key_index_to_try = (start_index + i) % len(API_KEYS)
        key = API_KEYS[key_index_to_try]

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={key}"
                response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=90)
                response.raise_for_status()

                result = response.json()
                part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0]
                audio_data = part.get('inlineData', {}).get('data')

                if audio_data:
                    print(f"✅ Áudio gerado via Gemini (chave {key[:8]}...) [tentativa {attempt}]")
                    with key_lock:
                        current_key_index = (key_index_to_try + 1) % len(API_KEYS)
                    return audio_data

            except requests.exceptions.HTTPError as http_err:
                if response.status_code == 429:
                    print(f"⚠️ Limite da chave {key[:8]} atingido. Tentando próxima chave...")
                    break  # Passa para a próxima chave
                else:
                    print(f"⚠️ Erro HTTP com chave {key[:8]} (tentativa {attempt}): {http_err}")
            except requests.exceptions.RequestException as req_err:
                print(f"⚠️ Erro de requisição com chave {key[:8]} (tentativa {attempt}): {req_err}")
            except Exception as e:
                print(f"⚠️ Outro erro com chave {key[:8]} (tentativa {attempt}): {e}")

            # Backoff exponencial com jitter antes de tentar novamente
            sleep_time = BACKOFF_BASE ** attempt + random.uniform(0, 1)
            print(f"⏱ Esperando {sleep_time:.1f}s antes da próxima tentativa...")
            time.sleep(sleep_time)

    # Se todas as chaves falharem
    print("⚠️ Todas as chaves Gemini falharam. Usando fallback gTTS...")
    return get_gtts_audio_data(text_to_speak)


def get_gtts_audio_data(text_to_speak):
    """Fallback local usando gTTS."""
    try:
        print("Usando gTTS como alternativa...")
        tts = gTTS(text=text_to_speak, lang="pt-br")
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"ERRO ao gerar TTS com gTTS: {e}")
        return None


def get_tts_audio_data(text_to_speak):
    """Função principal que tenta Gemini e usa gTTS se falhar."""
    try:
        return get_gemini_tts_audio_data(text_to_speak)
    except Exception as e:
        print(f"Erro inesperado no Gemini TTS: {e}")
        return get_gtts_audio_data(text_to_speak)

   
def transcrever_audio_base64(audio_base64):
    try:
        # Verifica se veio algo
        if not audio_base64:
            raise ValueError("O áudio recebido está vazio.")

        # Decodifica o base64 em bytes
        audio_bytes = base64.b64decode(audio_base64)

        # Converte o áudio para WAV (SpeechRecognition entende melhor WAV)
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)

        # Usa SpeechRecognition para transcrever
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            texto = recognizer.recognize_google(audio_data, language="pt-BR")
        
        return texto

    except Exception as e:
        print(f"Erro na transcrição do áudio: {e}")
        return "[Falha na transcrição]"


# ============================================================
# 🌐 APLICAÇÃO FLASK
# ============================================================

app = Flask(__name__)
CORS(app)



@app.route('/chat', methods=['POST'])
def chat():
    bot_reply_text = ""
    audio_base64 = None
    tts_is_enabled = False
    user_message_to_log = None
    profile = {}
    session_id = None

    try:
        # Extrair perfil e sessionId
        if 'audio_file' in request.files:
            audio_file = request.files['audio_file']
            profile_str = request.form.get('profile', '{}')
            try:
                profile = json.loads(profile_str)
            except json.JSONDecodeError:
                profile = {}
            session_id = profile.get('sessionId')

            if not session_id:
                return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

            # Buscar ou criar conversa ativa
            with convo_lock:
                if session_id not in active_conversations:
                    active_conversations[session_id] = model.start_chat(history=[])
                convo = active_conversations[session_id]

            # Processa áudio
            audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_file.read()}]
            response = convo.send_message(["Responda ao que foi dito neste áudio.", audio_parts[0]])
            audio_bytes = audio_parts[0]["data"]
            audio_base64_transcript = base64.b64encode(audio_bytes).decode("utf-8")
            texto = transcrever_audio_base64(audio_base64_transcript)

            user_message_to_log = f"[ÁUDIO ENVIADO]: {texto}"
            bot_reply_text = response.text
            tts_is_enabled = True

        elif request.is_json:
            data = request.json
            tts_is_enabled = data.get('tts_enabled', False)
            profile = data.get('profile', {})
            session_id = profile.get('sessionId')

            if not session_id:
                return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

            with convo_lock:
                if session_id not in active_conversations:
                    active_conversations[session_id] = model.start_chat(history=[])
                convo = active_conversations[session_id]

            if 'preset_question' in data:
                question = data['preset_question']
                user_message_to_log = f"[PRESET]: {question}"
                info = EVENT_INFO.get(question)
                if info:
                    bot_reply_text = info["text"]
                    if tts_is_enabled:
                        try:
                            with open(info["audio_path"], "rb") as f:
                                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
                        except FileNotFoundError:
                            audio_base64 = get_tts_audio_data(bot_reply_text)
                else:
                    convo.send_message(question)
                    bot_reply_text = convo.last.text

            elif 'message' in data:
                user_message = data['message']
                user_message_to_log = user_message
                convo.send_message(user_message)
                bot_reply_text = convo.last.text

        # Lógica de log (assumindo log_interaction)
        if user_message_to_log:
            log_interaction(user_message_to_log, bot_reply_text, profile)

        # Gera TTS se necessário
        if audio_base64 is None and tts_is_enabled and bot_reply_text:
            audio_base64 = get_tts_audio_data(bot_reply_text)

        return jsonify({
            "reply": bot_reply_text,
            "audioData": audio_base64,
            "presetQuestions": list(EVENT_INFO.keys())
        })

    except Exception as e:
        print(f"Erro no /chat: {e}")
        traceback.print_exc()
        return jsonify({"error": "Erro interno no servidor."}), 500

@app.route('/suggest-topic', methods=['GET'])
def suggest_topic():
    """Sugere um tópico curto para iniciar uma conversa."""
    try:
        response = model.generate_content(f"Sugira uma pergunta breve e divertida que pareça vinda do próprio usuário, para começar a conversar sobre o evento Metaday. Leve em consideração o prompt do sustem completo com info {SYSTEM_INSTRUCTION}")
        return jsonify({"topic": response.text.strip()})
    except Exception as e:
        return jsonify({"error": f"Erro ao sugerir tópico: {e}"}), 500


@app.route('/summarize', methods=['POST'])
def summarize():
    """Resume o histórico atual da conversa."""
    try:
        # 1. Obter o JSON enviado pelo frontend
        data = request.json
        session_id = data.get('profile', {}).get('sessionId')

        if not session_id:
            return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

        # 2. Encontrar a conversa correta
        convo = None
        with convo_lock:
            if session_id in active_conversations:
                convo = active_conversations[session_id]

        # 3. Usar a 'convo' específica da sessão
        if not convo or not convo.history:
            return jsonify({"summary": "Ainda não há histórico de conversa."})
        
        # O resto da sua lógica original, mas usando a 'convo' correta
        formatted = "\n".join(
            f"{'Usuário' if m.role == 'user' else 'Assistente'}: {m.parts[0].text}"
            for m in convo.history if m.parts and hasattr(m.parts[0], 'text')
        )
        prompt = f"Resuma a conversa em português, de forma breve e objetiva:\n\n{formatted}"
        response = model.generate_content(prompt)
        return jsonify({"summary": response.text})
        
    except Exception as e:
        return jsonify({"error": f"Erro ao resumir: {e}"}), 500

@app.route('/restart', methods=['POST'])
def restart():
    """Reinicia a conversa de uma sessão específica."""
    try:
        # O frontend deve enviar o profile com sessionId
        data = request.json
        session_id = data.get('profile', {}).get('sessionId')

        if not session_id:
            return jsonify({"error": "Nenhum ID de sessão fornecido."}), 400

        # Limpa a sessão específica de forma thread-safe
        with convo_lock:
            if session_id in active_conversations:
                del active_conversations[session_id]
                print(f"Sessão {session_id} reiniciada.")

        return jsonify({"status": "success", "message": f"Conversa da sessão {session_id} reiniciada."})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro ao reiniciar: {e}"}), 500



@app.route('/get-audio', methods=['POST'])
def get_audio():
    """Rota simples para converter um texto em áudio."""
    try:
        data = request.json
        text_to_speak = data.get('text')

        if not text_to_speak:
            return jsonify({"error": "Nenhum texto fornecido."}), 400

        # Reutiliza a função TTS existente
        audio_base64 = get_tts_audio_data(text_to_speak)
        
        return jsonify({"audioData": audio_base64})

    except Exception as e:
        print(f"Erro no /get-audio: {e}")
        traceback.print_exc()
        return jsonify({"error": "Erro interno no servidor."}), 500

# ============================================================
# 🚀 EXECUÇÃO
# ============================================================

# ROTA CORRIGIDA PARA ATIVOS (ASSETS)
# REMOVENDO A MANIPULAÇÃO AGRESSIVA DE CACHE HTTP
@app.route("/assets/<path:filename>")
def assets(filename):
    # A remoção do cabeçalho de Cache-Control agressivo aqui
    # permite que o "cache busting" do JavaScript funcione corretamente.
    return send_from_directory("assets", filename)

# Serve o index.html da raiz
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# Serve qualquer outro arquivo estático da raiz (CSS, JS, imagens, etc)
@app.route('/<path:filename>')
def serve_static_files(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)