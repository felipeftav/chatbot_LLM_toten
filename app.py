import os
import json
import requests
import base64
import io
import traceback
from gtts import gTTS
from flask import Flask, request, jsonify, render_template, make_response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai


# ============================================================
# 🔧 CONFIGURAÇÕES INICIAIS
# ============================================================

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

if DATABASE_URL:
    try:
        # Tenta conectar ao BD usando a URL
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conexão com o banco de dados PostgreSQL estabelecida com sucesso!")
        
        # Exemplo: Executar uma query de teste (opcional)
        # cursor.execute("SELECT version();")
        # db_version = cursor.fetchone()
        # print(f"Versão do PostgreSQL: {db_version[0]}")
        
    except Exception as e:
        print(f"❌ Erro ao conectar ao banco de dados: {e}")
        # Uma estratégia comum é permitir que o app inicie mesmo sem o BD,
        # mas desativar as funcionalidades que dependem dele.
        conn = None 
        cursor = None
else:
    print("⚠️ DATABASE_URL não encontrada. O aplicativo não terá acesso ao banco de dados.")
    conn = None 
    cursor = None

def log_message(sender, message_text):
    """Insere uma mensagem no banco de dados."""
    if not conn or not cursor:
        print("⚠️ Banco de dados não disponível. Mensagem não foi salva.")
        return
    
    try:
        # Cria a tabela se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_log (
                id SERIAL PRIMARY KEY,
                sender VARCHAR(10) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        
        # Insere a mensagem
        cursor.execute(
            "INSERT INTO chat_log (sender, message) VALUES (%s, %s);",
            (sender, message_text)
        )
        conn.commit()
        print(f"💾 Mensagem de {sender} salva no BD!")
    except Exception as e:
        print(f"❌ Erro ao salvar mensagem: {e}")
        conn.rollback()



# ============================================================
# 🤖 CONFIGURAÇÃO DO MODELO LIA (Assistente Virtual)
# ============================================================

SYSTEM_INSTRUCTION = """
Você é LIA, a assistente virtual oficial do evento Metaday.
Sua missão é ajudar os participantes com informações sobre o evento de forma amigável, clara e entusiasmada.

--- REGRAS GERAIS ---
- Seja sempre prestativa e positiva.
- Responda de forma concisa e direta.
- Use emojis para deixar a conversa mais leve.
- Fale apenas sobre o Metaday. Se não souber, diga que vai verificar com a organização.
- Não invente informações.

--- INFORMAÇÕES SOBRE OS PROJETOS (PI) ---

**Gestão de Negócios e Inovação (GNI)**
- 1º Semestre (manhã e noite): "Número Musical" – Prof. Clayton Alves Cunha.
- 2º Semestre (noite): Prof. Clayton Capellari.
- 4º Semestre (noite): "Pitchs e Impressora 3D" – Prof. Sidioney Silveira. Salas 204 e Maker.
- 6º Semestre (manhã e noite): "Consultoria" – Prof. Fátima Leone. Sala multiuso do térreo.

**Marketing (MKT)**
- 1º Semestre (manhã): Prof. Ana Lucia. Salas 209, 206 e sala de estágio.
- 3º Semestre (manhã e noite): Prof. Ana Lucia. Salas 206 e 207.
- 4º Semestre (noite): "Podcast" – Prof. Isabel. Aquário, 2º andar.

**Ciência de Dados para Negócios (CDN)**
- 1º Semestre (tarde): "Dashboard" – Prof. Nathane de Castro.
- 2º Semestre (tarde): "Assistente Virtual LIA" – Prof. Carlos Bezerra. (Projeto da própria LIA!)

Regras:
- Se o local não for informado, diga que deve confirmar com a organização.
- Se perguntarem sobre “LIA”, explique que é você, criada pelos alunos de Ciência de Dados. 😄
"""

