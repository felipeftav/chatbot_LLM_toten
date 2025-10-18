import os
import requests
import json
from dotenv import load_dotenv
import base64
import time

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não foi configurada. Verifique seu arquivo .env.")

# URL da API de TTS do Gemini
TTS_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GEMINI_API_KEY}"

# --- Dicionário de Perguntas e Respostas ---
# (O mesmo dicionário que você atualizou no app.py)
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

def generate_and_save_audio(text_to_speak, output_path):
    """Chama a API de TTS do Gemini e salva o áudio em um arquivo."""
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
        print(f"Gerando áudio para: '{output_path}'...")
        response = requests.post(TTS_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        result = response.json()
        part = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0]
        audio_data_base64 = part.get('inlineData', {}).get('data')

        if not audio_data_base64:
            raise ValueError("Nenhum dado de áudio recebido da API.")

        # Decodifica o base64 para bytes
        audio_bytes = base64.b64decode(audio_data_base64)

        # Garante que o diretório de saída exista
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Salva os bytes decodificados no arquivo de áudio
        with open(output_path, 'wb') as audio_file:
            audio_file.write(audio_bytes)

        print(f"✅ Áudio salvo com sucesso em '{output_path}'!")
        return True

    except Exception as e:
        print(f"❌ ERRO ao gerar áudio para '{output_path}': {e}")
        return False

# --- Script Principal ---
if __name__ == "__main__":
    print("--- Iniciando Geração de Áudios Pré-gravados ---")
    total_files = len(EVENT_INFO)
    success_count = 0

    # Itera sobre cada item no dicionário EVENT_INFO
    for question, info in EVENT_INFO.items():
        text = info["text"]
        path = info["audio_path"]
        
        if generate_and_save_audio(text, path):
            success_count += 1
        
        # Pausa para evitar exceder limites da API (opcional, mas recomendado)
        time.sleep(35) 

    print("\n--- Processo Concluído ---")
    print(f"Resumo: {success_count} de {total_files} arquivos de áudio gerados com sucesso.")