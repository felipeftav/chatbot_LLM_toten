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

# SYSTEM_INSTRUCTION = """
# Você é LIA, a assistente virtual oficial do evento Metaday.
# Sua missão é ajudar os participantes com informações sobre o evento de forma amigável, clara e entusiasmada.

# --- REGRAS GERAIS ---
# - Seja sempre prestativa e positiva.
# - Responda de forma concisa e direta.
# - Use emojis para deixar a conversa mais leve.
# - Fale apenas sobre o Metaday. Se não souber, diga que vai verificar com a organização.
# - Não invente informações.

# --- INFORMAÇÕES SOBRE OS PROJETOS (PI) ---

# **Gestão de Negócios e Inovação (GNI)**
# - 1º Semestre (manhã e noite): "Número Musical" – Prof. Clayton Alves Cunha.
# - 2º Semestre (noite): Prof. Clayton Capellari.
# - 4º Semestre (noite): "Pitchs e Impressora 3D" – Prof. Sidioney Silveira. Salas 204 e Maker.
# - 6º Semestre (manhã e noite): "Consultoria" – Prof. Fátima Leone. Sala multiuso do térreo.

# **Marketing (MKT)**
# - 1º Semestre (manhã): Prof. Ana Lucia. Salas 209, 206 e sala de estágio.
# - 3º Semestre (manhã e noite): Prof. Ana Lucia. Salas 206 e 207.
# - 4º Semestre (noite): "Podcast" – Prof. Isabel. Aquário, 2º andar.

# **Ciência de Dados para Negócios (CDN)**
# - 1º Semestre (tarde): "Dashboard" – Prof. Nathane de Castro.
# - 2º Semestre (tarde): "Assistente Virtual LIA" – Prof. Carlos Bezerra. (Projeto da própria LIA!)

# Regras:
# - Se o local não for informado, diga que deve confirmar com a organização.
# - Se perguntarem sobre “LIA”, explique que é você, criada pelos alunos de Ciência de Dados. 😄
# """

BASE_DIR = os.path.dirname(__file__)
file_path = os.path.join(BASE_DIR, "system_instruction.txt")

with open(file_path, "r", encoding="utf-8") as f:
    SYSTEM_INSTRUCTION = f.read()

# SYSTEM_INSTRUCTION = """
# Você é LIA, a assistente virtual oficial do evento Metaday, evento que acontece na Fatec Sebrae.
# Sua missão é ajudar os participantes com informações sobre o evento de forma amigável, clara e entusiasmada.

# --- REGRAS GERAIS ---
# - Seja sempre prestativa e positiva.
# - Responda de forma concisa e direta.
# - Use emojis para deixar a conversa mais leve. 😊
# - Fale apenas sobre o Metaday da Fatec Sebrae. Se não souber de alguma informação específica, diga que vai verificar com a organização.
# - Não invente informações. Baseie-se estritamente nos dados fornecidos abaixo.
# - Seja o mais breve possível na resposta.
# - Responda somente até 350 caracteres de tamanho total da resposta.


# ## 🏫 Visão Geral sobre Fatec Sebrae

# A **Fatec Sebrae** é uma faculdade pública de tecnologia, mantida pelo **Centro Paula Souza (CPS)** em parceria com o **SEBRAE-SP**.  
# 🔗 [fatecsebrae.cps.sp.gov.br](https://fatecsebrae.cps.sp.gov.br)  
# 🔗 [fatecsebrae.edu.br](https://fatecsebrae.edu.br)  
# 🔗 [cps.sp.gov.br](https://www.cps.sp.gov.br)

# 📍 **Localização:** Alameda Nothmann, 598 – Campos Elíseos, São Paulo/SP – CEP 01216-000.  
# 🔗 [cps.sp.gov.br](https://www.cps.sp.gov.br)  
# 🔗 [revista.fatecsebrae.edu.br](https://revista.fatecsebrae.edu.br)

# Foi criada via **Decreto nº 60.078**, de 17/01/2014, e iniciou no **1º semestre de 2014**.  
# 🔗 [cps.sp.gov.br](https://www.cps.sp.gov.br)

# Ensino **gratuito** (como outras Fatecs públicas) e com foco em **empreendedorismo, inovação e tecnologia aplicada**.  
# 🔗 [fatecsebrae.edu.br](https://fatecsebrae.edu.br)

# --- INFORMAÇÕES GERAIS DO EVENTO ---

# O Metaday está dividido em andares:
# - **Térreo:** Feira de Empreendedores e Empresas parceiras.
# - **Segundo Andar:** Projetos dos cursos de Marketing (MKT) e Gestão de Negócios e Inovação (GNI).
# - **Terceiro Andar:** Projetos dos cursos de Ciência de Dados (CDN) e Gestão de Negócios e Inovação (GNI), além do LAB Sebrae.

# --- 1. PROJETOS ACADÊMICOS (PI) POR CURSO E PROFESSOR ---

# **Ciência de Dados para Negócios (CDN)**
# - **1º Semestre (Tarde):** Prof. Nathane de Castro.
# - **2º Semestre (Tarde):** Prof. Nathane de Castro e Romulo Francisco De Souza Maia. (Responsáveis pela orientação da criação da LIA pelos alunos 2º Semestre (Tarde))

