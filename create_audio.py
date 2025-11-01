import os
import requests
import json
from dotenv import load_dotenv
import base64
import time

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEYS")

# Lê todas as chaves de API listadas em GEMINI_API_KEYS (separadas por vírgula)
API_KEYS = [key.strip() for key in os.getenv("GEMINI_API_KEYS", "").split(",") if key.strip()]

if not API_KEYS:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não foi configurada. Verifique seu arquivo .env.")

# URL da API de TTS do Gemini
TTS_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={API_KEYS[0]}"

# --- Dicionário de Perguntas e Respostas ---
# (O mesmo dicionário que você atualizou no app.py)
EVENT_INFO = {
    # "Onde posso ver os projetos de Ciência de Dados para Negócios?": {
    #     "text": "Os projetos de Ciência de Dados para Negócios estão no 3º andar, sala 307! 💡 Lá, os alunos mostram soluções inovadoras e é onde você encontra a LIA — eu! 🤖",
    #     "audio_path": "respostas_pre_gravadas/projetos_cdn.mp3"
    # },
    # "E os trabalhos de Marketing, onde estão?": {
    #     "text": "Os projetos de Marketing estão no 2º andar, nas salas 202, 203, 206, 208, 209, 210 e também na área do ping pong. 🎯 Uma mostra cheia de criatividade e estratégia!",
    #     "audio_path": "respostas_pre_gravadas/projetos_mkt.mp3"
    # },
    # "Onde encontro os projetos de GNI?": {
    #     "text": "Os projetos de Gestão de Negócios e Inovação (GNI) estão espalhados pelo térreo, 2º e 3º andares. 💼 No térreo há a Feira de Empreendedores, e nos outros andares, os projetos acadêmicos e especiais!",
    #     "audio_path": "respostas_pre_gravadas/projetos_gni.mp3"
    # },
    # "Onde encontro comidas e doces?": {
    #     "text": "A área de alimentação fica no térreo! 🍔🍰 Você encontra Tati Nasi Confeitaria, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom e Cantina das Bentas. Delícias feitas por empreendedores da feira!",
    #     "audio_path": "respostas_pre_gravadas/empresas_alimentacao.mp3"
    # },
    # "Quais empresas estão no evento?": {
    #     "text": "No térreo estão várias empresas e parceiros incríveis! 🌟 Como Tati Nasi, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom, Cantina das Bentas, Dans Brechó, Anainá Moda Sustentável e muitas outras!",
    #     "audio_path": "respostas_pre_gravadas/empresas_expondo.mp3"
    # },
    "O que é a LIA?": {
        "text": "Sou eu! 😄 Fui criada pelos alunos do 2º semestre de Ciência de Dados para Negócios — Felipe Tavares, Thiago Teles, Paulo Futagawa, Thais Nakazone e Riquelme Nichiyama — com orientação dos profs. Rômulo Maia e Nathane de Castro. Minha missão é ajudar você no Meta Day! 💙🤖",
        "audio_path": "respostas_pre_gravadas/o_que_e_lia.mp3"
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