# Cria o modelo Gemini configurado com as instruções da LIA
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION,
    generation_config={"temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048},
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
# 📚 RESPOSTAS PRÉ-PROGRAMADAS
# ============================================================

EVENT_INFO = {
    "Quais os projetos de GNI?": {
        "text": "O curso de Gestão de Negócios e Inovação (GNI) terá várias apresentações, como o 'Número Musical' do 1º semestre, 'pitchs e demonstração de impressora 3D' do 4º semestre, e 'atendimento de consultoria' do 6º semestre. Quer saber o local de algum específico?",
        "audio_path": "respostas_pre_gravadas/projetos_gni.mp3"
    },
    "Onde encontro os projetos de Marketing?": {
        "text": "Os projetos de Marketing (MKT) estão espalhados pelo evento! Temos apresentações nas salas 209, 206, 207 e um Podcast sendo gravado no Aquário do 2º andar. Qual semestre você procura?",
        "audio_path": "respostas_pre_gravadas/projetos_mkt.mp3"
    },
    "O que é o projeto da LIA?": {
        "text": "Esse projeto sou eu mesma! Fui desenvolvida pela turma de Ciência de Dados para Negócios para ser a assistente virtual oficial do Metaday e ajudar todos vocês com informações sobre o evento!",
        "audio_path": "respostas_pre_gravadas/o_que_e_lia.mp3"
    },
    "Onde será a apresentação de Pitch e Impressora 3D?": {
        "text": "A apresentação de pitchs com demonstração de impressora 3D, do 4º semestre de GNI, acontecerá na sala 204 e na sala maker. Parece bem interessante!",
        "audio_path": "respostas_pre_gravadas/pitch_impressora.mp3"
    },
    "Tem algum projeto de consultoria?": {
        "text": "Sim! Os alunos do 6º semestre de GNI, da turma da manhã, estarão oferecendo um atendimento de consultoria na sala multiuso do térreo. É uma ótima oportunidade!",
        "audio_path": "respostas_pre_gravadas/projeto_consultoria.mp3"
    },
    "Onde vai ser o podcast?": {
        "text": "O podcast está sendo gravado pelos alunos do 4º semestre de Marketing no Aquário do 2º andar. Vale a pena conferir!",
        "audio_path": "respostas_pre_gravadas/onde_e_podcast.mp3"
    }
}

# ============================================================
# 🔊 FUNÇÕES DE CONVERSÃO DE TEXTO EM ÁUDIO (TTS)
# ============================================================

def get_gemini_tts_audio_data(text_to_speak):
    """Gera áudio com a API de TTS do Gemini usando múltiplas chaves (fallback automático)."""
    payload = {
        "contents": [{"parts": [{"text": f"Fale de forma natural e clara, como uma assistente prestativa: {text_to_speak}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}
        },
        "model": "gemini-2.5-flash-preview-tts"
    }
    headers = {'Content-Type': 'application/json'}

    for key in API_KEYS:
        try:
            print(f"Tentando gerar áudio com a chave {key[:8]}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={key}"
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            response.raise_for_status()

            result = response.json()
            part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0]
            audio_data = part.get('inlineData', {}).get('data')

            if audio_data:
                print("✅ Áudio gerado com sucesso via Gemini!")
                return audio_data
        except Exception as e:
            print(f"⚠️ Erro com a chave {key[:8]}: {e}")
    
    raise RuntimeError("🚫 Todas as chaves de API falharam.")

def get_gtts_audio_data(text_to_speak):
    """Fallback local usando gTTS (voz menos natural, mas garantida)."""
    try:
        print("Usando gTTS como alternativa...")
        tts = gTTS(text=f"Fale de forma natural e clara: {text_to_speak}", lang="pt-br")
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"ERRO ao gerar TTS com gTTS: {e}")
        return None

def get_tts_audio_data(text_to_speak):
    """Função principal que tenta o Gemini TTS e usa gTTS se falhar."""
    try:
        return get_gemini_tts_audio_data(text_to_speak)
    except Exception as e:
        print(f"Erro no Gemini TTS: {e}")
        return get_gtts_audio_data(text_to_speak)

# ============================================================
# 🌐 APLICAÇÃO FLASK
# ============================================================

app = Flask(__name__)
CORS(app)

# @app.route('/chat', methods=['POST'])
# def chat():
#     """Rota principal do chatbot LIA."""
#     try:
#         bot_reply_text = ""
#         audio_base64 = None
#         tts_is_enabled = False

#         # Caso o usuário envie áudio
#         if 'audio_file' in request.files:
#             audio_file = request.files['audio_file']
#             audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_file.read()}]
#             response = convo.send_message(["Responda ao que foi dito neste áudio.", audio_parts[0]])
#             bot_reply_text = response.text
#             tts_is_enabled = True

#         # Caso o usuário envie JSON
#         elif request.is_json:
#             data = request.json
#             tts_is_enabled = data.get('tts_enabled', False)

#             # Pergunta pré-programada
#             if 'preset_question' in data:
#                 question = data['preset_question']
#                 info = EVENT_INFO.get(question)
#                 if info:
#                     bot_reply_text = info["text"]
#                     if tts_is_enabled:
#                         try:
#                             with open(info["audio_path"], "rb") as f:
#                                 audio_base64 = base64.b64encode(f.read()).decode('utf-8')
#                         except FileNotFoundError:
#                             audio_base64 = get_tts_audio_data(bot_reply_text)
#                 else:
#                     bot_reply_text = "Desculpe, não tenho uma resposta para essa pergunta."

#             # Mensagem normal
#             elif 'message' in data:
#                 user_message = data['message']
#                 convo.send_message(user_message)
#                 bot_reply_text = convo.last.text

#         # Gera áudio se o TTS estiver ativo
#         if audio_base64 is None and tts_is_enabled and bot_reply_text:
#             audio_base64 = get_tts_audio_data(bot_reply_text)

#         return jsonify({
#             "reply": bot_reply_text,
#             "audioData": audio_base64,
#             "presetQuestions": list(EVENT_INFO.keys())
#         })

#     except Exception as e:
#         print(f"Erro no /chat: {e}")
#         traceback.print_exc()
#         return jsonify({"error": "Erro interno no servidor."}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Rota principal do chatbot LIA, agora com log no BD."""
    bot_reply_text = ""
    audio_base64 = None
    tts_is_enabled = False
    user_message_to_log = None # Variável para capturar a mensagem do usuário

    try:
        # Caso o usuário envie áudio
        if 'audio_file' in request.files:
            audio_file = request.files['audio_file']
            audio_parts = [{"mime_type": audio_file.mimetype, "data": audio_file.read()}]
            
            # Não logamos o áudio, mas sim a transcrição ou a intenção (a resposta do LLM)
            response = convo.send_message(["Responda ao que foi dito neste áudio.", audio_parts[0]])
            
            # O texto da resposta do bot é o que será logado
            user_message_to_log = "[ÁUDIO ENVIADO]" # Marca para o log
            bot_reply_text = response.text
            tts_is_enabled = True # Assume TTS ativado para áudio

        # Caso o usuário envie JSON (Texto ou Preset)
        elif request.is_json:
            data = request.json
            tts_is_enabled = data.get('tts_enabled', False)

            # Pergunta pré-programada
            if 'preset_question' in data:
                question = data['preset_question']
                user_message_to_log = f"[PRESET]: {question}" # Loga como preset
                info = EVENT_INFO.get(question)
                
                if info:
                    bot_reply_text = info["text"]
                    if tts_is_enabled:
                        try:
                            # Tenta ler o áudio pré-gravado
                            with open(info["audio_path"], "rb") as f:
                                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
                        except FileNotFoundError:
                            # Se não encontrar o arquivo, gera o áudio na hora
                            audio_base64 = get_tts_audio_data(bot_reply_text)
                else:
                    # Se o preset não existir no dict, envia ao LLM como fallback
                    convo.send_message(question)
                    bot_reply_text = convo.last.text

            # Mensagem normal de texto
            elif 'message' in data:
                user_message = data['message']
                user_message_to_log = user_message # Loga a mensagem do usuário
                convo.send_message(user_message)
                bot_reply_text = convo.last.text

        # Lógica de Log (Salva a interação após a resposta ser gerada)
        if user_message_to_log:
            log_message('user', user_message_to_log)
            log_message('bot', bot_reply_text)

        # Gera áudio se o TTS estiver ativo e ainda não tiver sido gerado
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
        response = model.generate_content("Sugira um tópico divertido e curto para começar uma conversa.")
        return jsonify({"topic": response.text.strip()})
    except Exception as e:
        return jsonify({"error": f"Erro ao sugerir tópico: {e}"}), 500

@app.route('/summarize', methods=['POST'])
def summarize():
    """Resume o histórico atual da conversa."""
    try:
        if not convo.history:
            return jsonify({"summary": "Ainda não há histórico de conversa."})
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
    """Reinicia a conversa (limpa o histórico)."""
    try:
        convo.history.clear()
        return jsonify({"status": "success", "message": "Conversa reiniciada."})
    except Exception as e:
        return jsonify({"error": f"Erro ao reiniciar: {e}"}), 500

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