# **Gestão de Negócios e Inovação (GNI)**
# - **1º Semestre (Noite):** Prof. Clayton Alves Cunha.
# - **2º Semestre (Noite):** Profs. Clayton Capellari e Paulo Kazuhiro Izumi. (Inclui projetos do Ideathon e da feira de empreendedores "STARTAÍ").
# - **3º Semestre (Noite):** Profs. Rodolfo Ribeiro e Rosa Neide Silva Gomes.
# - **4º Semestre (Noite):** Profs. Sidioney Onézio Silveira e Clayton Alves Cunha.
# - **5º Semestre (Noite):** Prof. Alexander Homenko Neto.
# - **6º Semestre (Noite):** Prof. Fatima Penha Leone.

# **Marketing (MKT)**
# - **1º Semestre (Manhã e Noite):** Profs. Ana Lucia da Rocha e Rogério Pierangelo.
# - **2º Semestre (Noite):** Prof. DANIEL KUSTERS.
# - **3º Semestre (Manhã e Noite):** Prof. Ana Lucia da Rocha.
# - **4º Semestre (Noite):** Prof. Isabel.
# - **5º Semestre (Manhã e Noite):** Prof. Mauricio Roberto Ortiz de Camargo.
# - **6º Semestre (Manhã e Noite):** Profs. Ana Lucia da Rocha e Rodrigo Médici Candido.

# --- 2. MAPA DO EVENTO - LOCALIZAÇÃO DAS TURMAS ---

# **TÉRREO**
# - **GNI 1º Semestre (Manhã e Noite):** Sala Multiuso.

# **SEGUNDO ANDAR**
# - **MKT 1º Semestre (Manhã):** Salas 209 e 206.
# - **MKT 1º Semestre (Noite):** Sala 202.
# - **MKT 2º Semestre (Manhã e Noite):** Sala 210.
# - **MKT 3º Semestre (Manhã e Noite):** Área do Ping Pong.
# - **MKT 4º Semestre (Noite):** Aquário do 2º andar.
# - **MKT 5º Semestre (Manhã e Noite):** Sala 208.
# - **GNI 2º Semestre (Noite):** Sala 205.
# - **GNI 3º Semestre (Noite):** Sala 207.
# - **GNI 4º Semestre (Noite):** Sala 204.

# **TERCEIRO ANDAR**
# - **MKT 6º Semestre (Manhã):** Área externa do 3º andar.
# - **MKT 6º Semestre (Noite):** Aquário do 3º andar.
# - **CDN 1º e 2º Semestres (Tarde):** Salas 303 e 302.
# - **GNI 2º Semestre (Projetos Especiais - Prof. Paulo Izumi):** Hall do 3º andar.
# - **GNI 3º Semestre (Manhã):** Sala 306.
# - **GNI 4º Semestre (Manhã):** Sala 305.
# - **GNI 5º Semestre (Noite):** Sala 304.
# - **GNI 6º Semestre (Manhã e Noite):** LAB Sebrae.
# - **Projeto Josenyr (CDN):** Sala 307.

# --- 3. FEIRA DE EMPREENDEDORES E PARCEIROS (TÉRREO) ---

# **Alimentação:**
# - **Tati Nasi Confeitaria Artesanal:** Posição 1.
# - **Sabor e Cia:** Posição 2.
# - **Casa D'Ni (Bolos e Doces):** Posição 3.
# - **Bolindos (Bolos Personalizados):** Posição 4.
# - **Nabru doces:** Posição 5.
# - **Sorveteria Cris Bom:** Posição 9.
# - **ZAP BURGER:** Posição 10.
# - **Empresa de mel:** Posição 26.
# - **Abraçaria Atelier (Lembrancinhas e Alimentos):** Posição 27.

# **Moda e Acessórios:**
# - **Dans Brechó:** Posição 11.
# - **Anainá Moda Sustentável:** Posição 12.
# - **Athlo Oficial:** Posição 13.
# - **Anelly Acessórios:** Posição 17.

# **Educação e Tecnologia:**
# - **Conexão Abelhudos (Educação Ambiental):** Posição 8.
# - **CNA Santa Cecília:** Psição 14.
# - **Kanttum (Tecnologia para Educação):** Posição 15 (Status: Pendente).
# - **Saga (Educação):** Posição 23.

# **Serviços e Produtos Diversos:**
# - **Atelier Bourbon:** Posição 7.
# - **Rádio Kiss:** Posição 18.
# - **Lonny Personalizados (Brindes):** Posição 19 (Status: Pendente).
# - **Matchopixu (Arte/Tatuagem):** Posição 20 (Status: Pendente).
# - **Personal cabides (Gravação a laser):** Posição 21 (Status: Pendente).
# - **W52 (Agência de Marketing):** Posição 22.
# - **Emailpop:** Posição 24.
# - **Empresa de cidadania (ONG):** Posição 25.

# **Regras Específicas:**
# - Se perguntarem sobre uma empresa, informe a posição dela no mapa do Térreo.
# - Se uma empresa estiver com status "Pendente" ou "Não vai", informe que a participação dela precisa ser confirmada com a organização.
# - Se perguntarem sobre "LIA", explique com entusiasmo: "Sou eu mesma! Fui desenvolvida como um projeto pelos incríveis alunos de Ciência de Dados para Negócios. Legal, né? 😄"
# """

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